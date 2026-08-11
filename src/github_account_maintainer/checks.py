import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Literal, cast
from urllib.parse import quote

import httpx
from pydantic import Field, JsonValue, field_validator

from github_account_maintainer import __version__
from github_account_maintainer.auth import ClientFactory, CredentialResolver, auth_report_from_response, client_factory
from github_account_maintainer.config import AppConfig, CommunityConfig, MetadataConfig, SecurityConfig, StrictModel
from github_account_maintainer.constants import GITHUB_API_VERSION
from github_account_maintainer.credentials import resolve_credential
from github_account_maintainer.github_api import (
    GitHubApiClient,
    GitHubApiError,
    GitHubTransportError,
    accepted_permissions,
)
from github_account_maintainer.models import (
    CheckOutcome,
    CheckResult,
    CoverageRecord,
    CoverageState,
    Finding,
    RemediationClass,
    RepositoryAuditReport,
    RunStatus,
    Severity,
)
from github_account_maintainer.policy import ResolvedPolicy

type JsonObject = dict[str, object]
type Requirement = Literal["required", "optional"]

METADATA_CHECKS = (
    "metadata.description",
    "metadata.homepage",
    "metadata.topics",
    "metadata.primary_language",
    "metadata.visibility",
    "metadata.archive_state",
)
COMMUNITY_CHECKS = (
    "community.readme",
    "community.license",
    "community.security",
    "community.contributing",
    "community.code_of_conduct",
    "community.support",
    "community.issue_template",
    "community.pull_request_template",
)
SETTINGS_CHECKS = (
    "settings.branch_protection",
    "settings.rulesets",
    "settings.required_reviews",
    "settings.required_status_checks",
    "settings.actions_permissions",
    "settings.actions_workflow_permissions",
)
SECURITY_CHECKS = (
    "security.dependabot_alerts",
    "security.dependabot_security_updates",
    "security.secret_scanning",
    "security.push_protection",
    "security.code_scanning",
    "security.private_vulnerability_reporting",
)
ALL_CHECKS = METADATA_CHECKS + COMMUNITY_CHECKS + SETTINGS_CHECKS + SECURITY_CHECKS

_PROFILE_KEYS = {
    "readme": ("readme",),
    "license": ("license",),
    "contributing": ("contributing",),
    "code_of_conduct": ("code_of_conduct_file", "code_of_conduct"),
    "issue_template": ("issue_template",),
    "pull_request_template": ("pull_request_template",),
}
_COMMUNITY_DOCUMENTATION = "https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions"
_METADATA_DOCUMENTATION = (
    "https://docs.github.com/en/repositories/creating-and-managing-repositories/best-practices-for-repositories"
)
_RULES_DOCUMENTATION = "https://docs.github.com/en/rest/repos/rules"
_BRANCH_PROTECTION_DOCUMENTATION = "https://docs.github.com/en/rest/branches/branch-protection"
_ACTIONS_DOCUMENTATION = "https://docs.github.com/en/rest/actions/permissions"
_SECURITY_DOCUMENTATION = "https://docs.github.com/en/code-security/security-overview"


class RepositoryAuditTarget(StrictModel):
    repository_id: int
    api_name: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")]
    display_name: str

    @field_validator("api_name")
    @classmethod
    def validate_api_name(cls, value: str) -> str:
        owner, repository = value.split("/", 1)
        if owner in {".", ".."} or repository in {".", ".."}:
            raise ValueError("api_name must contain literal GitHub owner and repository names")
        return value

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name must not be empty")
        return normalized


def audit_repository(
    config: AppConfig,
    target: RepositoryAuditTarget,
    policy: ResolvedPolicy,
    *,
    credential_resolver: CredentialResolver = resolve_credential,
    make_client: ClientFactory = client_factory,
    now: Callable[[], datetime] | None = None,
) -> RepositoryAuditReport:
    if policy.target.repository.casefold() != target.api_name.casefold():
        raise ValueError("Resolved policy target does not match the repository audit target")

    credential = credential_resolver(config.credentials.audit)
    with make_client(credential.secret.get_secret_value(), config.account.github_host) as client:
        user_response = client.get("/user")
        auth_report_from_response(config, credential, user_response)
        return run_repository_checks(
            client,
            target,
            policy,
            credential_source=credential.source,
            now=now,
        )


def run_repository_checks(
    client: GitHubApiClient,
    target: RepositoryAuditTarget,
    policy: ResolvedPolicy,
    *,
    credential_source: str,
    repository_metadata: JsonObject | None = None,
    initial_permissions: tuple[str, ...] = (),
    now: Callable[[], datetime] | None = None,
) -> RepositoryAuditReport:
    clock = now or (lambda: datetime.now(UTC))
    started_at = clock()
    permissions: set[str] = set(initial_permissions)
    results: list[CheckResult] = []
    findings: list[Finding] = []

    try:
        if repository_metadata is None:
            response = client.get(f"/repos/{target.api_name}")
            _record_permissions(response, permissions)
            metadata = _json_object(response)
        else:
            metadata = repository_metadata
        repository_state = _parse_repository_metadata(metadata, target.repository_id)
    except (GitHubApiError, GitHubTransportError, TypeError, ValueError) as error:
        if isinstance(error, GitHubApiError) and error.accepted_permissions:
            permissions.add(error.accepted_permissions)
        coverage_state, outcome = _failure_state(error)
        results.extend(
            _unavailable_result(target, check_id, coverage_state, outcome, "repository metadata was unavailable")
            for check_id in ALL_CHECKS
        )
        return _report(
            target,
            policy,
            credential_source,
            started_at,
            clock(),
            permissions,
            results,
            findings,
        )

    metadata_results, metadata_findings = _evaluate_metadata(
        target,
        policy.settings.metadata,
        repository_state,
        policy.suppressed_checks,
        started_at,
    )
    results.extend(metadata_results)
    findings.extend(metadata_findings)

    community_results, community_findings = _evaluate_community(
        client,
        target,
        policy.settings.community,
        fork=cast(bool, repository_state["fork"]),
        suppressed_checks=policy.suppressed_checks,
        observed_at=started_at,
        permissions=permissions,
    )
    results.extend(community_results)
    findings.extend(community_findings)

    settings_results, settings_findings = _evaluate_settings_and_security(
        client,
        target,
        policy.settings.security,
        repository_state,
        suppressed_checks=policy.suppressed_checks,
        observed_at=started_at,
        permissions=permissions,
    )
    results.extend(settings_results)
    findings.extend(settings_findings)

    return _report(
        target,
        policy,
        credential_source,
        started_at,
        clock(),
        permissions,
        results,
        findings,
    )


