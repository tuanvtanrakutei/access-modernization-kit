---
name: triage-suite
description: "Work out what is actually wrong with a failing test suite by grouping failures by error signature instead of by file, so a wall of red resolves into a few root causes. Trigger when a suite is red and the cause is unclear, when there are more failures than anyone wants to read one at a time, before deciding whether failures belong to your change or predate it, or when the user asks what is failing and why. Examples: \"/triage-suite\", \"why are 48 tests failing\", \"are these failures mine\", \"group the test failures\"."
---

# Triage A Failing Suite

A red suite read file-by-file looks like many independent problems and gets fixed one test
at a time. Grouped by the error text, it usually collapses to a handful of causes. Measured
on this project twice: 24 failures were one root cause, and 49 failures resolved into three
groups of which two were fixed in a few lines each.

## Step 1 — Capture a run with tracebacks

```bash
{{TEST_CMD}} --tb=line > run.txt 2>&1
python "${CLAUDE_PLUGIN_ROOT}/modernize/scripts/triage_suite.py" --input run.txt --report triage.md
```

`--tb=no` omits the text the grouping works on, so the tool will have nothing to read.
`--tb=line` is enough and keeps the file small; `--tb=short` also works.

Read details from the report, not the console. The console summary is ASCII-only on purpose
because a Japanese assertion message printed to a cp932 console raises `UnicodeEncodeError`
and turns an analysis run into a traceback.

## Step 2 — Establish the baseline before attributing anything

This is the step that is skipped and the one that matters most. A failure count proves
nothing about whose change caused it.

```bash
git stash push -q -- <paths you changed>
{{TEST_CMD}} -q --tb=no          # this is the baseline
git stash pop
```

State the result as *before → after*. On this project a change looked like it broke 13
tests until the baseline showed 1 failure pre-existing and the true attribution was
different from the first guess. If you cannot stash — a dirty tree with other people's
work, for instance — say that the attribution is unverified rather than implying it is not.

## Step 3 — Take the largest signature first

The count beside a signature is how many tests one fix would clear. Work down the list.

For each group, open **one** instance before deciding anything. A signature is a grouping
of text, not a diagnosis; identical text can have two causes.

## Step 4 — Read errors before failures

The report puts ERROR ahead of FAILED because they are different findings:

- **FAILED** — the test ran and the assertion did not hold. Something is wrong.
- **ERROR** — the test body never ran. Whatever it covers has **never been checked**, so a
  green-looking summary is hiding a coverage hole, not a bug.

Never quote a pass count from a run that had errors without saying it had errors. On this
project a file sat in ERROR long enough that its endpoint had never once been exercised;
fixing the error was a one-word change and the feature turned out to be fine — but nobody
knew that until it ran.

## Signatures seen repeatedly, and what they usually mean

Offered as a starting hypothesis to check, never as a conclusion to report.

| Signature shape | Usually |
|---|---|
| `Database access not allowed, use the "django_db" mark` | the class touches the database through code the mocks do not cover; it is an integration test wearing a unit marker |
| `assert 0 == N` on a query-backed test | a mock stubs one link of a chained queryset, so the next link returns an empty mock and the test sees zero rows instead of an error |
| `'list' object has no attribute 'filter'` | the service gained a chained `.filter()` the mock does not route |
| `AttributeError: ... has no attribute` on a constant | a symbol was renamed or removed; check whether the correct one already exists under another name before adding anything |
| an English substring asserted against a localized message | the test predates a wording change, or asserts a spec the message never matched — decide which before editing either side |
| `Invalid format string` | a platform-specific format directive; it works in the container and not on a developer machine |
| `relation "..." does not exist` | a model with no migration in this environment, which may be a local staleness rather than a defect |

## Report like this

1. Totals, and the baseline they are measured against.
2. Errors, with the note that their bodies never ran.
3. Causes largest first: signature, count, one opened example, and what a fix would touch.
4. What is **not** yours, stated plainly, with how you established that.
5. What you propose to fix, and what you propose to leave.

## Do not

- Do not fix anything as part of triage. Triage produces a plan; ask before acting on it.
- Do not re-run until green. An intermittent failure is a suspected production bug until
  measured otherwise — a flaky-looking test here turned out to be a real ordering defect in
  a live screen.
- Do not report a count without the baseline. It is the difference between "I broke 13
  tests" and "12 of these were already failing".
