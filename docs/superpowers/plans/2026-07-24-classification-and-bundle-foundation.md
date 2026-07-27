# Classification and Bundle Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a backward-compatible V2.7 foundation where every project can be resolved to a composable classification and every accepted input can be represented by an approved, immutable Canonical Extraction Bundle before Graphify or Phase work.

**Architecture:** Add pure-Python contract modules under `plugins/ak/contracts/`, independently versioned rule fragments under `plugins/ak/profiles/`, and bounded `ak.py` subcommands. Keep V2.1 schemas, manifests, scripts, and outputs readable; V2.2 is additive and non-destructive. Adapter execution belongs to Plan 2; deterministic analyzers and Refactoring Handoff belong to Plan 3.

**Tech Stack:** Python 3.11, stdlib (`argparse`, `dataclasses`, `hashlib`, `json`, `pathlib`), PyYAML, JSON Schema draft 2020-12 via `jsonschema`, pytest. Fixtures are synthetic only.

**Design Spec:** `docs/superpowers/specs/2026-07-23-profile-driven-extraction-bundle-design.md` sections 6-8, 13-14, 18, 21-26.

---

## Boundaries

In scope: composable classification; rule fragments; Manifest V2.2 reader; staging/quarantine; bundle schemas/identity/immutability/lock/approval/distribution; readiness; legacy migration report; CLI; synthetic fixtures; CODEOWNERS and English canonical docs.

Out of scope: Access/imported/SQL acquisition adapters (Plan 2); SQL/VBA analyzers, analysis model, Graphify input migration, Data Model/Data Dictionary generation, Refactoring Handoff (Plan 3). V2.7 warns on legacy unprofiled phase execution; it does not hard-break V2.1 runs.

## Compatibility Invariants

- Existing `plugins/ak/schemas/manifest.schema.json` remains the V2.1 schema; V2.2 uses a separate schema.
- Existing script arguments and output shapes do not change.
- `python plugins/ak/scripts/validate_structure.py --package plugins/ak --repository-root .` remains green.
- `python -m pytest -q` remains green (baseline: 18 passed on July 24, 2026).
- No real MDB/ACCDB/ADP/BAK/MDF/LDF, credentials, proprietary artifacts, or production rows enter fixtures or Git.
- New contracts are deterministic; paths/timestamps never affect bundle identity.

## Planned File Map

Create:
- `plugins/ak/contracts/{__init__,classification,manifest_v22,staging,bundle,phase_readiness,migration}.py`
- `plugins/ak/profiles/{topology,frontend,source-availability,backend}.yaml` and `README.md`
- `plugins/ak/schemas/{classification-rule,manifest-v22,acquisition-plan,bundle,bundle-provenance,bundle-coverage,phase-readiness,bundle-lock,bundle-approval,legacy-manifest-migration}.schema.json`
- `plugins/ak/tests/test_{classification,manifest_v22,staging,bundle,phase_readiness,migration,cli_v27}.py`
- `plugins/ak/fixtures/` synthetic complete/incomplete representative profiles
- `.github/CODEOWNERS`
- `docs/architecture/{investigation-pipeline,extraction-bundle}.md` and `docs/project-classification/*.md`

Modify:
- `plugins/ak/scripts/ak.py` (new bounded subcommands only)
- `plugins/ak/scripts/validate_structure.py` (new required files + V2.2 validation)
- `plugins/ak/specifications/package.json` and version manifests (2.7.0 lock-step)

---

### Task 1: Classification rule schema and fragments

**Files:**
- Create: `plugins/ak/schemas/classification-rule.schema.json`
- Create: `plugins/ak/profiles/topology.yaml`
- Create: `plugins/ak/profiles/frontend.yaml`
- Create: `plugins/ak/profiles/source-availability.yaml`
- Create: `plugins/ak/profiles/backend.yaml`
- Create: `plugins/ak/profiles/README.md`
- Test: `plugins/ak/tests/test_classification.py`

