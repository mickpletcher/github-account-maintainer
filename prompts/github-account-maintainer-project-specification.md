# GitHub Account Maintainer Project Specification

**Status:** Approved product scope; Release 0.1 live pilot passed; FUT-005 read-only settings and security audit implemented
**Owner:** Mick Pletcher  
**Last updated:** 2026-08-10  
**Repository name:** `github-account-maintainer`  

## 1. Product Summary

GitHub Account Maintainer is a policy-driven automation system that audits and maintains GitHub resources within explicitly declared API, credential, repository, and plan coverage. It keeps profile pins, repository settings, security controls, About metadata, documentation, social-preview graphics, dependencies, CI workflows, releases, backups, and repository lifecycle state aligned with a configurable standard.

The system is audit-first and fail-closed. It may automatically apply only changes explicitly classified as safe by policy. Repository content changes are proposed through pull requests. Destructive, access-related, billable, or potentially breaking changes require explicit approval and are never silently applied.

The current implementation is GET-only. It runs 26 checks per in-scope repository across metadata, community files, default-branch controls, Actions permissions, and supported security features. The 2026-08-10 count-only pilot passed two matching audits across 73 repositories with zero writes. FUT-005 expanded the check set after that pilot and requires a new repeated pilot with the documented read-only permissions.

### Product description

> Policy-driven automation that audits and maintains a GitHub account, synchronizes profile pins, standardizes repository settings and security, and keeps metadata and documentation accurate.

### Tagline

> Automated maintenance and governance across your accessible GitHub account resources.

## 2. Goals

1. Maintain a complete inventory of repositories visible to the configured discovery credential and report the limits of that coverage.
2. Detect configuration, security, documentation, dependency, CI, release, and profile drift.
3. Apply explicitly allowlisted, verified corrections when policy and an immutable plan permit.
4. Propose repository-file changes through clear, evidence-backed pull requests.
5. Require approval for risky or potentially disruptive changes.
6. Keep the GitHub profile and repository presentation accurate and current.
7. Provide coverage-aware health scoring, reports, history, and best-effort rollback information for supported operations.
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
- **Coverage is explicit:** Every run reports which resources and checks were audited, unsupported, inaccessible, skipped, or not requested.
- **Evidence over inference:** Documentation claims must be supported by repository content or flagged for review.
- **Verified and recoverable:** Supported settings changes retain before-and-after snapshots, verification results, and best-effort rollback instructions. A snapshot is never represented as a guarantee that GitHub will accept a later rollback.
- **Low noise:** One consolidated maintenance pull request per repository, with cooldowns and duplicate detection.
- **Policy driven:** Global defaults, repository-class policies, and per-repository exceptions are version controlled.
- **Private by default:** Private repository content is not sent to an external AI provider without explicit configuration.
- **Untrusted input:** Repository files, API text, issue content, workflow output, and generated content are data, not instructions. They cannot expand permissions, change policy, approve plans, or trigger writes.

## 5. Repository Discovery and Classification

GitHub Account Maintainer must enumerate all repositories returned by the configured user-scoped discovery credential. Discovery uses GitHub's authenticated-user repository listing with explicit affiliations and pagination. GitHub App installation tokens are used only for repositories granted to the installation and must not be treated as proof of account-wide completeness.

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

### Discovery and coverage contract

Each inventory records:

- Authenticated account identity and GitHub host.
- Discovery credential type without storing the credential value.
- Requested affiliations, visibility, organizations, include patterns, and exclude patterns.
- Every pagination cursor or page boundary required to establish completeness.
- Repository ownership, effective viewer permission, and whether a configured execution credential can access the repository.
- Collection start and completion timestamps and any checkpoint used to resume.

Every repository and check receives exactly one coverage state: `audited`, `supported`, `unsupported`, `unavailable_by_plan`, `inherited`, `inaccessible`, `not_applicable`, `unverified`, `skipped_by_policy`, `not_requested`, or `failed`. A run is complete only when every requested repository and check has a terminal coverage state. Requested evidence that is `inaccessible`, `unverified`, or `failed` makes the run partial. The product must say "complete within declared coverage" rather than "complete account audit."

