# Release 0.1 Read-Only Pilot

This procedure verifies the Release 0.1 audit foundation against synthetic contracts and a live declared GitHub scope. It does not write an audit report to disk and does not call a GitHub mutation endpoint.

## Preconditions

- Run from Windows 11 with PowerShell 7 or later.
- Install Git and `uv`.
- Use a configuration whose `local_data.report_detail` is `minimal`.
- Store valid discovery and audit credentials for the configured GitHub login.
- Give the discovery credential repository Metadata read access.
- Give the audit credential repository Metadata, Contents, Administration, and Code scanning alerts read access.
- Include at least one repository through the configured include and exclude patterns.
- Do not run while another person or automation is intentionally changing the repositories in scope. The two pilot runs must produce the same semantic result.

The pilot rejects full-detail reports, non-serial requests, automatic write operations, automatic merge, destructive operations, fewer than two runs, and more than five runs.

## Windows procedure

From the repository root, replace the configuration path and run:

```powershell
.\scripts\Invoke-Release01Pilot.ps1 `
  -Config "$env:LOCALAPPDATA\GitHubAccountMaintainer\config\config.yaml" `
  -Repeat 2
```

The script performs these steps in order:

1. Installs the exact locked application and development dependencies.
2. Confirms `uv.lock` is current.
3. Runs Ruff lint and formatting validation.
4. Runs strict Pyright validation.
5. Runs every unit and synthetic contract test with the coverage gate.
6. Runs the live account audit twice without saving either detailed report.
7. Requires both live audits to have complete declared coverage.
8. Requires at least one in-scope repository and all 26 checks for every in-scope repository.
9. Validates the JSON schema version and required Markdown report sections in memory.
10. Compares a SHA-256 digest of the two semantic results after removing timestamps and time-derived finding IDs.

## Safe pilot output

The final pilot summary is count-only. It contains:

- pass status;
- repeated-run count;
- discovered, requested, and audited repository counts;
- policy-binding, check-result, coverage-record, and finding counts;
- whether repeated results matched;
- confirmation of minimal detail, GET-only mode, and an empty automatic-write allowlist.

It does not contain account names, repository names, repository IDs, URLs, credential references, policy selectors, finding details, or tokens.

## Result interpretation

- `passed`: The locked build, automated gate, complete live coverage, privacy mode, and repeated semantic result checks passed. Findings are allowed because the pilot verifies audit behavior, not repository compliance.
- Exit code `2`: The live audit was partial, no repository was in scope, a required check or classification was missing, or repeated results differed. Inspect normal local audit output separately. Do not publish private output.
- Exit code `3`: The configuration is missing, invalid, unsafe for the pilot, or uses full report detail.
- A failed Ruff, Pyright, pytest, lock, or dependency command stops the wrapper before the live pilot.

If repositories legitimately changed between the two live runs, wait for activity to stop and rerun. Do not weaken the comparison or switch to full-detail output.

## Linux procedure

Run the equivalent commands from the repository root:

```bash
uv sync --locked --dev
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv run python -m github_account_maintainer.pilot --config /private/path/config.yaml --repeat 2 --format markdown
```

Keep the configuration and any separately generated audit reports outside the repository.

## Latest count-only evidence

The private pilot passed on 2026-08-10 before FUT-005 was added:

- two repeated runs;
- 73 repositories discovered, requested, and audited;
- 1,022 check results and 1,169 coverage records;
- 122 findings;
- matching semantic results;
- minimal detail and GET-only mode enforced;
- zero automatic write operations.

This evidence contains no account name, repository identity, URL, credential reference, policy selector, or finding detail. Rerun the pilot after material audit changes before treating the newer check set as release evidence.

## Gate evidence

The machine-readable mapping from all ten specification criteria to automated evidence is [release/release-0.1-gate.json](release/release-0.1-gate.json). Synthetic end-to-end inputs are in [tests/fixtures/release-0.1-pilot.json](tests/fixtures/release-0.1-pilot.json). CI runs the same locked validation and contract suite on pull requests and pushes to `main`.
