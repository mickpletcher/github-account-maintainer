# GitHub Account Maintainer Assessment

**Last reviewed:** 2026-08-10  
**Current release:** `0.1.0.dev0`  
**Overall status:** Read-only authentication, inventory, deterministic classification, policy binding, and repository metadata and community-file checks are functional. The account-level Release 0.1 audit workflow is not finished.

## Quick overview

GitHub Account Maintainer is a local-first Python CLI and library for auditing GitHub account resources against an explicit policy. It verifies configured identities, inventories repositories, validates ephemeral metadata evidence, classifies seven repository dimensions with confidence and stable hashes, binds repository class and project type into strict layered policy, and evaluates metadata and common community-file presence. Reports preserve explicit coverage and privacy-safe findings while redacting non-public repository identities by default.

The implemented GitHub path is serial and GET-only. It cannot modify repositories, account settings, branches, pull requests, security settings, or other GitHub resources.

## Command status

| Command | Status | Purpose |
| --- | --- | --- |
| `init` | Implemented | Creates a strict local configuration without overwriting an existing file unless explicitly requested. |
| `auth check` | Implemented | Resolves the discovery credential, calls `GET /user`, and verifies the authenticated login. |
| `inventory` | Implemented | Enumerates repositories through paginated `GET /user/repos` requests within declared affiliations and visibility. |
| `audit` | Reserved | Exits with code `2`; repository checks exist as library code but account orchestration is not connected yet. |

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
- Layered metadata policy for description, homepage, minimum topic count, and primary-language presence.
- Layered required or optional policy for README, LICENSE, SECURITY, CONTRIBUTING, CODE_OF_CONDUCT, SUPPORT, issue-template, and pull-request-template files.
- Fourteen deterministic repository checks using GitHub metadata, community-profile, and directory-listing endpoints.
- Explicit compliant, noncompliant, observed, unknown, and inaccessible outcomes paired with terminal coverage states.
- Privacy-safe findings with stable IDs, current and desired state, evidence, severity, remediation class, documentation links, and timestamps.
- Schema-versioned repository JSON and Markdown report models and renderers.
- Strict GitHub repository metadata and language-response parsing for classification evidence.
- Deterministic classification of visibility, activity, repository kind, ownership, project type, repository class, and maintenance tier.
- Per-dimension confidence and sanitized evidence with canonical SHA-256 classification hashes.
- Fail-closed inventory/evidence identity and state matching, canonical-value enforcement, hash verification, and classification/policy timestamp binding.
- Automatic repository-class and project-type policy binding with repository-specific precedence preserved.
- Privacy-safe schema-versioned JSON and Markdown classification and binding records.
- Minimal report mode that replaces private and internal repository names with stable numeric labels and removes their URLs.
- Structured JSON and Markdown authentication and inventory reports.
- Stable CLI exit codes: `0` for success, `2` for incomplete or operational failure, and `3` for invalid configuration or input. Exit code `1` is reserved for completed audits with findings above the configured threshold.

## Safety and privacy assessment

- The GitHub API client exposes only GET operations.
- Repository checks use the separately configured audit credential and verify its identity before checking a repository.
- Repository checks inspect metadata and directory listings only. They do not clone repositories or read file bodies.
- Check reports store counts and presence indicators instead of description text, homepage URLs, topic names, language names, file paths, or file content.
- Raw topics, language names, and internal repository selectors are excluded from classification evidence serialization and policy-binding reports.
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

- Account-level report aggregation, finding-threshold evaluation, and CLI exit behavior are not implemented.
- The implemented repository check layer is library code and is not directly available as a CLI command.
- Classification and policy binding are library code and are not connected to the reserved account-level `audit` command.
- Flagship and exempt maintenance tiers require explicit override support that is not implemented yet.
- Account-wide check orchestration and aggregation are not implemented.
- No state database, scheduling, planning, approval, remediation, rollback, browser automation, backup, or notification workflow is implemented.
- The tool does not yet satisfy the complete Release 0.1 local pilot gate in the project specification.

## Verification and repository health

- Ruff lint passes.
- Ruff formatting checks pass.
- Strict Pyright checks pass with no errors.
- Pytest passes 111 tests with 94.52% total coverage.
- The lockfile is reproducible with `uv lock --check`.
- GitHub Actions uses read-only permissions, pinned action SHAs, non-persistent checkout credentials, stale-run cancellation, and a job timeout.
- CodeQL scans Python and GitHub Actions sources.
- Dependabot monitors uv and GitHub Actions dependencies.
- `main` requires a pull request, passing validation, passing CodeQL security thresholds, linear history, and resolved review threads.
- Every repository change is required to update this assessment and `changelog.md` in the same commit or pull request.
- Planned upgrades are tracked by stable IDs in a three-tier future backlog and moved to a permanent completed ledger with verification evidence when implemented.
- The README provides novice-focused installation, credential, configuration, command, privacy, troubleshooting, and development guidance.

## Next priorities

1. Implement the account-level audit command with classification, policy binding, check orchestration, coverage aggregation, and exit-code behavior.
2. Validate the full Release 0.1 gate with a local read-only pilot.
3. Add explicit classification overrides and classification-drift diagnostics.

## Required maintenance

Every repository change must update this file and `changelog.md` in the same commit or pull request. Review the quick overview, command status, capabilities, limitations, verification results, and next priorities. If a change does not affect tool behavior, update the review date and record that the assessment remains accurate.

When an upgrade is implemented, move its stable ID from `future-upgrades.md` to `completed-upgrades.md`, record the delivery and verification evidence, and add at least one new upgrade idea to the future backlog in the same pull request.

**Latest assessment change:** Added FUT-014 deterministic repository classification, confidence and classification hashes, validated GitHub evidence parsing, privacy-safe policy-binding records, and automatic repository-class and project-type policy selection.
