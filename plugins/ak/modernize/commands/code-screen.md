---
description: Implement one screen from its existing screen plan — backend then frontend
argument-hint: "[screen] [--backend-only|--frontend-only]"
---

Run **Stages 3a and 3b** for the screen named in the argument, against the contract its
screen plan already froze. `MASTER_WORKFLOW.md` is the authority on both stages.

## Refuse to start unless the upstream artifact exists

This is the whole point of the check. Entering at coding means Stages 1 and 2 were not run
for you.

1. `Screen_plans/{screen}.md` must exist and contain **both** contracts — backend and
   frontend. If it is missing, or has only one contract, stop and tell the user to run
   `/plan-screen` first. Do not infer a contract from the legacy evidence here; that is
   Stage 2's job and skipping it is how a screen ends up implemented against nobody's
   agreement.
2. Its gap matrix must be populated. An empty gap matrix means Stage 2 never closed G2.
3. Read `PROJECT_CONFIG.md`, then the backend, frontend and conventions rule documents.
4. Resolve and announce `be_mode` and `fe_mode` before editing anything.

## Then

- **Stage 3a** under `{{BACKEND_ROOT}}`, following the backend rules and conventions
  documents. Write `Coding_Records/{screen}.md` §Backend. Closing gate: `{{LINT_CMD}}`
  passes.
- **Stage 3b** under `{{FRONTEND_ROOT}}`, following the frontend rules. Write
  `Coding_Records/{screen}.md` §Frontend. Closing gate: `{{FE_LINT_CMD}}` passes, then **G3
  Implementation Coverage**.

Run 3a and 3b concurrently **only** if the screen plan marks the backend contract frozen.
Otherwise 3b waits: the frontend needs the contract to be real, not provisional.

`--backend-only` and `--frontend-only` restrict to one track. Say which you ran.

## Lint discipline

Run the lint command in **check mode over the files you changed**. Never a formatter, never
a `--fix` flag, and never over a whole change list — in this project a formatter run across
an entire diff reformatted seven files belonging to other people's work in progress and that
reached a shared branch.

Report the files you touched, both gate verdicts, and anything you could not implement with
the reason. A deviation from the frozen contract is a Stage 5 blocker — record it, do not
quietly adjust the contract to match the code.