def _parse_repository_metadata(payload: JsonObject, expected_id: int) -> JsonObject:
    repository_id = payload.get("id")
    topics = payload.get("topics")
    if repository_id != expected_id:
        raise ValueError("Repository response identity did not match the audit target")
    if not isinstance(topics, list) or any(not isinstance(topic, str) for topic in cast(list[object], topics)):
        raise TypeError("Repository response did not contain a valid topics array")
    for key in ("archived", "fork"):
        if not isinstance(payload.get(key), bool):
            raise TypeError(f"Repository response did not contain a valid {key} value")
    visibility = payload.get("visibility")
    if visibility not in {"public", "private", "internal"}:
        raise TypeError("Repository response did not contain a valid visibility value")
    for key in ("description", "homepage", "language"):
        if payload.get(key) is not None and not isinstance(payload.get(key), str):
            raise TypeError(f"Repository response did not contain a valid {key} value")
    default_branch = payload.get("default_branch")
    if default_branch is not None and not isinstance(default_branch, str):
        raise TypeError("Repository response did not contain a valid default_branch value")
    security_and_analysis = payload.get("security_and_analysis")
    if security_and_analysis is not None and not isinstance(security_and_analysis, dict):
        raise TypeError("Repository response did not contain valid security_and_analysis evidence")
    return payload


def _evaluate_metadata(
    target: RepositoryAuditTarget,
    policy: MetadataConfig,
    payload: JsonObject,
    suppressed_checks: tuple[str, ...],
    observed_at: datetime,
) -> tuple[list[CheckResult], list[Finding]]:
    topics = cast(list[str], payload["topics"])
    checks: tuple[tuple[str, object, JsonValue, Requirement | None], ...] = (
        (
            "metadata.description",
            _present(payload.get("description")),
            {"requirement": policy.description},
            policy.description,
        ),
        ("metadata.homepage", _present(payload.get("homepage")), {"requirement": policy.homepage}, policy.homepage),
        ("metadata.topics", len(topics), {"minimum_count": policy.minimum_topics}, "required"),
        (
            "metadata.primary_language",
            _present(payload.get("language")),
            {"requirement": policy.primary_language},
            policy.primary_language,
        ),
        ("metadata.visibility", payload["visibility"], {"mode": "report_only"}, None),
        ("metadata.archive_state", payload["archived"], {"mode": "report_only"}, None),
    )
    results: list[CheckResult] = []
    findings: list[Finding] = []
    for check_id, raw_current, desired, requirement in checks:
        current = _metadata_current(check_id, raw_current)
        if check_id in suppressed_checks:
            results.append(_suppressed_result(target, check_id, "metadata", current, desired))
            continue
        outcome = _metadata_outcome(check_id, raw_current, requirement, policy.minimum_topics)
        result = _result(
            target,
            check_id,
            "metadata",
            outcome,
            CoverageState.AUDITED,
            current,
            desired,
            "repository metadata field evaluated",
        )
        results.append(result)
        if outcome is CheckOutcome.NONCOMPLIANT:
            findings.append(
                _finding(
                    target,
                    result,
                    observed_at,
                    RemediationClass.APPROVAL_REQUIRED,
                    _METADATA_DOCUMENTATION,
                )
            )
    return results, findings


