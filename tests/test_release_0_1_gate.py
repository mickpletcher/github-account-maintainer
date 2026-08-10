import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import httpx
import pytest
from pydantic import SecretStr

import github_account_maintainer.pilot as pilot_module
from github_account_maintainer.account_audit import AccountAuditReport, run_account_audit
from github_account_maintainer.auth import ClientFactory
from github_account_maintainer.config import AppConfig, default_config, write_config
from github_account_maintainer.credentials import CredentialResolutionError, ResolvedCredential
from github_account_maintainer.github_api import GitHubApiClient
from github_account_maintainer.models import RunStatus
from github_account_maintainer.pilot import (
    PilotConfigurationError,
    PilotVerificationError,
    ReleasePilotSummary,
    main,
    render_pilot_markdown,
    run_release_pilot,
)
from github_account_maintainer.reporting import render_account_audit_markdown, render_json

FIXTURES = Path(__file__).parent / "fixtures"
SCENARIO = cast(dict[str, object], json.loads((FIXTURES / "release-0.1-pilot.json").read_text(encoding="utf-8")))
GITHUB_FIXTURES = FIXTURES / "github"


def test_release_gate_manifest_maps_every_requirement_to_evidence() -> None:
    manifest = cast(
        dict[str, object],
        json.loads((Path("release") / "release-0.1-gate.json").read_text(encoding="utf-8")),
    )
    criteria = cast(list[dict[str, object]], manifest["criteria"])
    live_pilot = cast(dict[str, object], manifest["live_pilot"])

    assert manifest["schema_version"] == "1.0"
    assert manifest["status"] == "ready_for_local_pilot"
    assert [criterion["id"] for criterion in criteria] == [f"R01-{number:02}" for number in range(1, 11)]
    assert all(cast(list[str], criterion["automated_evidence"]) for criterion in criteria)
    assert live_pilot["minimum_repeats"] == 2
    assert live_pilot["report_detail"] == "minimal"
    assert live_pilot["summary_detail"] == "count_only"
    assert live_pilot["request_mode"] == "get_only"
    assert live_pilot["automatic_write_operations"] == []


def test_release_pilot_repeats_complete_get_only_contract_without_private_output() -> None:
    requests: list[httpx.Request] = []
    summary = _run_pilot(_handler(requests))
    serialized = summary.model_dump_json()
    markdown = render_pilot_markdown(summary)

    assert summary.status == "passed"
    assert summary.repeated_runs == 2
    assert summary.repository_count == 2
    assert summary.requested_repository_count == 2
    assert summary.audited_repository_count == 2
    assert summary.policy_binding_count == 2
    assert summary.check_result_count == 28
    assert summary.finding_count >= 3
    assert summary.repeated_results_match is True
    assert summary.minimal_detail_enforced is True
    assert summary.request_mode == "get_only"
    assert summary.automatic_write_operations == ()
    assert "release-pilot/public-contract" not in serialized
    assert "release-pilot/private-contract" not in serialized
    assert "repository_id" not in serialized
    assert "# Release 0.1 Read-Only Pilot" in markdown
    assert requests and all(request.method == "GET" for request in requests)
    assert sum(request.url.path == "/user/repos" for request in requests) == 4


def test_release_contract_report_is_versioned_deterministic_and_redacted() -> None:
    first = _run_audit(_handler([]))
    second = _run_audit(_handler([]))
    json_output = render_json(first)
    markdown = render_account_audit_markdown(first)

    assert first.status is RunStatus.COMPLETE
    assert len(first.results) == 28
    assert len(first.bindings) == 2
    assert all(len(binding.policy_hash) == 64 for binding in first.bindings)
    assert [binding.policy_hash for binding in first.bindings] == [binding.policy_hash for binding in second.bindings]
    assert '"schema_version": "1.0"' in json_output
    assert "current=" in markdown and "desired=" in markdown
    assert "release-pilot/private-contract" not in json_output
    assert "release-pilot/private-contract" not in markdown
    assert "nonpublic-repository:102" in json_output


def test_release_pilot_fails_closed_on_partial_coverage() -> None:
    requests: list[httpx.Request] = []
    base_handler = _handler(requests)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/release-pilot/private-contract/languages":
            return httpx.Response(403, json={"message": "forbidden"})
        return base_handler(request)

    with pytest.raises(PilotVerificationError, match="partial coverage"):
        _run_pilot(handler)


@pytest.mark.parametrize("repeats", [1, 6])
def test_release_pilot_rejects_invalid_repeat_count(repeats: int) -> None:
    with pytest.raises(PilotConfigurationError, match="between 2 and 5"):
        run_release_pilot(default_config("release-pilot"), repeats=repeats)


def test_release_pilot_rejects_full_detail_and_unsafe_config() -> None:
    base = default_config("release-pilot")
    full = base.model_copy(update={"local_data": base.local_data.model_copy(update={"report_detail": "full"})})
    unsafe = base.model_copy(
        update={"safety": base.safety.model_copy(update={"automatic_write_operations": ("metadata.update",)})}
    )

    with pytest.raises(PilotConfigurationError, match="minimal report detail"):
        run_release_pilot(full)
    with pytest.raises(PilotConfigurationError, match="empty automatic-write allowlist"):
        run_release_pilot(unsafe)


