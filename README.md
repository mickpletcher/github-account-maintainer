# GitHub Account Maintainer

GitHub Account Maintainer is a policy-driven CLI for auditing accessible GitHub account resources. It is designed to be read-first, fail-closed, and explicit about API and credential coverage.

## Current status

Release 0.1 is under development. This scaffold provides:

- A Python 3.12 package managed with `uv`.
- A Typer CLI and strict Pydantic configuration schema.
- Strict coverage, finding, and report models.
- A REST client foundation pinned to GitHub API version `2026-03-10`.
- Serial, GET-only REST access with same-origin pagination and redirect validation.
- Read-only credential resolution through Windows Credential Manager or an explicitly named environment variable.
- Authentication identity preflight through `GET /user`.
- Paginated repository inventory through `GET /user/repos` with deduplication and terminal coverage states.
- Minimal-detail redaction of non-public repository names and URLs.
- Deterministic policy resolution across built-in, account, repository-class, project-type, repository, and exception layers.
- Complete policy provenance traces plus canonical SHA-256 hashes for resolved effective policy.
- JSON and Markdown report rendering.
- Ruff, Pyright, pytest, coverage, and pinned GitHub Actions validation.

`audit` remains reserved and exits with code `2`. Authentication and inventory are read-only. No GitHub mutation endpoint is implemented.

## Safety boundaries

- No GitHub write operations are implemented.
- The automatic-write allowlist is empty.
- Destructive operations and automatic merging are prohibited by the configuration schema.
- Unknown configuration fields are rejected.
- Policy layers cannot override hard safety invariants.
- Expired or not-yet-active exceptions never suppress checks.
- Tokens, cookies, private keys, and secret values do not belong in configuration files.
- Default local data paths resolve outside managed repositories.

See the [project specification](prompts/github-account-maintainer-project-specification.md) for the complete scope and release gates.

See [assessment.md](assessment.md) for the current quick overview, implemented capabilities, safety assessment, limitations, verification status, and next priorities.

See [changelog.md](changelog.md) for the complete repository change history.

See [future-upgrades.md](future-upgrades.md) for the three-tier prioritized backlog and [completed-upgrades.md](completed-upgrades.md) for verified upgrades that have shipped.

## Install

Install `uv`, clone the repository, and run:

```powershell
uv sync --locked --dev
uv run github-account-maintainer --help
```

Create a local configuration in the platform-specific application data directory:

```powershell
uv run github-account-maintainer init --login YOUR_GITHUB_LOGIN
```

To select a different local path:

```powershell
uv run github-account-maintainer init --login YOUR_GITHUB_LOGIN --output C:\LocalData\GitHubAccountMaintainer\config.yaml
```

Existing configuration files are not overwritten unless `--overwrite` is supplied.

Store the discovery credential in Windows Credential Manager through Python keyring:

```powershell
uv run keyring set github-account-maintainer discovery
```

The default configuration references `keyring:github-account-maintainer/discovery`. It does not contain the token. For an ephemeral development session, change the reference to `env:GITHUB_TOKEN` and provide that environment variable outside the repository.

Verify the authenticated identity:

```powershell
uv run github-account-maintainer auth check
```

Inventory repositories within the configured affiliations:

```powershell
uv run github-account-maintainer inventory --format markdown
```

JSON is the default output format. Minimal report detail replaces private and internal repository names with stable numeric labels and omits their URLs.

## Policy resolution

The local configuration accepts strict policy layers under `policy`. Later layers override earlier layers in this order: account settings, repository class, project type, repository, then matching active exceptions. Built-in safe defaults always apply first.

```yaml
policy:
  repository_classes:
    application:
      security:
        audit_code_scanning: true
  project_types:
    python:
      readme:
        validate_links: true
  repositories:
    owner/repository:
      readme:
        preserve_manual_sections: true
  exceptions:
    - exception_id: EXC-001
      target_selector: owner/repository
      check_ids: [metadata.description]
      reason: Temporary migration window
      creator: github-login
      created_at: 2026-08-10T00:00:00Z
      expires_at: 2026-09-10T00:00:00Z
```

Policy and exception fields reject unknown values. Non-permanent exceptions require RFC 3339 UTC creation and expiration timestamps. Resolution records every applied value and source, sorts exception effects deterministically, and hashes the canonical effective policy with SHA-256. The reserved `audit` command does not consume this engine until the remaining Release 0.1 checks and report workflow are implemented.

## Development

```powershell
uv sync --locked --dev
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

The CI workflow runs the same checks on pull requests and pushes to `main`.

Every repository change must update `changelog.md` and review and update `assessment.md` in the same commit or pull request, even for the smallest documentation, configuration, dependency, workflow, or maintenance change. If behavior is unchanged, update the assessment review date and latest assessment change to confirm that the overview remains accurate.

When a tracked upgrade is implemented, move it from `future-upgrades.md` to `completed-upgrades.md`, preserve its stable ID and evidence, and add at least one new upgrade idea to any future priority tier in the same pull request.

## Planned Release 0.1 work

1. Metadata and community-file checks.
2. Schema-versioned account audit reports.
3. Read-only Release 0.1 pilot verification.

No remediation work begins until the read-only Release 0.1 gate passes.
