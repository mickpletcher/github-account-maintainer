from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

import github_account_maintainer.cli as cli_module
from github_account_maintainer.cli import app
from github_account_maintainer.config import AppConfig
from github_account_maintainer.constants import GITHUB_API_VERSION
from github_account_maintainer.credentials import CredentialResolutionError
from github_account_maintainer.models import AuthReport, CoverageRecord, CoverageState, InventoryReport, RunStatus

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


def test_reserved_audit_command_fails_as_incomplete() -> None:
    result = runner.invoke(app, ["audit"])

    assert result.exit_code == 2
    assert "implementation" in result.stderr


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
