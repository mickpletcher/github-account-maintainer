# GitHub Account Maintainer

GitHub Account Maintainer is a local command-line tool for inspecting the GitHub repositories your account can access. It is being built to compare those repositories with an explicit policy and report what is correct, missing, unsupported, or inaccessible.

The current version is deliberately read-only. It can verify a GitHub identity, inventory repositories, redact private repository identities, and resolve layered policy. It cannot change GitHub.

## Contents

- [Current status](#current-status)
- [What the tool does](#what-the-tool-does)
- [What the tool does not do](#what-the-tool-does-not-do)
- [Safety and privacy](#safety-and-privacy)
- [Prerequisites](#prerequisites)
- [Quick start for Windows](#quick-start-for-windows)
- [Create a GitHub token](#create-a-github-token)
- [Store the token securely](#store-the-token-securely)
- [Create the configuration](#create-the-configuration)
- [Verify authentication](#verify-authentication)
- [Inventory repositories](#inventory-repositories)
- [Command reference](#command-reference)
- [Configuration guide](#configuration-guide)
- [Policy resolution](#policy-resolution)
- [Reports and exit codes](#reports-and-exit-codes)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Project documents](#project-documents)
- [Release roadmap](#release-roadmap)

## Current status

The package version is `0.1.0.dev0`. Release 0.1 is still under development.

| Capability | Status | Notes |
| --- | --- | --- |
| Create local configuration | Implemented | Uses strict validation and refuses accidental overwrite. |
| Verify authenticated identity | Implemented | Calls the read-only `GET /user` endpoint. |
| Inventory accessible repositories | Implemented | Calls paginated `GET /user/repos` requests. |
| Redact private repository identities | Implemented | Enabled by the default `minimal` report detail. |
| Resolve layered policy | Implemented foundation | Deterministic library code exists, but the reserved `audit` command does not use it yet. |
| Audit metadata and community files | Not implemented | Planned next. |
| Apply GitHub changes | Not implemented | No GitHub mutation endpoint exists. |
| Full Release 0.1 audit | Not implemented | The `audit` command exits with code `2`. |

This status matters. A successful inventory does not mean the account passed a full security or compliance audit.

## What the tool does

The current CLI can:

- Create a local YAML configuration with safe defaults.
- Load credentials from Windows Credential Manager through Python `keyring`.
- Load a credential from an explicitly named environment variable when requested.
- Confirm that the token belongs to the configured GitHub login.
- Inventory repositories visible within the configured affiliation and visibility scope.
- Follow GitHub pagination until no next page remains.
- Deduplicate repositories by GitHub repository ID.
- Record repository visibility, archive state, fork state, and effective permissions.
- Mark successful, partial, and failed coverage explicitly.
- Redact private and internal repository names and URLs by default.
- Produce JSON or Markdown output.
- Resolve policy in a deterministic order.
- Record where every resolved policy value came from.
- Create a canonical SHA-256 hash for the effective policy.
- Validate active, expired, pending, and permanent policy exceptions.

## What the tool does not do

The current version does not:

- Change repository settings.
- Create, edit, close, approve, or merge pull requests.
- Create or delete repositories, branches, tags, releases, issues, or files.
- Enable or disable GitHub security features.
- Dismiss security alerts.
- Clone repository content during inventory.
- Run the planned metadata and community-file audit.
- Apply the resolved policy to an account audit.
- Schedule unattended runs.
- Create backups.
- Use browser automation.

The configuration contains sections for planned features. The presence of a setting does not mean that feature is active.

## Safety and privacy

The project uses these boundaries:

- The GitHub API client exposes only GET operations.
- Requests are serial rather than concurrent.
- The API version is pinned to `2026-03-10`.
- Pagination and redirects must remain on the configured GitHub API origin.
- The automatic-write allowlist is empty.
- Automatic merge and destructive operations are prohibited by the schema.
- Policy layers cannot override hard safety invariants.
- Expired, pending, unmatched, or invalid exceptions cannot suppress checks.
- Unknown configuration and policy fields are rejected.
- Tokens are resolved at runtime and are not placed in reports.
- Backend credential errors are reduced to safe error classes.
- Private and internal repository names and URLs are redacted in `minimal` detail mode.
- Default configuration, state, cache, report, log, browser, and backup-metadata paths are outside the cloned repository.

Treat a personal access token like a password. Never paste it into `config.yaml`, a command history entry, an issue, a pull request, a report, or a committed file.

## Prerequisites

For the Windows instructions below, you need:

1. Windows 11 with PowerShell.
2. A GitHub account.
3. Git installed and available as `git`.
4. Internet access to GitHub and Python package sources.
5. `uv`, which manages Python 3.12 and the project dependencies.

You do not need to create a Python virtual environment manually. `uv sync` creates and manages `.venv` for this repository.

### Install Git

If this command prints a version, Git is already installed:

```powershell
git --version
```

If it is missing, install [Git for Windows](https://git-scm.com/download/win), reopen PowerShell, and run the version command again.

### Install uv

The simplest Windows package-manager installation is:

```powershell
winget install --id astral-sh.uv -e
```

Close and reopen PowerShell, then verify the installation:

```powershell
uv --version
```

The [official uv installation guide](https://docs.astral.sh/uv/getting-started/installation/) lists the standalone PowerShell installer and other supported methods.

## Quick start for Windows

These commands clone the repository, install the locked dependencies, and show the CLI help.

```powershell
git clone https://github.com/mickpletcher/github-account-maintainer.git
Set-Location .\github-account-maintainer
uv sync --locked --dev
uv run github-account-maintainer --version
uv run github-account-maintainer --help
```

What each command does:

- `git clone` downloads the source repository.
- `Set-Location` enters the repository folder.
- `uv sync --locked --dev` creates `.venv` and installs the exact locked application and development dependencies.
- `uv run` executes a command inside the managed project environment.

Expected version output:

```text
0.1.0.dev0
```

If `uv sync --locked --dev` would require a lockfile change, it stops instead. This protects reproducibility.

## Create a GitHub token

The implemented commands use a discovery credential. Use a fine-grained personal access token with the smallest practical access.

GitHub's current token steps are documented in [Managing your personal access tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).

1. Sign in to GitHub.
2. Open your profile menu and select **Settings**.
3. Open **Developer settings**.
4. Open **Personal access tokens**, then **Fine-grained tokens**.
5. Select **Generate new token**.
6. Give the token a clear name such as `github-account-maintainer-discovery`.
7. Set an expiration date.
8. Select the personal account or organization that owns the repositories you want to inventory.
9. Select all repositories or only the repositories that should be visible to this tool.
10. Grant repository **Metadata** permission with read access.
11. Do not grant write permissions for the current release.
12. Generate the token and copy it once.

The implemented `GET /user` call does not require an additional fine-grained permission. The implemented `GET /user/repos` inventory call requires repository **Metadata: read** access. See GitHub's official endpoint documentation for [the authenticated user](https://docs.github.com/en/rest/users/users#get-the-authenticated-user) and [repository inventory](https://docs.github.com/en/rest/repos/repos#list-repositories-for-the-authenticated-user).

Important token limitations:

- A fine-grained token is limited to its selected resource owner and repository access.
- An organization may require an administrator to approve the token.
- A pending or unapproved organization token may not return the expected repositories.
- A token cannot grant access that your GitHub account does not already have.
- Use a short practical expiration and rotate the token when it expires.

## Store the token securely

The default configuration expects this credential reference:

```text
keyring:github-account-maintainer/discovery
```

The part before the slash is the keyring service. The part after the slash is the keyring account.

From the repository directory, run:

```powershell
uv run keyring set github-account-maintainer discovery
```

The command prompts for a password. Paste the GitHub token at that prompt. The token is stored by the active system keyring backend, which is normally Windows Credential Manager on Windows. It is not written to the project configuration.

You can inspect keyring diagnostics without printing the token:

```powershell
uv run keyring diagnose
```

Do not use `keyring get` in a shared terminal, recording, or log. That command can print the stored secret.

### Temporary environment-variable option

For an isolated development session, you can use an environment variable instead of keyring.

First change the configuration reference:

```yaml
credentials:
  discovery: env:GITHUB_TOKEN
```

Then set the variable only in the current PowerShell process. The masked prompt requires PowerShell 7.1 or later:

```powershell
$env:GITHUB_TOKEN = Read-Host "GitHub token" -MaskInput
```

On older Windows PowerShell versions, use the recommended keyring method so the token is not displayed while you type it. Microsoft documents `-MaskInput` in the [Read-Host reference](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/read-host).

Run the command in the same PowerShell window. Remove the variable when finished:

```powershell
Remove-Item Env:GITHUB_TOKEN
```

Do not place the token in a `.ps1` file, profile, repository `.env` file, or committed configuration.

## Create the configuration

Replace `YOUR_GITHUB_LOGIN` with the login shown in your GitHub profile URL.

```powershell
uv run github-account-maintainer init --login YOUR_GITHUB_LOGIN
```

On Windows, the default file is normally:

```text
%LOCALAPPDATA%\GitHubAccountMaintainer\config\config.yaml
```

To display the expected path in PowerShell:

```powershell
Join-Path $env:LOCALAPPDATA "GitHubAccountMaintainer\config\config.yaml"
```

To create the file somewhere else:

```powershell
uv run github-account-maintainer init `
  --login YOUR_GITHUB_LOGIN `
  --output C:\LocalData\GitHubAccountMaintainer\config.yaml
```

The command creates parent directories when required. It does not overwrite an existing file unless `--overwrite` is explicitly supplied.

```powershell
uv run github-account-maintainer init `
  --login YOUR_GITHUB_LOGIN `
  --output C:\LocalData\GitHubAccountMaintainer\config.yaml `
  --overwrite
```

Use `--overwrite` carefully. It atomically replaces the selected configuration.

## Verify authentication

Run the identity preflight before inventory:

```powershell
uv run github-account-maintainer auth check
```

For readable Markdown output:

```powershell
uv run github-account-maintainer auth check --format markdown
```

For a nondefault configuration path:

```powershell
uv run github-account-maintainer auth check `
  --config C:\LocalData\GitHubAccountMaintainer\config.yaml `
  --format markdown
```

A successful report includes:

- The configured GitHub login.
- The login returned by GitHub.
- The authenticated numeric user ID.
- The credential source reference, not the credential value.
- OAuth scopes when GitHub reports them.
- Accepted permissions when GitHub reports them.
- Remaining rate-limit information when available.
- The check timestamp.

The command fails if the authenticated login does not match `account.login`. This prevents accidentally auditing with the wrong account's token.

## Inventory repositories

After authentication succeeds, run:

```powershell
uv run github-account-maintainer inventory --format markdown
```

JSON is the default:

```powershell
uv run github-account-maintainer inventory
```

To save a local JSON report:

```powershell
uv run github-account-maintainer inventory --format json |
  Set-Content -Path .\inventory.json -Encoding utf8
```

Treat saved reports as local data. Do not commit them unless you have reviewed their contents and intentionally accepted the disclosure risk.

The inventory report contains:

- Tool and report schema versions.
- The configured account display.
- The credential source reference.
- Declared affiliations.
- Start and completion timestamps.
- Complete or partial status.
- Pages read.
- Duplicate count.
- Accepted GitHub permissions when reported.
- Repository records.
- Terminal coverage records.

In the default `minimal` mode, a private repository may appear as:

```text
nonpublic-repository:123456789
```

Its URL is omitted. Public repository names and URLs are not redacted.

## Command reference

### Global command

```powershell
uv run github-account-maintainer [OPTIONS] COMMAND
```

| Option | Purpose |
| --- | --- |
| `--version` | Print the package version. |
| `--help` | Show the top-level help. |
| `--install-completion` | Install shell completion for the current shell. |
| `--show-completion` | Print shell-completion instructions. |

### `init`

```powershell
uv run github-account-maintainer init --login LOGIN [--output PATH] [--overwrite]
```

| Option | Required | Purpose |
| --- | --- | --- |
| `--login` | Yes | GitHub login placed in the configuration. |
| `--output` | No | Explicit configuration path. The platform default is used when omitted. |
| `--overwrite` | No | Atomically replace an existing configuration. |

### `auth check`

```powershell
uv run github-account-maintainer auth check [--config PATH] [--format json|markdown]
```

This command resolves the discovery credential, calls `GET /user`, and verifies the returned identity.

### `inventory`

```powershell
uv run github-account-maintainer inventory [--config PATH] [--format json|markdown]
```

This command verifies identity and then reads every page returned by `GET /user/repos` within the declared affiliation and visibility scope.

### `audit`

```powershell
uv run github-account-maintainer audit
```

This command is reserved. It prints an incomplete-implementation message and exits with code `2`. It does not run a partial audit and it does not change GitHub.

## Configuration guide

The configuration is strict YAML. Indentation matters. Unknown fields, invalid values, and unsafe combinations are rejected with exit code `3`.

### Sections at a glance

| Section | Current use |
| --- | --- |
| `account` | Controls identity, GitHub host, visibility, and repository affiliations used by authentication and inventory. |
| `github_api` | Pins the API version and serial request mode. |
| `credentials` | Stores credential references. It must never contain literal secrets. |
| `local_data` | Defines local directories, report detail, and retention values. |
| `safety` | Enforces non-overridable write and approval boundaries. |
| `repositories` | Supplies account-wide repository policy defaults. Include and exclude patterns are not yet applied by inventory. |
| `pins` | Validated policy for the planned profile-pin feature. Not active yet. |
| `readme` | Validated policy for planned README checks and remediation. Not active yet. |
| `social_preview` | Validated policy for planned social-preview work. Not active yet. |
| `security` | Validated desired security audit policy. The security audit is not active yet. |
| `backup` | Reserved and forced disabled in the current schema. |
| `notifications` | Validated notification policy. Notifications are not active yet. |
| `policy` | Stores repository-class, project-type, repository-specific, and exception overrides. |

### Account scope

The default account block is:

```yaml
account:
  login: YOUR_GITHUB_LOGIN
  github_host: github.com
  include_private: true
  include_owned: true
  include_administered: false
  affiliations:
    - owner
```

Rules:

- `login` must match the token's authenticated GitHub login, ignoring case.
- `github_host` is a hostname only. Do not include `https://` or a path.
- `include_private: false` requests only public repositories.
- `include_owned` must agree with whether `owner` appears in `affiliations`.
- `include_administered` must be true when `collaborator` or `organization_member` is selected.
- Valid affiliations are `owner`, `collaborator`, and `organization_member`.

Example that includes repositories administered through collaboration or organization membership:

```yaml
account:
  login: YOUR_GITHUB_LOGIN
  github_host: github.com
  include_private: true
  include_owned: true
  include_administered: true
  affiliations:
    - owner
    - collaborator
    - organization_member
```

The token must still be allowed to access those repositories. Configuration does not grant GitHub permissions.

### Credential references

Supported forms are:

```text
keyring:SERVICE/ACCOUNT
env:VARIABLE_NAME
```

Examples:

```yaml
credentials:
  discovery: keyring:github-account-maintainer/discovery
  audit: keyring:github-account-maintainer/audit
  remediation: disabled
  classic_token: disabled
  browser_profile: disabled
```

The current `auth check` and `inventory` commands use only `credentials.discovery`.

### Report privacy

```yaml
local_data:
  report_detail: minimal
```

Valid values are:

- `minimal`: Redacts private and internal repository names and removes their URLs.
- `full`: Includes private and internal repository names and URLs.

Use `full` only for private local reports with controlled storage. It increases disclosure risk.

## Policy resolution

The engine resolves policy in this order. A later matching layer overrides an earlier layer.

1. Built-in safe defaults.
2. Account-wide settings from the top-level configuration sections.
3. A matching repository-class policy.
4. A matching language or project-type policy.
5. A matching repository-specific policy.
6. Matching active exceptions.

Hard safety invariants are outside this hierarchy. A policy patch cannot enable automatic merging, destructive operations, write operations, secret collection, or the other prohibited behaviors.

Example:

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
      check_ids:
        - metadata.description
      reason: Temporary migration window
      creator: github-login
      created_at: 2026-08-10T00:00:00Z
      expires_at: 2026-09-10T00:00:00Z
```

Exception requirements:

- `exception_id` is stable and unique, ignoring case.
- `target_selector` identifies matching repositories and may use shell-style wildcard matching.
- `check_ids` is a nonempty list of stable lowercase identifiers.
- `reason` and `creator` cannot be empty.
- Timestamps must use RFC 3339 UTC.
- A non-permanent exception requires `expires_at` after `created_at`.
- A permanent exception sets `permanent: true` and must not have `expires_at`.
- A pending exception does not apply before `created_at`.
- An expired exception no longer suppresses checks.

Resolution produces:

- The final effective policy settings.
- Active exception records.
- Expired and pending exception IDs.
- The sorted set of suppressed check IDs.
- A trace containing each value, source layer, and source key.
- A canonical SHA-256 policy hash.

Equivalent policy inputs produce the same resolved result and hash. The current CLI validates this configuration, but the reserved `audit` command does not invoke the resolver yet.

## Reports and exit codes

### Output formats

`auth check` and `inventory` support:

- `json`: Machine-readable output. This is the default.
- `markdown`: Human-readable output.

### Exit codes

| Code | Meaning | Typical action |
| --- | --- | --- |
| `0` | The requested implemented command completed successfully. | Review the report. |
| `1` | Reserved for a completed future audit with findings above its configured failure threshold. | Review findings. |
| `2` | The run was incomplete or failed operationally. | Check authentication, authorization, rate limits, network access, coverage details, or command availability. |
| `3` | The command, configuration, policy, plan, or approval is invalid. | Correct the input before retrying. |

A partial inventory always exits with code `2`, even if it returns some repository records. Do not treat partial output as complete coverage.

To inspect the last exit code in PowerShell:

```powershell
$LASTEXITCODE
```

## Troubleshooting

### `uv` is not recognized

Close and reopen PowerShell after installing uv. Then run:

```powershell
uv --version
```

If it still fails, use the [official uv installation guide](https://docs.astral.sh/uv/getting-started/installation/) to verify the installation and PATH.

### Configuration already exists

`init` protects existing files. Either use the existing file, select a different `--output` path, or explicitly use `--overwrite` after reviewing the target.

### `Invalid configuration: ValidationError`

Common causes are:

- Incorrect YAML indentation.
- An unknown field.
- A literal token in a credential field.
- A URL instead of a hostname in `github_host`.
- `include_owned` or `include_administered` disagreeing with `affiliations`.
- An exception without a valid expiration or `permanent: true`.
- A non-UTC exception timestamp.

Compare the edited file with a fresh configuration created at a separate path.

### Credential was not found in keyring

Store it again with the exact service and account expected by the configuration:

```powershell
uv run keyring set github-account-maintainer discovery
```

Then confirm that the YAML reference is exactly:

```text
keyring:github-account-maintainer/discovery
```

Use `uv run keyring diagnose` if the keyring backend is unavailable.

### Authenticated login does not match configured login

The stored token belongs to a different GitHub user than `account.login`.

1. Confirm the intended GitHub login.
2. Replace the keyring entry with a token created by that account, or correct `account.login`.
3. Run `auth check` again.

Do not disable the identity check.

### Authentication error 401

The token is missing, invalid, expired, or revoked. Create or store a valid replacement token and retry.

### Authorization error 403

The token or account lacks access, an organization approval is pending, or GitHub denied the request. Review the token's resource owner, repository selection, metadata permission, expiration, and organization policy.

### Rate-limit error 403 or 429

Wait until the reported reset or retry period. Repeated immediate retries can prolong the problem. The tool fails closed and marks the inventory partial.

### Expected repositories are missing

Check all of these:

1. The token's resource owner.
2. The token's selected repositories.
3. Repository **Metadata: read** permission.
4. Organization approval status.
5. `include_private`.
6. `affiliations`.
7. The matching `include_owned` and `include_administered` flags.
8. Whether your GitHub account itself has access.

Fine-grained tokens have owner and repository boundaries. One token may not cover repositories owned by unrelated organizations.

### Inventory returns some data but exits with code 2

The report is partial. Inspect its final `inventory.repositories` coverage record and `detail` value. Earlier pages may be present, but declared coverage was not completed.

## Development

### Repository structure

| Path | Purpose |
| --- | --- |
| `src/github_account_maintainer/` | Application package. |
| `tests/` | Unit tests and sanitized fixtures. |
| `.github/workflows/` | Pinned GitHub Actions validation. |
| `prompts/` | Approved project specification. |
| `assessment.md` | Current capability, safety, limitation, and verification overview. |
| `changelog.md` | Complete repository change log. |
| `future-upgrades.md` | Prioritized backlog with stable `FUT` IDs. |
| `completed-upgrades.md` | Verified implemented upgrades. |

### Set up the development environment

```powershell
uv sync --locked --dev
```

### Run validation

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv lock --check
```

The current baseline is 81 tests with 95.76 percent total coverage. The configured minimum is 90 percent.

Pull requests and pushes to `main` run equivalent validation. CodeQL scans Python and GitHub Actions sources.

### Repository maintenance rules

Every repository change must:

1. Update `changelog.md` under `Unreleased`.
2. Review and update `assessment.md`.
3. Keep the README accurate when commands, behavior, status, safety, or setup changes.
4. Preserve the read-only and fail-closed boundaries unless a later approved release explicitly changes them.

When a tracked upgrade is implemented:

1. Remove it from `future-upgrades.md`.
2. Add it to `completed-upgrades.md` with its original ID and verification evidence.
3. Add at least one new, distinct future idea in the same pull request.
4. Confirm that no item appears in both ledgers and no ID is assigned twice.

## Project documents

- [Project specification](prompts/github-account-maintainer-project-specification.md): Approved scope, architecture, safety model, command surface, and release gates.
- [Assessment](assessment.md): Current implemented behavior, risks, limitations, verification, and next priorities.
- [Changelog](changelog.md): Every repository change.
- [Future upgrades](future-upgrades.md): Three-tier prioritized backlog.
- [Completed upgrades](completed-upgrades.md): Implemented upgrades with evidence.
- [Security policy](.github/SECURITY.md): Supported versions and vulnerability-reporting instructions.
- [License](LICENSE): MIT license terms.

## Release roadmap

The remaining Release 0.1 work is:

1. Implement read-only repository metadata and community-file checks.
2. Implement schema-versioned account audit reports and finding evaluation.
3. Connect repository classification and policy resolution to the audit workflow.
4. Validate the complete read-only Release 0.1 gate with contract fixtures and a local pilot.

No remediation work begins until the read-only Release 0.1 gate passes.