def _evaluate_community(
    client: GitHubApiClient,
    target: RepositoryAuditTarget,
    policy: CommunityConfig,
    *,
    fork: bool,
    suppressed_checks: tuple[str, ...],
    observed_at: datetime,
    permissions: set[str],
) -> tuple[list[CheckResult], list[Finding]]:
    profile: JsonObject = {}
    profile_state = CoverageState.UNSUPPORTED if fork else CoverageState.AUDITED
    if not fork:
        try:
            response = client.get(f"/repos/{target.api_name}/community/profile")
            _record_permissions(response, permissions)
            profile = _json_object(response)
        except (GitHubApiError, GitHubTransportError, TypeError, ValueError) as error:
            if isinstance(error, GitHubApiError) and error.accepted_permissions:
                permissions.add(error.accepted_permissions)
            profile_state, _outcome = _failure_state(error)

    discovered_paths: set[str] = set()
    contents_state = CoverageState.AUDITED
    for directory in ("", ".github", "docs"):
        try:
            suffix = f"/{directory}" if directory else ""
            response = client.get(f"/repos/{target.api_name}/contents{suffix}")
            _record_permissions(response, permissions)
            discovered_paths.update(_directory_paths(response))
        except GitHubApiError as error:
            if error.accepted_permissions:
                permissions.add(error.accepted_permissions)
            if error.kind == "not_found":
                continue
            state, _outcome = _failure_state(error)
            contents_state = _worse_state(contents_state, state)
        except (GitHubTransportError, TypeError, ValueError) as error:
            state, _outcome = _failure_state(error)
            contents_state = _worse_state(contents_state, state)

    results: list[CheckResult] = []
    findings: list[Finding] = []
    for name in (
        "readme",
        "license",
        "security",
        "contributing",
        "code_of_conduct",
        "support",
        "issue_template",
        "pull_request_template",
    ):
        check_id = f"community.{name}"
        requirement = cast(Requirement, getattr(policy, name))
        desired: dict[str, JsonValue] = {"requirement": requirement}
        local_present = any(_path_matches(name, path) for path in discovered_paths)
        profile_entry = _profile_entry(profile, name)
        inherited = profile_entry is not None and _profile_entry_is_inherited(profile_entry, target.api_name)
        present = local_present or profile_entry is not None
        current: dict[str, JsonValue] = {
            "present": present,
            "source": "repository"
            if local_present
            else "inherited"
            if inherited
            else "github_profile"
            if present
            else None,
        }
        if check_id in suppressed_checks:
            results.append(_suppressed_result(target, check_id, "community", current, desired))
            continue

        relevant_profile = name in _PROFILE_KEYS and not fork
        unavailable_state = contents_state
        if relevant_profile and profile_state in {CoverageState.INACCESSIBLE, CoverageState.FAILED}:
            unavailable_state = _worse_state(unavailable_state, profile_state)
        if present:
            coverage_state = CoverageState.INHERITED if inherited and not local_present else CoverageState.AUDITED
            outcome = CheckOutcome.COMPLIANT if requirement == "required" else CheckOutcome.OBSERVED
            evidence = "community file presence confirmed without reading file content"
        elif unavailable_state is CoverageState.INACCESSIBLE:
            coverage_state = CoverageState.INACCESSIBLE
            outcome = CheckOutcome.INACCESSIBLE
            evidence = "required GitHub content evidence was inaccessible"
        elif unavailable_state is CoverageState.FAILED:
            coverage_state = CoverageState.FAILED
            outcome = CheckOutcome.UNKNOWN
            evidence = "GitHub content evidence could not be evaluated"
        else:
            coverage_state = CoverageState.AUDITED
            outcome = CheckOutcome.NONCOMPLIANT if requirement == "required" else CheckOutcome.OBSERVED
            evidence = "community file presence was not reported"

        result = _result(
            target,
            check_id,
            "community",
            outcome,
            coverage_state,
            current,
            desired,
            evidence,
        )
        results.append(result)
        if outcome is CheckOutcome.NONCOMPLIANT:
            findings.append(
                _finding(
                    target,
                    result,
                    observed_at,
                    RemediationClass.PULL_REQUEST,
                    _COMMUNITY_DOCUMENTATION,
                )
            )
    return results, findings


