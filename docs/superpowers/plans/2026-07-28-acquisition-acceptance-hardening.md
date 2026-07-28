# Acquisition Acceptance Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the post-merge acceptance gaps in AK V2.7.1 acquisition without changing the V2.2 manifest or bundle contracts.

**Architecture:** Keep the existing four adapters and one canonical bundle. Harden package ingestion at the adapter boundary, make bundle assembly conflict-safe and atomic, validate DACPAC and managed Access execution with synthetic tests, and make readiness capabilities adapter-owned instead of inferred from ambiguous shared sections. Invalid or blocked acquisition never produces a bundle; `PARTIAL` evidence may still produce an unapproved bundle.

**Tech Stack:** Python 3.11+, pytest, stdlib `zipfile`, `tempfile`, `xml.etree.ElementTree`, JSON Schema, existing AK contracts and synthetic fixtures.

---

## Baseline and Constraints

- Baseline commit: `3f25ce8` on `main`.
- Baseline verification: `73 passed`; structure validation reports `0 warning(s)`.
- Keep package version `2.7.1`; the release tag does not exist yet.
- Keep manifest contract version `2.2` and bundle schema version `2.7.1`.
- Never open an original MDB/ACCDB/ADP. Managed execution continues to delegate only to `extract_access.py --execute`, which owns snapshot creation and verification.
- Do not commit ZIP, DACPAC, MDB, BAK, MDF, LDF, credentials, or production rows. Tests create ZIP/DACPAC bytes under `tmp_path`.
- Do not add dependencies. Use stdlib and installed `jsonschema`/`PyYAML` only.
- English remains canonical for package code, errors, tests, and docs.

## Acceptance Gap Map

| Gap | Root cause | Acceptance criteria |
|---|---|---|
| ZIP is documented but always rejected | `acquire()` only loads a manifest when `source.is_dir()` | AC2, AC3, AC7, AC10 |
| Cross-adapter logical IDs overwrite silently | `_logical_artifacts()` assigns the last digest | AC12, AC14 |
| Existing bundle directories can retain stale files | assembly writes directly into the final bundle path | AC12, AC19 |
| DACPAC code is unexecuted and uses `Path(ZipInfo)` | no DACPAC fixture or test | AC4, AC10, AC11 |
| Managed execution can accept stale extraction output | predictable session path is read after any subprocess result | AC3, AC6, AC7 |
| SQL tables imply Access capabilities | orchestrator infers capabilities from shared section names | AC4, AC8, AC16 |
| Invalid/blocked contributions still reach assembly | orchestrator always calls `assemble_bundle()` | AC2, AC7, AC13 |

---

### Task 1: Complete strict ZIP and directory package acquisition

**Files:**
- Modify: `plugins/ak/adapters/imported_sources/adapter.py`
- Modify: `plugins/ak/tests/adapters/test_imported_sources.py`

- [ ] **Step 1: Write failing ZIP package tests**

Append these helpers and tests to `plugins/ak/tests/adapters/test_imported_sources.py`:

```python
import zipfile

import yaml

from adapters.imported_sources.adapter import sha256_bytes


def _package_manifest(path: str, raw: bytes) -> dict:
    return {
        "version": "1.0",
        "producer": {"id": "synthetic", "version": "1.0.0"},
        "files": [{
            "logical_id": "MOD_ORDER", "path": path, "kind": "vba",
            "role": "frontend", "sha256": sha256_bytes(raw), "encoding": "utf-8",
        }],
    }


def _write_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)


def _zip_artifact() -> dict:
    return {
        "id": "ZIP_EXPORT", "kind": "source_export", "role": "frontend",
        "acquisition": "imported", "required": True,
        "source_ref": {"type": "local_path", "value": "export.zip"}, "format": "zip",
    }


def test_zip_with_manifest_is_acquired_without_extracting(tmp_path: Path) -> None:
    raw = b"Option Explicit\n"
    manifest = yaml.safe_dump(_package_manifest("modules/Order.bas", raw), sort_keys=False).encode()
    _write_zip(tmp_path / "export.zip", {
        "import-source-manifest.yaml": manifest,
        "modules/Order.bas": raw,
    })
    adapter = ImportedSourcesAdapter()
    result = adapter.acquire(adapter.plan(_request(tmp_path, _zip_artifact())))
    assert result.status == "VALID"
    assert result.records[0]["logical_id"] == "MOD_ORDER"
    assert result.records[0]["text"] == "Option Explicit\n"
    assert not (tmp_path / "modules").exists()
```

Continue the same test block with:

