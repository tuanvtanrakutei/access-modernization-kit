from copy import deepcopy
import json
from pathlib import Path

import jsonschema
import pytest
from collaboration import (
    CollaborationError,
    project_task,
    validate_work_package,
    work_package_digest,
)
from collaboration_helpers import (
    application_package,
    candidate_task,
    kit_package,
    mixed_package,
)


def task_schema() -> dict:
    path = Path(__file__).resolve().parents[1] / "schemas" / "task.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def kit_projection_pair() -> tuple[dict, dict]:
    package, task = kit_package(), candidate_task()
    package["scope"]["roles"] = [task["role"]]
    package["scope"]["wave_ids"] = [task["wave_id"]]
    package["scope"]["phase_targets"] = task["phase_targets"]
    package["scope"]["module_targets"] = task["module_targets"]
    package["input_paths"] = ["extracted/bundles/bundle-a/code/access-sql"]
    package["write_paths"] = ["work/sql_data/module-orders"]
    task["evidence_namespace"] = None
    return package, task


@pytest.mark.parametrize(
    "work_kind", ["application_evidence", "application_docs", "application_qa"]
)
def test_application_work_rejects_repository_only_authority(work_kind: str) -> None:
    package = application_package()
    package["work_kind"] = work_kind
    package["authority"] = kit_package()["authority"]

    with pytest.raises(CollaborationError, match="COLLAB_PACKAGE_INVALID"):
        validate_work_package(package)


def test_mixed_pilot_rejects_approved_bundle_authority() -> None:
    package = application_package()
    package["work_kind"] = "mixed_pilot"

    with pytest.raises(CollaborationError, match="COLLAB_PACKAGE_INVALID"):
        validate_work_package(package)


@pytest.mark.parametrize(
    "work_kind", ["application_evidence", "application_docs", "application_qa"]
)
@pytest.mark.parametrize("authority_factory", [application_package])
def test_application_work_accepts_app_bearing_authority(
    work_kind: str, authority_factory
) -> None:
    package = authority_factory()
    package["work_kind"] = work_kind

    validate_work_package(package)


@pytest.mark.parametrize(
    ("work_kind", "required_authority_kind"),
    [
        ("kit_code", "repository_revision"),
        ("kit_contract", "repository_revision"),
        ("kit_docs", "repository_revision"),
        ("application_evidence", "approved_bundle"),
        ("application_docs", "approved_bundle"),
        ("application_qa", "approved_bundle"),
        ("mixed_pilot", "mixed"),
    ],
)
@pytest.mark.parametrize(
    "authority_factory", [kit_package, application_package, mixed_package]
)
def test_work_kind_requires_exact_authority_kind(
    work_kind: str, required_authority_kind: str, authority_factory
) -> None:
    package = application_package()
    package["work_kind"] = work_kind
    package["authority"] = authority_factory()["authority"]

    if package["authority"]["kind"] == required_authority_kind:
        validate_work_package(package)
    else:
        with pytest.raises(CollaborationError, match="COLLAB_PACKAGE_INVALID"):
            validate_work_package(package)


def test_projection_binds_task_to_package_digest() -> None:
    package = application_package()
    task = project_task(package, candidate_task())
    assert task["work_package_id"] == package["package_id"]
    assert task["work_package_digest"] == work_package_digest(package)
    assert task["projection_version"] == "1.0"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("work_package_id", "WP_OTHER"),
        ("work_package_digest", "0" * 64),
        ("projection_version", "0.9"),
    ],
)
def test_projection_rejects_stale_existing_binding(field: str, value: str) -> None:
    package, task = application_package(), candidate_task()
    task.update(
        {
            "work_package_id": package["package_id"],
            "work_package_digest": work_package_digest(package),
            "projection_version": "1.0",
        }
    )
    task[field] = value

    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(package, task)


def test_projection_allows_exact_idempotent_reprojection() -> None:
    package = application_package()
    projected = project_task(package, candidate_task())

    assert project_task(package, projected) == projected


def test_projection_rejects_role_expansion() -> None:
    package, task = application_package(), candidate_task()
    task["role"] = "vba_ui"
    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(package, task)


def test_projection_rejects_wave_expansion() -> None:
    package, task = application_package(), candidate_task()
    task["wave_id"] = "wave2_component_analysis"

    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(package, task)


def test_projection_rejects_phase_expansion() -> None:
    package, task = application_package(), candidate_task()
    task["phase_targets"] = [1, 2]

    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(package, task)


