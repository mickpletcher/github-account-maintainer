# GitHub Account Maintainer

GitHub Account Maintainer is a policy-driven CLI for auditing accessible GitHub account resources. It is designed to be read-first, fail-closed, and explicit about API and credential coverage.

## Current status

Release 0.1 is under development. This scaffold provides:

- A Python 3.12 package managed with `uv`.
- A Typer CLI and strict Pydantic configuration schema.
- Strict coverage, finding, and report models.
- A REST client foundation pinned to GitHub API version `2026-03-10`.
- Serial, GET-only REST access with same-origin pagination and redirect validation.
- JSON and Markdown report rendering.
- Ruff, Pyright, pytest, coverage, and pinned GitHub Actions validation.

`auth check`, `inventory`, and `audit` are reserved commands and currently exit with code `2`. They do not call GitHub yet. Authentication and repository inventory are the next implementation slice.

## Safety boundaries

- No GitHub write operations are implemented.
- The automatic-write allowlist is empty.
- Destructive operations and automatic merging are prohibited by the configuration schema.
- Unknown configuration fields are rejected.
- Tokens, cookies, private keys, and secret values do not belong in configuration files.
- Default local data paths resolve outside managed repositories.

See the [project specification](prompts/github-account-maintainer-project-specification.md) for the complete scope and release gates.

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

## Development

```powershell
uv sync --locked --dev
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

The CI workflow runs the same checks on pull requests and pushes to `main`.

## Planned Release 0.1 work

1. Read-only credential resolution and authentication preflight.
2. Paginated repository inventory with declared coverage states.
3. Deterministic policy resolution and policy hashing.
4. Metadata and community-file checks.
5. Schema-versioned account reports.

No remediation work begins until the read-only Release 0.1 gate passes.
