# GitHub Account Maintainer Project Specification

**Status:** Approved scope, ready for implementation planning  
**Owner:** Mick Pletcher  
**Last updated:** 2026-08-10  
**Repository name:** `github-account-maintainer`  

## 1. Product Summary

GitHub Account Maintainer is a policy-driven automation system that audits and maintains an entire GitHub account. It keeps profile pins, repository settings, security controls, About metadata, documentation, social-preview graphics, dependencies, CI workflows, releases, backups, and repository lifecycle state aligned with a configurable standard.

The system is audit-first and fail-closed. It may automatically apply only changes explicitly classified as safe by policy. Repository content changes are proposed through pull requests. Destructive, access-related, billable, or potentially breaking changes require explicit approval and are never silently applied.

### Product description

> Policy-driven automation that audits and maintains a GitHub account, synchronizes profile pins, standardizes repository settings and security, and keeps metadata and documentation accurate.

### Tagline

> Automated maintenance and governance for your entire GitHub account.

## 2. Goals

1. Maintain a complete inventory of repositories accessible to the configured GitHub account.
2. Detect configuration, security, documentation, dependency, CI, release, and profile drift.
3. Apply safe, reversible corrections automatically when policy permits.
4. Propose repository-file changes through clear, evidence-backed pull requests.
5. Require approval for risky or potentially disruptive changes.
6. Keep the GitHub profile and repository presentation accurate and current.
7. Provide account-wide health scoring, reports, history, and rollback information.
8. Back up repository content and relevant GitHub metadata.
9. Bootstrap newly created repositories with the correct baseline.
10. Remain extensible as GitHub adds or changes features.

## 3. Non-Goals

GitHub Account Maintainer is not an unrestricted autonomous coding agent. The following remain outside the core scope:

- Implementing new product features.
- Refactoring application code solely for style or architecture.
- Automatically merging generated code or documentation changes.
- Automatically deleting repositories, releases, branches, tags, credentials, collaborators, deploy keys, or webhooks.
- Automatically changing repository visibility, ownership, or default branches.
- Automatically archiving repositories or dismissing security alerts.
- General issue or project management beyond maintenance-related findings.

These capabilities may be integrated later through separate, explicitly authorized tools, but they must not bypass GitHub Account Maintainer's approval boundaries.

## 4. Design Principles

- **Audit first:** Every write begins with a read, comparison, and evidence-backed plan.
- **Dry-run by default:** A normal invocation performs no external mutations.
- **Idempotent:** Repeated runs against a compliant account create no changes or duplicate pull requests.
- **Fail closed:** Unknown API responses, unsupported plans, authentication failures, or UI changes stop remediation.
- **Least privilege:** Audit and remediation credentials are separated whenever practical.
- **Evidence over inference:** Documentation claims must be supported by repository content or flagged for review.
- **Reversible:** Settings changes retain before-and-after snapshots and rollback instructions.
- **Low noise:** One consolidated maintenance pull request per repository, with cooldowns and duplicate detection.
- **Policy driven:** Global defaults, repository-class policies, and per-repository exceptions are version controlled.
- **Private by default:** Private repository content is not sent to an external AI provider without explicit configuration.

## 5. Repository Discovery and Classification

GitHub Account Maintainer must enumerate all repositories that the authenticated account owns and optionally repositories where it has administrative access.

Each repository is classified using the following dimensions:

- Public, private, or internal.
- Active, dormant, abandoned candidate, or archived.
- Source repository, fork, template, mirror, or empty repository.
- Personal-account or organization-owned.
- Primary project type, such as Python, PowerShell, Node.js, MCP server, documentation, configuration, web application, or mixed.
- Deployment type, such as library, CLI, service, desktop application, GitHub Pages site, or infrastructure repository.
- Maintenance tier: flagship, active, standard, experimental, legacy, or exempt.

### Default scope rules

- Owned repositories are included in full audits.
- Organization or contributed repositories are changed only when the account has administrative permission and policy enables them.
- Forks and archived repositories are audited but not modified by default.
- Empty repositories receive a classification report and bootstrap recommendation.
- Private repositories receive deterministic local audits; external AI analysis is disabled unless explicitly allowed.

## 6. Policy Inheritance

