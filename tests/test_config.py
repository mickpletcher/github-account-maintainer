from pathlib import Path

import pytest
from pydantic import ValidationError

from github_account_maintainer.config import AppConfig, default_config, load_config, write_config


def test_default_config_uses_hard_safety_invariants() -> None:
    config = default_config("mickpletcher")

    assert config.safety.automatic_merge == "prohibited"
    assert config.safety.destructive_operations == "prohibited"
    assert config.safety.automatic_write_operations == ()
    assert config.backup.enabled is False
    assert config.credentials.remediation == "disabled"


def test_unknown_configuration_field_is_rejected() -> None:
    raw = default_config("mickpletcher").model_dump(mode="json")
    raw["unknown"] = True

    with pytest.raises(ValidationError):
        AppConfig.model_validate(raw)


def test_hard_safety_invariant_cannot_be_enabled() -> None:
    raw = default_config("mickpletcher").model_dump(mode="json")
    raw["safety"]["destructive_operations"] = "allowed"

    with pytest.raises(ValidationError):
        AppConfig.model_validate(raw)


def test_config_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    expected = default_config("mickpletcher")

    write_config(expected, path)

    assert load_config(path) == expected
