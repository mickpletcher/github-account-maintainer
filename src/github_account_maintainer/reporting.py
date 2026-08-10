import json

from github_account_maintainer.account_audit import AccountAuditReport
from github_account_maintainer.classification import RepositoryPolicyBindingRecord
from github_account_maintainer.models import AuthReport, InventoryReport, RepositoryAuditReport, RunReport


def render_json(
    report: RunReport
    | AuthReport
    | InventoryReport
    | RepositoryAuditReport
    | RepositoryPolicyBindingRecord
    | AccountAuditReport,
) -> str:
    return report.model_dump_json(indent=2)


def render_markdown(report: RunReport) -> str:
    lines = [
        "# GitHub Account Maintainer Report",
        "",
        f"- Account: `{report.account_display}`",
        f"- Status: `{report.status.value}`",
        f"- Policy hash: `{report.policy_hash}`",
        f"- GitHub API version: `{report.github_api_version}`",
        f"- Started: `{report.started_at.isoformat()}`",
        f"- Completed: `{report.completed_at.isoformat()}`",
        "",
        "## Coverage",
        "",
    ]
    if report.coverage:
        lines.extend(
            f"- `{record.check_id}`: `{record.state.value}`" + (f" ({record.detail})" if record.detail else "")
            for record in report.coverage
        )
    else:
        lines.append("No coverage records.")

    lines.extend(["", "## Findings", ""])
    if report.findings:
        lines.extend(
            f"- **{finding.severity.value}** `{finding.check_id}`: "
            f"{json.dumps(finding.current_state, ensure_ascii=False)}"
            for finding in report.findings
        )
    else:
        lines.append("No findings.")
    return "\n".join(lines) + "\n"


def render_auth_markdown(report: AuthReport) -> str:
    permissions = report.accepted_permissions or "not reported"
    scopes = ", ".join(report.oauth_scopes) or "not reported"
    lines = [
        "# GitHub Authentication Preflight",
        "",
        f"- Configured login: `{report.configured_login}`",
        f"- Authenticated login: `{report.authenticated_login}`",
        f"- Authenticated user ID: `{report.authenticated_user_id}`",
        f"- Credential source: `{report.credential_source}`",
        f"- GitHub API version: `{report.github_api_version}`",
        f"- OAuth scopes: `{scopes}`",
        f"- Accepted permissions: `{permissions}`",
        f"- Rate limit remaining: `{report.rate_limit_remaining}`",
        f"- Checked: `{report.checked_at.isoformat()}`",
    ]
    return "\n".join(lines) + "\n"


def render_inventory_markdown(report: InventoryReport) -> str:
    lines = [
        "# GitHub Repository Inventory",
        "",
        f"- Account: `{report.account_display}`",
        f"- Status: `{report.status.value}`",
        f"- Credential source: `{report.credential_source}`",
        f"- GitHub API version: `{report.github_api_version}`",
        f"- Declared affiliations: `{', '.join(report.declared_affiliations)}`",
        f"- Pages read: `{report.pages_read}`",
        f"- Repositories: `{len(report.repositories)}`",
        f"- Duplicates removed: `{report.duplicates_removed}`",
        "",
        "## Repositories",
        "",
    ]
    if report.repositories:
        for repository in report.repositories:
            flags = [repository.visibility]
            if repository.archived:
                flags.append("archived")
            if repository.fork:
                flags.append("fork")
            lines.append(f"- `{repository.display_name}` ({', '.join(flags)})")
    else:
        lines.append("No repositories were returned within declared coverage.")

    lines.extend(["", "## Coverage", ""])
    lines.extend(
        f"- `{record.check_id}`: `{record.state.value}`" + (f" ({record.detail})" if record.detail else "")
        for record in report.coverage
    )
    return "\n".join(lines) + "\n"


def render_repository_audit_markdown(report: RepositoryAuditReport) -> str:
    lines = [
        "# GitHub Repository Audit",
        "",
        f"- Repository: `{report.repository_display}`",
        f"- Status: `{report.status.value}`",
        f"- Policy hash: `{report.policy_hash}`",
        f"- GitHub API version: `{report.github_api_version}`",
        f"- Started: `{report.started_at.isoformat()}`",
        f"- Completed: `{report.completed_at.isoformat()}`",
        "",
        "## Results",
        "",
    ]
    if report.results:
        lines.extend(
            f"- `{result.check_id}`: `{result.outcome.value}` (`{result.coverage_state.value}`)"
            for result in report.results
        )
    else:
        lines.append("No check results.")

    lines.extend(["", "## Findings", ""])
    if report.findings:
        lines.extend(
            f"- **{finding.severity.value}** `{finding.check_id}`: "
            f"current={json.dumps(finding.current_state, ensure_ascii=False)}; "
            f"desired={json.dumps(finding.desired_state, ensure_ascii=False)}"
            for finding in report.findings
        )
    else:
        lines.append("No findings.")
    return "\n".join(lines) + "\n"


