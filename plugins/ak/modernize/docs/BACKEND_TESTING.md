# Backend Testing Method (Stage 4a)

> **Layer 1 document.** The transferable method for testing a modernized screen's backend. Commands and paths resolve from `PROJECT_CONFIG.md`.
>
> File layout, naming, fixtures, markers, and coverage expectation are `CONVENTIONS.md` §4 — this document does not repeat them. It covers what to test, in what priority, and how to read the result honestly.

Stage 4a of `MASTER_WORKFLOW.md`. Runs before Stage 4b, which needs a working backend.

## Contents

- [Role](#role)
- [Source Of Truth, In Priority Order](#source-of-truth-in-priority-order)
- [The Three Tiers](#the-three-tiers)
  - [The Rule That Matters Most](#the-rule-that-matters-most)
- [Mocking Principle](#mocking-principle)
- [Pre-Check: Is The Environment The Problem?](#pre-check-is-the-environment-the-problem)
- [Format Portability](#format-portability)
- [Reading Results Honestly](#reading-results-honestly)
- [What Every Screen Must Cover](#what-every-screen-must-cover)
- [Recording Results](#recording-results)
- [Relationship To The Pipeline](#relationship-to-the-pipeline)
- [What This Document Is Not](#what-this-document-is-not)

## Role

**You are a tester, not a fixer.** The screen was implemented by someone else, possibly by an earlier pipeline pass.

- Do not fix production code to make a test pass. Fix the test's setup or assertion; if the expectation itself was wrong, that is a screen-plan correction, recorded as a finding.
- Do not weaken an assertion to turn a test green.
- Where behavior deviates from the specification, write a finding with root cause, impact, and suggested fix — and stop there.

## Source Of Truth, In Priority Order

1. `Test_Instruction/{screen}.md` — the specification, if it exists
2. `Screen_plans/{screen}.md` — the backend contract: endpoints, request/response shape, side effects
3. Legacy evidence — the exported VBA, query, or stored procedure, read with `{{SOURCE_ENCODING}}`
4. Current code — last resort. When used, say so explicitly: *expected behavior derived from the current implementation; no specification comparison performed.* That sentence is the difference between a test that verifies a requirement and one that merely freezes today's behavior.

## The Three Tiers

Classify every test, then push it as far toward UNIT as the logic under test allows.

| Tier | Covers | Method | Case id |
|---|---|---|---|
| **UNIT** | Pure logic: calculations, validation rules, serializer transforms, permission classification | Fully mocked, no database | `TC-{SCREEN}-UNIT-NN` |
| **API** | The endpoint contract: request/response shape, status codes, side effects, transactional integrity | `@pytest.mark.django_db`, real ORM against the test database | `TC-{SCREEN}-API-NN` |
| **PARITY** | Output fidelity: does the generated file or JSON match the legacy sample — column order, headers, formatting, encoding | Call the real service, then parse the produced artifact structurally | `TC-{SCREEN}-PARITY-NN` |

### The Rule That Matters Most

**A test is UNIT or API, never both, and the marker must say which.** A class marked `unit` whose method reaches the database is not a faster unit test — it is an API test wearing the wrong label, and pytest-django will block the connection and raise from deep inside Django rather than from your assertion. Read that error for what it is: a missing `@pytest.mark.django_db`, not a product defect. This happened repeatedly on this project; grouping the resulting failures by signature (see Reading Results Honestly, below) is what made the pattern visible instead of debugging each one as a separate mystery.

## Mocking Principle

**Mock a whole collaborator, or none of it.** A queryset chain — `.select_related().filter().values_list().order_by()` — is one collaborator. Stubbing one link and letting the next hand back a fresh auto-mock is the single most common backend test defect found on this project: the untouched link returns nothing, the test sees zero rows instead of an error, and the failure reads as a logic bug rather than a stale mock. It recurs every time the service under test gains a `.filter()` or reorders a call the mock did not anticipate.

| Target | Treatment |
|---|---|
| A queryset chain | Mock every link to return the same mock object, or don't mock the ORM at all and use `@pytest.mark.django_db` |
| An external system (NAS, SMB share, third-party API) | Always mock. Never let a UNIT or API test depend on network reachability |
| The permission check | Follow the project's `mock_permission_checks`-style fixture if one exists — but see the note below |
| The row your assertion targets | Never mock. If the object under test is a `MagicMock`, the assertion is checking the mock's behavior, not the code's |

**An autouse fixture that mocks the thing under test makes every test pass regardless of whether the real code works.** If the suite has an autouse fixture patching permission checks or a similar cross-cutting concern, a test that means to verify enforcement must explicitly opt out of it — otherwise the suite has no coverage of that concern at all, and nothing will ever fail to reveal that.

For PARITY tier, do **not** mock the artifact generation. The point of that tier is that the real code produced the real bytes.

## Pre-Check: Is The Environment The Problem?

Before writing a single test, or before trusting a batch of failures as defects, rule out the
environment itself:

- **Migrations.** Run `manage.py makemigrations --check --dry-run`. A non-empty result means a
  model has no migration in this environment — tests touching that table will fail with
  `relation "..." does not exist`, which reads as a data-layer bug but is a missing migration.
  Note the project's own convention before concluding anything is broken: a project whose
  `.gitignore` excludes migrations, or whose deploy script runs only `migrate` and never
  `makemigrations`, treats migrations as a **per-environment artifact** rather than a committed
  file — in that case the fix is running the generation step locally, not filing a defect.
- **Multi-database declarations.** A test touching a non-default database alias (a `target_big`,
  a reporting replica) needs `@pytest.mark.django_db(databases=[...])` naming every alias it
  reaches, not just the bare marker. The error — `Database threaded connections to 'X' are not
  allowed in this test` — names the missing alias directly; read it rather than guessing.
- **The database is reachable at all.** A suite that was green minutes ago and is now failing
  everywhere, across files you did not touch, is very likely infrastructure — a stopped
  container, not a regression. Confirm on one untouched, previously-passing test before
  attributing anything to your change.

## Format Portability

A test asserting an exact export format must pass on **every platform tests actually run on**,
not only the deployment container. `strftime("%-I")` — 12-hour clock without zero padding — is
a glibc extension: correct in the Linux container, `ValueError: Invalid format string` on a
Windows development machine. The defect was invisible for as long as no test pinned the output,
because the code path that mattered simply could not run locally.

- Pin the exact output string for any hand-built format, not just its general shape. A test
  asserting `len(row) == 29` catches nothing about the timestamp column's content.
- Cover the boundary values, not only a convenient one. For a 12-hour conversion: midnight and
  noon, where an off-by-one hides.
- If a platform-specific primitive is unavoidable, that is the finding, not something to work
  around silently in the test. Report it — the fix is almost always a portable replacement in
  the seven or eight lines around the primitive, not a test-side workaround.

## Reading Results Honestly

- **Establish the baseline before attributing a failure.** Stash your change, run the suite,
  restore it, and compare. A change that appears to break 13 tests may be revealing 1
  pre-existing failure and 12 you actually caused — or the reverse. Quoting a count without the
  baseline is a claim with no evidence behind it.
- **`ERROR` is not `FAILED`** — see `CONVENTIONS.md` §4.3. Resolve errors first; a suite with
  errors has parts that have never been exercised, not merely parts that are broken.
- **Group failures by error signature, not by file**, when there are more than a handful.
  `scripts/triage_suite.py` (skill: `triage-suite`) does this mechanically — it turned 49
  failures into 3 root causes on this project, two of which were fixed in a few lines once
  identified. A wall of red read file-by-file gets triaged one test at a time and looks far
  worse than it is.
- **A test that passes before and after a change proves nothing** as a regression test. If the
  point is to pin a fix, show the test failing against the unfixed code first.

## What Every Screen Must Cover

Derive the case list from the screen plan's backend contract — every endpoint and side effect
appears exactly once in the tier classification. Beyond that, these are always in scope:

- **Per endpoint**: the success path, and its primary validation-failure path.
- **Permission**: per `{{BACKEND_RULES_DOC}}` §12 — read-tier classification, and whether
  enforcement is actually exercised rather than bypassed by an autouse fixture (see Mocking
  Principle, above).
- **Calculations**: rounding boundaries and zero/negative-quantity edge cases, not just the
  typical case.
- **Transactional integrity**: a write touching more than one row or model rolls back
  completely on partial failure.
- **Output path**: for a report or export endpoint, PARITY-tier coverage of the generated
  artifact against the legacy sample.
- **Input path**: for an import or upload endpoint, cover the encodings the operator's own
  tools produce, a header row in a different column order, one case per row-level validation
  rule, and — where the import replaces data — a **forced** mid-write failure proving the
  rollback. Force it by patching the write to raise; a test that merely hopes for a partial
  failure passes while the transaction boundary is missing. Where an export of the same table
  exists, assert that the export re-imports unchanged: it is the cheapest guard against the
  two column lists drifting apart.

## Recording Results

Results go into `Test_Instruction/{screen}.md` §Backend — the same artifact the frontend track
uses for §Frontend. One file per screen means the Stage 5 reviewer reads one place and the
registry's `status_be` has a single evidence source.

Every finding carries: case id, expected, actual, root cause where known, impact, and suggested
fix. A finding without an expected-versus-actual pair is an opinion.

## Relationship To The Pipeline

- Runs as Stage 4a, before Stage 4b — the frontend track needs a working backend to test against.
- Its results are one of the inputs the Stage 5 reviewer checks.
- It does not set `status_be` — only a Stage 5 approval does that.
- Findings that affect more than one screen are promoted to `Known_Issues.md`.

## What This Document Is Not

- Not file layout, naming, fixtures, or markers — `CONVENTIONS.md` §4.
- Not the "a test must call the code it verifies" rule — `CONVENTIONS.md` §4.3b.
- Not permission-audit method — `{{BACKEND_RULES_DOC}}` §12.
- Not legacy-evidence anchor format — `TRACEBACK_GATES.md` §Anchor Format.
- Not project-specific credentials, ports, or container names. Those belong in the project's
  own testing notes, never in this document or in a shared plugin.