def test_release_pilot_requires_semantically_repeatable_results() -> None:
    reports = [_run_audit(_handler([])), _run_audit(_handler([]))]
    changed_result = reports[1].results[0].model_copy(update={"evidence": ("changed",)})
    reports[1] = reports[1].model_copy(update={"results": (changed_result, *reports[1].results[1:])})

    def next_report(_config: AppConfig, **_kwargs: object) -> AccountAuditReport:
        return reports.pop(0)

    with pytest.raises(PilotVerificationError, match="different semantic results"):
        run_release_pilot(default_config("release-pilot"), run_audit=next_report)


def test_release_pilot_main_outputs_only_count_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.yaml"
    write_config(default_config("release-pilot"), config_path)
    expected = ReleasePilotSummary(
        tool_version="0.1.0.dev0",
        github_api_version="2026-03-10",
        repeated_runs=2,
        repository_count=2,
        requested_repository_count=2,
        audited_repository_count=2,
        policy_binding_count=2,
        check_result_count=28,
        coverage_record_count=34,
        finding_count=3,
    )

    def return_summary(_config: AppConfig, *, repeats: int) -> ReleasePilotSummary:
        assert repeats == 2
        return expected

    monkeypatch.setattr(pilot_module, "run_release_pilot", return_summary)

    exit_code = main(["--config", str(config_path), "--format", "json"])
    output = capsys.readouterr()

    assert exit_code == 0
    assert '"status": "passed"' in output.out
    assert "release-pilot" not in output.out
    assert output.err == ""


def test_release_pilot_main_returns_three_for_missing_config(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["--config", str(tmp_path / "missing.yaml")])
    output = capsys.readouterr()

    assert exit_code == 3
    assert "Invalid pilot configuration: FileNotFoundError" in output.err


def test_release_pilot_main_redacts_operational_error_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.yaml"
    write_config(default_config("release-pilot"), config_path)

    def fail_pilot(_config: AppConfig, *, repeats: int) -> ReleasePilotSummary:
        raise CredentialResolutionError(f"private-reference-{repeats}")

    monkeypatch.setattr(pilot_module, "run_release_pilot", fail_pilot)

    exit_code = main(["--config", str(config_path)])
    output = capsys.readouterr()

    assert exit_code == 2
    assert "CredentialResolutionError" in output.err
    assert "private-reference" not in output.err


def _run_pilot(handler: Callable[[httpx.Request], httpx.Response]) -> ReleasePilotSummary:
    return run_release_pilot(
        default_config("release-pilot"),
        credential_resolver=_credential_resolver,
        make_client=_client_factory(httpx.MockTransport(handler)),
    )


def _run_audit(handler: Callable[[httpx.Request], httpx.Response]) -> AccountAuditReport:
    return run_account_audit(
        default_config("release-pilot"),
        credential_resolver=_credential_resolver,
        make_client=_client_factory(httpx.MockTransport(handler)),
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


def _handler(requests: list[httpx.Request]) -> Callable[[httpx.Request], httpx.Response]:
    account = cast(dict[str, object], SCENARIO["account"])
    pages = cast(list[list[dict[str, object]]], SCENARIO["inventory_pages"])
    repositories = cast(dict[str, dict[str, object]], SCENARIO["repositories"])

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/user":
            return httpx.Response(200, json=account)
        if request.url.path == "/user/repos":
            if request.url.params.get("page") == "2":
                return httpx.Response(200, json=pages[1], headers=_permissions("metadata=read"))
            return httpx.Response(
                200,
                json=pages[0],
                headers={
                    **_permissions("metadata=read"),
                    "Link": '<https://api.github.com/user/repos?page=2>; rel="next"',
                },
            )
        if request.url.path.endswith("/languages"):
            return httpx.Response(200, json=_fixture("classification-languages.json"))
        if request.url.path.endswith("/community/profile"):
            name = (
                "community-profile-missing.json"
                if "private-contract" in request.url.path
                else "community-profile-complete.json"
            )
            return httpx.Response(200, json=_fixture(name), headers=_permissions("contents=read"))
        if "/contents" in request.url.path:
            if request.url.path.endswith("/contents"):
                return httpx.Response(200, json=_fixture("contents-root.json"), headers=_permissions("contents=read"))
            if request.url.path.endswith("/contents/.github"):
                return httpx.Response(200, json=_fixture("contents-github.json"), headers=_permissions("contents=read"))
            return httpx.Response(404, json={"message": "not found"}, headers=_permissions("contents=read"))
        if request.url.path.startswith("/repos/"):
            api_name = request.url.path.removeprefix("/repos/")
            contract = repositories[api_name]
            return httpx.Response(200, json=_metadata(contract), headers=_permissions("metadata=read"))
        raise AssertionError(f"Unexpected request: {request.url}")

    return handler


def _metadata(contract: dict[str, object]) -> dict[str, object]:
    classification = cast(dict[str, object], _fixture("classification-metadata.json"))
    missing = cast(bool, contract["missing_required_metadata"])
    checks_fixture = "repository-metadata-missing.json" if missing else "repository-metadata-complete.json"
    metadata = {**classification, **cast(dict[str, object], _fixture(checks_fixture))}
    metadata["id"] = contract["id"]
    metadata["visibility"] = contract["visibility"]
    metadata["archived"] = False
    metadata["fork"] = False
    return metadata


def _fixture(name: str) -> object:
    return json.loads((GITHUB_FIXTURES / name).read_text(encoding="utf-8"))


def _permissions(value: str) -> dict[str, str]:
    return {"X-Accepted-GitHub-Permissions": value}