- [ ] **Step 1: Write the failing schema/fragment tests**

```python
# plugins/ak/tests/test_classification.py
import json
from pathlib import Path
import jsonschema
import yaml

PACKAGE = Path(__file__).resolve().parents[1]
PROFILES = PACKAGE / "profiles"

def test_all_rule_fragments_validate_and_ids_are_unique():
    schema = json.loads((PACKAGE / "schemas/classification-rule.schema.json").read_text(encoding="utf-8"))
    files = {
        "topology": "topology.yaml",
        "frontend": "frontend.yaml",
        "source_availability": "source-availability.yaml",
        "backend": "backend.yaml",
    }
    seen = set()
    for dimension, filename in files.items():
        rules = yaml.safe_load((PROFILES / filename).read_text(encoding="utf-8"))["rules"]
        assert rules
        for rule in rules:
            jsonschema.validate(rule, schema)
            assert rule["dimension"] == dimension
            assert rule["id"] not in seen
            seen.add(rule["id"])

def test_adp_rule_requires_sql_server_schema():
    rules = yaml.safe_load((PROFILES / "frontend.yaml").read_text(encoding="utf-8"))["rules"]
    adp = next(rule for rule in rules if rule["id"] == "frontend.adp.sql_server_context")
    assert "sql_server_schema_evidence" in adp["require"]["all"]
    assert adp["affects"]["phase1"] == "BLOCKED"
    assert adp["affects"]["phase3"] == "BLOCKED"
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `python -m pytest plugins/ak/tests/test_classification.py -q`
Expected: FAIL because schema/profile files do not exist.

- [ ] **Step 3: Add the schema**

`classification-rule.schema.json` must require `id`, `version`, `dimension`, `when`, `require`; dimension enum is `topology|frontend|source_availability|backend`; `require` permits `all` and `any` string arrays; `affects` maps `phase1`...`phase6` to `READY|LIMITED|BLOCKED|NOT_APPLICABLE`; `allow_limited_when` is a string array; top-level `additionalProperties` is false.

- [ ] **Step 4: Add independently versioned rules**

Required value coverage: topology `monolith|split_file|client_server|hybrid`; frontend `mdb|accdb|adp|mde|accde|exported`; source availability `full|compiled_only|exported_only|mixed`; backend `embedded_access|access_file|sql_server|odbc_database|text_or_csv|spreadsheet|external_application|unknown_boundary`. Use stable IDs from the design spec, including `frontend.adp.sql_server_context`, `backend.sql_server.programmable_objects`, and `backend.unknown_boundary.blocks_ready`.

- [ ] **Step 5: Run tests, register files, commit**

```bash
python -m pytest plugins/ak/tests/test_classification.py -q
python plugins/ak/scripts/validate_structure.py --package plugins/ak --repository-root .
git add plugins/ak/schemas/classification-rule.schema.json plugins/ak/profiles plugins/ak/tests/test_classification.py plugins/ak/scripts/validate_structure.py
git commit -m "feat(classification): add composable rule fragments"
```

---

### Task 2: Classification resolver and alias reconciliation

**Files:**
- Create: `plugins/ak/contracts/__init__.py`
- Create: `plugins/ak/contracts/classification.py`
- Modify: `plugins/ak/tests/test_classification.py`

- [ ] **Step 1: Add failing resolver tests**

```python
import sys
import pytest
sys.path.insert(0, str(PACKAGE / "contracts"))
from classification import Classification, ClassificationError, resolve_classification, reconcile_alias  # noqa: E402

def test_resolve_returns_rule_ids_and_versions():
    c = Classification("split_file", "mdb", "full", ("access_file", "text_or_csv"))
    resolved = resolve_classification(c, PROFILES)
    assert "topology.split_file.backend_required" in resolved.rule_ids
    assert resolved.rule_versions["frontend.mdb.dao"] == "1.0"

