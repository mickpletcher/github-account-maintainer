import os
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

import yaml
from platformdirs import user_data_path
from pydantic import BaseModel, ConfigDict, Field

from github_account_maintainer.constants import APP_NAME, GITHUB_API_VERSION

PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AccountConfig(StrictModel):
    login: str
    github_host: str = "github.com"
    include_private: bool = True
    include_owned: bool = True
    include_administered: bool = False
    affiliations: list[Literal["owner", "collaborator", "organization_member"]] = ["owner"]


class GitHubApiConfig(StrictModel):
    rest_api_version: Literal["2026-03-10"] = GITHUB_API_VERSION
    request_mode: Literal["serial"] = "serial"
    mutation_delay_seconds: PositiveInt = 1


class CredentialConfig(StrictModel):
    discovery: str = "github-account-maintainer/discovery"
    audit: str = "github-account-maintainer/audit"
    remediation: str = "disabled"
    classic_token: Literal["disabled"] = "disabled"  # noqa: S105
    browser_profile: str = "disabled"


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


class AppConfig(StrictModel):
    account: AccountConfig
    github_api: GitHubApiConfig = GitHubApiConfig()
    credentials: CredentialConfig = CredentialConfig()
    local_data: LocalDataConfig
    safety: SafetyConfig = SafetyConfig()
    repositories: RepositoryConfig = RepositoryConfig()
    pins: PinConfig = PinConfig()
    readme: ReadmeConfig = ReadmeConfig()
    social_preview: SocialPreviewConfig = SocialPreviewConfig()
    security: SecurityConfig = SecurityConfig()
    backup: BackupConfig = BackupConfig()
    notifications: NotificationConfig = NotificationConfig()


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
