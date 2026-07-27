# Profile-Driven Extraction Bundle Design

**Status:** Reviewed design  
**Original approval date:** 2026-07-23  
**Review date:** 2026-07-24  
**Target:** V2.7 and V2.8, with a measured path to V3  
**Canonical language:** English

## 1. Executive Summary

Access Modernization Kit currently supports automated extraction from an authorized Access snapshot and analysis of pre-exported sources. The safety model is strong, but input completeness is advisory. Loosely organized or incomplete sources can still reach phases whose technical prerequisites are missing.

V2.7 introduces a profile-driven acquisition boundary:

```text
Declared Project Profile
        |
        v
Strict Input Acceptance Gate
        |
        +-----------------------------+
        |                             |
        v                             v
Managed Extraction Adapter     Imported Source Adapter
        |                             |
        +--------------+--------------+
                       |
                       v
        Canonical Immutable Extraction Bundle
                       |
                       v
          Deterministic Analysis Model
                       |
                       v
             Graphify Supporting Context
                       |
                       v
             Phase 1-6 and QA Outputs
```

There are two acquisition methods but one downstream contract and one analysis pipeline. Project profiles define mandatory artifacts, valid alternatives, prohibited inputs, adapter selection, and phase-readiness rules. Unknown files are quarantined instead of silently analyzed.

## 2. Problem Statement

The current kit correctly provides hash-verified snapshots, immutable extraction sessions, binary-free Graphify normalization, evidence provenance, coordinator-only publication, deterministic evidence merge, conflict preservation, and provider-neutral handoffs.

The remaining structural problems are:

1. Input preconditions are advisory, not project-specific acceptance rules.
2. The manifest lists paths but does not declare application topology or backend authority.
3. Imported sources do not require a producer manifest or complete object inventory.
4. Extraction results contain a generic component list instead of a typed source contract.
5. Run creation inventories broad workspace roots instead of consuming an approved bundle.
6. MDB, ACCDB, ADP, compiled frontend, split database, and source-only projects lack distinct readiness rules.
7. Graphify can run before deterministic analyzers create a stable current-state model.
8. Agent collaboration is defined, but human ownership, profile fixtures, contract migrations, and adapter contract tests are missing.

These gaps can produce a formally valid Phase document that is not reliable enough for refactoring or replacement development.

## 3. Goals

V2.7 must:

1. Require a declared, versioned project profile for every new run.
2. Support managed extraction and imported sources without downstream duplication.
3. Convert accepted inputs into one immutable text-and-JSON Extraction Bundle.
4. Prevent unknown, conflicting, or untraceable files from entering analysis silently.
5. Compute rule-based readiness for each investigation phase.
6. Preserve current snapshot, evidence, Graphify, orchestration, and six-phase safety contracts.
7. Keep raw databases, backups, credentials, and runtime state outside shareable bundles and Git.
8. Let multiple developers and agents analyze the same approved bundle reproducibly.
9. Reuse suitable OSS through adapters without coupling the core to one exporter or runtime.
10. Migrate existing V2 workspaces non-destructively.

V2.8 adds deterministic VBA, SQL, CRUD, relationship, UI-event, and interface analysis before Graphify enrichment.

## 4. Non-Goals

V2.7 will not:

- decompile MDE or ACCDE into claimed original VBA source;
- attach arbitrary MDF or LDF files;
- restore SQL Server backups inside an application workspace;
- approve a project profile solely from filename extensions;
- accept an ADP as complete without SQL Server schema artifacts;
- make Graphify a primary parser or evidence source;
- vendor GPL code into the Apache-2.0 package;
- create a general-purpose dynamic plugin platform;
- require Java, Access, SQL Server, or a third-party exporter for every installation;
- exact-text golden-test generated natural-language documents;
- redesign the six-phase analyst contract.

## 5. Design Principles

### 5.1 One downstream contract

Managed and imported acquisition emit the same bundle schema. An analyzer must not branch on the producer.

### 5.2 Project topology before extension

MDB and ACCDB are formats, not sufficient project types. Profiles describe topology and backend authority; artifact declarations describe formats.

### 5.3 Deterministic facts before semantic inference

Object inventory, field types, indexes, procedures, query SQL, event bindings, calls, CRUD effects, and interfaces come from deterministic extraction or parsing. Graphify may enrich discovery but cannot replace those facts.

### 5.4 Raw input is not analysis input

User files first enter staging. Only artifacts accepted by the active profile and represented in the bundle manifest can reach indexing, Graphify, or Phase analysis.