```python
def test_zip_rejects_undeclared_member(tmp_path: Path) -> None:
    raw = b"Option Explicit\n"
    manifest = yaml.safe_dump(_package_manifest("modules/Order.bas", raw), sort_keys=False).encode()
    _write_zip(tmp_path / "export.zip", {
        "import-source-manifest.yaml": manifest,
        "modules/Order.bas": raw,
        "modules/Hidden.bas": b"Option Explicit\n",
    })
    adapter = ImportedSourcesAdapter()
    result = adapter.acquire(adapter.plan(_request(tmp_path, _zip_artifact())))
    assert result.status == "INVALID"
    assert result.failures == ({"logical_id": "ZIP_EXPORT", "reason": "UNDECLARED_PACKAGE_MEMBER"},)


def test_zip_rejects_duplicate_normalized_member(tmp_path: Path) -> None:
    raw = b"Option Explicit\n"
    manifest = yaml.safe_dump(_package_manifest("modules/Order.bas", raw), sort_keys=False).encode()
    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("import-source-manifest.yaml", manifest)
        handle.writestr("modules/Order.bas", raw)
        handle.writestr("modules\\Order.bas", raw)
    adapter = ImportedSourcesAdapter()
    result = adapter.acquire(adapter.plan(_request(tmp_path, _zip_artifact())))
    assert result.status == "INVALID"
    assert result.failures == ({"logical_id": "ZIP_EXPORT", "reason": "ARCHIVE_MEMBER_CONFLICT"},)


def test_directory_rejects_declared_symlink(tmp_path: Path) -> None:
    package = tmp_path / "loose"
    package.mkdir()
    outside = tmp_path / "outside.bas"
    outside.write_text("Option Explicit\n", encoding="utf-8")
    try:
        (package / "Order.bas").symlink_to(outside)
    except OSError:
        return
    manifest = _package_manifest("Order.bas", outside.read_bytes())
    (package / "import-source-manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    artifact = _zip_artifact() | {
        "id": "DIR_EXPORT", "source_ref": {"type": "local_path", "value": "loose"},
        "format": "directory",
    }
    adapter = ImportedSourcesAdapter()
    result = adapter.acquire(adapter.plan(_request(tmp_path, artifact)))
    assert result.status == "INVALID"
    assert result.failures == ({"logical_id": "DIR_EXPORT", "reason": "PACKAGE_SYMLINK"},)
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```text
python -m pytest plugins/ak/tests/adapters/test_imported_sources.py -v
```

Expected: existing tests pass; ZIP acceptance fails with `IMPORT_MANIFEST_REQUIRED`, and the undeclared/conflict/symlink assertions fail because those gates do not exist.

- [ ] **Step 3: Implement one package reader for directories and ZIPs**

Replace `load_import_manifest()` and add:

```python
def load_import_manifest_bytes(raw: bytes) -> dict[str, Any]:
    data = yaml.safe_load(raw.decode("utf-8", errors="strict")) or {}
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "import-source-manifest.schema.json"
    jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
    return data


def load_import_manifest(path: Path) -> dict[str, Any]:
    return load_import_manifest_bytes(path.read_bytes())


def _normalized_member_name(value: str) -> str:
    member = PurePosixPath(value.replace("\\", "/"))
    if member.is_absolute() or ".." in member.parts:
        raise ValueError("ARCHIVE_PATH_ESCAPE")
    return member.as_posix()


