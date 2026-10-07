---
name: test-screen
description: "Write and run the tests for one screen - backend suite then frontend end-to-end (Stages 4a-4b) - and close the stage with the evidence and gate G4: which rules the tests back, whether they can fail, whether the output matches the legacy output. Refuses to start unless a coding record already exists for the track being tested. Trigger when the user explicitly wants just the testing stage for a screen that is already coded, not the full pipeline. Examples: \"/ak:test-screen OrderEntry\", \"write and run tests for screen X\", \"test the backend for screen Y\"."
---

# Test One Screen

Run **Stages 4a and 4b** for the screen named in the request, then close the stage with the
evidence and **gate G4**. `MASTER_WORKFLOW.md` is the authority; `{{TEST_METHOD_DOC}}` and the
frontend testing document define how to choose test cases; `TRACEBACK_GATES.md` specifies G4.

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

- **Stage 4a** — write `Test_Instruction/{screen}.md` §Backend, then run `{{TEST_CMD}}` with the
  runner's JUnit option (`--junitxml=Test_Instruction/{screen}.junit.xml` for pytest) and keep the file.
  A test must name the rule it proves in its own name or docstring (`BR-ORD-01`), or the next
  stage cannot show it.
- **Stage 4b** — write §Frontend, then run `{{FE_E2E_TEST_CMD}}` (and `{{FE_UNIT_TEST_CMD}}`
  if defined), plus the output comparison against the legacy samples.
- **Close Stage 4** with the evidence and gate G4 (the section after the next one). Stage 4 is
  not done, and `Backend: pass` is not written in the header, until G4 has run.

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

## Close Stage 4: the evidence, then gate G4

A green run is a claim. Gate G4 turns it into evidence by reading the result files below, and a
missing file is a finding, never a pass. Run the steps in order once the backend suite is green,
and after the last change to code or tests. Each step writes one file beside the screen's
`Test_Instruction/{screen}.md`; `screen_verify.py` reads all of them. Write each file with the
script, never by hand: a count or a `Canary:` line typed into a document is a claim.

### 1. Which rules do the tests back

```bash
python "${CLAUDE_PLUGIN_ROOT}/modernize/scripts/screen_rule_tests.py" --ak "$AK_RUN_DIR" --screen "<screen>" \
  --junit Test_Instruction/{screen}.junit.xml --tests <this screen's test source folder> \
  --coverage-map Test_Instruction/{screen}.md --out Test_Instruction/{screen}.rule-tests.json
```

A rule is **TESTED** only when a test that names it ran and passed. **FAILING**, **NOT RUN**,
**CLAIMED** (only the coverage map says so) and **UNTESTED** are gaps: write the missing test, or
record the gap in section 6. Point `--tests` and `--junit` at this screen's tests only. When the
extraction's register holds no rule for the screen, use `--plan Screen_plans/{screen}.md` in place of `--ak` and
`--screen`: the rules are the ids its mapping rows carry (`BR-<PREFIX>-nn`, see `Screen_plans/README.md` §5).
The rules in scope are a superset of what the screen uses, so a rule that is not the screen's, or
cannot be asserted, may be set aside with `--waive BR-X="reason"`: a waiver is a person's decision,
never yours, so ask for it and record the reason. Copy each rule's state into the coverage map's
Status column from the result file, never from memory.

### 2. Can the tests fail (the canary)

Break one line that matters in a scratch copy and see whether anything fails. Pick a line a rule
depends on: a rounding mode, a threshold moved by one, a comparison reversed. Break the line that
applies a value, not the constant that holds it: a test that imports the constant moves with it.
The break must still build, or the run errors before any test runs. Run one canary for each
calculation or validation the screen plan marks as critical.

```bash
python "${CLAUDE_PLUGIN_ROOT}/modernize/scripts/screen_canary.py" --root <code folder> \
  --file <file under root> --find "<exact text, once>" --replace "<broken text>" \
  --cmd "{{TEST_CMD}}" --out Test_Instruction/{screen}.canary-1.json
```

It never writes the real code. **CAUGHT** is the only pass. **SURVIVED**: no test depends on that
line, so add the missing test and run the canary again. **INCONCLUSIVE**: the break stopped the
tests from running, so choose another break. **NO BASELINE**: the untouched copy was not green.

### 3. Does the output match (screens that produce a file or a response)

Save the legacy output once, produce the new output from the same input, list the pairs in a
`cases.json` and compare them. Matching the recorded samples proves the cases someone picked,
so after they match invent at least ten more inputs that are not in the sample set: boundaries,
the empty input, an oversize one, malformed records, rows in another order, the encodings the
operator's tools produce. Run each through the legacy system and the new one, list them as
`"origin": "fresh"` with the `"input"` file and a `"kind"`.

```bash
python "${CLAUDE_PLUGIN_ROOT}/modernize/scripts/screen_parity.py" <cases.json> \
  --min-fresh 10 --min-kinds 4 --out Test_Instruction/{screen}.parity.json
```

Do not drop a fresh input because its output differs: that difference is the finding. If the
legacy system cannot run here, say so and do not count the case. A screen that produces no
output has no parity result, and G4 does not ask for one.

### 4. Gate G4

```bash
python "${CLAUDE_PLUGIN_ROOT}/modernize/scripts/screen_verify.py" --screen "<screen>" \
  --rule-tests Test_Instruction/{screen}.rule-tests.json \
  --canary Test_Instruction/{screen}.canary-1.json [Test_Instruction/{screen}.canary-2.json ...] \
  [--parity Test_Instruction/{screen}.parity.json] [--output-screen]
```

Add `--output-screen` when the screen produces a file or a response, so a missing parity result is
a finding. G4 reads the files and runs nothing, so run steps 1 to 3 after the last change.

- **HIGH** blocks: stop and ask the user `examine` / `defer` / `cancel`, as for any gate.
- **MEDIUM and LOW** continue to Stage 5: file each as a `traceability` row in `Known_Issues.md`
  per `TRACEBACK_GATES.md`, so the reviewer confirms it.
- Fill `Test_Instruction/{screen}.md` §3.6 with the result files, the finding counts and every
  waiver with its reason, and set the header's `G4` field.
- G4 reads the backend JUnit result. Frontend evidence stays in the 4b results: say so in the
  report instead of implying G4 covered it.

Report the real numbers, the baseline, every skipped case with its reason, and the G4 findings.
