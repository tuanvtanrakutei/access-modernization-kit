"""Answer, for one phase, what evidence is missing and how to supply it.

Readiness already said which capability a phase lacks. It never said what to do
about it, so `missing:any:trigger_effect_output_trace` was a true statement an
operator could not act on. This maps every capability to the routes that produce
it, and renders the actual commands for each.

Nothing here decides policy. It reports what is satisfied, what is missing, and
what would satisfy it; blocking is the caller's decision.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import evidence_classes
import phase_readiness as phase_readiness_contract
from classification import Classification

RUNTIME = "runtime"
FILES = "files"
DECLARE = "declare"
ANALYSIS = "analysis"

# capability -> (what it is for, [(route, instruction)])
SUPPLY: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "access_schema_inventory": (
        "the tables the application stores data in",
        [(RUNTIME, "acquire the declared Access databases; the DAO tier reads this without starting Access"),
         (FILES, "supply an export package containing schema/tables.json")],
    ),
    "field_inventory": (
        "every column, with type, size and whether it is required",
        [(RUNTIME, "acquire the declared Access databases"),
         (FILES, "supply an export package containing schema/tables.json")],
    ),
    "key_index_inventory": (
        "primary keys and indexes, which is where integrity lives when no relationships are declared",
        [(RUNTIME, "acquire the declared Access databases"),
         (FILES, "supply an export package containing schema/tables.json")],
    ),
    "boundary_inventory": (
        "linked tables and file interfaces - where data enters and leaves",
        [(RUNTIME, "acquire the declared Access databases"),
         (FILES, "supply an export package containing schema/tables.json with connect strings")],
    ),
    "access_object_inventory": (
        "the forms, reports, macros and modules the application is built from",
        [(RUNTIME, "acquire the declared Access databases"),
         (FILES, "supply an export package with forms/, reports/, macros/ and vba/")],
    ),
    "ui_object_inventory": (
        "screens and reports, by name and ideally by definition",
        [(RUNTIME, "acquire with runtime.skip_object_export unset to export definition text"),
         (FILES, "supply an export package with forms/ and reports/")],
    ),
    "vba_query_inventory": (
        "the code and saved queries that carry the business rules",
        [(RUNTIME, "acquire the declared Access databases"),
         (FILES, "supply an export package with vba/ and queries/")],
    ),
    "document_inventory": (
        "business documents describing intended behaviour",
        [(FILES, "place business documents in sources/documents/ or shared-docs/ and declare them as kind: document")],
    ),
    "server_object_inventory": (
        "server-side tables, views and procedures",
        [(FILES, "supply a SQL Server catalog or schema export and declare it as kind: sql_server_catalog")],
    ),
    "backend_authority_declared": (
        "which store the project treats as authoritative",
        [(DECLARE, "in manifest.yaml set role: backend and backend_kind on the authoritative database")],
    ),
    "trigger_effect_output_trace": (
        "which action writes which table and produces which output",
        [(FILES, "place sample inputs the application reads in sources/samples/ and outputs it produces in sources/reports-out/"),
         (RUNTIME, "run the application against a snapshot and record what each action changes")],
    ),
    "prior_phase_outputs_accepted": (
        "phases 1 to 5 reviewed and accepted",
        [(ANALYSIS, "complete and accept the earlier phases; this is a process state, not a file")],
    ),
    "unresolved_risk_register": (
        "the risks the earlier phases left open",
        [(ANALYSIS, "produce the risk register in the synthesis phase")],
    ),
    # Required by the composable profile rules rather than by a phase baseline. A
    # classification that declares a backend or frontend shape is also declaring what
    # has to be proven about it, so each of these is reachable the same way.
    "source_inventory": (
        "a complete list of the sources this run analysed",
        [(RUNTIME, "acquire the declared artifacts; the bundle's own inventory is this"),
         (FILES, "supply the export packages and declare each artifact in manifest.yaml")],
    ),
    "validated_source_export": (
        "an export proven complete against a producer manifest, not a folder taken on trust",
        [(FILES, "run import-sources on the export tree to write import-source-manifest.yaml, "
                 "which declares every member so a truncated package is refused")],
    ),
    "per_artifact_source_availability": (
        "for a mixed project, which artifacts have full source and which are compiled or exported",
        [(DECLARE, "give each artifact its own source availability in manifest.yaml rather than "
                   "one project-wide value")],
    ),
    "definitions_for_referenced_objects": (
        "the definition of every server object the application actually calls",
        [(FILES, "supply the SQL Server object definitions for the views, procedures and functions "
                 "the queries reference")],
    ),
    "dependency_closure": (
        "the full dependency chain of those objects, so nothing referenced is unexamined",
        [(FILES, "supply definitions transitively until nothing referenced is missing")],
    ),
    "server_boundary_declared": (
        "where the server ends and this application begins",
        [(DECLARE, "declare the server or ODBC boundary in manifest.yaml, including which objects "
                   "are owned elsewhere")],
    ),
    "file_interface_inventory": (
        "the text and CSV files this application reads and writes",
        [(RUNTIME, "acquire the databases; linked text tables carry their own connect strings"),
         (FILES, "place the interface files in sources/samples/ and declare them")],
    ),
    "spreadsheet_interface_inventory": (
        "the spreadsheets this application reads and writes",
        [(FILES, "place the spreadsheets in sources/samples/ and declare them as kind: sample")],
    ),
    "external_application_boundary": (
        "what the external application owns and what it exchanges",
        [(DECLARE, "declare the external application boundary and the data crossing it")],
    ),
    "boundary_authority_resolved": (
        "which store is authoritative when the backend is not yet known",
        [(DECLARE, "identify the backend and declare it; this rule is deliberately not waivable, "
                   "because an unresolved boundary makes every later finding provisional")],
    ),
    "data_macro_inventory": (
        "table-level data macros, which run without any form or module involved",
        [(RUNTIME, "acquire the .accdb; data macros live in the database, not in exported text"),
         (FILES, "supply an export that includes data macro definitions")],
    ),
    "sql_server_schema_evidence": (
        "the server schema an ADP project binds to, since it holds no local tables",
        [(FILES, "supply the SQL Server schema or catalog export and declare it")],
    ),
    "compiled_object_inventory": (
        "objects recovered from a compiled database",
        [(FILES, "supply an msaccess-vcs export of the compiled database")],
    ),
    "data_only_proof": (
        "evidence that the database holds data and no interface",
        [(DECLARE, "declare the database as data-only if it genuinely has no forms, reports or macros")],
    ),
    "external_schema_inventory": (
        "schema of an external store the application reads",
        [(FILES, "supply the external schema export and declare it")],
    ),
    "interface_inventory": (
        "the interfaces between the parts of a hybrid application",
        [(FILES, "supply the interface definitions and declare them")],
    ),
}


def required_capabilities(phase: str) -> dict[str, set[str]]:
    baseline = phase_readiness_contract.BASELINE.get(phase, {})
    return {"all": set(baseline.get("all", set())), "any": set(baseline.get("any", set()))}


def requirements(
    phase: int,
    classification: Classification,
    profiles_dir: Path,
    present: set[str],
    supplied_by: dict[str, str] | None = None,
    package_root: Path | None = None,
    app_root: Path | str | None = None,
) -> dict[str, Any]:
    """Report one phase's evidence position, and what would close each gap.

    Capabilities answer whether an inventory can be computed. Evidence classes
    answer whether the phase can say what the inventory means - and when it cannot,
    which class is missing and what the document loses without it. An operator gets
    a thing to fetch either way.
    """
    key = f"phase{phase}"
    readiness = phase_readiness_contract.compute_readiness(
        classification, profiles_dir, present,
        package_root=package_root, app_root=app_root,
    )
    entry = readiness.get(key, {})
    baseline = required_capabilities(key)

    needed = set(baseline["all"])
    # An "any" group is satisfied by one member, so it only becomes a gap as a group.
    any_group = baseline["any"]
    satisfied_any = present & any_group

    satisfied = sorted((needed | any_group) & present)
    missing_all = sorted(needed - present)
    missing_any = sorted(any_group) if any_group and not satisfied_any else []
    missing_all = list(missing_all)
    missing_any = list(missing_any)

    def describe(capability: str) -> dict[str, Any]:
        purpose, routes = SUPPLY.get(capability, ("", []))
        return {
            "capability": capability,
            "needed_for": purpose,
            "supply": [{"route": route, "how": how} for route, how in routes],
        }

    # Readiness states its reasons as "missing:a,b" or "missing:any:x|y", covering both
    # the phase baseline and the composable profile rules. Parsing them is what keeps a
    # BLOCKED verdict from ever arriving without a gap to act on.
    for reason in entry.get("reasons", []):
        text = str(reason)
        if not text.startswith("missing:"):
            continue
        body = text[len("missing:"):]
        if body.startswith("any:"):
            for name in body[len("any:"):].split("|"):
                if name and name not in present:
                    missing_any.append(name)
        else:
            for name in body.split(","):
                if name and name not in present and name not in missing_all:
                    missing_all.append(name)
    missing_all = sorted(dict.fromkeys(missing_all))
    missing_any = sorted(dict.fromkeys(missing_any))

    gaps = [describe(name) for name in missing_all]
    if missing_any:
        gaps.append({
            "capability": "any_of",
            "alternatives": missing_any,
            "needed_for": "any one of these satisfies the phase",
            "supply": [route for name in missing_any for route in describe(name)["supply"]],
        })

    report = {
        "phase": key,
        "status": entry.get("status", "UNKNOWN"),
        "reasons": entry.get("reasons", []),
        "rule_ids": entry.get("rule_ids", []),
        "satisfied": [
            {"capability": name, "supplied_by": (supplied_by or {}).get(name, "present")}
            for name in satisfied
        ],
        "missing": gaps,
    }

    if package_root is not None:
        contract = evidence_classes.load_contract(package_root)
        observed = readiness.get("_meta", {}).get("evidence_classes_present", {})
        status = evidence_classes.phase_status(key, set(observed), contract)
        report["evidence"] = {
            "characteristic_claim": status.get("characteristic_claim", ""),
            "classes_present": observed,
            "blocking": [
                evidence_classes.how_to_supply(name, contract) for name in status["blocking"]
            ],
            # Named, not merely counted: an operator reads what the document will be
            # unable to say, which is the only form of "something is missing" that
            # tells them whether they care.
            "degraded": [
                {
                    "supply_any_of": [
                        evidence_classes.how_to_supply(name, contract)
                        for name in degradation["classes"]
                    ],
                    "otherwise": degradation["costs"],
                }
                for degradation in status["degradations"]
            ],
        }
    return report
