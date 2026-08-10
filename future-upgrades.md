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

No pending upgrades. The private live pilot is a release operation documented in `RELEASE-0.1-PILOT.md`, not a repository implementation backlog item.

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

### FUT-015: Classification overrides and drift diagnostics

Add strict lifecycle-threshold settings and explicit flagship, exempt, and maintenance-tier overrides. Report classification changes between runs without allowing low-confidence evidence to silently select a different policy.

### FUT-016: Audit report compatibility and migration tooling

Validate stored report schema compatibility across tool versions and provide deterministic local migrations without weakening hashes, privacy redaction, or terminal coverage semantics.

### FUT-017: Versioned release evidence bundles

Generate a sanitized release evidence bundle containing the gate-manifest version, lockfile hash, test summary, coverage summary, workflow links, and count-only pilot attestation without detailed repository or finding data.

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
