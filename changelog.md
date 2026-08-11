# Changelog

This file records every repository change, including code, documentation, configuration, dependencies, workflows, security controls, and maintenance files. Even the smallest change must add or update an entry under `Unreleased` in the same commit or pull request.

## Unreleased

### Added

- Added FUT-006 sanitized audit history in a versioned local SQLite database with per-account hashed identity, stable run and finding keys, and new, persistent, resolved, and regressed transitions.
- Added the `history` command with count-only JSON and Markdown summaries, a 1 through 100 run limit, default audit recording, the `--no-history` per-run escape, and the persistent `history.enabled` configuration switch.
- Added numbered transactional forward-only migrations, database integrity checks, readable pre-migration backups for nonempty databases, newer-schema rejection, chronological ordering, duplicate-run idempotency, and fail-closed local path validation.
- Added repository ignore rules for SQLite databases, journals, write-ahead logs, shared-memory files, and migration-backup directories as defense in depth.
- Added synthetic history contracts for privacy exclusions, all transition states, partial-run resolution protection, migrations, rollback, backups, unsafe paths, empty history, newer schemas, and CLI behavior.
- Added FUT-005 with twelve GET-only checks for branch protection, active rulesets, required reviews, required status checks, Actions policy, default workflow permissions, Dependabot alerts and security updates, secret scanning, push protection, code scanning, and private vulnerability reporting.
- Added explicit `supported`, `not_applicable`, and `unverified` coverage states and fail-closed partial-run behavior for unverified requested evidence.
- Added permission-aware synthetic contracts for complete, inaccessible, not-applicable, unverified, unsupported, and noncompliant settings and security evidence.
- Added count-only expanded Release 0.1 live-pilot evidence for two matching GET-only runs across 73 repositories, 1,898 check results, 2,045 coverage records, 604 findings, and zero writes.
- Added FUT-004 Release 0.1 gate manifest mapping all ten specification criteria to automated and live-pilot evidence.
- Added a paginated synthetic Release 0.1 account fixture and end-to-end tests for separate credentials, public and private repositories, policy hashes, 14 checks per repository, report contracts, redaction, GET-only requests, partial coverage, and repeatability.
- Added a count-only repeated live-pilot verifier that enforces minimal detail, serial requests, hard safety invariants, complete coverage, report schemas, and matching semantic fingerprints without persisting detailed reports.
- Added PowerShell and Linux pilot procedures that validate the locked build, lint, formatting, types, tests, and coverage before the live read-only audit.
- Added FUT-003 account-wide audit orchestration with separate discovery and audit credentials, internal private repository targets, classification, policy binding, and 14 checks per in-scope repository.
- Added schema-versioned aggregate JSON and detailed Markdown reports containing sanitized bindings, exact results, findings, severity counts, accepted permissions, and terminal coverage.
- Added configurable audit finding thresholds and deterministic exit codes `0`, `1`, and `2`, with incomplete coverage taking precedence over findings.
- Added case-insensitive repository include and exclude pattern enforcement with explicit `not_requested` coverage.
- Added multi-repository contract tests for GET-only operation, metadata reuse, private-name redaction, exclusions, findings, inaccessible repositories, malformed evidence, report rendering, and CLI exit behavior.
- Added FUT-014 deterministic classification for visibility, activity, repository kind, ownership, project type, repository class, and maintenance tier.
- Added per-dimension confidence, sanitized evidence, audited coverage, canonical classification hashes, and tamper detection.
- Added strict parsing for synthetic GitHub repository metadata and language-response fixtures while excluding raw topics and language names from serialization.
- Added privacy-safe repository policy-binding records that feed canonical class and project type into layered policy while preserving repository-specific precedence.
- Added JSON and Markdown renderers plus tests for classification thresholds, unknown evidence, mixed languages, input mismatch, policy precedence, privacy, and binding integrity.
- Added FUT-002 repository checks for description, homepage, topic count, primary language, visibility, archive state, and eight common community files.
- Added explicit compliant, noncompliant, observed, unknown, and inaccessible results with terminal coverage for every repository check.
- Added privacy-safe repository findings and schema-versioned JSON and Markdown report models that omit repository metadata values, repository file URLs and paths, and file content.
- Added strict layered metadata and community-file policy settings with required and optional requirements.
- Added synthetic GitHub REST contract fixtures and tests for compliant, noncompliant, inherited, inaccessible, failed, suppressed, credential-isolated, redacted, and GET-only behavior.
- Added this changelog and backfilled the complete repository history through PR #6.
- Added `future-upgrades.md` with three priority tiers, stable upgrade IDs, and an initial backlog aligned with the project specification.
- Added `completed-upgrades.md` as the permanent record for implemented and verified backlog items.
- Added a strict policy hierarchy covering account, repository-class, project-type, repository-specific, and exception layers.
- Added deterministic policy resolution with complete provenance traces and canonical SHA-256 hashes.
- Added active, expired, pending, permanent, and unmatched exception handling with strict identifiers and RFC 3339 UTC timestamp validation.
- Added equivalent YAML policy fixtures and policy tests covering precedence, canonicalization, hashing, exceptions, and unknown-field rejection.
- Added policy hashes and traces to account run reports.

