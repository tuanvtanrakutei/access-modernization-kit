---
name: bootstrap-project
description: "Set up a brand-new modernization project - copy the template documents into a target repo's docs directory, and seed Screens_Registry.md from a six-phase run's Phase 2 inventory when one exists. Trigger when the user wants to start a new Access-family modernization project, bootstrap a project, or set up the docs folder for a new subsystem before running the pipeline for the first time. Examples: \"bootstrap a new project for A05\", \"set up the modernize docs for this repo\", \"seed the screens registry from the six-phase run\"."
---

# Bootstrap A New Modernization Project

Runs once, before Stage 1 ever runs for any screen. This is the one moment a wrong path
silently writes files into the wrong place, so every write here is defensive: refuse
rather than guess, and never overwrite an existing project's config.

This skill does not run `validate-docs` itself and does not run any pipeline stage. It
ends by telling the user to run `validate-docs` next.

## Step 0 — Defensive precondition

Before writing anything, check whether `{{DOCS_DIR}}/PROJECT_CONFIG.md` already exists at
the target path. If it does, **stop** and report it — this is very likely either a
repeat invocation or the wrong target path, and both call for the user's eyes, not a
silent overwrite. Do not proceed past this check on assumption.

## Step 1 — Collect the required inputs

1. **Target docs directory** — where `{{DOCS_DIR}}` will live in the target repo. Ask if
   not given.
2. **`AK_RUN_DIR`** — the root of a six-phase `ak` run for this project, or the literal
   `n/a` if Stage 0 will be manual export per `LEGACY_EVIDENCE.md`. Ask if not given. Do
   not guess `n/a` by default — an unanswered question is not the same as a real "no
   phase output exists yet."
3. **`PROJECT_NAME`, `SUBSYSTEM_CODE`, `LEGACY_VARIANT`** — ask if not given. These three,
   plus the two above, are the only values this skill ever writes into
   `PROJECT_CONFIG.md` on the user's behalf (Step 2) and the only ones the Step 4 CLAUDE.md
   pointer block needs — everything else in `PROJECT_CONFIG.md` stays hand-authored. Asking
   for these five up front, rather than the two alone, is what makes Step 4 possible without
   a second round trip once `PROJECT_CONFIG.md` is filled later.

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
| `Business_flows_README.md` | `{{DOCS_DIR}}/Business_flows/README.md` |
| `Screen_plans_README.md` | `{{DOCS_DIR}}/Screen_plans/README.md` |
| `Coding_Records_README.md` | `{{DOCS_DIR}}/Coding_Records/README.md` |
| `Test_Instruction_README.md` | `{{DOCS_DIR}}/Test_Instruction/README.md` |
| `Code_Review_README.md` | `{{DOCS_DIR}}/Code_Review/README.md` |
| `Final_Acceptance_README.md` | `{{DOCS_DIR}}/Final_Acceptance/README.md` |
| `Bug_Reports_README.md` | `{{DOCS_DIR}}/Bug_Reports/README.md` |

Create the seven per-screen folders named above if they do not exist. Do not auto-fill
`PROJECT_CONFIG.md`'s `{{...}}` placeholders beyond the five values collected in Step 1
(`DOCS_DIR`, `AK_RUN_DIR`, `PROJECT_NAME`, `SUBSYSTEM_CODE`, `LEGACY_VARIANT` — write each
directly into its own row) — it remains, by design, the one file the user authors by hand
for everything else. Filling the rest here would silently write a guess into the file whose
whole job is to never contain one.

## Step 3 — Seed `Screens_Registry.md`

This step is the reason this skill exists rather than being five manual copy commands.
Phase 2's content is trustworthy on its own — this step only runs once its gate reads
`PUBLISHED`, meaning `ak`'s own six-phase process already QA'd it — so `screen`, `type`,
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
- The `PROJECT_CONFIG.md` Validation Checklist, unchanged from the template, as the
  user's next concrete action.
- That `validate-docs` should be run next, once `PROJECT_CONFIG.md` is filled.

## Do not

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