## 6. Policy Inheritance

Policy is resolved in this order, with later levels overriding earlier levels:

1. Built-in safe defaults.
2. Account-wide policy.
3. Repository-class policy.
4. Language or project-type policy.
5. Repository-specific overrides.
6. Time-limited exceptions.

The policy schema rejects unknown fields and incompatible combinations. Resolution is deterministic, emits an explanation trace, and produces a canonical SHA-256 policy hash stored with every run and plan. Built-in defaults contain no automatically writable operations.

Hard safety invariants are not policy switches and cannot be overridden by repository policy or exceptions. These include no automatic merge; no deletion of repositories, releases, branches, tags, credentials, packages, collaborators, keys, or webhooks; no unattended visibility, ownership, archive, or default-branch changes; no security-alert dismissal; no secret-value collection; and no approval based only on a finding ID.

Exceptions must contain a stable exception ID, target selector, check IDs, reason, creator, creation timestamp, and mandatory expiration timestamp unless explicitly marked permanent. Timestamps use RFC 3339 UTC. Expired exceptions become findings and no longer suppress results.

## 7. Operating Modes

GitHub Account Maintainer exposes the following operating modes:

| Mode | Purpose | External writes |
| --- | --- | --- |
| `audit` | Inventory and evaluate the account | None |
| `plan` | Produce exact proposed changes and diffs | None |
| `apply-safe` | Apply an exact policy-approved plan whose operations are in the automatic-write allowlist | Allowlisted writes only |
| `open-prs` | Create or update consolidated maintenance pull requests | Branch and PR writes |
| `apply-approved` | Apply a previously approved immutable plan | Approved writes only |
| `pins-sync` | Synchronize profile pins through the local UI adapter | Profile-pin changes |
| `previews-sync` | Upload merged social-preview assets through the local UI adapter | Social-preview changes |
| `backup` | Back up repositories and metadata | Backup-destination writes |
| `bootstrap` | Apply the baseline to a new repository | Policy-controlled writes |
| `rollback` | Restore a captured settings snapshot where supported | Explicitly selected writes |

## 8. Remediation Safety Matrix

| Change category | Default handling |
| --- | --- |
| Inventory, scoring, and reports | Automatic, read-only |
| Metadata and nonbreaking settings | Plan only until the exact operation is added to the automatic-write allowlist and enabled by policy |
| README, documentation, templates, configuration, graphics, and workflow files | Pull request |
| Security feature enablement | Explicit policy approval and plan/feature support checks |
| Actions permission changes | Approval required unless an exact safe baseline was previously approved |
| Rulesets and branch protection | Approval required |
| Collaborators, GitHub Apps, deploy keys, webhooks, and environment access | Report only by default |
| Visibility, ownership transfer, archiving, or default-branch changes | Report and manual approval; never unattended |
| Repository, release, branch, tag, credential, or package deletion | Never automatic |
| Security-alert dismissal | Never automatic |
| Profile pins and social-preview assignment | Local browser adapter with dry-run and verification |

### Operation catalog and immutable plans

Every mutating capability is registered in an operation catalog with a stable operation ID, required credential type and permissions, risk class, planner, preconditions, verification procedure, rollback support, and test evidence. The automatic-write allowlist is empty in Release 0.1. Adding an operation requires an explicit policy change and tests for planning, conflict detection, verification, redaction, and rollback behavior where supported.

A plan is immutable and contains:

- Plan ID and SHA-256 content hash.
- Account, repository, and exact target identifiers.
- Exact operations, current values, desired values, and evidence.
- Credential type and required effective permissions.
- Policy hash and tool version.
- Target preconditions such as ETag, node ID, commit SHA, or settings snapshot hash.
- Creation and expiration timestamps.
- Risk and remediation classification.