def test_alias_disagreement_fails():
    c = Classification("split_file", "mdb", "full", ("access_file",))
    reconcile_alias("access-file-split", c)
    with pytest.raises(ClassificationError):
        reconcile_alias("access-adp-sqlserver", c)

def test_invalid_dimension_fails():
    with pytest.raises(ClassificationError):
        Classification("galaxy", "mdb", "full", ("access_file",))
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest plugins/ak/tests/test_classification.py -q`
Expected: FAIL because `classification.py` is missing.

- [ ] **Step 3: Implement minimal resolver**

Create frozen dataclasses `Classification` and `ResolvedClassification`. Validate dimension enums in `Classification.__post_init__`. `resolve_classification()` loads the four fragment files, selects matching `when` rules, sorts rule IDs, and returns exact rule versions plus merged effects. `reconcile_alias()` implements only the four friendly aliases in spec 6.5; aliases constrain the authoritative classification and never replace it. Raise `ClassificationError` on disagreement (acceptance criterion 17).

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest plugins/ak/tests/test_classification.py -q
git add plugins/ak/contracts plugins/ak/tests/test_classification.py plugins/ak/scripts/validate_structure.py
git commit -m "feat(classification): resolve dimensions and reconcile aliases"
```

---

### Task 3: Manifest V2.2 additive reader

**Files:**
- Create: `plugins/ak/schemas/manifest-v22.schema.json`
- Create: `plugins/ak/contracts/manifest_v22.py`
- Create: `plugins/ak/tests/test_manifest_v22.py`

- [ ] **Step 1: Write failing V2.1/V2.2 compatibility tests**

```python
# plugins/ak/tests/test_manifest_v22.py
import sys
from pathlib import Path
import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))
from manifest_v22 import load_manifest, ManifestError  # noqa: E402

V22 = """
version: "2.2"
app: {id: "A05", name_en: "Product Picking Support"}
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
    source_ref: {type: "local_path", value: "sources/access/frontend.mdb"}
"""

def test_v21_remains_readable():
    manifest = load_manifest(PACKAGE / "references" / "manifest.example.yaml")
    assert manifest.version == "2.1"
    assert manifest.classification is None
    assert manifest.artifacts == ()

def test_v22_reads_classification_and_artifacts(tmp_path):
    path = tmp_path / "manifest.yaml"
    path.write_text(V22, encoding="utf-8")
    manifest = load_manifest(path)
    assert manifest.classification.topology == "split_file"
    assert manifest.artifacts[0].source_ref.type == "local_path"

def test_alias_disagreement_fails(tmp_path):
    path = tmp_path / "manifest.yaml"
    path.write_text(V22.replace("access-file-split", "access-adp-sqlserver"), encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(path)
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest plugins/ak/tests/test_manifest_v22.py -q`
Expected: FAIL because V2.2 reader/schema are missing.

- [ ] **Step 3: Add schema and reader**

Keep `manifest.schema.json` unchanged for V2.1. New schema requires for V2.2: `project.classification` with four dimensions; optional `project.profile`/`profile_version`; `artifacts[]` with `id`, `kind`, `role`, `acquisition` (`managed|imported|mixed`), `required`, and `source_ref.type` (`local_path|workspace_path|external_path|secret_ref|bundle_ref|generated_ref`). Reader returns dataclasses and calls Task 2 alias reconciliation. For V2.1 return `classification=None`, `artifacts=()`; do not infer or rewrite.

- [ ] **Step 4: Run all compatibility tests and commit**

```bash
python -m pytest plugins/ak/tests/test_manifest_v22.py plugins/ak/tests/test_package_smoke.py -q
python plugins/ak/scripts/validate_structure.py --package plugins/ak --repository-root .
git add plugins/ak/schemas/manifest-v22.schema.json plugins/ak/contracts/manifest_v22.py plugins/ak/tests/test_manifest_v22.py plugins/ak/scripts/validate_structure.py
git commit -m "feat(manifest): add non-destructive V2.2 reader"
```

