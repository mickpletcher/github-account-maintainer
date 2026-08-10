import httpx
import pytest
from pydantic import SecretStr

from github_account_maintainer.auth import AuthenticationPreflightError, ClientFactory, run_auth_check
from github_account_maintainer.config import default_config
from github_account_maintainer.credentials import ResolvedCredential
from github_account_maintainer.github_api import GitHubApiClient, GitHubApiError


def credential_resolver(_reference: str) -> ResolvedCredential:
    return ResolvedCredential(secret=SecretStr("test-token"), source="env:TEST_TOKEN")


def make_client(handler: httpx.MockTransport) -> ClientFactory:
    def factory(token: str, host: str) -> GitHubApiClient:
        assert token == "test-token"
        assert host == "github.com"
        return GitHubApiClient(token, transport=handler)

    return factory


def test_auth_check_verifies_identity_and_reports_headers() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"login": "MickPletcher", "id": 42},
            headers={
                "X-OAuth-Scopes": "repo, read:org",
                "X-Accepted-OAuth-Scopes": "read:user",
                "X-Accepted-GitHub-Permissions": "metadata=read",
                "X-RateLimit-Remaining": "4999",
            },
        )

    report = run_auth_check(
        default_config("mickpletcher"),
        credential_resolver=credential_resolver,
        make_client=make_client(httpx.MockTransport(handler)),
    )

    assert report.authenticated_login == "MickPletcher"
    assert report.authenticated_user_id == 42
    assert report.oauth_scopes == ("read:org", "repo")
    assert report.accepted_permissions == "metadata=read"
    assert report.rate_limit_remaining == 4999


def test_auth_check_rejects_identity_mismatch() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"login": "other", "id": 1}))

    with pytest.raises(AuthenticationPreflightError, match="does not match"):
        run_auth_check(
            default_config("mickpletcher"),
            credential_resolver=credential_resolver,
            make_client=make_client(transport),
        )


@pytest.mark.parametrize("payload", [[], {}, {"login": "mickpletcher"}, {"login": 4, "id": 1}])
def test_auth_check_rejects_invalid_identity_payload(payload: object) -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=payload))

    with pytest.raises(AuthenticationPreflightError, match="identity|object"):
        run_auth_check(
            default_config("mickpletcher"),
            credential_resolver=credential_resolver,
            make_client=make_client(transport),
        )


def test_auth_check_classifies_authentication_failure() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(401, json={"message": "Bad credentials"}))

    with pytest.raises(GitHubApiError) as error:
        run_auth_check(
            default_config("mickpletcher"),
            credential_resolver=credential_resolver,
            make_client=make_client(transport),
        )

    assert error.value.kind == "authentication"


def test_auth_check_rejects_invalid_json() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, content=b"not-json"))

    with pytest.raises(AuthenticationPreflightError, match="valid JSON"):
        run_auth_check(
            default_config("mickpletcher"),
            credential_resolver=credential_resolver,
            make_client=make_client(transport),
        )