def _zip_member_map(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    result: dict[str, zipfile.ZipInfo] = {}
    for info in safe_zip_members(archive):
        if info.is_dir():
            continue
        name = _normalized_member_name(info.filename)
        if name in result:
            raise ValueError("ARCHIVE_MEMBER_CONFLICT")
        result[name] = info
    return result


def _read_directory_package(source: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    manifest_path = source / "import-source-manifest.yaml"
    if not manifest_path.is_file():
        raise ValueError("IMPORT_MANIFEST_REQUIRED")
    manifest = load_import_manifest(manifest_path)
    declared = {_normalized_member_name(item["path"]): item for item in manifest["files"]}
    actual = {
        path.relative_to(source).as_posix()
        for path in source.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if actual != set(declared):
        raise ValueError("UNDECLARED_PACKAGE_MEMBER")
    payloads: dict[str, bytes] = {}
    for name in sorted(declared):
        path = source / Path(*PurePosixPath(name).parts)
        if path.is_symlink():
            raise ValueError("PACKAGE_SYMLINK")
        payloads[name] = confined(source, name).read_bytes()
    return manifest, payloads


def _read_zip_package(source: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    with zipfile.ZipFile(source) as archive:
        members = _zip_member_map(archive)
        manifest_info = members.get("import-source-manifest.yaml")
        if manifest_info is None:
            raise ValueError("IMPORT_MANIFEST_REQUIRED")
        manifest = load_import_manifest_bytes(archive.read(manifest_info))
        declared = {_normalized_member_name(item["path"]): item for item in manifest["files"]}
        if set(members) != set(declared) | {"import-source-manifest.yaml"}:
            raise ValueError("UNDECLARED_PACKAGE_MEMBER")
        return manifest, {name: archive.read(members[name]) for name in sorted(declared)}


def _read_package(source: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    return _read_directory_package(source) if source.is_dir() else _read_zip_package(source)
```

Replace the package branch in `ImportedSourcesAdapter.acquire()` with:

```python
            if operation["is_package"]:
                try:
                    manifest, payloads = _read_package(source)
                except (OSError, UnicodeError, ValueError, zipfile.BadZipFile, jsonschema.ValidationError) as exc:
                    reason = str(exc) if str(exc).isupper() else "INVALID_IMPORT_PACKAGE"
                    failures.append({"logical_id": artifact["id"], "reason": reason})
                    continue
                for item in manifest["files"]:
                    name = _normalized_member_name(item["path"])
                    raw = payloads[name]
                    if sha256_bytes(raw) != item["sha256"]:
                        failures.append({"logical_id": item["logical_id"], "reason": "HASH_MISMATCH"})
                        continue
                    records.append(_record(item, raw))
                    hashes[item["logical_id"]] = item["sha256"]
                continue
```

- [ ] **Step 4: Run imported-source tests and verify GREEN**

```text
python -m pytest plugins/ak/tests/adapters/test_imported_sources.py -v
```

Expected: all imported-source tests pass; no archive is extracted to disk.

- [ ] **Step 5: Commit Task 1**

```text
git add plugins/ak/adapters/imported_sources/adapter.py plugins/ak/tests/adapters/test_imported_sources.py
git commit -m "fix(ak): complete strict ZIP package acquisition"
```

---

### Task 2: Reject contribution conflicts and assemble bundles atomically

**Files:**
- Modify: `plugins/ak/contracts/bundle_assembly.py`
- Modify: `plugins/ak/tests/test_bundle_assembly.py`

- [ ] **Step 1: Write failing conflict and stale-target tests**

Append to `plugins/ak/tests/test_bundle_assembly.py`:

```python
def _assemble(tmp_path: Path, contributions: list[dict]) -> dict:
    return assemble_bundle(
        app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
        contributions=contributions, normalization_config={"text": "utf-8-lf"},
        profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "LIMITED"}},
        output_root=tmp_path,
    )


def test_cross_adapter_hash_conflict_is_rejected(tmp_path: Path) -> None:
    first = _contribution("imported_sources")
    second = _contribution("msaccess_vcs")
    second["provenance"]["source_hashes"]["q1"] = "b" * 64
    second["code"]["access_sql"][0]["sha256"] = "b" * 64
    try:
        _assemble(tmp_path, [first, second])
    except ValueError as exc:
        assert str(exc) == "DUPLICATE_MISMATCH:q1"
        return
    raise AssertionError("cross-adapter digest conflicts must be rejected")


def test_identical_cross_adapter_record_is_deduplicated(tmp_path: Path) -> None:
    result = _assemble(tmp_path, [_contribution("imported_sources"), _contribution("msaccess_vcs")])
    inventory = json.loads(
        (Path(result["bundle_dir"]) / "code" / "access-sql" / "inventory.json").read_text(encoding="utf-8")
    )
    assert len(inventory) == 1


def test_reassembly_reuses_identical_existing_bundle(tmp_path: Path) -> None:
    first = _assemble(tmp_path, [_contribution("imported_sources")])
    second = _assemble(tmp_path, [_contribution("imported_sources")])
    assert second == first


def test_reassembly_rejects_stale_extra_file_without_deleting_it(tmp_path: Path) -> None:
    first = _assemble(tmp_path, [_contribution("imported_sources")])
    stale = Path(first["bundle_dir"]) / "stale.txt"
    stale.write_text("stale", encoding="utf-8")
    try:
        _assemble(tmp_path, [_contribution("imported_sources")])
    except ValueError as exc:
        assert str(exc) == "BUNDLE_PATH_CONFLICT"
        assert stale.read_text(encoding="utf-8") == "stale"
        return
    raise AssertionError("stale target content must not be overwritten")
```

- [ ] **Step 2: Run focused tests and verify RED**

```text
python -m pytest plugins/ak/tests/test_bundle_assembly.py -v
```

Expected: conflict does not raise, identical records are duplicated, and stale-target reuse is not rejected.

- [ ] **Step 3: Add deterministic de-duplication and atomic target publication**

Add imports:

```python
import shutil
import tempfile
```

Replace `_logical_artifacts()` with:

```python
def _logical_artifacts(contributions: list[dict[str, Any]]) -> list[dict[str, str]]:
    artifacts: dict[str, str] = {}
    for contribution in contributions:
        for logical_id, digest in contribution["provenance"]["source_hashes"].items():
            previous = artifacts.get(logical_id)
            if previous is not None and previous != digest:
                raise ValueError(f"DUPLICATE_MISMATCH:{logical_id}")
            artifacts[logical_id] = digest
    return [{"logical_id": key, "content_sha256": artifacts[key]} for key in sorted(artifacts)]
```

Add this helper and call it instead of `.extend()` for every section list in `_merge_sections()`:

```python
def _merge_records(target: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> None:
    keyed: dict[tuple[str, str], dict[str, Any]] = {}
    unkeyed: list[dict[str, Any]] = []
    for record in [*target, *incoming]:
        logical_id = record.get("logical_id")
        digest = record.get("sha256")
        if logical_id is None or digest is None:
            unkeyed.append(record)
            continue
        keyed.setdefault((str(logical_id), str(digest)), record)
    target[:] = [keyed[key] for key in sorted(keyed)] + sorted(
        unkeyed, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True)
    )
```

Add publication helpers:

```python
def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def _publish_bundle(staged: Path, target: Path) -> None:
    if target.exists():
        if _tree_hashes(target) != _tree_hashes(staged):
            raise ValueError("BUNDLE_PATH_CONFLICT")
        return
    staged.replace(target)
```

In `assemble_bundle()`, calculate identity, merged sections, status, `bundle_json`, and provenance first. Replace direct final-directory writes with:

```python
    output = Path(output_root).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    bundle_dir = output / bundle_id
    staged = Path(tempfile.mkdtemp(prefix=f".{bundle_id}.", dir=output))
    try:
        _write_layout(staged, merged, contributions, bundle_id, schema_version)
        _write_json(staged / "profile-validation.json", profile_validation)
        _write_json(staged / "phase-readiness.json", phase_readiness)
        _write_json(staged / "bundle.json", bundle_json)
        _write_json(staged / "provenance.json", provenance)
        _validate_json(staged / "provenance.json", "bundle-provenance.schema.json")
        _validate_json(staged / "coverage.json", "bundle-coverage.schema.json")
        _write_checksums(staged)
        bundle_contract.validate_bundle(staged)
        _publish_bundle(staged, bundle_dir)
    finally:
        if staged.exists():
            shutil.rmtree(staged)
```

Do not delete or mutate an existing target bundle.

- [ ] **Step 4: Run bundle tests and verify GREEN**

```text
python -m pytest plugins/ak/tests/test_bundle_assembly.py plugins/ak/tests/test_bundle.py -v
```

Expected: all tests pass; identical assembly reuses the target, while stale or conflicting content is preserved and rejected.

- [ ] **Step 5: Commit Task 2**

```text
git add plugins/ak/contracts/bundle_assembly.py plugins/ak/tests/test_bundle_assembly.py
git commit -m "fix(ak): reject bundle conflicts and publish atomically"
```

---

### Task 3: Validate DACPAC packages and map only supported SQL objects

**Files:**
- Modify: `plugins/ak/adapters/sql_server/adapter.py`
- Modify: `plugins/ak/tests/adapters/test_sql_server.py`

- [ ] **Step 1: Write failing synthetic DACPAC tests**

Append to `plugins/ak/tests/adapters/test_sql_server.py`:

```python
import zipfile


MODEL_XML = b'''<?xml version="1.0" encoding="utf-8"?>
<DataSchemaModel xmlns="http://schemas.microsoft.com/sqlserver/dac/Serialization/2012/02">
  <Model>
    <Element Type="SqlTable" Name="[sales].[Order]" />
    <Element Type="SqlProcedure" Name="[sales].[usp_Order]" />
    <Element Type="SqlScalarFunction" Name="[sales].[fn_Order]" />
    <Element Type="SqlColumn" Name="[sales].[Order].[OrderId]" />
  </Model>
</DataSchemaModel>'''


def _write_dacpac(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)


def test_dacpac_model_maps_supported_objects_without_extracting(tmp_path: Path) -> None:
    _write_dacpac(tmp_path / "schema.dacpac", {"model.xml": MODEL_XML})
    artifact = {
        "id": "DACPAC", "kind": "sql_server_package", "role": "backend",
        "acquisition": "imported", "required": True,
        "source_ref": {"type": "local_path", "value": "schema.dacpac"}, "format": "dacpac",
    }
    adapter = SqlServerAdapter()
    result = adapter.acquire(adapter.plan(_request(tmp_path, (artifact,))))
    contribution = adapter.normalize(result)
    assert result.status == "VALID"
    assert [(item["schema"], item["name"], item["type"]) for item in contribution["databases"]["tables"]] == [
        ("sales", "Order", "table")
    ]
    assert {(item["name"], item["type"]) for item in contribution["databases"]["objects"]} == {
        ("fn_Order", "function"), ("usp_Order", "procedure")
    }
    assert not (tmp_path / "model.xml").exists()


def test_dacpac_requires_exactly_one_model(tmp_path: Path) -> None:
    _write_dacpac(tmp_path / "schema.dacpac", {"a/model.xml": MODEL_XML, "b/model.xml": MODEL_XML})
    artifact = {
        "id": "DACPAC", "kind": "sql_server_package", "role": "backend",
        "acquisition": "imported", "required": True,
        "source_ref": {"type": "local_path", "value": "schema.dacpac"}, "format": "dacpac",
    }
    adapter = SqlServerAdapter()
    result = adapter.acquire(adapter.plan(_request(tmp_path, (artifact,))))
    assert result.status == "INVALID"
    assert result.failures == ({"logical_id": "DACPAC", "reason": "DACPAC_MODEL_REQUIRED"},)
```

- [ ] **Step 2: Run SQL adapter tests and verify RED**

```text
python -m pytest plugins/ak/tests/adapters/test_sql_server.py -v
```

Expected: `Path(ZipInfo)` raises during the first DACPAC test; the adapter does not normalize DACPAC errors into an `AcquisitionResult`.

- [ ] **Step 3: Implement supported-type DACPAC parsing and error normalization**

Add these constants and helpers in `sql_server/adapter.py`:

```python
DACPAC_TYPES = {
    "SqlTable": "table", "SqlView": "view", "SqlProcedure": "procedure",
    "SqlScalarFunction": "function", "SqlTableValuedFunction": "function",
    "SqlDmlTrigger": "trigger", "SqlUserDefinedType": "type", "SqlSequence": "sequence",
}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _qualified_name(value: str) -> tuple[str, str]:
    parts = re.findall(r"\[([^]]+)\]", value)
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    plain = [part for part in value.split(".") if part]
    return (plain[-2], plain[-1]) if len(plain) >= 2 else ("dbo", plain[-1])
```

Add `import re`. Replace `_read_dacpac_model()` with:

```python
def _read_dacpac_model(path: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        members = safe_zip_members(archive)
        models = [info for info in members if Path(info.filename).name == "model.xml"]
        if len(models) != 1:
            raise ValueError("DACPAC_MODEL_REQUIRED")
        root = ElementTree.fromstring(archive.read(models[0]))
    objects: list[dict[str, Any]] = []
    for element in root.iter():
        if _local_name(element.tag) != "Element":
            continue
        mapped = DACPAC_TYPES.get(str(element.get("Type", "")))
        if mapped is None:
            continue
        schema, name = _qualified_name(str(element.get("Name", "")))
        objects.append({
            "schema": schema, "name": name, "type": mapped,
            "columns": [], "definition": None,
        })
    return sorted(objects, key=lambda item: (item["schema"], item["name"], item["type"]))
```

In `SqlServerAdapter.acquire()`, isolate each artifact failure rather than escaping the adapter:

```python
        for operation in plan.operations:
            artifact = operation["artifact"]
            try:
                produced, produced_failures, produced_hashes = _handle_artifact(
                    artifact, Path(operation["source_root"])
                )
            except (OSError, UnicodeError, ValueError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
                reason = str(exc) if str(exc).isupper() else "INVALID_SQL_ARTIFACT"
                failures.append({"logical_id": artifact["id"], "reason": reason})
                continue
            records.extend(produced)
            failures.extend(produced_failures)
            hashes.update(produced_hashes)
```

Validate the generated DACPAC catalog with `_validate_catalog()` before returning its record.

- [ ] **Step 4: Run SQL and readiness tests and verify GREEN**

```text
python -m pytest plugins/ak/tests/adapters/test_sql_server.py plugins/ak/tests/test_phase_readiness.py -v
```

Expected: DACPAC tests pass; ADP readiness remains blocked without server inventory.

- [ ] **Step 5: Commit Task 3**

```text
git add plugins/ak/adapters/sql_server/adapter.py plugins/ak/tests/adapters/test_sql_server.py
git commit -m "fix(ak): validate DACPAC model inventory"
```

---

### Task 4: Harden managed Access execution receipts

**Files:**
- Modify: `plugins/ak/adapters/managed_access/adapter.py`
- Modify: `plugins/ak/tests/adapters/test_managed_access.py`
- Modify: `plugins/ak/scripts/ak.py`

- [ ] **Step 1: Write failing managed-execution tests**

Append to `plugins/ak/tests/adapters/test_managed_access.py`:

```python
import subprocess


def _managed_plan(tmp_path: Path, authorized: bool = True):
    db = tmp_path / "frontend.mdb"
    db.write_bytes(b"synthetic-signature-only")
    request = AcquisitionRequest("SYN", CLASSIFICATION, ({
        "id": "FRONTEND", "kind": "access_database", "role": "frontend",
        "acquisition": "managed", "required": True,
        "source_ref": {"type": "local_path", "value": "frontend.mdb"}, "format": "mdb",
    },), tmp_path)
    return dataclasses.replace(
        ManagedAccessAdapter().plan(request),
        acquisition_id="run-1", runtime_output_root=str(tmp_path / "staging"),
        granted_authorization=("access_snapshot_extract",) if authorized else (),
    )


def test_acquire_without_authorization_never_spawns(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("spawned")))
    result = ManagedAccessAdapter().acquire(_managed_plan(tmp_path, authorized=False))
    assert result.status == "BLOCKED"
    assert result.failures[0]["reason"] == "AUTHORIZATION_REQUIRED"


def test_acquire_rejects_preexisting_receipt(monkeypatch, tmp_path: Path) -> None:
    plan = _managed_plan(tmp_path)
    receipt = Path(plan.runtime_output_root) / "FRONTEND" / plan.acquisition_id / "access-extraction.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("spawned")))
    result = ManagedAccessAdapter().acquire(plan)
    assert result.status == "BLOCKED"
    assert result.failures[0]["reason"] == "STALE_EXTRACTION_RESULT"


def test_acquire_accepts_fresh_extractor_receipt(monkeypatch, tmp_path: Path) -> None:
    plan = _managed_plan(tmp_path)
    source_before = Path(plan.operations[0]["source"]).read_bytes()

    def fake_run(command, **kwargs):
        receipt = Path(plan.runtime_output_root) / "FRONTEND" / plan.acquisition_id / "access-extraction.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text(json.dumps({
            "database_id": "FRONTEND", "status": "EXTRACTED",
            "source": {"sha256": "a" * 64}, "components": [], "warnings": [],
        }), encoding="utf-8")
        assert "--execute" in command
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = ManagedAccessAdapter().acquire(plan)
    assert result.status == "VALID"
    assert Path(plan.operations[0]["source"]).read_bytes() == source_before


def test_acquire_rejects_nonzero_extractor_without_receipt(monkeypatch, tmp_path: Path) -> None:
    plan = _managed_plan(tmp_path)
    monkeypatch.setattr(
        subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 2, "", "failed"),
    )
    result = ManagedAccessAdapter().acquire(plan)
    assert result.status == "BLOCKED"
    assert result.failures[0]["reason"] == "EXTRACTOR_FAILED"