---

### Task 4: Staging, quarantine, and acquisition states

**Files:**
- Create: `plugins/ak/schemas/acquisition-plan.schema.json`
- Create: `plugins/ak/contracts/staging.py`
- Create: `plugins/ak/tests/test_staging.py`

- [ ] **Step 1: Write failing security/acceptance tests**

```python
# plugins/ak/tests/test_staging.py
import sys
from pathlib import Path
PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))
from staging import acceptance_state, classify_incoming  # noqa: E402

def test_extension_alone_never_accepts(tmp_path):
    candidate = tmp_path / "fake.mdb"
    candidate.write_bytes(b"not-access")
    decision = classify_incoming(candidate, declared_kind="access_database", signature_ok=False, staging_root=tmp_path)
    assert decision.destination == "quarantine"
    assert decision.reason == "SIGNATURE_MISMATCH"

def test_path_escape_quarantines(tmp_path):
    decision = classify_incoming(Path("../../outside.txt"), declared_kind="text_or_csv", signature_ok=True, staging_root=tmp_path)
    assert decision.reason == "PATH_ESCAPE"

def test_acceptance_states_are_rule_based():
    assert acceptance_state(True, False, [], False) == "VALID"
    assert acceptance_state(True, True, [], False) == "PARTIAL"
    assert acceptance_state(False, True, ["conflict"], False) == "INVALID"
    assert acceptance_state(False, False, [], True) == "BLOCKED"
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest plugins/ak/tests/test_staging.py -q`
Expected: FAIL because module/schema are missing.

- [ ] **Step 3: Implement bounded staging decisions**

`classify_incoming()` returns `StagingDecision(destination, reason)` and quarantines unknown/signature mismatch, artifact conflict, duplicate mismatch, undeclared binary in archive, path escape, missing provenance, lossy encoding, or profile prohibition (spec 8). `acceptance_state()` returns `VALID|PARTIAL|INVALID|BLOCKED`. Schema covers `staging/<ACQUISITION_ID>/acquisition-plan.json` and result records; adapters do not run in this task.

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest plugins/ak/tests/test_staging.py -q
git add plugins/ak/schemas/acquisition-plan.schema.json plugins/ak/contracts/staging.py plugins/ak/tests/test_staging.py plugins/ak/scripts/validate_structure.py
git commit -m "feat(staging): add quarantine and acceptance contracts"
```

---

### Task 5: Canonical bundle schemas, identity, lock, and approval

**Files:**
- Create: `plugins/ak/schemas/bundle.schema.json`
- Create: `plugins/ak/schemas/bundle-provenance.schema.json`
- Create: `plugins/ak/schemas/bundle-coverage.schema.json`
- Create: `plugins/ak/schemas/bundle-lock.schema.json`
- Create: `plugins/ak/schemas/bundle-approval.schema.json`
- Create: `plugins/ak/contracts/bundle.py`
- Create: `plugins/ak/tests/test_bundle.py`

- [ ] **Step 1: Write failing deterministic/immutability tests**

```python
# plugins/ak/tests/test_bundle.py
import hashlib
import json
import sys
from pathlib import Path
import jsonschema
import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))
from bundle import BundleError, compute_bundle_id, make_lock, verify_immutable  # noqa: E402

BASE = {
    "app_id": "A05",
    "classification_rule_versions": {"frontend.mdb.dao": "1.0"},
    "artifacts": [{"logical_id": "A05_FRONTEND", "content_sha256": "a" * 64}],
    "adapters": [{"id": "managed_access", "version": "2.7.0"}],
    "bundle_schema_version": "1.0",
    "normalization_config": {"encoding": "utf-8", "line_endings": "LF"},
}