Policy is resolved in this order, with later levels overriding earlier levels:

1. Built-in safe defaults.
2. Account-wide policy.
3. Repository-class policy.
4. Language or project-type policy.
5. Repository-specific overrides.
6. Time-limited exceptions.

Exceptions must contain a reason, creator, creation date, and optional expiration date. Expired exceptions become findings.

## 7. Operating Modes

GitHub Account Maintainer exposes the following operating modes:

| Mode | Purpose | External writes |
| --- | --- | --- |
| `audit` | Inventory and evaluate the account | None |
| `plan` | Produce exact proposed changes and diffs | None |
| `apply-safe` | Apply policy-approved, reversible settings changes | Safe writes only |
| `open-prs` | Create or update consolidated maintenance pull requests | Branch and PR writes |
| `apply-approved` | Apply previously approved sensitive changes | Approved writes only |
| `pins-sync` | Synchronize profile pins through the local UI adapter | Profile-pin changes |
| `previews-sync` | Upload merged social-preview assets through the local UI adapter | Social-preview changes |
| `backup` | Back up repositories and metadata | Backup-destination writes |
| `bootstrap` | Apply the baseline to a new repository | Policy-controlled writes |
| `rollback` | Restore a captured settings snapshot where supported | Explicitly selected writes |

## 8. Remediation Safety Matrix

| Change category | Default handling |
| --- | --- |
| Inventory, scoring, and reports | Automatic, read-only |
| Clearly safe metadata and nonbreaking settings | Automatic only after policy enables the rule |
| README, documentation, templates, configuration, graphics, and workflow files | Pull request |
| Security feature enablement | Explicit policy approval and plan/feature support checks |
| Actions permission changes | Approval required unless an exact safe baseline was previously approved |
| Rulesets and branch protection | Approval required |
| Collaborators, GitHub Apps, deploy keys, webhooks, and environment access | Report only by default |
| Visibility, ownership transfer, archiving, or default-branch changes | Report and manual approval; never unattended |
| Repository, release, branch, tag, credential, or package deletion | Never automatic |
| Security-alert dismissal | Never automatic |
| Profile pins and social-preview assignment | Local browser adapter with dry-run and verification |

## 9. Profile Maintenance

### 9.1 Profile pins

GitHub Account Maintainer must:

- Read the current `pinnedItems` and eligible `pinnableItems` through GitHub GraphQL.
- Consider repository items only unless policy enables gists.
- Rank eligible repositories by star count.
- Exclude private, archived, forked, or explicitly ignored repositories by default.
- Allow contributed and organization repositories when GitHub identifies them as pinnable.
- Support protected pins, required pins, exclusions, and manually assigned slots.
- Preserve currently pinned repositories during star-count ties to prevent churn.
- Use a stable secondary tie-breaker, followed by repository name.
- Limit the result to GitHub's maximum of six profile items.
- Generate an audit report showing the current and desired order.
- Apply changes through a local Playwright adapter using a dedicated signed-in browser profile.
- Stop without changes when GitHub's page structure or verification expectations differ from the tested adapter.

### 9.2 Profile README and public profile

GitHub Account Maintainer must audit:

- The special profile repository and profile `README.md`.
- Bio accuracy and length.
- Public website and social links.
- Broken or outdated profile links.
- Flagship-project references.
- Technologies, roles, and descriptions that no longer match the account's current work.

Profile README changes are submitted through a pull request. Profile-field changes require explicit UI or API approval.

## 10. Repository About and Discoverability

For every eligible repository, GitHub Account Maintainer audits and maintains:

- Repository description.
- Homepage or project URL.
- Topics.
- Primary language and project classification.
- Visibility and archive state, as report-only sensitive fields.
- Social-preview asset and assignment.
- Repository naming consistency.
- GitHub Pages configuration and custom-domain health when present.
- Sponsor, funding, citation, and support links when relevant.

Generated descriptions and topics must be grounded in the repository's actual content. Low-confidence suggestions are reported rather than applied.

## 11. Repository Settings

GitHub Account Maintainer audits relevant settings, including:

