# Completed Upgrades

This file is the permanent record of upgrades completed from `future-upgrades.md`. Entries retain their original stable `FUT` ID. IDs are never reused.

## Tracking rules

- Add an entry only after the upgrade is implemented and verified.
- Remove the matching entry from `future-upgrades.md` in the same pull request.
- Record the former tier, completion date, pull request or commit, delivered scope, verification evidence, and the replacement idea added to the future backlog.
- Confirm that no upgrade item exists in both ledgers and no `FUT` ID is assigned to more than one item.
- Do not edit historical completion evidence except to correct a factual error.

## Completed

### FUT-014: Repository classification and policy binding

- Former tier: Tier 1, Release critical
- Completed: 2026-08-10
- Pull request or commit: This pull request
- Delivered: Added strict parsing for GitHub repository metadata and language evidence; deterministic classification across seven dimensions; per-dimension confidence and sanitized evidence; terminal coverage and canonical classification hashes; inventory-state, canonical-value, hash, target, and timestamp validation; privacy-safe binding records; and automatic repository-class and project-type policy selection with repository-specific precedence.
- Verification: Synthetic GitHub fixtures and unit tests cover direct, inferred, mixed, empty, archived, unknown, mismatched, malformed, tampered, stale, redacted, and layered-policy behavior. Ruff, formatting, strict Pyright, pytest, lock validation, and ledger-uniqueness checks pass with at least 94% coverage.
- Replacement idea: Classification overrides and drift diagnostics was added to Tier 2.

### FUT-002: Metadata and community-file audit checks

- Former tier: Tier 1, Release critical
- Completed: 2026-08-10
- Pull request or commit: [PR #11](https://github.com/mickpletcher/github-account-maintainer/pull/11)
- Delivered: Added 14 deterministic GET-only repository checks for metadata and common community files; separate audit-credential identity verification; layered required and optional policy; compliant, noncompliant, observed, unknown, and inaccessible outcomes; explicit terminal coverage; privacy-safe findings; inherited-file detection; and schema-versioned JSON and Markdown repository reports.
- Verification: Synthetic GitHub REST fixtures cover compliant, missing, inherited, inaccessible, malformed, suppressed, redacted, credential-isolated, and GET-only behavior. Ruff, formatting, strict Pyright, pytest, and ledger-uniqueness validation pass with at least 95% coverage.
- Replacement idea: Repository classification and policy binding was added to Tier 1.

### FUT-001: Deterministic policy engine

- Former tier: Tier 1, Release critical
- Completed: 2026-08-10
- Pull request or commit: [PR #9](https://github.com/mickpletcher/github-account-maintainer/pull/9)
- Delivered: Added strict account, repository-class, project-type, repository, and exception policy layers; deterministic precedence; full provenance traces; active, expired, and pending exception handling; canonical SHA-256 policy hashes; and run-report policy fields.
- Verification: Equivalent YAML fixtures resolve to identical results and hashes. Ruff, formatting, strict Pyright, and 81 pytest tests pass with 95.76% coverage.
- Replacement idea: Policy diagnostics and exception hygiene was added to Tier 2.

## Required entry format

```text
### <upgrade ID>: <title>

- Former tier: <tier>
- Completed: <YYYY-MM-DD>
- Pull request or commit: <reference>
- Delivered: <implemented scope>
- Verification: <tests or evidence>
- Replacement idea: <new upgrade ID and title>
```
