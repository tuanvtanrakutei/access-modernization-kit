---
description: Write and run the tests for one screen — backend suite then frontend end-to-end
argument-hint: "[screen] [--backend-only|--frontend-only]"
---

Run **Stages 4a and 4b** for the screen named in the argument. `MASTER_WORKFLOW.md` is the
authority; `{{TEST_METHOD_DOC}}` and the frontend testing document define how to choose test
cases.

## Refuse to start unless the code exists

1. `Coding_Records/{screen}.md` must exist with the section for each track you intend to
   test. No coding record means Stage 3 did not run — stop and say so.
2. Read `PROJECT_CONFIG.md` and respect `{{REFERENCE_DB_POLICY}}` for reference data. Never
   read production data to make a test pass.
3. Announce which suites you will run before running them.

## Order is not negotiable

**4a before 4b.** The end-to-end suite needs a running backend, so a frontend run before the
backend suite passes tests nothing and reports success. If the backend suite fails, stop and
report; do not proceed to 4b to produce a greener-looking summary.

- **Stage 4a** — write `Test_Instruction/{screen}.md` §Backend, then run `{{TEST_CMD}}`.
- **Stage 4b** — write §Frontend, then run `{{FE_E2E_TEST_CMD}}` (and `{{FE_UNIT_TEST_CMD}}`
  if defined), plus the output comparison against the legacy samples.

## Reading the result honestly

This is where a run most often lies to itself.

- **Establish the baseline first.** If the suite already had failures before your change, get
  that number before you touch anything, and report your result against it. A count alone
  proves nothing.
- **An ERROR is not a FAILED.** A failure says something is wrong; an error says the test
  body never ran. Resolve errors before reading failures, and never quote a pass count from a
  run that had errors without saying so.
- **A test that passes before and after your change proves nothing.** For a regression test,
  show it failing against the unfixed code.
- If the suite is red for reasons outside this screen, group the failures by **error
  signature rather than by file** — that turned 49 failures into three root causes here, two
  of them fixed in a few lines.

Report the real numbers, the baseline, and every skipped case with its reason.
