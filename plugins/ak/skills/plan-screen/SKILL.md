---
name: plan-screen
description: "Run Stages 1 and 2 only for one screen - the computed scope and the screen plan - without touching code. Trigger when the user explicitly wants just the planning and documentation stages for a screen, not full implementation - modernize-screen already covers straight through implementation, so use this only when the user asks to plan a screen, or to stop after documents. Examples: \"/ak:plan-screen OrderEntry\", \"just plan out screen X, don't code it yet\", \"write the screen plan for Y\"."
---

# Plan One Screen

Run **Stages 1 and 2 only** for the screen named in the request. Produce documents; write
no code.

Do not restate the method here. `MASTER_WORKFLOW.md` in the project's docs directory is the
authority for what each stage does and what closes it.

## Before starting

0. If no screen was named in the request, stop and ask which screen before reading anything
   else — do not guess a screen from recent conversation context.
1. Read `PROJECT_CONFIG.md`. An unfilled `{{...}}` stops the run — ask, do not substitute a
   plausible default.
2. Resolve the screen in `Screens_Registry.md`. If absent, run Agent-Assisted Registration:
   detect the row from evidence and existing code, show it as plain text, and wait for `ok`,
   `edit field=value`, or `cancel`.
3. Grep `Known_Issues.md` for the screen and its module. Report open rows, especially
   `type: traceability` — a known gap changes what Stage 2 must cover.
4. Resolve and announce `doc_mode` for this screen in one line before writing anything.

## Then

- Stage 1 is computed and writes nothing: run `modernize/scripts/screen_scope.py --ak <AK_RUN_DIR> --screen "<screen>"` and read the report. Closing gate: **G1 Evidence Coverage**, which the script computes.
- Stage 2 per `Screen_plans/README.md`, producing **both** contracts — backend and frontend.
  Closing gate: **G2 Rule Coverage** plus a populated gap matrix, with `screen_scope.py --plan Screen_plans/<screen>.md` reporting no finding.
  When the register holds no rule for the screen, the mapping rows carry ids minted as `BR-<PREFIX>-nn`: run
  `modernize/scripts/screen_rule_ids.py --registry Screens_Registry.md --screen "<screen>" --plan Screen_plans/<screen>.md`
  and apply what it proposes. Ask the user to declare the screen's `rule_prefix` in the registry if it is missing; never pick it yourself.

Mark the backend contract frozen only if the user says 3a and 3b will run concurrently.

## Entering here is the risk this skill carries

This skill starts mid-pipeline by design, so nothing upstream has been verified for you.
If Stage 1's scope cannot be computed or its evidence is missing, stop at G1 and report what is absent rather than
writing a plan on top of a gap — a screen plan built over missing evidence is worse than no
plan, because it looks finished.

Report what you wrote, both gate verdicts, and any HIGH finding with its options. Do not
update `Screens_Registry.md` status to anything beyond what documents alone justify.
