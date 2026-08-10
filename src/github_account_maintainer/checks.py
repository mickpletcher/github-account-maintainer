import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Literal, cast

import httpx
from pydantic import Field, JsonValue, field_validator

from github_account_maintainer import __version__
from github_account_maintainer.auth import ClientFactory, CredentialResolver, auth_report_from_response, client_factory
from github_account_maintainer.config import AppConfig, CommunityConfig, MetadataConfig, StrictModel
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
ALL_CHECKS = METADATA_CHECKS + COMMUNITY_CHECKS

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
    now: Callable[[], datetime] | None = None,
) -> RepositoryAuditReport:
    clock = now or (lambda: datetime.now(UTC))
    started_at = clock()
    permissions: set[str] = set()
    results: list[CheckResult] = []
    findings: list[Finding] = []

    try:
        response = client.get(f"/repos/{target.api_name}")
        _record_permissions(response, permissions)
        metadata = _json_object(response)
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
) -> Finding:
    identity = f"{target.repository_id}:{result.check_id}:{observed_at.isoformat()}".encode()
    finding_id = f"finding-{hashlib.sha256(identity).hexdigest()[:24]}"
    return Finding(
        finding_id=finding_id,
        check_id=result.check_id,
        repository_id=target.repository_id,
        repository_display=target.display_name,
        category=result.category,
        severity=Severity.LOW,
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
        if any(result.coverage_state in {CoverageState.FAILED, CoverageState.INACCESSIBLE} for result in results)
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