```

Add `import dataclasses` to the test file.

- [ ] **Step 2: Run managed tests and verify RED**

```text
python -m pytest plugins/ak/tests/adapters/test_managed_access.py -v
```

Expected: stale receipt is accepted today, and nonzero extractor exit is reported as `EXTRACTION_RESULT_MISSING` rather than `EXTRACTOR_FAILED`.

- [ ] **Step 3: Require a fresh successful extraction receipt**

In `ManagedAccessAdapter.acquire()`, calculate `extraction` before spawning and replace the current subprocess/result block with:

```python
            extraction = _find_extraction(
                Path(plan.runtime_output_root), artifact["id"], plan.acquisition_id
            )
            if extraction.exists():
                failures.append({
                    "logical_id": artifact["id"], "reason": "STALE_EXTRACTION_RESULT"
                })
                continue
            completed = subprocess.run(
                command, check=False, capture_output=True, text=True, encoding="utf-8"
            )
            if completed.returncode != 0:
                failures.append({
                    "logical_id": artifact["id"], "reason": "EXTRACTOR_FAILED",
                    "returncode": completed.returncode,
                })
                continue
            if not extraction.is_file():
                failures.append({
                    "logical_id": artifact["id"], "reason": "EXTRACTION_RESULT_MISSING",
                    "returncode": completed.returncode,
                })
                continue