def _evaluate_settings_and_security(
    client: GitHubApiClient,
    target: RepositoryAuditTarget,
    policy: SecurityConfig,
    repository_state: JsonObject,
    *,
    suppressed_checks: tuple[str, ...],
    observed_at: datetime,
    permissions: set[str],
) -> tuple[list[CheckResult], list[Finding]]:
    results: list[CheckResult] = []
    findings: list[Finding] = []
    default_branch = cast(str | None, repository_state.get("default_branch"))
    visibility = cast(str, repository_state["visibility"])
    archived = cast(bool, repository_state["archived"])
    plan_limited = visibility == "private" and not isinstance(repository_state.get("security_and_analysis"), dict)
    branch_forbidden = CoverageState.UNAVAILABLE_BY_PLAN if plan_limited else CoverageState.INACCESSIBLE

    branch_values: dict[str, tuple[bool | None, CoverageState, JsonValue]] = {}
    if default_branch is None:
        for check_id in SETTINGS_CHECKS[:4]:
            branch_values[check_id] = (None, CoverageState.NOT_APPLICABLE, {"reason": "no_default_branch"})
    else:
        encoded_branch = quote(default_branch, safe="")
        rules, rules_state = _get_array(
            client,
            f"/repos/{target.api_name}/rules/branches/{encoded_branch}",
            permissions,
            not_found=CoverageState.UNSUPPORTED,
            forbidden=branch_forbidden,
        )
        protection, protection_state, classic_protected = _get_branch_protection(
            client,
            target,
            encoded_branch,
            permissions,
            forbidden=branch_forbidden,
        )
        rule_types: set[str] = _rule_types(rules) if rules is not None else set()
        active_rules = len(rules) if rules is not None else None
        branch_values["settings.rulesets"] = (
            active_rules is not None and active_rules > 0,
            rules_state,
            {"active_rule_count": active_rules},
        )
        branch_values["settings.branch_protection"] = _combined_branch_control(
            protection_state,
            classic_protected,
            rules_state,
            active_rules is not None and active_rules > 0,
            {
                "classic_protection": classic_protected,
                "active_rule_count": active_rules,
            },
        )
        classic_reviews = (
            _object_present(protection, "required_pull_request_reviews")
            if protection_state is CoverageState.SUPPORTED
            else None
        )
        branch_values["settings.required_reviews"] = _combined_branch_control(
            protection_state,
            classic_reviews,
            rules_state,
            "pull_request" in rule_types,
            {
                "classic_requirement": classic_reviews,
                "ruleset_requirement": "pull_request" in rule_types if rules is not None else None,
            },
        )
        classic_checks = (
            _required_status_checks_present(protection) if protection_state is CoverageState.SUPPORTED else None
        )
        branch_values["settings.required_status_checks"] = _combined_branch_control(
            protection_state,
            classic_checks,
            rules_state,
            "required_status_checks" in rule_types,
            {
                "classic_requirement": classic_checks,
                "ruleset_requirement": "required_status_checks" in rule_types if rules is not None else None,
            },
        )

    branch_policy = {
        "settings.branch_protection": policy.audit_branch_protection,
        "settings.rulesets": policy.audit_rulesets,
        "settings.required_reviews": policy.audit_required_reviews,
        "settings.required_status_checks": policy.audit_required_status_checks,
    }
    for check_id, enabled_by_policy in branch_policy.items():
        value, state, current = branch_values[check_id]
        result, finding = _feature_result(
            target,
            check_id,
            "settings",
            enabled_by_policy,
            suppressed_checks,
            state,
            current,
            {"enabled": True},
            compliant=value,
            evidence="default-branch protection evidence evaluated without storing branch or rule names",
            observed_at=observed_at,
            severity=Severity.MEDIUM,
            documentation_url=(
                _RULES_DOCUMENTATION if check_id == "settings.rulesets" else _BRANCH_PROTECTION_DOCUMENTATION
            ),
        )
        results.append(result)
        if finding is not None:
            findings.append(finding)

    actions, actions_state = _get_object(
        client,
        f"/repos/{target.api_name}/actions/permissions",
        permissions,
        not_found=CoverageState.UNSUPPORTED,
    )
    actions_current, actions_compliant, actions_state = _actions_policy(actions, actions_state)
    result, finding = _feature_result(
        target,
        "settings.actions_permissions",
        "settings",
        policy.audit_actions_permissions,
        suppressed_checks,
        actions_state,
        actions_current,
        {"enabled_or_disabled": "restricted", "allowed_actions": ["local_only", "selected"], "sha_pinning": True},
        compliant=actions_compliant,
        evidence="repository Actions policy evaluated without storing allowed action names",
        observed_at=observed_at,
        severity=Severity.MEDIUM,
        documentation_url=_ACTIONS_DOCUMENTATION,
    )
    results.append(result)
    if finding is not None:
        findings.append(finding)

    if actions_current.get("enabled") is False and actions_state is CoverageState.SUPPORTED:
        workflow = None
        workflow_state = CoverageState.NOT_APPLICABLE
    else:
        workflow, workflow_state = _get_object(
            client,
            f"/repos/{target.api_name}/actions/permissions/workflow",
            permissions,
            not_found=CoverageState.UNSUPPORTED,
        )
    workflow_current, workflow_compliant, workflow_state = _workflow_policy(workflow, workflow_state)
    result, finding = _feature_result(
        target,
        "settings.actions_workflow_permissions",
        "settings",
        policy.audit_actions_workflow_permissions,
        suppressed_checks,
        workflow_state,
        workflow_current,
        {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False},
        compliant=workflow_compliant,
        evidence="default workflow token permissions evaluated",
        observed_at=observed_at,
        severity=Severity.MEDIUM,
        documentation_url=_ACTIONS_DOCUMENTATION,
    )
    results.append(result)
    if finding is not None:
        findings.append(finding)

    alerts_value, alerts_state = _get_enabled_endpoint(
        client,
        f"/repos/{target.api_name}/vulnerability-alerts",
        permissions,
        payload_enabled=False,
    )
    result, finding = _feature_result(
        target,
        "security.dependabot_alerts",
        "security",
        policy.audit_dependabot,
        suppressed_checks,
        alerts_state,
        {"enabled": alerts_value},
        {"enabled": True},
        compliant=alerts_value,
        evidence="Dependabot alert enablement evaluated",
        observed_at=observed_at,
        severity=Severity.MEDIUM,
        documentation_url=_SECURITY_DOCUMENTATION,
    )
    results.append(result)
    if finding is not None:
        findings.append(finding)

    updates_value, updates_state = _get_enabled_endpoint(
        client,
        f"/repos/{target.api_name}/automated-security-fixes",
        permissions,
        payload_enabled=False,
    )
    result, finding = _feature_result(
        target,
        "security.dependabot_security_updates",
        "security",
        policy.audit_dependabot,
        suppressed_checks,
        updates_state,
        {"enabled": updates_value},
        {"enabled": True},
        compliant=updates_value,
        evidence="Dependabot security-update state evaluated",
        observed_at=observed_at,
        severity=Severity.MEDIUM,
        documentation_url=_SECURITY_DOCUMENTATION,
    )
    results.append(result)
    if finding is not None:
        findings.append(finding)

    security_mapping = (
        ("security.secret_scanning", policy.audit_secret_scanning, "secret_scanning", Severity.HIGH),
        ("security.push_protection", policy.audit_push_protection, "secret_scanning_push_protection", Severity.HIGH),
    )
    for check_id, enabled_by_policy, key, severity in security_mapping:
        value, state = _metadata_security_feature(
            repository_state,
            key,
            missing=CoverageState.UNAVAILABLE_BY_PLAN if plan_limited else CoverageState.UNVERIFIED,
        )
        result, finding = _feature_result(
            target,
            check_id,
            "security",
            enabled_by_policy,
            suppressed_checks,
            state,
            {"enabled": value},
            {"enabled": True},
            compliant=value,
            evidence="GitHub security-and-analysis status evaluated",
            observed_at=observed_at,
            severity=severity,
            documentation_url=_SECURITY_DOCUMENTATION,
        )
        results.append(result)
        if finding is not None:
            findings.append(finding)

    code_value, code_state, code_current = _code_scanning_state(
        client,
        target,
        repository_state,
        permissions,
        archived=archived,
        plan_limited=plan_limited,
    )
    result, finding = _feature_result(
        target,
        "security.code_scanning",
        "security",
        policy.audit_code_scanning,
        suppressed_checks,
        code_state,
        code_current,
        {"configured": True},
        compliant=code_value,
        evidence="code scanning default or advanced analysis evidence evaluated without storing analysis details",
        observed_at=observed_at,
        severity=Severity.HIGH,
        documentation_url=_SECURITY_DOCUMENTATION,
    )
    results.append(result)
    if finding is not None:
        findings.append(finding)

    if visibility != "public":
        private_reporting = None
        private_reporting_state = CoverageState.NOT_APPLICABLE
    else:
        private_payload, private_reporting_state = _get_object(
            client,
            f"/repos/{target.api_name}/private-vulnerability-reporting",
            permissions,
            not_found=CoverageState.UNSUPPORTED,
            unprocessable=CoverageState.NOT_APPLICABLE,
        )
        private_value = private_payload.get("enabled") if private_payload is not None else None
        if private_payload is not None and not isinstance(private_value, bool):
            private_reporting_state = CoverageState.UNVERIFIED
            private_reporting = None
        else:
            private_reporting = cast(bool | None, private_value)
    result, finding = _feature_result(
        target,
        "security.private_vulnerability_reporting",
        "security",
        policy.audit_private_vulnerability_reporting,
        suppressed_checks,
        private_reporting_state,
        {"enabled": private_reporting},
        {"enabled": True},
        compliant=private_reporting,
        evidence="private vulnerability reporting status evaluated",
        observed_at=observed_at,
        severity=Severity.MEDIUM,
        documentation_url=_SECURITY_DOCUMENTATION,
    )
    results.append(result)
    if finding is not None:
        findings.append(finding)
    return results, findings


