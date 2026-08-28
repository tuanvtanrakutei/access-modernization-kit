from __future__ import annotations

from pathlib import Path
from typing import Any

import evidence_classes
from classification import Classification, resolve_classification

PHASES = tuple(f"phase{i}" for i in range(1, 7))
RANK = {"READY": 0, "NOT_APPLICABLE": 0, "LIMITED": 1, "BLOCKED": 2}
NON_WAIVABLE_RULES = {
    "backend.unknown_boundary.blocks_ready",
}
BASELINE = {
    "phase1": {
        "all": {"field_inventory", "key_index_inventory", "boundary_inventory"},
        "any": {"access_schema_inventory", "server_object_inventory", "external_schema_inventory"},
        "status": "BLOCKED",
    },
    "phase2": {
        "any": {"access_object_inventory", "compiled_object_inventory", "ui_object_inventory", "data_only_proof"},
        "status": "BLOCKED",
    },
    "phase3": {
        "any": {"vba_query_inventory", "compiled_object_inventory", "server_object_inventory", "data_only_proof"},
        "status": "BLOCKED",
    },
    "phase4": {"any": {"trigger_effect_output_trace"}, "status": "BLOCKED"},
    "phase5": {"any": {"document_inventory"}, "status": "LIMITED"},
    "phase6": {
        "all": {"prior_phase_outputs_accepted", "unresolved_risk_register"},
        "status": "BLOCKED",
    },
}


def _missing(require: dict[str, list[str]], capabilities: set[str]) -> list[str]:
    missing = [item for item in require.get("all", []) if item not in capabilities]
    any_items = require.get("any", [])
    if any_items and not capabilities.intersection(any_items):
        missing.append("any:" + "|".join(any_items))
    return missing


def _set_status(target: dict[str, Any], status: str, rule_id: str, reason: str) -> None:
    if RANK[status] > RANK[target["status"]] or status == "NOT_APPLICABLE":
        target["status"] = status
    if rule_id not in target["rule_ids"]:
        target["rule_ids"].append(rule_id)
    target["reasons"].append(reason)


def compute_readiness(
    classification: Classification,
    profiles_dir: Path,
    present_capabilities: set[str],
    waivers: list[dict[str, str]] | None = None,
    package_root: Path | None = None,
    app_root: Path | str | None = None,
) -> dict[str, Any]:
    """Phase readiness by capability, and - when the class contract is reachable - by
    evidence class as well.

    The capability half answers "can an inventory be computed". It cannot answer
    "can this phase say what any of it means", because every capability a bundle
    produces on its own is structural. The class half answers that, and a phase
    that has to publish without a class it needs now says which class and what the
    absence costs, rather than reporting READY and quietly writing counts.

    `package_root` is optional so every existing caller keeps working; without it
    the class half is skipped and behaviour is exactly as before.
    """
    resolved = resolve_classification(classification, profiles_dir)
    result: dict[str, Any] = {
        phase: {"status": "READY", "reasons": [], "rule_ids": []} for phase in PHASES
    }
    for phase, baseline in BASELINE.items():
        missing_all = sorted(baseline.get("all", set()) - present_capabilities)
        any_items = baseline.get("any", set())
        missing_any = bool(any_items) and not present_capabilities.intersection(any_items)
        if missing_all or missing_any:
            missing = missing_all + (["any:" + "|".join(sorted(any_items))] if missing_any else [])
            _set_status(result[phase], baseline["status"], "baseline." + phase, "missing:" + ",".join(missing))
    requested = {item.get("rule_id", "") for item in (waivers or [])}
    rejected = sorted(requested.intersection(NON_WAIVABLE_RULES))
    accepted = sorted(requested - set(rejected))

    for rule in resolved.rules:
        rule_id = rule["id"]
        missing = _missing(rule.get("require", {}), present_capabilities)
        waived = rule_id in accepted
        if missing and not waived:
            limited_proof = rule.get("allow_limited_when", [])
            can_limit = bool(limited_proof) and set(limited_proof).issubset(present_capabilities)
            for phase, declared in rule.get("affects", {}).items():
                status = "LIMITED" if declared == "BLOCKED" and can_limit else declared
                _set_status(result[phase], status, rule_id, f"missing:{','.join(missing)}")
        elif rule.get("applies_when_satisfied"):
            for phase, status in rule.get("affects", {}).items():
                _set_status(result[phase], status, rule_id, "intrinsic_profile_limit")

        proof = set(rule.get("not_applicable_when", []))
        if proof and proof.issubset(present_capabilities):
            for phase, status in rule.get("affects", {}).items():
                if status == "NOT_APPLICABLE":
                    _set_status(result[phase], status, rule_id, "positive_non_applicability_proof")

    classes: dict[str, list[str]] = {}
    if package_root is not None:
        contract = evidence_classes.load_contract(package_root)
        classes = evidence_classes.observe(present_capabilities, app_root)
        present_classes = set(classes)
        for phase in PHASES:
            status = evidence_classes.phase_status(phase, present_classes, contract)
            if not status["known"]:
                continue
            for name in status["blocking"]:
                _set_status(result[phase], "BLOCKED", "classes." + phase, f"missing_class:{name}")
            for degradation in status["degradations"]:
                names = "|".join(degradation["classes"])
                _set_status(
                    result[phase], "LIMITED", "classes." + phase,
                    f"degraded_without:{names}: {degradation['costs']}",
                )
            result[phase]["evidence_classes"] = {
                "required": status["required"],
                "blocking": status["blocking"],
                "degradations": status["degradations"],
            }

    result["_meta"] = {
        "waivers_accepted": accepted,
        "waivers_rejected": rejected,
        "rule_versions": resolved.rule_versions,
        "evidence_classes_present": {name: sorted(why) for name, why in sorted(classes.items())},
    }
    return result