def test_id_ignores_paths_and_timestamps():
    noisy = dict(BASE, _absolute_path="D:/machine", _generated_at="2026-07-24T00:00:00Z")
    assert compute_bundle_id(noisy) == compute_bundle_id(BASE)

def test_id_changes_when_content_changes():
    changed = dict(BASE, artifacts=[{"logical_id": "A05_FRONTEND", "content_sha256": "b" * 64}])
    assert compute_bundle_id(changed) != compute_bundle_id(BASE)

def test_immutable_hash_verification(tmp_path):
    file = tmp_path / "bundle.json"
    file.write_text("{}", encoding="utf-8")
    expected = {"bundle.json": hashlib.sha256(b"{}").hexdigest()}
    verify_immutable(tmp_path, expected)
    file.write_text("{ }", encoding="utf-8")
    with pytest.raises(BundleError):
        verify_immutable(tmp_path, expected)

def test_lock_has_external_approval_reference():
    lock = make_lock("bundle-abc", "c" * 64, "1.0", {"topology": "split_file"}, "artifact_store://a05", "AP-1")
    assert lock["approval_record_id"] == "AP-1"

def test_bundle_schema_requires_normalized_evidence_sources():
    schema = json.loads((PACKAGE / "schemas/bundle.schema.json").read_text(encoding="utf-8"))
    bundle = {
        "schema_version": "1.0", "bundle_id": "bundle-abc", "app_id": "A05",
        "classification": {"topology": "split_file", "frontend_format": "mdb",
                           "source_availability": "full", "backend_kinds": ["access_file"]},
        "rule_versions": {"frontend.mdb.dao": "1.0"},
        "evidence_sources": {
            "documents": {"inventory": "evidence-sources/documents/inventory.json"},
            "screenshots": {"inventory": "evidence-sources/screenshots/inventory.json"},
            "reports": {"inventory": "evidence-sources/reports/inventory.json"},
            "samples": {"inventory": "evidence-sources/samples/inventory.json"},
        },
    }
    jsonschema.validate(bundle, schema)
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest plugins/ak/tests/test_bundle.py -q`
Expected: FAIL because bundle contracts are missing.

- [ ] **Step 3: Implement bundle controls**

`compute_bundle_id()` hashes canonical JSON containing app id, resolved classification/rule versions, sorted logical artifact IDs+hashes, adapter IDs/versions, bundle schema version, and normalization config. Ignore underscore-prefixed operational fields; reject absolute paths and timestamps in identity input. `verify_immutable()` recomputes every checksum. `make_lock()` emits `bundle.lock.json` with bundle id/checksum/schema/classification/location/approval id. `make_approval()` emits external `bundle-approval.json`; never writes inside the immutable bundle.

The bundle schema must model spec-13 paths: control files, `databases/`, `code/`, `ui/`, `interfaces/`, `evidence-sources/{documents,screenshots,reports,samples}/`, and `failures/`. Evidence-source binaries remain external; only normalized text/JSON, structure/profile outputs, logical artifact ID, permitted hash, and provenance enter the bundle. Distribution enum is `local_only|shared_path|artifact_store|git_allowed`; production defaults to `artifact_store`. Schemas prohibit raw Access/SQL backup files, credentials, production row dumps, and unredacted connections.

- [ ] **Step 4: Validate schema fixtures and commit**

```bash
python -m pytest plugins/ak/tests/test_bundle.py -q
python plugins/ak/scripts/validate_structure.py --package plugins/ak --repository-root .
git add plugins/ak/schemas/bundle*.schema.json plugins/ak/contracts/bundle.py plugins/ak/tests/test_bundle.py plugins/ak/scripts/validate_structure.py
git commit -m "feat(bundle): add canonical bundle identity and approval contracts"
```

---

### Task 6: Rule-based phase readiness

**Files:**
- Create: `plugins/ak/schemas/phase-readiness.schema.json`
- Create: `plugins/ak/contracts/phase_readiness.py`
- Create: `plugins/ak/tests/test_phase_readiness.py`

- [ ] **Step 1: Write failing readiness tests**

```python
# plugins/ak/tests/test_phase_readiness.py
import sys
from pathlib import Path
PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))
from classification import Classification  # noqa: E402
from phase_readiness import compute_readiness  # noqa: E402

