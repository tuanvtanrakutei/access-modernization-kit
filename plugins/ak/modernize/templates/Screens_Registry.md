# Screens Registry

> **Template.** Copy to `{{DOCS_DIR}}/Screens_Registry.md` and fill. This is the single source of truth mapping each screen to its identifiers and implementation state.

The pipeline reads this file at pre-flight. If a screen is absent, the agent runs Agent-Assisted Registration (`MASTER_WORKFLOW.md`) rather than guessing.

## Identifier Definitions

| Column | Source | Used where |
|---|---|---|
| `screen` | The legacy object name, in `{{SCREEN_NAME_LANG}}` | Filename for every per-screen artifact. **Join key across all documents** |
| `screen_key` | `{{SCREEN_KEY_CASE}}` slug | Agent-prompt variable; folder name under `{{API_COLLECTION_DIR}}` |
| `url_segment` | Path segment after the module prefix | Backend route under `{{API_PREFIX}}{module_prefix}/` |
| `module` | Backend app that owns the screen | Code placement; parallelism partitioning |
| `module_prefix` | URL prefix the module is mounted at | First path segment after `{{API_PREFIX}}` |
| `fe_route` | Frontend route under `{{FE_ROUTE_BASE}}` | Frontend placement; deep-link target |
| `priority` | Implementation order | Sequencing across screens |
| `status_be` | Backend implementation state | Resolves `be_mode` for Stages 3a and 4a |
| `status_fe` | Frontend implementation state | Resolves `fe_mode` for Stages 3b and 4b |

### Why Two Status Columns

Backend and frontend progress independently. A screen whose API shipped months ago may have no UI yet. A single status column forces a lie in one direction and makes the agent pick the wrong run mode. Track them separately and each stage resolves its own mode.

## Status Vocabulary

| Value | Meaning | Set by | Run mode it implies |
|---|---|---|---|
| `not_started` | No code exists for this track | Registration, or manual seeding | Greenfield |
| `implemented` | Code is complete but has **not** been verified by this pipeline | Coding stage end gate, or manual seeding of a pre-existing system | Backfill |
| `verified` | Reviewed and approved at Stage 5 | Review verdict gate | Refresh |
| `partial` | Code exists but work was intentionally deferred; see the coding record's deferred items | Coding stage end gate | Backfill |
| `blocked` | Cannot proceed; an open blocker exists in `Known_Issues.md` | Abort gate, or coding stage end gate | Pipeline stops |

### Why `implemented` And `verified` Are Separate

A modernization project usually starts with code that already exists and has never been through this pipeline. Collapsing "the code is written" and "we have validated it against the legacy system" into one value makes that state impossible to express, and forces the registry to overstate what is actually known.

The separation also makes run-mode resolution exact instead of heuristic: `implemented` means Backfill, `verified` means Refresh. Without it, the agent must guess Backfill by noticing that some artifact is missing — which quietly fails when an artifact exists but is stale.

Do not set `verified` at the coding stage. Only a Stage 5 approval earns it.

## Active Screens

| # | screen | screen_key | url_segment | module | module_prefix | fe_route | status_be | status_fe |
|---|---|---|---|---|---|---|---|---|
| 1 | `{{SCREEN_1}}` | `{{SCREEN_1_KEY}}` | `{{SCREEN_1_URL}}` | `{{SCREEN_1_MODULE}}` | `{{SCREEN_1_PREFIX}}` | `{{SCREEN_1_FE_ROUTE}}` | `not_started` | `not_started` |
| 2 | | | | | | | | |

## Future Scope

Screens planned but not yet started. No per-screen artifacts exist for these. The pipeline promotes a row to the active table when work begins.

| # | screen | screen_key (proposed) | module (proposed) |
|---|---|---|---|
| | | | |

## Client-Collection Folder Naming

Applies when `{{API_COLLECTION_DIR}}` is in use. Per-screen folders there must use the `screen_key` exactly as recorded above, in `{{SCREEN_KEY_CASE}}`.

Do not rename folders speculatively. Stage 4a normalizes the folder for the screen it is working on, so the rename lands in the same change that touches the screen. Record any rename in the coding record's files-touched list.

## Update Rules

This file is written only at the moments below. Every other edit is a manual exception that should be rare and deliberate.

| Trigger | Change |
|---|---|
| Agent-Assisted Registration confirmed by the user | New row added to the active table |
| Pre-flight gate on a future-scope screen | Row promoted to active; statuses stay `not_started` |
| Coding stage end gate | Track status → `implemented`, or `partial` / `blocked` when applicable, with a link to the coding record's deferred or blocking item |
| Review verdict gate | On approval, the covered track statuses → `verified` |
| Abort gate | Track status → `blocked` when the cause is screen-level |

Additional rules:

1. **Never rename `screen`.** It is the join key for every per-screen artifact; renaming it orphans the whole document set.
2. Treat `screen_key` as stable once any artifact folder uses it.
3. Moving a screen to a different `module` requires the code, tests, frontend route, and every reference in this row to move together, plus a `Known_Issues.md` entry if the screen is already implemented.
4. Do not set a status without a triggering gate. A status that drifted from reality is worse than a missing one, because the agent trusts it when choosing a run mode.
5. Two bulk edits are expected and legitimate: seeding a brand-new project with every screen at `not_started`, and onboarding an existing system by setting the tracks that already have code to `implemented` — never to `verified`, which only a review can grant.

## Cross-Reference

| Document | Uses this registry for |
|---|---|
| `MASTER_WORKFLOW.md` | Pre-flight lookup; run-mode resolution; parallelism partitioning |
| `TRACEBACK_GATES.md` | Mode-aware gate behavior per track |
| `Business_flows/README.md`, `Screen_plans/README.md`, `Coding_Records/README.md`, `Test_Instruction/README.md`, `Code_Review/README.md` | Index tables and the `screen` join key |
| `Known_Issues.md` | Screen and module identifiers used in issue rows |
| `PROJECT_CONFIG.md` | Module list and naming conventions this file follows |
