# Changelog

This file records every repository change, including code, documentation, configuration, dependencies, workflows, security controls, and maintenance files. Even the smallest change must add or update an entry under `Unreleased` in the same commit or pull request.

## Unreleased

### Added

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
