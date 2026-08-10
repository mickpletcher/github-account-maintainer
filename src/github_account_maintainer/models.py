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


class RunReport(StrictModel):
    schema_version: Literal["1.0"] = REPORT_SCHEMA_VERSION
    tool_version: str
    github_api_version: str
    account_display: str
    started_at: datetime
    completed_at: datetime
    status: RunStatus
    coverage: list[CoverageRecord] = []
    findings: list[Finding] = []