### 5.5 Readiness is rule-based

A numeric coverage score may be informational, but it cannot override a missing mandatory artifact.

### 5.6 Provenance survives transformation

Every normalized object retains its producer, source artifact, extraction session, original name, hash when permitted, encoding, parser, parser version, and transformation chain.

### 5.7 English canonical documentation

Kit contracts, schemas, references, and contributor docs are canonical in English. Application outputs continue to follow manifest languages and may be bilingual.

## 6. Composable Project Classification

V2.7 uses a composable Access project classification rather than a flat list of profiles. Rules live under `plugins/ak/profiles/` as independently versioned topology, frontend, source-availability, and backend rule fragments. A resolved profile is the validated combination of those dimensions.

### 6.1 Topology

Allowed topology values:

- `monolith`: one Access file owns UI, code, and authoritative local data;
- `split_file`: one or more frontends use Access backend files and optional file interfaces;
- `client_server`: an Access frontend uses SQL Server or another authoritative database server;
- `hybrid`: the application depends on more than one authoritative backend kind, such as Access files, SQL Server, and scheduled text feeds.

Topology determines which backend roles and boundary evidence are mandatory.

### 6.2 Frontend format

Allowed frontend formats:

- `mdb`;
- `accdb`;
- `adp`;
- `mde`;
- `accde`;
- `exported` when only a validated source export is available.

Format rules add format-specific extraction requirements. For example, ACCDB rules cover data macros and modern field types, while ADP rules require SQL Server context.

### 6.3 Source availability

Allowed source states:

- `full`: editable database/project source is available;
- `compiled_only`: only MDE/ACCDE or equivalent compiled frontend is available;
- `exported_only`: a validated source export exists but the original file is unavailable;
- `mixed`: source availability differs by artifact.

Compiled-only source can support bounded UI, dependency, and interface analysis but cannot produce a complete VBA reconstruction claim.

### 6.4 Backend kinds

Each backend declaration uses one of:

- `embedded_access`;
- `access_file`;
- `sql_server`;
- `odbc_database`;
- `text_or_csv`;
- `spreadsheet`;
- `external_application`;
- `unknown_boundary`.

Backend rules define required schema, code, link metadata, samples, authority classification, and phase effects.

### 6.5 Resolved profile examples

Friendly aliases may map common combinations without becoming separate contract types:

| Alias | Resolved classification |
|---|---|
| `access-file-monolith` | `monolith + mdb/accdb + full/exported_only + embedded_access` |
| `access-file-split` | `split_file + mdb/accdb/mde/accde + access_file` |
| `access-adp-sqlserver` | `client_server + adp + full/exported_only + sql_server` |
| `access-compiled-frontend` | Any topology with `mde/accde + compiled_only` |

Aliases exist for user guidance only. Validators execute the underlying rule fragments.

### 6.6 Acquisition method is orthogonal

Every resolved profile supports `managed`, `imported`, or mixed acquisition. Imported sources still declare the original classification and provide producer/version, source identity, object inventory, names/types, encoding, exported/skipped/failed/unsupported lists, and hashes when permitted.

Loose files cannot become an approved bundle until classified, traced, conflict-checked, represented by an import manifest, and mapped to a resolved profile. Unknown topology or backend authority may support `LIMITED` assessment, but never `READY` Phase publication.

### 6.7 Rule fragment format

Each rule fragment has stable IDs and explicit effects:

```yaml
id: backend.sql_server.programmable_objects
version: "1.0"
when:
  backend_kind: sql_server
require:
  all:
    - server_object_inventory
    - definitions_for_referenced_objects
    - dependency_closure
affects:
  phase1: BLOCKED
  phase3: BLOCKED
allow_limited_when:
  - server_boundary_declared
```

The server dependency closure includes every server object directly referenced by Access source plus recursively referenced views, procedures, functions, and triggers that affect observed application behavior.

## 7. Manifest V2.2