PROFILES = PACKAGE / "profiles"

def test_adp_without_sql_schema_blocks_phase1_and_phase3():
    c = Classification("client_server", "adp", "full", ("sql_server",))
    result = compute_readiness(c, PROFILES, set())
    assert result["phase1"]["status"] == "BLOCKED"
    assert result["phase3"]["status"] == "BLOCKED"

def test_compiled_frontend_never_claims_complete_vba():
    c = Classification("split_file", "mde", "compiled_only", ("access_file",))
    result = compute_readiness(c, PROFILES, {"access_schema_inventory"})
    assert result["phase3"]["status"] == "LIMITED"

def test_not_applicable_requires_positive_proof():
    c = Classification("split_file", "mdb", "full", ("access_file",))
    result = compute_readiness(c, PROFILES, set())
    assert all(v["status"] != "NOT_APPLICABLE" for k, v in result.items() if k.startswith("phase"))

def test_security_integrity_waiver_is_rejected():
    c = Classification("split_file", "mdb", "full", ("unknown_boundary",))
    result = compute_readiness(c, PROFILES, set(), waivers=[{
        "rule_id": "backend.unknown_boundary.blocks_ready", "approver": "reviewer",
        "reason": "continue anyway", "affected_scope": "phase1", "accepted_risk": "unknown backend",
    }])
    assert "backend.unknown_boundary.blocks_ready" in result["_meta"]["waivers_rejected"]
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest plugins/ak/tests/test_phase_readiness.py -q`
Expected: FAIL because readiness module/schema are missing.

- [ ] **Step 3: Implement readiness matrix**

Resolve matched rules, compare `require.all`/`any` with present capabilities, merge the strictest status per phase, and include reasons/rule IDs. Baseline requirements come from spec 14.1; fragments may strengthen, never weaken security/integrity/path confinement. Waivers record approver/reason/scope/risk; a fixed non-waivable rule class rejects security, authorization, integrity, and confinement waivers. `NOT_APPLICABLE` requires a proof capability token. Output validates against `phase-readiness.schema.json`.

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest plugins/ak/tests/test_phase_readiness.py -q
git add plugins/ak/schemas/phase-readiness.schema.json plugins/ak/contracts/phase_readiness.py plugins/ak/tests/test_phase_readiness.py plugins/ak/scripts/validate_structure.py
git commit -m "feat(readiness): compute reproducible phase readiness"
```

---

### Task 7: Non-destructive V2.1 migration report

**Files:**
- Create: `plugins/ak/schemas/legacy-manifest-migration.schema.json`
- Create: `plugins/ak/contracts/migration.py`
- Create: `plugins/ak/tests/test_migration.py`

- [ ] **Step 1: Write failing migration test**

```python
# plugins/ak/tests/test_migration.py
import sys
from pathlib import Path
PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))
from migration import propose_migration  # noqa: E402

def test_migration_proposes_without_rewriting():
    source = PACKAGE / "references" / "manifest.example.yaml"
    before = source.read_bytes()
    report = propose_migration(source)
    assert source.read_bytes() == before
    assert report["source_version"] == "2.1"
    assert "candidate_classification" in report
    assert isinstance(report["mapped_artifacts"], list)
    assert report["required_bundle_rebuild"] is True
    assert report["required_graphify_rebuild"] is True
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest plugins/ak/tests/test_migration.py -q`
Expected: FAIL because migration module/schema are missing.

- [ ] **Step 3: Implement proposal-only migration**