- Merge-commit, squash-merge, and rebase-merge policies.
- Automatic deletion of merged head branches.
- Auto-merge availability.
- Web-commit signoff policy.
- Issues, Discussions, Projects, Wiki, and Pages enablement.
- Template-repository state.
- Fork policy where supported.
- Default branch and branch naming, report-only unless explicitly approved.
- Immutable releases where supported.
- Private vulnerability reporting.
- Push policy and destructive multi-ref push limits where supported.
- Autolinks and repository-specific integrations.

Settings are compared against the resolved repository-class policy rather than one universal baseline.

## 12. Security and Access Governance

### 12.1 Security features

GitHub Account Maintainer audits availability and state for:

- Dependency graph.
- Dependabot alerts.
- Dependabot security updates.
- Dependabot version-update configuration.
- Secret scanning.
- Push protection.
- Code scanning and CodeQL default setup.
- Private vulnerability reporting.
- Security advisories.
- Artifact attestations and provenance.
- Rulesets and branch protection.
- Required status checks and review requirements.
- Force-push and branch-deletion protections.

The system must distinguish unsupported, unavailable-by-plan, inherited, disabled, and misconfigured states. It must never represent an unavailable feature as a failure.

### 12.2 Access inventory

GitHub Account Maintainer audits:

- Collaborators and permission levels.
- Organization teams and ownership continuity where accessible.
- Installed GitHub Apps and integrations.
- OAuth applications where accessible.
- Repository deploy keys.
- Repository webhooks.
- Environment reviewers and deployment protections.
- Repository and environment secret names and last-known use metadata where exposed; secret values are never read.
- Account SSH and signing keys.
- Personal access tokens or credentials where GitHub exposes manageable metadata.
- Stale, unverified, unexpectedly writable, or overly broad access.

Access changes are report-only unless the user explicitly selects and approves a target. GitHub Account Maintainer never bulk-removes access.

### 12.3 Account continuity

The audit should remind the user to maintain:

- A repository successor for personal repositories.
- More than one owner for important organizations.
- Current recovery methods, passkeys, and two-factor authentication.
- Securely stored recovery codes outside the application.

GitHub Account Maintainer must not store recovery codes or authentication secrets in its database.

## 13. Branches, Rulesets, and Pull Requests

The system audits:

- Default-branch rulesets.
- Protection against force pushes and deletion.
- Required reviews and stale-review dismissal.
- Required status checks and whether referenced checks still exist.
- Required signed commits where appropriate.
- Bypass actors and overly broad exceptions.
- Long-lived, merged, abandoned, or unprotected branches.
- Duplicate or obsolete rulesets.
- Pull requests that have been stale beyond policy thresholds.

Branch deletion, ruleset replacement, or default-branch changes are never unattended.

## 14. GitHub Actions and CI Health

GitHub Account Maintainer audits:

- Whether Actions is enabled appropriately.
- Allowed-action policy and reusable-workflow restrictions.
- Default `GITHUB_TOKEN` permissions.
- Whether Actions may create or approve pull requests.
- Workflow-level and job-level `permissions` declarations.
- Third-party actions not pinned to a full commit SHA.
- Deprecated or obsolete action versions.
- Failing, cancelled, disabled, or chronically flaky workflows.
- Missing lint, test, build, security, or release validation where appropriate.
- Artifact and log retention.
- Cache age and excessive cache usage where exposed.
- Fork pull-request approval policy.
- Self-hosted runner exposure and scope where applicable.
- Workflow references to missing secrets, environments, scripts, or branches.

Workflow-file corrections are pull-request changes. Permission-policy changes require approval unless already covered by an approved baseline.

## 15. Dependency and Supply-Chain Health

GitHub Account Maintainer audits:

- Dependency manifests and lockfiles.
- Whether lockfiles match manifests when deterministically testable.
- Known Dependabot alerts and severity.
- Dependabot configuration coverage and schedule.
- Outdated dependencies when a supported package manager can report them.
- Direct and transitive dependency risk where GitHub exposes it.
- Dependency license conflicts or missing license information.
- Stale runtime or language versions.
- Container base-image freshness and digest pinning where applicable.
- Exportable SPDX software bills of materials.
- Release checksums, signatures, provenance, and artifact attestations.

Dependency upgrades and configuration changes are proposed through pull requests. Security alerts are never automatically dismissed.

## 16. README and Documentation Accuracy

GitHub Account Maintainer must evaluate the current repository rather than rewriting a README from its existing prose alone.

