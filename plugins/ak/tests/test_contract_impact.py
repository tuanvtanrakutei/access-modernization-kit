from copy import deepcopy
import json
from pathlib import Path

import jsonschema
import pytest

from collaboration import CollaborationError
from collaboration_helpers import acceptance_receipt, impact, kit_package
from contract_impact import contract_impact_required, validate_contract_impact
from review import validate_review_receipt


SENSITIVE_PATHS = [
    "plugins/ak/schemas/task.schema.json",
    "plugins/ak/contracts/bundle.py",
    "plugins/ak/profiles/frontend.yaml",
    "plugins/ak/adapters/managed_access/adapter.py",
    "plugins/ak/orchestration/waves.json",
    "plugins/ak/scripts/ak.py",
]


def schema() -> dict:
    path = Path(__file__).resolve().parents[1] / "schemas/contract-impact.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def implementation_receipt(package: dict, stage: str = "implementation") -> dict:
    receipt = acceptance_receipt(package)
    receipt["review_stage"] = stage
    receipt["producer"] = "implementation-agent"
    receipt["reviewed_at"] = "2026-07-28T00:30:00Z"
    receipt["authority_snapshot"] = {
        **receipt["authority_snapshot"],
        "produced_revision": "cafebabe",
    }
    if stage == "publication":
        receipt["publication_phase"] = 1
    return receipt


@pytest.mark.parametrize("path", SENSITIVE_PATHS)
def test_contract_paths_require_impact(path: str) -> None:
    assert contract_impact_required([path])


@pytest.mark.parametrize(
    "path",
    [
        "plugins/ak/templates/phase1-data-understanding.md",
        "plugins/ak/specifications/output-contract.yaml",
        "plugins\\ak\\contracts\\review.py",
    ],
)
def test_all_sensitive_prefixes_use_portable_normalization(path: str) -> None:
    assert contract_impact_required([path])


@pytest.mark.parametrize(
    "path",
    ["plugins", "plugins/ak", "plugins/ak/scripts"],
)
def test_sensitive_ancestor_scopes_require_impact(path: str) -> None:
    assert contract_impact_required([path])


@pytest.mark.parametrize("path", ["plugins/ak/tests", "plugins/aka"])
def test_nonsensitive_sibling_scopes_do_not_require_impact(path: str) -> None:
    assert not contract_impact_required([path])


def test_ordinary_test_change_does_not_require_impact() -> None:
    assert not contract_impact_required(
        ["plugins/ak/tests/test_collaboration.py"]
    )


@pytest.mark.parametrize(
    "paths",
    [
        ["../plugins/ak/contracts/review.py"],
        ["C:/repo/plugins/ak/contracts/review.py"],
        ["plugins/ak/contracts/review.py", "plugins/ak/contracts/REVIEW.py"],
    ],
)
def test_changed_path_gate_rejects_nonportable_or_ambiguous_paths(
    paths: list[str],
) -> None:
    with pytest.raises(CollaborationError, match="COLLAB_IMPACT_REQUIRED"):
        contract_impact_required(paths)


def test_valid_impact_matches_package_and_changed_paths() -> None:
    package = kit_package()

    validate_contract_impact(
        package,
        impact(package),
        ["plugins\\ak\\schemas\\work-package.schema.json"],
    )


def test_contract_impact_schema_is_closed_draft_2020_12() -> None:
    value = schema()

    assert value["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert value["additionalProperties"] is False
    jsonschema.Draft202012Validator.check_schema(value)


@pytest.mark.parametrize(
    "field",
    [
        "schema_version", "impact_id", "work_package_id",
        "work_package_digest", "changed_paths", "affected_contracts",
        "compatibility", "migration_behavior", "synthetic_fixtures",
        "compatibility_tests", "documentation_updates", "validation_evidence",
        "untested_runtime_paths", "untested_runtime_reason",
        "security_and_data_handling_impact", "release_target", "reviewer",
    ],
)
def test_contract_impact_schema_requires_every_design_field(field: str) -> None:
    package = kit_package()
    record = impact(package)
    del record[field]

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, schema())


def test_contract_impact_schema_rejects_additional_properties() -> None:
    package = kit_package()
    record = impact(package)
    record["optional_later"] = True

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, schema())


@pytest.mark.parametrize(
    ("compatibility", "migration_required"),
    [("compatible", False), ("migration_required", True), ("breaking", True)],
)
def test_compatibility_matches_migration_requirement(
    compatibility: str, migration_required: bool
) -> None:
    package = kit_package()
    record = impact(package)
    record["compatibility"] = compatibility
    record["migration_behavior"]["required"] = migration_required

    validate_contract_impact(package, record, record["changed_paths"])