### Changed

- Moved FUT-006 to `completed-upgrades.md`, added FUT-019 audit-history integrity verification and recovery planning to Tier 2, and synchronized the project prompt, README, assessment, changelog, and upgrade ledgers.
- Updated `audit` to record sanitized local history after GitHub reads while preserving its JSON and Markdown output contracts and exit-code precedence. Partial audits are recorded but cannot resolve findings that were not observed.
- Expanded each in-scope repository audit from 14 to 26 deterministic checks while preserving GET-only requests, serial execution, minimal-detail redaction, stable findings, and exact terminal coverage.
- Classified private repository branch and security restrictions as `unavailable_by_plan` and archived code scanning as `not_applicable`, while preserving fail-closed `inaccessible` behavior for actual public or credential authorization failures.
- Treated HTTP 204 from the automated security-fixes endpoint as enabled, preserved unknown classic branch requirements when protection evidence is inaccessible, and treated confirmed disabled code scanning as supported noncompliance instead of plan unavailability.
- Required audit credentials to use Metadata, Contents, Administration, and Code scanning alerts read access while continuing to prohibit every write permission.
- Moved FUT-005 to `completed-upgrades.md`, added FUT-018 credential capability preflight and token templates to Tier 2, and synchronized the README, assessment, pilot procedure, gate evidence, and project specification.
- Moved FUT-004 to `completed-upgrades.md`, added FUT-017 versioned release evidence bundles to Tier 2, and updated the README and assessment for pilot readiness.
- Moved FUT-003 to `completed-upgrades.md`, added FUT-016 audit report compatibility and migration tooling to Tier 2, and synchronized the README and assessment.
- Refactored inventory collection to retain private API selectors only in a non-serializable internal snapshot while preserving the existing redacted inventory report contract.
- Allowed account orchestration to pass already validated repository metadata into the check layer, avoiding a duplicate metadata request and preventing classification/check observation drift.
- Moved FUT-014 to `completed-upgrades.md`, added FUT-015 classification overrides and drift diagnostics to Tier 2, and synchronized the README and assessment.
- Moved FUT-002 to `completed-upgrades.md`, added FUT-014 repository classification and policy binding to Tier 1, and synchronized the README and assessment.
- Documented the repository check foundation, audit-credential boundary, policy defaults, outcome vocabulary, report contents, privacy behavior, and remaining account-audit work.
- Updated repository instructions and the README to require changelog maintenance for every change.
- Reviewed and updated `assessment.md` to record the new changelog requirement without changing the tool's runtime behavior.
- Updated repository instructions, the README, and the assessment to require implemented upgrades to move between ledgers with evidence and a replacement future idea.
- Moved FUT-001 to `completed-upgrades.md`, added FUT-013 policy diagnostics and exception hygiene to Tier 2, and synchronized the README and assessment.
- Reworked the README into a novice-first guide covering prerequisites, Windows setup, minimal-permission token creation, secure credential storage, configuration, commands, policy resolution, reports, exit codes, troubleshooting, development, and the release roadmap.
- Reviewed and updated `assessment.md` to record the documentation improvement without changing runtime behavior.

### Security

