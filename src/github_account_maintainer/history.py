import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final
from uuid import uuid4

from pydantic import Field

from github_account_maintainer.account_audit import AccountAuditReport
from github_account_maintainer.config import AppConfig, StrictModel
from github_account_maintainer.models import CheckOutcome, Finding, RunStatus

CURRENT_SCHEMA_VERSION: Final = 2
DATABASE_FILENAME: Final = "audit-history.sqlite3"
BACKUP_DIRECTORY_NAME: Final = "migration-backups"


class FindingTransition(StrEnum):
    NEW = "new"
    PERSISTENT = "persistent"
    RESOLVED = "resolved"
    REGRESSED = "regressed"


class HistoryError(RuntimeError):
    pass


class HistoryWriteResult(StrictModel):
    run_id: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    recorded: bool
    schema_version: Annotated[int, Field(ge=1)]
    new: Annotated[int, Field(ge=0)]
    persistent: Annotated[int, Field(ge=0)]
    resolved: Annotated[int, Field(ge=0)]
    regressed: Annotated[int, Field(ge=0)]


class HistoryRunSummary(StrictModel):
    run_id: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    started_at: datetime
    completed_at: datetime
    status: RunStatus
    repository_count: Annotated[int, Field(ge=0)]
    audited_repository_count: Annotated[int, Field(ge=0)]
    finding_count: Annotated[int, Field(ge=0)]
    new: Annotated[int, Field(ge=0)]
    persistent: Annotated[int, Field(ge=0)]
    resolved: Annotated[int, Field(ge=0)]
    regressed: Annotated[int, Field(ge=0)]


class AuditHistoryReport(StrictModel):
    schema_version: Annotated[int, Field(ge=0)]
    total_run_count: Annotated[int, Field(ge=0)]
    returned_run_count: Annotated[int, Field(ge=0)]
    runs: tuple[HistoryRunSummary, ...] = ()


MIGRATIONS: Final = (
    (
        1,
        "initial_audit_history",
        (
            """
            CREATE TABLE audit_runs (
                run_id TEXT PRIMARY KEY,
                account_key TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('complete', 'partial')),
                tool_version TEXT NOT NULL,
                report_schema_version TEXT NOT NULL,
                github_api_version TEXT NOT NULL,
                repository_count INTEGER NOT NULL CHECK (repository_count >= 0),
                requested_repository_count INTEGER NOT NULL CHECK (requested_repository_count >= 0),
                audited_repository_count INTEGER NOT NULL CHECK (audited_repository_count >= 0),
                finding_count INTEGER NOT NULL CHECK (finding_count >= 0),
                threshold TEXT NOT NULL,
                threshold_met INTEGER NOT NULL CHECK (threshold_met IN (0, 1)),
                new_count INTEGER NOT NULL CHECK (new_count >= 0),
                persistent_count INTEGER NOT NULL CHECK (persistent_count >= 0),
                resolved_count INTEGER NOT NULL CHECK (resolved_count >= 0),
                regressed_count INTEGER NOT NULL CHECK (regressed_count >= 0),
                recorded_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX audit_runs_account_completed ON audit_runs(account_key, completed_at DESC)",
            """
            CREATE TABLE finding_state (
                account_key TEXT NOT NULL,
                finding_key TEXT NOT NULL,
                repository_id INTEGER,
                check_id TEXT NOT NULL,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                remediation_class TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                resolved_at TEXT,
                active INTEGER NOT NULL CHECK (active IN (0, 1)),
                last_transition TEXT NOT NULL CHECK (
                    last_transition IN ('new', 'persistent', 'resolved', 'regressed')
                ),
                PRIMARY KEY (account_key, finding_key)
            )
            """,
            "CREATE INDEX finding_state_account_active ON finding_state(account_key, active)",
            """
            CREATE TABLE finding_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL REFERENCES audit_runs(run_id) ON DELETE RESTRICT,
                account_key TEXT NOT NULL,
                finding_key TEXT NOT NULL,
                repository_id INTEGER,
                check_id TEXT NOT NULL,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                remediation_class TEXT NOT NULL,
                transition TEXT NOT NULL CHECK (transition IN ('new', 'persistent', 'resolved', 'regressed')),
                event_at TEXT NOT NULL,
                UNIQUE (run_id, finding_key)
            )
            """,
            "CREATE INDEX finding_events_account_key ON finding_events(account_key, finding_key, event_at DESC)",
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """,
        ),
    ),
    (
        2,
        "sanitized_state_hash",
        (
            "ALTER TABLE finding_state ADD COLUMN state_hash TEXT",
            "ALTER TABLE finding_events ADD COLUMN state_hash TEXT",
        ),
    ),
)