@pytest.mark.parametrize(
    ("compatibility", "migration_required"),
    [("compatible", True), ("migration_required", False), ("breaking", False)],
)
def test_inconsistent_migration_behavior_is_rejected(
    compatibility: str, migration_required: bool
) -> None:
    package = kit_package()
    record = impact(package)
    record["compatibility"] = compatibility
    record["migration_behavior"]["required"] = migration_required

    with pytest.raises(CollaborationError, match="COLLAB_IMPACT_REQUIRED"):
        validate_contract_impact(package, record, record["changed_paths"])


@pytest.mark.parametrize(
    "field",
    [
        "changed_paths", "affected_contracts", "synthetic_fixtures",
        "compatibility_tests", "documentation_updates", "validation_evidence",
    ],
)
def test_required_impact_arrays_cannot_be_empty(field: str) -> None:
    package = kit_package()
    record = impact(package)
    record[field] = []

    with pytest.raises(CollaborationError, match="COLLAB_IMPACT_REQUIRED"):
        validate_contract_impact(package, record, record["changed_paths"])


def test_empty_untested_paths_require_explicit_reason() -> None:
    package = kit_package()
    record = impact(package)
    record["untested_runtime_reason"] = " "

    with pytest.raises(CollaborationError, match="COLLAB_IMPACT_REQUIRED"):
        validate_contract_impact(package, record, record["changed_paths"])


@pytest.mark.parametrize(
    "value",
    [
        "N/A", "NA", "none", "later", "unknown", "TBD", "TODO",
        "N/A.", "unknown pending review", "TBD - determine later",
        "Not applicable", "not-applicable.", "TO BE DETERMINED",
        "Pending review - assign owner",
        "Pending", "Pending compatibility confirmation",
        "Awaiting review", "awaiting-review.",
        "Not yet determined", "NOT YET DETERMINED - verify fixture",
    ],
)
@pytest.mark.parametrize(
    "field",
    [
        "migration_summary", "untested_runtime_reason",
        "security_and_data_handling_impact", "validation_evidence",
    ],
)
def test_vague_impact_values_are_rejected(field: str, value: str) -> None:
    package = kit_package()
    record = impact(package)
    if field == "migration_summary":
        record["migration_behavior"]["summary"] = value
    elif field == "validation_evidence":
        record[field] = [value]
    else:
        record[field] = value

    with pytest.raises(CollaborationError, match="COLLAB_IMPACT_REQUIRED"):
        validate_contract_impact(package, record, record["changed_paths"])


@pytest.mark.parametrize(
    "value",
    [
        "The migration state remains unknown after review.",
        "The migration state remains pending after review.",
        "The migration owner marked this tbd after review.",
        "The migration owner marked this todo after review.",
        "The migration owner will decide this later after review.",
    ],
)
def test_standalone_placeholder_words_are_rejected_anywhere(value: str) -> None:
    package = kit_package()
    record = impact(package)
    record["migration_behavior"]["summary"] = value

    with pytest.raises(CollaborationError, match="COLLAB_IMPACT_REQUIRED"):
        validate_contract_impact(package, record, record["changed_paths"])


@pytest.mark.parametrize(
    "value",
    [
        "The review explains why this case is not applicable to generated data.",
        "The migration owner marks the item pending review after validation.",
        "The report leaves the runtime choice to be determined by deployers.",
        "The package remains pending after deterministic validation.",
        "The evidence is awaiting review after all commands complete.",
        "The final platform choice is not yet determined by this record.",
    ],
)
def test_placeholder_phrases_are_rejected_anywhere(
    value: str,
) -> None:
    package = kit_package()
    record = impact(package)
    record["migration_behavior"]["summary"] = value

    with pytest.raises(CollaborationError, match="COLLAB_IMPACT_REQUIRED"):
        validate_contract_impact(package, record, record["changed_paths"])


@pytest.mark.parametrize(
    "value",
    [
        "No pending migration remains after validation.",
        "No unknown runtime paths remain after validation.",
    ],
)
def test_immediately_negated_placeholder_words_are_allowed(value: str) -> None:
    package = kit_package()
    record = impact(package)
    record["migration_behavior"]["summary"] = value

    validate_contract_impact(package, record, record["changed_paths"])


