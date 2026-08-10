# Completed Upgrades

This file is the permanent record of upgrades completed from `future-upgrades.md`. Entries retain their original stable `FUT` ID. IDs are never reused.

## Tracking rules

- Add an entry only after the upgrade is implemented and verified.
- Remove the matching entry from `future-upgrades.md` in the same pull request.
- Record the former tier, completion date, pull request or commit, delivered scope, verification evidence, and the replacement idea added to the future backlog.
- Confirm that no upgrade item exists in both ledgers and no `FUT` ID is assigned to more than one item.
- Do not edit historical completion evidence except to correct a factual error.

## Completed

### FUT-001: Deterministic policy engine

- Former tier: Tier 1, Release critical
- Completed: 2026-08-10
- Pull request or commit: This pull request. The final PR reference will be recorded before merge.
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
