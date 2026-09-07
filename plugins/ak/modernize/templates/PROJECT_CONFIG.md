# PROJECT_CONFIG

> **Fill every `{{...}}` before running the pipeline.** This file is the single source of all project-specific values. Generic pipeline documents reference these as placeholders and resolve them by reading this file at pre-flight.
>
> If a value genuinely does not apply, write `n/a` and one clause explaining why. Do not delete the row — a missing row and an intentionally-absent value look identical to an agent, and it will stop to ask.

Copy this file to your project's documentation root. Keep it under version control.

## 1. Project Identity

| Key | Value | Notes |
|---|---|---|
| `PROJECT_NAME` | `{{PROJECT_NAME}}` | Human-readable, e.g. "SMS Replacement — Order Receiving" |
| `SUBSYSTEM_CODE` | `{{SUBSYSTEM_CODE}}` | Short code used in paths and identifiers, e.g. `A01` |
| `DOCS_DIR` | `{{DOCS_DIR}}` | Where per-screen artifacts live, e.g. `a01_docs` |
| `SCREEN_NAME_LANG` | `{{SCREEN_NAME_LANG}}` | Language of screen names used as filenames, e.g. `ja`, `en` |

## 2. Legacy Source

| Key | Value | Notes |
|---|---|---|
| `LEGACY_VARIANT` | `{{LEGACY_VARIANT}}` | One of: `adp`, `mdb`, `accdb`, `split-mdb`, `split-accdb`. Drives evidence taxonomy — see `LEGACY_EVIDENCE.md`. |
| `LEGACY_FE_FILE` | `{{LEGACY_FE_FILE}}` | Front-end file name, e.g. `SMS_A01.adp` |
| `LEGACY_DATA_FILE` | `{{LEGACY_DATA_FILE}}` | Data file for split designs; `n/a` for `adp` (data lives in SQL Server) |
| `LEGACY_DB_ENGINE` | `{{LEGACY_DB_ENGINE}}` | `sqlserver`, `jet`, or `ace` |
| `LEGACY_DB_SCRIPT` | `{{LEGACY_DB_SCRIPT}}` | Path to exported DDL, e.g. `{{DOCS_DIR}}/schema.sql`, or `n/a` |
| `SOURCE_ENCODING` | `{{SOURCE_ENCODING}}` | Codepage of exported VBA/text, e.g. `cp932` for Japanese, `cp1252` for Western European |

### Evidence Directories

| Key | Value | Contains |
|---|---|---|
| `EVIDENCE_CODE_DIR` | `{{EVIDENCE_CODE_DIR}}` | Exported forms, reports, VBA modules |
| `EVIDENCE_UI_DIR` | `{{EVIDENCE_UI_DIR}}` | Screenshots of the legacy UI |
| `EVIDENCE_OUTPUT_DIR` | `{{EVIDENCE_OUTPUT_DIR}}` | Legacy report output samples (PDF, Excel, text) |
| `EVIDENCE_INTERVIEW_DIR` | `{{EVIDENCE_INTERVIEW_DIR}}` | Recorded answers from named people, dated - the only class besides a document that can carry a claim about meaning, usage or intent. `n/a` if none have been recorded, which is the honest value on a project that has only exports |
| `EVIDENCE_DOCUMENT_DIR` | `{{EVIDENCE_DOCUMENT_DIR}}` | Business documents supplied for this application - operation manuals, data dictionaries, screen lists. `n/a` if none |
| `AK_RUN_DIR` | `{{AK_RUN_DIR}}` | Root of a six-phase analysis run (contains `run-state.json`, and `Evidence.json` / `TraceabilityMatrix.csv` if the enriched tier was produced), or `n/a` if Stage 0 was manual export per `LEGACY_EVIDENCE.md` §6 |

## 3. Target Backend

Fixed stack: Django + Django REST Framework + PostgreSQL.

| Key | Value | Notes |
|---|---|---|
| `BACKEND_ROOT` | `{{BACKEND_ROOT}}` | e.g. `backend/sms_a01` |
| `API_PREFIX` | `{{API_PREFIX}}` | e.g. `/api/v1/a01/` — every endpoint mounts under this |
| `TABLE_MAP_DOC` | `{{TABLE_MAP_DOC}}` | Legacy-to-new table/field mapping document |
| `LINT_CMD` | `{{LINT_CMD}}` | Exact command, e.g. `./scripts/lint.sh` from `backend/` |
| `TEST_CMD` | `{{TEST_CMD}}` | Exact command, e.g. `./scripts/test.sh <module_path>` |
| `MIGRATIONS_POLICY` | `{{MIGRATIONS_POLICY}}` | `owned` (this project creates migrations) or `external` (models and migrations belong to another module — do not create) |

### Modules

One row per Django app that owns screens. The pipeline uses `module` for parallelism partitioning and code placement.