def history_database_path(config: AppConfig) -> Path:
    configured_directory = config.local_data.state_directory.expanduser().absolute()
    if _contains_link_or_junction(configured_directory):
        raise HistoryError("Audit history state directory cannot use symbolic links or junctions")
    state_directory = configured_directory.resolve()
    if _inside_git_worktree(state_directory):
        raise HistoryError("Audit history state directory must be outside a Git worktree")
    if state_directory.exists() and (not state_directory.is_dir() or state_directory.is_symlink()):
        raise HistoryError("Audit history state directory is not a regular directory")
    return state_directory / DATABASE_FILENAME


def record_audit_history(config: AppConfig, report: AccountAuditReport) -> HistoryWriteResult:
    database_path = history_database_path(config)
    _validate_report_timestamps(report)
    if report.account_display.casefold() != config.account.login.casefold():
        raise HistoryError("Audit report account did not match the configured account")
    account_key = _account_key(config)
    findings = _normalized_findings(report.findings)
    run_id = _run_id(account_key, report, findings)

    try:
        connection = _open_database(database_path, create=True)
        try:
            return _record_run(connection, account_key, run_id, report, findings)
        finally:
            connection.close()
    except HistoryError:
        raise
    except (OSError, sqlite3.Error) as error:
        raise HistoryError(f"Audit history operation failed: {type(error).__name__}") from None


def read_audit_history(config: AppConfig, *, limit: int = 20) -> AuditHistoryReport:
    if not 1 <= limit <= 100:
        raise ValueError("history limit must be between 1 and 100")
    database_path = history_database_path(config)
    if not database_path.exists():
        return AuditHistoryReport(schema_version=0, total_run_count=0, returned_run_count=0)
    if database_path.is_symlink() or not database_path.is_file():
        raise HistoryError("Audit history database is not a regular file")

    account_key = _account_key(config)
    try:
        connection = _open_database(database_path, create=False)
        try:
            total = int(
                connection.execute(
                    "SELECT COUNT(*) FROM audit_runs WHERE account_key = ?",
                    (account_key,),
                ).fetchone()[0]
            )
            rows = connection.execute(
                """
                SELECT run_id, started_at, completed_at, status, repository_count,
                       audited_repository_count, finding_count, new_count, persistent_count,
                       resolved_count, regressed_count
                FROM audit_runs
                WHERE account_key = ?
                ORDER BY completed_at DESC, run_id DESC
                LIMIT ?
                """,
                (account_key, limit),
            ).fetchall()
            runs = tuple(_history_run(row) for row in rows)
            return AuditHistoryReport(
                schema_version=CURRENT_SCHEMA_VERSION,
                total_run_count=total,
                returned_run_count=len(runs),
                runs=runs,
            )
        finally:
            connection.close()
    except HistoryError:
        raise
    except (OSError, sqlite3.Error) as error:
        raise HistoryError(f"Audit history operation failed: {type(error).__name__}") from None