```

Do not remove an existing receipt. A caller that explicitly reuses an acquisition ID must choose a new ID.

In `plugins/ak/scripts/ak.py`, add `import uuid`, change `--acquisition-id` default to `None`, and pass:

```python
        acquisition_id = args.acquisition_id or f"acquire-{uuid.uuid4().hex}"
        result = run_acquisition(
            manifest_path, Path(args.output_root).expanduser().resolve(),
            tuple(args.authorize), acquisition_id,
        )
```

Runtime acquisition IDs remain excluded from bundle identity.

- [ ] **Step 4: Run managed and CLI tests and verify GREEN**

```text
python -m pytest plugins/ak/tests/adapters/test_managed_access.py plugins/ak/tests/test_cli_acquire.py -v
```

Expected: all tests pass without invoking Access or creating snapshots.

- [ ] **Step 5: Commit Task 4**

```text
git add plugins/ak/adapters/managed_access/adapter.py plugins/ak/tests/adapters/test_managed_access.py plugins/ak/scripts/ak.py
git commit -m "fix(ak): require fresh managed extraction receipts"
```

---

### Task 5: Make readiness capabilities adapter-owned and conservative

**Files:**
- Modify: `plugins/ak/adapters/imported_sources/adapter.py`
- Modify: `plugins/ak/adapters/managed_access/adapter.py`
- Modify: `plugins/ak/adapters/msaccess_vcs/adapter.py`
- Modify: `plugins/ak/contracts/acquisition_orchestrator.py`
- Create: `plugins/ak/tests/test_acquisition_orchestrator.py`

- [ ] **Step 1: Write failing capability attribution tests**

Create `plugins/ak/tests/test_acquisition_orchestrator.py`:

```python
from __future__ import annotations

