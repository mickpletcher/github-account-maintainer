import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from github_account_maintainer.account_audit import AccountAuditReport, FindingSummary
from github_account_maintainer.config import AppConfig, default_config
from github_account_maintainer.constants import GITHUB_API_VERSION
from github_account_maintainer.history import (
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
    HistoryError,
    history_database_path,
    read_audit_history,
    record_audit_history,
)
from github_account_maintainer.models import (
    CheckOutcome,
    CheckResult,
    CoverageRecord,
    CoverageState,
    Finding,
    RemediationClass,
    RunStatus,
    Severity,
)


def test_records_new_persistent_resolved_and_regressed_transitions(tmp_path: Path) -> None:
    config = history_config(tmp_path)
    started = datetime(2026, 8, 11, 12, tzinfo=UTC)
    finding = sample_finding(started)

    first = record_audit_history(config, report_at(started, RunStatus.COMPLETE, (finding,)))
    partial = record_audit_history(
        config,
        report_at(started + timedelta(minutes=1), RunStatus.PARTIAL, ()),
    )
    persistent = record_audit_history(
        config,
        report_at(started + timedelta(minutes=2), RunStatus.COMPLETE, (finding,)),
    )
    resolved = record_audit_history(
        config,
        report_at(started + timedelta(minutes=3), RunStatus.COMPLETE, ()),
    )
    regressed = record_audit_history(
        config,
        report_at(started + timedelta(minutes=4), RunStatus.COMPLETE, (finding,)),
    )

    assert (first.new, first.persistent, first.resolved, first.regressed) == (1, 0, 0, 0)
    assert (partial.new, partial.persistent, partial.resolved, partial.regressed) == (0, 0, 0, 0)
    assert (persistent.new, persistent.persistent, persistent.resolved, persistent.regressed) == (0, 1, 0, 0)
    assert (resolved.new, resolved.persistent, resolved.resolved, resolved.regressed) == (0, 0, 1, 0)
    assert (regressed.new, regressed.persistent, regressed.resolved, regressed.regressed) == (0, 0, 0, 1)

    history = read_audit_history(config)
    assert history.schema_version == CURRENT_SCHEMA_VERSION
    assert history.total_run_count == 5
    assert history.runs[0].regressed == 1
    assert history.runs[-1].new == 1
    assert read_audit_history(config, limit=2).returned_run_count == 2


def test_history_is_idempotent_for_the_same_report(tmp_path: Path) -> None:
    config = history_config(tmp_path)
    report = report_at(datetime(2026, 8, 11, 12, tzinfo=UTC), RunStatus.COMPLETE, ())

    first = record_audit_history(config, report)
    duplicate = record_audit_history(config, report)

    assert first.recorded is True
    assert duplicate.recorded is False
    assert duplicate.run_id == first.run_id
    assert read_audit_history(config).total_run_count == 1
    with pytest.raises(HistoryError, match="chronological"):
        record_audit_history(config, report.model_copy(update={"status": RunStatus.PARTIAL}))


def test_history_is_isolated_by_hashed_account_identity(tmp_path: Path) -> None:
    first_config = history_config(tmp_path)
    second_config = history_config(tmp_path).model_copy(
        update={"account": first_config.account.model_copy(update={"login": "another-account"})}
    )
    timestamp = datetime(2026, 8, 11, 12, tzinfo=UTC)

    record_audit_history(first_config, report_at(timestamp, RunStatus.COMPLETE, ()))
    record_audit_history(
        second_config,
        report_at(timestamp, RunStatus.COMPLETE, ()).model_copy(update={"account_display": "another-account"}),
    )

    assert read_audit_history(first_config).total_run_count == 1
    assert read_audit_history(second_config).total_run_count == 1
    database_content = history_database_path(first_config).read_bytes()
    assert b"mickpletcher" not in database_content
    assert b"another-account" not in database_content


def test_rejects_report_for_a_different_account(tmp_path: Path) -> None:
    config = history_config(tmp_path)
    report = report_at(datetime(2026, 8, 11, 12, tzinfo=UTC), RunStatus.COMPLETE, ()).model_copy(
        update={"account_display": "another-account"}
    )

    with pytest.raises(HistoryError, match="configured account"):
        record_audit_history(config, report)

    assert not history_database_path(config).exists()


def test_history_database_excludes_private_report_content(tmp_path: Path) -> None:
    config = history_config(tmp_path)
    timestamp = datetime(2026, 8, 11, 12, tzinfo=UTC)
    finding = sample_finding(timestamp)

    record_audit_history(config, report_at(timestamp, RunStatus.COMPLETE, (finding,)))

    database_content = history_database_path(config).read_bytes()
    for private_value in (
        b"mickpletcher",
        b"private-owner/private-repository",
        b"env:AUDIT_TOKEN",
        b"sensitive evidence",
        b"missing private description",
    ):
        assert private_value not in database_content