Approval binds to the plan hash, not a finding ID. An approval records the approver, timestamp, expiration, and optional comment. Application re-reads permissions and target state, verifies every precondition, and fails closed if the plan expired, policy changed, approval is missing, or target state drifted. A new plan and approval are required after any such change.

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

The coverage report must identify access data that GitHub does not expose to the active credential or through a public API. In particular, the product must not claim an account-wide list of personal OAuth grants or personal access tokens when only application-owned grants, organization-scoped token metadata, or settings-page data is available. Such checks use the defined `unsupported` or `inaccessible` coverage state and may emit a finding whose remediation is `manual only`; they are never silently omitted. Browser-based access inventory is a separate, optional capability and remains read-only unless a later scope explicitly approves writes.

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

### Managed maintenance pull requests

- The managed branch defaults to `github-account-maintainer/maintenance` in each target repository.
- The pull request body and branch contain a versioned machine-readable ownership marker, source plan ID, plan hash, policy hash, and observed base commit SHA.
- The system updates only a branch and pull request whose marker, repository, and recorded state match its local state. A same-name unmarked branch or pull request is a conflict and is never overwritten.
- Planning computes changes against the current default-branch commit. Application re-reads the default branch and fails when that base moved unless a new plan is created.
- Commits append normally. Force pushes, history rewrites, direct default-branch commits, and automatic merges are disabled.
- Workflow-file changes require the credential permission GitHub specifies for workflow content. Missing permission fails before branch creation.
- Branch protection, rulesets, required signatures, and organization policy are honored. Inability to satisfy them produces an actionable failure, not a bypass.
- Generated commits use a configured maintainer identity or GitHub App identity. The product does not claim commits are signed unless GitHub verifies the actual signature.

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
- Backup configuration requires an explicit absolute destination, encryption mode, key reference, retention policy, and minimum free-space preflight. No default destination is inferred.
- Private repository and sensitive metadata payloads use the maintained `age` file format with an X25519 recipient. Archive payloads use `.tar.zst.age`; public, non-sensitive mirrors may remain unencrypted only when policy explicitly permits it.
- Encryption is performed by a pinned and preflighted `age` implementation. The project must not implement custom cryptography. The public recipient may be stored in policy; the private identity remains in the operating-system credential store or an explicitly protected file outside the source repository, state database, backup destination, payload, and manifest.
- Backup manifests contain checksums and timestamps.
- Scheduled verification confirms that mirrors and archives can be read.
- Retention and pruning are explicit policy settings.
- Pruning is disabled until separately planned and explicitly applied. Verification never overwrites a live repository.
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

Each run produces machine-readable and human-readable results appropriate to the implemented release:

- Account summary.
- Per-repository health score when scoring is enabled in Release 0.4 or later.
- Category scores for metadata, documentation, security, access, CI, dependencies, releases, and backup when scoring is enabled.
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

Findings have separate stable check IDs and per-observation finding instance IDs. A finding ID is never an approval target.

### Coverage-aware scoring

Scores are not part of Release 0.1. When introduced, scoring uses versioned weights and includes only checks with comparable `audited` or `supported` states in the denominator. `unsupported`, `unavailable_by_plan`, `inaccessible`, `not_applicable`, `unverified`, `skipped_by_policy`, `not_requested`, and `failed` results remain visible but do not silently reduce a repository's score. Reports show numerator, denominator, excluded-state counts, scoring-policy version, and enough detail to reproduce the score.

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

- Use a user-scoped discovery credential to enumerate repositories visible to the configured account. Release 0.1 supports a fine-grained personal access token with documented read permissions and no write permissions.
- The implemented discovery path requires repository Metadata read access. The complete FUT-005 audit additionally requires repository Contents, Administration, and Code scanning alerts read access. No current command requires a repository write permission.
- Use GitHub App installation tokens for long-term repository operations when practical. An installation token covers only repositories granted to that installation and is never treated as an account-discovery credential.
- Use a GitHub App user access token only when an account-level API operation requires user authorization and the app has the corresponding account permission.
- Separate discovery, read-only audit, write-enabled remediation, browser-session, and optional classic-token capabilities. One credential must not silently substitute for another role.
- Use short-lived installation tokens where possible.
- Require separate explicit authorization for capabilities that need a classic personal access token.
- Store secrets in the operating system credential store or an approved secrets manager.
- Store the Playwright browser profile outside the repository and encrypt or protect it using operating-system controls.