from adapters.base import empty_sections
from acquisition_orchestrator import _capabilities


def _contribution(adapter_id: str, capabilities: list[str]) -> dict:
    return {
        "adapter_id": adapter_id, "adapter_version": "1.0.0", "app_id": "SYN",
        "status": "VALID", **empty_sections(), "failures": [],
        "provenance": {
            "producer": adapter_id, "source_hashes": {}, "capabilities": capabilities,
        },
    }


def test_sql_tables_do_not_imply_access_schema_capability() -> None:
    contribution = _contribution("sql_server", ["server_object_inventory"])
    contribution["databases"]["tables"].append({
        "schema": "dbo", "name": "Order", "type": "table"
    })
    assert _capabilities([contribution]) == {"server_object_inventory"}


def test_only_declared_capabilities_are_aggregated() -> None:
    first = _contribution("imported_sources", ["vba_query_inventory"])
    second = _contribution("managed_access", ["access_object_inventory", "ui_object_inventory"])
    assert _capabilities([first, second]) == {
        "vba_query_inventory", "access_object_inventory", "ui_object_inventory"
    }
```

- [ ] **Step 2: Run the new test and verify RED**

```text
python -m pytest plugins/ak/tests/test_acquisition_orchestrator.py -v
```

Expected: SQL tables add `access_schema_inventory`, `field_inventory`, and `key_index_inventory` today.

- [ ] **Step 3: Declare capabilities in each adapter contribution**

Add this local helper to `imported_sources/adapter.py` and `msaccess_vcs/adapter.py`:

```python
def _content_capabilities(sections: dict[str, Any]) -> list[str]:
    capabilities: set[str] = set()
    if sections["code"]["vba"] or sections["code"]["access_sql"]:
        capabilities.add("vba_query_inventory")
    if any(sections["ui"].values()):
        capabilities.add("ui_object_inventory")
    if sections["evidence_sources"]["documents"]["inventory"]:
        capabilities.add("document_inventory")
    if sections["interfaces"]["linked_tables"] or sections["interfaces"]["file_interfaces"]:
        capabilities.add("boundary_inventory")
    return sorted(capabilities)
```

Add `"capabilities": _content_capabilities(sections)` to those adapters' provenance.

Add this helper to `managed_access/adapter.py`:

```python
def _access_capabilities(sections: dict[str, Any]) -> list[str]:
    capabilities: set[str] = set()
    if any(sections["databases"].values()) or any(sections["ui"].values()) or any(sections["code"].values()):
        capabilities.add("access_object_inventory")
    if sections["databases"]["tables"]:
        capabilities.add("access_schema_inventory")
    if sections["databases"]["fields"]:
        capabilities.add("field_inventory")
    if sections["databases"]["indexes"]:
        capabilities.add("key_index_inventory")
    if sections["code"]["vba"] or sections["code"]["access_sql"]:
        capabilities.add("vba_query_inventory")
    if any(sections["ui"].values()):
        capabilities.add("ui_object_inventory")
    if sections["interfaces"]["linked_tables"]:
        capabilities.add("boundary_inventory")
    return sorted(capabilities)
```

Add `"capabilities": _access_capabilities(sections)` to managed provenance. Keep SQL Server's existing explicit `server_object_inventory` capability.

Replace orchestrator `_capabilities()` with:

```python
def _capabilities(contributions: list[dict[str, Any]]) -> set[str]:
    capabilities: set[str] = set()
    for contribution in contributions:
        capabilities.update(contribution["provenance"].get("capabilities", []))
    return capabilities
```

- [ ] **Step 4: Run capability and readiness tests and verify GREEN**

```text
python -m pytest plugins/ak/tests/test_acquisition_orchestrator.py plugins/ak/tests/test_phase_readiness.py plugins/ak/tests/adapters -v
```

Expected: all tests pass; no adapter receives a capability from another adapter's section semantics.

- [ ] **Step 5: Commit Task 5**

```text
git add plugins/ak/adapters/imported_sources/adapter.py plugins/ak/adapters/managed_access/adapter.py plugins/ak/adapters/msaccess_vcs/adapter.py plugins/ak/contracts/acquisition_orchestrator.py plugins/ak/tests/test_acquisition_orchestrator.py
git commit -m "fix(ak): make acquisition capabilities adapter-owned"
```

---

### Task 6: Gate invalid acquisition and test multi-adapter CLI runs

**Files:**
- Modify: `plugins/ak/contracts/acquisition_orchestrator.py`
- Modify: `plugins/ak/scripts/ak.py`
- Modify: `plugins/ak/tests/test_cli_acquire.py`

- [ ] **Step 1: Write failing multi-adapter and invalid-input CLI tests**

Append to `plugins/ak/tests/test_cli_acquire.py`:

```python
def _run_raw(args: list[str], tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(AK), *args], cwd=tmp_path,
        capture_output=True, text=True, encoding="utf-8",
    )


def _write_multi_adapter_manifest(tmp_path: Path) -> Path:
    (tmp_path / "Order.bas").write_text("Option Explicit\n", encoding="utf-8")
    (tmp_path / "catalog.json").write_text(json.dumps({
        "version": "1.0", "database": "SyntheticDb",
        "objects": [{
            "schema": "dbo", "name": "SyntheticOrder", "type": "table",
            "columns": [], "definition": None,
        }],
    }), encoding="utf-8")
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "version: '2.2'\n"
        "app: {id: SYN, name_en: Synthetic}\n"
        "project:\n"
        "  classification: {topology: client_server, frontend_format: exported, source_availability: exported_only, backend_kinds: [sql_server]}\n"
        "artifacts:\n"
        "  - {id: VBA_ORDER, kind: source_export, role: frontend, acquisition: imported, required: true, format: vba, source_ref: {type: local_path, value: Order.bas}}\n"
        "  - {id: SQL_CATALOG, kind: sql_server_catalog, role: backend, acquisition: imported, required: true, format: json, source_ref: {type: local_path, value: catalog.json}}\n",
        encoding="utf-8",
    )
    return manifest


