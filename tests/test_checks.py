import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from github_account_maintainer.checks import RepositoryAuditTarget, audit_repository, run_repository_checks
from github_account_maintainer.config import AppConfig, PolicyHierarchyConfig, default_config
from github_account_maintainer.credentials import ResolvedCredential
from github_account_maintainer.github_api import GitHubApiClient
from github_account_maintainer.models import (
    CheckOutcome,
    CheckResult,
    CoverageState,
    RemediationClass,
    RepositoryAuditReport,
    RunStatus,
)
from github_account_maintainer.policy import PolicyTarget, ResolvedPolicy, resolve_policy
from github_account_maintainer.reporting import render_json, render_repository_audit_markdown

FIXTURES = Path(__file__).parent / "fixtures" / "github"
OBSERVED_AT = datetime(2026, 8, 10, 15, tzinfo=UTC)
TARGET = RepositoryAuditTarget(repository_id=101, api_name="example/synthetic", display_name="example/synthetic")


def test_complete_contract_fixture_reports_explicit_outcomes_without_findings() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _response_for_complete_fixture(request)

    report = _run(handler)

    assert report.status is RunStatus.COMPLETE
    assert len(report.results) == 14
    assert report.findings == ()
    assert _result(report, "metadata.description").outcome is CheckOutcome.COMPLIANT
    assert _result(report, "metadata.homepage").outcome is CheckOutcome.OBSERVED
    assert _result(report, "community.security").outcome is CheckOutcome.COMPLIANT
    assert _result(report, "community.support").outcome is CheckOutcome.OBSERVED
    assert all(record.state is CoverageState.AUDITED for record in report.coverage)
    assert report.accepted_permissions == ("contents=read", "metadata=read")
    assert requests and all(request.method == "GET" for request in requests)
    assert all("/git/" not in request.url.path for request in requests)


def test_missing_required_metadata_and_files_create_privacy_safe_findings() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/example/synthetic":
            return _fixture_response("repository-metadata-missing.json", permission="metadata=read")
        if request.url.path == "/repos/example/synthetic/community/profile":
            return _fixture_response("community-profile-missing.json", permission="contents=read")
        if request.url.path.endswith("/contents"):
            return httpx.Response(200, json=[], headers=_permission_header("contents=read"))
        return httpx.Response(404, json={})

    report = _run(handler)
    finding_checks = {finding.check_id for finding in report.findings}

    assert report.status is RunStatus.COMPLETE
    assert finding_checks == {
        "metadata.description",
        "metadata.topics",
        "metadata.primary_language",
        "community.readme",
        "community.license",
        "community.security",
    }
    assert all(finding.severity.value == "low" for finding in report.findings)
    assert _result(report, "metadata.description").current_state == {"present": False}
    assert _result(report, "metadata.visibility").outcome is CheckOutcome.OBSERVED
    assert _result(report, "community.readme").outcome is CheckOutcome.NONCOMPLIANT
    assert all("example/synthetic" not in evidence for finding in report.findings for evidence in finding.evidence)
    assert {finding.remediation_class for finding in report.findings} == {
        RemediationClass.APPROVAL_REQUIRED,
        RemediationClass.PULL_REQUEST,
    }


def test_content_permission_failure_is_inaccessible_not_noncompliant() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/example/synthetic":
            return _fixture_response("repository-metadata-complete.json", permission="metadata=read")
        return httpx.Response(
            403,
            json={"message": "forbidden"},
            headers=_permission_header("contents=read"),
        )

    report = _run(handler)

    assert report.status is RunStatus.PARTIAL
    assert all(
        result.outcome is CheckOutcome.INACCESSIBLE for result in report.results if result.category == "community"
    )
    assert all(
        result.coverage_state is CoverageState.INACCESSIBLE
        for result in report.results
        if result.category == "community"
    )
    assert not any(finding.category == "community" for finding in report.findings)


def test_invalid_metadata_contract_marks_every_check_unknown() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 101, "topics": "invalid"})

    report = _run(handler)

    assert report.status is RunStatus.PARTIAL
    assert len(report.results) == 14
    assert all(result.outcome is CheckOutcome.UNKNOWN for result in report.results)
    assert all(result.coverage_state is CoverageState.FAILED for result in report.results)
    assert report.findings == ()


def test_inherited_community_file_has_explicit_inherited_coverage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/example/synthetic":
            return _fixture_response("repository-metadata-complete.json")
        if request.url.path == "/repos/example/synthetic/community/profile":
            payload = cast(dict[str, object], _fixture("community-profile-missing.json"))
            files = cast(dict[str, object], payload["files"])
            files["readme"] = {"url": "https://api.github.com/repos/example/.github/contents/profile/README.md"}
            return httpx.Response(200, json=payload)
        return httpx.Response(404, json={})

    report = _run(handler)
    result = _result(report, "community.readme")

    assert result.outcome is CheckOutcome.COMPLIANT
    assert result.coverage_state is CoverageState.INHERITED
    assert result.current_state == {"present": True, "source": "inherited"}


