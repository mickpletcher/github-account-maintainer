from collections.abc import Callable
from datetime import UTC, datetime
from fnmatch import fnmatchcase
from typing import Annotated, Literal, cast

import httpx
from pydantic import Field, model_validator

from github_account_maintainer import __version__
from github_account_maintainer.auth import (
    ClientFactory,
    CredentialResolver,
    auth_report_from_response,
    client_factory,
)
from github_account_maintainer.checks import ALL_CHECKS, RepositoryAuditTarget, run_repository_checks
from github_account_maintainer.classification import (
    RepositoryClassificationError,
    RepositoryPolicyBindingRecord,
    RepositoryPolicyBindingTarget,
    classification_evidence_from_github,
    classify_and_bind_repository,
)
from github_account_maintainer.config import AppConfig, StrictModel
from github_account_maintainer.constants import GITHUB_API_VERSION, REPORT_SCHEMA_VERSION
from github_account_maintainer.credentials import resolve_credential
from github_account_maintainer.github_api import (
    GitHubApiError,
    GitHubTransportError,
    accepted_permissions,
)
from github_account_maintainer.inventory import InventoryTarget, collect_inventory_snapshot
from github_account_maintainer.models import (
    CheckOutcome,
    CheckResult,
    CoverageRecord,
    CoverageState,
    Finding,
    RunStatus,
    Severity,
)

type JsonObject = dict[str, object]