### Evidence sources

- Source entry points, public modules, and CLI definitions.
- Package manifests and dependency files.
- Build, lint, test, and release scripts.
- GitHub Actions workflows.
- Configuration files and example configuration.
- Environment-variable references.
- Dockerfiles, compose files, deployment manifests, and service definitions.
- Existing docs, examples, screenshots, and changelogs.
- Generated command help when safe and available.
- Tests that demonstrate supported behavior.

### README checks

- Project purpose and value.
- Implemented feature list.
- Features claimed but not implemented.
- Implemented features missing from documentation.
- Installation and prerequisites.
- Exact commands, arguments, paths, ports, and filenames.
- Configuration keys and environment variables.
- Platform compatibility.
- Usage examples.
- Security and privacy notes.
- Testing and development instructions.
- Support and contribution paths.
- License and maintainer information.
- Links, badges, anchors, images, and referenced files.
- Screenshots that no longer match the product.
- Stale status or roadmap claims.

### README remediation rules

- Preserve the project's voice and manually curated sections.
- Make only claims supported by repository evidence.
- Flag uncertainty rather than inventing information.
- Include an evidence summary in the maintenance pull request.
- Run link, Markdown, spelling, and command validation where configured.
- Never commit directly to the default branch.

## 17. Social-Preview Graphics

GitHub Account Maintainer treats the repository social preview as a maintained build artifact.

### Asset rules

- Preserve a configured existing path when present.
- Default new assets to `.github/social-preview.png`.
- Use a deterministic, versioned template renderer.
- Render at 1280 by 640 pixels.
- Produce PNG or JPEG output below GitHub's 1 MB limit.
- Include the repository name, grounded description, primary language or category, owner branding, and optional project icon.
- Provide accessible contrast and safe text margins.
- Support account-wide themes, repository-class themes, and repository-specific overrides.
- Support protected custom artwork that must never be overwritten.

### Regeneration triggers

- Missing asset.
- Invalid dimensions, format, or file size.
- Repository rename.
- Description or project-category change.
- Branding or template-version change.
- Primary language change when the selected theme displays it.
- Current asset inputs no longer match the repository.

The generated asset is added to the repository's consolidated maintenance pull request. After the pull request merges, a local Playwright adapter verifies and uploads the asset under the repository's Social preview setting. Content hashes prevent unnecessary regeneration and upload.

## 18. Community Health and Repository Files

GitHub Account Maintainer audits the presence, relevance, and consistency of:

- `LICENSE`.
- `SECURITY.md`.
- `CONTRIBUTING.md`.
- `CODE_OF_CONDUCT.md` where appropriate.
- `SUPPORT.md`.
- `FUNDING.yml` where appropriate.
- `CITATION.cff` where appropriate.
- Issue templates or issue forms.
- Pull-request template.
- `CODEOWNERS`.
- `.gitignore`.
- `.gitattributes`.
- `.editorconfig`.
- Example environment or configuration files without secrets.
- Changelog and release documentation.
- Dependabot configuration.

Files are not added mechanically to every repository. Applicability is determined by repository class and policy.

## 19. Release Hygiene

GitHub Account Maintainer audits:

- Tag and release consistency.
- Semantic-version patterns where adopted.
- Draft, prerelease, and latest-release state.
- Release notes and changelog consistency.
- Broken or missing release assets.
- Checksums and signatures where policy requires them.
- SBOM and provenance availability.
- Artifact attestations and verification.
- Immutable-release settings where supported.
- Stale prereleases and abandoned drafts.

Release deletion, publication, or mutation requires explicit approval. Proposed changelog or release-workflow changes use pull requests.

## 20. Repository Lifecycle Management

GitHub Account Maintainer identifies:

- Empty repositories.
- Duplicate or superseded repositories.
- Repositories with no activity beyond configured thresholds.
- Repositories whose README claims active status despite abandonment.
- Oversized repositories and unexpectedly large objects.
- Large binary files that should use Git LFS or release assets.
- Stale branches and tags.
- Open issues and pull requests beyond configured age thresholds.
- Forks that have diverged or fallen behind upstream.
- Repositories that may be ready to archive.
- Archived repositories whose metadata or README does not explain their status.