def _open_database(path: Path, *, create: bool) -> sqlite3.Connection:
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise HistoryError("Audit history database is not a regular file")
    if not path.exists() and not create:
        raise HistoryError("Audit history database does not exist")
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)

    preexisting_size = path.stat().st_size if path.exists() else 0
    connection = sqlite3.connect(path, isolation_level=None, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        integrity = connection.execute("PRAGMA quick_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise HistoryError("Audit history database integrity check failed")
        current_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if current_version > CURRENT_SCHEMA_VERSION:
            raise HistoryError("Audit history schema is newer than this application")
        if current_version < CURRENT_SCHEMA_VERSION:
            if preexisting_size > 0:
                _backup_database(connection, path, current_version)
            _apply_migrations(connection, current_version)
        return connection
    except Exception:
        connection.close()
        raise


def _backup_database(connection: sqlite3.Connection, path: Path, current_version: int) -> None:
    backup_directory = path.parent / BACKUP_DIRECTORY_NAME
    if backup_directory.exists() and (
        not backup_directory.is_dir() or backup_directory.is_symlink() or backup_directory.is_junction()
    ):
        raise HistoryError("Audit history migration backup directory is not a regular directory")
    backup_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = backup_directory / (f"{path.name}.v{current_version}-to-v{CURRENT_SCHEMA_VERSION}.{timestamp}.bak")
    temp_path = backup_directory / f".{backup_path.name}.{uuid4().hex}.tmp"
    backup_connection: sqlite3.Connection | None = None
    try:
        backup_connection = sqlite3.connect(temp_path)
        connection.backup(backup_connection)
        backup_connection.close()
        backup_connection = None
        os.replace(temp_path, backup_path)
    finally:
        if backup_connection is not None:
            backup_connection.close()
        temp_path.unlink(missing_ok=True)


def _apply_migrations(connection: sqlite3.Connection, current_version: int) -> None:
    for version, name, statements in MIGRATIONS:
        if version <= current_version:
            continue
        try:
            connection.execute("BEGIN IMMEDIATE")
            for statement in statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, _utc_now()),
            )
            connection.execute(f"PRAGMA user_version = {version}")
            connection.execute("COMMIT")
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise


