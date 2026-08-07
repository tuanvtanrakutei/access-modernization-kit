# Smoke Test Prompt — Six-Phase Investigation → Modernize Bootstrap

Paste this whole file as your first message in a fresh session. It is self-contained —
no prior conversation context needed.

## Goal

`plugins/ak/modernize/BACKLOG.md` entry D2 (and the G-series follow-ups after it) have never
been exercised against a **real** six-phase run — only against hand-built fixtures in a
scratchpad. This is the one remaining gap. Close it: run the six-phase investigation for
real on a tiny synthetic app, then bootstrap a modernize project from its real output, and
report exactly what broke, if anything.

Repo root: `D:\Anrakutei\access-modernization-kit`. Do all work inside a scratch directory
outside this repo — your session's own scratchpad/temp directory, or any throwaway folder
outside the repo tree — so nothing gets committed by accident. Only commit fixes to files
under `D:\Anrakutei\access-modernization-kit` itself if you find and fix a real bug — not
the smoke-test scratch data.

Keep it light: the existing fixture below has exactly two tiny source files. Do not invent
a larger one. Do not run this at production rigor (exhaustive VBA cross-checking, full
multi-agent parallelism) — the point is to prove the two pipelines connect correctly, not
to produce a publishable Phase document.

## Step 1 — Use the existing light fixture, don't create new sample data

`plugins/ak/examples/minimal-app/` already exists for exactly this purpose:
- `manifest.yaml` — `app.id: "DEMO"`, Graphify and multi-agent both enabled, 8 human
  checkpoints declared.
- `sources/vba/DemoOrderForm.bas` — one tiny synthetic form.
- `sources/sql/demo_orders.sql` — one tiny synthetic table.

Copy this directory into your scratch workspace as `DEMO/`. Edit **your copy** of
`manifest.yaml` only, not the one in the repo:
- Set `multi_agent.human_checkpoints: []` and `multi_agent.max_parallel: 1` — a real smoke
  run should not stop and wait for input at 8 points.
- Leave `graphify.enabled: true` — it is the mandatory phase gate; do not fake around it.
  If Graphify's managed runtime needs to install on first use, let it — that itself is
  part of what a real run exercises. If it fails or times out, that is a real finding, not
  a blocker to route around.

## Step 2 — Run the deterministic setup steps for real

These are real CLI commands (`plugins/ak/scripts/ak.py`), not chat-trigger phrases — run
them directly:

```bash
python D:/Anrakutei/access-modernization-kit/plugins/ak/scripts/ak.py init DEMO --source <scratch>/DEMO
python D:/Anrakutei/access-modernization-kit/plugins/ak/scripts/ak.py preflight DEMO
python D:/Anrakutei/access-modernization-kit/plugins/ak/scripts/ak.py acquire DEMO
```

(Consult `python .../ak.py <subcommand> --help` for exact flags — do not guess syntax.)

## Step 3 — Run the six phases for real, yourself, as the `investigate` skill

`ak.py` has no `run`/`phase` subcommand on purpose — analyzing legacy VBA/SQL and writing
Phase documents is agent work, not a deterministic script. Read `plugins/ak/skills/investigate/SKILL.md`
and `plugins/ak/specifications/senior-system-analyst-instruction.md`, then produce, for real,
for app `DEMO`:

- Phase 1–6 documents, named per `plugins/ak/specifications/output-contract.yaml`:
  `DEMO_Phase1_DataUnderstanding_EN.md` … `DEMO_Phase6_Synthesis_EN.md`. **Phase 2 §1
  "Screen, Form, and Report Inventory" must have at least one real row** derived from
  `DemoOrderForm.bas` — this is the one table `scan_phase2_inventory.py` actually parses.
- `DEMO_Evidence.json`, `DEMO_TraceabilityMatrix.csv`, `DEMO_QuestionList.md`, `DEMO_QA_Report.md`.
- `run-state.json` with `phase_gates.phase2`, `.phase4`, `.phase6` all reaching `"PUBLISHED"`.

