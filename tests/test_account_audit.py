import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

import httpx
from pydantic import SecretStr

from github_account_maintainer.account_audit import AccountAuditReport, audit_exit_code, run_account_audit
from github_account_maintainer.auth import ClientFactory
from github_account_maintainer.checks import ALL_CHECKS
from github_account_maintainer.config import AppConfig, default_config
from github_account_maintainer.credentials import ResolvedCredential
from github_account_maintainer.github_api import GitHubApiClient
from github_account_maintainer.models import CoverageState, RunStatus
from github_account_maintainer.reporting import render_account_audit_markdown, render_json

FIXTURES = Path(__file__).parent / "fixtures" / "github"
NOW = datetime(2026, 8, 10, 15, tzinfo=UTC)


def test_account_audit_aggregates_multiple_repositories_and_redacts_private_identity() -> None:
    requests: list[httpx.Request] = []
    repositories = [
        _inventory_repository(101, "example/public"),
        _inventory_repository(102, "example/private-project", private=True),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _complete_response(request, repositories)

    report = _run(handler)
    serialized = render_json(report)

    assert report.status is RunStatus.COMPLETE
    assert report.repository_count == 2
    assert report.requested_repository_count == 2
    assert report.audited_repository_count == 2
    assert len(report.bindings) == 2
    assert len(report.results) == 2 * len(ALL_CHECKS)
    assert len(report.findings) == 0
    assert report.finding_summary.threshold.value == "low"
    assert audit_exit_code(report) == 0
    assert "example/private-project" not in serialized
    assert "nonpublic-repository:102" in serialized
    assert all(request.method == "GET" for request in requests)
    assert sum(request.url.path == "/repos/example/public" for request in requests) == 1


def test_account_audit_returns_one_when_complete_findings_reach_threshold() -> None:
    repositories = [_inventory_repository(101, "example/public")]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/example/public":
            return httpx.Response(200, json=_metadata(101, missing_required=True))
        return _complete_response(request, repositories)

    report = _run(handler)

    assert report.status is RunStatus.COMPLETE
    assert report.finding_summary.low >= 3
    assert report.finding_summary.threshold_met is True
    assert audit_exit_code(report) == 1


def test_account_audit_honors_configured_severity_threshold() -> None:
    repositories = [_inventory_repository(101, "example/public")]
    base = default_config("example")
    config = base.model_copy(update={"audit": base.audit.model_copy(update={"failure_threshold": "medium"})})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/example/public":
            return httpx.Response(200, json=_metadata(101, missing_required=True))
        return _complete_response(request, repositories)

    report = _run(handler, config=config)

    assert report.finding_summary.low >= 3
    assert report.finding_summary.threshold.value == "medium"
    assert report.finding_summary.threshold_met is False
    assert audit_exit_code(report) == 0


def test_account_audit_continues_after_inaccessible_repository_and_exits_two() -> None:
    repositories = [
        _inventory_repository(101, "example/public"),
        _inventory_repository(102, "example/inaccessible"),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/example/inaccessible/languages":
            return httpx.Response(
                403,
                json={"message": "forbidden"},
                headers={"X-Accepted-GitHub-Permissions": "metadata=read"},
            )
        return _complete_response(request, repositories)

    report = _run(handler)

    assert report.status is RunStatus.PARTIAL
    assert report.audited_repository_count == 1
    assert len(report.results) == 2 * len(ALL_CHECKS)
    assert any(record.repository_id == 102 and record.state is CoverageState.INACCESSIBLE for record in report.coverage)
    assert audit_exit_code(report) == 2


def test_account_audit_marks_excluded_repository_not_requested_without_fetching_it() -> None:
    repositories = [_inventory_repository(101, "example/excluded")]
    config = default_config("example").model_copy(
        update={
            "repositories": default_config("example").repositories.model_copy(
                update={"exclude_patterns": ["example/excluded"]}
            )
        }
    )
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return _complete_response(request, repositories)

    report = _run(handler, config=config)

    assert report.status is RunStatus.COMPLETE
    assert report.requested_repository_count == 0
    assert report.audited_repository_count == 0
    assert all(result.coverage_state is CoverageState.NOT_REQUESTED for result in report.results)
    assert not any(path.startswith("/repos/") for path in requests)


def test_account_audit_invalid_classification_contract_is_partial_and_safe() -> None:
    repositories = [_inventory_repository(101, "example/public")]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/example/public":
            payload = _metadata(101)
            payload["owner"] = {"type": "Bot"}
            return httpx.Response(200, json=payload)
        return _complete_response(request, repositories)

    report = _run(handler)

    assert report.status is RunStatus.PARTIAL
    assert report.bindings == ()
    assert all(result.coverage_state is CoverageState.FAILED for result in report.results)
    assert all(record.detail != "example/public" for record in report.coverage)


def test_account_audit_markdown_contains_contract_details() -> None:
    repositories = [_inventory_repository(101, "example/public")]
    report = _run(lambda request: _complete_response(request, repositories))

    output = render_account_audit_markdown(report)

    assert "# GitHub Account Audit" in output
    assert "Repositories audited: `1`" in output
    assert "## Policy bindings" in output
    assert "## Results" in output
    assert "## Coverage" in output
    assert output.endswith("\n")


def _run(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    config: AppConfig | None = None,
) -> AccountAuditReport:
    transport = httpx.MockTransport(handler)
    return run_account_audit(
        config or default_config("example"),
        credential_resolver=_credential_resolver,
        make_client=_client_factory(transport),
        now=lambda: NOW,
    )


def _credential_resolver(reference: str) -> ResolvedCredential:
    role = "audit" if reference.endswith("/audit") else "discovery"
    return ResolvedCredential(secret=SecretStr(f"{role}-token"), source=f"env:{role.upper()}_TOKEN")


def _client_factory(transport: httpx.MockTransport) -> ClientFactory:
    def factory(token: str, host: str) -> GitHubApiClient:
        assert token in {"discovery-token", "audit-token"}
        assert host == "github.com"
        return GitHubApiClient(token, transport=transport)

    return factory


def _inventory_repository(
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
        "permissions": {"admin": True, "pull": True},
    }


def _metadata(repository_id: int, *, missing_required: bool = False) -> dict[str, object]:
    return {
        "id": repository_id,
        "description": None if missing_required else "Synthetic repository",
        "homepage": None,
        "topics": [] if missing_required else ["automation"],
        "language": None if missing_required else "PowerShell",
        "visibility": "private" if repository_id == 102 else "public",
        "archived": False,
        "fork": False,
        "default_branch": "main",
        "owner": {"type": "User"},
        "is_template": False,
        "mirror_url": None,
        "size": 42,
        "has_pages": False,
        "pushed_at": "2026-08-01T12:00:00Z",
        "security_and_analysis": {
            "advanced_security": {"status": "enabled"},
            "code_security": {"status": "enabled"},
            "secret_scanning": {"status": "enabled"},
            "secret_scanning_push_protection": {"status": "enabled"},
        },
    }


def _complete_response(request: httpx.Request, repositories: list[dict[str, object]]) -> httpx.Response:
    if request.url.path == "/user":
        return httpx.Response(200, json={"login": "example", "id": 1})
    if request.url.path == "/user/repos":
        return httpx.Response(200, json=repositories, headers={"X-Accepted-GitHub-Permissions": "metadata=read"})
    if request.url.path.endswith("/languages"):
        return httpx.Response(200, json={"PowerShell": 200})
    if request.url.path.endswith("/rules/branches/main"):
        return httpx.Response(200, json=[{"type": "pull_request"}, {"type": "required_status_checks"}])
    if request.url.path.endswith("/branches/main/protection"):
        return httpx.Response(
            200,
            json={
                "required_pull_request_reviews": {"required_approving_review_count": 1},
                "required_status_checks": {"contexts": ["validation"], "checks": []},
            },
        )
    if request.url.path.endswith("/actions/permissions"):
        return httpx.Response(
            200,
            json={"enabled": True, "allowed_actions": "selected", "sha_pinning_required": True},
        )
    if request.url.path.endswith("/actions/permissions/workflow"):
        return httpx.Response(
            200,
            json={"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False},
        )
    if request.url.path.endswith("/vulnerability-alerts"):
        return httpx.Response(204)
    if request.url.path.endswith("/automated-security-fixes"):
        return httpx.Response(200, json={"enabled": True, "paused": False})
    if request.url.path.endswith("/code-scanning/default-setup"):
        return httpx.Response(200, json={"state": "configured"})
    if request.url.path.endswith("/private-vulnerability-reporting"):
        return httpx.Response(200, json={"enabled": True})
    if request.url.path.endswith("/community/profile"):
        return httpx.Response(200, json=_fixture("community-profile-complete.json"))
    if "/contents" in request.url.path:
        if request.url.path.endswith("/contents"):
            return httpx.Response(200, json=_fixture("contents-root.json"))
        if request.url.path.endswith("/contents/.github"):
            return httpx.Response(200, json=_fixture("contents-github.json"))
        return httpx.Response(404, json={"message": "not found"})
    if request.url.path.startswith("/repos/"):
        api_name = request.url.path.removeprefix("/repos/")
        inventory = next(item for item in repositories if item["full_name"] == api_name)
        return httpx.Response(200, json=_metadata(cast(int, inventory["id"])))
    raise AssertionError(f"Unexpected request: {request.url}")


def _fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