@pytest.mark.parametrize(
    "command",
    [
        "python /tmp/test.py",
        "python ../../outside/test.py",
        'python "C:/repo/test.py"',
        "python '/tmp/test.py'",
        r"python C:\repo\test.py",
        "python C://repo/test.py",
        "python scripts/check.py >/tmp/result.txt",
        "python scripts/check.py --output:/tmp/result.txt",
        'python scripts/check.py --output:"/tmp/result.txt"',
        "python scripts/check.py -o=/tmp/result.txt",
        "python scripts/check.py -o:../../x",
        "python scripts/check.py --endpoint=file:///tmp/resource",
        "python scripts/check.py -I/usr/include",
        "python scripts/check.py -I../include",
        "python scripts/check.py -o/tmp/result",
        "python scripts/check.py -o../result",
        "python scripts/check.py -Wl,-rpath,/usr/lib",
        "python scripts/check.py -Wl,-rpath,../lib",
        "python scripts/check.py --hooks=/tmp/hooks",
        "python scripts/check.py --hooks=../hooks",
        "python scripts/check.py --hooks=C:/tmp/hooks",
        'python scripts/check.py --cache_dir="/tmp/cache"',
        "python scripts/check.py value(/tmp)",
        "python scripts/check.py value=../x",
        "python scripts/check.py value,C:/x",
        "python scripts/check.py @args.txt",
        "python scripts/check.py $HOME/input",
        "python scripts/check.py ${TMPDIR}/input",
        "python scripts/check.py $(pwd)/input",
        "python scripts/check.py %TEMP%/input",
        "python scripts/check.py `pwd`/input",
        "python scripts/check.py test_*.py",
        "python scripts/check.py test_?.py",
        "python scripts/check.py [ab].txt",
        "python scripts/check.py {one,two}",
        "python scripts/check.py ~other/input",
        "python scripts/check.py | tee result.txt",
        "python scripts/check.py & echo done",
        "python scripts/check.py; echo done",
    ],
)
def test_validation_evidence_rejects_nonportable_command_paths(
    command: str,
) -> None:
    package = kit_package()
    record = impact(package)
    record["validation_evidence"] = [command]

    with pytest.raises(CollaborationError, match="COLLAB_IMPACT_REQUIRED"):
        validate_contract_impact(package, record, record["changed_paths"])


@pytest.mark.parametrize(
    "command",
    [
        "node ./validate.js",
        "ruby ./validate.rb",
        "perl ./validate.pl",
        "php ./validate.php",
        "lua ./validate.lua",
        "Rscript ./validate.r",
        "sh ./validate.sh",
        "bash ./validate.sh",
        "dash ./validate.sh",
        "zsh ./validate.sh",
        "ksh ./validate.sh",
        "fish ./validate.fish",
        "csh ./validate.csh",
        "tcsh ./validate.csh",
        "ash ./validate.sh",
        "pwsh -File ./validate.ps1",
        "powershell -NoProfile ./validate.ps1",
        "cmd /q",
        "uv run python -m pytest",
        "env python -m pytest",
        "command python -m pytest",
        "nice python -m pytest",
        "FOO=bar python -m pytest",
        "python",
        "python -",
        "python -i",
        'python -c "print(1)"',
        "python --version",
        "py -V:3.12 -m pytest",
        "python scripts/check.py\nnode evil.js",
        "python -m pytest\nwhoami",
        "python scripts/check.py\rwhoami",
        "python -c.py",
        "python -m.py",
        "py -3.13t -c.py",
        "python CON.py",
        "python scripts./check.py",
    ],
)
def test_validation_evidence_rejects_non_direct_python_commands(
    command: str,
) -> None:
    package = kit_package()
    record = impact(package)
    record["validation_evidence"] = [command]

    with pytest.raises(CollaborationError, match="COLLAB_IMPACT_REQUIRED"):
        validate_contract_impact(package, record, record["changed_paths"])


def test_validation_evidence_accepts_long_harmless_command() -> None:
    package = kit_package()
    record = impact(package)
    arguments = [f"arg{index}" for index in range(64)]
    record["validation_evidence"] = [
        " ".join(["python", "scripts/check.py", *arguments])
    ]

    validate_contract_impact(package, record, record["changed_paths"])


@pytest.mark.parametrize(
    "command",
    [
        "python -m pytest plugins/ak/tests/test_collaboration.py -q",
        "python 'plugins/ak/tests/test_collaboration.py' --maxfail=1",
        "python -m tool --endpoint=https://example.test/a/../b -q",
        "python -m pytest --cov-report=term-missing:skip-covered",
        "python -m pytest --filterwarnings=error::DeprecationWarning",
        'python scripts/check.py --endpoint="https://example.test/query?a=1&b=2"',
        "python -m pytest plugins/ak/tests/test_contract_impact.py -q",
        "python ./relative.py",
        "python3.12 scripts/check.py",
        "python3.13t -m pytest",
        "python3.13t.exe scripts/check.py",
        "py -m pytest",
        "py -3.12 -m pytest",
        "py -3.13t -m pytest",
        "py -3.13t scripts/check.py",
        "PYTHON.EXE -m pytest",
        (
            "python ./plugins/ak/scripts/validate_structure.py "
            "--package plugins/ak --repository-root ."
        ),
    ],
)
def test_validation_evidence_accepts_portable_commands(command: str) -> None:
    package = kit_package()
    record = impact(package)
    record["validation_evidence"] = [command]

    validate_contract_impact(package, record, record["changed_paths"])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("changed_paths", "plugins/ak/contracts/../schemas/task.schema.json"),
        ("affected_contracts", "../task.schema.json"),
        ("synthetic_fixtures", "C:/fixtures/collaboration"),
        ("compatibility_tests", "plugins/ak/tests//test_contract_impact.py"),
        ("documentation_updates", "docs\\collaboration\\changes.md"),
        ("untested_runtime_paths", "plugins/ak/adapters/../scripts/ak.py"),
    ],
)
def test_impact_path_arrays_require_portable_paths(field: str, value: str) -> None:
    package = kit_package()
    record = impact(package)
    record[field] = [value]

    with pytest.raises(CollaborationError, match="COLLAB_IMPACT_REQUIRED"):
        validate_contract_impact(package, record, record["changed_paths"])


