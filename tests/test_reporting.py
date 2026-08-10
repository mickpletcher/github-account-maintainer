from datetime import UTC, datetime

from github_account_maintainer.constants import GITHUB_API_VERSION
from github_account_maintainer.models import CoverageRecord, CoverageState, RunReport, RunStatus
from github_account_maintainer.reporting import render_json, render_markdown


def report() -> RunReport:
    timestamp = datetime(2026, 8, 10, 12, tzinfo=UTC)
    return RunReport(
        tool_version="0.1.0.dev0",
        github_api_version=GITHUB_API_VERSION,
        account_display="mickpletcher",
        started_at=timestamp,
        completed_at=timestamp,
        status=RunStatus.COMPLETE,
        coverage=[CoverageRecord(check_id="inventory.repositories", state=CoverageState.AUDITED)],
    )


def test_render_json_is_schema_versioned() -> None:
    output = render_json(report())

    assert '"schema_version": "1.0"' in output
    assert '"github_api_version": "2026-03-10"' in output


def test_render_markdown_contains_coverage() -> None:
    output = render_markdown(report())

    assert "# GitHub Account Maintainer Report" in output
    assert "`inventory.repositories`: `audited`" in output
    assert output.endswith("\n")
