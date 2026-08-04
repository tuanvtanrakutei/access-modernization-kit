# Plan 3A Collaboration Foundation Design

**Status:** Proposed for user approval
**Target release:** AK 2.7.2
**Canonical language:** English
**Parent design:** `docs/superpowers/specs/2026-07-23-profile-driven-extraction-bundle-design.md`

## 1. Summary

Plan 3A adds the collaboration contracts needed for multiple developers and agents to work on the AK kit or the same application investigation without creating a second investigation pipeline.

The design introduces one canonical work-package model shared by humans and agents. Existing runtime task envelopes remain execution projections derived from that model. Production extraction bundles remain outside Git by default, while Git stores the bundle authority reference, work contracts, review receipts, conflict records, and approved documentation changes.

The six investigation phases remain sequentially published by the coordinator. Parallel contributors may collect evidence, implement kit components, prepare scoped application artifacts, and review independent work, but they may not merge canonical Phase outputs unless their work package grants the coordinator or designated document-owner role.

## 2. Problem Statement

AK already has provider-neutral task envelopes, handoffs, conflict records, immutable run snapshots, bundle locks, coordinator-only Phase publication, and independent QA. These runtime contracts are sufficient for one orchestrated run but do not fully define how human developers and agents collaborate across branches, repositories, bundle authorities, reviews, and contract changes.

Without a collaboration foundation:

- a human ticket, agent task, and runtime task may describe the same work differently;
- contributors can accidentally claim overlapping write paths or evidence namespaces;
- a review can approve prose without binding the approval to the exact work package, commit, bundle, and validation results;
- schema, profile, adapter, readiness, or output-contract changes can merge without a complete migration and compatibility statement;
- application teams may place production bundles or proprietary source exports in Git because the authority model is unclear;
- contributor documentation may duplicate the investigation pipeline and drift from the architecture contracts.

## 3. Goals

Plan 3A must:

1. Define one canonical work package for human and agent collaboration.
2. Derive existing runtime task envelopes from that work package rather than maintaining a second collaboration model.
3. Support both AK kit contributors and application investigation teams with conditional authority rules.
4. Bind every review to exact immutable inputs and validation results.
5. Detect overlapping write scopes, evidence namespaces, and coordinator-reserved outputs before execution.
6. Require explicit contract-impact records for compatibility-sensitive changes.
7. Extend bundle-lock authority for multi-developer use without invalidating existing V2.7 locks.
8. Keep production bundles outside Git by default through `artifact_store` references.
9. Preserve coordinator-only canonical Phase publication and independent QA.
10. Provide English-canonical collaboration documentation without duplicating the investigation pipeline.
11. Validate the collaboration contracts on Windows and Linux using synthetic, non-proprietary fixtures.

## 4. Non-Goals

Plan 3A does not:

- implement SQL, VBA, UI, CRUD, relationship, or interface analyzers;
- introduce the stable deterministic analysis model;
- migrate Graphify inputs to the future analysis model;
- create Phase 1 technical appendices or the Phase 6 Refactoring Handoff;
- run or authorize live Access, ADP, SQL Server, backup restore, COM, DAO, or network acquisition;
- implement a vendor-specific artifact-store client;
- create a GitHub-only collaboration model, pull-request bot, or mandatory MCP dependency;
- permit workers to publish canonical Phase documents;
- place production bundles, database binaries, credentials, row dumps, or proprietary exports in Git.

Those deterministic-analysis and refactoring-document concerns belong to Plan 3B, targeted at AK 2.8.0.

## 5. Design Principles

### 5.1 One collaboration model

`work-package.json` is the canonical scoped-work contract. Human tickets, branch descriptions, agent prompts, and runtime task envelopes refer to the same package ID and digest.

`task.schema.json` remains a runtime execution format. It is generated from a work package plus the active run, wave, role, and runtime adapter. Contributors do not independently author a second task definition containing conflicting scope.

### 5.2 Immutable authority, separate execution state

The accepted work package is immutable. Its digest identifies the exact objective, authority, inputs, writes, expected artifacts, validation commands, evidence namespace, coordinator, and reviewer.

Mutable execution state stays in existing run-state, task, handoff, conflict, and review-receipt files. A change to scope creates a superseding work package instead of editing an accepted package in place.

### 5.3 Git stores control records, not production bundles