- Audit history excludes account and repository names, credential references, URLs, evidence, and raw current and desired values. It stores only hashed account identity, numeric repository IDs, stable check metadata, one-way state hashes, timestamps, and counts outside the repository.
- History state rejects Git worktrees, symbolic links, junctions, irregular database or backup targets, out-of-order runs, duplicate finding identities, corrupt databases, and schemas newer than the application.
- Settings and security evidence now stores only booleans, policy enums, and counts; branch names, ruleset names, status-check names, action allowlists, analysis details, alert content, and tokens are never serialized.
- Inaccessible or unverified security evidence cannot be reported as compliant and causes exit code `2`; verified noncompliance produces medium or high approval-required findings without enabling remediation.
- Plan-limited and archived feature states produce no false findings, expose no repository identities, and remain distinct from permission failures.

## 2026-08-10

### Added

- [`9f45f11`](https://github.com/mickpletcher/github-account-maintainer/commit/9f45f1110d82d3ca63640d329da56311642624f6) Added the maintained project assessment, repository assessment instructions, and README assessment links in [PR #6](https://github.com/mickpletcher/github-account-maintainer/pull/6).
- [`46bd0d5`](https://github.com/mickpletcher/github-account-maintainer/commit/46bd0d5a9b6c9a243c5848851d7487c4a5608efe) Added the security policy and weekly Dependabot configuration for uv and GitHub Actions in [PR #4](https://github.com/mickpletcher/github-account-maintainer/pull/4).
- [`46b07ca`](https://github.com/mickpletcher/github-account-maintainer/commit/46b07ca37a56775e36dfafda6dee99d9e59cc80d) Added read-only credential resolution, authentication identity verification, paginated repository inventory, redaction, coverage reporting, safe API failures, and expanded tests in [PR #2](https://github.com/mickpletcher/github-account-maintainer/pull/2).
- [`75ab133`](https://github.com/mickpletcher/github-account-maintainer/commit/75ab133d1e9136abc75c8b87bbefbf14acaf7331) Added the Release 0.1 Python package, strict configuration, CLI scaffold, report models, GET-only API client, test suite, CI workflow, README, and lockfile in [PR #1](https://github.com/mickpletcher/github-account-maintainer/pull/1).
- [`cd97868`](https://github.com/mickpletcher/github-account-maintainer/commit/cd978689672ee47375f1dfe6abec908833e992ae) Added the initial GitHub Account Maintainer project specification.
- [`223ae8a`](https://github.com/mickpletcher/github-account-maintainer/commit/223ae8a18ec68ab9bcdfa826d39b5e85293567ef) Created the repository with `.gitignore`, MIT license, and initial README.

### Changed

- [`75d0068`](https://github.com/mickpletcher/github-account-maintainer/commit/75d006848c113680882d4fdf552970baaedd6ca7) Updated `pytest-cov` from 6.3.0 to 7.1.0 and refreshed the lockfile in [PR #5](https://github.com/mickpletcher/github-account-maintainer/pull/5).
- [`547fe4a`](https://github.com/mickpletcher/github-account-maintainer/commit/547fe4a50d9b98502e80d5173be72830e3a673b8) Hardened the project specification with explicit scope, safety, privacy, permission, coverage, reporting, and release-gate requirements.
- [`f5c92c4`](https://github.com/mickpletcher/github-account-maintainer/commit/f5c92c49fcf2ac860bf2316559c24d9e9a96f5e8) Moved the project specification into the `prompts` directory.

### Security

- Enabled a no-bypass `main` ruleset requiring pull requests, linear history, resolved review threads, the `validate` status check, and passing CodeQL thresholds while blocking force pushes and branch deletion.
- Restricted GitHub Actions to GitHub-owned actions plus `astral-sh/setup-uv`, required full commit SHA pins, retained read-only workflow tokens, blocked workflow PR approval, and required approval for all external contributor workflows.
- Enabled Dependabot alerts and security updates, automated security fixes, CodeQL default setup, secret scanning, push protection, and private vulnerability reporting.
- Reduced Actions artifact and log retention to 30 days, enabled automatic merged-branch deletion, and disabled unused Projects and Wiki features.
- [`46bd0d5`](https://github.com/mickpletcher/github-account-maintainer/commit/46bd0d5a9b6c9a243c5848851d7487c4a5608efe) Upgraded pytest from 8.4.2 to 9.1.1 to resolve `GHSA-6w46-j5rx-g56g` in [PR #4](https://github.com/mickpletcher/github-account-maintainer/pull/4).
