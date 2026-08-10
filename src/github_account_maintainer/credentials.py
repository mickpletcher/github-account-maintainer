import os
from collections.abc import Mapping
from dataclasses import dataclass

import keyring
from keyring.errors import KeyringError
from pydantic import SecretStr


class CredentialResolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResolvedCredential:
    secret: SecretStr
    source: str


def resolve_credential(
    reference: str,
    *,
    environment: Mapping[str, str] | None = None,
) -> ResolvedCredential:
    scheme, separator, target = reference.partition(":")
    if not separator or not target:
        raise CredentialResolutionError("Credential reference must use env:NAME or keyring:SERVICE/ACCOUNT")

    if scheme == "env":
        source = environment if environment is not None else os.environ
        value = source.get(target)
        if not value:
            raise CredentialResolutionError(f"Credential environment variable is not set: {target}")
        return ResolvedCredential(secret=SecretStr(value), source=f"env:{target}")

    if scheme == "keyring":
        service, account_separator, account = target.rpartition("/")
        if not account_separator or not service or not account:
            raise CredentialResolutionError("Keyring reference must use keyring:SERVICE/ACCOUNT")
        try:
            value = keyring.get_password(service, account)
        except KeyringError as error:
            raise CredentialResolutionError(f"Credential keyring failed: {type(error).__name__}") from None
        if not value:
            raise CredentialResolutionError(f"Credential was not found in keyring: {service}/{account}")
        return ResolvedCredential(secret=SecretStr(value), source=f"keyring:{service}/{account}")

    raise CredentialResolutionError(f"Unsupported credential reference scheme: {scheme}")
