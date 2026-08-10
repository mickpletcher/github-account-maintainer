import argparse
import hashlib
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

import yaml
from pydantic import ValidationError

from github_account_maintainer import __version__
from github_account_maintainer.account_audit import AccountAuditReport, run_account_audit
from github_account_maintainer.auth import (
    AuthenticationPreflightError,
    ClientFactory,
    CredentialResolver,
    client_factory,
)
from github_account_maintainer.checks import ALL_CHECKS
from github_account_maintainer.config import AppConfig, StrictModel, default_config_path, load_config
from github_account_maintainer.constants import GITHUB_API_VERSION, REPORT_SCHEMA_VERSION
from github_account_maintainer.credentials import CredentialResolutionError, resolve_credential
from github_account_maintainer.github_api import GitHubApiError, GitHubTransportError
from github_account_maintainer.models import CoverageState, RunStatus
from github_account_maintainer.reporting import render_account_audit_markdown, render_json


class PilotConfigurationError(ValueError):
    pass


class PilotVerificationError(RuntimeError):
    pass


class ReleasePilotSummary(StrictModel):
    schema_version: Literal["1.0"] = REPORT_SCHEMA_VERSION
    tool_version: str
    github_api_version: str
    status: Literal["passed"] = "passed"
    repeated_runs: int
    repository_count: int
    requested_repository_count: int
    audited_repository_count: int
    policy_binding_count: int
    check_result_count: int
    coverage_record_count: int
    finding_count: int
    repeated_results_match: Literal[True] = True
    minimal_detail_enforced: Literal[True] = True
    request_mode: Literal["get_only"] = "get_only"
    automatic_write_operations: tuple[()] = ()


def run_release_pilot(
    config: AppConfig,
    *,
    repeats: int = 2,
    credential_resolver: CredentialResolver = resolve_credential,
    make_client: ClientFactory = client_factory,
    run_audit: Callable[..., AccountAuditReport] = run_account_audit,
) -> ReleasePilotSummary:
    _validate_pilot_config(config, repeats)
    reports = [
        run_audit(
            config,
            credential_resolver=credential_resolver,
            make_client=make_client,
        )
        for _run in range(repeats)
    ]
    for report in reports:
        _validate_report(report)

    fingerprints = {_report_fingerprint(report) for report in reports}
    if len(fingerprints) != 1:
        raise PilotVerificationError("Repeated read-only audits returned different semantic results")

    report = reports[-1]
    return ReleasePilotSummary(
        tool_version=__version__,
        github_api_version=GITHUB_API_VERSION,
        repeated_runs=repeats,
        repository_count=report.repository_count,
        requested_repository_count=report.requested_repository_count,
        audited_repository_count=report.audited_repository_count,
        policy_binding_count=len(report.bindings),
        check_result_count=len(report.results),
        coverage_record_count=len(report.coverage),
        finding_count=len(report.findings),
    )


def render_pilot_markdown(summary: ReleasePilotSummary) -> str:
    lines = [
        "# Release 0.1 Read-Only Pilot",
        "",
        f"- Status: `{summary.status}`",
        f"- Repeated runs: `{summary.repeated_runs}`",
        f"- Repositories discovered: `{summary.repository_count}`",
        f"- Repositories requested: `{summary.requested_repository_count}`",
        f"- Repositories audited: `{summary.audited_repository_count}`",
        f"- Policy bindings: `{summary.policy_binding_count}`",
        f"- Check results: `{summary.check_result_count}`",
        f"- Coverage records: `{summary.coverage_record_count}`",
        f"- Findings: `{summary.finding_count}`",
        f"- Repeated results match: `{str(summary.repeated_results_match).lower()}`",
        f"- Minimal detail enforced: `{str(summary.minimal_detail_enforced).lower()}`",
        f"- Request mode: `{summary.request_mode}`",
        f"- Automatic write operations: `{len(summary.automatic_write_operations)}`",
    ]
    return "\n".join(lines) + "\n"


