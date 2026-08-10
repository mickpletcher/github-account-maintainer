# Future Upgrades

This file is the prioritized backlog for GitHub Account Maintainer. Every entry has a stable `FUT` ID. IDs are never reused.

## Tracking rules

When an upgrade is implemented:

1. Verify the implementation with tests or other recorded evidence.
2. Remove the entry from this file.
3. Add it to `completed-upgrades.md` with the same ID, its former tier, completion date, pull request or commit, delivered scope, and verification evidence.
4. Add at least one new, distinct upgrade idea to any priority tier in this file in the same pull request.
5. Update `assessment.md` and `changelog.md`. Update the README when user-facing behavior, commands, or status changes.
6. Confirm that no upgrade item exists in both ledgers and no `FUT` ID is assigned to more than one item.

Priority can change as the project develops. Moving an unimplemented item between tiers does not change its ID.

## Tier 1: Release critical

These upgrades directly unblock the read-only Release 0.1 gate.

### FUT-002: Metadata and community-file audit checks

Add read-only checks for repository metadata and required community files. Every check must report explicit coverage and distinguish compliant, noncompliant, unknown, and inaccessible results.

### FUT-003: Account audit command and schema reports

Implement the account-level `audit` command with finding evaluation, complete coverage reporting, schema-versioned JSON, Markdown output, and documented exit-code behavior.

### FUT-004: Release 0.1 pilot verification

Add contract fixtures and a local read-only pilot procedure that verifies the full Release 0.1 gate without mutating GitHub resources or exposing private repository details.

## Tier 2: High value

These upgrades broaden useful audit coverage and make repeated audits reliable.

### FUT-005: Settings and security coverage audit

Audit repository settings and enabled security features using explicit supported, inaccessible, not-applicable, and unverified coverage states.

### FUT-006: Local audit history and finding transitions

Store sanitized audit history in a versioned local SQLite database. Track new, persistent, resolved, and regressed findings with tested migrations.

### FUT-007: Checkpoint and resume support

Add resumable multi-repository audits with deterministic checkpoints, bounded retry behavior, and protection against resuming with a different policy or repository set.

### FUT-008: README evidence and social preview validation

Validate README evidence, repository presentation requirements, and social preview configuration while preserving the project's private-data redaction rules.

### FUT-013: Policy diagnostics and exception hygiene

Report unused policy layers, redundant overrides, unmatched selectors, and exceptions that are pending, expired, or nearing expiration without changing the resolved policy or suppressing findings.

## Tier 3: Strategic

These upgrades prepare the project for controlled remediation, deeper assurance, and unattended operation after earlier safety gates pass.

### FUT-009: Immutable remediation plans and rollback

Create immutable plans, explicit approvals, pre-change snapshots, and rollback records before any GitHub write operation is introduced.

### FUT-010: Advanced supply-chain audits

Audit access, rulesets, Actions, dependencies, releases, software bills of materials, and attestations with permission-aware evidence and coverage reporting.

### FUT-011: Coverage-aware dashboard and scoring

Generate a local HTML dashboard whose scores account for incomplete or inaccessible coverage and never present missing evidence as compliance.

### FUT-012: Scheduled execution and recovery

Add scheduler integration, single-instance locks, cooldowns, notifications, rate-limit handling, interruption recovery, and bounded retention for unattended audits.