def test_multi_adapter_run_contains_vba_and_sql_catalog(tmp_path: Path) -> None:
    manifest = _write_multi_adapter_manifest(tmp_path)
    plan = _run(["acquire", "plan", "--manifest", str(manifest)], tmp_path)
    assert plan["adapters"] == {
        "imported_sources": ["VBA_ORDER"], "sql_server": ["SQL_CATALOG"]
    }
    result = _run([
        "acquire", "run", "--manifest", str(manifest),
        "--output-root", str(tmp_path / "bundles"),
    ], tmp_path)
    bundle = Path(result["bundle_dir"])
    assert json.loads((bundle / "code" / "vba" / "inventory.json").read_text(encoding="utf-8"))
    assert json.loads((bundle / "databases" / "tables.json").read_text(encoding="utf-8"))


def test_invalid_package_does_not_create_bundle(tmp_path: Path) -> None:
    loose = tmp_path / "loose"
    loose.mkdir()
    (loose / "Order.bas").write_text("Option Explicit\n", encoding="utf-8")
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "version: '2.2'\n"
        "app: {id: SYN, name_en: Synthetic}\n"
        "project:\n"
        "  classification: {topology: monolith, frontend_format: exported, source_availability: exported_only, backend_kinds: [unknown_boundary]}\n"
        "artifacts:\n"
        "  - {id: LOOSE, kind: source_export, role: frontend, acquisition: imported, required: true, format: directory, source_ref: {type: local_path, value: loose}}\n",
        encoding="utf-8",
    )
    output = tmp_path / "bundles"
    completed = _run_raw([
        "acquire", "run", "--manifest", str(manifest), "--output-root", str(output)
    ], tmp_path)
    assert completed.returncode == 2
    data = json.loads(completed.stdout)
    assert data["status"] == "INVALID"
    assert data["bundle_id"] is None
    assert not list(output.glob("bundle-*"))


def test_managed_without_authorization_does_not_create_bundle(tmp_path: Path) -> None:
    (tmp_path / "frontend.mdb").write_bytes(b"synthetic-signature-only")
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "version: '2.2'\n"
        "app: {id: SYN, name_en: Synthetic}\n"
        "project:\n"
        "  classification: {topology: monolith, frontend_format: mdb, source_availability: full, backend_kinds: [embedded_access]}\n"
        "artifacts:\n"
        "  - {id: FRONTEND, kind: access_database, role: frontend, acquisition: managed, required: true, format: mdb, source_ref: {type: local_path, value: frontend.mdb}}\n",
        encoding="utf-8",
    )
    output = tmp_path / "bundles"
    completed = _run_raw([
        "acquire", "run", "--manifest", str(manifest), "--output-root", str(output)
    ], tmp_path)
    assert completed.returncode == 2
    data = json.loads(completed.stdout)
    assert data["status"] == "BLOCKED"
    assert data["failures"][0]["reason"] == "AUTHORIZATION_REQUIRED"
    assert not list(output.glob("bundle-*"))
```

- [ ] **Step 2: Run CLI tests and verify RED**

```text
python -m pytest plugins/ak/tests/test_cli_acquire.py -v
```

Expected: multi-adapter run may pass, but invalid and blocked acquisition currently create bundle directories and return exit code 0.

- [ ] **Step 3: Stop before assembly for invalid or blocked contributions**

Add to `acquisition_orchestrator.py`:

```python
def _contribution_failures(contributions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [failure for contribution in contributions for failure in contribution["failures"]],
        key=lambda item: (item.get("logical_id", ""), item.get("reason", "")),
    )
```

Immediately after computing `profile_validation` in `run_acquisition()`:

```python
    worst = _worst_contribution_status(contributions)
    if worst in {"INVALID", "BLOCKED"}:
        return {
            "bundle_id": None, "bundle_dir": None, "status": worst,
            "failures": _contribution_failures(contributions),
        }
```

In `ak.py` acquire-run dispatch, print the result and return nonzero when no bundle was produced:

```python
        print_json(result)
        return 0 if result.get("bundle_id") else 2
```

Keep `PARTIAL` eligible for unapproved bundle assembly.

- [ ] **Step 4: Run CLI, bundle, and package smoke tests and verify GREEN**

```text
python -m pytest plugins/ak/tests/test_cli_acquire.py plugins/ak/tests/test_bundle_assembly.py plugins/ak/tests/test_package_smoke.py -v
```

Expected: valid multi-adapter acquisition produces one canonical bundle; invalid/blocked acquisition produces JSON diagnostics only.

- [ ] **Step 5: Commit Task 6**

```text
git add plugins/ak/contracts/acquisition_orchestrator.py plugins/ak/scripts/ak.py plugins/ak/tests/test_cli_acquire.py
git commit -m "fix(ak): gate invalid acquisition before bundle assembly"
```

---

### Task 7: Align docs, validation, changelog, and release gates

**Files:**
- Modify: `plugins/ak/scripts/validate_structure.py`
- Modify: `docs/acquisition/decision-guide.md`
- Modify: `docs/acquisition/imported-sources.md`
- Modify: `docs/acquisition/managed-access.md`
- Modify: `docs/acquisition/sql-server.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Extend structure validation and verify RED before editing docs**

