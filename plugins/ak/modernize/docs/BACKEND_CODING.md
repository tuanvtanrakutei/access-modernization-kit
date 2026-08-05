# Backend Coding Rules (Stage 3a)

> **Read before any backend coding.** Invoked at Stage 3a of `MASTER_WORKFLOW.md`. Paths, commands, and class names resolve from `PROJECT_CONFIG.md`.
>
> Frontend rules are in `FRONTEND_CODING.md`. Language-level style is in `CONVENTIONS.md`.

Target stack: Django + Django REST Framework + PostgreSQL. This document covers what the backend code must look like; it does not cover business interpretation, which is Stages 1 and 2.

## Contents

- [1. Project Layout](#1-project-layout)
- [2. URL Convention](#2-url-convention)
- [3. Models And Migrations](#3-models-and-migrations)
  - [3.1 Primary Keys — Follow `{{PK_STRATEGY}}`](#31-primary-keys-follow-pk_strategy)
  - [3.2 Foreign References Outside This Subsystem — `{{INTEGRATION_MODULE}}`](#32-foreign-references-outside-this-subsystem-integration_module)
- [4. Evidence And Mapping (Mandatory)](#4-evidence-and-mapping-mandatory)
- [5. View Layer](#5-view-layer)
- [6. Pagination](#6-pagination)
  - [Cursor Ordering With `.values()`](#cursor-ordering-with-values)
  - [Other Pagination Rules](#other-pagination-rules)
- [7. ORM First, Raw SQL Second](#7-orm-first-raw-sql-second)
- [8. Export And File Endpoints](#8-export-and-file-endpoints)
  - [8.1 Output Format Rule](#81-output-format-rule)
  - [8.2 Excel Specifics](#82-excel-specifics)
  - [8.3 Other Formats](#83-other-formats)
- [9. Standard API Response](#9-standard-api-response)
  - [9.1 Outcome To Status Mapping](#91-outcome-to-status-mapping)
  - [9.2 Rules](#92-rules)
  - [9.3 Required Pattern: One Service-Error Handler Per Module](#93-required-pattern-one-service-error-handler-per-module)
  - [9.4 Anti-Patterns To Flag In Review](#94-anti-patterns-to-flag-in-review)
- [10. Query Performance And Transactions](#10-query-performance-and-transactions)
  - [10.1 Avoid N+1 Queries](#101-avoid-n1-queries)
  - [10.2 Transactions On Write Paths](#102-transactions-on-write-paths)
  - [10.4 "The Latest Row" Needs A Total Order](#104-the-latest-row-needs-a-total-order)
- [11. OpenAPI Documentation](#11-openapi-documentation)
  - [11.1 Required Annotations](#111-required-annotations)
  - [11.2 Rules](#112-rules)
- [12. Permissions And Authentication](#12-permissions-and-authentication)
  - [12.1 Establish What **Production** Enforces, Not What The File Currently Says](#121-establish-what-production-enforces-not-what-the-file-currently-says)
  - [12.2 Development Bypasses Must Live In Configuration, Not In Code](#122-development-bypasses-must-live-in-configuration-not-in-code)
  - [12.3 Read Endpoints Are Not One Category](#123-read-endpoints-are-not-one-category)
  - [12.4 Auditing Coverage](#124-auditing-coverage)
  - [12.5 Read The Surrounding Definitions Before Acting On The First Symbol You Find](#125-read-the-surrounding-definitions-before-acting-on-the-first-symbol-you-find)
- [13. Documenting A Coding Decision](#13-documenting-a-coding-decision)
- [14. What This File Is Not](#14-what-this-file-is-not)

## 1. Project Layout

| Concern | Location |
|---|---|
| Serializers | `{{BACKEND_ROOT}}/{module}/serializers/{screen_or_domain}.py` |
| Views | `{{BACKEND_ROOT}}/{module}/views/{screen_or_domain}.py` |
| Services | `{{BACKEND_ROOT}}/{module}/services/{service_name}.py` |
| URLs | `{{BACKEND_ROOT}}/{module}/urls.py`, included from the project URL conf |
| Tests | `{{BACKEND_ROOT}}/{module}/tests/` |

The `{module}` value comes from `Screens_Registry.md` for the screen being implemented. Do not invent module names.

Business logic lives in the **service layer**, not in views or serializers. A view parses the request, calls a service, and maps the result or exception to a response. When a view starts containing conditionals about business rules, that logic belongs in a service.

## 2. URL Convention

- Every endpoint mounts under `{{API_PREFIX}}`.
- The module URL prefix is fixed in `Screens_Registry.md`. Changing it requires an issue-log entry, because it is a published contract.
- Path segments are kebab-case; query and body fields are snake_case.

## 3. Models And Migrations

Follow `{{MIGRATIONS_POLICY}}`.

When the policy is `external` — models are owned by other modules:

- **Do not create models** in this subsystem. Import them.
- **Do not create migrations.**
- **Do not rename existing tables or columns.**
- If a needed model or field exists nowhere, stop and follow `{{MISSING_MODEL_ESCALATION}}`. Do not create it speculatively, and do not add a nullable placeholder to keep the code compiling — a placeholder silently changes the data contract.

When the policy is `owned`, normal Django model and migration practice applies, and the legacy table mapping in `{{TABLE_MAP_DOC}}` is the source of field names.

### 3.1 Primary Keys — Follow `{{PK_STRATEGY}}`

Access applications routinely use a **business code** as the primary key: a product code, a store code, a slip number. Carrying that choice into the replacement looks like fidelity and is usually a mistake — business codes get reissued, re-typed, and occasionally renumbered by the business, and every one of those events becomes a primary-key change with foreign keys hanging off it.

`{{PK_STRATEGY}}` states what this project does instead. Read it rather than inferring from the legacy table, and apply it consistently: a table that follows a different rule than its neighbours is the one that breaks a join six months later.

Whatever the strategy says, two things hold:

- **The business code keeps its own uniqueness constraint.** Moving it off the primary key does not make it optional; a duplicate product code is still a data defect and the database should say so.
- **The legacy code stays queryable.** Operators, reports, and the legacy interface files all address rows by business code. If a lookup by that code needs an index, add it — an internal surrogate key is an implementation detail, not a reason to make the operator's identifier slow.

### 3.2 Foreign References Outside This Subsystem — `{{INTEGRATION_MODULE}}`

Models belonging to another subsystem live in `{{INTEGRATION_MODULE}}` and are **read-only here**. Reference them, never write them.

The rule exists because the failure it prevents is silent. A write to another subsystem's table succeeds, passes tests, and produces a row that subsystem's own validation would have rejected — the damage appears in *their* reports, not yours, which is the worst possible place to discover it.

- Declare foreign keys to those models normally, but treat any code path that would insert or update one as a defect.
- If a field this project needs exists only in another subsystem, that is a scope question, not a modelling one. Follow `{{MISSING_MODEL_ESCALATION}}`.
- If `{{INTEGRATION_MODULE}}` is `n/a`, this project has no such references and a model appearing to come from elsewhere is a mapping error worth stopping on.

## 4. Evidence And Mapping (Mandatory)

Before writing code:

1. Identify the tables and fields involved via `{{TABLE_MAP_DOC}}`. Use the target schema's names; do not invent columns.
2. Trace the legacy behavior from the evidence directories, per `LEGACY_EVIDENCE.md` for `{{LEGACY_VARIANT}}`.
3. Record the legacy-to-new mapping in `Screen_plans/{screen}.md` — the Stage 2 artifact — not as inline code comments.

If a table or field is missing from `{{TABLE_MAP_DOC}}`, stop and ask. Silently renaming or inventing a column is how a modernization project ends up with two incompatible schemas.

## 5. View Layer

- Default to DRF generics: `ListAPIView`, `RetrieveAPIView`, `CreateAPIView`, `UpdateAPIView`, `DestroyAPIView`, or the combined variants.
- Use plain `APIView` only where generics do not fit: file export, bulk actions, and genuinely custom request or response shapes.
- Keep the view thin. Request parsing, service call, response mapping — nothing else.

## 6. Pagination

- Reuse the project's shared pagination class, `{{PAGINATION_CLASS}}`, so behavior is consistent across screens.
- Enable or disable pagination per endpoint based on the API contract in the screen plan and on legacy behavior.

Cursor pagination contract:

- Query parameters: `cursor`, `page_size`.
- Response shape: `data` for the current page; `pagination.next` and `pagination.previous` as cursor URLs or `null`; optional `meta`, for example `meta.totals`.
- **Do not return page-number fields** (`count`, `page`, `limit`, `total_pages`) from a cursor endpoint. A client that sees them will build a numbered pager that cannot work.
- Apply pagination to an ordered `QuerySet` or ordered `.values()` queryset. Never pass a materialized Python list to a cursor paginator.
- Set stable, deterministic ordering — preferably a unique legacy key such as the screen's business number field.
- If totals are required, compute them over the **full filtered queryset before pagination** and return them under `meta.totals`. Summing the current page produces a number that changes as the user scrolls.

### Cursor Ordering With `.values()`

A cursor paginator that defaults to ordering by `id` will raise `KeyError: 'id'` when the service returns a `.values(...)` queryset that omits `id`. The error is raised **after** the service's own `try`/`except`, so it surfaces as an uncaught 500 rather than a handled error response — which makes it look like an infrastructure fault instead of a coding mistake.

Rule: whenever a view paginates a `.values()` result, set the paginator's ordering explicitly to a field that **is** present in the `.values()` list.

```python
class ProductListView(ListAPIView):
    pagination_class = CursorPagination
    pagination_ordering = "product_cd"   # must exist in the .values() fields the service returns
```

Do not rely on the default ordering unless the key it uses is explicitly included in `.values()`.

### Other Pagination Rules

- Never paginate a file export endpoint.
- For POST endpoints that return data, follow the screen plan. If the contract says no pagination, return all rows with no `pagination` block.

## 7. ORM First, Raw SQL Second

- Use the Django ORM by default.
- If an endpoint cannot be expressed cleanly or performs badly through the ORM — a common case when porting a complex legacy report query — **stop and ask before writing raw SQL.** Include the endpoint, why the ORM is inadequate, and the proposed alternative.
- Treat relationship columns as scalar fields where the legacy schema did, and enforce integrity at the database level with real foreign keys.
- Enforce integrity in application code only where the API or the legacy behavior requires it beyond what constraints express.

## 8. Export And File Endpoints

Legacy Access reports were typically emitted with `DoCmd.OutputTo` or `DoCmd.TransferText`.

### 8.1 Output Format Rule

Output format follows the **legacy format**, with exactly one exception: Excel is modernized. Everything else is preserved.

| Legacy format | New system | Reason |
|---|---|---|
| `.xls` | **`{{EXCEL_FORMAT}}`** | The project standardizes on the modern Excel format |
| `.csv` | `.csv` | Preserved |
| `.txt` | `.txt` | Preserved |
| `.dat` | `.dat` | Preserved |
| `.pdf` | `.pdf` | Preserved |
| `.zip` | `.zip` | Preserved |

Do not change a format opportunistically. Turning a legacy `.txt` into a `.csv` because it seems tidier breaks whatever downstream system consumes it, and that system is usually invisible from inside this project.

### 8.2 Excel Specifics

- Generate with `{{EXCEL_LIB}}`.
- Match legacy column order, sheet naming, and formatting wherever evidence exists.
- Set `Content-Type` for the Excel MIME type and `Content-Disposition: attachment; filename="..."`.

### 8.3 Other Formats

- Encoding is `{{FILE_ENCODING_OUT}}`.
- Match legacy column order, delimiter, line ending, and filename convention **exactly**. The comparison baseline is the legacy sample in the evidence output directory.
- Quoting behavior counts. Legacy exports through an ODBC driver sometimes quote numeric columns that a modern writer would leave bare; that difference is a decision to record, not a detail to overlook.
- For PDF, use `{{PDF_LIB}}`. Introducing another PDF library requires an issue-log entry first.

## 9. Standard API Response

All endpoints return through `{{RESPONSE_CLASS}}`. Do not use the raw framework response, and do not call a generic low-level error helper directly — use the typed helper for the situation so the status contract stays enforceable.

### 9.1 Outcome To Status Mapping

| Business outcome | HTTP | Helper |
|---|---|---|
| Success with data | 200 | `success(data, pagination=None, meta=None)` |
| Resource created | 201 | `created(data=None, meta=None)` |
| Succeeded, no body | 204 | `no_content()` |
| Malformed request parameter, not serializer-level | 400 | `bad_request(details, message?)` |
| Missing or invalid credentials | 401 | `unauthorized(message?)` |
| Authenticated but not permitted | 403 | `forbidden(message?)` |
| Resource does not exist | 404 | `not_found(message?)` |
| Method not allowed on this URL | 405 | `method_not_allowed(message?)` |
| Business constraint violated | 409 | `conflict(message?)` |
| Serializer validation failed | 422 | `validation_error(details, message?)` |
| Unexpected server error | 500 | `internal_error(message?)` |
| Declared but not implemented | 501 | `not_implemented(message?)` |
| Dependency unreachable | 503 | `service_unavailable(message?)` |

### 9.2 Rules

1. **Serializer errors are 422, not 400.** Reserve 400 for query-parameter and path-parameter parsing failures that never reach a serializer.
2. **404 means the addressed resource does not exist.** A filter that matches nothing is 200 with `data: []`. Returning 404 there makes an empty result indistinguishable from a broken URL.
3. **409 covers business conflicts** — unique-constraint violations, an attempt to delete a protected referenced row, an optimistic-lock mismatch. Map them explicitly; letting them reach the client as 500 hides a rule the user needs to know about.
4. **503 is for downstream outages** — file share unreachable, reference database timing out, an integration endpoint down. It is not for "no data found".
5. **500 is the catch-all for the genuinely unexpected.** Log the original exception; never swallow it.

### 9.3 Required Pattern: One Service-Error Handler Per Module

Each module exposes a single private function mapping its service exceptions to responses. Views call it from their `except` block.

```python
def _handle_{domain}_service_error(exc: Exception):
    if isinstance(exc, {Domain}ValidationError):
        return ApiResponse.validation_error(exc.details, message=exc.message)
    if isinstance(exc, {Domain}BusinessError):
        return ApiResponse.bad_request(exc.details or {}, message=exc.message)
    if isinstance(exc, {Domain}NotFoundError):
        return ApiResponse.not_found(exc.message)
    if isinstance(exc, {Domain}ConflictError):
        return ApiResponse.conflict(message=exc.message)
    return ApiResponse.internal_error(message=str(exc))
```

Do not map exceptions inline across several endpoints in the same module. Inline mapping diverges as endpoints are added, and inconsistent status codes across one screen's endpoints is the usual result.

### 9.4 Anti-Patterns To Flag In Review

- Importing the raw framework response class in a view module, even unused — it is a dead import that invites misuse.
- Calling the generic low-level error helper instead of a typed one.
- 400 for serializer validation failures.
- 404 for an empty list result.
- Letting an integrity or protected-delete error reach the client as 500.
- Inline `isinstance` chains in views instead of the module handler.

## 10. Query Performance And Transactions

### 10.1 Avoid N+1 Queries

Any list endpoint whose serializer reads a related object must eager-load that relation, or each row triggers another query.

- `select_related('fk_field')` for forward foreign keys and one-to-one relations.
- `prefetch_related('reverse_or_m2m')` for reverse foreign keys and many-to-many.
- Chain both when needed.

Apply them to the base queryset **before** pagination, never after slicing.

Reviewers flag any list serializer that traverses `obj.related.field` with no matching eager load.

### 10.2 Transactions On Write Paths

Wrap multi-step writes in `transaction.atomic` at the **service** layer.

```python
from django.db import transaction

class EntryService:
    def register(self, payload):
        with transaction.atomic():
            header = self._create_header(payload)
            self._create_lines(header, payload.lines)
            self._update_related(header)
            return header
```

- Required when a write touches more than one model, or mutates a row plus an audit trail.
- Not required for read-only endpoints or a single-row update with no side effect.
- Do not decorate the whole view. The service is the correct boundary, so error handling and response mapping stay outside the transaction.
- Use `transaction.on_commit` for post-commit side effects such as writing a file or notifying another system. An external side effect inside the transaction can block or corrupt the rollback path.

### 10.4 "The Latest Row" Needs A Total Order

Any query that narrows a set to one row — `.first()`, `.last()`, `.latest()`, `LIMIT 1` — must order by something **unique**. Ordering on a timestamp alone does not qualify, and the failure is silent: on a tie the database is free to return either row, and no error is raised.

This is not a rare edge case when the timestamp is a creation stamp. A field populated by the ORM at insert time takes its value from the application clock, whose resolution is coarser than the time needed to insert consecutive rows. Measured on a real project: two rows written back to back received an **identical** timestamp about **70%** of the time, and the "latest" query then returned the wrong row in about **80%** of attempts once the table held other rows.

- **Always append the surrogate primary key as the tie-breaker** — `order_by("-created_at", "-id")`. An auto-increment key is monotonic, so it resolves every tie in true insertion order.
- **Do not test the tie by inserting two rows and hoping.** A test written that way passes most of the time, which is worse than failing: it certifies the bug. Force the collision — write both rows, then update them to share one timestamp — and assert the newer one still wins.
- **Note where the risk concentrates.** A near-empty table often returns physical insertion order by accident, so a small test dataset hides the defect while a populated production table exposes it. The environment that looks safe is the one that is lying.
- The same rule applies to `Meta.ordering` and to any pagination that orders on a non-unique column, where a tie causes rows to repeat or vanish across pages.

## 11. OpenAPI Documentation

Every endpoint carries a schema annotation so the generated schema and its UI are usable by the frontend and by QA.

### 11.1 Required Annotations

Per view or method, declare: a tag grouping by module, a globally unique operation id, a summary that names the screen, a description, every query and path parameter, and a response entry for each status code the endpoint can return, tied to a serializer.

Keep the screen name in a module-level constant and interpolate it, so the summary cannot drift from the screen it documents.

### 11.2 Rules

- Tags group by business module, so the UI is navigable by someone who thinks in screens rather than in code layout.
- Operation ids are snake_case and prefixed by module and screen key.
- List every status code the endpoint really returns. An endpoint documented as only 200 will be integrated as if errors cannot happen.
- Request body schema comes from the request serializer; required parameters must not be omitted.

## 12. Permissions And Authentication

Where the project defines `{{PERMISSION_DECORATOR}}` and `{{PERMISSION_CODE_ENUM}}`:

- Apply the permission check **per HTTP method**, not once at class level. Different methods on one URL usually need different permission codes.
- The code comes from the project's permission enum. If the constant for this screen action does not exist, add it before merging rather than reusing an approximate one.
- Do not hand-roll per-view permission classes when the project has a decorator pattern; one path for all checks is what makes an audit possible.

### 12.1 Establish What **Production** Enforces, Not What The File Currently Says

Before judging any permission gap, determine whether the framework enforces authentication project-wide in the environment that matters. A commented-out `DEFAULT_AUTHENTICATION_CLASSES` is often a deliberate development or demo convenience, not an oversight — so read the file, then ask which configuration ships.

The answer decides the severity, and the two cases are far apart:

| Production baseline | An undecorated handler means | Severity |
|---|---|---|
| Authentication enforced project-wide | Any **authenticated** user can invoke it regardless of their granted permissions | Privilege escalation between roles. Real, because per-action codes exist precisely so that view rights and delete rights differ |
| No baseline enforced | The handler has neither authentication nor authorization | Unauthenticated access to whatever it exposes |

Record which case applies in the screen plan, so a later reader does not have to infer it — and do not describe a gap as unauthenticated access when the deployed configuration authenticates.

### 12.2 Development Bypasses Must Live In Configuration, Not In Code

Modernization projects almost always run with access control relaxed during development, because the legacy application had no equivalent and the replacement's permission service may not exist yet. That is legitimate. **How the bypass is expressed is what matters.**

Two patterns recur, and both are traps:

1. Commenting out the framework's authentication and permission classes in the settings module.
2. An early `return` at the top of the permission-check function, so every decorator becomes a no-op while still appearing present in the code.

The second is the dangerous one. A reviewer inspecting the settings module or the environment files sees nothing wrong, and every view still carries its decorator, so the code reads as secured. Only opening the check function reveals that none of the decorators do anything.

When both patterns are present, a secure release requires **two independent manual reverts**, and a release that performs only the first looks completely secured while authorization is still disabled everywhere.

**Check for the third pattern, which turns the other two from a checklist item into an unverifiable one: an autouse test fixture that patches the permission check out of every test.** It is added early for the ordinary reason — endpoint tests should not need a live authorization server — and once it is `autouse`, the enforcement code has no coverage anywhere and cannot acquire any, because a test would have to explicitly opt out of a fixture it never asked for. Combine it with a bypass in the code and the enforcement path has never executed at all: not in development, where the early `return` short-circuits it, and not in CI, where the fixture removes it. The first production request to hit a permission check becomes the first execution of that code in the project's history.

So when auditing, ask three questions, not two:

1. Are the framework's authentication and permission classes actually enabled in the configuration the target environment uses?
2. Does the check function actually run, or does it return before doing anything?
3. **Is there a single test that exercises enforcement — one that opts out of any autouse bypass and asserts a request without the required permission is rejected?** If not, the first two answers cannot be verified by running anything.

Scope the bypass fixture so it is opt-in per test, or keep it autouse but add one test that disables it and asserts a rejection. The secure-by-default configuration below also makes such a test writable, because an environment flag is something a test can flip while a hardcoded `return` is not.

Express the bypass as configuration instead, secure by default:

```python
# settings.py — doing nothing gives you the secure behavior
AUTH_ENABLED             = env.bool("AUTH_ENABLED", default=True)
PERMISSION_CHECK_ENABLED = env.bool("PERMISSION_CHECK_ENABLED", default=True)

if AUTH_ENABLED:
    REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = (...)
    REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = (...)

# Refuse to run a non-debug deployment with access control switched off.
if not DEBUG and not (AUTH_ENABLED and PERMISSION_CHECK_ENABLED):
    raise ImproperlyConfigured(
        "AUTH_ENABLED and PERMISSION_CHECK_ENABLED must be true when DEBUG is false."
    )
```

```python
# the permission check consults the flag instead of returning unconditionally
def make_check_permission(self, function_cd, operator="") -> None:
    if not settings.PERMISSION_CHECK_ENABLED:
        return
    ...
```

Three properties this buys:

- **Forgetting produces the safe state.** With `default=True`, an environment that declares nothing is secured. A `default=False` would rebuild the original trap.
- **The bypass is visible where people look.** `AUTH_ENABLED=false` in an environment file is obvious in a diff and in a deployment review; a `return` inside a method body is not.
- **Misconfiguration becomes impossible rather than discouraged.** The startup guard means the application refuses to boot with access control off outside debug, instead of running silently without it.

Migration cost, worth stating to the team before doing it: with secure-by-default, local development stops working until the two `false` entries are added to the development environment file. That is a deliberate one-time cost in exchange for removing a standing release risk.

**Check where the decorator validates.** If it calls an external permission service, a new value added to the local enum does **not** create the permission upstream; the check will fail rather than pass. Codes must exist in the authoritative catalogue before use, which makes "add a new code" a cross-team action, not a local edit.

### 12.3 Read Endpoints Are Not One Category

Access applications have no per-query permission concept, so a port naturally guards the buttons — the writes — and leaves the reads open. The result looks like a deliberate convention and is usually not one. Classify every read endpoint into one of three tiers, because they carry different obligations.

| Tier | What it is | Obligation |
|---|---|---|
| **A — Transaction read** | The screen's main list or inquiry endpoint, returning business records | **Must be protected**, with the owning screen's own view-level code. Leaving it open while the same screen's delete is guarded means the data can be read without credentials but not removed — an incoherent posture, not a policy |
| **B — Reference lookup** | Dropdown, options, and code-list feeders; master data that exists to populate a control | **Policy decision.** Defensible to leave open, or to guard with a single generic read code. Minting a distinct code per dropdown produces a permission catalogue nobody maintains |
| **C — Existence oracle** | Duplicate checks, availability probes, async job-status polls | **Should be protected** with the owning screen's code. A duplicate check answers a business question — whether a record exists for a given key — so it leaks the same facts as a read of that record |

Tier A is the one teams miss, because a `GET` that returns a list looks like the same kind of thing as a `GET` that returns a dropdown. Judge by **what the response contains**, not by the HTTP method or the word "list" in the class name.

### 12.4 Auditing Coverage

When measuring decorator coverage across a codebase, attribute each decorator to the block between one `def` or `class` and the next. A fixed-size lookback window silently misses multi-line decorators — a list of codes combined with an OR operator can easily span ten lines — and produces both false positives and an understated coverage figure. Verify any surprising result by opening the file before reporting it, particularly when the finding is a security one.

Report read and write coverage separately. A single combined percentage hides the case that matters most: writes fully guarded while transaction reads are open.

The rule below is written for permission audits but applies to **any** claim about code you are about to change on the strength of a search.

**Never conclude that something is unused from a truncated search.** A deadness claim — "this constant is dead", "no caller passes this argument", "this branch is unreachable" — is a claim about the *absence* of matches, so it is only supportable from a **complete** result set. Piping a search through `head` is safe when you are asking *does this exist* and unsafe when you are asking *does this not exist*: the first few hits can all be the pattern you expected while the ones that refute you sit below the cut. The failure is silent, and it reads as confirmation.

Two consequences for how a finding is written up:

- **Deletion proposals need the call-site list, not a count.** If a finding says "delete these constants", it must enumerate `file:line` for every usage found, so a reviewer can see the search was exhaustive. A finding that cannot produce that list has not established its premise.
- **A wording or naming cleanup that touches call sites is a behaviour change.** Removing a per-screen constant in favour of a global one changes what the API returns. Classify it as such, size it by the tests that break, and decide the desired value first — in a legacy replacement the older string is sometimes the correct one, and the migration runs the other way.

### 12.5 Read The Surrounding Definitions Before Acting On The First Symbol You Find

A search answers the question you typed, not the question you have. The gap between them is
where this failure lives, and it is the single most repeated reasoning error observed on this
project — four wrong fixes in one working session, each wearing a different disguise:

| What the search said | What was concluded | What was true |
|---|---|---|
| a `head`-truncated grep showed only global usages | the per-screen constants are dead, delete them | they had 17 live call sites below the cut; deleting them broke 13 tests |
| `A01FunctionCd.DcShipmentDataImport` does not resolve | the enum entry is missing, add it | the permission existed as `DcShipmentResultInquiry`; the decorator named the wrong class |
| `OrderDataDeliveryDateExport.CSV_OUTPUT` resolves fine | this is the right symbol, fix its value | the correct class already existed two hundred lines up; editing this one created a duplicate |
| `git diff --name-only` listed the changed files | format all of them | most belonged to other people's uncommitted work, and the reformat reached a shared branch |

The common step is not a bad search. It is **acting on the first symbol found without reading
what surrounds it**. Resolving a name answers "does this name exist"; it does not answer "is
this the right name", and for an enum, a constants module, or a settings block those are
different questions with different answers.

Three cheap habits close it:

- **Grep the intended value, not the name.** Searching `A01_003_008` would have surfaced the
  correct class immediately; searching the class name could only ever confirm the wrong one.
- **Read the file around the hit.** For a constants or enum module, read the whole block. The
  right entry is usually already there under a name you did not guess — legacy systems
  accumulate synonyms, and word order flips between languages (`PatternDeliveryWeekday`
  against `DeliveryWeekdayPattern` for the same master).
- **Scope a bulk command to what you changed, never to what a tool lists.** A file list from
  version control describes the working tree, not your change. Enumerate your own edits.

The asymmetry worth remembering: a search that finds something proves existence, and one
finding nothing proves nothing at all. Absence is only established by a complete result set
(§12.4) *and* by having looked for the right thing.

## 13. Documenting A Coding Decision

Decisions made while coding go into `Coding_Records/{screen}.md`, not only into code comments. See its README for which section takes what.

Findings that affect more than one screen are promoted to `Known_Issues.md`.

## 14. What This File Is Not

- Not the frontend rules — that is `FRONTEND_CODING.md`.
- Not the backend test method — that is `BACKEND_TESTING.md`.
- Not language-level style — that is `CONVENTIONS.md`.
- Not the workflow — that is `MASTER_WORKFLOW.md`.
- Not the per-screen contract — that is `Screen_plans/{screen}.md`.
- Not the architecture and scope constraints — that is `{{ARCHITECTURE_DOC}}`.

On a workflow conflict the workflow document wins. On a scope conflict the architecture document wins. On a style conflict this file wins for backend-specific matters. Record any conflict in `Known_Issues.md` so the divergent document gets fixed rather than quietly ignored.