Application repositories commit the extended `bundle.lock.json`, work packages, review receipts, conflict records, and approved documents. Production bundle content remains in the approved artifact authority unless distribution is explicitly `git_allowed` for synthetic or non-sensitive content.

### 5.4 Coordinator publication remains singular

Parallel work ends in scoped artifacts and handoffs. Only the coordinator or a work-package-designated document owner may merge canonical Phase files. A document owner is still subordinate to coordinator checkpoints and cannot approve their own publication receipt.

### 5.5 English canonical package documentation

Schemas, architecture references, CLI help, contributor documentation, and contract examples are canonical in English. Application outputs continue to follow manifest language declarations and may be bilingual.

## 6. Canonical Collaboration Model

The collaboration model has four durable records:

1. `work-package.json`: immutable scope and authority.
2. `review-receipt.json`: review decision bound to the package digest and produced revision.
3. `contract-impact.json`: required compatibility statement for contract-sensitive changes.
4. `bundle.lock.json`: application bundle authority and distribution reference.

Existing task, handoff, conflict, approval, and run-state records remain runtime or bundle records. They reference the canonical work-package ID and digest where applicable.

No fifth ticket schema is introduced. External systems such as GitHub Issues, Jira, or local Markdown may link to a work-package ID but are not authoritative for AK scope.

Versioned collaboration records use this project-root layout in both the kit repository and application repositories:

```text
collaboration/
├─ work-packages/<PACKAGE_ID>/work-package.json
├─ reviews/<RECEIPT_ID>.json
├─ contract-impacts/<IMPACT_ID>.json
└─ conflicts/<CONFLICT_ID>.json
```

Runtime projections and handoffs remain under `runs/<RUN_ID>/`. The project-root collaboration records must not contain production bundle content.

## 7. Kit Contributor and Application-Team Surfaces

### 7.1 Kit contributor

A kit contribution uses repository revision authority. The work package pins:

- repository identifier;
- base revision;
- allowed write paths;
- expected changed artifacts;
- validation commands;
- reviewer and coordinator;
- whether contract impact is required.

It does not require an application bundle unless the contribution is a controlled application pilot. Synthetic fixtures must contain invented data only.

### 7.2 Application team

An application investigation package uses approved-bundle authority. It pins:

- app ID;
- bundle ID and checksum;
- bundle-lock digest;
- approval record ID and approval checksum when available;
- distribution policy and logical artifact reference;
- phase, module, role, and evidence scopes;
- coordinator and independent reviewer.

The package may read normalized approved bundle content but may not add raw source binaries to Git or bypass acquisition authorization.

### 7.3 Mixed pilot

A controlled kit pilot may use both authorities. It pins the kit base revision and the approved application bundle. Changes to either authority require a superseding work package and a new review receipt.

## 8. `work-package.schema.json`

Plan 3A adds `plugins/ak/schemas/work-package.schema.json` using JSON Schema Draft 2020-12.

Required top-level fields:

| Field | Purpose |
|---|---|
| `schema_version` | Collaboration contract version. |
| `package_id` | Stable identifier matching `^[A-Z0-9_-]+$`. |
| `title` | Short English-canonical title. |
| `objective` | Bounded outcome, not a general project goal. |
| `work_kind` | `kit_code`, `kit_contract`, `kit_docs`, `application_evidence`, `application_docs`, `application_qa`, or `mixed_pilot`. |
| `authority` | Repository revision, approved bundle, or both. |
| `scope` | Profile, adapter, module, phase, role, or document targets. |
| `dependencies` | Other work-package IDs that must be accepted first. |
| `input_paths` | Readable logical paths. |
| `write_paths` | Exclusive writable logical paths. |
| `expected_artifacts` | Required output path, kind, and publication class. |
| `evidence_namespace` | Exclusive evidence-ID prefix or `null` for kit-only work. |
| `validation_commands` | Deterministic commands required before review. |
| `coordinator` | Integration authority. |
| `reviewer` | Required reviewer; distinct from the producer when independent review is required. |
| `publication_policy` | `scoped_only`, `document_owner`, or `coordinator_only`. |
| `security_constraints` | Data, path, network, and authorization restrictions. |
| `created_by` | Human or agent identity label. |
| `created_at` | ISO 8601 timestamp excluded from semantic scope comparison. |