| module | url prefix (after `API_PREFIX`) | owns |
|---|---|---|
| `{{MODULE_1}}` | `{{MODULE_1_PREFIX}}` | `{{MODULE_1_SCOPE}}` |
| `{{MODULE_2}}` | `{{MODULE_2_PREFIX}}` | `{{MODULE_2_SCOPE}}` |

### Shared Backend Components

| Key | Value | Notes |
|---|---|---|
| `RESPONSE_CLASS` | `{{RESPONSE_CLASS}}` | Standard API response wrapper, e.g. `{{DJANGO_PROJECT}}.utils.response.ApiResponse` |
| `PAGINATION_CLASS` | `{{PAGINATION_CLASS}}` | Default list pagination, e.g. `{{DJANGO_PROJECT}}.utils.paginations.CursorPagination` |
| `MODEL_BASE_CLASS` | `{{MODEL_BASE_CLASS}}` | Base class master models inherit, or `n/a` |
| `PERMISSION_DECORATOR` | `{{PERMISSION_DECORATOR}}` | e.g. `{{DJANGO_PROJECT}}.permissions.require_permission`, or `n/a` |
| `PERMISSION_CODE_ENUM` | `{{PERMISSION_CODE_ENUM}}` | Where permission codes are defined, or `n/a` |

## 4. Target Frontend

| Key | Value | Notes |
|---|---|---|
| `FRONTEND_ROOT` | `{{FRONTEND_ROOT}}` | e.g. `frontend/src` |
| `FE_ROUTE_BASE` | `{{FE_ROUTE_BASE}}` | e.g. `/a01` |
| `FE_PAGE_DIR` | `{{FE_PAGE_DIR}}` | Route-level components, e.g. `{{FRONTEND_ROOT}}/pages` |
| `FE_API_DIR` | `{{FE_API_DIR}}` | Typed API client modules |
| `FE_TYPES_DIR` | `{{FE_TYPES_DIR}}` | Shared TypeScript types |
| `FE_STATE_LIB` | `{{FE_STATE_LIB}}` | e.g. `Zustand` |
| `FE_QUERY_LIB` | `{{FE_QUERY_LIB}}` | e.g. `TanStack Query` |
| `FE_FORM_LIB` | `{{FE_FORM_LIB}}` | e.g. `react-hook-form + Zod` |
| `FE_STYLE_LIB` | `{{FE_STYLE_LIB}}` | e.g. `Tailwind CSS` |
| `FE_LINT_CMD` | `{{FE_LINT_CMD}}` | e.g. `npm run lint` |
| `FE_UNIT_TEST_CMD` | `{{FE_UNIT_TEST_CMD}}` | e.g. `npm run test`, or `n/a` |
| `FE_E2E_TEST_CMD` | `{{FE_E2E_TEST_CMD}}` | e.g. `npx playwright test` |
| `I18N_LIB` | `{{I18N_LIB}}` | e.g. `i18next`, or `n/a` if single-language |
| `FE_PATTERN_DOCS` | `{{FE_PATTERN_DOCS}}` | Project-owned documents holding **concrete** frontend patterns — component choices, hook names, file layout, message-constant organization. `FRONTEND_CODING.md` states principles and defers to these for specifics. Write `n/a` if none exist yet, and expect component choices to vary between screens until they do |
| `FE_REFERENCE_SCREEN` | `{{FE_REFERENCE_SCREEN}}` | A screen whose implementation is a good worked example of the project's form or table pattern, for a developer to copy from. `n/a` until one is nominated |

## 5. Database

| Key | Value | Notes |
|---|---|---|
| `SCHEMA_OWNED` | `{{SCHEMA_OWNED}}` | Schema this subsystem writes to |
| `SCHEMAS_READONLY` | `{{SCHEMAS_READONLY}}` | Schemas readable but never written, or `n/a` |
| `USE_TZ` | `{{USE_TZ}}` | `true` or `false` — decides naive vs aware datetimes |
| `TIMEZONE` | `{{TIMEZONE}}` | e.g. `Asia/Tokyo` |
| `PK_STRATEGY` | `{{PK_STRATEGY}}` | e.g. auto-increment `id`, business codes as separate unique indexed fields |

## 6. Naming Conventions

| Key | Value | Notes |
|---|---|---|
| `CODE_FIELD_SUFFIX` | `{{CODE_FIELD_SUFFIX}}` | e.g. `_cd` for business codes |
| `BOOL_FIELD_SUFFIX` | `{{BOOL_FIELD_SUFFIX}}` | e.g. `_flg` |
| `TIME_FIELD_SUFFIX` | `{{TIME_FIELD_SUFFIX}}` | e.g. `_time` |
| `MAX_LINE_LENGTH` | `{{MAX_LINE_LENGTH}}` | e.g. `120` |
| `VERBOSE_NAME_LANG` | `{{VERBOSE_NAME_LANG}}` | Language for model `verbose_name` |
| `HELP_TEXT_LANG` | `{{HELP_TEXT_LANG}}` | Language for `help_text` |