```yaml
version: "2.2"

app:
  id: "A05"
  name_en: "Product Picking Support"

project:
  profile: "access-file-split"
  profile_version: "1.0"
  classification:
    topology: "split_file"
    frontend_format: "mdb"
    source_availability: "full"
    backend_kinds: ["access_file", "text_or_csv"]

artifacts:
  - id: "A05_FRONTEND"
    kind: "access_database"
    role: "frontend"
    format: "mdb"
    acquisition: "managed"
    required: true
    source_ref:
      type: "local_path"
      value: "sources/access/frontend.mdb"

  - id: "A05_DATA"
    kind: "access_database"
    role: "backend"
    format: "mdb"
    acquisition: "managed"
    required: true
    source_ref:
      type: "local_path"
      value: "sources/access/data.mdb"

  - id: "A05_ORDER_FEED"
    kind: "file_interface"
    role: "backend"
    backend_kind: "text_or_csv"
    acquisition: "imported"
    required: false
    source_ref:
      type: "external_path"
      value: "secret-or-external://order-feed"

analysis:
  bundle_selection: "approved_only"

graphify:
  enabled: true
  required_before_phases: true
  input_policy: "approved_bundle_only"
```

Supported source references are `local_path`, `workspace_path`, `external_path`, `secret_ref`, `bundle_ref`, and `generated_ref`. The manifest never contains literal passwords, tokens, or SQL credentials.

The `profile` alias is optional user guidance; `classification` is the authoritative resolved profile. When both are present and disagree, validation fails rather than silently choosing one.

### 7.1 Legacy compatibility

V2.7 reads V2.1 manifests, maps current declarations to candidate artifacts, proposes a classification with evidence, and emits `legacy-manifest-migration.json`. It does not rewrite the manifest without explicit migration. `$ak assess` remains available, but new Phase publication is blocked when classification ambiguity affects mandatory coverage.

## 8. Input Staging and Acceptance

User-supplied files first enter an acquisition staging area:

```text
staging/<ACQUISITION_ID>/
├─ incoming/
├─ classified/
├─ quarantine/
├─ acquisition-plan.json
└─ acquisition-result.json
```

Classification uses declared artifact role, extension and file signature, exporter metadata, safely inspectable internal metadata, and project-profile rules. Extension alone never approves an artifact.

Files enter quarantine when their type is unknown, they conflict with declared artifacts, duplicate objects differ, archives contain undeclared binaries, paths escape staging, provenance cannot be reconstructed, encoding conversion would lose information, or the active profile prohibits them. Quarantined files are excluded from indexing and Graphify.

Acquisition states:

- `VALID`: all mandatory acquisition rules passed;
- `PARTIAL`: accepted artifacts exist but optional or phase-specific inputs are missing;
- `INVALID`: the artifact set violates the profile contract;
- `BLOCKED`: authorization, runtime, secrets, or an external system prevents acquisition.

## 9. Acquisition Adapter Contract

Each adapter has one responsibility: produce typed acquisition records from declared artifacts. Adapters do not create Phase documents or Graphify outputs.

Conceptual interface:

```python
class AcquisitionAdapter:
    adapter_id: str
    adapter_version: str
    supported_profiles: tuple[str, ...]
    supported_artifact_kinds: tuple[str, ...]

    def probe(self, request: AcquisitionRequest) -> CapabilityReport: ...
    def plan(self, request: AcquisitionRequest) -> AcquisitionPlan: ...
    def acquire(self, plan: AcquisitionPlan) -> AcquisitionResult: ...
    def normalize(self, result: AcquisitionResult) -> BundleContribution: ...
```

Every adapter must provide deterministic ID/version, explicit authorization requirements, declared read/write behavior, bounded paths, typed failures, source/output hashes, repeatable normalization, and no direct writes to canonical Phase outputs.

## 10. Managed Access Adapter

The existing Python and PowerShell extractors become the first managed adapter.

Preserved behavior:

- runtime probe before snapshot creation;
- original database remains unopened;
- byte-for-byte snapshot and SHA-256 verification;
- immutable extraction session;
- external password reference only;
- redacted connections;
- PARTIAL status for protected or unsupported objects.

New behavior:

- typed object collections instead of generic components only;
- coverage by object type;
- skipped, failed, protected, and unsupported object lists;
- producer and transformation metadata;
- declared and inferred project context kept separate;
- normalization into the canonical bundle;
- no canonical approval until bundle validation passes.

## 11. Imported Source Adapter

The imported adapter accepts packaged exporter output, supported third-party exports, manually organized source with a valid import manifest, and legacy loose sources routed through a one-time classifier.

It must identify the producer format, validate its manifest, map object types, preserve exact original names, detect safe-name collisions, detect conflicting duplicates, validate encoding without silent replacement, record unsupported fields, and emit the same bundle contribution schema as managed extraction.

## 12. SQL Server Acquisition

SQL Server acquisition is separate because ADP and pass-through applications contain server-side behavior that Access extraction cannot make authoritative.