def _record_run(
    connection: sqlite3.Connection,
    account_key: str,
    run_id: str,
    report: AccountAuditReport,
    findings: dict[str, Finding],
) -> HistoryWriteResult:
    completed_at = report.completed_at.isoformat()
    recorded_at = _utc_now()
    counts = {transition: 0 for transition in FindingTransition}
    conclusively_evaluated = {
        (result.repository_id, result.check_id)
        for result in report.results
        if result.outcome in {CheckOutcome.COMPLIANT, CheckOutcome.OBSERVED}
    }

    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = _existing_result(connection, run_id)
        if existing is not None:
            connection.execute("COMMIT")
            return existing
        latest = connection.execute(
            "SELECT completed_at FROM audit_runs WHERE account_key = ? ORDER BY completed_at DESC LIMIT 1",
            (account_key,),
        ).fetchone()
        if latest is not None and completed_at <= str(latest["completed_at"]):
            raise HistoryError("Audit history only accepts runs in chronological order")
        previous_rows = connection.execute(
            "SELECT * FROM finding_state WHERE account_key = ?",
            (account_key,),
        ).fetchall()
        previous = {str(row["finding_key"]): row for row in previous_rows}
        connection.execute(
            """
            INSERT INTO audit_runs(
                run_id, account_key, started_at, completed_at, status, tool_version,
                report_schema_version, github_api_version, repository_count,
                requested_repository_count, audited_repository_count, finding_count,
                threshold, threshold_met, new_count, persistent_count, resolved_count,
                regressed_count, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?)
            """,
            (
                run_id,
                account_key,
                report.started_at.isoformat(),
                completed_at,
                report.status.value,
                report.tool_version,
                report.schema_version,
                report.github_api_version,
                report.repository_count,
                report.requested_repository_count,
                report.audited_repository_count,
                report.finding_summary.total,
                report.finding_summary.threshold.value,
                int(report.finding_summary.threshold_met),
                recorded_at,
            ),
        )

        for finding_key, finding in findings.items():
            prior = previous.get(finding_key)
            if prior is None:
                transition = FindingTransition.NEW
                first_seen_at = completed_at
            elif int(prior["active"]) == 1:
                transition = FindingTransition.PERSISTENT
                first_seen_at = str(prior["first_seen_at"])
            else:
                transition = FindingTransition.REGRESSED
                first_seen_at = str(prior["first_seen_at"])
            counts[transition] += 1
            state_hash = _finding_state_hash(finding)
            _insert_event(connection, run_id, account_key, finding_key, finding, transition, completed_at, state_hash)
            connection.execute(
                """
                INSERT INTO finding_state(
                    account_key, finding_key, repository_id, check_id, category, severity,
                    remediation_class, first_seen_at, last_seen_at, resolved_at, active,
                    last_transition, state_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 1, ?, ?)
                ON CONFLICT(account_key, finding_key) DO UPDATE SET
                    repository_id = excluded.repository_id,
                    check_id = excluded.check_id,
                    category = excluded.category,
                    severity = excluded.severity,
                    remediation_class = excluded.remediation_class,
                    last_seen_at = excluded.last_seen_at,
                    resolved_at = NULL,
                    active = 1,
                    last_transition = excluded.last_transition,
                    state_hash = excluded.state_hash
                """,
                (
                    account_key,
                    finding_key,
                    finding.repository_id,
                    finding.check_id,
                    finding.category,
                    finding.severity.value,
                    finding.remediation_class.value,
                    first_seen_at,
                    completed_at,
                    transition.value,
                    state_hash,
                ),
            )

        if report.status is RunStatus.COMPLETE:
            for finding_key, prior in previous.items():
                if finding_key in findings or int(prior["active"]) == 0:
                    continue
                if (prior["repository_id"], prior["check_id"]) not in conclusively_evaluated:
                    continue
                transition = FindingTransition.RESOLVED
                counts[transition] += 1
                _insert_resolved_event(connection, run_id, account_key, prior, completed_at)
                connection.execute(
                    """
                    UPDATE finding_state
                    SET active = 0, resolved_at = ?, last_transition = ?
                    WHERE account_key = ? AND finding_key = ?
                    """,
                    (completed_at, transition.value, account_key, finding_key),
                )

        connection.execute(
            """
            UPDATE audit_runs
            SET new_count = ?, persistent_count = ?, resolved_count = ?, regressed_count = ?
            WHERE run_id = ?
            """,
            (
                counts[FindingTransition.NEW],
                counts[FindingTransition.PERSISTENT],
                counts[FindingTransition.RESOLVED],
                counts[FindingTransition.REGRESSED],
                run_id,
            ),
        )
        connection.execute("COMMIT")
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise

    return HistoryWriteResult(
        run_id=run_id,
        recorded=True,
        schema_version=CURRENT_SCHEMA_VERSION,
        new=counts[FindingTransition.NEW],
        persistent=counts[FindingTransition.PERSISTENT],
        resolved=counts[FindingTransition.RESOLVED],
        regressed=counts[FindingTransition.REGRESSED],
    )