def test_active_policy_exception_skips_check_without_finding() -> None:
    hierarchy = PolicyHierarchyConfig.model_validate(
        {
            "exceptions": [
                {
                    "exception_id": "EXC-001",
                    "target_selector": "example/synthetic",
                    "check_ids": ["metadata.description"],
                    "reason": "Synthetic exception",
                    "creator": "test",
                    "created_at": "2026-08-01T00:00:00Z",
                    "expires_at": "2026-09-01T00:00:00Z",
                }
            ]
        }
    )
    config = default_config("example").model_copy(update={"policy": hierarchy})
    policy = _policy(config)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/example/synthetic":
            return _fixture_response("repository-metadata-missing.json")
        if request.url.path == "/repos/example/synthetic/community/profile":
            return _fixture_response("community-profile-missing.json")
        return httpx.Response(404, json={})

    report = _run(handler, config=config, policy=policy)
    result = _result(report, "metadata.description")

    assert result.outcome is CheckOutcome.UNKNOWN
    assert result.coverage_state is CoverageState.SKIPPED_BY_POLICY
    assert not any(finding.check_id == "metadata.description" for finding in report.findings)


def test_audit_repository_uses_audit_credential_and_checks_identity() -> None:
    config = default_config("example")
    resolved_references: list[str] = []

    def credential_resolver(reference: str) -> ResolvedCredential:
        resolved_references.append(reference)
        return ResolvedCredential(source="keyring:audit", secret=SecretStr("audit-token"))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "example", "id": 7})
        return _response_for_complete_fixture(request)

    def make_client(token: str, host: str) -> GitHubApiClient:
        assert token == "audit-token"
        assert host == "github.com"
        return GitHubApiClient(token, transport=httpx.MockTransport(handler))

    report = audit_repository(
        config,
        TARGET,
        _policy(config),
        credential_resolver=credential_resolver,
        make_client=make_client,
        now=lambda: OBSERVED_AT,
    )

    assert resolved_references == [config.credentials.audit]
    assert report.credential_source == "keyring:audit"


def test_repository_target_and_policy_binding_fail_closed() -> None:
    for invalid_name in ("example/repo/extra", "../repo"):
        with pytest.raises(ValidationError):
            RepositoryAuditTarget(repository_id=1, api_name=invalid_name, display_name="repo")

    with pytest.raises(ValueError, match="does not match"):
        audit_repository(default_config("example"), TARGET, _policy(default_config("example"), "other/repo"))


def test_repository_report_renderers_preserve_redacted_display_name() -> None:
    private_target = TARGET.model_copy(update={"display_name": "nonpublic-repository:101"})
    report = _run(_response_for_complete_fixture, target=private_target)

    json_output = render_json(report)
    markdown_output = render_repository_audit_markdown(report)

    assert '"schema_version": "1.0"' in json_output
    assert "nonpublic-repository:101" in json_output
    assert "example/synthetic" not in json_output
    assert "# GitHub Repository Audit" in markdown_output
    assert "`community.security`: `compliant` (`audited`)" in markdown_output
    assert markdown_output.endswith("\n")


def _run(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    config: AppConfig | None = None,
    policy: ResolvedPolicy | None = None,
    target: RepositoryAuditTarget = TARGET,
) -> RepositoryAuditReport:
    app_config = config if config is not None else default_config("example")
    resolved_policy = policy if policy is not None else _policy(app_config)
    with GitHubApiClient("test-token", transport=httpx.MockTransport(handler)) as client:
        return run_repository_checks(
            client,
            target,
            resolved_policy,
            credential_source="env:TEST_AUDIT_TOKEN",
            now=lambda: OBSERVED_AT,
        )


def _policy(config: AppConfig, repository: str = "example/synthetic") -> ResolvedPolicy:
    return resolve_policy(
        config,
        PolicyTarget(repository=repository, evaluated_at=OBSERVED_AT),
    )


def _result(report: RepositoryAuditReport, check_id: str) -> CheckResult:
    return next(result for result in report.results if result.check_id == check_id)


def _response_for_complete_fixture(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/repos/example/synthetic":
        return _fixture_response("repository-metadata-complete.json", permission="metadata=read")
    if path == "/repos/example/synthetic/community/profile":
        return _fixture_response("community-profile-complete.json", permission="contents=read")
    if path == "/repos/example/synthetic/contents":
        return _fixture_response("contents-root.json", permission="contents=read")
    if path == "/repos/example/synthetic/contents/.github":
        return _fixture_response("contents-github.json", permission="contents=read")
    return httpx.Response(404, json={})


def _fixture_response(name: str, *, permission: str | None = None) -> httpx.Response:
    return httpx.Response(200, json=_fixture(name), headers=_permission_header(permission))


def _fixture(name: str) -> object:
    return cast(object, json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def _permission_header(value: str | None) -> dict[str, str]:
    return {"X-Accepted-GitHub-Permissions": value} if value else {}
