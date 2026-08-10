import json

from github_account_maintainer.models import RunReport


def render_json(report: RunReport) -> str:
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