def _get_object(
    client: GitHubApiClient,
    path: str,
    permissions: set[str],
    *,
    not_found: CoverageState,
    unprocessable: CoverageState = CoverageState.FAILED,
    forbidden: CoverageState = CoverageState.INACCESSIBLE,
) -> tuple[JsonObject | None, CoverageState]:
    try:
        response = client.get(path)
        _record_permissions(response, permissions)
        return _json_object(response), CoverageState.SUPPORTED
    except GitHubApiError as error:
        if error.accepted_permissions:
            permissions.add(error.accepted_permissions)
        if error.status_code == 404:
            return None, not_found
        if error.status_code == 422:
            return None, unprocessable
        if error.kind == "authorization":
            return None, forbidden
        return None, CoverageState.FAILED
    except (GitHubTransportError, TypeError, ValueError):
        return None, CoverageState.FAILED


def _get_array(
    client: GitHubApiClient,
    path: str,
    permissions: set[str],
    *,
    not_found: CoverageState,
    forbidden: CoverageState = CoverageState.INACCESSIBLE,
) -> tuple[list[JsonObject] | None, CoverageState]:
    try:
        response = client.get(path)
        _record_permissions(response, permissions)
        payload = cast(object, response.json())
        if not isinstance(payload, list) or any(not isinstance(item, dict) for item in cast(list[object], payload)):
            raise TypeError("GitHub response must be a JSON array of objects")
        return cast(list[JsonObject], payload), CoverageState.SUPPORTED
    except GitHubApiError as error:
        if error.accepted_permissions:
            permissions.add(error.accepted_permissions)
        if error.status_code == 404:
            return None, not_found
        if error.kind == "authorization":
            return None, forbidden
        return None, CoverageState.FAILED
    except (GitHubTransportError, TypeError, ValueError):
        return None, CoverageState.FAILED


def _get_branch_protection(
    client: GitHubApiClient,
    target: RepositoryAuditTarget,
    encoded_branch: str,
    permissions: set[str],
    *,
    forbidden: CoverageState = CoverageState.INACCESSIBLE,
) -> tuple[JsonObject | None, CoverageState, bool | None]:
    try:
        response = client.get(f"/repos/{target.api_name}/branches/{encoded_branch}/protection")
        _record_permissions(response, permissions)
        return _json_object(response), CoverageState.SUPPORTED, True
    except GitHubApiError as error:
        if error.accepted_permissions:
            permissions.add(error.accepted_permissions)
        if error.status_code == 404:
            return None, CoverageState.SUPPORTED, False
        if error.kind == "authorization":
            return None, forbidden, None
        return None, CoverageState.FAILED, None
    except (GitHubTransportError, TypeError, ValueError):
        return None, CoverageState.FAILED, None


def _get_enabled_endpoint(
    client: GitHubApiClient,
    path: str,
    permissions: set[str],
    *,
    payload_enabled: bool,
) -> tuple[bool | None, CoverageState]:
    try:
        response = client.get(path)
        _record_permissions(response, permissions)
        if not payload_enabled:
            return True, CoverageState.SUPPORTED
        payload = _json_object(response)
        enabled = payload.get("enabled")
        return (enabled, CoverageState.SUPPORTED) if isinstance(enabled, bool) else (None, CoverageState.UNVERIFIED)
    except GitHubApiError as error:
        if error.accepted_permissions:
            permissions.add(error.accepted_permissions)
        if error.status_code == 404:
            return False, CoverageState.SUPPORTED
        if error.kind == "authorization":
            return None, CoverageState.INACCESSIBLE
        return None, CoverageState.FAILED
    except (GitHubTransportError, TypeError, ValueError):
        return None, CoverageState.FAILED


