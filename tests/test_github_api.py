import httpx
import pytest

from github_account_maintainer.constants import GITHUB_API_VERSION
from github_account_maintainer.github_api import (
    GitHubApiClient,
    GitHubApiError,
    GitHubTransportError,
    accepted_permissions,
)


def test_get_sets_required_headers_without_exposing_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.headers["X-GitHub-Api-Version"] == GITHUB_API_VERSION
        assert request.headers["Accept"] == "application/vnd.github+json"
        return httpx.Response(
            200,
            json={"login": "octocat"},
            headers={"X-Accepted-GitHub-Permissions": "metadata=read"},
        )

    with GitHubApiClient("test-token", transport=httpx.MockTransport(handler)) as client:
        response = client.get("/user")

    assert response.json() == {"login": "octocat"}
    assert accepted_permissions(response) == "metadata=read"
    assert "test-token" not in repr(response)


def test_paginate_follows_same_host_link() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=[{"id": 2}])
        return httpx.Response(
            200,
            json=[{"id": 1}],
            headers={"Link": '<https://api.github.com/user/repos?page=2>; rel="next"'},
        )

    with GitHubApiClient("test-token", transport=httpx.MockTransport(handler)) as client:
        items = list(client.paginate("/user/repos", params={"per_page": 100}))

    assert items == [{"id": 1}, {"id": 2}]
    assert len(requests) == 2


def test_paginate_rejects_cross_host_link_before_sending_token() -> None:
    request_count = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            200,
            json=[{"id": 1}],
            headers={"Link": '<https://example.com/steal>; rel="next"'},
        )

    with (
        GitHubApiClient("test-token", transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ValueError, match="changed origins"),
    ):
        list(client.paginate("/user/repos"))

    assert request_count == 1


def test_get_rejects_cross_origin_url_before_sending_token() -> None:
    request_count = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(200, json={})

    with (
        GitHubApiClient("test-token", transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ValueError, match="changed origins"),
    ):
        client.get("http://api.github.com/user")

    assert request_count == 0


def test_get_follows_same_origin_redirect() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request.url.path == "/old":
            return httpx.Response(301, headers={"Location": "/new"})
        return httpx.Response(200, json={"moved": True})

    with GitHubApiClient("test-token", transport=httpx.MockTransport(handler)) as client:
        response = client.get("/old")

    assert response.json() == {"moved": True}
    assert request_count == 2


def test_paginate_requires_array_payload() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"id": 1}))

    with GitHubApiClient("test-token", transport=transport) as client, pytest.raises(TypeError, match="JSON array"):
        list(client.paginate("/user/repos"))


@pytest.mark.parametrize(
    ("status_code", "headers", "kind"),
    [
        (401, {}, "authentication"),
        (403, {}, "authorization"),
        (403, {"X-RateLimit-Remaining": "0"}, "rate_limit"),
        (429, {"Retry-After": "60"}, "rate_limit"),
        (404, {}, "not_found"),
        (500, {}, "server"),
        (422, {}, "api_error"),
    ],
)
def test_get_classifies_api_failures(status_code: int, headers: dict[str, str], kind: str) -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(status_code, headers=headers, json={}))

    with GitHubApiClient("test-token", transport=transport) as client, pytest.raises(GitHubApiError) as error:
        client.get("/user")

    assert error.value.kind == kind


def test_get_redacts_transport_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private transport detail", request=request)

    with (
        GitHubApiClient("test-token", transport=httpx.MockTransport(handler)) as client,
        pytest.raises(GitHubTransportError, match="ConnectError") as error,
    ):
        client.get("/user")

    assert "private transport detail" not in str(error.value)
