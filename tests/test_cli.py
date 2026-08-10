from pathlib import Path

import yaml
from typer.testing import CliRunner

from github_account_maintainer.cli import app

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


def test_reserved_read_only_commands_fail_as_incomplete() -> None:
    for command in (["auth", "check"], ["inventory"], ["audit"]):
        result = runner.invoke(app, command)

        assert result.exit_code == 2
        assert "implementation" in result.stderr