def _rule_types(rules: list[JsonObject] | None) -> set[str]:
    if rules is None:
        return set()
    types: set[str] = set()
    for rule in rules:
        rule_type = rule.get("type")
        if not isinstance(rule_type, str):
            raise TypeError("GitHub branch rule did not contain a valid type")
        types.add(rule_type)
    return types


def _object_present(payload: JsonObject | None, key: str) -> bool | None:
    if payload is None:
        return False
    value = payload.get(key)
    return isinstance(value, dict)


def _required_status_checks_present(payload: JsonObject | None) -> bool | None:
    if payload is None:
        return False
    value = payload.get("required_status_checks")
    if not isinstance(value, dict):
        return False
    values = cast(JsonObject, value)
    contexts = values.get("contexts", [])
    checks = values.get("checks", [])
    if not isinstance(contexts, list) or not isinstance(checks, list):
        return None
    return bool(cast(list[object], contexts) or cast(list[object], checks))


def _combined_branch_control(
    classic_state: CoverageState,
    classic_value: bool | None,
    rules_state: CoverageState,
    rules_value: bool,
    current: JsonValue,
) -> tuple[bool | None, CoverageState, JsonValue]:
    if classic_value is True or (rules_state is CoverageState.SUPPORTED and rules_value):
        return True, CoverageState.SUPPORTED, current
    if classic_state is CoverageState.SUPPORTED and rules_state in {
        CoverageState.SUPPORTED,
        CoverageState.UNSUPPORTED,
        CoverageState.UNAVAILABLE_BY_PLAN,
    }:
        return False, CoverageState.SUPPORTED, current
    return None, _worst_terminal_state(classic_state, rules_state), current


def _worst_terminal_state(*states: CoverageState) -> CoverageState:
    for state in (CoverageState.INACCESSIBLE, CoverageState.FAILED, CoverageState.UNVERIFIED):
        if state in states:
            return state
    if CoverageState.UNSUPPORTED in states:
        return CoverageState.UNSUPPORTED
    if CoverageState.UNAVAILABLE_BY_PLAN in states:
        return CoverageState.UNAVAILABLE_BY_PLAN
    return CoverageState.UNVERIFIED


def _actions_policy(
    payload: JsonObject | None,
    state: CoverageState,
) -> tuple[dict[str, JsonValue], bool | None, CoverageState]:
    if payload is None:
        return {"enabled": None, "allowed_actions": None, "sha_pinning_required": None}, None, state
    enabled = payload.get("enabled")
    allowed_actions = payload.get("allowed_actions")
    sha_pinning = payload.get("sha_pinning_required")
    if not isinstance(enabled, bool):
        return {"enabled": None, "allowed_actions": None, "sha_pinning_required": None}, None, CoverageState.UNVERIFIED
    current: dict[str, JsonValue] = {
        "enabled": enabled,
        "allowed_actions": allowed_actions if isinstance(allowed_actions, str) else None,
        "sha_pinning_required": sha_pinning if isinstance(sha_pinning, bool) else None,
    }
    if not enabled:
        return current, True, CoverageState.SUPPORTED
    if not isinstance(allowed_actions, str) or not isinstance(sha_pinning, bool):
        return current, None, CoverageState.UNVERIFIED
    return current, allowed_actions in {"local_only", "selected"} and sha_pinning, CoverageState.SUPPORTED


def _workflow_policy(
    payload: JsonObject | None,
    state: CoverageState,
) -> tuple[dict[str, JsonValue], bool | None, CoverageState]:
    if state is CoverageState.NOT_APPLICABLE:
        return {"default_workflow_permissions": None, "can_approve_pull_request_reviews": None}, None, state
    if payload is None:
        return {"default_workflow_permissions": None, "can_approve_pull_request_reviews": None}, None, state
    default_permissions = payload.get("default_workflow_permissions")
    can_approve = payload.get("can_approve_pull_request_reviews")
    current: dict[str, JsonValue] = {
        "default_workflow_permissions": default_permissions if isinstance(default_permissions, str) else None,
        "can_approve_pull_request_reviews": can_approve if isinstance(can_approve, bool) else None,
    }
    if not isinstance(default_permissions, str) or not isinstance(can_approve, bool):
        return current, None, CoverageState.UNVERIFIED
    return current, default_permissions == "read" and not can_approve, CoverageState.SUPPORTED


def _metadata_security_feature(
    payload: JsonObject,
    key: str,
    *,
    missing: CoverageState = CoverageState.UNVERIFIED,
) -> tuple[bool | None, CoverageState]:
    security = payload.get("security_and_analysis")
    if not isinstance(security, dict):
        return None, missing
    feature = cast(JsonObject, security).get(key)
    if not isinstance(feature, dict):
        return None, missing
    status = cast(JsonObject, feature).get("status")
    if status == "enabled":
        return True, CoverageState.SUPPORTED
    if status == "disabled":
        return False, CoverageState.SUPPORTED
    if status in {"unavailable", "not_available"}:
        return None, CoverageState.UNAVAILABLE_BY_PLAN
    return None, CoverageState.UNVERIFIED


