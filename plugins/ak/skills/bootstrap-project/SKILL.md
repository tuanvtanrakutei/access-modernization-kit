---
name: bootstrap-project
description: "Set up a brand-new modernization project - copy the template documents into a target repo's docs directory, and seed Screens_Registry.md from a five-phase run's Phase 2 inventory when one exists. Trigger when the user wants to start a new Access-family modernization project, bootstrap a project, or set up the docs folder for a new subsystem before running the pipeline for the first time. Examples: \"bootstrap a new project for A99\", \"set up the modernize docs for this repo\", \"seed the screens registry from the five-phase run\"."
---

# Bootstrap A New Modernization Project

Runs once, before Stage 1 ever runs for any screen. This is the one moment a wrong path
silently writes files into the wrong place, so every write here is defensive: refuse
rather than guess, and never overwrite an existing project's config.

The developer's part is a handful of replies: confirm the detected inputs, accept the
proposed configuration, accept the registry, accept the `CLAUDE.md` pointer. Everything
else — detecting, copying, substituting, checking — is this skill's. It runs the
`validate-docs` checker itself at the end (read-only) and does not run any pipeline stage.

## Step 0 — Defensive precondition

Before writing anything, check whether `{{DOCS_DIR}}/PROJECT_CONFIG.md` already exists at
the target path. If it does, **stop** and report it — this is very likely either a
repeat invocation or the wrong target path, and both call for the user's eyes, not a
silent overwrite. Do not proceed past this check on assumption.

## Step 1 — Detect the required inputs, then confirm them once

Detect each of the five values below before asking for any of them, and show them as one
table — value, and the file or search it came from — with one `ok` / `edit field=value`.
Ask only for a value nothing on disk answers. Where to look:

- `AK_RUN_DIR`: a directory holding a `run-state.json` under the repository or a path the user
  named. More than one found → list them and ask which; none → ask, as below.
- `SUBSYSTEM_CODE`, `PROJECT_NAME`, `LEGACY_VARIANT`: the five-phase workspace's `manifest.yaml`
  (its app id, name and source files) when `AK_RUN_DIR` was found; the legacy file's extension
  (`.adp`, `.mdb`, `.accdb`, a split pair) otherwise.
- The docs directory: as point 1 below.

1. **Target docs directory** — where `{{DOCS_DIR}}` will live in the target repo. Ask if
   not given, and offer `docs` at the repository root. Offer a prefixed name
   (`<project>_docs`) only when the repository already has a `docs/` of its own that is not
   this kit's: say that is the reason, so the prefix is not copied as a convention.
2. **`AK_RUN_DIR`** — the root of a five-phase `ak` run for this project, or the literal
   `n/a` if Stage 0 will be manual export per `LEGACY_EVIDENCE.md`. Ask if not detected. Do
   not guess `n/a` by default — an unanswered question is not the same as a real "no
   phase output exists yet."
3. **`PROJECT_NAME`, `SUBSYSTEM_CODE`, `LEGACY_VARIANT`** — ask if not detected. These three,
   plus the two above, are written into `PROJECT_CONFIG.md` in Step 2 and are the only ones
   the Step 4 CLAUDE.md pointer block needs; every other row is proposed in Step 2b and
   written only on the user's `ok`.

## Step 2 — Copy templates

Copy, unfilled, from `${CLAUDE_PLUGIN_ROOT}/modernize/templates/` into the target docs
directory:

| Template | Becomes |
|---|---|
| `PROJECT_CONFIG.md` | `{{DOCS_DIR}}/PROJECT_CONFIG.md` |
| `ARCHITECTURE.md` | `{{DOCS_DIR}}/ARCHITECTURE.md` |
| `Screens_Registry.md` | `{{DOCS_DIR}}/Screens_Registry.md` |
| `Known_Issues.md` | `{{DOCS_DIR}}/Known_Issues.md` |
| `Known_Issues_Archive.md` | `{{DOCS_DIR}}/Known_Issues_Archive.md` (starts empty by design) |
| `DOCS_README.md` | `{{DOCS_DIR}}/README.md` |
| `Screen_plans_README.md` | `{{DOCS_DIR}}/Screen_plans/README.md` |
| `Coding_Records_README.md` | `{{DOCS_DIR}}/Coding_Records/README.md` |
| `Test_Instruction_README.md` | `{{DOCS_DIR}}/Test_Instruction/README.md` |
| `Code_Review_README.md` | `{{DOCS_DIR}}/Code_Review/README.md` |
| `Final_Acceptance_README.md` | `{{DOCS_DIR}}/Final_Acceptance/README.md` |
| `Bug_Reports_README.md` | `{{DOCS_DIR}}/Bug_Reports/README.md` |