Supported V2.7 inputs:

- DDL and programmable-object scripts;
- catalog metadata export;
- DACPAC or equivalent schema package after deterministic extraction;
- explicitly authorized read-only metadata connection;
- schema/code exported from an isolated restored backup.

### 12.1 BAK policy

BAK files are optional, remain outside Git and the shareable app workspace, are referenced through external metadata, are restored only into an isolated SQL Server instance, never enter Graphify or the canonical bundle as raw binaries, and contribute only approved exports and restore audit metadata.

### 12.2 MDF/LDF policy

Direct MDF/LDF attachment is unsupported in standard V2.7. A future specialist adapter requires version compatibility, complete-file-set validation, immutable copies, attach isolation, and cleanup rules.

## 13. Canonical Extraction Bundle

Approved bundles live at `extracted/bundles/<BUNDLE_ID>/`:

```text
<BUNDLE_ID>/
├─ bundle.json
├─ checksums.sha256
├─ provenance.json
├─ profile-validation.json
├─ coverage.json
├─ phase-readiness.json
├─ databases/
│  ├─ objects.json
│  ├─ tables.json
│  ├─ fields.json
│  ├─ indexes.json
│  └─ declared-relationships.json
├─ code/
│  ├─ vba/
│  ├─ access-sql/
│  └─ sql-server/
├─ ui/
│  ├─ forms/
│  ├─ reports/
│  └─ macros/
├─ interfaces/
│  ├─ linked-tables.json
│  ├─ file-interfaces.json
│  └─ connections.redacted.json
├─ evidence-sources/
│  ├─ documents/
│  │  ├─ inventory.json
│  │  └─ extracted-text/
│  ├─ screenshots/
│  │  ├─ inventory.json
│  │  └─ navigation-map.json
│  ├─ reports/
│  │  ├─ inventory.json
│  │  └─ extracted-structure/
│  └─ samples/
│     ├─ inventory.json
│     └─ profiles/
└─ failures/
   └─ extraction-failures.json
```

Bundle identity derives from app ID, resolved classification and rule versions, sorted logical artifact IDs and content hashes, adapter IDs/versions, bundle schema version, and normalization configuration. Absolute machine paths and timestamps do not participate.

Approved bundles are immutable. New evidence, corrected encoding, or new adapter versions create new bundle IDs. Shareable bundles prohibit raw MDB, ACCDB, ADP, MDE, ACCDE, BAK, MDF, LDF, credentials, and unredacted connections.

Documents, spreadsheets, PDFs, screenshots, reports, and sample files enter the bundle only as approved normalized text/JSON, structural metadata, redacted profiles, and provenance records. Their original binaries remain external and are referenced by logical artifact ID and hash when permitted. A Phase may use an original binary through a specialized authorized renderer, but the resulting evidence receipt and normalized output become the bundle contribution.

### 13.1 Canonical normalization

Text is normalized to UTF-8 with LF line endings only when conversion is lossless. Original encoding and source hash remain in provenance. JSON outputs use stable key ordering, normalized logical paths, deterministic array ordering where order is not semantic, and no generated timestamp in content identity.

### 13.2 Bundle cache and distribution

`extracted/bundles/` is a local cache, not automatically the team authority. The application repository commits `bundle.lock.json`, containing bundle ID, checksum, schema version, resolved classification, approved location/reference, and approval record ID.

Supported distribution policies:

- `local_only` for one-machine investigation;
- `shared_path` for a controlled read-only team share;
- `artifact_store` as the default multi-developer production policy;
- `git_allowed` only for synthetic or explicitly approved non-sensitive bundles.

Production bundles are not committed merely because they contain text. Exported VBA, SQL, object names, and documents may remain proprietary.

### 13.3 Bundle approval

Approval is stored outside the immutable bundle in `bundle-approval.json`. It records bundle ID/checksum, validator and schema versions, validation result, coordinator/approver, approval timestamp, distribution policy, and superseded bundle when applicable. Approval cannot alter bundle contents.

## 14. Phase Readiness

`phase-readiness.json` is computed by profile rules.

Allowed states:

- `READY`: mandatory technical evidence is present;
- `LIMITED`: a bounded phase scope is permitted and declared in the report;
- `BLOCKED`: required technical evidence is absent;
- `NOT_APPLICABLE`: the profile proves the input category does not exist.

A waiver may acknowledge optional or externally unavailable evidence, but cannot convert missing technical core evidence into `READY`. Waivers record rule ID, approver, reason, affected scope, review condition, and accepted risk. Security, authorization, integrity, and path-confinement rules cannot be waived.