def _code_scanning_state(
    client: GitHubApiClient,
    target: RepositoryAuditTarget,
    repository_state: JsonObject,
    permissions: set[str],
    *,
    archived: bool,
    plan_limited: bool,
) -> tuple[bool | None, CoverageState, JsonValue]:
    if archived:
        return None, CoverageState.NOT_APPLICABLE, {"configured": None, "mode": None}
    unavailable = CoverageState.UNAVAILABLE_BY_PLAN if plan_limited else CoverageState.INACCESSIBLE
    default_setup, default_state = _get_object(
        client,
        f"/repos/{target.api_name}/code-scanning/default-setup",
        permissions,
        not_found=CoverageState.SUPPORTED,
        forbidden=unavailable,
    )
    if default_setup is not None:
        state = default_setup.get("state")
        if state == "configured":
            return True, CoverageState.SUPPORTED, {"configured": True, "mode": "default"}
        if state not in {"not-configured", None}:
            return None, CoverageState.UNVERIFIED, {"configured": None, "mode": None}
    elif default_state is CoverageState.UNAVAILABLE_BY_PLAN:
        return None, default_state, {"configured": None, "mode": None}

    analyses, analyses_state = _get_array(
        client,
        f"/repos/{target.api_name}/code-scanning/analyses?per_page=1",
        permissions,
        not_found=CoverageState.SUPPORTED,
        forbidden=unavailable,
    )
    if analyses is not None:
        configured = bool(analyses)
        return (
            configured,
            CoverageState.SUPPORTED,
            {
                "configured": configured,
                "mode": "advanced_or_external" if configured else None,
            },
        )
    if analyses_state is CoverageState.SUPPORTED:
        return False, CoverageState.SUPPORTED, {"configured": False, "mode": None}
    product_value, product_state = _metadata_security_feature(repository_state, "code_security")
    if product_state is CoverageState.UNVERIFIED:
        product_value, product_state = _metadata_security_feature(repository_state, "advanced_security")
    if product_value is False:
        return False, CoverageState.SUPPORTED, {"configured": False, "mode": None}
    return (
        None,
        _worst_terminal_state(default_state, analyses_state, product_state),
        {
            "configured": None,
            "mode": None,
        },
    )


def _feature_result(
    target: RepositoryAuditTarget,
    check_id: str,
    category: str,
    enabled_by_policy: bool,
    suppressed_checks: tuple[str, ...],
    coverage_state: CoverageState,
    current_state: JsonValue,
    desired_state: JsonValue,
    *,
    compliant: bool | None,
    evidence: str,
    observed_at: datetime,
    severity: Severity,
    documentation_url: str,
) -> tuple[CheckResult, Finding | None]:
    if check_id in suppressed_checks or not enabled_by_policy:
        return (
            _result(
                target,
                check_id,
                category,
                CheckOutcome.UNKNOWN,
                CoverageState.SKIPPED_BY_POLICY,
                current_state,
                desired_state,
                "active policy disabled or suppressed evaluation",
            ),
            None,
        )
    if coverage_state is CoverageState.NOT_APPLICABLE:
        return (
            _result(
                target,
                check_id,
                category,
                CheckOutcome.OBSERVED,
                coverage_state,
                current_state,
                desired_state,
                "check does not apply to this repository state",
            ),
            None,
        )
    if coverage_state is not CoverageState.SUPPORTED or compliant is None:
        outcome = CheckOutcome.INACCESSIBLE if coverage_state is CoverageState.INACCESSIBLE else CheckOutcome.UNKNOWN
        return (
            _result(target, check_id, category, outcome, coverage_state, current_state, desired_state, evidence),
            None,
        )
    outcome = CheckOutcome.COMPLIANT if compliant else CheckOutcome.NONCOMPLIANT
    result = _result(target, check_id, category, outcome, coverage_state, current_state, desired_state, evidence)
    finding = (
        None
        if compliant
        else _finding(
            target,
            result,
            observed_at,
            RemediationClass.APPROVAL_REQUIRED,
            documentation_url,
            severity=severity,
        )
    )
    return result, finding


def _metadata_current(check_id: str, value: object) -> JsonValue:
    if check_id == "metadata.topics":
        return {"count": cast(int, value)}
    if check_id in {"metadata.description", "metadata.homepage", "metadata.primary_language"}:
        return {"present": cast(bool, value)}
    return {"value": cast(str | bool, value)}


def _metadata_outcome(
    check_id: str,
    value: object,
    requirement: Requirement | None,
    minimum_topics: int,
) -> CheckOutcome:
    if requirement is None:
        return CheckOutcome.OBSERVED
    if check_id == "metadata.topics":
        return CheckOutcome.COMPLIANT if cast(int, value) >= minimum_topics else CheckOutcome.NONCOMPLIANT
    if requirement == "optional":
        return CheckOutcome.OBSERVED
    return CheckOutcome.COMPLIANT if value is True else CheckOutcome.NONCOMPLIANT


