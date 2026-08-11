# GitHub Account Maintainer

GitHub Account Maintainer is a local command-line tool for inspecting the GitHub repositories your account can access. It is being built to compare those repositories with an explicit policy and report what is correct, missing, unsupported, or inaccessible.

The current version is deliberately read-only. It can verify GitHub identities, inventory and classify repositories, redact private repository identities, bind classifications to layered policy, audit metadata, community files, repository settings, and security features, aggregate an account audit, and retain sanitized local finding history. It cannot change GitHub.

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
- [Audit repositories](#audit-repositories)
- [Review audit history](#review-audit-history)
- [Run the Release 0.1 pilot](#run-the-release-01-pilot)
- [Command reference](#command-reference)
- [Repository check foundation](#repository-check-foundation)
- [Classification and policy binding](#classification-and-policy-binding)
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
| Classify repositories and bind policy | Implemented | The account audit records confidence and binds repository-class, project-type, and repository policy. |
| Resolve layered policy | Implemented | The account audit resolves and hashes policy separately for each in-scope repository. |
| Audit repository policy | Implemented | The public `audit` command runs 26 deterministic metadata, community, settings, and security checks per in-scope repository. |
| Track audit history | Implemented | A versioned local SQLite database tracks new, persistent, resolved, and regressed findings without storing repository names or report evidence. |
| Apply GitHub changes | Not implemented | No GitHub mutation endpoint exists. |
| Full Release 0.1 audit | Pilot passed | Two expanded 26-check read-only runs matched across 73 repositories with zero writes on 2026-08-10. |

This status matters. A successful inventory does not mean the account passed a full security or compliance audit.

## What the tool does

The implemented code can:

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
- Classify visibility, activity, repository kind, ownership, project type, repository class, and maintenance tier from validated evidence.
- Record per-dimension confidence and privacy-safe evidence, plus terminal classification coverage and a stable classification hash.
- Bind the classified repository class and project type to the existing policy hierarchy before repository checks run.
- Evaluate repository description, homepage, topic count, primary language, visibility, and archive state.
- Detect eight common community files through GitHub's community-profile and contents metadata endpoints without cloning or reading file content.
- Audit default-branch protection, active rules, required reviews, required status checks, Actions policy, and default workflow token permissions.
- Audit Dependabot alerts and security updates, secret scanning, push protection, code scanning, and private vulnerability reporting.
- Distinguish supported, inaccessible, not-applicable, unverified, unsupported, and unavailable-by-plan settings evidence without treating missing evidence as compliance.
- Distinguish compliant, noncompliant, observed, unknown, and inaccessible outcomes with a terminal coverage state for every check.
- Produce privacy-safe repository findings with stable check IDs, exact current and desired states, evidence, severity, and remediation class.
- Run the complete account audit from one CLI command and continue across repository-specific failures.
- Apply include and exclude patterns before requesting repository audit endpoints.
- Aggregate schema-versioned JSON or Markdown bindings, results, findings, severity counts, accepted permissions, and coverage.
- Record sanitized audit runs and finding transitions in a versioned local SQLite database.
- Report recent audit history as count-only JSON or Markdown without exposing account or repository names.
- Exit with code `0`, `1`, or `2` based on complete coverage and the configured finding threshold.

## What the tool does not do

The current version does not:

- Change repository settings.
- Create, edit, close, approve, or merge pull requests.
- Create or delete repositories, branches, tags, releases, issues, or files.
- Enable or disable GitHub security features.
- Dismiss security alerts.
- Clone repository content during inventory.
- Infer flagship or exempt maintenance tiers without explicit future override rules.
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
- Repository checks report presence and counts. They do not store descriptions, homepage URLs, topic names, language names, file paths, or file content.
- Classification evidence treats raw topics and language names as ephemeral input. Serialized evidence and binding reports exclude those values and the internal repository API name.
- Audit history stores a hashed account key, numeric repository IDs, stable check metadata, transition counts, timestamps, and one-way state hashes. It does not store account names, repository names, credentials, URLs, evidence, or raw current and desired values.
- SQLite migrations are numbered, transactional, and forward-only. A local backup is created before a nonempty database is upgraded.
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

The implemented commands use discovery and audit credential references. Use fine-grained personal access tokens with the smallest practical access. A single read-only token may be stored under both references, or you may create separate tokens.

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
10. Grant repository **Metadata** read access for discovery. For the complete `audit`, also grant repository **Contents**, **Administration**, and **Code scanning alerts** read access.
11. Do not grant write permissions for the current release.
12. Generate the token and copy it once.

The implemented `GET /user` call does not require an additional fine-grained permission. Inventory requires repository **Metadata: read** access. The complete audit requires **Contents: read** for community-file metadata, **Administration: read** for branch protection, Actions, Dependabot, and code-scanning setup, and **Code scanning alerts: read** to detect advanced or external code-scanning analyses. No write permission is required. See GitHub's official endpoint documentation for [repository inventory](https://docs.github.com/en/rest/repos/repos#list-repositories-for-the-authenticated-user), [branch protection](https://docs.github.com/en/rest/branches/branch-protection), [Actions permissions](https://docs.github.com/en/rest/actions/permissions), and [code scanning](https://docs.github.com/en/rest/code-scanning/code-scanning).

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

To run the full audit, also store a token under the audit account:

```powershell
uv run keyring set github-account-maintainer audit
```

That token needs Metadata, Contents, Administration, and Code scanning alerts read access. If one least-privilege token has all four read permissions, you may paste the same token into both prompts.

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

## Audit repositories

After both credentials are stored, run the complete read-only audit:

```powershell
uv run github-account-maintainer audit --format markdown
$LASTEXITCODE
```

The command performs this sequence:

1. Verifies the discovery credential and inventories every repository in declared affiliation and visibility scope.
2. Verifies the separate audit credential against the configured GitHub login.
3. Applies `repositories.include_patterns` and `repositories.exclude_patterns`.
4. Reads repository metadata and language totals for deterministic classification.
5. Resolves and hashes the effective policy for that repository.
6. Runs six metadata, eight community-file, six repository-settings, and six security-feature checks.
7. Continues to the next repository if one repository is inaccessible or returns invalid evidence.
8. Aggregates policy bindings, results, findings, permissions, and terminal coverage.
9. Evaluates findings against `audit.failure_threshold`.
10. Records a sanitized local run and its finding transitions when history is enabled.

JSON is the default and is intended for local automation:

```powershell
uv run github-account-maintainer audit --format json |
  Set-Content -Path .\account-audit.json -Encoding utf8
$auditExitCode = $LASTEXITCODE
```

Treat saved audit reports as private local data. Minimal mode redacts private and internal names, but reports still contain public repository names, numeric repository IDs, policy decisions, findings, and operational coverage.

Exit code `0` means complete coverage with no finding at or above the configured threshold. Code `1` means complete coverage with a threshold finding. Code `2` means coverage is partial, even if findings were also produced. Code `3` means the configuration or command input is invalid.

By default, complete and partial audit results are recorded in:

```text
%LOCALAPPDATA%\GitHubAccountMaintainer\state\audit-history.sqlite3
```

This database is local application state. It is not inside the cloned repository and is not pushed to GitHub. To skip history for one audit, add `--no-history`. To disable automatic history for all audits using a configuration, set `history.enabled` to `false`.

## Review audit history

Show the 20 most recent stored runs as readable Markdown:

```powershell
uv run github-account-maintainer history --format markdown
```

JSON is the default. Use `--limit` to return between 1 and 100 recent runs:

```powershell
uv run github-account-maintainer history --limit 50
```

The history report contains run timestamps, complete or partial status, repository and finding counts, a one-way run ID, and these transition counts:

- `new`: The finding identity has not been seen before.
- `persistent`: The finding was active in local history and appeared again.
- `resolved`: A complete audit no longer contains a previously active finding.
- `regressed`: A resolved finding appeared again.

A partial audit never resolves an absent finding. Missing evidence is not proof that a problem was fixed. The history command returns only sanitized counts and run metadata. It does not return finding evidence, current or desired values, repository names, credential references, URLs, or local file paths.

Runs must match the configured account and be recorded in chronological order. Re-recording the same semantic audit is idempotent and does not duplicate events. The tool rejects a database created by a newer schema. When an older nonempty database needs an upgrade, the tool checks database integrity, creates a timestamped backup under the local state directory, and applies each numbered migration in its own transaction.

If enabled history recording fails, `audit` still writes its complete JSON or Markdown report to stdout. It writes a sanitized history error to stderr and exits with code `2` so automation cannot mistake missing requested history for full success.

## Run the Release 0.1 pilot

The Release 0.1 pilot verifies the locked build and then runs the live audit twice. It emits only counts and pass/fail state. Detailed audit reports stay in memory and are not written to disk.

Use a private minimal-detail configuration with at least one repository in scope:

```powershell
.\scripts\Invoke-Release01Pilot.ps1 `
  -Config "$env:LOCALAPPDATA\GitHubAccountMaintainer\config\config.yaml" `
  -Repeat 2
```

The pilot intentionally rejects:

- `report_detail: full`;
- fewer than two or more than five repeated audits;
- a non-serial GitHub request mode;
- automatic write operations;
- automatic merge or destructive operations;
- zero in-scope repositories;
- partial inventory, classification, or check coverage;
- missing JSON or Markdown report contract sections;
- different semantic results between the repeated runs.

Findings do not fail the pilot. Findings describe repository compliance. The pilot verifies that the audit itself is complete, deterministic, private by default, and read-only.

The latest 2026-08-10 pilot passed two matching runs across 73 repositories. Each run produced 1,898 check results, 2,045 coverage records, and 604 findings. The summary contained counts only, enforced minimal detail and GET-only requests, and recorded zero automatic writes.

See [RELEASE-0.1-PILOT.md](RELEASE-0.1-PILOT.md) for prerequisites, Windows and Linux commands, safe output fields, exit behavior, and the evidence manifest.

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
uv run github-account-maintainer audit [--config PATH] [--format json|markdown] [--no-history]
```

This command inventories repositories with the discovery credential, verifies the separate audit credential, applies repository scope patterns, classifies each in-scope repository, binds its effective policy, runs 26 checks, aggregates the result, and records sanitized history unless configuration or `--no-history` disables it. It uses only GET requests and does not change GitHub.

For a readable report:

```powershell
uv run github-account-maintainer audit --format markdown
$LASTEXITCODE
```

The command continues when one repository is inaccessible or malformed. The final report marks every affected check with terminal coverage and exits with code `2` so partial evidence cannot look complete.

### `history`

```powershell
uv run github-account-maintainer history [--config PATH] [--format json|markdown] [--limit 1..100]
```

This command reads sanitized run and transition counts for the configured account. It does not contact GitHub. If no history database exists, it returns an empty report without creating one.

## Repository check foundation

FUT-002 provides the read-only repository check layer used by the account-level `audit` command.

The layer performs 26 stable checks:

- Metadata: `metadata.description`, `metadata.homepage`, `metadata.topics`, `metadata.primary_language`, `metadata.visibility`, and `metadata.archive_state`.
- Community files: `community.readme`, `community.license`, `community.security`, `community.contributing`, `community.code_of_conduct`, `community.support`, `community.issue_template`, and `community.pull_request_template`.
- Repository settings: `settings.branch_protection`, `settings.rulesets`, `settings.required_reviews`, `settings.required_status_checks`, `settings.actions_permissions`, and `settings.actions_workflow_permissions`.
- Security features: `security.dependabot_alerts`, `security.dependabot_security_updates`, `security.secret_scanning`, `security.push_protection`, `security.code_scanning`, and `security.private_vulnerability_reporting`.

Each result records:

- `outcome`: `compliant`, `noncompliant`, `observed`, `unknown`, or `inaccessible`.
- `coverage_state`: the terminal coverage vocabulary, including `audited`, `supported`, `unsupported`, `unavailable_by_plan`, `inherited`, `inaccessible`, `not_applicable`, `unverified`, `skipped_by_policy`, `not_requested`, and `failed`.
- Sanitized current and desired state.
- Count-only or presence-only evidence.

Required values that are confirmed missing produce findings. Optional values are observed without producing false violations. Repository or community-profile authorization and not-found responses are treated as inaccessible. A missing directory listing is treated as an absent directory only after repository access succeeds. Malformed or operational failures are unknown and failed. An active policy exception marks its check `skipped_by_policy` and does not produce a finding.

Settings and security checks fail closed. Supported evidence can produce a compliant or noncompliant result. A confirmed disabled feature is supported evidence and may produce a finding. Inaccessible or unverified evidence makes the account audit partial, records unknown values instead of false negatives, and does not produce a false finding. A feature that does not apply to the repository visibility, archive state, or branch state uses `not_applicable`. A feature that GitHub does not provide for the active plan uses `unavailable_by_plan`. Private repositories without the required GitHub plan use `unavailable_by_plan` for unavailable branch controls, secret scanning, push protection, and code scanning. Archived repositories use `not_applicable` for code scanning.

The implementation uses only these GET requests:

- `GET /user` to verify the audit credential identity.
- `GET /repos/{owner}/{repository}` for metadata.
- `GET /repos/{owner}/{repository}/community/profile` for GitHub-recognized community files on non-forks.
- `GET /repos/{owner}/{repository}/contents`, plus `.github` and `docs` directory listings, for file-presence metadata.
- `GET /repos/{owner}/{repository}/rules/branches/{branch}` and the default-branch protection endpoint for branch policy.
- Repository Actions policy and default workflow permission GET endpoints.
- Dependabot alert and automated security-fix status GET endpoints. HTTP 204 means enabled and HTTP 404 means disabled for these status-only checks; the tool does not try to parse an empty 204 response body.
- Repository security-and-analysis metadata, code-scanning setup or count-only analysis presence, and private vulnerability reporting status.

It does not clone repositories or request file bodies. Inherited community files are reported with `inherited` coverage when GitHub identifies a source outside the audited repository.

## Classification and policy binding

FUT-014 provides the deterministic layer between inventory and repository checks. FUT-003 now orchestrates it across every in-scope inventoried repository.

The classifier evaluates seven dimensions:

| Dimension | Possible results |
| --- | --- |
| Visibility | `public`, `private`, or `internal` |
| Activity | `active`, `dormant`, `abandoned_candidate`, `archived`, or `unknown` |
| Repository kind | `source`, `fork`, `template`, `mirror`, or `empty` |
| Ownership | `personal_account`, `organization`, or `unknown` |
| Project type | `python`, `powershell`, `nodejs`, `mcp_server`, `documentation`, `configuration`, `web_application`, `infrastructure`, `mixed`, or `unknown` |
| Repository class | `application`, `library`, `cli`, `service`, `desktop_application`, `github_pages`, `infrastructure`, `documentation`, `configuration`, `empty`, or `unknown` |
| Maintenance tier | `active`, `standard`, `experimental`, or `legacy` from current evidence. `flagship` and `exempt` are reserved for explicit future override rules. |

Direct GitHub facts such as visibility, archive state, fork state, owner type, template state, mirror state, repository size, Pages state, and push time receive the strongest confidence. Project type and repository class use a fixed allowlist of known topic and language families. Unknown inputs never become new policy selectors. Multiple recognized language families that each represent at least 20 percent are classified as `mixed`.

Activity uses fixed Release 0.1 thresholds:

- `active`: pushed within 180 days.
- `dormant`: last push was 181 through 730 days ago.
- `abandoned_candidate`: last push was more than 730 days ago.
- `archived`: GitHub reports the repository as archived.
- `unknown`: no push timestamp was available.

The raw GitHub repository and language responses are validated before classification. Repository ID, visibility, archive state, and fork state must match inventory. A mismatch fails closed. The classification hash must match its canonical decisions, and policy binding requires the classification timestamp to equal the policy evaluation timestamp.

Binding feeds the canonical repository class and project type into policy resolution in the existing order. Repository-specific policy still has higher precedence. The privacy-safe binding record contains the redacted display name, classification decisions and confidence, classification hash, policy hash, and applied policy-source types. It does not contain the internal `owner/repository` selector, raw topics, raw language names, or policy source keys.

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
| `audit` | Sets the finding severity that makes a complete audit exit with code `1`. |
| `history` | Enables or disables automatic sanitized SQLite history recording for `audit`. |
| `repositories` | Supplies account-wide repository policy defaults. Include and exclude patterns are applied by `audit`. |
| `pins` | Validated policy for the planned profile-pin feature. Not active yet. |
| `readme` | Validated policy for planned README checks and remediation. Not active yet. |
| `metadata` | Active desired-state policy for the repository metadata check layer. |
| `community` | Active required or optional policy for eight common community files. |
| `social_preview` | Validated policy for planned social-preview work. Not active yet. |
| `security` | Active read-only policy toggles for repository settings and security-feature checks. |
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

The `auth check` and `inventory` commands use only `credentials.discovery`. The `audit` command uses discovery for inventory and `credentials.audit` for repository evidence. It verifies both identities and never falls back to the discovery or remediation credential for checks.

Store the audit token after storing the discovery token:

```powershell
uv run keyring set github-account-maintainer audit
```

The audit token needs repository Metadata, Contents, Administration, and Code scanning alerts read access for every repository in scope. You may store the same least-privilege token under both keyring accounts, but separate credentials make the access boundary explicit.

### Audit threshold and repository scope

The default threshold is `low`:

```yaml
audit:
  failure_threshold: low
repositories:
  include_patterns:
    - "*"
  exclude_patterns: []
```

Valid thresholds are `informational`, `low`, `medium`, `high`, and `critical`. Matching is case-insensitive and uses shell-style wildcard patterns against `owner/repository`. An excluded repository remains in inventory coverage but its classification and checks are marked `not_requested`.

### Audit history

History is enabled by default:

```yaml
history:
  enabled: true
```

Set `enabled: false` to prevent future `audit` commands from writing local history. This does not delete existing history. The `history` command can still read an existing database. Retention is not automatic in the current release because pruning requires its own explicit plan.

### Settings and security checks

The default configuration enables every implemented read-only settings and security check:

```yaml
security:
  audit_branch_protection: true
  audit_rulesets: true
  audit_required_reviews: true
  audit_required_status_checks: true
  audit_actions_permissions: true
  audit_actions_workflow_permissions: true
  audit_dependabot: true
  audit_secret_scanning: true
  audit_push_protection: true
  audit_code_scanning: true
  audit_private_vulnerability_reporting: true
  security_alert_dismissal: prohibited
```

Setting an audit toggle to `false` marks that check `skipped_by_policy`. It does not change GitHub. The `security_alert_dismissal` value is fixed at `prohibited`.

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
      metadata:
        minimum_topics: 2
      community:
        security: required
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

Equivalent policy inputs produce the same resolved result and hash. The `audit` command resolves and records one binding for each successfully classified in-scope repository.

The classification layer supplies `repository_class` and `project_type` automatically during account-wide CLI execution.

The built-in metadata policy requires a description, at least one topic, and a primary language. Homepage is optional. The built-in community policy requires README, LICENSE, and SECURITY files. CONTRIBUTING, CODE_OF_CONDUCT, SUPPORT, issue templates, and pull request templates are optional unless a matching policy layer makes them required.

## Reports and exit codes

### Output formats

`auth check`, `inventory`, `audit`, and `history` support:

- `json`: Machine-readable output. This is the default.
- `markdown`: Human-readable output.

The account audit report includes sanitized repository displays, classification and policy hashes, all check results, finding counts by severity, exact current and desired states, remediation details, accepted GitHub permissions, and terminal coverage. Internal selectors for private repositories are used only in memory and are not serialized in minimal mode.

Classification and policy binding also have schema-versioned JSON and Markdown renderers. They include confidence and hashes without exposing raw private classification inputs.

### Exit codes

| Code | Meaning | Typical action |
| --- | --- | --- |
| `0` | The command completed, coverage is complete, and no audit finding reached the configured threshold. | Review the report. |
| `1` | The audit completed and at least one finding reached the configured threshold. | Review and prioritize findings. |
| `2` | The run was incomplete or failed operationally. Partial status takes precedence over findings. | Check authentication, authorization, rate limits, network access, and coverage details. |
| `3` | The command, configuration, policy, plan, or approval is invalid. | Correct the input before retrying. |

A partial inventory or audit always exits with code `2`, even if it returns repository records or findings. Do not treat partial output as complete coverage.

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
- [Release 0.1 pilot](RELEASE-0.1-PILOT.md): Locked validation and count-only repeated live-audit procedure.
- [Release 0.1 gate manifest](release/release-0.1-gate.json): Machine-readable mapping of all ten gate criteria to evidence.
- [Security policy](.github/SECURITY.md): Supported versions and vulnerability-reporting instructions.
- [License](LICENSE): MIT license terms.

## Release roadmap

The expanded Release 0.1 private pilot passed on 2026-08-10. It completed two matching GET-only audits across 73 repositories, with 1,898 check results, 2,045 coverage records, 604 findings, and zero writes per run. Before tagging the release:

1. Rerun the count-only pilot after any further material audit change with a private minimal-detail configuration and valid read-only credentials.
2. Retain only the count-only result and CI links as release evidence. Do not commit private audit output.

Release 0.1 remains read-only. No remediation path is enabled.
