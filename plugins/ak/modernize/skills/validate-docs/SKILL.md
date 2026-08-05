---
name: validate-docs
description: "Check a bootstrapped modernization project's documentation set for defects a reader will not notice — unfilled config keys, unresolved placeholders, dangling document references, malformed or duplicated issue rows, issue numbers cited by code with no row, resolved rows citing files that no longer exist, an unparseable screen registry, and missing artifact folders. Trigger when the user wants to validate, check, audit or lint the docs, before or after bootstrapping a project, before a release, or when a document seems out of step with the code. Examples: \"/validate-docs\", \"check the a01_docs set\", \"is the registry still valid\", \"did we leave any placeholder unfilled\"."
---

# Validate The Documentation Set

Run the checker, read its report, and present findings for a human to decide on. This
skill **never repairs anything**. Machine detects, human decides, agent executes — a fix
is a separate, explicitly requested action.

## Step 1 — Locate the three roots

| Root | What it is | How to find it |
|---|---|---|
| docs | the per-screen artifact directory | `DOCS_DIR` in `PROJECT_CONFIG.md`, e.g. `a01_docs` |
| plugin | this plugin's own tree | the directory containing `docs/` and `templates/` |
| source | the code tree | `BACKEND_ROOT` and `FRONTEND_ROOT`'s common ancestor |

The plugin root is optional but two checks degrade without it: `dead-config-key` is
skipped entirely, because a resolved project has no placeholders left and every key
would look unread. The source root is optional; without it `dangling-issue-ref` and
`stale-resolved-anchor` are skipped.

## Step 2 — Run it

```bash
python "${CLAUDE_PLUGIN_ROOT}/modernize/scripts/validate_docs.py" \
  --docs-dir <docs> --plugin-dir "${CLAUDE_PLUGIN_ROOT}/modernize" --source-dir <source> \
  --report <docs>/../validate-docs-report.md
```

Exit status is 0 when clean, 1 when there are findings, 2 when it could not run. A
non-zero status on findings is intentional so a caller can gate on it.

The console summary is deliberately ASCII-only and the report is UTF-8. A Japanese
screen name printed to a cp932 console raises `UnicodeEncodeError`, which would turn a
successful check into a crash — read details from the report, not the console.

## Step 3 — Present findings, do not fix them

Group by severity. For each finding give the location, what is wrong, and the smallest
action that would resolve it. Then stop and ask which ones to act on.

| Severity | Meaning |
|---|---|
| HIGH | a stage would guess, or read the wrong thing: unfilled config key, a document consuming an undeclared key, duplicate issue number, code citing a non-existent issue, unparseable or duplicate-keyed registry, missing artifact folder |
| MEDIUM | a reader is misled but no stage misbehaves: unresolved placeholder in an instance document, dangling document reference, malformed or unknown-status issue row, missing folder README |
| LOW | hygiene: a config key nothing reads, a resolved row citing a file that has moved |

## What each check catches, and why it exists

Every check corresponds to a defect that actually occurred, not one that seemed
plausible. When reporting, it helps to say which real failure the check descends from.

- **unfilled config key** — a downstream stage guesses a path. `PROJECT_CONFIG.md` is the
  one file authored by hand, and a wrong path writes files into the wrong place silently.
- **missing-config-key** — a method document reads `{{X}}` that no config row declares,
  so the substitution can never happen.
- **dead-config-key** — the project must fill a key nothing reads. This is not merely
  untidy: a key implies a capability. Asking for an API collection tool suggests the
  pipeline maintains one when nothing does.
- **dangling-doc-ref** — an artifact cites a document that was deleted or renamed. Found
  nine references to removed planning files in a real project.
- **issue-row-malformed / duplicate / unknown-status** — one row with nine columns
  instead of ten rendered wrongly and went unnoticed for weeks.
- **dangling-issue-ref** — five code comments cited an issue number before the row
  existed. Code that points at nothing is worse than code with no pointer.
- **stale-resolved-anchor** — a row marked resolved cites a file that no longer exists,
  which is how a row came to describe code that had been reverted. Found a row citing
  `test_purchasing_data_views.py` after it was renamed to `..._services.py`.
- **registry checks** — the registry is the single source of truth for screen identity.
  A parse failure there silently mis-scopes every stage.

## Known limits — state these when reporting

The checker is deliberately simple and its precision is not perfect. Say so rather than
presenting output as authoritative.

- **Prose mentions of a filename** are hard to separate from real references. A bare
  lowercase name like `legacy.md` is skipped as illustrative, but a capitalised one such
  as `Test_Instruction.md` written to mean "the per-screen artifact" is still reported.
  Treat `dangling-doc-ref` as advisory and read the citing line before acting.
- **A renamed file** looks identical to a deleted one. `stale-resolved-anchor` says the
  path is absent, not that the work was undone.
- **No semantic checking.** It cannot tell whether a business flow is correct, only
  whether its references resolve. Coverage of legacy behaviour is the job of the
  traceback gates, not of this skill.
- **It cannot see into a resolved instance's history.** Whether a `resolved` row is
  honest requires reading the code, which the gates and review stage do.

## Do not

- Do not fix anything, reformat anything, or create a missing file as a side effect of
  running this. Report and wait.
- Do not run the fixer-style tools of the project — no formatter, no `--fix` flag — as
  part of validation. In this project a formatter run over a whole change list
  reformatted seven files belonging to other people's work in progress.
- Do not treat exit status 1 as failure of the run. It means findings exist. And when
  reading the status through a shell pipe, remember the status belongs to the last
  command in the pipe — `... | head` reports `head`'s status, not the checker's.
- Do not point `--docs-dir` at this plugin's own `templates/` directory. Templates are
  unfilled by design, so the run reports hundreds of findings that are all correct and
  all meaningless. `--docs-dir` takes a **bootstrapped project's** artifact directory.