def _present(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _json_object(response: httpx.Response) -> JsonObject:
    payload = cast(object, response.json())
    if not isinstance(payload, dict):
        raise TypeError("GitHub response must be a JSON object")
    return cast(JsonObject, payload)


def _directory_paths(response: httpx.Response) -> set[str]:
    payload = cast(object, response.json())
    if not isinstance(payload, list):
        raise TypeError("GitHub contents response must be a JSON array")
    paths: set[str] = set()
    for item in cast(list[object], payload):
        if not isinstance(item, dict):
            raise TypeError("GitHub contents response item must contain a path")
        item_values = cast(dict[str, object], item)
        path = item_values.get("path")
        if not isinstance(path, str):
            raise TypeError("GitHub contents response item must contain a path")
        paths.add(path.casefold())
    return paths


def _profile_entry(profile: JsonObject, name: str) -> object | None:
    files = profile.get("files")
    if not isinstance(files, dict):
        return None
    file_values = cast(dict[str, object], files)
    for key in _PROFILE_KEYS.get(name, ()):
        value = file_values.get(key)
        if value is not None:
            return value
    return None


def _profile_entry_is_inherited(entry: object, api_name: str) -> bool:
    if not isinstance(entry, dict):
        return False
    entry_values = cast(dict[str, object], entry)
    urls = [
        value.casefold() for key, value in entry_values.items() if key in {"url", "html_url"} and isinstance(value, str)
    ]
    return bool(urls) and all(f"/{api_name.casefold()}/" not in url for url in urls)


def _path_matches(name: str, path: str) -> bool:
    normalized = path.casefold()
    basename = normalized.rsplit("/", 1)[-1]
    if name == "readme":
        return basename == "readme" or basename.startswith("readme.")
    if name == "license":
        return basename == "license" or basename.startswith("license.")
    if name == "security":
        return basename == "security" or basename.startswith("security.")
    if name == "contributing":
        return basename == "contributing" or basename.startswith("contributing.")
    if name == "code_of_conduct":
        return basename == "code_of_conduct" or basename.startswith("code_of_conduct.")
    if name == "support":
        return basename == "support" or basename.startswith("support.")
    if name == "issue_template":
        return basename == "issue_template" or "issue_template/" in normalized
    return (
        basename == "pull_request_template"
        or basename.startswith("pull_request_template.")
        or "pull_request_template/" in normalized
    )


def _result(
    target: RepositoryAuditTarget,
    check_id: str,
    category: str,
    outcome: CheckOutcome,
    coverage_state: CoverageState,
    current_state: JsonValue,
    desired_state: JsonValue,
    evidence: str,
) -> CheckResult:
    return CheckResult(
        repository_id=target.repository_id,
        repository_display=target.display_name,
        check_id=check_id,
        category=category,
        outcome=outcome,
        coverage_state=coverage_state,
        current_state=current_state,
        desired_state=desired_state,
        evidence=(evidence,),
    )


def _suppressed_result(
    target: RepositoryAuditTarget,
    check_id: str,
    category: str,
    current_state: JsonValue,
    desired_state: JsonValue,
) -> CheckResult:
    return _result(
        target,
        check_id,
        category,
        CheckOutcome.UNKNOWN,
        CoverageState.SKIPPED_BY_POLICY,
        current_state,
        desired_state,
        "active policy exception suppressed evaluation",
    )


def _unavailable_result(
    target: RepositoryAuditTarget,
    check_id: str,
    coverage_state: CoverageState,
    outcome: CheckOutcome,
    evidence: str,
) -> CheckResult:
    return _result(target, check_id, check_id.split(".", 1)[0], outcome, coverage_state, None, None, evidence)


def _finding(
    target: RepositoryAuditTarget,
    result: CheckResult,
    observed_at: datetime,
    remediation_class: RemediationClass,
    documentation_url: str,
    *,
    severity: Severity = Severity.LOW,
) -> Finding:
    identity = f"{target.repository_id}:{result.check_id}:{observed_at.isoformat()}".encode()
    finding_id = f"finding-{hashlib.sha256(identity).hexdigest()[:24]}"
    return Finding(
        finding_id=finding_id,
        check_id=result.check_id,
        repository_id=target.repository_id,
        repository_display=target.display_name,
        category=result.category,
        severity=severity,
        current_state=result.current_state,
        desired_state=result.desired_state,
        evidence=list(result.evidence),
        remediation_class=remediation_class,
        documentation_url=documentation_url,
        observed_at=observed_at,
    )


def _failure_state(error: Exception) -> tuple[CoverageState, CheckOutcome]:
    if isinstance(error, GitHubApiError) and error.kind in {"authorization", "not_found"}:
        return CoverageState.INACCESSIBLE, CheckOutcome.INACCESSIBLE
    return CoverageState.FAILED, CheckOutcome.UNKNOWN


def _worse_state(current: CoverageState, candidate: CoverageState) -> CoverageState:
    order = {CoverageState.AUDITED: 0, CoverageState.FAILED: 1, CoverageState.INACCESSIBLE: 2}
    return candidate if order[candidate] > order[current] else current


def _record_permissions(response: httpx.Response, permissions: set[str]) -> None:
    value = accepted_permissions(response)
    if value:
        permissions.add(value)


def _report(
    target: RepositoryAuditTarget,
    policy: ResolvedPolicy,
    credential_source: str,
    started_at: datetime,
    completed_at: datetime,
    permissions: set[str],
    results: list[CheckResult],
    findings: list[Finding],
) -> RepositoryAuditReport:
    coverage = tuple(
        CoverageRecord(repository_id=target.repository_id, check_id=result.check_id, state=result.coverage_state)
        for result in results
    )
    status = (
        RunStatus.PARTIAL
        if any(
            result.coverage_state in {CoverageState.FAILED, CoverageState.INACCESSIBLE, CoverageState.UNVERIFIED}
            for result in results
        )
        else RunStatus.COMPLETE
    )
    return RepositoryAuditReport(
        tool_version=__version__,
        github_api_version=GITHUB_API_VERSION,
        repository_id=target.repository_id,
        repository_display=target.display_name,
        credential_source=credential_source,
        started_at=started_at,
        completed_at=completed_at,
        status=status,
        policy_hash=policy.policy_hash,
        accepted_permissions=tuple(sorted(permissions)),
        results=tuple(results),
        coverage=coverage,
        findings=tuple(findings),
    )
