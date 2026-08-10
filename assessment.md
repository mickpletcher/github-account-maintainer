# GitHub Account Maintainer Assessment

**Last reviewed:** 2026-08-10  
**Current release:** `0.1.0.dev0`  
**Overall status:** Read-only authentication, repository inventory, and deterministic policy resolution are functional. The complete Release 0.1 audit workflow is not finished.

## Quick overview

GitHub Account Maintainer is a local-first Python CLI for auditing GitHub account resources against an explicit policy. It currently verifies the configured GitHub identity, inventories repositories visible to a discovery credential, resolves strict layered policy with provenance and a stable hash, records coverage and permissions, redacts non-public repository identities by default, and produces JSON or Markdown reports.

The implemented GitHub path is serial and GET-only. It cannot modify repositories, account settings, branches, pull requests, security settings, or other GitHub resources.

## Command status

| Command | Status | Purpose |
| --- | --- | --- |
| `init` | Implemented | Creates a strict local configuration without overwriting an existing file unless explicitly requested. |
| `auth check` | Implemented | Resolves the discovery credential, calls `GET /user`, and verifies the authenticated login. |
| `inventory` | Implemented | Enumerates repositories through paginated `GET /user/repos` requests within declared affiliations and visibility. |
| `audit` | Reserved | Exits with code `2`; policy evaluation and repository checks are not implemented yet. |

## Implemented capabilities

- Python 3.12 package and Typer CLI managed with `uv`.
- Strict Pydantic configuration with unknown-field rejection and hard safety invariants.
- Credential references through Windows Credential Manager using `keyring` or explicitly named environment variables.
- Authenticated identity validation with credential values excluded from reports and errors.
- Same-origin URL, redirect, and pagination validation to prevent credential forwarding to another host.
- Repository inventory with affiliation and visibility declarations, pagination, deduplication, permission capture, timestamps, and terminal coverage states.
- Strict policy patches for account, repository-class, project-type, repository-specific, and exception layers.
- Deterministic policy precedence with a trace of every built-in and overridden value.
- Canonical SHA-256 hashes over effective policy and applicable exception state.
- Validation and deterministic handling for active, expired, pending, and permanent exceptions.
- Minimal report mode that replaces private and internal repository names with stable numeric labels and removes their URLs.
- Structured JSON and Markdown authentication and inventory reports.
- Stable CLI exit codes: `0` for success, `2` for incomplete or operational failure, and `3` for invalid configuration or input. Exit code `1` is reserved for completed audits with findings above the configured threshold.

## Safety and privacy assessment

- The GitHub API client exposes only GET operations.
- The automatic-write allowlist is empty.
- Automatic merge and destructive operations are prohibited by the configuration schema.
- Policy patches do not expose safety controls, so repository policy and exceptions cannot override hard safety invariants.
- Expired, pending, unmatched, and invalid exceptions cannot suppress checks.
- Credentials are resolved at runtime and are never written to configuration or report payloads.
- Transport and keyring errors are reduced to safe error classes without raw backend details.
- Private and internal repository names and URLs are redacted unless full report detail is explicitly enabled.
- API authentication, authorization, rate-limit, server, transport, response, and partial-coverage failures fail closed.
- Default application data paths resolve outside the source repository.

## Known limitations

- Metadata and community-file audits are not implemented.
- The account-level `audit` report and finding evaluation workflow are not implemented.
- The policy engine is not yet connected to the reserved account-level `audit` command.
- Repository classification is limited to inventory fields such as visibility, archive state, fork state, and effective permissions.
- No state database, scheduling, planning, approval, remediation, rollback, browser automation, backup, or notification workflow is implemented.
- The tool does not yet satisfy the complete Release 0.1 local pilot gate in the project specification.

## Verification and repository health

- Ruff lint passes.
- Ruff formatting checks pass.
- Strict Pyright checks pass with no errors.
- Pytest passes 81 tests with 95.76% total coverage.
- The lockfile is reproducible with `uv lock --check`.
- GitHub Actions uses read-only permissions, pinned action SHAs, non-persistent checkout credentials, stale-run cancellation, and a job timeout.
- CodeQL scans Python and GitHub Actions sources.
- Dependabot monitors uv and GitHub Actions dependencies.
- `main` requires a pull request, passing validation, passing CodeQL security thresholds, linear history, and resolved review threads.
- Every repository change is required to update this assessment and `changelog.md` in the same commit or pull request.
- Planned upgrades are tracked by stable IDs in a three-tier future backlog and moved to a permanent completed ledger with verification evidence when implemented.

## Next priorities

1. Add read-only repository metadata and community-file checks.
2. Implement the account-level audit command with findings and complete coverage reporting.
3. Validate the full Release 0.1 gate with read-only integration fixtures and a local pilot.

## Required maintenance

Every repository change must update this file and `changelog.md` in the same commit or pull request. Review the quick overview, command status, capabilities, limitations, verification results, and next priorities. If a change does not affect tool behavior, update the review date and record that the assessment remains accurate.

When an upgrade is implemented, move its stable ID from `future-upgrades.md` to `completed-upgrades.md`, record the delivery and verification evidence, and add at least one new upgrade idea to the future backlog in the same pull request.

**Latest assessment change:** Implemented FUT-001 deterministic policy resolution, explanation traces, exception state handling, and stable policy hashing. The GitHub execution path remains read-only.