This intentionally refines the parent design's generic “task ID” wording: `package_id` is the canonical collaboration-level work identifier, while `task_id` identifies only a derived runtime execution unit. One package may project multiple task IDs without creating multiple authorities.

Authority is a discriminated union:

- `repository_revision`: requires repository and base revision;
- `approved_bundle`: requires app ID, bundle ID, checksum, bundle-lock digest, approval record ID, distribution policy, and artifact reference;
- `mixed`: requires both authority sets.

`write_paths` must be app- or repository-relative, normalized with forward slashes, and free of absolute paths or `..`. Canonical Phase output paths are rejected unless publication policy and role grant coordinator or document-owner authority.

The schema remains provider-neutral. It does not contain GitHub usernames, Codex agent IDs, Claude session IDs, or runtime-specific spawn fields.

## 9. Runtime Task Projection

Plan 3A extends `task.schema.json` with required projection references for newly generated tasks:

- `work_package_id`;
- `work_package_digest`;
- `projection_version`.

Legacy tasks without these fields remain readable under a compatibility path. New `create_tasks.py` behavior accepts a validated work package and projects only the subset needed by the active run:

- `run_id`, `app_id`, `wave_id`, `role`, status, attempt, and token budget come from runtime context;
- input and write paths must be equal to or narrower than the canonical package scope;
- module and phase targets must be equal to or narrower than the canonical package scope;
- evidence namespace must match the canonical package exactly or use an approved child prefix;
- instructions may add runtime procedure but may not expand authority.

Projection fails closed when a task expands read paths, write paths, module scope, phase scope, evidence namespace, network permission, or publication authority.

## 10. Handoff Collaboration Fields

Plan 3A extends `handoff.schema.json` for new handoffs with:

- `work_package_id`;
- `work_package_digest`;
- `produced_revision` for repository work or `null` for artifact-only work;
- `validation_results`, each containing command, exit code, and concise result;
- `review_receipt_required`.

Artifacts and evidence IDs must stay inside the work-package claims. `validate_handoffs.py` verifies package identity, task projection, immutable inventory membership, write scope, evidence prefix, and required validations.

Handoffs do not approve work. They report completion, failure, or blocking. Approval belongs to the review receipt.

## 11. `review-receipt.schema.json`

Plan 3A adds `plugins/ak/schemas/review-receipt.schema.json`.

Required fields:

- `receipt_id`;
- `work_package_id` and `work_package_digest`;
- `review_stage`: `scope_acceptance`, `implementation`, or `publication`;
- `authority_snapshot`, containing the reviewed commit and/or bundle authority;
- `producer`;
- `reviewer`;
- `review_scope`;
- `validation_results`;
- `findings`;
- `decision`: `APPROVED`, `CHANGES_REQUESTED`, or `REJECTED`;
- `reviewed_at`.

An approval is valid only when:

- the reviewed package digest matches the accepted work package;
- the reviewed repository revision or artifact digest is exact;
- required validation commands completed successfully;
- the reviewer is not the producer when independent review is required;
- no unresolved conflict blocks the package;
- contract-sensitive changes include a valid contract-impact record.

A `scope_acceptance` receipt approves the immutable package before task projection. Its validation results cover package schema, authority, path/evidence conflicts, dependency checks, and required security constraints. An `implementation` receipt approves produced code or scoped artifacts. A `publication` receipt is required for canonical document publication and must be issued by an authorized reviewer after coordinator integration checks.

A new commit, bundle, scope, or validation command invalidates the prior approval for integration.

## 12. `contract-impact.schema.json`

Plan 3A adds `plugins/ak/schemas/contract-impact.schema.json` for changes under contracts, schemas, profiles, adapters, readiness rules, orchestration policies, templates, output contracts, or public CLI behavior.

Required fields:

- `impact_id`;
- `work_package_id` and digest;
- `changed_paths`;
- `affected_contracts`;
- `compatibility`: `compatible`, `migration_required`, or `breaking`;
- `migration_behavior`;
- `synthetic_fixtures`;
- `compatibility_tests`;
- `documentation_updates`;
- `validation_evidence`;
- `untested_runtime_paths`;
- `security_and_data_handling_impact`;
- `release_target`;
- `reviewer`.