Read V2.1 sources, map candidate Access/VBA/SQL/doc artifacts, propose classification with evidence, list ambiguous roles, missing mandatory inputs, quarantined paths, and required bundle/Graphify rebuilds. Return a dict validating the schema. Never overwrite the manifest; output is caller-selected `legacy-manifest-migration.json` (spec 24).

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest plugins/ak/tests/test_migration.py -q
git add plugins/ak/schemas/legacy-manifest-migration.schema.json plugins/ak/contracts/migration.py plugins/ak/tests/test_migration.py plugins/ak/scripts/validate_structure.py
git commit -m "feat(migration): add V2.1 migration proposal report"
```

---

### Task 8: Bounded V2.7 CLI subcommands

**Files:**
- Modify: `plugins/ak/scripts/ak.py`
- Create: `plugins/ak/tests/test_cli_v27.py`

- [ ] **Step 1: Write failing CLI tests**

```python
# plugins/ak/tests/test_cli_v27.py
import json
import subprocess
import sys
from pathlib import Path
PACKAGE = Path(__file__).resolve().parents[1]
AK = PACKAGE / "scripts" / "ak.py"

def run_ok(*args):
    result = subprocess.run([sys.executable, str(AK), *args], cwd=PACKAGE, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)

def test_profile_validate():
    data = run_ok("profile", "validate", "--topology", "split_file", "--frontend", "mdb",
                  "--source-availability", "full", "--backend", "access_file")
    assert "topology.split_file.backend_required" in data["rule_ids"]

def test_manifest_migrate():
    data = run_ok("manifest", "migrate", "--manifest", str(PACKAGE / "references" / "manifest.example.yaml"))
    assert data["source_version"] == "2.1"
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest plugins/ak/tests/test_cli_v27.py -q`
Expected: FAIL because subcommands are absent.

- [ ] **Step 3: Add spec-18 subcommands**

Add `profile detect|validate`, `bundle validate|approve`, `manifest migrate`. Each imports a contract module and prints deterministic JSON. `bundle approve` requires explicit `--output`; approval stays outside bundle. Keep all existing command parsers/dispatch unchanged. Do not add `acquire run` yet (Plan 2 owns adapter execution).

- [ ] **Step 4: Regression test and commit**

```bash
python -m pytest plugins/ak/tests/test_cli_v27.py plugins/ak/tests/test_package_smoke.py -q
git add plugins/ak/scripts/ak.py plugins/ak/tests/test_cli_v27.py
git commit -m "feat(cli): expose classification, bundle, and migration contracts"
```

---

### Task 9: Representative synthetic fixtures

**Files:**
- Create: `plugins/ak/fixtures/access-file-split/{complete,incomplete}/`
- Create: `plugins/ak/fixtures/access-adp-sqlserver/{complete,incomplete}/`
- Create: `plugins/ak/fixtures/access-compiled-frontend/{complete,incomplete}/`
- Modify: `plugins/ak/tests/test_phase_readiness.py`

- [ ] **Step 1: Add a failing fixture matrix test**

```python
# append to test_phase_readiness.py
import json