Lifecycle findings remain recommendations. No repository, branch, tag, issue, or pull request is deleted, closed, or archived automatically.

## 21. Backup and Recovery

GitHub Account Maintainer provides recoverable, verified backups of:

- Git repositories, including all refs, through mirror clones.
- Wikis when present.
- Releases and downloadable release assets.
- Issues, pull requests, comments, labels, milestones, and discussions where APIs permit export.
- Repository metadata, topics, settings, rulesets, hooks metadata, and access inventory.
- GitHub Account Maintainer policy, findings, approvals, and settings snapshots.
- Optional GitHub user migration archives when separately authorized.

### Backup rules

- Backup destinations are configurable and outside the source repository.
- Sensitive metadata and private repositories are encrypted at rest.
- Backup manifests contain checksums and timestamps.
- Scheduled verification confirms that mirrors and archives can be read.
- Retention and pruning are explicit policy settings.
- User migration archives are downloaded promptly because GitHub makes them available only temporarily.
- User migrations requiring broad classic-token permissions are optional and disabled by default.
- Restore procedures are tested without overwriting live repositories.

## 22. New-Repository Bootstrap

GitHub Account Maintainer detects newly created repositories through scheduled inventory comparison or optional webhooks.

Bootstrap may:

- Classify the project.
- Apply safe repository settings.
- Add topics and an evidence-based description.
- Enable approved security features.
- Create the initial ruleset plan.
- Open a pull request with applicable community-health files.
- Create or improve the README.
- Generate the social-preview asset.
- Add baseline lint, test, or release workflows when policy and project evidence support them.
- Add the repository to backup coverage.

Bootstrap must not overwrite existing files or presume that an empty repository is ready for public release.

## 23. Cost, Storage, and Operational Health

GitHub Account Maintainer reports:

- Repository size trends.
- Git LFS usage where visible.
- Actions artifact and log retention.
- Actions cache inventory and age where visible.
- Workflow run frequency and recurring failures.
- Package and release-asset storage where visible.
- Excessive generated files committed to source control.
- Backup size and retention trends.

Cost-affecting changes require approval.

## 24. Reporting and Dashboard

Each run produces machine-readable and human-readable results:

- Account summary.
- Per-repository health score.
- Category scores for metadata, documentation, security, access, CI, dependencies, releases, and backup.
- Findings grouped by severity and remediation type.
- Exact current and desired values.
- Evidence and official GitHub links where relevant.
- Proposed API operations or file diffs.
- Approval requirements.
- Applied-change history.
- Rollback information.
- Suppressed findings and exception-expiration dates.

Supported output formats:

- JSON for automation.
- Markdown for GitHub issues and review.
- HTML for a local dashboard.
- Optional CSV for inventory export.

### Finding model

Every finding contains:

- Stable check ID.
- Repository and category.
- Severity: informational, low, medium, high, or critical.
- Current state.
- Desired state.
- Evidence.
- Confidence.
- Remediation class: automatic, pull request, approval required, or manual only.
- Documentation link.
- First seen, last seen, and resolved timestamps.
- Exception state and expiration.

## 25. Notifications and Noise Control

GitHub Account Maintainer notifies only when policy requires action.

- No notification for a clean run unless a periodic summary is configured.
- Findings are deduplicated across runs.
- Repeated unresolved findings observe a notification cooldown.
- Critical security or backup failures may bypass cooldowns.
- One maintenance pull request is maintained per repository.
- Existing Steward branches and pull requests are updated rather than duplicated.
- Pull requests are labeled consistently and contain a generated/managed marker.
- Notifications may use email, GitHub issues, or other configured adapters.

## 26. Scheduling and Event Triggers

Recommended defaults:

- Daily profile-pin audit.
- Weekly full-account audit.
- Weekly backup verification.
- Monthly dependency, access, lifecycle, and release deep scan.
- Immediate or scheduled bootstrap after detecting a new repository.
- Event-triggered audit after repository rename, visibility change, default-branch change, or major release when webhooks are configured.

All schedules are configurable, timezone aware, and protected from overlapping runs.

## 27. Authentication and Credential Handling

### Recommended authentication model