def test_complete_run_resolves_but_partial_run_does_not(tmp_path: Path) -> None:
    config = history_config(tmp_path)
    timestamp = datetime(2026, 8, 11, 12, tzinfo=UTC)
    finding = sample_finding(timestamp)
    record_audit_history(config, report_at(timestamp, RunStatus.COMPLETE, (finding,)))

    partial = record_audit_history(
        config,
        report_at(timestamp + timedelta(minutes=1), RunStatus.PARTIAL, ()),
    )
    complete = record_audit_history(
        config,
        report_at(timestamp + timedelta(minutes=2), RunStatus.COMPLETE, ()),
    )

    assert partial.resolved == 0
    assert complete.resolved == 1


def test_complete_run_does_not_resolve_findings_outside_current_coverage(tmp_path: Path) -> None:
    config = history_config(tmp_path)
    timestamp = datetime(2026, 8, 11, 12, tzinfo=UTC)
    finding = sample_finding(timestamp)
    record_audit_history(config, report_at(timestamp, RunStatus.COMPLETE, (finding,)))
    narrowed_report = report_at(timestamp + timedelta(minutes=1), RunStatus.COMPLETE, ()).model_copy(
        update={
            "results": (),
            "coverage": (
                CoverageRecord(
                    repository_id=finding.repository_id,
                    check_id=finding.check_id,
                    state=CoverageState.NOT_REQUESTED,
                ),
            ),
        }
    )

    narrowed = record_audit_history(config, narrowed_report)
    resolved = record_audit_history(
        config,
        report_at(timestamp + timedelta(minutes=2), RunStatus.COMPLETE, ()),
    )

    assert narrowed.resolved == 0
    assert resolved.resolved == 1


def test_migrates_v1_transactionally_and_creates_backup(tmp_path: Path) -> None:
    config = history_config(tmp_path)
    database_path = history_database_path(config)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    create_v1_database(database_path)

    record_audit_history(
        config,
        report_at(datetime(2026, 8, 11, 12, tzinfo=UTC), RunStatus.COMPLETE, ()),
    )

    with sqlite3.connect(database_path) as connection:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        state_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(finding_state)")}
        event_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(finding_events)")}
    backups = list((database_path.parent / "migration-backups").glob("*.bak"))
    assert version == CURRENT_SCHEMA_VERSION
    assert "state_hash" in state_columns
    assert "state_hash" in event_columns
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as backup:
        assert int(backup.execute("PRAGMA user_version").fetchone()[0]) == 1


def test_failed_migration_rolls_back_and_preserves_backup(tmp_path: Path) -> None:
    config = history_config(tmp_path)
    database_path = history_database_path(config)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    create_v1_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("ALTER TABLE finding_state ADD COLUMN state_hash TEXT")

    with pytest.raises(HistoryError, match="OperationalError"):
        record_audit_history(
            config,
            report_at(datetime(2026, 8, 11, 12, tzinfo=UTC), RunStatus.COMPLETE, ()),
        )

    with sqlite3.connect(database_path) as connection:
        assert int(connection.execute("PRAGMA user_version").fetchone()[0]) == 1
        event_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(finding_events)")}
    assert "state_hash" not in event_columns
    assert len(list((database_path.parent / "migration-backups").glob("*.bak"))) == 1


def test_rejects_newer_schema_and_out_of_order_runs(tmp_path: Path) -> None:
    config = history_config(tmp_path)
    newer_path = history_database_path(config)
    newer_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(newer_path) as connection:
        connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 1}")

    with pytest.raises(HistoryError, match="newer"):
        read_audit_history(config)

    config = history_config(tmp_path / "chronological")
    latest = datetime(2026, 8, 11, 13, tzinfo=UTC)
    record_audit_history(config, report_at(latest, RunStatus.COMPLETE, ()))
    with pytest.raises(HistoryError, match="chronological"):
        record_audit_history(
            config,
            report_at(latest - timedelta(minutes=1), RunStatus.COMPLETE, ()),
        )


def test_rejects_non_utc_and_backwards_report_timestamps(tmp_path: Path) -> None:
    config = history_config(tmp_path)
    timestamp = datetime(2026, 8, 11, 12, tzinfo=UTC)
    valid_report = report_at(timestamp, RunStatus.COMPLETE, ())

    with pytest.raises(HistoryError, match="UTC"):
        record_audit_history(
            config,
            valid_report.model_copy(
                update={
                    "started_at": valid_report.started_at.replace(tzinfo=None),
                    "completed_at": valid_report.completed_at.replace(tzinfo=None),
                }
            ),
        )
    with pytest.raises(HistoryError, match="completed before"):
        record_audit_history(
            config,
            valid_report.model_copy(update={"completed_at": timestamp - timedelta(seconds=1)}),
        )