### 14.1 Baseline phase rules

Resolved classification rules may strengthen this matrix but may not weaken security or integrity requirements.

| Phase | Minimum technical evidence | Limited behavior | Blocked condition |
|---|---|---|---|
| Phase 1 | Authoritative backend/schema inventory, fields, keys/indexes, boundaries | Missing samples or unverified inferred relationships are explicit gaps | No authoritative schema for an in-scope backend |
| Phase 2 | Form/report/macro inventory and event/control metadata, or proved data-only component | Compiled-only or screenshot-only UI evidence | Claimed complete UI analysis without inspectable UI source/evidence |
| Phase 3 | VBA/query/server-code inventory and data/file effects | Missing source behind a compiled or external boundary | Required code tier absent with no bounded scope |
| Phase 4 | Triggers, processing chain, affected data/interfaces, observable outputs | Missing runtime samples or operator confirmation | No evidence-backed path from trigger to effect/output |
| Phase 5 | Declared business/system documents and comparison scope | No documents produces a gap-focused limited report | Document claims are made from undeclared or untraceable sources |
| Phase 6 | Accepted outputs/readiness from prior phases and unresolved-risk register | Synthesis explicitly preserves limited sections | Unresolved critical source-integrity or system-thesis blockers |

`NOT_APPLICABLE` requires positive evidence, such as a data-only backend with no UI objects. Absence alone does not prove non-applicability.

## 15. Deterministic Analysis Model

V2.8 introduces a stable intermediate model before Graphify:

```text
approved bundle
    ├─ object index
    ├─ symbol index
    ├─ VBA call graph
    ├─ SQL AST and dependencies
    ├─ CRUD matrix
    ├─ UI event/navigation graph
    ├─ relationship candidates
    └─ file/system interface map
             |
             v
      analysis-model.json
```

Every relationship records source, target, relation type, evidence location, parser/extraction method, status, confidence when inferred, and proof gaps. The result is deterministic for a given bundle, parser set, analyzer version, and configuration.

## 16. Graphify Role

Graphify readiness is checked before each Phase, but semantic build/update occurs only when the approved bundle ID, deterministic analysis-model hash, Graphify version, or normalization configuration changes. An unchanged graph is reused and only the phase-specific query receipt is refreshed. Its input changes from broad workspace roots to approved bundle content plus deterministic analysis output.

Graphify may support semantic discovery, component clustering, phase retrieval, candidate cross-source connections, and navigation of large source sets.

Graphify may not create authoritative object inventory, replace VBA/SQL parsing, convert inferred edges into extracted evidence, read database binaries, or override profile and phase gates.

## 17. OSS Integration Policy

### 17.1 `msaccess-vcs-addin`

V2.7.1 adds an importer for supported producer-format versions. The tool is not a mandatory installation and is not initially vendored. AK preserves producer version, unsupported fields, exact object names, and source provenance. Copying code requires a separate license and attribution review.

### 17.2 UCanAccess and Jackcess

V2.8 may add an optional Java sidecar for cross-platform MDB/ACCDB schema and authorized data profiling. It supplements, but does not replace, Access automation for forms, reports, macros, VBA, or ADP.

### 17.3 SQLGlot

V2.8 may use SQLGlot for T-SQL and supported dialects. Access SQL requires an AK dialect extension and explicit PARTIAL fallback for unsupported syntax.

### 17.4 Rubberduck and CodeWiki

Rubberduck and CodeWiki remain architecture and analysis inspiration only. They are not core dependencies and their code is not vendored without separate legal and technical review.

### 17.5 Dependency acceptance

Every dependency or external producer adapter requires license classification, maintenance status, platform support, deterministic-output assessment, security/network review, pinning policy, fallback behavior, and synthetic contract fixtures.

## 18. Agent and CLI Behavior

Existing agent commands remain valid. V2.7 adds `$ak acquire`.

| Command | V2.7 behavior |
|---|---|
| `$ak init <APP_ID>` | Require or detect project classification and scaffold rule-specific guidance. |
| `$ak assess <APP_ID>` | Detect classification candidates with evidence, compare them to declarations, validate artifacts/quarantine, and report acquisition readiness without analysis. |
| `$ak acquire <APP_ID>` | Run declared adapters and attempt to produce an approved bundle. |
| `$ak phase <1-6> <APP_ID>` | Require an approved bundle and non-blocked phase readiness before Graphify. |
| `$ak run <APP_ID>` | Run only technically permitted phases and stop on `BLOCKED`. |
| `$ak status <APP_ID>` | Show profile, active bundle, phase readiness, run, QA, and publication state. |
| `$ak render <APP_ID> [LANGUAGE]` | Preserve current Phase 6, traceability, and QA prerequisites. |

