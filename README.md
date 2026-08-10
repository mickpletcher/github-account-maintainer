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
- JSON and Markdown report rendering.
- Ruff, Pyright, pytest, coverage, and pinned GitHub Actions validation.

`audit` remains reserved and exits with code `2`. Authentication and inventory are read-only. No GitHub mutation endpoint is implemented.

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

1. Deterministic policy resolution and policy hashing.
2. Metadata and community-file checks.
3. Schema-versioned account audit reports.

No remediation work begins until the read-only Release 0.1 gate passes.