Add `tests/test_acquisition_orchestrator.py` to `REQUIRED_FILES`. Extend `publication_checks` with:

```python
        "docs/acquisition/decision-guide.md": (
            "Invalid or blocked acquisition", "does not produce a bundle", "PARTIAL"
        ),
        "docs/acquisition/imported-sources.md": (
            "UNDECLARED_PACKAGE_MEMBER", "ARCHIVE_MEMBER_CONFLICT", "without extracting"
        ),
        "docs/acquisition/managed-access.md": (
            "STALE_EXTRACTION_RESULT", "EXTRACTOR_FAILED", "disposable snapshot"
        ),
        "docs/acquisition/sql-server.md": (
            "DACPAC_MODEL_REQUIRED", "server_object_inventory", "model.xml"
        ),
```

Run:

```text
python plugins/ak/scripts/validate_structure.py --package plugins/ak --repository-root .
```

Expected: validation fails because the hardening terms are not yet present in the docs.

- [ ] **Step 2: Update the four English-canonical acquisition docs**

Make these exact behavior statements:

- `decision-guide.md`: invalid or blocked acquisition returns diagnostics and does not produce a bundle; `PARTIAL` may produce an unapproved bundle.
- `imported-sources.md`: ZIPs are read in memory without extracting; the manifest must account for every non-directory member; duplicate normalized paths fail with `ARCHIVE_MEMBER_CONFLICT`; undeclared files fail with `UNDECLARED_PACKAGE_MEMBER`.
- `managed-access.md`: default acquisition IDs are unique; an explicitly reused ID with an existing receipt fails `STALE_EXTRACTION_RESULT`; a nonzero delegated extractor exit fails `EXTRACTOR_FAILED`; original Access files remain unopened by the adapter.
- `sql-server.md`: DACPAC processing reads exactly one `model.xml` in memory, maps only supported object types, and never extracts/copies the DACPAC; missing/duplicate model entries fail `DACPAC_MODEL_REQUIRED`.

Do not duplicate the shared pipeline from `docs/architecture/investigation-pipeline.md`.

- [ ] **Step 3: Add the unreleased V2.7.1 changelog entry**

Insert below `# Changelog`:

```markdown
## [2.7.1] - 2026-07-28

### Added

- Managed/imported Access, msaccess-vcs, and SQL Server acquisition adapters with `ak acquire plan|run`.
- Deterministic canonical bundle assembly and English acquisition decision guides.

### Fixed

- ZIP package acquisition now validates and reads declared members without extraction.
- Cross-adapter conflicts, stale bundle targets, stale managed-extraction receipts, and invalid pre-bundle acquisition are rejected.
- DACPAC object inventory and adapter-owned readiness capabilities prevent false Access/SQL completeness claims.

### Security

- Raw Access databases, SQL Server backups/data files, archive executables, path escapes, symlinks, undeclared package members, and unapproved bundles remain outside analysis inputs.
```

- [ ] **Step 4: Run release verification and verify GREEN**

```text
python -m compileall -q plugins/ak/contracts plugins/ak/adapters plugins/ak/scripts plugins/ak/tests
python -m pytest -q
python plugins/ak/scripts/validate_structure.py --package plugins/ak --repository-root .
git diff --check
```

Expected: all tests pass, structure validation reports `0 warning(s)`, compile exits 0, and `git diff --check` is clean.

- [ ] **Step 5: Commit Task 7**

```text
git add plugins/ak/scripts/validate_structure.py docs/acquisition CHANGELOG.md
git commit -m "docs(ak): document hardened acquisition release gates"
```

---

## Post-Merge Release Procedure

Do this only after the Plan 2A PR is merged and the `Validate` workflow succeeds on `main`:

```text
git checkout main
git pull --ff-only origin main
git tag -a v2.7.1 -m "Access Modernization Kit 2.7.1"
git push origin v2.7.1
gh release create v2.7.1 --title "Access Modernization Kit 2.7.1" --notes-from-tag
```

If `gh` is unavailable, create the release from the pushed tag in GitHub. Do not push `main` to bypass the PR.

## Self-Review

### Spec coverage

- AC2/AC7/AC13: Tasks 1 and 6 reject undeclared, invalid, blocked, or forbidden acquisition before bundle/analysis.
- AC3: Tasks 1, 3, and 4 keep all acquisition paths on `BundleContribution`.
- AC4/AC8/AC16: Tasks 3 and 5 make SQL inventory explicit and readiness capability-derived.
- AC10/AC11: Tasks 1, 3, 4, and 6 add synthetic adapter tests independent from Phase generation.
- AC12/AC14/AC19: Task 2 rejects conflict/stale targets and publishes deterministic bundles atomically.
- AC15: Task 7 updates adapter-specific docs only; shared workflow remains in `docs/architecture/`.

### Non-goals

- No live SQL Server connection or restore automation.
- No actual Access COM execution in hosted tests.
- No TAR/MSI package support.
- No DACPAC column/dependency reconstruction; V2.7.1 provides supported object inventory only.
- No V3 architecture changes and no manifest/bundle schema version bump.

### Type and behavior consistency

- Adapter method names remain `probe/plan/acquire/normalize`.
- `INVALID` and `BLOCKED` return diagnostics with no bundle; `PARTIAL` remains bundle-eligible.
- Capabilities are sorted strings under `provenance.capabilities` and are unioned without inference.
- Acquisition IDs and staging paths remain runtime-only and absent from bundle identity.
- Existing output bundles are never deleted or overwritten.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-28-acquisition-acceptance-hardening.md`.

Execution options:

1. **Subagent-Driven (recommended):** fresh implementation agent per task with review between commits.
2. **Inline Execution:** use `superpowers:executing-plans` and implement Tasks 1-7 sequentially with TDD checkpoints.
