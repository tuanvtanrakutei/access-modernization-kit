---
name: modernize-screen
description: "Run the end-to-end legacy Access modernization pipeline for one screen or several in parallel — business flow, screen plan, backend coding, frontend coding, tests, and review. Trigger when the user wants to implement, refresh, test, or review a screen of a legacy Access application being rebuilt as Django REST plus React. Examples: \"/modernize-screen OrderInquiry\", \"implement screen X\", \"refresh the pipeline for screen Y\", \"implement the frontend for screen Z\", \"review screen W\", \"implement X and Y in parallel\"."
---

# Modernize One Screen

You are running the modernization pipeline for one or more screens of a legacy Microsoft Access application. The authoritative orchestration document is `MASTER_WORKFLOW.md` in the project's documentation directory.

## Step 1 — Read The Project Configuration First

Before anything else, locate and read `PROJECT_CONFIG.md`. Every path, command, and convention you need is defined there, and none of it may be guessed.

If you cannot find it, ask the user where it is. If a value you need is still an unfilled `{{...}}` placeholder, stop and ask the user to complete that row — do not substitute a plausible default. A wrong path silently writes files into the wrong place, and a wrong command silently reports a passing test suite that never ran.

## Step 2 — Parse The Request

Identify three things:

1. **Screens.** One or many. Match them against `Screens_Registry.md` using the `screen` column verbatim.
2. **Intent.**
   - `implement` (default) — run the full pipeline
   - `refresh` — Refresh mode; reconcile artifacts against current code
   - `review only` — Stage 5 alone, after verifying upstream gates passed
   - `test only` — Stage 4 alone, after verifying upstream gates passed
   - `accept only` — Stage 6 alone, requiring an approved Stage 5 verdict
3. **Track.** `both` (default), `backend only` (Stages 3a and 4a), or `frontend only` (Stages 3b and 4b, which require the backend artifacts to already exist).

If the request is ambiguous — a screen name that does not match, no screen named, an unclear track — stop and ask before doing any work.

## Step 3 — Read The Orchestrator

Read `MASTER_WORKFLOW.md` in full. Do not skim. It defines:

- The pipeline: Stage 0 handoff, Stages 1 through 6, where 3a/3b and 4a/4b split, and why Stage 5 review is separate from Stage 6 acceptance
- Run Modes, resolved separately as `doc_mode`, `be_mode`, and `fe_mode`
- Pre-Flight Check, including the concurrent-activity soft lock
- Agent-Assisted Registration for unregistered screens
- Parallelism Rules
- Update Gates for the registry and the issue log
- Traceback Gates G1, G2, and G3 — summarized there, specified fully in `TRACEBACK_GATES.md`
- Loop Handling, Abort and Cleanup, and the scope boundaries

Also read `LEGACY_EVIDENCE.md` for the project's declared legacy variant. What counts as complete evidence for a `.adp` differs from a split `.accdb`, and gate G1 measures against that difference.

If these documents disagree with anything you believe about this project, the documents win.

## Step 4 — Pre-Flight, Batched

Issue these reads in one message rather than one at a time:

1. `PROJECT_CONFIG.md` — resolve every placeholder
2. `Screens_Registry.md` — locate each requested screen's row
3. `Known_Issues.md` — grep for each screen name and module, paying attention to `type: traceability` rows
4. The evidence directories declared in the config, filtered for each screen
5. The table mapping document
6. The backend, frontend, and conventions rule documents

Then, for each screen, resolve and announce the three run modes in one line, for example:

> *Screen OrderInquiry — doc_mode: Backfill, be_mode: Backfill, fe_mode: Greenfield. Backend shipped; documentation and the whole frontend are missing.*

If a screen is absent from the registry, run **Agent-Assisted Registration**: detect the row from evidence and existing code, present it as plain text, and wait for `ok`, `edit field=value`, or `cancel`. Write the row only on `ok`. Never halt with a bare request for the user to edit the file by hand — detection is your job, and the scope decision is theirs.

## Step 5 — Route

### Single screen

Run the master prompt from `MASTER_WORKFLOW.md` §"Master Agent Prompt", stages in order, honoring each stage's closing gate:

- G1 after Stage 1, G2 after Stage 2, G3 after Stage 3b
- On a HIGH gate finding, prompt the user with `examine` / `defer` / `cancel` and wait
- On MEDIUM or LOW, file a `traceability` row and continue
- Apply the registry and issue-log update gates at the moments defined, and nowhere else

### Multiple screens

Partition by `module`, treating screens that share a frontend layout, route group, or store as the same group. One background agent per group; screens within a group run sequentially.

Do not improvise the orchestration — it is encoded:

1. Read `orchestration/parallelism.json` for the partition rules and `orchestration/roles.json` for who may write what and who may prompt.
2. Write one envelope per group from `templates/group-task-envelope.json`, filling `write_paths` with **only** that group's artifacts and code directories. `Screens_Registry.md` and `Known_Issues.md` never appear in a group's `write_paths`.
3. Dispatch each group agent with `templates/group-agent-prompt.md` plus its envelope.
4. Collect the per-screen handoffs. Write the `intended_registry_row` and `intended_issue_rows` yourself — an intended row is a request, not a record.
5. Collect HIGH findings from every group and prompt the user **once** with a numbered list, then dispatch the decisions back.

`MASTER_WORKFLOW.md` §"Multi-Screen Batch" remains the explanation of why. On a conflict, that document wins and the JSON is the bug.

Collect HIGH gate findings from subagents and prompt the user **once**, consolidated, then dispatch the decisions back. Subagents never prompt the user directly. Never let two agents write the registry or the issue log at the same time — queue those writes here.

## Step 6 — Report

After each stage, post one paragraph: what was produced, the closing gate result with finding counts per sub-check, and the next stage.

At the end, post: a link to every artifact, the verdict, the registry status changes applied, open follow-ups, and a count of traceability rows filed, resolved, deferred, and marked will-not-fix.

On an abort, follow the cleanup policy for the stage you were in, then report exactly which files were reverted, which were deleted, and which were left in place — plus any command the user must run themselves.

## Hard Rules

1. **Read `PROJECT_CONFIG.md` before anything else.** Never guess a path, command, or convention.
2. **Never skip pre-flight**, however urgent the request sounds.
3. **In Backfill mode, do not write code.** Document what exists. If the user wants new behavior, they will say so explicitly.
4. **Never parallelize stages within one screen.** The single exception is 3a with 3b, and only when the screen plan marks the backend contract frozen.
5. **Never parallelize screens sharing a module**, or sharing frontend layout or state.
6. **Never write the registry or the issue log outside the defined update gates.**
7. **Never close an issue row** without naming the change or review that resolved it.
8. **Never set a track status to `implemented`** before review approves it.
9. **Stop rather than invent a model or a migration** when the target schema lacks something. Follow the project's escalation rule and record it.
10. **Stop rather than proceed without evidence.** Implementing a screen with no legacy evidence is redesign, which is outside this pipeline.
11. **Do not weaken a test to make it pass**, and do not report an environment blocker as a functional failure.
12. **Report failures plainly.** A red lint or test result stated honestly is useful; one hidden behind an optimistic status makes every later approval worthless.