`run` still does not authorize live Access, ADP, SQL Server, backup restore, or network access.

The deterministic CLI gains bounded subcommands:

```text
ak.py profile detect
ak.py profile validate
ak.py acquire plan
ak.py acquire run
ak.py bundle validate
ak.py bundle approve
ak.py manifest migrate
```

## 19. Documentation Structure

Package docs remain English canonical and document the shared pipeline once:

```text
docs/
├─ architecture/
│  ├─ investigation-pipeline.md
│  └─ extraction-bundle.md
├─ project-classification/
│  ├─ topology-rules.md
│  ├─ frontend-format-rules.md
│  ├─ source-availability-rules.md
│  ├─ backend-rules.md
│  └─ resolved-examples.md
├─ acquisition/
│  ├─ decision-guide.md
│  ├─ managed-access.md
│  ├─ imported-sources.md
│  └─ sql-server.md
├─ analysis/
│  ├─ deterministic-model.md
│  ├─ graphify-integration.md
│  └─ phase-readiness.md
└─ collaboration/
   ├─ contributor-workflow.md
   ├─ contract-changes.md
   └─ application-team-workflow.md
```

Adapter docs cover only prerequisites, commands, adapter-specific failures, and bundle contribution behavior.

## 20. Application Output Design

V2.7 preserves the six Phase documents and required control outputs while standardizing technical appendices.

Phase 1 canonical set:

```text
<APP_ID>_Phase1_DataUnderstanding_<LANG>.md
<APP_ID>_Phase1_DataModel_<LANGS>.md
<APP_ID>_Phase1_DataDictionary_<LANGS>.md
<APP_ID>_QuestionList.md
<APP_ID>_QA_Report.md
<APP_ID>_Evidence.json
<APP_ID>_TraceabilityMatrix.csv
```

The Phase report is business-readable and table-first. Data Model contains logical domains and current-state relationships. Data Dictionary contains complete schema detail. Declared keys and inferred relationships remain distinct. Generated render pages stay in run artifacts rather than becoming primary design documents.

Data Model and Data Dictionary are required Phase 1 technical appendices whenever Phase 1 is `READY` or `LIMITED`. A limited appendix remains required but must expose its exact coverage and blockers. This is an intentional V2.7 output-contract change with migration validation.

### 20.1 Refactoring handoff output

Because the kit exists to feed refactoring and replacement development, Phase 6 emits a dedicated handoff:

```text
<APP_ID>_RefactoringHandoff_<LANG>.md
```

It contains a current-state capability map, domain and boundary model, external interface contracts, data-integrity rules that any replacement must preserve, behavior that is safe to change versus must be preserved, migration risks, and open decisions. Every statement links to evidence IDs and carries `EXTRACTED`, `INFERRED`, or `AMBIGUOUS` status. The handoff is a derived output; it does not introduce facts absent from evidence and the approved bundle.

Prerequisites are accepted Phase 6, traceability validation, independent QA, and no unresolved critical source-integrity conflict. The handoff may remain blocked while the six investigation phases are retained as historical outputs.

## 21. Multi-Developer Collaboration

### 21.1 Repository ownership

Add `.github/CODEOWNERS` for contracts/schemas, project profiles, Access adapters, imported-source adapters, SQL analyzers, documentation templates, orchestration, and releases.

### 21.2 Target code organization

```text
plugins/ak/
├─ profiles/
├─ adapters/
│  ├─ managed_access/
│  ├─ imported_sources/
│  ├─ msaccess_vcs/
│  ├─ sql_server/
│  └─ ucanaccess/
├─ contracts/
├─ analyzers/
│  ├─ access_objects/
│  ├─ vba/
│  ├─ sql/
│  └─ interfaces/
├─ fixtures/
└─ tests/
   ├─ contract/
   ├─ profiles/
   ├─ adapters/
   ├─ analyzers/
   ├─ orchestration/
   └─ integration/
```

Existing scripts remain compatibility entrypoints until they delegate to focused modules.

### 21.3 Human work packages

