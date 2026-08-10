from typing import Literal

import httpx
from pydantic import SecretStr

from github_account_maintainer.auth import ClientFactory
from github_account_maintainer.config import AppConfig, default_config
from github_account_maintainer.credentials import ResolvedCredential
from github_account_maintainer.github_api import GitHubApiClient
from github_account_maintainer.inventory import collect_inventory
from github_account_maintainer.models import CoverageState, RunStatus


def credential_resolver(_reference: str) -> ResolvedCredential:
    return ResolvedCredential(secret=SecretStr("test-token"), source="env:TEST_TOKEN")


def client_factory(transport: httpx.MockTransport) -> ClientFactory:
    def factory(token: str, host: str) -> GitHubApiClient:
        assert token == "test-token"
        assert host == "github.com"
        return GitHubApiClient(token, transport=transport)

    return factory


def repository(
    repository_id: int,
    name: str,
    *,
    private: bool = False,
    visibility: Literal["public", "private", "internal"] | None = None,
) -> dict[str, object]:
    return {
        "id": repository_id,
        "node_id": f"R_{repository_id}",
        "full_name": name,
        "private": private,
        "visibility": visibility or ("private" if private else "public"),
        "archived": False,
        "fork": False,
        "html_url": f"https://github.com/{name}",
        "permissions": {"admin": True, "maintain": True, "push": True, "triage": True, "pull": True},
    }


def test_inventory_paginates_deduplicates_and_redacts_private_repositories() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "mickpletcher", "id": 1})
        if request.url.params.get("page") == "2":
            return httpx.Response(
                200,
                json=[
                    repository(2, "mickpletcher/private-project", private=True),
                    repository(1, "mickpletcher/public"),
                ],
                headers={"X-Accepted-GitHub-Permissions": "metadata=read"},
            )
        assert request.url.params.get("affiliation") == "owner"
        assert request.url.params.get("per_page") == "100"
        return httpx.Response(
            200,
            json=[repository(1, "mickpletcher/public")],
            headers={
                "Link": '<https://api.github.com/user/repos?page=2>; rel="next"',
                "X-Accepted-GitHub-Permissions": "metadata=read",
            },
        )

    report = collect_inventory(
        default_config("mickpletcher"),
        credential_resolver=credential_resolver,
        make_client=client_factory(httpx.MockTransport(handler)),
    )

    assert report.status is RunStatus.COMPLETE
    assert report.pages_read == 2
    assert report.duplicates_removed == 1
    assert len(report.repositories) == 2
    assert report.repositories[1].display_name == "nonpublic-repository:2"
    assert report.repositories[1].html_url is None
    serialized = report.model_dump_json()
    assert "private-project" not in serialized
    assert "https://github.com/mickpletcher/private-project" not in serialized
    assert report.accepted_permissions == ("metadata=read",)
    assert report.coverage[-1].state is CoverageState.AUDITED


def test_inventory_full_detail_includes_private_identity() -> None:
    config = with_report_detail(default_config("mickpletcher"), "full")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "mickpletcher", "id": 1})
        return httpx.Response(200, json=[repository(2, "mickpletcher/private-project", private=True)])

    report = collect_inventory(
        config,
        credential_resolver=credential_resolver,
        make_client=client_factory(httpx.MockTransport(handler)),
    )

    assert report.repositories[0].display_name == "mickpletcher/private-project"
    assert report.repositories[0].html_url == "https://github.com/mickpletcher/private-project"


def test_inventory_minimal_detail_redacts_internal_identity_and_preserves_unknown_permissions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "mickpletcher", "id": 1})
        payload = repository(3, "organization/internal-project", visibility="internal")
        payload.pop("permissions")
        return httpx.Response(200, json=[payload])

    report = collect_inventory(
        default_config("mickpletcher"),
        credential_resolver=credential_resolver,
        make_client=client_factory(httpx.MockTransport(handler)),
    )

    assert report.repositories[0].display_name == "nonpublic-repository:3"
    assert report.repositories[0].html_url is None
    assert report.repositories[0].permissions.admin is None


def test_inventory_rate_limit_after_first_page_returns_partial_report() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "mickpletcher", "id": 1})
        if request.url.params.get("page") == "2":
            return httpx.Response(429, headers={"Retry-After": "60"}, json={"message": "rate limited"})
        return httpx.Response(
            200,
            json=[repository(1, "mickpletcher/public")],
            headers={"Link": '<https://api.github.com/user/repos?page=2>; rel="next"'},
        )

    report = collect_inventory(
        default_config("mickpletcher"),
        credential_resolver=credential_resolver,
        make_client=client_factory(httpx.MockTransport(handler)),
    )

    assert report.status is RunStatus.PARTIAL
    assert report.pages_read == 1
    assert len(report.repositories) == 1
    assert report.coverage[-1].state is CoverageState.FAILED
    assert report.coverage[-1].detail == "rate_limit:429:retry_after=60"


def test_inventory_permission_failure_returns_partial_report() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "mickpletcher", "id": 1})
        return httpx.Response(
            403,
            headers={"X-Accepted-GitHub-Permissions": "metadata=read"},
            json={"message": "forbidden"},
        )

    report = collect_inventory(
        default_config("mickpletcher"),
        credential_resolver=credential_resolver,
        make_client=client_factory(httpx.MockTransport(handler)),
    )

    assert report.status is RunStatus.PARTIAL
    assert report.coverage[-1].detail == "authorization:403"
    assert report.accepted_permissions == ("metadata=read",)


def test_inventory_malformed_repository_returns_partial_report() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "mickpletcher", "id": 1})
        return httpx.Response(200, json=[{"id": 1}])

    report = collect_inventory(
        default_config("mickpletcher"),
        credential_resolver=credential_resolver,
        make_client=client_factory(httpx.MockTransport(handler)),
    )

    assert report.status is RunStatus.PARTIAL
    assert report.coverage[-1].state is CoverageState.FAILED


def test_inventory_rejects_inconsistent_visibility() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "mickpletcher", "id": 1})
        return httpx.Response(200, json=[repository(4, "mickpletcher/conflict", private=True, visibility="public")])

    report = collect_inventory(
        default_config("mickpletcher"),
        credential_resolver=credential_resolver,
        make_client=client_factory(httpx.MockTransport(handler)),
    )

    assert report.status is RunStatus.PARTIAL
    assert "inconsistent visibility" in (report.coverage[-1].detail or "")


def with_report_detail(config: AppConfig, detail: Literal["minimal", "full"]) -> AppConfig:
    return config.model_copy(update={"local_data": config.local_data.model_copy(update={"report_detail": detail})})