def _insert_event(
    connection: sqlite3.Connection,
    run_id: str,
    account_key: str,
    finding_key: str,
    finding: Finding,
    transition: FindingTransition,
    event_at: str,
    state_hash: str,
) -> None:
    connection.execute(
        """
        INSERT INTO finding_events(
            run_id, account_key, finding_key, repository_id, check_id, category,
            severity, remediation_class, transition, event_at, state_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            account_key,
            finding_key,
            finding.repository_id,
            finding.check_id,
            finding.category,
            finding.severity.value,
            finding.remediation_class.value,
            transition.value,
            event_at,
            state_hash,
        ),
    )


def _insert_resolved_event(
    connection: sqlite3.Connection,
    run_id: str,
    account_key: str,
    prior: sqlite3.Row,
    event_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO finding_events(
            run_id, account_key, finding_key, repository_id, check_id, category,
            severity, remediation_class, transition, event_at, state_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            account_key,
            prior["finding_key"],
            prior["repository_id"],
            prior["check_id"],
            prior["category"],
            prior["severity"],
            prior["remediation_class"],
            FindingTransition.RESOLVED.value,
            event_at,
            prior["state_hash"],
        ),
    )


def _existing_result(connection: sqlite3.Connection, run_id: str) -> HistoryWriteResult | None:
    row = connection.execute(
        """
        SELECT new_count, persistent_count, resolved_count, regressed_count
        FROM audit_runs WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    return HistoryWriteResult(
        run_id=run_id,
        recorded=False,
        schema_version=CURRENT_SCHEMA_VERSION,
        new=int(row["new_count"]),
        persistent=int(row["persistent_count"]),
        resolved=int(row["resolved_count"]),
        regressed=int(row["regressed_count"]),
    )


def _normalized_findings(findings: tuple[Finding, ...]) -> dict[str, Finding]:
    normalized: dict[str, Finding] = {}
    for finding in findings:
        key = _finding_key(finding)
        if key in normalized:
            raise HistoryError("Audit report contained duplicate finding identities")
        normalized[key] = finding
    return normalized


def _finding_key(finding: Finding) -> str:
    return _digest(
        _canonical_json(
            {
                "repository_id": finding.repository_id,
                "check_id": finding.check_id,
                "category": finding.category,
            }
        )
    )


def _finding_state_hash(finding: Finding) -> str:
    return _digest(
        _canonical_json(
            {
                "severity": finding.severity.value,
                "current_state": finding.current_state,
                "desired_state": finding.desired_state,
                "remediation_class": finding.remediation_class.value,
            }
        )
    )


def _account_key(config: AppConfig) -> str:
    return _digest(
        _canonical_json(
            {
                "github_host": config.account.github_host.casefold(),
                "login": config.account.login.casefold(),
            }
        )
    )


def _run_id(account_key: str, report: AccountAuditReport, findings: dict[str, Finding]) -> str:
    return _digest(
        _canonical_json(
            {
                "account_key": account_key,
                "started_at": report.started_at.isoformat(),
                "completed_at": report.completed_at.isoformat(),
                "tool_version": report.tool_version,
                "report_schema_version": report.schema_version,
                "status": report.status.value,
                "repository_count": report.repository_count,
                "requested_repository_count": report.requested_repository_count,
                "audited_repository_count": report.audited_repository_count,
                "finding_threshold": report.finding_summary.threshold.value,
                "threshold_met": report.finding_summary.threshold_met,
                "findings": [
                    {"finding_key": finding_key, "state_hash": _finding_state_hash(finding)}
                    for finding_key, finding in sorted(findings.items())
                ],
            }
        )
    )


def _history_run(row: sqlite3.Row) -> HistoryRunSummary:
    return HistoryRunSummary(
        run_id=str(row["run_id"]),
        started_at=datetime.fromisoformat(str(row["started_at"])),
        completed_at=datetime.fromisoformat(str(row["completed_at"])),
        status=RunStatus(str(row["status"])),
        repository_count=int(row["repository_count"]),
        audited_repository_count=int(row["audited_repository_count"]),
        finding_count=int(row["finding_count"]),
        new=int(row["new_count"]),
        persistent=int(row["persistent_count"]),
        resolved=int(row["resolved_count"]),
        regressed=int(row["regressed_count"]),
    )


def _validate_report_timestamps(report: AccountAuditReport) -> None:
    if report.started_at.utcoffset() != timedelta(0) or report.completed_at.utcoffset() != timedelta(0):
        raise HistoryError("Audit history requires UTC report timestamps")
    if report.completed_at < report.started_at:
        raise HistoryError("Audit report completed before it started")


def _inside_git_worktree(path: Path) -> bool:
    return any((candidate / ".git").exists() for candidate in (path, *path.parents))


def _contains_link_or_junction(path: Path) -> bool:
    return any(candidate.is_symlink() or candidate.is_junction() for candidate in (path, *path.parents))


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