The repository must never contain tokens, cookies, private keys, recovery codes, or unredacted secret values.

### Permission preflight

Before every operation, GitHub Account Maintainer confirms the authenticated identity, credential role, target coverage, and required effective permissions. REST clients record relevant `X-Accepted-GitHub-Permissions` response information when available. Missing or ambiguous permissions produce actionable coverage results rather than partial, misleading success. Permission discovery is never used to broaden the credential automatically.

The project maintains a versioned operation-to-endpoint-to-credential permission matrix. A capability cannot leave experimental status until its matrix entry is backed by a contract or integration test.

## 28. Privacy and AI Use

- Deterministic checks run locally whenever practical.
- Public-repository AI analysis may use a configured provider.
- Private-repository AI analysis is disabled by default.
- A local model can be selected for private README and metadata analysis.
- External AI use requires an explicit provider, model, data-scope, and retention policy.
- Prompts and responses must not contain secrets or credential values.
- Generated content retains evidence references and confidence scores.
- AI suggestions cannot directly alter default branches or merge themselves.

### Local data boundaries

`platformdirs` resolves all default per-user paths. On Windows the application root is `%LOCALAPPDATA%\GitHubAccountMaintainer`, with `config`, `state`, `cache`, `reports`, `logs`, `browser`, and `backup-metadata` child directories. The implementation uses the Windows Known Folder result rather than trusting a repository-controlled path. Other platforms use the corresponding `platformdirs` config, state, cache, log, and data locations. These paths never default inside a managed source repository. Backup payload destinations never receive a default.

- Local paths are resolved to absolute paths and checked before writes.
- Reports, logs, SQLite files, browser data, backup manifests, raw captures, fixtures derived from private data, and temporary clones are excluded from source packages and Git commits.
- State and report retention are explicit configuration values. Pruning requires its own plan and cannot remove backups.
- Reports default to the minimum data required. Private repository names, URLs, paths, source excerpts, collaborator identities, and access metadata require an explicitly selected local report detail level.
- Recorded API fixtures are synthetic or sanitized. They contain no tokens, cookies, signed URLs, private repository names, private source content, or personal access details.

### Threat model

Before any write-enabled release, the repository contains a reviewed threat model covering credential theft, malicious repository content, prompt injection, poisoned fixtures, path traversal, symlink and junction handling, command injection, unsafe Git configuration, browser-session theft, forged approvals, plan replay, API response drift, log leakage, backup disclosure, and compromised dependencies.

Repository content and external text are untrusted. Deterministic parsers receive structured inputs. AI output can create suggestions or proposed diffs only; it cannot call mutating adapters, alter policy, approve a plan, select credentials, or mark verification successful. Private content sent to an external provider requires a repository allowlist plus explicit provider, model, fields, retention policy, and per-run consent.

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
- `uv` for dependency management, reproducible environments, and a committed `uv.lock`.
- `platformdirs` for deterministic per-user config, state, cache, log, report, and browser-data locations.
- Typer for the CLI.
- Pydantic for policy, finding, and API models.
- `httpx` for GitHub REST and GraphQL access.
- The Python standard-library `sqlite3` module with numbered forward-only migrations for local state, findings, approvals, run history, and content hashes.
- Jinja2 for text reports and Pillow with bundled, versioned fonts for deterministic social-preview rendering. Templates, fonts, dimensions, layout, colors, and renderer version are explicit inputs to the content hash; system fonts are not used.
- Playwright for GitHub features without supported write APIs.
- Structured JSON logging with redaction.