def render_policy_binding_markdown(record: RepositoryPolicyBindingRecord) -> str:
    lines = [
        "# GitHub Repository Classification and Policy Binding",
        "",
        f"- Repository: `{record.repository_display}`",
        f"- Repository class: `{record.repository_class}`",
        f"- Project type: `{record.project_type}`",
        f"- Classification hash: `{record.classification.classification_hash}`",
        f"- Coverage: `{record.classification.coverage_state.value}`",
        f"- Policy hash: `{record.policy_hash}`",
        f"- Bound: `{record.bound_at.isoformat()}`",
        "",
        "## Classification",
        "",
    ]
    lines.extend(
        f"- `{decision.dimension.value}`: `{decision.value}` (confidence `{decision.confidence:.2f}`)"
        for decision in record.classification.decisions
    )
    lines.extend(["", "## Policy sources", ""])
    lines.extend(f"- `{source.value}`" for source in record.policy_sources)
    return "\n".join(lines) + "\n"


def render_account_audit_markdown(report: AccountAuditReport) -> str:
    summary = report.finding_summary
    lines = [
        "# GitHub Account Audit",
        "",
        f"- Account: `{report.account_display}`",
        f"- Status: `{report.status.value}`",
        f"- Inventory status: `{report.inventory_status.value}`",
        f"- GitHub API version: `{report.github_api_version}`",
        f"- Repositories discovered: `{report.repository_count}`",
        f"- Repositories requested: `{report.requested_repository_count}`",
        f"- Repositories audited: `{report.audited_repository_count}`",
        f"- Finding threshold: `{summary.threshold.value}`",
        f"- Threshold met: `{str(summary.threshold_met).lower()}`",
        f"- Findings: `{summary.total}`",
        f"- Started: `{report.started_at.isoformat()}`",
        f"- Completed: `{report.completed_at.isoformat()}`",
        "",
        "## Findings by severity",
        "",
        f"- Critical: `{summary.critical}`",
        f"- High: `{summary.high}`",
        f"- Medium: `{summary.medium}`",
        f"- Low: `{summary.low}`",
        f"- Informational: `{summary.informational}`",
        "",
        "## Policy bindings",
        "",
    ]
    if report.bindings:
        lines.extend(
            f"- `{binding.repository_display}`: class=`{binding.repository_class}`; "
            f"project=`{binding.project_type}`; policy=`{binding.policy_hash}`"
            for binding in report.bindings
        )
    else:
        lines.append("No repository policy bindings were completed.")

    lines.extend(["", "## Results", ""])
    if report.results:
        lines.extend(
            f"- `{result.repository_display}` `{result.check_id}`: `{result.outcome.value}` "
            f"(`{result.coverage_state.value}`); current={json.dumps(result.current_state, ensure_ascii=False)}; "
            f"desired={json.dumps(result.desired_state, ensure_ascii=False)}"
            for result in report.results
        )
    else:
        lines.append("No check results.")

    lines.extend(["", "## Findings", ""])
    if report.findings:
        for finding in report.findings:
            lines.append(
                f"- **{finding.severity.value}** `{finding.repository_display}` `{finding.check_id}`: "
                f"current={json.dumps(finding.current_state, ensure_ascii=False)}; "
                f"desired={json.dumps(finding.desired_state, ensure_ascii=False)}; "
                f"evidence={json.dumps(finding.evidence, ensure_ascii=False)}; "
                f"remediation=`{finding.remediation_class.value}`; "
                f"documentation={finding.documentation_url or 'not provided'}"
            )
    else:
        lines.append("No findings reached reportable conditions.")

    lines.extend(["", "## Coverage", ""])
    lines.extend(
        f"- repository=`{record.repository_id if record.repository_id is not None else 'account'}` "
        f"`{record.check_id}`: `{record.state.value}`" + (f" ({record.detail})" if record.detail else "")
        for record in report.coverage
    )
    return "\n".join(lines) + "\n"
