from collections.abc import Mapping

import pytest
from keyring.errors import KeyringError

import github_account_maintainer.credentials as credential_module
from github_account_maintainer.credentials import CredentialResolutionError, resolve_credential


def test_resolve_environment_credential_redacts_value() -> None:
    credential = resolve_credential("env:TEST_TOKEN", environment={"TEST_TOKEN": "secret-value"})

    assert credential.secret.get_secret_value() == "secret-value"
    assert "secret-value" not in repr(credential)
    assert credential.source == "env:TEST_TOKEN"


def test_missing_environment_credential_fails() -> None:
    environment: Mapping[str, str] = {}

    with pytest.raises(CredentialResolutionError, match="not set"):
        resolve_credential("env:TEST_TOKEN", environment=environment)


def test_resolve_keyring_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    def get_password(service: str, account: str) -> str:
        return f"{service}:{account}"

    monkeypatch.setattr(credential_module.keyring, "get_password", get_password)

    credential = resolve_credential("keyring:github-account-maintainer/discovery")

    assert credential.secret.get_secret_value() == "github-account-maintainer:discovery"


def test_keyring_failure_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_keyring(_service: str, _account: str) -> str:
        raise KeyringError("backend detail")

    monkeypatch.setattr(credential_module.keyring, "get_password", fail_keyring)

    with pytest.raises(CredentialResolutionError, match="KeyringError") as error:
        resolve_credential("keyring:github-account-maintainer/discovery")

    assert "backend detail" not in str(error.value)


@pytest.mark.parametrize("reference", ["literal-token", "file:token.txt", "keyring:missing-account"])
def test_unsupported_or_invalid_reference_fails(reference: str) -> None:
    with pytest.raises(CredentialResolutionError):
        resolve_credential(reference, environment={})