## 7. File Interface Rules

| Key | Value | Notes |
|---|---|---|
| `FILE_ENCODING_OUT` | `{{FILE_ENCODING_OUT}}` | Encoding for generated files, e.g. `UTF-8` |
| `EXCEL_FORMAT` | `{{EXCEL_FORMAT}}` | Target Excel format, e.g. `.xlsx` only |
| `EXCEL_LIB` | `{{EXCEL_LIB}}` | e.g. `openpyxl` |
| `PDF_LIB` | `{{PDF_LIB}}` | Library already in dependencies, or `n/a` |
| `PRESERVED_FORMATS` | `{{PRESERVED_FORMATS}}` | Formats kept as-is from legacy, e.g. `.csv, .txt, .dat, .zip` |
| `FILE_SHARE_ACCESS` | `{{FILE_SHARE_ACCESS}}` | How the app reads network files, e.g. `SMB via smbprotocol`, or `n/a` |

## 8. QA Handoff Artifacts

| Key | Value | Notes |
|---|---|---|
| `API_COLLECTION_DIR` | `{{API_COLLECTION_DIR}}` | Where API-client examples live per screen, or `n/a` |
| `SCREEN_KEY_CASE` | `{{SCREEN_KEY_CASE}}` | Case convention for `screen_key`, e.g. `snake_case` |
| `REFERENCE_DB_POLICY` | `{{REFERENCE_DB_POLICY}}` | e.g. read-only probes only; mutate the test database exclusively |

## 9. Cross-Subsystem Rules

Fill only if this subsystem coexists with others sharing a database or model layer. Otherwise mark `n/a`.

| Key | Value | Notes |
|---|---|---|
| `MODEL_OWNERSHIP` | `{{MODEL_OWNERSHIP}}` | Which modules may define models; what this subsystem must import instead of define |
| `INTEGRATION_MODULE` | `{{INTEGRATION_MODULE}}` | Module holding read-only foreign references, or `n/a` |
| `MISSING_MODEL_ESCALATION` | `{{MISSING_MODEL_ESCALATION}}` | What to do when a needed model exists nowhere — who decides, how it is tracked |

## 10. Rule Document Names

The pipeline references these four documents by placeholder so a project may name them however it likes. Give each a filename; the file is expected to sit under `DOCS_DIR`.

| Key | Value | Default if you have no preference |
|---|---|---|
| `BACKEND_RULES_DOC` | `{{BACKEND_RULES_DOC}}` | `BACKEND_CODING.md` |
| `FRONTEND_RULES_DOC` | `{{FRONTEND_RULES_DOC}}` | `FRONTEND_CODING.md` |
| `CONVENTIONS_DOC` | `{{CONVENTIONS_DOC}}` | `CONVENTIONS.md` |
| `ARCHITECTURE_DOC` | `{{ARCHITECTURE_DOC}}` | `ARCHITECTURE.md` |

## 11. Document Map

Fixed names — these are not configurable, because the pipeline documents reference each other directly.

| Purpose | Path |
|---|---|
| Pipeline orchestrator | `{{DOCS_DIR}}/MASTER_WORKFLOW.md` |
| Coverage gate specification | `{{DOCS_DIR}}/TRACEBACK_GATES.md` |
| Legacy evidence taxonomy | `{{DOCS_DIR}}/LEGACY_EVIDENCE.md` |
| Screen registry | `{{DOCS_DIR}}/Screens_Registry.md` |
| Cross-screen issue log | `{{DOCS_DIR}}/Known_Issues.md` |
| Backend coding rules | `{{DOCS_DIR}}/{{BACKEND_RULES_DOC}}` |
| Frontend coding rules | `{{DOCS_DIR}}/{{FRONTEND_RULES_DOC}}` |
| Code style conventions | `{{DOCS_DIR}}/{{CONVENTIONS_DOC}}` |
| Architecture constraints | `{{DOCS_DIR}}/{{ARCHITECTURE_DOC}}` |
| Per-screen artifacts | `{{DOCS_DIR}}/{Business_flows,Screen_plans,Coding_Records,Test_Instruction,Code_Review}/` |

## Validation Checklist

Before the first pipeline run, confirm:

- [ ] No `{{...}}` placeholder remains unfilled (or is explicitly `n/a` with a reason).
- [ ] `LEGACY_VARIANT` matches the actual files you have.
- [ ] `LINT_CMD` and `TEST_CMD` run successfully when executed by hand.
- [ ] `FE_E2E_TEST_CMD` runs (even if it reports "no tests found").
- [ ] Every module listed in §3 exists as a directory under `BACKEND_ROOT`.
- [ ] Evidence directories in §2 exist and contain at least one file.
- [ ] `Screens_Registry.md` has at least one screen row.