def _validate_pilot_config(config: AppConfig, repeats: int) -> None:
    if not 2 <= repeats <= 5:
        raise PilotConfigurationError("Pilot repeats must be between 2 and 5")
    if config.local_data.report_detail != "minimal":
        raise PilotConfigurationError("Release 0.1 pilot requires minimal report detail")
    if config.github_api.request_mode != "serial":
        raise PilotConfigurationError("Release 0.1 pilot requires serial GitHub requests")
    if config.safety.automatic_write_operations:
        raise PilotConfigurationError("Release 0.1 pilot requires an empty automatic-write allowlist")
    if config.safety.automatic_merge != "prohibited" or config.safety.destructive_operations != "prohibited":
        raise PilotConfigurationError("Release 0.1 pilot requires prohibited merge and destructive operations")


def _validate_report(report: AccountAuditReport) -> None:
    if report.status is not RunStatus.COMPLETE:
        raise PilotVerificationError("Release 0.1 pilot audit returned partial coverage")
    if report.requested_repository_count == 0:
        raise PilotVerificationError("Release 0.1 pilot requires at least one in-scope repository")
    if report.audited_repository_count != report.requested_repository_count:
        raise PilotVerificationError("Release 0.1 pilot did not audit every in-scope repository")
    if len(report.results) != report.requested_repository_count * len(ALL_CHECKS):
        raise PilotVerificationError("Release 0.1 pilot did not return every repository check")
    requested_ids = {binding.repository_id for binding in report.bindings}
    classified_ids = {
        record.repository_id
        for record in report.coverage
        if record.check_id == "classification.repository" and record.state is CoverageState.AUDITED
    }
    if classified_ids != requested_ids:
        raise PilotVerificationError("Release 0.1 pilot classification coverage was incomplete")
    payload = json.loads(render_json(report))
    if payload.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise PilotVerificationError("Release 0.1 pilot JSON schema version was invalid")
    markdown = render_account_audit_markdown(report)
    if not all(section in markdown for section in ("## Policy bindings", "## Results", "## Findings", "## Coverage")):
        raise PilotVerificationError("Release 0.1 pilot Markdown report was incomplete")


def _report_fingerprint(report: AccountAuditReport) -> str:
    projection = {
        "repository_count": report.repository_count,
        "requested_repository_count": report.requested_repository_count,
        "audited_repository_count": report.audited_repository_count,
        "bindings": [
            {
                "repository_id": binding.repository_id,
                "classification_hash": binding.classification.classification_hash,
                "policy_hash": binding.policy_hash,
                "decisions": [decision.model_dump(mode="json") for decision in binding.classification.decisions],
            }
            for binding in report.bindings
        ],
        "results": [result.model_dump(mode="json") for result in report.results],
        "coverage": [record.model_dump(mode="json") for record in report.coverage],
        "findings": [
            finding.model_dump(mode="json", exclude={"finding_id", "observed_at"}) for finding in report.findings
        ],
        "finding_summary": report.finding_summary.model_dump(mode="json"),
    }
    canonical = json.dumps(projection, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a count-only Release 0.1 read-only pilot.")
    parser.add_argument("--config", type=Path, default=default_config_path(), help="Local configuration path.")
    parser.add_argument("--repeat", type=int, default=2, help="Number of repeated audits, from 2 through 5.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown", help="Summary format.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = load_config(args.config)
        summary = run_release_pilot(config, repeats=args.repeat)
    except (FileNotFoundError, OSError, ValidationError, yaml.YAMLError, PilotConfigurationError) as error:
        print(f"Invalid pilot configuration: {type(error).__name__}", file=sys.stderr)
        return 3
    except (
        CredentialResolutionError,
        AuthenticationPreflightError,
        GitHubApiError,
        GitHubTransportError,
    ) as error:
        print(f"Release 0.1 pilot failed: {type(error).__name__}", file=sys.stderr)
        return 2
    except PilotVerificationError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(summary.model_dump_json(indent=2) if args.format == "json" else render_pilot_markdown(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
