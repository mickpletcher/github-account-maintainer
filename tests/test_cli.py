from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

import github_account_maintainer.cli as cli_module
from github_account_maintainer.account_audit import AccountAuditReport, FindingSummary
from github_account_maintainer.cli import app
from github_account_maintainer.config import AppConfig
from github_account_maintainer.constants import GITHUB_API_VERSION
from github_account_maintainer.credentials import CredentialResolutionError
from github_account_maintainer.history import AuditHistoryReport, HistoryWriteResult
from github_account_maintainer.models import (
    AuthReport,
    CoverageRecord,
    CoverageState,
    Finding,
    InventoryReport,
    RemediationClass,
    RunStatus,
    Severity,
)

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0.dev0"


def test_init_creates_strict_local_config(tmp_path: Path) -> None:
    output = tmp_path / "config" / "config.yaml"

    result = runner.invoke(app, ["init", "--login", "mickpletcher", "--output", str(output)])

    assert result.exit_code == 0
    content = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert content["account"]["login"] == "mickpletcher"
    assert content["safety"]["automatic_write_operations"] == []
    assert content["safety"]["destructive_operations"] == "prohibited"
    assert content["history"]["enabled"] is True
    assert not list(output.parent.glob("*.tmp"))


def test_init_refuses_to_overwrite_by_default(tmp_path: Path) -> None:
    output = tmp_path / "config.yaml"
    output.write_text("preserve: true\n", encoding="utf-8")

    result = runner.invoke(app, ["init", "--login", "mickpletcher", "--output", str(output)])

    assert result.exit_code == 3
    assert output.read_text(encoding="utf-8") == "preserve: true\n"


def test_init_overwrites_only_when_explicit(tmp_path: Path) -> None:
    output = tmp_path / "config.yaml"
    output.write_text("preserve: true\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["init", "--login", "mickpletcher", "--output", str(output), "--overwrite"],
    )

    assert result.exit_code == 0
    assert "preserve" not in yaml.safe_load(output.read_text(encoding="utf-8"))


def test_audit_command_outputs_report_and_honors_findings_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = create_config(tmp_path)
    report = account_audit_report(RunStatus.COMPLETE, threshold_met=True)

    def return_report(_config: AppConfig) -> AccountAuditReport:
        return report

    monkeypatch.setattr(cli_module, "run_account_audit", return_report)

    result = runner.invoke(
        app,
        ["audit", "--config", str(config_path), "--format", "markdown", "--no-history"],
    )

    assert result.exit_code == 1
    assert "# GitHub Account Audit" in result.stdout