@pytest.mark.parametrize(
    "field",
    [
        "changed_paths", "affected_contracts", "synthetic_fixtures",
        "compatibility_tests", "documentation_updates", "validation_evidence",
        "untested_runtime_paths",
    ],
)
def test_impact_arrays_reject_duplicates_and_casefold_collisions(field: str) -> None:
    package = kit_package()
    record = impact(package)
    original = record[field][0] if record[field] else "plugins/ak/scripts/ak.py"
    record[field] = [original, original.swapcase()]
    changed_paths = (
        ["plugins/ak/schemas/work-package.schema.json"]
        if field == "changed_paths"
        else record["changed_paths"]
    )

    with pytest.raises(CollaborationError, match="COLLAB_IMPACT_REQUIRED"):
        validate_contract_impact(package, record, changed_paths)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("work_package_id", "WP_OTHER"),
        ("work_package_digest", "0" * 64),
        ("reviewer", "other-reviewer"),
        ("release_target", "2.8.0"),
    ],
)
def test_impact_identity_and_plan_release_are_exact(field: str, value: str) -> None:
    package = kit_package()
    record = impact(package)
    record[field] = value

    with pytest.raises(CollaborationError, match="COLLAB_IMPACT_REQUIRED"):
        validate_contract_impact(package, record, record["changed_paths"])


def test_impact_reviewer_must_be_independent_from_package_creator() -> None:
    package = kit_package()
    package["reviewer"] = package["created_by"]
    record = impact(package)

    with pytest.raises(CollaborationError, match="COLLAB_IMPACT_REQUIRED"):
        validate_contract_impact(package, record, record["changed_paths"])


def test_changed_paths_must_match_exact_normalized_set() -> None:
    package = kit_package()
    record = impact(package)

    with pytest.raises(CollaborationError, match="COLLAB_IMPACT_REQUIRED"):
        validate_contract_impact(
            package,
            record,
            [record["changed_paths"][0], "plugins/ak/contracts/review.py"],
        )


@pytest.mark.parametrize("stage", ["implementation", "publication"])
def test_sensitive_implementation_and_publication_require_impact(stage: str) -> None:
    package = kit_package()
    receipt = implementation_receipt(package, stage)
    kwargs = {
        "expected_producer": "implementation-agent",
        "produced_revision": "cafebabe",
        "changed_paths": ["plugins/ak/schemas/work-package.schema.json"],
    }
    if stage == "publication":
        kwargs["expected_publication_phase"] = 1

    with pytest.raises(CollaborationError, match="COLLAB_IMPACT_REQUIRED"):
        validate_review_receipt(package, receipt, **kwargs)


@pytest.mark.parametrize("stage", ["implementation", "publication"])
def test_sensitive_review_accepts_matching_impact(stage: str) -> None:
    package = kit_package()
    receipt = implementation_receipt(package, stage)
    kwargs = {
        "expected_producer": "implementation-agent",
        "produced_revision": "cafebabe",
        "changed_paths": ["plugins/ak/schemas/work-package.schema.json"],
        "contract_impact": impact(package),
    }
    if stage == "publication":
        kwargs["expected_publication_phase"] = 1

    validate_review_receipt(package, receipt, **kwargs)


def test_scope_acceptance_never_requires_contract_impact() -> None:
    package = kit_package()

    validate_review_receipt(
        package,
        acceptance_receipt(package),
        changed_paths=["plugins/ak/schemas/work-package.schema.json"],
    )


def test_ordinary_or_legacy_review_does_not_require_contract_impact() -> None:
    package = kit_package()
    receipt = implementation_receipt(package)
    common = {
        "expected_producer": "implementation-agent",
        "produced_revision": "cafebabe",
    }

    validate_review_receipt(
        package,
        deepcopy(receipt),
        changed_paths=["plugins/ak/tests/test_contract_impact.py"],
        **common,
    )
    validate_review_receipt(package, receipt, **common)