GitHub REST requests pin `X-GitHub-Api-Version: 2026-03-10`. The pinned version is a single application constant and reported in every run. Changing it requires contract-test review and a changelog entry.

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
github-account-maintainer init [--output PATH]
github-account-maintainer auth check
github-account-maintainer inventory
github-account-maintainer audit [--repo OWNER/REPO] [--deep]
github-account-maintainer plan [--repo OWNER/REPO]
github-account-maintainer plans show PLAN_ID
github-account-maintainer apply-safe PLAN_ID --apply
github-account-maintainer open-prs PLAN_ID --apply
github-account-maintainer approvals list
github-account-maintainer approvals approve PLAN_ID --expires RFC3339_TIMESTAMP --apply
github-account-maintainer apply-approved PLAN_ID --apply
github-account-maintainer pins audit
github-account-maintainer pins sync PLAN_ID --apply
github-account-maintainer previews audit
github-account-maintainer previews generate PLAN_ID --apply
github-account-maintainer previews sync PLAN_ID --apply
github-account-maintainer backup plan
github-account-maintainer backup run PLAN_ID --apply
github-account-maintainer backup verify
github-account-maintainer bootstrap plan OWNER/REPO
github-account-maintainer bootstrap apply PLAN_ID --apply
github-account-maintainer report --format html
github-account-maintainer rollback plan SNAPSHOT_ID
github-account-maintainer rollback apply PLAN_ID --apply
github-account-maintainer schedule install PLAN_ID --apply
```

Read-only commands do not accept `--dry-run` because they cannot mutate GitHub. Operational commands capable of changing GitHub, browser state, managed repository files, backups, schedules, approvals, or rollback state require both an unexpired immutable plan ID and the literal `--apply` flag. Interactive confirmation is not an alternative. Omitting either produces no mutation. Initialization and explicit report output may create only the user-selected local path and use atomic no-overwrite behavior unless `--overwrite` is separately supplied. Planning never creates branches, pull requests, browser changes, schedules, backups, or target files.

The CLI defines stable automation exit codes:

- `0`: requested work completed and no finding met the configured failure threshold.
- `1`: requested audit completed and one or more findings met the configured failure threshold.
- `2`: run incomplete because of authentication, authorization, API, validation, coverage, or operational failure.
- `3`: invalid command, configuration, policy, plan, or approval.

A partial audit always exits `2`, even when it also produced findings.

## 32. Configuration Outline

```yaml
account:
  login: mickpletcher
  github_host: github.com
  include_private: true
  include_owned: true
  include_administered: false
  affiliations: [owner]

github_api:
  rest_api_version: "2026-03-10"
  request_mode: serial
  mutation_delay_seconds: 1

credentials:
  discovery: github-account-maintainer/discovery
  audit: github-account-maintainer/audit
  remediation: disabled
  classic_token: disabled
  browser_profile: disabled

local_data:
  config_directory: auto
  state_directory: auto
  report_directory: auto
  log_directory: auto
  report_detail: minimal
  state_retention_days: 365
  report_retention_days: 90

safety:
  require_explicit_apply: true
  automatic_merge: prohibited
  destructive_operations: prohibited
  require_approval_for_sensitive_settings: true
  automatic_write_operations: []
  plan_ttl_hours: 24

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
  audit_branch_protection: true
  audit_rulesets: true
  audit_required_reviews: true
  audit_required_status_checks: true
  audit_actions_permissions: true
  audit_actions_workflow_permissions: true
  audit_dependabot: true
  audit_secret_scanning: true
  audit_push_protection: true
  audit_code_scanning: true
  audit_private_vulnerability_reporting: true
  security_alert_dismissal: prohibited

backup:
  enabled: false
  destination: null
  encryption_mode: null
  encryption_key_reference: null
  retention_policy: null
  encrypt_private_data: true
  include_releases: true
  include_metadata: true
  verify_after_backup: true

notifications:
  clean_run_summary: false
  maintenance_pr_label: github-account-maintainer
  cooldown_hours: 168