def test_projection_rejects_module_expansion() -> None:
    package, task = application_package(), candidate_task()
    task["module_targets"] = ["module-orders", "module-products"]

    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(package, task)


@pytest.mark.parametrize("package_factory", [application_package, mixed_package])
def test_projection_rejects_cross_app_task(package_factory) -> None:
    package, task = package_factory(), candidate_task()
    task["app_id"] = "OTHER"

    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(package, task)


def test_projection_rejects_write_expansion() -> None:
    package, task = application_package(), candidate_task()
    task["write_paths"] = ["outputs/SYN_Phase1_DataUnderstanding_EN.md"]
    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(package, task)


def test_projection_allows_narrower_module_and_paths() -> None:
    package, task = application_package(), candidate_task()
    package["scope"]["module_targets"].append("module-products")
    package["write_paths"].append("work/sql_data/module-products")
    assert project_task(package, task)["module_targets"] == ["module-orders"]


def test_projected_task_validates_against_task_schema() -> None:
    jsonschema.validate(project_task(application_package(), candidate_task()), task_schema())


def test_legacy_task_without_projection_fields_remains_valid() -> None:
    jsonschema.validate(candidate_task(), task_schema())


def test_partial_projection_fields_are_invalid() -> None:
    task = candidate_task()
    task["work_package_id"] = "WP_SYN_SQL"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(task, task_schema())


def test_projection_rejects_missing_evidence_namespace() -> None:
    task = candidate_task()
    del task["evidence_namespace"]

    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(application_package(), task)


@pytest.mark.parametrize(
    ("field", "value"),
    [("status", "QUEUED"), ("task_id", "lowercase-task")],
)
def test_projection_rejects_schema_invalid_task_fields(field: str, value: str) -> None:
    task = candidate_task()
    task[field] = value

    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(application_package(), task)


def test_projection_rejects_extra_task_property() -> None:
    task = candidate_task()
    task["unexpected"] = True

    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(application_package(), task)


@pytest.mark.parametrize(
    "path",
    [
        "C:/sources/sql",
        "C:\\sources\\sql",
        "D:sources/sql",
        "/sources/sql",
        "../extracted/bundles/bundle-a/code/access-sql",
        "../../../extracted/bundles/bundle-a/code/access-sql",
        "../../extracted/bundles/../bundle-a/code/access-sql",
    ],
)
def test_projection_rejects_escaped_input_paths(path: str) -> None:
    package, task = application_package(), candidate_task()
    task["input_paths"] = [path]

    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(package, task)


def test_projection_allows_parent_prefix_for_input_paths() -> None:
    package, task = application_package(), candidate_task()

    assert project_task(package, task)["input_paths"] == task["input_paths"]


@pytest.mark.parametrize(
    "path", ["../../work/sql_data/module-orders", "work/../sql_data/module-orders"]
)
def test_projection_rejects_parent_segments_in_write_paths(path: str) -> None:
    package, task = application_package(), candidate_task()
    task["write_paths"] = [path]

    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(package, task)


@pytest.mark.parametrize(
    ("field", "path"),
    [
        ("input_paths", "extracted\\bundles\\bundle-a\\code\\access-sql"),
        ("input_paths", "..\\..\\extracted\\bundles\\bundle-a\\code\\access-sql"),
        ("write_paths", "work\\sql_data\\module-orders"),
    ],
)
def test_projection_rejects_backslash_task_paths(field: str, path: str) -> None:
    package, task = application_package(), candidate_task()
    task[field] = [path]

    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(package, task)


@pytest.mark.parametrize(
    ("field", "path"),
    [
        (
            "input_paths",
            "../.././extracted/bundles/bundle-a/code/access-sql",
        ),
        (
            "input_paths",
            "../../extracted/./bundles/bundle-a/code/access-sql",
        ),
        ("write_paths", "work/./sql_data/module-orders"),
        ("input_paths", "./../../extracted/bundles/bundle-a/code/access-sql"),
        ("write_paths", "./work/sql_data/module-orders"),
        ("input_paths", "../../extracted//bundles/bundle-a/code/access-sql"),
        ("write_paths", "work//sql_data/module-orders"),
        ("input_paths", "../../extracted/bundles/bundle-a/code/access-sql/"),
        ("write_paths", "work/sql_data/module-orders/"),
        (
            "input_paths",
            "../../extracted/bundles/bundle-a/code/access-sql/query:stream",
        ),
        ("write_paths", "work/sql_data/module-orders/result:stream"),
    ],
)
def test_projection_rejects_noncanonical_task_paths(field: str, path: str) -> None:
    package, task = application_package(), candidate_task()
    task[field] = [path]

    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(package, task)