Empty arrays are allowed only when accompanied by an explicit reason field. Vague values such as `N/A`, `later`, or `unknown` do not satisfy the contract.

The validator determines whether a contract-impact record is mandatory from changed paths and declared public behavior. Contributors cannot opt out by setting a Boolean in the work package.

## 13. Extended Bundle-Lock Authority

The existing `bundle-lock.schema.json` remains valid. Plan 3A adds optional authority fields for new locks:

- `lock_version`;
- `distribution_policy`;
- `artifact_reference`;
- `bundle_approval_checksum`;
- `profile_rule_versions`;
- `normalization_config_checksum`;
- `supersedes_lock_checksum`.

New multi-developer application work packages require these fields when the information is available from bundle assembly and approval. A legacy lock may support existing V2.7 behavior but cannot provide a complete collaboration authority claim until enriched or regenerated.

The lock is committed to the application repository. The production bundle and external approval record remain outside Git unless policy explicitly permits otherwise.

## 14. Production Artifact Policy

`artifact_store` remains the default production distribution policy. Plan 3A defines only logical references and validation behavior, not a vendor client.

Allowed examples:

```text
artifact_store://sms/A05/bundles/<BUNDLE_ID>
shared_path://controlled-team-share/A05/<BUNDLE_ID>
local_only://<BUNDLE_ID>
```

Machine-specific absolute paths are not portable authority references and may not be committed as the approved location for multi-developer work. Credentials, signed URLs, access tokens, and provider secrets never appear in work packages or bundle locks.

`git_allowed` is valid only for synthetic or explicitly approved non-sensitive bundles. Validation requires the approval record to state that policy.

## 15. Work-Package Lifecycle

The lifecycle is:

1. `DRAFT`: package may change and has no execution authority.
2. `VALIDATED`: schema, paths, authority, dependencies, and conflict checks pass.
3. `ACCEPTED`: a valid `scope_acceptance` review receipt approves the immutable package digest.
4. `PROJECTED`: one or more runtime tasks are derived without expanding scope.
5. `IN_PROGRESS`: contributors execute scoped work.
6. `HANDED_OFF`: required handoffs and validation results exist.
7. `REVIEWED`: review receipt exists.
8. `INTEGRATED`: approved revision or artifacts are merged by the coordinator.
9. `SUPERSEDED` or `CANCELLED`: no further projection or integration is allowed.

Lifecycle state is not edited into the immutable package. It is derived from accepted-package records, task/handoff state, review receipts, and integration receipts. This avoids changing the package digest during execution.

## 16. Path and Evidence Conflict Rules

Before acceptance or projection, AK checks all active packages for:

- overlapping write paths;
- a write path inside another package's read-only frozen output;
- duplicate expected artifact paths;
- duplicate evidence namespaces or ambiguous prefix overlap;
- duplicate package IDs with different digests;
- concurrent claims on coordinator-reserved Phase files;
- mismatched bundle authority for packages intended to merge together;
- dependency cycles;
- reviewer/producer conflicts where independent review is required.

Read/read overlap is allowed. Write/write overlap is blocked unless one package explicitly depends on the other and begins only after the predecessor is integrated. Evidence namespaces cannot be reused even sequentially; superseding evidence uses new IDs and explicit links.

Detected conflicts use the existing conflict policy and `conflict.schema.json`. Collaboration conflicts add stable topics and failure codes rather than introducing another conflict record type.

Plan 3A extends `conflict.schema.json` backward-compatibly so a conflict has exactly one reporter: `reported_by_task` or `reported_by_work_package`. It also adds optional `resolved_by_work_package`. Existing task-reported conflict records remain valid.

## 17. Contributor Workflows

### 17.1 Kit contributor workflow

1. Update local `main` and create a focused branch or worktree.
2. Validate a work package pinned to the base revision.
3. Implement only allowed paths.
4. Run declared validation commands.
5. Produce a handoff and contract-impact record when required.
6. Obtain a review receipt bound to the exact head revision.
7. Let the coordinator merge after conflict and compatibility checks.

### 17.2 Application-team workflow

1. Approve or resolve the application bundle and commit its lock.
2. Create work packages pinned to the same bundle authority.
3. Allocate disjoint module, evidence, and write scopes.
4. Project packages into runtime tasks or execute the same contract sequentially when no agent runtime exists.
5. Merge worker evidence deterministically.
6. Review scoped artifacts independently.
7. Publish canonical Phase outputs only through coordinator checkpoints.