- Use a GitHub App for long-term account-wide repository API access when practical.
- Separate read-only audit credentials from write-enabled remediation credentials.
- Use short-lived installation tokens where possible.
- Permit a fine-grained personal access token for MVP development with documented permissions.
- Require separate explicit authorization for capabilities that need a classic personal access token.
- Store secrets in the operating system credential store or an approved secrets manager.
- Store the Playwright browser profile outside the repository and encrypt or protect it using operating-system controls.

The repository must never contain tokens, cookies, private keys, recovery codes, or unredacted secret values.

### Permission preflight

Before every operation, GitHub Account Maintainer confirms that the credential has the required effective permission. Missing permissions produce actionable findings rather than partial, misleading results.

## 28. Privacy and AI Use

- Deterministic checks run locally whenever practical.
- Public-repository AI analysis may use a configured provider.
- Private-repository AI analysis is disabled by default.
- A local model can be selected for private README and metadata analysis.
- External AI use requires an explicit provider, model, data-scope, and retention policy.
- Prompts and responses must not contain secrets or credential values.
- Generated content retains evidence references and confidence scores.
- AI suggestions cannot directly alter default branches or merge themselves.

## 29. Extensibility

Checks and remediators use a plugin contract containing:

- Check metadata and stable ID.
- Supported repository classes.
- Required GitHub permissions.
- Data collectors.
- Evaluation logic.
- Evidence output.
- Remediation type.
- Optional planner and applier.
- Verification and rollback logic.

New GitHub features can be added as plugins without changing the core inventory, policy, reporting, approval, or scheduling engine.

## 30. Proposed Technical Architecture

### Core stack

- Python 3.12 or later.
- Typer for the CLI.
- Pydantic for policy, finding, and API models.
- `httpx` for GitHub REST and GraphQL access.
- SQLite for local state, findings, approvals, run history, and content hashes.
- Jinja2 plus a deterministic graphics renderer for reports and social previews.
- Playwright for GitHub features without supported write APIs.
- Structured JSON logging with redaction.

### Major modules

- `inventory`: accounts, organizations, repositories, and classification.
- `policy`: inheritance, overrides, exceptions, and validation.
- `github_api`: REST, GraphQL, pagination, caching, and rate limits.
- `checks`: metadata, security, access, CI, dependencies, docs, releases, lifecycle, and backup.
- `remediation`: planners, safe appliers, pull-request builders, approvals, and rollback.
- `readme`: evidence collection and documentation reconciliation.
- `social_preview`: deterministic generation, validation, hashing, and theme management.
- `browser`: fail-closed profile-pin and social-preview upload adapters.
- `backup`: mirrors, metadata export, manifests, encryption, verification, and restore testing.
- `reporting`: JSON, Markdown, HTML, CSV, scoring, and dashboard.
- `scheduler`: Windows Task Scheduler, cron, and optional webhook processing.
- `notifications`: GitHub issues, email, and optional external adapters.
- `state`: runs, findings, exceptions, approvals, snapshots, hashes, and migrations.

## 31. Proposed Command Surface

```text
github-account-maintainer init
github-account-maintainer auth check
github-account-maintainer inventory
github-account-maintainer audit [--repo OWNER/REPO] [--deep]
github-account-maintainer plan [--repo OWNER/REPO]
github-account-maintainer apply-safe [--repo OWNER/REPO]
github-account-maintainer open-prs [--repo OWNER/REPO]
github-account-maintainer approvals list
github-account-maintainer approvals approve FINDING_ID
github-account-maintainer apply-approved
github-account-maintainer pins audit
github-account-maintainer pins sync
github-account-maintainer previews audit
github-account-maintainer previews generate
github-account-maintainer previews sync
github-account-maintainer backup run
github-account-maintainer backup verify
github-account-maintainer bootstrap OWNER/REPO
github-account-maintainer report --format html
github-account-maintainer rollback SNAPSHOT_ID
github-account-maintainer schedule install
```

Every mutating command supports `--dry-run`, and dry-run remains the default until `--apply` or an equivalent explicit confirmation is supplied.

## 32. Configuration Outline