It is fine for this to be a thin, honest pass over two tiny files — do not pad it. It is
not fine to fabricate the phase_gates state without actually producing the content those
gates certify.

Note the exact directory this output lands in — that is your `AK_RUN_DIR` for Step 4.

## Step 4 — Bootstrap a modernize project from that real output

In a **separate** scratch directory (e.g. `<scratch>/modernize-target/`), invoke the
`bootstrap-project` skill (`plugins/ak/skills/bootstrap-project/SKILL.md`) with:
- `DOCS_DIR` = e.g. `<scratch>/modernize-target/demo_docs`
- `AK_RUN_DIR` = the directory from Step 3
- `PROJECT_NAME` = `Synthetic Order Demo`, `SUBSYSTEM_CODE` = `DEMO`, `LEGACY_VARIANT` = `split-mdb` or whatever matches the fixture's actual shape (check `manifest.yaml` / the source files — do not guess this either)

Verify concretely, don't just trust the skill's own "done" claim:

1. **File discovery** — `scan_phase2_inventory.py` must find `DEMO_Phase2_ScreenAnalysis_EN.md`
   by substring match, not fail with "no phase2*.md document found."
2. **Registry seeding** — `Screens_Registry.md` gets a real row for the screen found in
   Phase 2. Check `screen_key` derivation (PascalCase-split if the object name is ASCII;
   `screen_<row ID>` fallback if not), `module`/`module_prefix` (`UNASSIGNED` if
   `PROJECT_CONFIG.md`'s Modules table is still empty at seed time — expected on a fresh
   bootstrap, not a bug), `url_segment`/`fe_route` derived from `screen_key`.
3. **The one accept gate** — confirm the skill actually stops and shows the proposed table
   before writing, rather than writing silently.
4. **`CLAUDE.md`/`AGENTS.md` wiring** — run this part twice to exercise both paths:
   - First run, no existing `CLAUDE.md`: confirm it gets **created** containing only the
     `<!-- modernize-plugin:start/end -->` block.
   - Add unrelated hand-written content to that `CLAUDE.md`, then re-run bootstrap (or
     just re-invoke this step): confirm the unrelated content is untouched and only the
     text between the markers changes — not appended a second time, not duplicated.
5. Run the `validate-docs` skill against `<scratch>/modernize-target/demo_docs`. It will
   report real findings (this is a fresh, mostly-unfilled project) — read them, confirm
   they are the *expected* kind (unfilled `PROJECT_CONFIG.md` placeholders, not a crash or
   a nonsensical finding), not that the count is zero.

## Step 5 — Report and, only if something is actually broken, fix it

Write a plain summary: what ran, what the real Phase 2 inventory row looked like, what
`Screens_Registry.md` ended up containing, which of the 5 checks above passed as-is.

If you find a real bug in `plugins/ak/modernize/scripts/scan_phase2_inventory.py`, the
`bootstrap-project` SKILL.md, or elsewhere under `D:\Anrakutei\access-modernization-kit`:
fix it there (not in the scratch copy), then before committing:

```bash
python plugins/ak/scripts/validate_structure.py --package plugins/ak --repository-root .
python -m pytest -q
```

Both must pass. Commit with a message in this repo's established style (`type(scope):
summary`, body explaining what broke and why, `Co-Authored-By: Claude Sonnet 5
<noreply@anthropic.com>`), push to `main`, and update `plugins/ak/modernize/BACKLOG.md`'s
D2 entry to mark the smoke test done — name the specific bug found and fixed, or state
plainly that all 5 checks passed clean on the first real run.

If nothing is broken: do not force a fix to justify the exercise. Update BACKLOG.md saying
so, and stop there — no commit needed for a clean run with no code changes.

## Do not

- Do not invent bigger sample data than the existing `examples/minimal-app` fixture.
- Do not fake `phase_gates` to `PUBLISHED` without actually producing the phase content.
- Do not commit anything from the scratch directories.
- Do not skip re-running the two verification commands in Step 5 before pushing, even for
  a one-line fix.
