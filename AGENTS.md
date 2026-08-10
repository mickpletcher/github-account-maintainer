# Repository Instructions

## Changelog maintenance

- Update `changelog.md` in the same change as every repository modification, including code, documentation, configuration, dependencies, workflows, and maintenance files.
- Record even the smallest change under `Unreleased` using the appropriate Added, Changed, Fixed, Removed, Security, or Documentation heading.
- Do not merge a repository change that has not updated `changelog.md`.

## Assessment maintenance

- Update `assessment.md` in the same change as every repository modification.
- Keep its quick overview, command status, implemented capabilities, safety boundaries, limitations, verification results, and next priorities accurate.
- If a change does not affect behavior, update the review date and latest assessment change to confirm that the assessment was reviewed.
- Do not merge a repository change that has not reviewed and updated `assessment.md`.

## Upgrade tracking

- Track planned work in `future-upgrades.md` using stable `FUT` IDs and three priority tiers.
- When an upgrade is implemented, remove it from `future-upgrades.md` and add it to `completed-upgrades.md` in the same change. Preserve its ID and record the former tier, completion date, pull request or commit, delivered scope, and verification evidence.
- Add at least one new, distinct idea to any tier of `future-upgrades.md` whenever an implemented upgrade is moved to `completed-upgrades.md`. Record the replacement idea in the completed entry.
- Confirm that no upgrade item exists in both ledgers and no `FUT` ID is assigned to more than one item.
- Update `assessment.md` and `changelog.md` in the same change. Update the README when user-facing behavior, commands, or status changes.
- Do not merge an implemented upgrade while the two ledgers are inconsistent.