_SEVERITY_RANK = {
    Severity.INFORMATIONAL: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


class FindingSummary(StrictModel):
    threshold: Severity
    threshold_met: bool
    total: Annotated[int, Field(ge=0)]
    informational: Annotated[int, Field(ge=0)] = 0
    low: Annotated[int, Field(ge=0)] = 0
    medium: Annotated[int, Field(ge=0)] = 0
    high: Annotated[int, Field(ge=0)] = 0
    critical: Annotated[int, Field(ge=0)] = 0

    @model_validator(mode="after")
    def validate_counts(self) -> "FindingSummary":
        counts = {
            Severity.INFORMATIONAL: self.informational,
            Severity.LOW: self.low,
            Severity.MEDIUM: self.medium,
            Severity.HIGH: self.high,
            Severity.CRITICAL: self.critical,
        }
        if self.total != sum(counts.values()):
            raise ValueError("finding total did not match severity counts")
        expected_threshold = any(
            count > 0 and _SEVERITY_RANK[severity] >= _SEVERITY_RANK[self.threshold]
            for severity, count in counts.items()
        )
        if self.threshold_met != expected_threshold:
            raise ValueError("finding threshold state did not match severity counts")
        return self


class AccountAuditReport(StrictModel):
    schema_version: Literal["1.0"] = REPORT_SCHEMA_VERSION
    tool_version: str
    github_api_version: str
    account_display: str
    discovery_credential_source: str
    audit_credential_source: str
    started_at: datetime
    completed_at: datetime
    status: RunStatus
    inventory_status: RunStatus
    repository_count: Annotated[int, Field(ge=0)]
    requested_repository_count: Annotated[int, Field(ge=0)]
    audited_repository_count: Annotated[int, Field(ge=0)]
    accepted_permissions: tuple[str, ...] = ()
    bindings: tuple[RepositoryPolicyBindingRecord, ...] = ()
    results: tuple[CheckResult, ...] = ()
    coverage: tuple[CoverageRecord, ...] = ()
    findings: tuple[Finding, ...] = ()
    finding_summary: FindingSummary

    @model_validator(mode="after")
    def validate_aggregation(self) -> "AccountAuditReport":
        if not 0 <= self.audited_repository_count <= self.requested_repository_count <= self.repository_count:
            raise ValueError("repository aggregation counts were inconsistent")
        if self.audited_repository_count != len(self.bindings):
            raise ValueError("audited repository count did not match policy bindings")
        if self.finding_summary.total != len(self.findings):
            raise ValueError("finding summary did not match aggregated findings")
        return self


def run_account_audit(
    config: AppConfig,
    *,
    credential_resolver: CredentialResolver = resolve_credential,
    make_client: ClientFactory = client_factory,
    now: Callable[[], datetime] | None = None,
) -> AccountAuditReport:
    clock = now or (lambda: datetime.now(UTC))
    started_at = clock()
    snapshot = collect_inventory_snapshot(
        config,
        credential_resolver=credential_resolver,
        make_client=make_client,
    )
    credential = credential_resolver(config.credentials.audit)
    permissions = set(snapshot.report.accepted_permissions)
    bindings: list[RepositoryPolicyBindingRecord] = []
    results: list[CheckResult] = []
    findings: list[Finding] = []
    coverage = list(snapshot.report.coverage)
    requested_count = 0

    with make_client(credential.secret.get_secret_value(), config.account.github_host) as client:
        user_response = client.get("/user")
        auth_report = auth_report_from_response(config, credential, user_response)
        if auth_report.accepted_permissions:
            permissions.add(auth_report.accepted_permissions)

        for target in snapshot.targets:
            if not _in_scope(config, target.api_name):
                coverage.extend(_repository_coverage(target, CoverageState.NOT_REQUESTED, "outside declared scope"))
                results.extend(_unavailable_results(target, CoverageState.NOT_REQUESTED, CheckOutcome.UNKNOWN))
                continue

            requested_count += 1
            try:
                metadata_response = client.get(f"/repos/{target.api_name}")
                metadata_permission = accepted_permissions(metadata_response)
                if metadata_permission:
                    permissions.add(metadata_permission)
                metadata = _json_object(metadata_response)

                languages_response = client.get(f"/repos/{target.api_name}/languages")
                languages_permission = accepted_permissions(languages_response)
                if languages_permission:
                    permissions.add(languages_permission)
                languages = _json_object(languages_response)

                evidence = classification_evidence_from_github(metadata, languages)
                bound = classify_and_bind_repository(
                    config,
                    RepositoryPolicyBindingTarget(
                        repository_id=target.record.repository_id,
                        api_name=target.api_name,
                    ),
                    target.record,
                    evidence,
                    evaluated_at=started_at,
                )
                repository_report = run_repository_checks(
                    client,
                    RepositoryAuditTarget(
                        repository_id=target.record.repository_id,
                        api_name=target.api_name,
                        display_name=target.record.display_name,
                    ),
                    bound.resolved_policy,
                    credential_source=credential.source,
                    repository_metadata=metadata,
                    initial_permissions=tuple(
                        value for value in (metadata_permission, languages_permission) if value is not None
                    ),
                    now=clock,
                )
            except (
                GitHubApiError,
                GitHubTransportError,
                RepositoryClassificationError,
                TypeError,
                ValueError,
            ) as error:
                state, outcome, detail = _failure(error)
                coverage.extend(_repository_coverage(target, state, detail))
                results.extend(_unavailable_results(target, state, outcome))
                if isinstance(error, GitHubApiError) and error.accepted_permissions:
                    permissions.add(error.accepted_permissions)
                continue

            bindings.append(bound.record)
            coverage.append(
                CoverageRecord(
                    repository_id=target.record.repository_id,
                    check_id="classification.repository",
                    state=CoverageState.AUDITED,
                )
            )
            coverage.extend(repository_report.coverage)
            results.extend(repository_report.results)
            findings.extend(repository_report.findings)
            permissions.update(repository_report.accepted_permissions)

    status = _run_status(snapshot.report.status, coverage)
    summary = _finding_summary(findings, Severity(config.audit.failure_threshold))
    return AccountAuditReport(
        tool_version=__version__,
        github_api_version=GITHUB_API_VERSION,
        account_display=config.account.login,
        discovery_credential_source=snapshot.report.credential_source,
        audit_credential_source=credential.source,
        started_at=started_at,
        completed_at=clock(),
        status=status,
        inventory_status=snapshot.report.status,
        repository_count=len(snapshot.targets),
        requested_repository_count=requested_count,
        audited_repository_count=len(bindings),
        accepted_permissions=tuple(sorted(permissions)),
        bindings=tuple(bindings),
        results=tuple(results),
        coverage=tuple(coverage),
        findings=tuple(findings),
        finding_summary=summary,
    )


def audit_exit_code(report: AccountAuditReport) -> int:
    if report.status is RunStatus.PARTIAL:
        return 2
    return 1 if report.finding_summary.threshold_met else 0


def _in_scope(config: AppConfig, api_name: str) -> bool:
    normalized = api_name.casefold()
    included = any(fnmatchcase(normalized, pattern.casefold()) for pattern in config.repositories.include_patterns)
    excluded = any(fnmatchcase(normalized, pattern.casefold()) for pattern in config.repositories.exclude_patterns)
    return included and not excluded


def _json_object(response: httpx.Response) -> JsonObject:
    try:
        payload = cast(object, response.json())
    except ValueError:
        raise TypeError("GitHub response was not valid JSON") from None
    if not isinstance(payload, dict):
        raise TypeError("GitHub response was not a JSON object")
    return cast(JsonObject, payload)


def _failure(error: Exception) -> tuple[CoverageState, CheckOutcome, str]:
    if isinstance(error, GitHubApiError):
        detail = f"{error.kind}:{error.status_code}"
        if error.kind in {"authorization", "not_found"}:
            return CoverageState.INACCESSIBLE, CheckOutcome.INACCESSIBLE, detail
        return CoverageState.FAILED, CheckOutcome.UNKNOWN, detail
    return CoverageState.FAILED, CheckOutcome.UNKNOWN, type(error).__name__


def _repository_coverage(target: InventoryTarget, state: CoverageState, detail: str) -> list[CoverageRecord]:
    return [
        CoverageRecord(
            repository_id=target.record.repository_id,
            check_id=check_id,
            state=state,
            detail=detail,
        )
        for check_id in ("classification.repository", *ALL_CHECKS)
    ]


def _unavailable_results(
    target: InventoryTarget,
    state: CoverageState,
    outcome: CheckOutcome,
) -> list[CheckResult]:
    return [
        CheckResult(
            repository_id=target.record.repository_id,
            repository_display=target.record.display_name,
            check_id=check_id,
            category=check_id.partition(".")[0],
            outcome=outcome,
            coverage_state=state,
            current_state=None,
            desired_state=None,
            evidence=("repository prerequisite was unavailable",),
        )
        for check_id in ALL_CHECKS
    ]


def _run_status(inventory_status: RunStatus, coverage: list[CoverageRecord]) -> RunStatus:
    if inventory_status is RunStatus.PARTIAL:
        return RunStatus.PARTIAL
    if any(record.state in {CoverageState.FAILED, CoverageState.INACCESSIBLE} for record in coverage):
        return RunStatus.PARTIAL
    return RunStatus.COMPLETE


def _finding_summary(findings: list[Finding], threshold: Severity) -> FindingSummary:
    counts = {severity: 0 for severity in Severity}
    for finding in findings:
        counts[finding.severity] += 1
    return FindingSummary(
        threshold=threshold,
        threshold_met=any(_SEVERITY_RANK[finding.severity] >= _SEVERITY_RANK[threshold] for finding in findings),
        total=len(findings),
        informational=counts[Severity.INFORMATIONAL],
        low=counts[Severity.LOW],
        medium=counts[Severity.MEDIUM],
        high=counts[Severity.HIGH],
        critical=counts[Severity.CRITICAL],
    )
