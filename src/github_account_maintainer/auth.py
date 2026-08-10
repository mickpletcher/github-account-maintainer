from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

import httpx

from github_account_maintainer import __version__
from github_account_maintainer.config import AppConfig
from github_account_maintainer.constants import GITHUB_API_VERSION
from github_account_maintainer.credentials import ResolvedCredential, resolve_credential
from github_account_maintainer.github_api import GitHubApiClient, accepted_permissions
from github_account_maintainer.models import AuthReport

CredentialResolver = Callable[[str], ResolvedCredential]
ClientFactory = Callable[[str, str], GitHubApiClient]


class AuthenticationPreflightError(RuntimeError):
    pass


def github_api_url(host: str) -> str:
    return "https://api.github.com" if host.casefold() == "github.com" else f"https://{host}/api/v3"


def client_factory(token: str, host: str) -> GitHubApiClient:
    return GitHubApiClient(token, base_url=github_api_url(host))


def run_auth_check(
    config: AppConfig,
    *,
    credential_resolver: CredentialResolver = resolve_credential,
    make_client: ClientFactory = client_factory,
) -> AuthReport:
    credential = credential_resolver(config.credentials.discovery)
    with make_client(credential.secret.get_secret_value(), config.account.github_host) as client:
        response = client.get("/user")

    return auth_report_from_response(config, credential, response)


def auth_report_from_response(
    config: AppConfig,
    credential: ResolvedCredential,
    response: httpx.Response,
) -> AuthReport:
    try:
        payload = cast(object, response.json())
    except ValueError:
        raise AuthenticationPreflightError("GitHub user response was not valid JSON") from None
    if not isinstance(payload, dict):
        raise AuthenticationPreflightError("GitHub user response was not a JSON object")
    user_payload = cast(dict[str, object], payload)
    login = user_payload.get("login")
    user_id = user_payload.get("id")
    if not isinstance(login, str) or not isinstance(user_id, int):
        raise AuthenticationPreflightError("GitHub user response did not contain a valid identity")
    if login.casefold() != config.account.login.casefold():
        raise AuthenticationPreflightError(f"Authenticated GitHub login does not match configured login: {login}")

    return AuthReport(
        tool_version=__version__,
        github_api_version=GITHUB_API_VERSION,
        configured_login=config.account.login,
        authenticated_login=login,
        authenticated_user_id=user_id,
        credential_source=credential.source,
        oauth_scopes=_split_header(response.headers.get("X-OAuth-Scopes")),
        accepted_oauth_scopes=_split_header(response.headers.get("X-Accepted-OAuth-Scopes")),
        accepted_permissions=accepted_permissions(response),
        rate_limit_remaining=_parse_optional_int(response.headers.get("X-RateLimit-Remaining")),
        checked_at=datetime.now(UTC),
    )


def _split_header(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(sorted(item.strip() for item in value.split(",") if item.strip()))


def _parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
