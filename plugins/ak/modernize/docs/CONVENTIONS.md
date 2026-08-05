# Code Conventions

> **Layer 1 document.** Language-level conventions for any Python file in the backend. Values resolve from `PROJECT_CONFIG.md`.
>
> Django and DRF patterns are in `BACKEND_CODING.md`. Frontend rules are in `FRONTEND_CODING.md`.

Applies to models, serializers, services, views, tests, management commands, and utilities alike.

## Contents

- [1. Naming And Formatting](#1-naming-and-formatting)
- [2. Numbers And Dates](#2-numbers-and-dates)
  - [2.1 Money And Quantity Use `Decimal`](#21-money-and-quantity-use-decimal)
  - [2.2 Datetimes](#22-datetimes)
- [3. Type Hints](#3-type-hints)
- [4. Test Layout And Naming](#4-test-layout-and-naming)
  - [4.1 Structure](#41-structure)
  - [4.2 Naming](#42-naming)
  - [4.3 Fixtures And Data](#43-fixtures-and-data)
  - [4.3b A Test Must Call The Code It Verifies, Never Restate It](#43b-a-test-must-call-the-code-it-verifies-never-restate-it)
  - [4.4 Markers](#44-markers)
  - [4.5 Coverage Expectation](#45-coverage-expectation)
- [5. Logging](#5-logging)
  - [5.1 Setup](#51-setup)
  - [5.2 Levels](#52-levels)
  - [5.3 What Never To Log](#53-what-never-to-log)
  - [5.4 Correlation](#54-correlation)
- [What This File Is Not](#what-this-file-is-not)

## 1. Naming And Formatting

- `snake_case` for Python identifiers and for JSON field names.
- Field naming, matched to the target schema:
  - business codes end in `{{CODE_FIELD_SUFFIX}}`
  - boolean flags end in `{{BOOL_FIELD_SUFFIX}}`
  - datetimes end in `{{TIME_FIELD_SUFFIX}}`
- Model `Meta` sets `db_table`, `verbose_name`, and `ordering`.
- `verbose_name` in `{{VERBOSE_NAME_LANG}}`; `help_text` in `{{HELP_TEXT_LANG}}`.
- Foreign keys use a protective delete policy by default. A cascading delete is a deliberate decision that must appear in the screen plan, because it changes what a user's delete action destroys.
- Import order: standard library, then Django and DRF, then third-party, then local — one blank line between groups.
- Maximum line length `{{MAX_LINE_LENGTH}}`.
- Master models inherit `{{MODEL_BASE_CLASS}}` where the project defines one.

## 2. Numbers And Dates

### 2.1 Money And Quantity Use `Decimal`

Every monetary amount and quantity — totals, unit prices, tax, tax-inclusive amounts, weights — uses `decimal.Decimal`. Never a float.

```python
from decimal import Decimal

amount: Decimal = Decimal("1234.56")
tax: Decimal = (amount * Decimal("0.10")).quantize(Decimal("0.01"))
```

- Construct from a string: `Decimal("0.1")`, not `Decimal(0.1)`. The second one is already wrong before you use it.
- Round with `.quantize()` at the precision the target schema declares. Legacy Access `Currency` fields are fixed-point with four decimal places, so confirm the intended scale against the legacy field rather than assuming two.
- Keep decimals as strings through serialization. Coercing to float in a custom serializer reintroduces the error the `Decimal` was there to prevent.
- Rounding direction is a business rule. Legacy code that used integer truncation is not doing the same thing as `round()`, and the difference shows up in totals.

### 2.2 Datetimes

- The project sets `USE_TZ = {{USE_TZ}}` with timezone `{{TIMEZONE}}`.
- When `USE_TZ` is false, all datetimes are naive local time. Do not expect `timezone.now()` to return an aware value; be consistent about which "now" the code uses.
- Serialize datetimes as ISO 8601 and dates as `YYYY-MM-DD` unless a legacy file contract requires another format, in which case that format belongs to the export layer only, not to the API.
- Legacy `Date()` and `Now()` were server-local. Preserve that meaning rather than introducing UTC into a system whose users and reports are all in one timezone.

## 3. Type Hints

Required for:

- Every public function and method signature, parameters and return type.
- Every dataclass, `TypedDict`, and service-layer data transfer object.
- Exception classes whose `__init__` accepts a structured payload.

Optional for local variables with an obvious type, and for test functions.

Conventions:

- Put `from __future__ import annotations` at the top of new modules so forward references need no quoting.
- Prefer built-in generics — `list[int]`, `dict[str, Any]`.
- Pick one optional style per module, `X | None` or `Optional[X]`, and hold to it. New code prefers `X | None`.
- Annotate `QuerySet[Model]` where it clarifies a service boundary.
- Do not reach for `Any` to silence a type error. Use it only at a genuine boundary such as raw request data.

Type checking may not run in CI. Treat hints as documentation the reviewer reads; inconsistencies are flagged, not blocking.

## 4. Test Layout And Naming

### 4.1 Structure

```
{{BACKEND_ROOT}}/{module}/tests/
├── __init__.py
├── test_{screen_key}_api.py          ← view, serializer, and URL together
├── test_{screen_key}_service.py      ← service-layer unit tests
├── test_{screen_key}_serializer.py   ← only when the serializer is non-trivial
└── test_{shared_helper}.py
```

Cross-module integration tests, which should be rare, live at the project's top-level tests package.

### 4.2 Naming

- File: `test_{screen_key}_{layer}.py`, using the `screen_key` from `Screens_Registry.md`.
- Class: `Test{ScreenKeyCamelCase}{Layer}`.
- Method: `test_{input_condition}_{expected_outcome}` — for example `test_register_with_duplicate_returns_409`.

Avoid `test_register_1` and `test_register_happy_path`. A failing test should name the broken behavior in its own output, without anyone opening the file.

### 4.3 Fixtures And Data

- Shared setup goes in a per-module `conftest.py`.
- Use factories for seeded data rather than pasting dictionaries into every test.
- Tests needing real reference values follow `{{REFERENCE_DB_POLICY}}`: probe read-only, copy the minimal case into the test database, assert there.

**Never copy a fixture into a second test module — move it to `conftest.py` instead.** A duplicated fixture looks harmless and costs almost nothing to paste, which is exactly why it spreads. The damage shows up when a new test file requests it and forgets the copy: pytest reports a **setup ERROR, not a test failure**, and an error means **the test body never executed**. The endpoint that file was written to cover has silently never been exercised, and the run still summarises as green apart from one line that reads like any other red line. A duplicated fixture therefore converts a missing copy from a visible failure into a coverage hole.

Two rules follow:

- **Treat `ERROR` and `FAILED` as different findings.** A failure says something is wrong; an error says nothing was checked. When a suite reports errors, resolve them before reading the failures — and never quote a pass count from a run that had errors without saying so.
- **When consolidating duplicated fixtures, prove the copies are identical first**, mechanically rather than by eye, then delete them in one change. Copies that have drifted encode per-module behaviour that a single shared fixture will silently change. Afterwards, find the imports the deletion orphaned with a linter rule for unused imports rather than by searching for the symbol — the import line contains the name, so a naive search always reports it as still in use.

### 4.3b A Test Must Call The Code It Verifies, Never Restate It

A test that re-implements the query or calculation it is checking — copying the view's `order_by` into the test body, recomputing the expected total with the same formula the service uses — proves only that the copy agrees with itself. It cannot fail when production is wrong, because both sides carry the same fault.

The second-order damage is worse than the missing coverage. When such a test does misbehave, **"the test is flaky" becomes an available explanation that does not implicate production code**, so the finding gets filed as test hygiene and the real defect stays open. This has happened on this project: an intermittent assertion was recorded as an order-dependent test, and turned out to be a data-correctness bug in a live screen that the test had been mirroring faithfully all along.

- Call the service method or hit the endpoint. If that is awkward because the logic is inline in a view, that is the finding — extract it, then have both the view and the test call the extraction.
- Write expected values as **literals** wherever the value is knowable, not as an expression that reuses production's arithmetic.
- Treat an intermittent test as a suspected production bug until measured otherwise. Reach for a probe that quantifies the suspected mechanism — collision rates, retry counts, orderings — rather than re-running until green.

### 4.4 Markers

- `@pytest.mark.django_db` on anything touching the ORM.
- A slow marker for tests over roughly two seconds.
- An integration marker for tests spanning modules.

### 4.5 Coverage Expectation

No hard threshold. The reviewer expects each public service method to have at least one success and one failure test, and each endpoint to cover a success status and its main error status. A calculation with no test for its rounding boundary is not covered, whatever the percentage says.

## 5. Logging

### 5.1 Setup

```python
import logging

logger = logging.getLogger(__name__)
```

Always `__name__`; never a hardcoded logger name. Hardcoding breaks per-module filtering, which is what makes production logs searchable.

### 5.2 Levels

| Level | Use for |
|---|---|
| `debug` | Internal flow useful only while debugging. Off in production |
| `info` | Significant business events: import started and finished, export generated, batch job boundaries, register and delete completed |
| `warning` | Recoverable anomaly: a dependency was slow, a retry succeeded, an ambiguous input took a default |
| `error` | An unrecoverable failure that became a 5xx. Include `exc_info=True` |
| `critical` | System-level failure — database unreachable, file share unmounted. Should trigger an alert |

### 5.3 What Never To Log

- **Personal data** — names, addresses, phone numbers. Log identifiers instead. Logs are usually forwarded to systems with broader access than the database.
- **Secrets** — passwords, tokens, connection credentials.
- **Full request bodies** on write endpoints. Log the operation and the key identifiers.

### 5.4 Correlation

Where the project sets a trace or request identifier in middleware, it is attached automatically; do not add it by hand. For management commands and batch jobs, ensure one is established at entry so a batch failure can be traced across log lines.

## What This File Is Not

- Not the workflow — `MASTER_WORKFLOW.md`.
- Not architecture or scope constraints — `{{ARCHITECTURE_DOC}}`.
- Not Django or DRF patterns — `BACKEND_CODING.md`.
- Not frontend rules — `FRONTEND_CODING.md`.
- Not the per-screen design — `Screen_plans/{screen}.md`.

Where this file conflicts with `BACKEND_CODING.md`, the backend-specific rule wins. Record the conflict in `Known_Issues.md`.
