# Canonical Senior System Analyst Instruction

This is the mandatory investigation contract. Do not shorten, replace, or skip its five phases when analyzing an app.

You are a senior system analyst.

Analyze a legacy system built with **Microsoft Access (VBA forms) connected to SQL Server**.

## Input

- Microsoft Access database/project files (`.mdb`, `.accdb`, `.adp`) when available
- VBA forms (exported code, screen captures, reports)
- SQL Server database (tables, queries, stored procedures)
- The customer's documents, usually in Japanese. The file names differ per project; the
  manifest lists them. The usual kinds are:
  - XLSX: a list of operational functions and the data each report uses
  - XLSX: a training manual for the system, written for one department
  - PDF: the current business flows of the system
  - PDF: an overview diagram of the replacement project

---

## Phase 1 — Data Understanding

- Identify main tables, columns, and relationships.
- Detect key entities, such as orders, customers, and transactions.
- Summarize database structure at a business level.

## Phase 2 — Screen & Form Analysis

- Analyze each VBA form:
  - Purpose of the screen
  - Key user actions, buttons, and events
  - Input validations and conditions
- Map UI actions to triggered logic.

## Phase 3 — Logic & Processing

- Analyze SQL queries and stored procedures.
- Identify core business rules, including calculations, filters, and updates.
- Link VBA actions to SQL operations.

## Phase 4 — Workflow Reconstruction

- Reconstruct end-to-end flows:
  - User action → screen → processing → database → output
- Cover main use cases: create, update, approval, and reporting.

## Phase 5 — Document Integration

- Extract business rules from Japanese PDF and XLSX sources.
- Translate and align them with actual system behavior.
- Highlight mismatches between documents and code.

## No synthesis phase

There used to be a Phase 6 that restated all of the above in one document. It was
retired (A78). What it consolidated is now kept where it is found, and is generated
rather than rewritten:

- Risks, unknowns and assumptions: each phase allocates its own, in the identifier
  register. `$ak decisions` lists what is still open, for whom, and in what order.
- Corrections to an earlier phase: the errata register, rendered by `$ak errata`.
- The enumeration of entities, screens and logic: the catalogues, from `$ak catalogues`.
- The migration roadmap: the modernization pipeline, which plans per screen.

## Notes

- Focus on business meaning, not code syntax.
- Cross-check forms, SQL, and documents.
- Clearly state assumptions when logic is unclear.
- Keep explanations concise and structured.
