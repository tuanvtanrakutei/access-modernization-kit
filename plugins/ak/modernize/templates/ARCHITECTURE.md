# Architecture And Scope Constraints

> **Template.** Copy to `{{DOCS_DIR}}/{{ARCHITECTURE_DOC}}` and fill for your project.
>
> **Non-negotiable once agreed.** This file records decisions that are not up for reinterpretation during implementation. Coding rules live in `{{BACKEND_RULES_DOC}}` and `{{FRONTEND_RULES_DOC}}`; the workflow lives in `MASTER_WORKFLOW.md`.

This document exists because modernization projects drift. A developer three months in, facing an awkward legacy behavior, will be tempted to improve the architecture rather than reproduce the behavior. This file is what that developer reads instead.

## Scope Boundary

| Question | Answer |
|---|---|
| What subsystem does this project cover? | `{{SUBSYSTEM_CODE}}` — {{PROJECT_NAME}} |
| What is explicitly **not** this project's responsibility? | {{fill: adjacent subsystems, shared master data, other teams' modules}} |
| Is this a modernization or a redesign? | Modernization. Screens, flows, file contracts, and report outputs are preserved. Business behavior changes require a recorded decision, not a developer's judgment call |
| May this project change business behavior? | Only through an open decision approved by the business owner and recorded in the screen plan as an accepted difference |

## Architecture Pattern

| Aspect | Decision |
|---|---|
| Overall shape | {{fill: e.g. single SPA over one or several backend services, path-based routing}} |
| Frontend | React SPA at `{{FE_ROUTE_BASE}}`, no server-side rendering, served as a static build |
| Backend | Django REST Framework, mounted at `{{API_PREFIX}}` |
| Database | PostgreSQL |
| Batch processing | {{fill: e.g. management commands scheduled externally}} |

State the API prefix once here and treat it as published. Legacy documents that show an older, unversioned form are wrong; say so explicitly so nobody reintroduces it.

## Database Scope

| Rule | Value |
|---|---|
| Schema this project owns and writes to | `{{SCHEMA_OWNED}}` |
| Schemas readable but never written | `{{SCHEMAS_READONLY}}` |
| Cross-schema joins | {{fill: permitted pattern, or none beyond read-only foreign references}} |
| Model ownership | `{{MODEL_OWNERSHIP}}` |
| Migration policy | `{{MIGRATIONS_POLICY}}` |
| Module holding read-only foreign references | `{{INTEGRATION_MODULE}}` |
| Primary key strategy | `{{PK_STRATEGY}}` |
| Legacy database synchronization | Out of scope. This project does not replicate, diff, or reconcile the legacy database |

## Legacy Interface Boundary

| Rule | Value |
|---|---|
| Integration style with remaining legacy systems | File-based, not database-level |
| File names and directory structure | Preserved. Not reorganized by module |
| Encoding of files this project writes | `{{FILE_ENCODING_OUT}}` |
| Encoding of legacy source files | `{{SOURCE_ENCODING}}` — conversion is handled at extraction, not in application code |
| Excel format | `{{EXCEL_FORMAT}}` only |
| Other formats | `{{PRESERVED_FORMATS}}` — preserved as-is; the legacy format choice is part of the contract |
| Shared storage access | `{{FILE_SHARE_ACCESS}}` |

## Hosting Boundary

| Aspect | Decision |
|---|---|
| Runtime | {{fill}} |
| Disaster recovery | {{fill, or reference a separate hosting document}} |
| Environment separation | {{fill}} |

Infrastructure detail beyond these boundaries belongs in a separate hosting document, not here.

**That hosting document is a project artifact, and this plugin deliberately does not template it.** Runtime platform, RPO/RTO targets, database HA, backup and restore procedure, file-storage choice and DR sync are decisions about the customer's infrastructure, not about the legacy Access application being replaced. They are also decided once for the system rather than per screen, so no pipeline stage reads them: nothing in the six stages, and no coverage gate, consults hosting values. Two consequences worth stating plainly — a hosting template carried inside the plugin would either sit empty or, worse, harden one customer's infrastructure choice into an apparent default that the next project copies without deciding; and it would be the section nobody updates, because its content lives and dies with a specific deployment.

Write it as a project-level document, reference it from the Disaster recovery row above, and leave it out of the pipeline's reading list.

## What This Project Must Not Do

Fill in the ones that apply, and delete the rest rather than leaving an ambiguous list:

- Implement legacy database synchronization
- Implement gateway, proxy, or reverse-proxy logic that belongs to infrastructure
- Reorganize the preserved file directory structure
- Read or write another subsystem's schema outside the agreed read-only pattern
- Perform encoding conversion of legacy source files in application code
- Redesign business flows that operators depend on
- Create models or migrations, when `{{MIGRATIONS_POLICY}}` is `external`

## Where Each Rule Lives

| Topic | Authoritative document |
|---|---|
| Architecture and scope — this file | `{{ARCHITECTURE_DOC}}` |
| Backend coding rules | `{{BACKEND_RULES_DOC}}` |
| Frontend coding rules | `{{FRONTEND_RULES_DOC}}` |
| Language-level style | `{{CONVENTIONS_DOC}}` |
| Pipeline, stages, gates, run modes | `MASTER_WORKFLOW.md` |
| Coverage gate specification | `TRACEBACK_GATES.md` |
| Legacy evidence taxonomy | `LEGACY_EVIDENCE.md` |
| Project values and paths | `PROJECT_CONFIG.md` |
| Screen identifiers and track status | `Screens_Registry.md` |
| Cross-screen issues | `Known_Issues.md` |

## Conflict Resolution

This file wins on architecture and scope. `{{BACKEND_RULES_DOC}}` and `{{FRONTEND_RULES_DOC}}` win on coding matters. `MASTER_WORKFLOW.md` wins on workflow.

When two documents disagree, record it in `Known_Issues.md` as a `process` row and fix the divergent document. Choosing silently between them leaves the next reader to make the same choice differently.