```

The final schema rejects unknown fields and incompatible combinations. Hard safety fields accept only the documented `prohibited` value. It fails validation before a run when required credentials, paths, permission declarations, plan support, backup destinations, encryption settings, or retention values are absent. Enabling private backup coverage while encryption is disabled is invalid. Credential fields contain credential-store references only, never secret values.

## 33. State and Audit History

The state database records:

- Discovered accounts and repositories.
- Repository classification and resolved policy version.
- Runs and checkpoints.
- Findings and status transitions.
- Exceptions and expirations.
- Immutable plans, plan hashes, expiration, preconditions, and application status.
- Approval decisions, actor, plan hash, creation timestamp, and expiration.
- Settings snapshots and rollback operations.
- Open maintenance branches and pull requests.
- Social-preview input and output hashes.
- Backup manifests and verification results.
- Notification cooldowns.

Secrets, credential-store payloads, browser cookies, raw private repository content, raw AI prompts or responses containing repository content, and backup encryption keys are not stored in the state database. Repository identifiers and evidence stored in minimal mode use stable IDs and redacted display values where full names are unnecessary. Database schema changes use numbered, transactional, forward-only migrations and are covered by migration tests. A pre-migration backup is created outside the source repository before any nonempty database is upgraded.

## 34. Reliability Requirements

- Paginate every GitHub collection correctly.
- Send `X-GitHub-Api-Version: 2026-03-10` on every GitHub REST request and expose the pinned version in reports.
- Respect primary and secondary GitHub rate limits.
- Use conditional requests and caching where safe.
- Begin with serial API requests. Later concurrency requires category-specific measured limits and must never exceed GitHub's published guidance.
- Wait at least one second between mutating API requests unless GitHub publishes a stricter requirement.
- Honor `Retry-After` and rate-limit reset headers. Back off with jitter for retryable transient failures and stop after a bounded number of attempts.
- Resume account-wide runs from durable checkpoints.
- Serialize writes to the same repository or path.
- Detect concurrent repository changes before applying a plan.
- Re-read and verify every settings mutation.
- Verify pull-request branch state before updating it.
- Redact credentials, cookies, secrets, authorization headers, and signed URLs from logs.
- Resolve and validate every local write target before writing. Reject path traversal and paths that resolve through unexpected symlinks or Windows junctions.
- Run Git subprocesses with an explicit argument vector, controlled environment, disabled credential prompting, and no shell interpolation of repository-controlled text.
- Produce a partial-run report that uses the defined coverage states and exits with code `2`.

## 35. Testing Strategy

### Unit tests

- Policy inheritance and exceptions.
- Policy canonicalization, explanation traces, unknown-field rejection, and policy hashes.
- Repository classification.
- Pin ranking and tie stability.
- Findings, severity, coverage states, and finding-instance identity.
- README evidence extraction.
- Social-preview rendering and size validation.
- Redaction.
- Immutable plan hashes, expiration, approval binding, replay rejection, precondition conflicts, settings diffs, and rollback-plan generation.
- Path traversal, symlink and junction handling, and command-argument safety.
- Exit-code behavior, including partial runs.

### Contract tests

- Synthetic or sanitized recorded GitHub REST and GraphQL response fixtures.
- Pagination and rate-limit behavior.
- Permission and plan-dependent feature responses.
- API-version headers, redirects, ETags, `Retry-After`, primary limits, and secondary-limit responses.
- `audited`, `supported`, `unsupported`, `unavailable_by_plan`, `inherited`, `inaccessible`, `not_applicable`, `unverified`, `skipped_by_policy`, `not_requested`, and `failed` coverage classification.
- Content update conflicts.
- Pull-request deduplication.

### Integration tests

- Dedicated test account and repositories.
- Safe metadata update and verification.
- Maintenance branch and pull-request lifecycle.
- Backup and restore verification.
- GitHub App and fine-grained-token authentication.
- Discovery completeness compared with the declared credential scope.
- Credential-role separation and rejection of an incorrect credential role.
- Plan application against deliberately changed target state.

### Browser-adapter tests

- Pin audit and reorder against a disposable test profile.
- Social-preview upload against a disposable test repository.
- Detection of changed GitHub UI selectors.
- Failure without mutation when verification is uncertain.

Browser adapters must not be tested against production repositories without an explicit test target.

All write-capable tests use disposable repositories, accounts, browser profiles, schedules, and backup destinations. Test cleanup is explicit and limited to resources created by the test run. Tests never require production credentials.

## 36. Release Gates

Acceptance is phase-specific. Passing a later-looking demonstration does not waive an earlier gate. A release contains only capabilities whose tests and documentation pass its gate.

### Release 0.1: Audit foundation gate

Release 0.1 passed its local read-only pilot after it could:

1. Install reproducibly from the committed `pyproject.toml` and `uv.lock` on supported Windows and Linux test environments.
2. Run `auth check`, verify the discovery identity and read-only role, and never print or persist the token.
3. Inventory every repository visible within declared discovery scope with proven pagination and a terminal coverage state for every requested item.
4. Classify repositories and resolve strict policy deterministically with an explanation trace and stable policy hash.
5. Run deterministic metadata and community-file checks without cloning private content unnecessarily.
6. Produce schema-versioned JSON and Markdown reports with exact coverage, findings, current and desired values, and minimal-detail privacy defaults.
7. Use only read-only GitHub requests. The Release 0.1 code path contains no enabled mutating adapter and the automatic-write allowlist is empty.
8. Return the documented exit codes, including code `2` for every partial run.
9. Pass unit and contract tests for pagination, API versioning, permission failures, coverage states, policy validation, redaction, paths, and exit codes.
10. Leave the repository and GitHub account unchanged during repeated audits.

### Release 0.2: Expanded read-only audit gate

Release 0.2 is ready when it additionally:

1. Audits supported repository settings, security features, README evidence, and social-preview validity.
2. Distinguishes supported, unsupported, unavailable-by-plan, inherited, inaccessible, not-applicable, unverified, and failed states through tested API fixtures.
3. Stores migrated run and finding history without secrets or raw private source content.
4. Resumes a deliberately interrupted multi-repository audit without duplicating completed work.
5. Produces a complete-within-declared-coverage audit. Scoring remains disabled unless its separate coverage-aware contract is implemented and tested.

### Release 0.3: Planned remediation and pull-request gate

Release 0.3 is ready when it additionally:

1. Includes the reviewed threat model and versioned operation-permission matrix.
2. Implements immutable plans, expiring approvals, target preconditions, replay prevention, before-and-after snapshots, verification, and supported rollback planning.
3. Demonstrates one explicitly allowlisted metadata or nonbreaking settings operation against a disposable repository, including deliberate conflict and verification-failure tests.
4. Creates or updates one consolidated maintenance branch and pull request in a disposable repository without committing to the default branch or duplicating pull requests.
5. Proposes an evidence-backed README change without unsupported claims.
6. Generates a deterministic social-preview asset below the configured size limit and avoids regeneration when inputs are unchanged.
7. Demonstrates that destructive, access-related, visibility, ownership, archival, default-branch, deletion, and security-alert dismissal operations cannot run unattended.

### Release 0.4: Advanced audit and reporting gate

Release 0.4 is ready when advanced access, ruleset, Actions, dependency, release, SBOM, and attestation checks have documented coverage and contract tests. The HTML dashboard and scoring require reproducible coverage-aware calculations and versioned schemas.

### Release 0.5: Browser-adapter gate

Release 0.5 is ready when profile-pin ranking is stable, browser mutations require immutable approved plans, disposable-account tests pass, selector drift fails without mutation, and session data remains outside the repository. Social-preview assignment follows the same gate.

### Release 0.6: Backup, lifecycle, and bootstrap gate

Release 0.6 is ready when a disposable repository and metadata export can be encrypted, checksummed, verified, and restored to an isolated target; retention does not prune without a separate approved plan; lifecycle remains recommendation-only; and bootstrap never overwrites existing files.

### Release 1.0: Scheduled production gate

Release 1.0 is ready for scheduled production use when Windows Task Scheduler and cron integrations, non-overlap locks, notifications, cooldowns, checkpoint recovery, performance limits, rate-limit handling, upgrade migrations, and end-to-end failure recovery pass. Every capability included in the production schedule must have already passed its own release gate.

## 37. Delivery Phases

### Phase 1A: Release 0.1 audit foundation

- `uv` project scaffold, typed models, CLI, linting, testing, and packaging.
- User-scoped read-only authentication and permission preflight.
- Inventory, declared coverage, pagination, and repository classification.
- Strict policy engine, exception validation, explanation traces, and policy hashes.
- Finding model plus read-only metadata and community-file checks.
- Schema-versioned JSON and Markdown reports.
- Serial, version-pinned GitHub clients, redaction, privacy-safe paths, and contract fixtures.

### Phase 1B: Release 0.2 expanded audits and state

- Read-only settings and supported security-feature checks.
- Deterministic README evidence and social-preview validation.
- SQLite migrations, run history, finding transitions, and checkpoint resume.
- Explicit unsupported and manual-review coverage for unavailable account data.

### Phase 2: Release 0.3 planned remediation and pull requests

- Threat model and operation-permission matrix.
- Immutable planners, approvals, safe appliers, verification, snapshots, and rollback planning.
- Consolidated maintenance branches and pull requests.
- README and documentation reconciliation.
- Deterministic social-preview generation with bundled fonts.

### Phase 3: Release 0.4 advanced security, CI, and supply chain

- Access governance within declared API coverage.
- Rulesets and Actions audits.
- Dependency and release health.
- SBOM and attestation verification.
- HTML dashboard and coverage-aware scoring.

### Phase 4: Release 0.5 profile and UI adapters

- Profile-pin synchronization against disposable test profiles.
- Social-preview assignment against disposable test repositories.
- Profile-field audit and separately approved updates.

### Phase 5: Release 0.6 backup, lifecycle, and bootstrap

- Encrypted mirror and metadata backup.
- Verification and isolated restore testing.
- Lifecycle recommendations.
- New-repository detection and non-overwriting baseline bootstrap.

### Phase 6: Release 1.0 scheduling and production hardening

- Windows Task Scheduler and cron support.
- Optional webhook processing.
- Notifications and cooldowns.
- Non-overlap locking, checkpoint resume, performance, API limits, migrations, and failure hardening.
- End-to-end production-readiness review.

## 38. Known Constraints

- GitHub exposes profile pins through GraphQL but does not document a public write mutation for personal profile pins.
- GitHub documents social-preview assignment through repository settings rather than a public upload API.
- Browser automation is therefore isolated, local, optional, and fail-closed.
- A GitHub App installation token can access only repositories granted to that installation. User-scoped discovery and account permissions require separate credential roles.
- Feature availability varies by repository visibility, ownership, GitHub plan, and organization policy.
- Public APIs do not provide a guaranteed account-wide inventory of personal OAuth grants or personal access tokens. Unavailable data remains an explicit coverage limitation and manual-review finding.
- Settings snapshots do not guarantee rollback. Permissions, GitHub behavior, plan availability, and concurrent changes can make a later rollback impossible.
- GitHub user migration archives require distinct authorization and remain downloadable for a limited period.
- Automated README review cannot prove undocumented intent; uncertain changes require human review.

## 39. Official GitHub References

- Repository API: <https://docs.github.com/en/rest/repos/repos>
- REST API versions: <https://docs.github.com/en/rest/about-the-rest-api/api-versions>
- REST API best practices and rate limits: <https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api>
- GitHub App permissions: <https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app>
- GitHub App installation scope: <https://docs.github.com/en/apps/using-github-apps/installing-a-github-app-from-a-third-party>
- GitHub App installation endpoints: <https://docs.github.com/en/rest/apps/installations>
- OAuth authorization endpoints: <https://docs.github.com/en/rest/apps/oauth-applications>
- Organization personal-access-token endpoints: <https://docs.github.com/en/rest/orgs/personal-access-tokens>
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
