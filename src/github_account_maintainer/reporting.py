import json

from github_account_maintainer.models import AuthReport, InventoryReport, RunReport


def render_json(report: RunReport | AuthReport | InventoryReport) -> str:
    return report.model_dump_json(indent=2)


def render_markdown(report: RunReport) -> str:
    lines = [
        "# GitHub Account Maintainer Report",
        "",
        f"- Account: `{report.account_display}`",
        f"- Status: `{report.status.value}`",
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