Human developers and agents use the same immutable bundle and scoped work contract. A work package records task ID, bundle ID, assigned module/profile/adapter, allowed write paths, expected artifacts, evidence namespace, dependencies, validation commands, and reviewer/coordinator.

Only the coordinator or designated document owner merges canonical Phase outputs.

### 21.4 Contract changes

A PR changing a profile, schema, adapter output, or readiness rule includes contract impact, migration behavior, synthetic fixtures, compatibility tests, docs, validation evidence, untested runtime paths, and security/data-handling impact.

## 22. Testing Strategy

Maintain at least one complete and one intentionally incomplete synthetic fixture per profile. Fixtures contain invented data only and no proprietary database binaries.

Golden-test deterministic outputs:

- profile detection and validation;
- acquisition plans;
- bundle manifests;
- object inventories;
- coverage and phase readiness;
- component indexes;
- SQL AST;
- CRUD matrices;
- relationship candidates;
- schema migrations;
- evidence references.

Do not exact-text golden-test LLM prose. Document tests validate required sections/tables, evidence links, filenames, Mermaid syntax, UTF-8, language declarations, no unsupported physical-FK claims, and no raw database or credential paths.

Required CI covers Linux/Windows package tests, supported Python versions, JSON Schemas, profile fixtures, adapter import, bundle reproducibility, docs, and PowerShell parsing.

Controlled integration CI may use self-hosted Windows Access and isolated SQL Server runners. Hosted CI must not claim live extraction passed when it only parsed scripts or ran dry-run behavior.

## 23. Security and Data Handling

Never commit or include in shareable bundles:

- MDB, ACCDB, ADP, MDE, ACCDE;
- BAK, MDF, LDF;
- credential-bearing DSNs;
- passwords, tokens, or connection secrets;
- production row dumps;
- unredacted connection strings;
- proprietary artifacts in the public kit repository.

Adapters verify that resolved paths remain inside declared roots before recursive copy, move, or delete operations. Imported archives are protected against path traversal and unexpected executable content.

Data profiling defaults to metadata and aggregate statistics. Representative row extraction requires explicit authorization, documented masking, and retention rules.

## 24. Backward Compatibility and Migration

V2.7 behavior:

- V2.1 manifests remain readable;
- existing extraction sessions remain evidence but are not automatically approved bundles;
- existing `sources/vba` and `sources/sql` can be imported by the legacy adapter;
- existing Graphify outputs are rebuilt from approved bundles;
- historical Phase outputs are not silently rewritten.

`ak.py manifest migrate` creates a proposed V2.2 manifest and report without overwriting the original. The report lists candidate profile, mapped artifacts, ambiguous roles, missing mandatory inputs, quarantined paths, and required bundle/Graphify rebuilds.

V2.7 warns on legacy unprofiled Phase execution. V2.8 may require an approved profile and bundle for new runs. V3 may remove legacy direct-source execution.

## 25. Delivery Plan

### 25.1 V2.7.0: Profile and Bundle Foundation

- classification schema and topology, frontend, source-availability, and backend rule fragments;
- Manifest V2.2 compatibility reader;
- staging and quarantine;
- acquisition adapter contract;
- Extraction Bundle schemas;
- strict validation and phase readiness;
- managed Access adapter migration;
- legacy/imported source adapter;
- `$ak acquire` routing;
- English canonical docs;
- bundle lock/approval and distribution policy;
- required Phase 1 Data Model/Data Dictionary contract;
- Phase 6 Refactoring Handoff contract;
- CODEOWNERS and contract-oriented tests.

### 25.2 V2.7.1: External Producer Integration

- `msaccess-vcs-addin` importer;
- SQL Server script/catalog importer;
- producer compatibility fixtures;
- stronger collision, encoding, and unsupported-object reporting.

### 25.3 V2.8: Deterministic Analysis Acceleration

- SQLGlot-based SQL analysis with Access extension;
- VBA symbol, procedure, reference, and call extraction;
- CRUD matrix;
- UI event/navigation graph;
- relationship inference registry;
- stable analysis model;
- incremental cache;
- optional UCanAccess/Jackcess sidecar.

### 25.4 Implementation-plan decomposition

Implementation planning must use three independently testable plans rather than one repository-wide plan:

1. **Classification and Bundle Foundation:** Manifest V2.2, rule fragments, staging/quarantine, bundle schemas, approval/lock/distribution, migration, and readiness.
2. **Acquisition Adapters:** managed Access migration, imported-source adapter, SQL Server importer, and external producer adapters.
3. **Deterministic Analysis and Refactoring Handoff:** SQL/VBA analyzers, analysis model, Graphify input migration, technical appendices, and Refactoring Handoff.