### 17.3 Multi-developer repository rule

Each branch should normally implement one accepted work package. Multiple packages may share a branch only when they have the same coordinator, compatible authority, no path overlap, and separate review receipts.

Git merge order follows work-package dependencies. Runtime wave order does not replace Git dependency order, and Git dependency order does not authorize Phase publication.

## 18. Collaboration CLI

Plan 3A adds bounded deterministic commands:

```text
ak.py collaboration package validate --package <work-package.json>
ak.py collaboration package conflicts --root <work-package-root>
ak.py collaboration package project --package <work-package.json> --run <run-dir>
ak.py collaboration handoff validate --run <run-dir>
ak.py collaboration review validate --package <work-package.json> --receipt <review-receipt.json>
ak.py collaboration impact validate --package <work-package.json> --impact <contract-impact.json> --changed-paths <file>
```

Commands are local and deterministic. They do not create branches, push commits, call GitHub, upload bundles, open Access, connect to SQL Server, or approve human checkpoints.

Existing scripts remain compatibility entrypoints. `create_tasks.py` and `validate_handoffs.py` delegate to collaboration contract modules after migration.

## 19. Documentation Structure

Plan 3A creates:

```text
docs/collaboration/
├─ contributor-workflow.md
├─ application-team-workflow.md
└─ contract-changes.md
```

The documents link to, but do not restate, the canonical pipeline in:

- `docs/architecture/investigation-pipeline.md`;
- `docs/architecture/extraction-bundle.md`;
- `plugins/ak/references/orchestration-guide.md`.

`contributor-workflow.md` explains kit branch/worktree, work-package, validation, review, and merge behavior. `application-team-workflow.md` explains bundle authority, scoped investigation work, evidence merge, and coordinator publication. `contract-changes.md` explains contract-impact triggers and release compatibility.

Application-specific bilingual terminology belongs in application outputs, not duplicated package contracts.

## 20. Testing and CI

Plan 3A adds contract, orchestration, CLI, and integration tests using invented fixtures only.

Required coverage:

- valid kit, application, and mixed work packages;
- invalid absolute paths, path traversal, missing authority, and unsupported publication claims;
- runtime projection that narrows scope;
- projection rejection when scope expands;
- valid and invalid review receipts;
- reviewer independence;
- contract-impact trigger detection from changed paths;
- backward-compatible legacy bundle locks;
- enriched multi-developer bundle locks;
- write-path and evidence-namespace collisions;
- dependency cycles;
- coordinator-reserved output enforcement;
- two-contributor synthetic application fixture with disjoint work and deterministic merge order;
- Windows and Linux path normalization;
- UTF-8 English-canonical docs and JSON Schema validation.

The synthetic collaboration fixture uses no Access or SQL Server binaries. It references a synthetic approved bundle through `artifact_store://fixture/...` and includes two work packages, projected tasks, handoffs, one contract-impact record, two review receipts, and an integration-order assertion.

GitHub Actions continues to run the same `Validate` workflow on Windows and Linux. No self-hosted Access or SQL Server runner is required for Plan 3A.

## 21. Security and Failure Codes

Collaboration validation fails closed with stable codes:

| Code | Meaning |
|---|---|
| `COLLAB_PACKAGE_INVALID` | Work package fails schema or semantic validation. |
| `COLLAB_AUTHORITY_MISSING` | Required repository or approved-bundle authority is absent. |
| `COLLAB_AUTHORITY_MISMATCH` | Packages intended to merge use incompatible authority. |
| `COLLAB_PATH_ESCAPE` | A path is absolute or escapes its declared root. |
| `COLLAB_WRITE_CONFLICT` | Active packages claim overlapping write paths. |
| `COLLAB_EVIDENCE_CONFLICT` | Evidence namespaces overlap or are reused. |
| `COLLAB_PUBLICATION_FORBIDDEN` | A worker claims coordinator-reserved output. |
| `COLLAB_PROJECTION_EXPANDED` | Runtime task exceeds work-package scope. |
| `COLLAB_REVIEW_STALE` | Review receipt does not match the current package or revision. |
| `COLLAB_REVIEW_NOT_INDEPENDENT` | Required independent reviewer equals the producer. |
| `COLLAB_IMPACT_REQUIRED` | Contract-sensitive changes lack a valid impact record. |
| `COLLAB_DEPENDENCY_CYCLE` | Work-package dependency graph contains a cycle. |
| `COLLAB_SECRET_OR_BINARY_PROHIBITED` | A control record contains a prohibited secret, binary, or production-data reference. |