def test_audit_partial_report_exits_two(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = create_config(tmp_path)
    report = account_audit_report(RunStatus.PARTIAL, threshold_met=False)

    def return_report(_config: AppConfig) -> AccountAuditReport:
        return report

    monkeypatch.setattr(cli_module, "run_account_audit", return_report)

    result = runner.invoke(app, ["audit", "--config", str(config_path), "--no-history"])

    assert result.exit_code == 2
    assert '"status": "partial"' in result.stdout


def test_audit_records_sanitized_history_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = create_config(tmp_path)
    report = account_audit_report(RunStatus.COMPLETE, threshold_met=False)
    recorded: list[AccountAuditReport] = []

    def run_audit(_config: AppConfig) -> AccountAuditReport:
        return report

    monkeypatch.setattr(cli_module, "run_account_audit", run_audit)

    def record(_config: AppConfig, audit_report: AccountAuditReport) -> HistoryWriteResult:
        recorded.append(audit_report)
        return HistoryWriteResult(
            run_id="a" * 64,
            recorded=True,
            schema_version=2,
            new=0,
            persistent=0,
            resolved=0,
            regressed=0,
        )

    monkeypatch.setattr(cli_module, "record_audit_history", record)

    result = runner.invoke(app, ["audit", "--config", str(config_path)])

    assert result.exit_code == 0
    assert recorded == [report]


def test_history_command_outputs_sanitized_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = create_config(tmp_path)
    report = AuditHistoryReport(schema_version=2, total_run_count=0, returned_run_count=0)

    def read_history(_config: AppConfig, *, limit: int) -> AuditHistoryReport:
        return report

    monkeypatch.setattr(cli_module, "read_audit_history", read_history)

    result = runner.invoke(
        app,
        ["history", "--config", str(config_path), "--format", "markdown", "--limit", "5"],
    )

    assert result.exit_code == 0
    assert "# Sanitized Audit History" in result.stdout
    assert "Stored runs: `0`" in result.stdout


def test_auth_check_outputs_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = create_config(tmp_path)
    timestamp = datetime(2026, 8, 10, 12, tzinfo=UTC)
    report = AuthReport(
        tool_version="0.1.0.dev0",
        github_api_version=GITHUB_API_VERSION,
        configured_login="mickpletcher",
        authenticated_login="mickpletcher",
        authenticated_user_id=1,
        credential_source="env:TEST_TOKEN",
        checked_at=timestamp,
    )

    def return_report(_config: AppConfig) -> AuthReport:
        return report

    monkeypatch.setattr(cli_module, "run_auth_check", return_report)

    result = runner.invoke(app, ["auth", "check", "--config", str(config_path)])

    assert result.exit_code == 0
    assert '"authenticated_login": "mickpletcher"' in result.stdout


def test_inventory_partial_report_exits_two(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = create_config(tmp_path)
    timestamp = datetime(2026, 8, 10, 12, tzinfo=UTC)
    report = InventoryReport(
        tool_version="0.1.0.dev0",
        github_api_version=GITHUB_API_VERSION,
        account_display="mickpletcher",
        credential_source="env:TEST_TOKEN",
        declared_affiliations=("owner",),
        started_at=timestamp,
        completed_at=timestamp,
        status=RunStatus.PARTIAL,
        pages_read=0,
        duplicates_removed=0,
        coverage=(CoverageRecord(check_id="inventory.repositories", state=CoverageState.FAILED),),
    )

    def return_report(_config: AppConfig) -> InventoryReport:
        return report

    monkeypatch.setattr(cli_module, "collect_inventory", return_report)

    result = runner.invoke(app, ["inventory", "--config", str(config_path), "--format", "markdown"])

    assert result.exit_code == 2
    assert "Status: `partial`" in result.stdout


def test_auth_failure_exits_two_without_secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = create_config(tmp_path)

    def fail_auth(_config: AppConfig) -> AuthReport:
        raise CredentialResolutionError("credential unavailable")

    monkeypatch.setattr(cli_module, "run_auth_check", fail_auth)

    result = runner.invoke(app, ["auth", "check", "--config", str(config_path)])

    assert result.exit_code == 2
    assert "credential unavailable" in result.stderr


def test_missing_config_exits_three(tmp_path: Path) -> None:
    result = runner.invoke(app, ["auth", "check", "--config", str(tmp_path / "missing.yaml")])

    assert result.exit_code == 3
    assert "Invalid configuration" in result.stderr


def test_invalid_config_does_not_echo_literal_credential(tmp_path: Path) -> None:
    config_path = create_config(tmp_path)
    content = config_path.read_text(encoding="utf-8").replace(
        "keyring:github-account-maintainer/discovery", "literal-secret-token"
    )
    config_path.write_text(content, encoding="utf-8")

    result = runner.invoke(app, ["auth", "check", "--config", str(config_path)])

    assert result.exit_code == 3
    assert "literal-secret-token" not in result.stderr


@pytest.mark.parametrize("reference", ["disabled", "env:", "keyring:missing-account"])
def test_invalid_discovery_credential_config_exits_three(tmp_path: Path, reference: str) -> None:
    config_path = create_config(tmp_path)
    content = config_path.read_text(encoding="utf-8").replace("keyring:github-account-maintainer/discovery", reference)
    config_path.write_text(content, encoding="utf-8")

    result = runner.invoke(app, ["inventory", "--config", str(config_path)])

    assert result.exit_code == 3
    assert "Invalid configuration" in result.stderr


def create_config(tmp_path: Path) -> Path:
    path = tmp_path / "config.yaml"
    config = cli_module.default_config("mickpletcher")
    cli_module.write_config(config, path)
    return path


def account_audit_report(status: RunStatus, *, threshold_met: bool) -> AccountAuditReport:
    timestamp = datetime(2026, 8, 10, 12, tzinfo=UTC)
    return AccountAuditReport(
        tool_version="0.1.0.dev0",
        github_api_version=GITHUB_API_VERSION,
        account_display="mickpletcher",
        discovery_credential_source="env:DISCOVERY_TOKEN",
        audit_credential_source="env:AUDIT_TOKEN",
        started_at=timestamp,
        completed_at=timestamp,
        status=status,
        inventory_status=RunStatus.COMPLETE,
        repository_count=0,
        requested_repository_count=0,
        audited_repository_count=0,
        finding_summary=FindingSummary(
            threshold=Severity.LOW,
            threshold_met=threshold_met,
            total=1 if threshold_met else 0,
            low=1 if threshold_met else 0,
        ),
        findings=(_finding(timestamp),) if threshold_met else (),
    )


def _finding(timestamp: datetime) -> Finding:
    return Finding(
        finding_id="test-finding",
        check_id="metadata.description",
        category="metadata",
        severity=Severity.LOW,
        current_state={"present": False},
        desired_state={"requirement": "required"},
        remediation_class=RemediationClass.APPROVAL_REQUIRED,
        observed_at=timestamp,
    )
