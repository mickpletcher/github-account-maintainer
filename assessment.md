# GitHub Account Maintainer Assessment

**Last reviewed:** 2026-08-11
**Current release:** `0.1.0.dev0`  
**Overall status:** The read-only account audit implements 26 metadata, community, repository-settings, and security checks. FUT-006 adds sanitized versioned SQLite history with new, persistent, resolved, and regressed finding transitions. The expanded Release 0.1 private pilot passed two matching GET-only runs across 73 repositories with complete declared coverage and zero GitHub writes.

## Quick overview

GitHub Account Maintainer is a local-first Python CLI and library for auditing GitHub account resources against an explicit policy. It verifies separate discovery and audit credentials, inventories repositories, applies declared scope, validates ephemeral metadata evidence, classifies seven repository dimensions with confidence and stable hashes, binds repository class and project type into strict layered policy, and evaluates metadata, community-file presence, default-branch controls, Actions permissions, and supported security features. Account reports preserve exact terminal coverage, threshold evaluation, and privacy-safe findings while redacting non-public repository identities by default. The CLI records sanitized run and transition history outside the repository by default.

Release 0.1 has a versioned ten-criterion evidence manifest, a paginated public/private synthetic account contract, and a repeated live-pilot verifier. The verifier runs detailed audits only in memory and emits a count-only summary. The expanded 2026-08-10 private pilot completed two matching audits across 73 repositories, 1,898 check results, 2,045 coverage records, and 604 findings with zero writes.

The implemented GitHub path is serial and GET-only. It cannot modify repositories, account settings, branches, pull requests, security settings, or other GitHub resources.

## Command status

| Command | Status | Purpose |
| --- | --- | --- |
| `init` | Implemented | Creates a strict local configuration without overwriting an existing file unless explicitly requested. |
| `auth check` | Implemented | Resolves the discovery credential, calls `GET /user`, and verifies the authenticated login. |
| `inventory` | Implemented | Enumerates repositories through paginated `GET /user/repos` requests within declared affiliations and visibility. |
| `audit` | Implemented | Runs the complete read-only account workflow and emits schema-versioned JSON or Markdown with exit codes `0`, `1`, or `2`. |
| `history` | Implemented | Reads count-only recent run summaries and new, persistent, resolved, and regressed finding-transition counts from local SQLite state. |

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
- Twenty-six deterministic repository checks covering metadata, community files, default-branch controls, Actions permissions, and security features.
- GET-only checks for branch protection, active rulesets, required reviews and status checks, restricted Actions execution, read-only workflow tokens, Dependabot alerts and updates, secret scanning, push protection, code scanning, and private vulnerability reporting.
- Explicit `supported`, `unsupported`, `unavailable_by_plan`, `inaccessible`, `not_applicable`, and `unverified` coverage states, with unverified or inaccessible requested evidence making the audit partial instead of producing false compliance findings.
- Explicit compliant, noncompliant, observed, unknown, and inaccessible outcomes paired with terminal coverage states.
- Privacy-safe findings with stable IDs, current and desired state, evidence, severity, remediation class, documentation links, and timestamps.
- Schema-versioned repository JSON and Markdown report models and renderers.
- Strict GitHub repository metadata and language-response parsing for classification evidence.
- Deterministic classification of visibility, activity, repository kind, ownership, project type, repository class, and maintenance tier.
- Per-dimension confidence and sanitized evidence with canonical SHA-256 classification hashes.
- Fail-closed inventory/evidence identity and state matching, canonical-value enforcement, hash verification, and classification/policy timestamp binding.
- Automatic repository-class and project-type policy binding with repository-specific precedence preserved.
- Privacy-safe schema-versioned JSON and Markdown classification and binding records.
- Account-wide orchestration that reuses validated metadata for classification and checks, continues across repository-specific failures, and aggregates bindings, results, findings, permissions, and coverage.
- Case-insensitive include and exclude pattern enforcement with `not_requested` coverage for repositories outside declared audit scope.
- Configurable finding threshold with severity counts and deterministic exit codes: `0` for a clean complete run, `1` for a complete run at or above threshold, and `2` for partial coverage.
- Minimal report mode that replaces private and internal repository names with stable numeric labels and removes their URLs.
- Default sanitized audit-history recording with configured-account binding, per-account isolation, deterministic idempotent semantic run IDs, stable finding identities, and chronological ordering.
- New, persistent, resolved, and regressed finding transitions, with absent findings resolved only after complete audits.
- Count-only JSON and Markdown history reports with a configurable 1 through 100 run limit and no GitHub requests.
- Versioned SQLite schema with numbered transactional forward-only migrations, integrity checks, pre-migration backups for nonempty databases, and newer-schema rejection.
- Structured JSON and Markdown authentication and inventory reports.
- Stable CLI exit codes: `0` for complete below-threshold results, `1` for complete audits at or above threshold, `2` for incomplete or operational failure, and `3` for invalid configuration or input.
- Versioned mapping from all ten Release 0.1 specification criteria to locked, test, fixture, and live-pilot evidence.
- Synthetic end-to-end contract covering pagination, separate credentials, public and private repositories, deterministic hashes, 26 checks per repository, exact report contracts, redaction, and GET-only requests.
- Count-only repeated live-pilot verifier that enforces minimal detail, serial requests, hard safety invariants, complete declared coverage, at least one in-scope repository, JSON and Markdown contracts, and matching semantic fingerprints.
- Windows PowerShell and Linux pilot procedures that run the locked validation gate before the live GitHub audit.