def test_rejects_duplicate_finding_identities(tmp_path: Path) -> None:
    config = history_config(tmp_path)
    timestamp = datetime(2026, 8, 11, 12, tzinfo=UTC)
    finding = sample_finding(timestamp)
    duplicate = finding.model_copy(update={"finding_id": "different-report-id"})

    with pytest.raises(HistoryError, match="duplicate finding identities"):
        record_audit_history(
            config,
            report_at(timestamp, RunStatus.COMPLETE, (finding, duplicate)),
        )


def test_reading_empty_history_does_not_create_database(tmp_path: Path) -> None:
    config = history_config(tmp_path)

    report = read_audit_history(config)

    assert report.total_run_count == 0
    assert not history_database_path(config).exists()
    with pytest.raises(ValueError, match="between 1 and 100"):
        read_audit_history(config, limit=0)


def test_rejects_state_directory_inside_git_worktree(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    config = history_config(tmp_path / "state")

    with pytest.raises(HistoryError, match="outside a Git worktree"):
        history_database_path(config)


def test_rejects_broken_symbolic_link_in_state_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    link = tmp_path / "broken-link"
    original_is_symlink = Path.is_symlink

    def fake_is_symlink(path: Path) -> bool:
        return path == link or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)
    config = history_config(link / "state")

    with pytest.raises(HistoryError, match="symbolic links"):
        history_database_path(config)


def test_history_isolates_same_login_on_different_github_hosts(tmp_path: Path) -> None:
    github_config = history_config(tmp_path)
    enterprise_config = github_config.model_copy(
        update={"account": github_config.account.model_copy(update={"github_host": "github.example.com"})}
    )
    timestamp = datetime(2026, 8, 11, 12, tzinfo=UTC)
    report = report_at(timestamp, RunStatus.COMPLETE, ())

    record_audit_history(github_config, report)
    record_audit_history(enterprise_config, report)

    assert read_audit_history(github_config).total_run_count == 1
    assert read_audit_history(enterprise_config).total_run_count == 1


def history_config(state_directory: Path) -> AppConfig:
    config = default_config("mickpletcher")
    local_data = config.local_data.model_copy(update={"state_directory": state_directory})
    return config.model_copy(update={"local_data": local_data})


def report_at(
    timestamp: datetime,
    status: RunStatus,
    findings: tuple[Finding, ...],
) -> AccountAuditReport:
    counts = {severity: 0 for severity in Severity}
    for finding in findings:
        counts[finding.severity] += 1
    outcome = CheckOutcome.NONCOMPLIANT if findings else CheckOutcome.COMPLIANT
    return AccountAuditReport(
        tool_version="0.1.0.dev0",
        github_api_version=GITHUB_API_VERSION,
        account_display="mickpletcher",
        discovery_credential_source="env:DISCOVERY_TOKEN",
        audit_credential_source="env:AUDIT_TOKEN",
        started_at=timestamp,
        completed_at=timestamp + timedelta(seconds=1),
        status=status,
        inventory_status=RunStatus.COMPLETE,
        repository_count=1,
        requested_repository_count=1,
        audited_repository_count=0,
        results=(
            CheckResult(
                repository_id=987654321,
                repository_display="nonpublic-repository:987654321",
                check_id="metadata.description",
                category="metadata",
                outcome=outcome,
                coverage_state=CoverageState.AUDITED,
                current_state={"present": not findings},
                desired_state={"requirement": "required"},
            ),
        ),
        findings=findings,
        finding_summary=FindingSummary(
            threshold=Severity.LOW,
            threshold_met=bool(findings),
            total=len(findings),
            informational=counts[Severity.INFORMATIONAL],
            low=counts[Severity.LOW],
            medium=counts[Severity.MEDIUM],
            high=counts[Severity.HIGH],
            critical=counts[Severity.CRITICAL],
        ),
    )


def sample_finding(timestamp: datetime) -> Finding:
    return Finding(
        finding_id="test-finding",
        check_id="metadata.description",
        repository_id=987654321,
        repository_display="private-owner/private-repository",
        category="metadata",
        severity=Severity.LOW,
        current_state={"description": "missing private description"},
        desired_state={"requirement": "required"},
        evidence=["sensitive evidence"],
        remediation_class=RemediationClass.APPROVAL_REQUIRED,
        documentation_url="https://private.example.invalid/documentation",
        observed_at=timestamp,
    )


def create_v1_database(path: Path) -> None:
    version, name, statements = MIGRATIONS[0]
    with sqlite3.connect(path) as connection:
        for statement in statements:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
            (version, name, datetime(2026, 8, 11, 12, tzinfo=UTC).isoformat()),
        )
        connection.execute(f"PRAGMA user_version = {version}")