And copy, unchanged, from `${CLAUDE_PLUGIN_ROOT}/modernize/docs/` into the same directory:

| Document | Becomes |
|---|---|
| `MASTER_WORKFLOW.md` | `{{DOCS_DIR}}/MASTER_WORKFLOW.md` |
| `TRACEBACK_GATES.md` | `{{DOCS_DIR}}/TRACEBACK_GATES.md` |
| `LEGACY_EVIDENCE.md` | `{{DOCS_DIR}}/LEGACY_EVIDENCE.md` |
| `BACKEND_CODING.md` | `{{DOCS_DIR}}/BACKEND_CODING.md` |
| `BACKEND_TESTING.md` | `{{DOCS_DIR}}/BACKEND_TESTING.md` |
| `FRONTEND_CODING.md` | `{{DOCS_DIR}}/FRONTEND_CODING.md` |
| `FRONTEND_TESTING.md` | `{{DOCS_DIR}}/FRONTEND_TESTING.md` |
| `CONVENTIONS.md` | `{{DOCS_DIR}}/CONVENTIONS.md` |
| `PHASE_OUTPUT_GUIDE.md` | `{{DOCS_DIR}}/PHASE_OUTPUT_GUIDE.md` |

These are not optional extras. `PROJECT_CONFIG.md` §11 states the document map uses fixed
names *because the pipeline documents reference each other directly*, and
`MASTER_WORKFLOW.md` cites its siblings by bare filename twelve times. Copying the
templates without them produces a project whose own `README.md` and `CLAUDE.md` pointer
both name `MASTER_WORKFLOW.md` and whose `MASTER_WORKFLOW.md` is not there — which is what
one project got. A project holds its own copies so that a plugin upgrade cannot silently change
the manual a half-finished screen was planned against.

Copy them **unsubstituted**, like every other template here. They carry `{{...}}` keys that
resolve from `PROJECT_CONFIG.md`, and at this point only five of its rows are filled. Step 2b
resolves them once the rest of the config is accepted; a key nobody filled stays as `{{KEY}}`,
and Step 5's `validate-docs` run lists it.

Create the seven per-screen folders named above if they do not exist. Write the five values
from Step 1 (`DOCS_DIR`, `AK_RUN_DIR`, `PROJECT_NAME`, `SUBSYSTEM_CODE`, `LEGACY_VARIANT`)
directly into their own rows of `PROJECT_CONFIG.md`. The rest are proposed in Step 2b, never
written silently: this is the file whose whole job is to never contain a guess.

## Step 2b — Propose the rest of `PROJECT_CONFIG.md` from the repository

Most rows are already answered by the target repository. Read it and propose a value for
every row it answers, citing the file and line each came from:

| Rows | Where the answer usually is |
|---|---|
| `BACKEND_ROOT`, `API_PREFIX`, `USE_TZ`, `TIMEZONE`, `MODEL_BASE_CLASS`, `RESPONSE_CLASS`, `PAGINATION_CLASS`, `PERMISSION_DECORATOR` | `manage.py`, the root `urls.py`, the Django settings module, `REST_FRAMEWORK` in settings, the common base classes the existing apps import |
| `LINT_CMD`, `TEST_CMD`, `MAX_LINE_LENGTH` | `pyproject.toml` / `setup.cfg` / `tox.ini` (ruff, flake8, black, pytest), a `scripts/` folder, a `Makefile`, the CI file |
| `FRONTEND_ROOT`, `PACKAGE_MANAGER`, `FE_LINT_CMD`, `FE_UNIT_TEST_CMD`, `FE_E2E_TEST_CMD`, `FE_*_LIB`, `I18N_LIB` | `package.json` scripts and dependencies, the lock file present, `playwright.config.*`, `vite.config.*` |
| `SOURCE_ENCODING`, `EVIDENCE_*_DIR` | the five-phase workspace's `manifest.yaml` and `input/` folders |
| Modules table (§3) | the Django apps under `BACKEND_ROOT` |