Identity labels provide traceability, not authentication. Repository permissions, artifact-store access control, CODEOWNERS, and human checkpoint approval remain external enforcement boundaries.

## 22. Backward Compatibility

Plan 3A is additive for AK 2.7.2:

- current V2.1/V2.2 manifests remain readable;
- current task and handoff records remain readable through legacy validation;
- newly projected tasks and handoffs carry work-package references;
- existing bundle locks remain schema-valid;
- enriched lock authority is required only for new complete multi-developer claims;
- historical runs and Phase outputs are not rewritten;
- existing provider-neutral runtime adapters continue to operate;
- application teams may adopt work packages incrementally before AK 2.8 makes stronger collaboration gates mandatory.

Compatibility warnings must distinguish `LEGACY_COLLABORATION_UNBOUND` from invalid or blocked work. A legacy run is not falsely reported as having review-bound collaboration provenance.

## 23. Release Strategy

Plan 3A ships as AK 2.7.2 because it extends the V2.7 profile, acquisition, bundle, and orchestration foundation without adding the V2.8 analyzer architecture.

The release includes:

- collaboration schemas and validators;
- runtime task/handoff projection references;
- bundle-lock authority extension;
- deterministic CLI commands;
- collaboration docs;
- synthetic multi-contributor fixtures;
- Windows/Linux CI coverage;
- package version and plugin metadata updates.

Plan 3B remains AK 2.8.0 and owns deterministic analyzers, stable analysis outputs, Graphify migration, technical appendix generation, and Refactoring Handoff production.

## 24. Acceptance Criteria

Plan 3A is accepted when:

1. One schema-valid work package can drive human work and project runtime tasks without a second authored task contract.
2. Projected tasks cannot expand package authority.
3. Kit, application, and mixed authority variants validate deterministically.
4. Overlapping write paths and evidence namespaces block before execution.
5. Workers cannot claim canonical Phase publication paths.
6. Review receipts bind approval to exact package digest, revision or artifact digest, validations, and reviewer.
7. Contract-sensitive changes cannot pass validation without a complete contract-impact record.
8. Existing bundle locks remain valid and enriched locks support artifact-store authority.
9. Production bundle content is absent from Git fixtures and examples.
10. The synthetic two-contributor workflow passes on Windows and Linux.
11. Existing package validation and acquisition tests continue to pass.
12. Collaboration docs are English canonical and link to the single pipeline documentation rather than copying it.
13. No Plan 3A command opens Access, connects to SQL Server, performs acquisition, uploads artifacts, or approves a human checkpoint.
14. Package and plugin versions report `2.7.2` only after all acceptance tests pass.

## 25. Implementation-Plan Boundaries

The implementation plan must use eight independently reviewable tasks:

1. Add work-package schema, semantic model, digest, and fixtures.
2. Add path, evidence, dependency, authority, and publication conflict validation.
3. Add deterministic runtime task projection and backward-compatible task validation.
4. Extend handoffs and add review-receipt validation.
5. Add contract-impact schema, changed-path trigger logic, and CODEOWNERS-aligned tests.
6. Extend bundle-lock authority and add application-team artifact policy tests.
7. Add collaboration CLI and English-canonical documentation.
8. Add synthetic multi-contributor integration fixture, Windows/Linux CI coverage, version bump, and release validation.

Every task must use TDD, leave the package usable, run focused tests before broader tests, and commit independently. No task may implement Plan 3B analyzers or run a real application pilot.

## 26. Approval Decision

The recommended design is **approved for implementation planning after user review**.

Reasons:

- it preserves one canonical collaboration model;
- it reuses existing task, handoff, conflict, bundle-lock, orchestration, and coordinator contracts;
- it prevents documentation and pipeline duplication;
- it supports both kit contributors and application teams without mixing production bundles into Git;
- it creates a bounded AK 2.7.2 checkpoint before deterministic analysis work begins in Plan 3B.
