from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from github_account_maintainer.constants import REPORT_SCHEMA_VERSION


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CoverageState(StrEnum):
    AUDITED = "audited"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE_BY_PLAN = "unavailable_by_plan"
    INHERITED = "inherited"
    INACCESSIBLE = "inaccessible"
    SKIPPED_BY_POLICY = "skipped_by_policy"
    NOT_REQUESTED = "not_requested"
    FAILED = "failed"


class CheckOutcome(StrEnum):
    COMPLIANT = "compliant"
    NONCOMPLIANT = "noncompliant"
    OBSERVED = "observed"
    UNKNOWN = "unknown"
    INACCESSIBLE = "inaccessible"


class Severity(StrEnum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RemediationClass(StrEnum):
    AUTOMATIC = "automatic"
    PULL_REQUEST = "pull_request"
    APPROVAL_REQUIRED = "approval_required"
    MANUAL_ONLY = "manual_only"


class RunStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"


class PolicySource(StrEnum):
    BUILT_IN = "built_in"
    ACCOUNT = "account"
    REPOSITORY_CLASS = "repository_class"
    PROJECT_TYPE = "project_type"
    REPOSITORY = "repository"
    EXCEPTION = "exception"


class PolicyTraceRecord(StrictModel):
    path: str
    source: PolicySource
    source_key: str | None = None
    value: JsonValue


class CoverageRecord(StrictModel):
    repository_id: int | None = None
    check_id: str
    state: CoverageState
    detail: str | None = None


class Finding(StrictModel):
    finding_id: str
    check_id: str
    repository_id: int | None = None
    repository_display: str | None = None
    category: str
    severity: Severity
    current_state: JsonValue
    desired_state: JsonValue
    evidence: list[str] = []
    confidence: Annotated[float, Field(ge=0, le=1)] = 1.0
    remediation_class: RemediationClass
    documentation_url: str | None = None
    observed_at: datetime


class CheckResult(StrictModel):
    repository_id: int
    repository_display: str
    check_id: str
    category: str
    outcome: CheckOutcome
    coverage_state: CoverageState
    current_state: JsonValue
    desired_state: JsonValue
    evidence: tuple[str, ...] = ()


class RunReport(StrictModel):
    schema_version: Literal["1.0"] = REPORT_SCHEMA_VERSION
    tool_version: str
    github_api_version: str
    account_display: str
    started_at: datetime
    completed_at: datetime
    status: RunStatus
    policy_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    policy_trace: tuple[PolicyTraceRecord, ...] = ()
    coverage: list[CoverageRecord] = []
    findings: list[Finding] = []


class AuthReport(StrictModel):
    schema_version: Literal["1.0"] = REPORT_SCHEMA_VERSION
    tool_version: str
    github_api_version: str
    configured_login: str
    authenticated_login: str
    authenticated_user_id: int
    credential_source: str
    oauth_scopes: tuple[str, ...] = ()
    accepted_oauth_scopes: tuple[str, ...] = ()
    accepted_permissions: str | None = None
    rate_limit_remaining: int | None = None
    checked_at: datetime


class RepositoryPermissions(StrictModel):
    admin: bool | None = None
    maintain: bool | None = None
    push: bool | None = None
    triage: bool | None = None
    pull: bool | None = None


class RepositoryInventoryRecord(StrictModel):
    repository_id: int
    node_id: str
    display_name: str
    private: bool
    visibility: Literal["public", "private", "internal"]
    archived: bool
    fork: bool
    html_url: str | None = None
    permissions: RepositoryPermissions


class InventoryReport(StrictModel):
    schema_version: Literal["1.0"] = REPORT_SCHEMA_VERSION
    tool_version: str
    github_api_version: str
    account_display: str
    credential_source: str
    declared_affiliations: tuple[str, ...]
    started_at: datetime
    completed_at: datetime
    status: RunStatus
    pages_read: int
    duplicates_removed: int
    accepted_permissions: tuple[str, ...] = ()
    repositories: tuple[RepositoryInventoryRecord, ...] = ()
    coverage: tuple[CoverageRecord, ...] = ()


class RepositoryAuditReport(StrictModel):
    schema_version: Literal["1.0"] = REPORT_SCHEMA_VERSION
    tool_version: str
    github_api_version: str
    repository_id: int
    repository_display: str
    credential_source: str
    started_at: datetime
    completed_at: datetime
    status: RunStatus
    policy_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    accepted_permissions: tuple[str, ...] = ()
    results: tuple[CheckResult, ...] = ()
    coverage: tuple[CoverageRecord, ...] = ()
    findings: tuple[Finding, ...] = ()
