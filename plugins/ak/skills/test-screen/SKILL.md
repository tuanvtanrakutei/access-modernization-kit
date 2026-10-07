---
name: test-screen
description: "Write and run the tests for one screen - backend suite then frontend end-to-end (Stages 4a-4b). Refuses to start unless a coding record already exists for the track being tested. Trigger when the user explicitly wants just the testing stage for a screen that is already coded, not the full pipeline. Examples: \"/ak:test-screen OrderEntry\", \"write and run tests for screen X\", \"test the backend for screen Y\"."
---

# Test One Screen

Run **Stages 4a and 4b** for the screen named in the request. `MASTER_WORKFLOW.md` is the
authority; `{{TEST_METHOD_DOC}}` and the frontend testing document define how to choose test
cases.

## Refuse to start unless the code exists

0. If no screen was named in the request, stop and ask which screen before checking
   anything else — do not guess a screen from recent conversation context.
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
- **Gate G4** — when 4a and 4b are done, run `python "${CLAUDE_PLUGIN_ROOT}/modernize/scripts/screen_verify.py" --screen "<screen>" --parity <PARITY.json> --rule-tests <rule-tests.json> --canary <CANARY.json ...>`
  (add `--output-screen` when the screen produces a file or a response). It reads the results of the parity,
  rule-test and canary scripts; a missing result is a finding. File every finding as a `traceability` row
  per `TRACEBACK_GATES.md`: HIGH blocks and asks, MEDIUM and LOW continue to Stage 5.

## Inputs nobody used

Matching the recorded legacy samples proves the new code handles the cases someone picked. After
they match, invent at least ten more inputs that are not in the sample set: boundaries, the empty
input, an oversize one, malformed records, rows in another order, the encodings the operator's tools
produce. Run each through the legacy system and the new one, list them in `cases.json` as
`"origin": "fresh"` with the `"input"` file and a `"kind"`, and run
`screen_parity.py --min-fresh 10 --min-kinds 4`. Do not drop a fresh input because its output
differs: that difference is the finding. If the legacy system cannot run here, say so and do not
count the case.

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

## Check which rules the tests back

The coverage map in `Test_Instruction/{screen}.md` is a claim. Keep the runner's JUnit XML from the
backend run (`--junitxml=<file>` for pytest) and let the script read it against the screen's rules:

```bash
python "${CLAUDE_PLUGIN_ROOT}/modernize/scripts/screen_rule_tests.py" --ak "$AK_RUN_DIR" --screen "<screen>" \
  --junit <result file or folder> --tests <test source folder> \
  --coverage-map Test_Instruction/{screen}.md --out Test_Instruction/{screen}.rule-tests.json
```

A rule is **TESTED** only when a test that names it ran and passed. A test names a rule in its
own name (`test_br_ord_01_rounds_up`) or, in Python test files, in its docstring, decorator or a
comment. **FAILING**, **NOT RUN** (only skipped tests, or a test with no result), **CLAIMED**
(only the coverage map says so) and **UNTESTED** are all gaps: write the missing test, or record
the gap in section 6. The rules in scope are a superset of what the screen uses, so a rule the
screen plan says it does not use may be set aside with `--waive BR-X="reason"`; the waiver is
listed in the result. Copy the state of each rule into the coverage map's Status column from the
result file, never from memory.

## Prove the tests can fail (the canary)

A green run says the tests agree with the code, not that they could disagree. Once the backend
suite is green, break one line that matters in a scratch copy and see whether anything fails.
Pick a line the screen's rules depend on: a rounding mode, a threshold moved by one, a
comparison reversed. The break must still build, or the run errors before any test runs.

```bash
python "${CLAUDE_PLUGIN_ROOT}/modernize/scripts/screen_canary.py" --root <code folder>   --file <file under root> --find "<exact text, once>" --replace "<broken text>"   --cmd "{{TEST_CMD}}" --out Test_Instruction/{screen}.canary.json
```

It never writes the real code. **CAUGHT** is the only pass. **SURVIVED** means no test depends on
that line: add the missing test, then run the canary again. **INCONCLUSIVE** means the break
stopped the tests from running: choose another break. **NO BASELINE** means the untouched copy
was not green: fix that first. Record the verdict, the file and the line in the screen's test
instructions. A `Canary:` line typed by hand is a claim; the result file is the evidence.

Report the real numbers, the baseline, and every skipped case with its reason.