```yaml
account:
  login: mickpletcher
  include_private: true
  include_owned: true
  include_administered: false

safety:
  dry_run_default: true
  auto_merge: false
  allow_destructive_operations: false
  require_approval_for_sensitive_settings: true

repositories:
  modify_archived: false
  modify_forks: false
  include_patterns: ["*"]
  exclude_patterns: []

pins:
  mode: top_stars
  count: 6
  include_contributed: true
  exclude_archived: true
  exclude_forks: true
  preserve_ties: true
  protected: []
  excluded: []

readme:
  enabled: true
  remediation: pull_request
  preserve_manual_sections: true
  validate_links: true
  private_ai_provider: disabled

social_preview:
  enabled: true
  default_path: .github/social-preview.png
  width: 1280
  height: 640
  max_bytes: 1000000
  remediation: pull_request_then_browser_upload
  protected_repositories: []

security:
  audit_dependabot: true
  audit_secret_scanning: true
  audit_push_protection: true
  audit_code_scanning: true
  audit_private_vulnerability_reporting: true
  never_dismiss_alerts: true

backup:
  enabled: true
  encrypt_private_data: true
  include_releases: true
  include_metadata: true
  verify_after_backup: true

notifications:
  clean_run_summary: false
  maintenance_pr_label: github-account-maintainer
  cooldown_hours: 168
```

The final schema must validate incompatible combinations and warn about permissions, plan limitations, or missing destinations before a run begins.

## 33. State and Audit History

The state database records:

- Discovered accounts and repositories.
- Repository classification and resolved policy version.
- Runs and checkpoints.
- Findings and status transitions.
- Exceptions and expirations.
- Approval decisions and actor.
- Settings snapshots and rollback operations.
- Open maintenance branches and pull requests.
- Social-preview input and output hashes.
- Backup manifests and verification results.
- Notification cooldowns.

Secrets and raw private repository content are not stored in the state database.

## 34. Reliability Requirements

- Paginate every GitHub collection correctly.
- Respect primary and secondary GitHub rate limits.
- Use conditional requests and caching where safe.
- Back off with jitter for transient failures.
- Resume account-wide runs from durable checkpoints.
- Limit concurrency per API category.
- Serialize writes to the same repository or path.
- Detect concurrent repository changes before applying a plan.
- Re-read and verify every settings mutation.
- Verify pull-request branch state before updating it.
- Redact credentials, cookies, secrets, authorization headers, and signed URLs from logs.
- Produce a partial-run report that clearly distinguishes failed, skipped, unsupported, and unaudited checks.

## 35. Testing Strategy

### Unit tests

- Policy inheritance and exceptions.
- Repository classification.
- Pin ranking and tie stability.
- Findings, severity, and scoring.
- README evidence extraction.
- Social-preview rendering and size validation.
- Redaction.
- Settings diff and rollback-plan generation.

### Contract tests

- Recorded GitHub REST and GraphQL response fixtures.
- Pagination and rate-limit behavior.
- Permission and plan-dependent feature responses.
- Content update conflicts.
- Pull-request deduplication.

### Integration tests

- Dedicated test account and repositories.
- Safe metadata update and verification.
- Maintenance branch and pull-request lifecycle.
- Backup and restore verification.
- GitHub App and fine-grained-token authentication.

### Browser-adapter tests

- Pin audit and reorder against a disposable test profile.
- Social-preview upload against a disposable test repository.
- Detection of changed GitHub UI selectors.
- Failure without mutation when verification is uncertain.

Browser adapters must not be tested against production repositories without an explicit test target.

## 36. Acceptance Criteria

GitHub Account Maintainer is ready for an initial production run when it can:

1. Inventory every repository in the configured account without missing pagination.
2. Classify repositories and resolve policy deterministically.
3. Produce a complete read-only account audit and health report.
4. Show exact current and desired values for supported settings.
5. Apply a safe metadata or settings correction and verify the result.
6. Create one consolidated, evidence-backed maintenance pull request for a test repository.
7. Detect and propose an accurate README update without unsupported claims.
8. Generate a valid social-preview asset and avoid regeneration when inputs are unchanged.
9. Compute the desired six profile pins with stable tie handling.
10. Back up and verify a test repository and its metadata.
11. Resume a deliberately interrupted multi-repository run.
12. Demonstrate that destructive and access-related operations cannot run unattended.
13. Redact secrets from logs and reports.
14. Pass unit, contract, integration, and browser-adapter test suites.

## 37. Delivery Phases

