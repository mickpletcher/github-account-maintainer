from datetime import UTC, datetime

from github_account_maintainer.constants import GITHUB_API_VERSION
from github_account_maintainer.models import (
    AuthReport,
    CoverageRecord,
    CoverageState,
    InventoryReport,
    RepositoryInventoryRecord,
    RepositoryPermissions,
    RunReport,
    RunStatus,
)
from github_account_maintainer.reporting import (
    render_auth_markdown,
    render_inventory_markdown,
    render_json,
    render_markdown,
)


def report() -> RunReport:
    timestamp = datetime(2026, 8, 10, 12, tzinfo=UTC)
    return RunReport(
        tool_version="0.1.0.dev0",
        github_api_version=GITHUB_API_VERSION,
        account_display="mickpletcher",
        started_at=timestamp,
        completed_at=timestamp,
        status=RunStatus.COMPLETE,
        policy_hash="0" * 64,
        coverage=[CoverageRecord(check_id="inventory.repositories", state=CoverageState.AUDITED)],
    )


def test_render_json_is_schema_versioned() -> None:
    output = render_json(report())

    assert '"schema_version": "1.0"' in output
    assert '"github_api_version": "2026-03-10"' in output
    assert '"policy_hash": "0000000000000000000000000000000000000000000000000000000000000000"' in output


def test_render_markdown_contains_coverage() -> None:
    output = render_markdown(report())

    assert "# GitHub Account Maintainer Report" in output
    assert "`inventory.repositories`: `audited`" in output
    assert "Policy hash: `0000000000000000000000000000000000000000000000000000000000000000`" in output
    assert output.endswith("\n")


def test_render_auth_markdown_contains_identity_not_secrets() -> None:
    timestamp = datetime(2026, 8, 10, 12, tzinfo=UTC)
    auth_report = AuthReport(
        tool_version="0.1.0.dev0",
        github_api_version=GITHUB_API_VERSION,
        configured_login="mickpletcher",
        authenticated_login="mickpletcher",
        authenticated_user_id=1,
        credential_source="env:TEST_TOKEN",
        oauth_scopes=("repo",),
        checked_at=timestamp,
    )

    output = render_auth_markdown(auth_report)

    assert "Authenticated login: `mickpletcher`" in output
    assert "OAuth scopes: `repo`" in output


def test_render_inventory_markdown_contains_summary_and_redacted_repository() -> None:
    timestamp = datetime(2026, 8, 10, 12, tzinfo=UTC)
    inventory_report = InventoryReport(
        tool_version="0.1.0.dev0",
        github_api_version=GITHUB_API_VERSION,
        account_display="mickpletcher",
        credential_source="env:TEST_TOKEN",
        declared_affiliations=("owner",),
        started_at=timestamp,
        completed_at=timestamp,
        status=RunStatus.COMPLETE,
        pages_read=1,
        duplicates_removed=0,
        repositories=(
            RepositoryInventoryRecord(
                repository_id=2,
                node_id="R_2",
                display_name="nonpublic-repository:2",
                private=True,
                visibility="private",
                archived=False,
                fork=False,
                permissions=RepositoryPermissions(pull=True),
            ),
        ),
        coverage=(CoverageRecord(check_id="inventory.repositories", state=CoverageState.AUDITED),),
    )

    output = render_inventory_markdown(inventory_report)

    assert "Repositories: `1`" in output
    assert "`nonpublic-repository:2` (private)" in output
