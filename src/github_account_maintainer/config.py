import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

import yaml
from platformdirs import user_data_path
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from github_account_maintainer.constants import APP_NAME, GITHUB_API_VERSION

PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]


def _valid_credential_reference(value: str) -> bool:
    scheme, separator, target = value.partition(":")
    if not separator or not target:
        return False
    if scheme == "env":
        return True
    if scheme == "keyring":
        service, account_separator, account = target.rpartition("/")
        return bool(account_separator and service and account)
    return False


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AccountConfig(StrictModel):
    login: str
    github_host: str = "github.com"
    include_private: bool = True
    include_owned: bool = True
    include_administered: bool = False
    affiliations: list[Literal["owner", "collaborator", "organization_member"]] = ["owner"]

    @field_validator("github_host")
    @classmethod
    def validate_github_host(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", value):
            raise ValueError("github_host must be a hostname without a scheme or path")
        return value

    @model_validator(mode="after")
    def validate_affiliations(self) -> "AccountConfig":
        if self.include_owned != ("owner" in self.affiliations):
            raise ValueError("include_owned must match the owner affiliation")
        administered = "collaborator" in self.affiliations or "organization_member" in self.affiliations
        if self.include_administered != administered:
            raise ValueError("include_administered must match collaborator or organization_member affiliation")
        return self


class GitHubApiConfig(StrictModel):
    rest_api_version: Literal["2026-03-10"] = GITHUB_API_VERSION
    request_mode: Literal["serial"] = "serial"
    mutation_delay_seconds: PositiveInt = 1


class CredentialConfig(StrictModel):
    discovery: str = "keyring:github-account-maintainer/discovery"
    audit: str = "keyring:github-account-maintainer/audit"
    remediation: str = "disabled"
    classic_token: Literal["disabled"] = "disabled"  # noqa: S105
    browser_profile: str = "disabled"

    @field_validator("discovery", "audit")
    @classmethod
    def validate_required_reference(cls, value: str) -> str:
        if _valid_credential_reference(value):
            return value
        raise ValueError("Credential value must use env:NAME or keyring:SERVICE/ACCOUNT")

    @field_validator("remediation", "browser_profile")
    @classmethod
    def validate_optional_reference(cls, value: str) -> str:
        if value == "disabled" or _valid_credential_reference(value):
            return value
        raise ValueError("Credential value must be disabled or use env:NAME or keyring:SERVICE/ACCOUNT")


class LocalDataConfig(StrictModel):
    config_directory: Path
    state_directory: Path
    cache_directory: Path
    report_directory: Path
    log_directory: Path
    browser_directory: Path
    backup_metadata_directory: Path
    report_detail: Literal["minimal", "full"] = "minimal"
    state_retention_days: PositiveInt = 365
    report_retention_days: PositiveInt = 90


class SafetyConfig(StrictModel):
    require_explicit_apply: Literal[True] = True
    automatic_merge: Literal["prohibited"] = "prohibited"
    destructive_operations: Literal["prohibited"] = "prohibited"
    require_approval_for_sensitive_settings: Literal[True] = True
    automatic_write_operations: tuple[str, ...] = ()
    plan_ttl_hours: PositiveInt = 24


class RepositoryConfig(StrictModel):
    modify_archived: bool = False
    modify_forks: bool = False
    include_patterns: list[str] = ["*"]
    exclude_patterns: list[str] = []


class AuditConfig(StrictModel):
    failure_threshold: Literal["informational", "low", "medium", "high", "critical"] = "low"


class PinConfig(StrictModel):
    mode: Literal["top_stars"] = "top_stars"
    count: Annotated[int, Field(ge=1, le=6)] = 6
    include_contributed: bool = True
    exclude_archived: bool = True
    exclude_forks: bool = True
    preserve_ties: bool = True
    protected: list[str] = []
    excluded: list[str] = []


class ReadmeConfig(StrictModel):
    enabled: bool = True
    remediation: Literal["pull_request"] = "pull_request"
    preserve_manual_sections: bool = True
    validate_links: bool = True
    private_ai_provider: Literal["disabled"] = "disabled"


class MetadataConfig(StrictModel):
    description: Literal["required", "optional"] = "required"
    homepage: Literal["required", "optional"] = "optional"
    minimum_topics: NonNegativeInt = 1
    primary_language: Literal["required", "optional"] = "required"


class CommunityConfig(StrictModel):
    readme: Literal["required", "optional"] = "required"
    license: Literal["required", "optional"] = "required"
    security: Literal["required", "optional"] = "required"
    contributing: Literal["required", "optional"] = "optional"
    code_of_conduct: Literal["required", "optional"] = "optional"
    support: Literal["required", "optional"] = "optional"
    issue_template: Literal["required", "optional"] = "optional"
    pull_request_template: Literal["required", "optional"] = "optional"


class SocialPreviewConfig(StrictModel):
    enabled: bool = True
    default_path: Path = Path(".github/social-preview.png")
    width: PositiveInt = 1280
    height: PositiveInt = 640
    max_bytes: PositiveInt = 1_000_000
    remediation: Literal["pull_request_then_browser_upload"] = "pull_request_then_browser_upload"
    protected_repositories: list[str] = []


class SecurityConfig(StrictModel):
    audit_dependabot: bool = True
    audit_secret_scanning: bool = True
    audit_push_protection: bool = True
    audit_code_scanning: bool = True
    audit_private_vulnerability_reporting: bool = True
    security_alert_dismissal: Literal["prohibited"] = "prohibited"


class BackupConfig(StrictModel):
    enabled: Literal[False] = False
    destination: None = None
    encryption_mode: None = None
    encryption_key_reference: None = None
    retention_policy: None = None
    encrypt_private_data: Literal[True] = True
    include_releases: bool = True
    include_metadata: bool = True
    verify_after_backup: bool = True


class NotificationConfig(StrictModel):
    clean_run_summary: bool = False
    maintenance_pr_label: str = "github-account-maintainer"
    cooldown_hours: NonNegativeInt = 168


class RepositoryPolicyPatch(StrictModel):
    modify_archived: bool | None = None
    modify_forks: bool | None = None
    include_patterns: tuple[str, ...] | None = None
    exclude_patterns: tuple[str, ...] | None = None


class PinPolicyPatch(StrictModel):
    mode: Literal["top_stars"] | None = None
    count: Annotated[int, Field(ge=1, le=6)] | None = None
    include_contributed: bool | None = None
    exclude_archived: bool | None = None
    exclude_forks: bool | None = None
    preserve_ties: bool | None = None
    protected: tuple[str, ...] | None = None
    excluded: tuple[str, ...] | None = None


class ReadmePolicyPatch(StrictModel):
    enabled: bool | None = None
    remediation: Literal["pull_request"] | None = None
    preserve_manual_sections: bool | None = None
    validate_links: bool | None = None
    private_ai_provider: Literal["disabled"] | None = None


class MetadataPolicyPatch(StrictModel):
    description: Literal["required", "optional"] | None = None
    homepage: Literal["required", "optional"] | None = None
    minimum_topics: NonNegativeInt | None = None
    primary_language: Literal["required", "optional"] | None = None


class CommunityPolicyPatch(StrictModel):
    readme: Literal["required", "optional"] | None = None
    license: Literal["required", "optional"] | None = None
    security: Literal["required", "optional"] | None = None
    contributing: Literal["required", "optional"] | None = None
    code_of_conduct: Literal["required", "optional"] | None = None
    support: Literal["required", "optional"] | None = None
    issue_template: Literal["required", "optional"] | None = None
    pull_request_template: Literal["required", "optional"] | None = None


class SocialPreviewPolicyPatch(StrictModel):
    enabled: bool | None = None
    default_path: Path | None = None
    width: PositiveInt | None = None
    height: PositiveInt | None = None
    max_bytes: PositiveInt | None = None
    remediation: Literal["pull_request_then_browser_upload"] | None = None
    protected_repositories: tuple[str, ...] | None = None


class SecurityPolicyPatch(StrictModel):
    audit_dependabot: bool | None = None
    audit_secret_scanning: bool | None = None
    audit_push_protection: bool | None = None
    audit_code_scanning: bool | None = None
    audit_private_vulnerability_reporting: bool | None = None
    security_alert_dismissal: Literal["prohibited"] | None = None


class NotificationPolicyPatch(StrictModel):
    clean_run_summary: bool | None = None
    maintenance_pr_label: str | None = None
    cooldown_hours: NonNegativeInt | None = None


class PolicySettingsPatch(StrictModel):
    repositories: RepositoryPolicyPatch | None = None
    pins: PinPolicyPatch | None = None
    readme: ReadmePolicyPatch | None = None
    metadata: MetadataPolicyPatch | None = None
    community: CommunityPolicyPatch | None = None
    social_preview: SocialPreviewPolicyPatch | None = None
    security: SecurityPolicyPatch | None = None
    notifications: NotificationPolicyPatch | None = None


class PolicyExceptionConfig(StrictModel):
    exception_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")]
    target_selector: str
    check_ids: tuple[str, ...]
    reason: str
    creator: str
    created_at: datetime
    expires_at: datetime | None = None
    permanent: bool = False

    @field_validator("target_selector", "reason", "creator")
    @classmethod
    def validate_nonempty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized

    @field_validator("check_ids")
    @classmethod
    def validate_check_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("check_ids must not be empty")
        if any(not re.fullmatch(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", check_id) for check_id in value):
            raise ValueError("check_ids must contain stable lowercase identifiers")
        return tuple(sorted(set(value)))

    @field_validator("created_at", "expires_at")
    @classmethod
    def validate_utc_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() != timedelta(0):
            raise ValueError("timestamps must use RFC 3339 UTC")
        return value

    @model_validator(mode="after")
    def validate_expiration(self) -> "PolicyExceptionConfig":
        if self.permanent and self.expires_at is not None:
            raise ValueError("permanent exceptions must not have an expiration")
        if not self.permanent and self.expires_at is None:
            raise ValueError("non-permanent exceptions require an expiration")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("exception expiration must be after creation")
        return self


class PolicyHierarchyConfig(StrictModel):
    repository_classes: dict[str, PolicySettingsPatch] = {}
    project_types: dict[str, PolicySettingsPatch] = {}
    repositories: dict[str, PolicySettingsPatch] = {}
    exceptions: tuple[PolicyExceptionConfig, ...] = ()

    @field_validator("repository_classes", "project_types", "repositories")
    @classmethod
    def validate_layer_keys(cls, value: dict[str, PolicySettingsPatch]) -> dict[str, PolicySettingsPatch]:
        normalized_keys = [key.strip() for key in value]
        if any(not key for key in normalized_keys):
            raise ValueError("policy layer keys must not be empty")
        if normalized_keys != list(value):
            raise ValueError("policy layer keys must not have surrounding whitespace")
        if len({key.casefold() for key in normalized_keys}) != len(normalized_keys):
            raise ValueError("policy layer keys must be unique ignoring case")
        return value

    @model_validator(mode="after")
    def validate_exception_ids(self) -> "PolicyHierarchyConfig":
        exception_ids = [exception.exception_id.casefold() for exception in self.exceptions]
        if len(set(exception_ids)) != len(exception_ids):
            raise ValueError("exception IDs must be unique ignoring case")
        return self


class AppConfig(StrictModel):
    account: AccountConfig
    github_api: GitHubApiConfig = GitHubApiConfig()
    credentials: CredentialConfig = CredentialConfig()
    local_data: LocalDataConfig
    safety: SafetyConfig = SafetyConfig()
    audit: AuditConfig = AuditConfig()
    repositories: RepositoryConfig = RepositoryConfig()
    pins: PinConfig = PinConfig()
    readme: ReadmeConfig = ReadmeConfig()
    metadata: MetadataConfig = MetadataConfig()
    community: CommunityConfig = CommunityConfig()
    social_preview: SocialPreviewConfig = SocialPreviewConfig()
    security: SecurityConfig = SecurityConfig()
    backup: BackupConfig = BackupConfig()
    notifications: NotificationConfig = NotificationConfig()
    policy: PolicyHierarchyConfig = PolicyHierarchyConfig()


def default_root() -> Path:
    return user_data_path(APP_NAME, appauthor=False, roaming=False)


def default_config(login: str) -> AppConfig:
    root = default_root()
    local_data = LocalDataConfig(
        config_directory=root / "config",
        state_directory=root / "state",
        cache_directory=root / "cache",
        report_directory=root / "reports",
        log_directory=root / "logs",
        browser_directory=root / "browser",
        backup_metadata_directory=root / "backup-metadata",
    )
    return AppConfig(account=AccountConfig(login=login), local_data=local_data)


def default_config_path() -> Path:
    return default_root() / "config" / "config.yaml"


def write_config(config: AppConfig, path: Path, *, overwrite: bool = False) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise FileExistsError(target)

    temp_path = target.parent / f".{target.name}.{uuid4().hex}.tmp"
    content = yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False)
    try:
        temp_path.write_text(content, encoding="utf-8", newline="\n")
        if overwrite:
            os.replace(temp_path, target)
        else:
            os.link(temp_path, target)
            temp_path.unlink()
    finally:
        temp_path.unlink(missing_ok=True)


def load_config(path: Path) -> AppConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return AppConfig.model_validate(raw)