### Phase 1: Audit foundation

- Authentication and permission preflight.
- Inventory and repository classification.
- Policy engine and exceptions.
- Read-only metadata, settings, security, README, social-preview, and community-health audits.
- JSON and Markdown reports.

### Phase 2: Safe remediation and pull requests

- Settings planner and safe applier.
- Before-and-after snapshots.
- Consolidated maintenance branches and pull requests.
- README and documentation reconciliation.
- Social-preview generation.

### Phase 3: Advanced security, CI, and supply chain

- Access governance.
- Rulesets and Actions audits.
- Dependency and release health.
- SBOM and attestation verification.
- HTML dashboard and scoring.

### Phase 4: Profile and UI adapters

- Profile pin synchronization.
- Social-preview assignment.
- Profile-field audit and approved updates.

### Phase 5: Backup, lifecycle, and bootstrap

- Mirror and metadata backup.
- Verification and restore testing.
- Lifecycle recommendations.
- New-repository detection and baseline bootstrap.

### Phase 6: Scheduling and production hardening

- Windows Task Scheduler and cron support.
- Optional webhook processing.
- Notifications and cooldowns.
- Checkpoint/resume, performance, rate-limit, and failure hardening.
- End-to-end production-readiness review.

## 38. Known Constraints

- GitHub exposes profile pins through GraphQL but does not document a public write mutation for personal profile pins.
- GitHub documents social-preview assignment through repository settings rather than a public upload API.
- Browser automation is therefore isolated, local, optional, and fail-closed.
- Feature availability varies by repository visibility, ownership, GitHub plan, and organization policy.
- Some account credential and security metadata is intentionally unavailable through APIs.
- GitHub user migration archives require distinct authorization and remain downloadable for a limited period.
- Automated README review cannot prove undocumented intent; uncertain changes require human review.

## 39. Official GitHub References

- Repository API: <https://docs.github.com/en/rest/repos/repos>
- Repository topics: <https://docs.github.com/en/rest/repos/repos#replace-all-repository-topics>
- Community-profile metrics: <https://docs.github.com/en/rest/metrics/community>
- Repository rulesets: <https://docs.github.com/en/rest/repos/rules>
- Actions permissions and retention: <https://docs.github.com/en/rest/actions/permissions>
- Repository contents: <https://docs.github.com/en/rest/repos/contents>
- Secret scanning: <https://docs.github.com/en/rest/secret-scanning/secret-scanning>
- Dependabot alerts: <https://docs.github.com/en/rest/dependabot/alerts>
- SBOM export: <https://docs.github.com/en/rest/dependency-graph/sboms>
- Artifact attestations: <https://docs.github.com/en/rest/repos/attestations>
- User migrations: <https://docs.github.com/en/rest/migrations/users>
- SSH key API: <https://docs.github.com/en/rest/users/keys>
- Profile pins: <https://docs.github.com/en/account-and-profile/how-tos/profile-customization/pinning-items-to-your-profile>
- Social previews: <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview>
- README guidance: <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes>
- Ownership continuity: <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/maintaining-ownership-continuity-of-your-personal-accounts-repositories>

## 40. Approved Scope Checklist

- [x] Profile pins based on top-starred eligible repositories.
- [x] Profile README, bio, and link maintenance.
- [x] Repository discovery and classification.
- [x] About metadata, description, homepage, and topics.
- [x] Social-preview file generation and GitHub assignment.
- [x] Repository settings and features.
- [x] Security features and alerts.
- [x] Access governance and credential inventory.
- [x] Rulesets and branch protection.
- [x] GitHub Actions security, health, and retention.
- [x] Dependency and supply-chain health.
- [x] Evidence-based README and documentation maintenance.
- [x] Community-health files.
- [x] Release hygiene, SBOMs, and attestations.
- [x] Repository lifecycle recommendations.
- [x] Backup, verification, and recovery.
- [x] New-repository bootstrap.
- [x] Cost and storage monitoring.
- [x] Ownership continuity reminders.
- [x] Reports, dashboard, scoring, history, and rollback.
- [x] Notifications, cooldowns, and PR-noise controls.
- [x] Scheduling and optional event-driven runs.
- [x] Privacy controls and local-model support.
- [x] Plugin-style extensibility.