## Safety and privacy assessment

- The GitHub API client exposes only GET operations.
- Repository checks use the separately configured audit credential and verify its identity before checking a repository.
- Repository checks inspect metadata and directory listings only. They do not clone repositories or read file bodies.
- Check reports store counts and presence indicators instead of description text, homepage URLs, topic names, language names, file paths, or file content.
- Settings and security reports store booleans, policy enums, and counts. They exclude branch names, ruleset names, status-check names, allowed-action patterns, analysis details, and security-alert content.
- Raw topics, language names, and internal repository selectors are excluded from classification evidence serialization and policy-binding reports.
- Private repository selectors are retained only in an internal inventory snapshot long enough to make audit GET requests and are never serialized in minimal account reports.
- The automatic-write allowlist is empty.
- Automatic merge and destructive operations are prohibited by the configuration schema.
- Policy patches do not expose safety controls, so repository policy and exceptions cannot override hard safety invariants.
- Expired, pending, unmatched, and invalid exceptions cannot suppress checks.
- Credentials are resolved at runtime and are never written to configuration or report payloads.
- Transport and keyring errors are reduced to safe error classes without raw backend details.
- Private and internal repository names and URLs are redacted unless full report detail is explicitly enabled.
- API authentication, authorization, rate-limit, server, transport, response, and partial-coverage failures fail closed.
- The pilot does not persist detailed reports and does not emit account names, repository names or IDs, URLs, credential references, policy selectors, or finding details.
- Audit history stores only a hashed account key, numeric repository IDs, stable check metadata, transition counts, timestamps, and one-way state hashes. It excludes account and repository names, credential references, URLs, evidence, and raw current or desired state.
- History paths inside a Git worktree, symbolic links, junctions, irregular database files, and irregular migration-backup directories fail closed.
- Repository ignore rules exclude SQLite databases, journal files, write-ahead logs, shared-memory files, and migration-backup directories as defense in depth.
- Partial audits never resolve absent findings. Re-recording an identical run is idempotent, and out-of-order runs are rejected.
- A history persistence failure preserves the completed audit report on stdout, emits only a sanitized error on stderr, and forces exit code `2`.
- Default application data paths resolve outside the source repository.

## Known limitations

- Flagship and exempt maintenance tiers require explicit override support that is not implemented yet.
- Local audit history is implemented, but automatic retention pruning, scheduling, planning, approval, remediation, rollback, browser automation, backup, and notification workflows are not.
- The expanded FUT-005 audit requires repository Metadata, Contents, Administration, and Code scanning alerts read access. The live credential boundary was verified with those read-only permissions. Missing permissions remain explicit `inaccessible` or `unverified` states and make the run partial.
- Private plan restrictions are explicit `unavailable_by_plan` states. Archived repository code scanning is `not_applicable`. Neither state creates false findings or makes otherwise complete declared coverage partial.
- Code scanning detection checks default setup first and then only the presence count of advanced or external analyses. It does not store analysis records, alert details, paths, refs, or tool names.

## Verification and repository health

- Ruff lint passes.
- Ruff formatting checks pass.
- Strict Pyright checks pass with no errors.
- Pytest passes 151 tests with 93.21% total coverage.
- The lockfile is reproducible with `uv lock --check`.
- GitHub Actions uses read-only permissions, pinned action SHAs, non-persistent checkout credentials, stale-run cancellation, and a job timeout.
- CodeQL scans Python and GitHub Actions sources.
- Dependabot monitors uv and GitHub Actions dependencies.
- `main` requires a pull request, passing validation, passing CodeQL security thresholds, linear history, and resolved review threads.
- Every repository change is required to update this assessment and `changelog.md` in the same commit or pull request.
- Planned upgrades are tracked by stable IDs in a three-tier future backlog and moved to a permanent completed ledger with verification evidence when implemented.
- The README provides novice-focused installation, credential, configuration, command, privacy, troubleshooting, and development guidance.
- The expanded count-only live pilot passed two matching GET-only runs across 73 repositories, 1,898 results, 2,045 coverage records, and 604 findings with zero writes. The credential preflight and plan-availability diagnostics exposed no repository or credential details.

## Next priorities

1. Implement FUT-018 credential capability preflight and token templates.
2. Add explicit classification overrides and classification-drift diagnostics through FUT-015.
3. Implement FUT-019 audit-history integrity verification and recovery planning.

## Required maintenance

Every repository change must update this file and `changelog.md` in the same commit or pull request. Review the quick overview, command status, capabilities, limitations, verification results, and next priorities. If a change does not affect tool behavior, update the review date and record that the assessment remains accurate.

When an upgrade is implemented, move its stable ID from `future-upgrades.md` to `completed-upgrades.md`, record the delivery and verification evidence, and add at least one new upgrade idea to the future backlog in the same pull request.

**Latest assessment change:** Recorded FUT-006 sanitized local SQLite history, transition semantics, migration and path safeguards, the `history` command, and 151-test verification at 93.21% coverage.