Each plan must leave the package usable and backward-compatible at its checkpoint.

### 25.5 V3 entry criteria

V3 begins only after successful trials on one split MDB application, one ACCDB application using ACCDB-specific features, and one ADP/SQL Server application. Each trial records profile gaps, adapter failures, migrations, analysis accuracy, documentation usefulness, and contributor workflow issues.

## 26. Acceptance Criteria

Implementation is accepted when:

1. Every new run has a resolved classification and an approved bundle ID recorded in `bundle.lock.json`.
2. Loose files cannot enter Graphify or Phase analysis without classification and provenance.
3. Managed and imported acquisition produce schema-equivalent bundles.
4. ADP without SQL Server schema blocks complete Phase 1 and Phase 3.
5. Split projects expose frontend/backend authority and missing-backend blockers.
6. Compiled frontends cannot produce a false complete-VBA claim.
7. Raw database and backup files are absent from approved bundles.
8. Phase readiness is reproducible from classification rule fragments and bundle contents.
9. V2.1 workspaces receive non-destructive migration reports.
10. Complete and incomplete fixtures cover every rule fragment, with pairwise representative combinations across topology, frontend format, source availability, and backend kind.
11. Adapter tests run independently from Phase generation.
12. Deterministic outputs reproduce for the same inputs and tool versions.
13. Graphify consumes approved bundle and deterministic analysis content only.
14. Contributors can work against one bundle without sharing canonical write paths.
15. Shared workflow docs are not duplicated across adapters.
16. A resolved classification and its rule-fragment versions are recorded for every run.
17. A `profile` alias that disagrees with `classification` fails validation.
18. Phase 6 produces a `RefactoringHandoff` output whose statements resolve to evidence IDs.
19. Production bundles follow distribution policy and are not committed unless synthetic or explicitly approved.

## 27. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Rule combinations become excessive | Keep independent rule fragments and test pairwise representative combinations instead of every Cartesian product. |
| Strict gates block partial value | Permit explicit `LIMITED` scope, never false completion. |
| Producer format changes | Pin supported versions and maintain fixtures. |
| Optional Java sidecar adds burden | Keep it optional and outside V2.7.0 requirements. |
| Access runtime is absent in hosted CI | Use synthetic tests and controlled self-hosted integration. |
| Bundle schemas evolve | Version schemas and provide explicit migrations. |
| Contributors conflict on contracts | CODEOWNERS, focused PRs, migration tests, coordinator integration. |
| Graph output varies | Keep evidence and deterministic analysis independent. |
| Backups expose data | External-only reference, isolated restore, no raw backup in bundle. |

## 28. Final Architectural Decisions

1. V2.7 uses two acquisition methods and one bundle contract.
2. Classification captures topology, frontend format, source availability, and backend authority; extension alone is never sufficient.
3. Projects use composable classification (topology, frontend format, source availability, backend kinds); aliases are guidance only and acquisition method is independent.
4. ADP requires SQL Server schema evidence.
5. BAK is optional and external-only.
6. MDF/LDF attachment is outside standard V2.7.
7. Unknown or conflicting imported files are quarantined.
8. Missing mandatory technical evidence blocks or limits affected phases.
9. The approved bundle, not loose workspace directories, is the analysis source.
10. Deterministic analyzers precede Graphify.
11. OSS integrates through producer/import/sidecar adapters.
12. English is the canonical package language.
13. Existing V2 workspaces migrate non-destructively.
14. Humans and agents share bundle and scoped-write contracts.
15. V3 waits for evidence from three materially different trials.

## 29. References

- Microsoft Access file formats: https://support.microsoft.com/en-US/Access/which-access-file-format-should-i-use
- Microsoft Access Data Projects: https://support.microsoft.com/en-us/access/create-an-access-project
- SQL Server backups: https://learn.microsoft.com/en-us/sql/relational-databases/backup-restore/create-a-full-database-backup-sql-server
- msaccess-vcs-addin: https://github.com/joyfullservice/msaccess-vcs-addin
- UCanAccess: https://github.com/spannm/ucanaccess
- Jackcess: https://github.com/jahlborn/jackcess
- SQLGlot: https://github.com/tobymao/sqlglot
- Rubberduck: https://github.com/rubberduck-vba/rubberduck
- CodeWiki: https://github.com/FSoft-AI4Code/CodeWiki