Show the proposal as one table — row, proposed value, source — then, separately, the rows
nothing on disk answers (policy rows such as `MIGRATIONS_POLICY`, `REFERENCE_DB_POLICY`,
`MISSING_MODEL_ESCALATION`, `SCHEMA_OWNED` usually are), each with the template's own example
as the suggested answer. Wait for one reply:

- `ok` — write every proposed value; the unanswered rows keep their `{{...}}`.
- `edit ROW=value ...` — change those, show the table again.
- `cancel` — write nothing from this step; the user fills the file by hand.

Never write a row the repository did not answer and the user did not give: an unfilled
`{{...}}` makes a later stage stop and ask, a wrong value makes it write to the wrong place.

**Then resolve the copied documents.** For every row now filled, replace its `{{KEY}}` in
the documents this skill copied (not in `PROJECT_CONFIG.md`, and not in the plugin's own
templates). A key still unfilled stays as `{{KEY}}`, and Step 5's `validate-docs` run lists
it.

## Step 3 — Seed `Screens_Registry.md`

This step is the reason this skill exists rather than being five manual copy commands.
Phase 2's content is trustworthy on its own — this step only runs once its gate reads
`PUBLISHED`, meaning `ak`'s own five-phase process already QA'd it — so `screen`, `type`,
`business_purpose`, `entry_path` and `evidence_ids` are taken as given, not re-confirmed.
`screen_key`, `url_segment` and `fe_route` are mechanical derivations with no real
ambiguity once computed (see the script's own docstring for exactly how). The **one**
thing left to a human is `module`: which new-system Django app a legacy screen belongs to
is an architecture decision Phase 2 cannot know, and a wrong one costs real rework once
code lands there. So this step produces one accept, covering the whole table, not one
question per row or per field.

**Before running this step**, make sure `PROJECT_CONFIG.md` section 3's Modules table is
filled — the module guess has nothing to score against otherwise, and every row falls
back to the literal `UNASSIGNED` placeholder. This is not a blocking requirement; a
bootstrap run started before the modules are decided still produces a complete, valid
registry, just one where every `module` cell reads `UNASSIGNED` until this step is
re-run.

**If `AK_RUN_DIR` is `n/a`:** skip this step entirely. Leave `Screens_Registry.md`'s
Active Screens table exactly as the template ships it — one placeholder example row plus
the empty row beneath it. Say so plainly in the final report: registry seeding did not
run, rows must be added by hand or via Agent-Assisted Registration per screen.

**Otherwise, detect:**

```bash
python "${CLAUDE_PLUGIN_ROOT}/modernize/scripts/scan_phase2_inventory.py" \
  --ak-run-dir <AK_RUN_DIR> --screen-key-case {{SCREEN_KEY_CASE}} \
  --project-config <target>/{{DOCS_DIR}}/PROJECT_CONFIG.md \
  --out <target>/{{DOCS_DIR}}/bootstrap-registry-proposal.json
```

Branch on exit status:

| Exit | Meaning | Action |
|---|---|---|
| `0` | Proposal written, every row fully filled | Continue to Propose below |
| `1` | Phase 2 gate is not `PUBLISHED` yet | Stop this step, do not seed. Report which gate value blocked it. This is expected mid-run, not a bug — proceed with the rest of bootstrap, seed later by re-running this step alone |
| `2` | Could not parse (missing `run-state.json`, missing or malformed Phase 2 document) | Stop this step, show the stderr message, ask the user whether to fall back to manual seeding for this run rather than treating it as a hard failure of the whole skill |

**Propose — one table, one accept.** Read the JSON at `--out` and print every row:
`priority`, `screen`, `screen_key`, `type`, `module`, `module_prefix`, `fe_route`. `type`
is shown for context only — Phase 2 lists forms and reports alike, and whether a given
legacy Report becomes its own screen in the new system is the one judgment call folded
into this same accept, not a separate question. Call out plainly, once, at the top of the
table rather than per row:

- how many rows have `module: UNASSIGNED` and therefore need a manual edit after writing;
- how many rows used the non-ASCII `screen_key` fallback (`screen_N`) and may be worth a
  more readable rename later, at no risk since nothing reads that name until Stage 1 runs
  for that screen.

Wait. Offer exactly two replies:

- `ok` — write the whole table as shown, `UNASSIGNED` cells and all. A row that needs a
  real module is now visible and grep-able in `Screens_Registry.md` itself, which is
  strictly easier to act on than a row that was never written at all.
- `cancel` — write nothing from this step; `Screens_Registry.md` keeps its template
  skeleton, same as the `n/a` path. Offer this when the user would rather fill
  `PROJECT_CONFIG.md` section 3 first and re-run than accept `UNASSIGNED` placeholders.

There is no per-row edit step here. If one row's guess is wrong, editing the Markdown
table directly afterward is exactly as fast as a chat-based edit round trip, and does not
add a third reply the human must learn.

**Apply.** On `ok`, insert every row into the Active Screens table sorted by `priority`,
`status_be` and `status_fe` both `not_started` for every row (this is a new project — no
code exists yet, unlike Agent-Assisted Registration's on-demand case which must check for
pre-existing code). Delete `bootstrap-registry-proposal.json` once applied — it is a
working file, not a project artifact, and leaving it invites confusion with
`Screens_Registry.md` itself as the source of truth.

## Step 4 — Wire `CLAUDE.md` / `AGENTS.md`

Neither file is auto-loaded from `{{DOCS_DIR}}` — only a root `CLAUDE.md` (and, on a project
that also targets Codex, `AGENTS.md`) is loaded automatically at the start of a session. Without
a pointer there, a freshly bootstrapped project has **no** standing awareness of its own scope
boundary or where its pipeline docs live, until a skill's own trigger phrase happens to match
what the user types. This step closes that gap with the smallest write that does — a pointer,
not a copy of content that already lives elsewhere.

**Locate the target.** Both files, if they exist, sit next to the directory that contains
`{{DOCS_DIR}}` — not necessarily the repository root; a project's actual source checkout can
sit one level below its documentation/workspace root, and this skill has no way to know which
without being told. Ask if it is not obvious from context.

**Detect.** For each of `CLAUDE.md` and `AGENTS.md` at that location:

| State | Action |
|---|---|
| File does not exist | Will be **created**, containing only the block below |
| File exists, no `<!-- modernize-plugin:start -->` marker | Block will be **appended** to the end, every existing byte preserved |
| File exists, marker found | Only the text between `<!-- modernize-plugin:start -->` and `<!-- modernize-plugin:end -->` will be **replaced**; everything outside those markers is untouched |

**Propose — one preview, one accept, covering both files.** Print the exact block that will
be written, resolved from Step 1's five values:

```markdown
<!-- modernize-plugin:start -->
## {{PROJECT_NAME}} ({{SUBSYSTEM_CODE}}) — Modernization Pipeline

This subsystem is being modernized from a legacy {{LEGACY_VARIANT}} Access application via the
`ak` modernize pipeline. Entry point for all design/planning docs: `{{DOCS_DIR}}/README.md` —
read it before `{{DOCS_DIR}}/MASTER_WORKFLOW.md`, which is the operational manual, not the
introduction.

The fixed scope and architecture boundary for this subsystem are in
`{{DOCS_DIR}}/ARCHITECTURE.md` — non-negotiable, read before any cross-subsystem-adjacent
change.

When asked to implement, refresh, test, or review a screen: look it up in
`{{DOCS_DIR}}/Screens_Registry.md` first, then follow `{{DOCS_DIR}}/MASTER_WORKFLOW.md`'s
Pre-Flight Check. Do not skip pre-flight even for a small change.
<!-- modernize-plugin:end -->
```

State plainly, per file, which of the three actions above will happen. This is the one accept
in this skill with the highest stakes of anything it writes — `CLAUDE.md`/`AGENTS.md` color
every future session in the repo, not just this one project, so a wrong pointer is far more
expensive to leave unnoticed than a wrong `Screens_Registry.md` row.

Wait. Offer exactly two replies, same shape as Step 3:

- `ok` — write to both files as previewed (create, append, or update-in-place, per file, as
  detected above).
- `cancel` — write nothing from this step. Note in Step 5's report that the project has no
  automatic pointer yet, and that Agent-Assisted Registration and the skills' own trigger
  phrases remain the only discovery paths until this step is re-run.

**If only one of the two files exists** (commonly `CLAUDE.md` without `AGENTS.md`, or vice
versa), still only touch the one(s) that exist or are being created — do not invent a
Codex-specific file for a project that has never used one, and do not skip `AGENTS.md` if it
already exists just because this step's primary audience is Claude Code. A project's own
`AGENTS.md`, if present, may already declare its own sync rule with `CLAUDE.md` (as this
project's real instance does — "whenever CLAUDE.md is changed, update this AGENTS.md file in
the same turn"); writing the identical block to both honors that rule rather than requiring
the user to notice and repeat it.

## Step 5 — Report

State plainly, in one place:

- Which files were copied and where.
- Whether registry seeding ran, and if so, how many rows were written, how many read
  `module: UNASSIGNED`, and how many used the non-ASCII `screen_key` fallback (name them
  — do not just give a count).
- Whether `CLAUDE.md`/`AGENTS.md` were created, appended to, updated, or left untouched
  (`cancel`), per file.
- The `PROJECT_CONFIG.md` Validation Checklist, **run, not handed over**: run `LINT_CMD`,
  `TEST_CMD` and `FE_E2E_TEST_CMD` once each when they are filled, check each §3 module
  directory and each evidence directory exists, count the registry rows. Report every item
  as passed, failed (with the output line), or not checkable yet (its row is unfilled). A
  command that fails here is reported, not fixed.
- The `validate-docs` result: run `validate_docs.py` as the `validate-docs` skill does (it
  only reads) and give the finding counts by severity, with the report's path.
- The one next action, as a line to paste: the rows still unfilled if any, otherwise
  `/ak:modernize-screen <first screen by priority>`.
- Whether the docs directory would be sent to a Docker build. If the repository has a
  Dockerfile or a compose file whose build context contains the docs directory, and its
  `.dockerignore` does not leave the directory out, say so: git ignoring the directory does
  not keep it out of an image, and its `input/` holds the customer's data. Suggest the
  `.dockerignore` line; do not edit the file, it belongs to the project.

## Do not

- Do not write a `PROJECT_CONFIG.md` row from a guess. A value comes from a file on disk
  that you cite, or from the user; anything else stays `{{...}}`.
- Do not overwrite an existing `PROJECT_CONFIG.md`. Step 0 exists precisely so this
  never becomes an agent judgment call under time pressure.
- Do not silently pick a module for an `UNASSIGNED` row. Writing the sentinel is
  automation; guessing quietly and calling it certain is not — the whole reason `module`
  is the one field routed through an accept is that a wrong one is expensive once code
  lands there.
- Do not run any pipeline stage as part of bootstrap. Bootstrap ends at a
  registry ready for Stage 1, not at Stage 1 itself.
- Do not treat `scan_phase2_inventory.py` exit status 1 as an error. It is the expected
  outcome for an `n/a` project or a run still mid-flight.
- Do not write to `CLAUDE.md`/`AGENTS.md` outside the `<!-- modernize-plugin:start -->` /
  `<!-- modernize-plugin:end -->` markers. Everything outside them may be hand-written
  project content (dev commands, environment variables, architecture notes) that has
  nothing to do with this plugin — the marker pair exists precisely so this skill never has
  to read, understand, or risk the rest of the file to make its one edit.
- Do not restate `ARCHITECTURE.md`'s actual rules or `{{DOCS_DIR}}/README.md`'s doc map
  inside the `CLAUDE.md` block. Point at them instead. A second copy of either is a second
  place to go stale the moment the original is edited.
