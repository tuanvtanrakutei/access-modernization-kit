from copy import deepcopy


def kit_package(package_id: str = "WP_KIT_SCHEMA") -> dict:
    return {
        "schema_version": "1.0",
        "package_id": package_id,
        "title": "Add collaboration schema",
        "objective": "Add one validated work-package contract.",
        "work_kind": "kit_contract",
        "authority": {
            "kind": "repository_revision",
            "repository": "access-modernization-kit",
            "base_revision": "8b9f7e0",
        },
        "scope": {
            "roles": [],
            "wave_ids": [],
            "phase_targets": [],
            "module_targets": [],
            "profile_targets": [],
            "adapter_targets": [],
            "document_targets": [],
        },
        "dependencies": [],
        "input_paths": ["plugins/ak/schemas/task.schema.json"],
        "write_paths": ["plugins/ak/schemas/work-package.schema.json"],
        "expected_artifacts": [
            {
                "path": "plugins/ak/schemas/work-package.schema.json",
                "kind": "schema",
                "required": True,
                "publication_class": "scoped",
            }
        ],
        "evidence_namespace": None,
        "validation_commands": [
            "python -m pytest plugins/ak/tests/test_collaboration.py -q"
        ],
        "coordinator": "maintainer",
        "reviewer": "contract-reviewer",
        "publication_policy": "scoped_only",
        "security_constraints": {
            "network": False,
            "live_access": False,
            "live_sql_server": False,
            "production_data": False,
        },
        "created_by": "planner",
        "created_at": "2026-07-28T00:00:00Z",
    }


def application_package(package_id: str = "WP_SYN_SQL") -> dict:
    value = deepcopy(kit_package(package_id))
    value.update(
        {
            "title": "Analyze synthetic SQL evidence",
            "objective": "Produce one scoped SQL evidence fragment.",
            "work_kind": "application_evidence",
            "authority": {
                "kind": "approved_bundle",
                "app_id": "SYN",
                "bundle_id": "bundle-" + "a" * 64,
                "checksum": "b" * 64,
                "bundle_lock_digest": "c" * 64,
                "approval_record_id": "AP-SYN-1",
                "distribution_policy": "artifact_store",
                "artifact_reference": "artifact_store://fixture/SYN/bundle-a",
            },
            "scope": {
                "roles": ["sql_data"],
                "wave_ids": ["wave1_source_extraction"],
                "phase_targets": [1],
                "module_targets": ["module-orders"],
                "profile_targets": [],
                "adapter_targets": [],
                "document_targets": [],
            },
            "input_paths": ["extracted/bundles/bundle-a/code/access-sql"],
            "write_paths": ["work/sql_data/module-orders", "evidence/fragments"],
            "expected_artifacts": [
                {
                    "path": "work/sql_data/module-orders/result.json",
                    "kind": "analysis_fragment",
                    "required": True,
                    "publication_class": "scoped",
                }
            ],
            "evidence_namespace": "SYN-P1-SQL_DATA-ORDERS",
        }
    )
    return value


def candidate_task() -> dict:
    return {
        "task_id": "SYN-W1-SQL-ORDERS", "run_id": "SYN-RUN", "app_id": "SYN",
        "wave_id": "wave1_source_extraction", "role": "sql_data", "phase_targets": [1],
        "module_targets": ["module-orders"], "module_order": ["module-orders"], "dependencies": [],
        "input_paths": ["../../extracted/bundles/bundle-a/code/access-sql"],
        "write_paths": ["work/sql_data/module-orders"],
        "evidence_namespace": "SYN-P1-SQL_DATA-ORDERS", "instructions": [],
        "status": "PENDING", "attempt": 0, "max_attempts": 2, "token_budget": None,
        "created_at": "2026-07-28T00:00:00Z",
    }


def mixed_package(package_id: str = "WP_SYN_PILOT") -> dict:
    value = application_package(package_id)
    value["work_kind"] = "mixed_pilot"
    value["authority"].update(
        {
            "kind": "mixed",
            "repository": "access-modernization-kit",
            "base_revision": "8b9f7e0",
        }
    )
    return value