@pytest.mark.parametrize("field", ["input_paths", "write_paths"])
@pytest.mark.parametrize(
    "device",
    [
        "CON",
        "prn.txt",
        "Aux.log",
        "nul",
        "COM1",
        "com9.txt",
        "LPT1",
        "lpt9.log",
        "CON ",
        "prN.",
        "AuX .txt",
    ],
)
def test_projection_rejects_windows_device_components(
    field: str, device: str
) -> None:
    package, task = application_package(), candidate_task()
    base = (
        "../../extracted/bundles/bundle-a/code/access-sql"
        if field == "input_paths"
        else "work/sql_data/module-orders"
    )
    task[field] = [f"{base}/{device}"]

    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(package, task)


@pytest.mark.parametrize("field", ["input_paths", "write_paths"])
@pytest.mark.parametrize(
    "name", ["CONSOLE", "PRN-file", "auxiliary.txt", "COM10", "LPT0", "icon .txt"]
)
def test_projection_allows_ordinary_windows_path_components(
    field: str, name: str
) -> None:
    package, task = application_package(), candidate_task()
    base = (
        "../../extracted/bundles/bundle-a/code/access-sql"
        if field == "input_paths"
        else "work/sql_data/module-orders"
    )
    task[field] = [f"{base}/{name}"]

    assert project_task(package, task)[field] == task[field]


@pytest.mark.parametrize("field", ["input_paths", "write_paths"])
@pytest.mark.parametrize("suffix", ["result.", "result ", "folder./file", "..."])
def test_projection_rejects_windows_trimmed_path_components(
    field: str, suffix: str
) -> None:
    package, task = application_package(), candidate_task()
    base = (
        "../../extracted/bundles/bundle-a/code/access-sql"
        if field == "input_paths"
        else "work/sql_data/module-orders"
    )
    task[field] = [f"{base}/{suffix}"]

    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(package, task)


@pytest.mark.parametrize("field", ["input_paths", "write_paths"])
@pytest.mark.parametrize("suffix", ["result.json", "folder.name/file.txt"])
def test_projection_allows_ordinary_dotted_path_components(
    field: str, suffix: str
) -> None:
    package, task = application_package(), candidate_task()
    base = (
        "../../extracted/bundles/bundle-a/code/access-sql"
        if field == "input_paths"
        else "work/sql_data/module-orders"
    )
    task[field] = [f"{base}/{suffix}"]

    assert project_task(package, task)[field] == task[field]


def test_projection_allows_forward_slash_child_paths() -> None:
    package, task = application_package(), candidate_task()
    task["input_paths"] = [
        "../../extracted/bundles/bundle-a/code/access-sql/queries"
    ]
    task["write_paths"] = ["work/sql_data/module-orders/results"]

    projected = project_task(package, task)

    assert projected["input_paths"] == task["input_paths"]
    assert projected["write_paths"] == task["write_paths"]


def test_projected_kit_task_allows_null_evidence_namespace() -> None:
    package, task = kit_projection_pair()

    projected = project_task(package, task)

    assert projected["evidence_namespace"] is None
    jsonschema.validate(projected, task_schema())


def test_legacy_task_with_null_evidence_namespace_is_invalid() -> None:
    task = candidate_task()
    task["evidence_namespace"] = None

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(task, task_schema())


def test_kit_projection_rejects_string_evidence_namespace() -> None:
    package, task = kit_projection_pair()
    task["evidence_namespace"] = "SYN-P1-SQL_DATA-ORDERS"

    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(package, task)


def test_repository_package_does_not_require_app_binding() -> None:
    package, task = kit_projection_pair()
    task["app_id"] = "OTHER"

    assert project_task(package, task)["app_id"] == "OTHER"


def test_projection_rejects_invalid_task_evidence_namespace() -> None:
    task = candidate_task()
    task["evidence_namespace"] = None

    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(application_package(), task)


def test_projection_does_not_mutate_inputs() -> None:
    package, task = application_package(), candidate_task()
    original_package, original_task = deepcopy(package), deepcopy(task)

    project_task(package, task)

    assert package == original_package
    assert task == original_task


def test_projected_task_nested_lists_do_not_alias_candidate() -> None:
    package, task = application_package(), candidate_task()
    projected = project_task(package, task)

    projected["module_targets"].append("module-products")

    assert task["module_targets"] == ["module-orders"]