def test_fixture_matrix_matches_expected_readiness():
    cases = sorted((PACKAGE / "fixtures").glob("*/*/expected-readiness.json"))
    assert len(cases) == 6
    for case in cases:
        spec = json.loads(case.read_text(encoding="utf-8"))
        classification = Classification(**spec["classification"])
        actual = compute_readiness(classification, PROFILES, set(spec["present_capabilities"]))
        for phase, expected in spec["expected"].items():
            assert actual[phase]["status"] == expected, (case, phase)
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest plugins/ak/tests/test_phase_readiness.py -q`
Expected: FAIL because fixtures do not exist.

- [ ] **Step 3: Add six invented fixtures**

Each fixture contains V2.2 `manifest.yaml`, invented text/JSON source stubs (no database binary), and `expected-readiness.json`. Required cases: split MDB complete/incomplete; ADP+SQL complete and missing SQL schema (P1/P3 blocked); compiled frontend complete-for-limited and incomplete. This gives complete/incomplete coverage plus pairwise representative dimensions without Cartesian explosion (spec 22, 26.10).

- [ ] **Step 4: Run matrix and commit**

```bash
python -m pytest plugins/ak/tests/test_phase_readiness.py plugins/ak/tests/test_manifest_v22.py -q
git add plugins/ak/fixtures plugins/ak/tests/test_phase_readiness.py plugins/ak/scripts/validate_structure.py
git commit -m "test(fixtures): add representative profile matrices"
```

---

### Task 10: Package structure, ownership, docs, and release metadata

**Files:**
- Modify: `plugins/ak/scripts/validate_structure.py`
- Modify: `plugins/ak/specifications/package.json`
- Modify: `plugins/ak/.codex-plugin/plugin.json`
- Modify: `plugins/ak/.claude-plugin/plugin.json`
- Modify: `.agents/plugins/marketplace.json`
- Modify: `.claude-plugin/marketplace.json`
- Create: `.github/CODEOWNERS`
- Create: `docs/architecture/extraction-bundle.md`
- Create: `docs/architecture/investigation-pipeline.md`
- Create: `docs/project-classification/topology-rules.md`
- Create: `docs/project-classification/frontend-format-rules.md`
- Create: `docs/project-classification/source-availability-rules.md`
- Create: `docs/project-classification/backend-rules.md`
- Create: `docs/project-classification/resolved-examples.md`

- [ ] **Step 1: Register every new contract file**

Update `REQUIRED_FILES` so missing schema/profile/contract/test/docs files fail package validation. Extend manifest validation: V2.1 examples use `manifest.schema.json`; V2.2 fixtures use `manifest-v22.schema.json`.

- [ ] **Step 2: Add English canonical docs and CODEOWNERS**

Docs explain the shared pipeline once and link to rule fragments; no adapter-specific duplication. CODEOWNERS covers contracts/schemas, profiles, adapters, analyzers, templates, orchestration, docs, and release manifests using the repository owner `@tuanvtanrakutei`.

- [ ] **Step 3: Bump package to 2.7.0 in lock-step**

Set `plugins/ak/specifications/package.json` version `2.7.0`, contract version `2.2`, add features `composable_classification`, `canonical_extraction_bundle`, `phase_readiness_matrix`, `manifest_v22_reader`. Update all version manifests together; the existing smoke test enforces equality.

- [ ] **Step 4: Full verification**

```bash
python -m compileall -q plugins/ak/contracts plugins/ak/scripts plugins/ak/tests
python plugins/ak/scripts/validate_structure.py --package plugins/ak --repository-root .
python -m pytest -q
git diff --check
```

Expected: compile clean; structure PASS; all tests PASS; no whitespace errors.

- [ ] **Step 5: Commit the release checkpoint**

```bash
git add plugins/ak docs .github/CODEOWNERS .agents .claude-plugin
git commit -m "feat(ak): release 2.7 classification and bundle foundation"
```

---

## Self-Review Against Design Spec

- Section 6 + acceptance 16/17: Tasks 1-2.
- Section 7: Task 3.
- Section 8: Task 4.
- Section 13 + acceptance 1/7/19: Task 5.
- Section 14 + acceptance 4/6/8: Task 6.
- Section 24 + acceptance 9: Task 7.
- Section 18: Task 8.
- Sections 22/26.10: Task 9.
- Sections 19/21/25.1: Task 10.

Deliberate deferrals: adapters/`ak acquire` (Plan 2); analyzers/Graphify migration/Refactoring Handoff (Plan 3); hard blocking legacy V2.1 phase execution (V2.8 or later per spec 24).

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-24-classification-and-bundle-foundation.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh worker per task, two-stage review between tasks.
2. **Inline Execution** — execute in this session with plan checkpoints.

Which approach?
