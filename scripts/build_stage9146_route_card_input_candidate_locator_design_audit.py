#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9145_route_card_input_candidate_locator_design import (
        ALLOWED_SEARCH_ROOTS,
        FORBIDDEN_SEARCH_ROOTS,
        LOCATOR_RULES,
        REQUIRED_CANDIDATE_TYPES,
        build_design,
        validate_design,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9145_route_card_input_candidate_locator_design import (  # type: ignore
        ALLOWED_SEARCH_ROOTS,
        FORBIDDEN_SEARCH_ROOTS,
        LOCATOR_RULES,
        REQUIRED_CANDIDATE_TYPES,
        build_design,
        validate_design,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9146
NAME = "stage9146_route_card_input_candidate_locator_design_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9145 = ROOT / "runs/summaries/stage9145_route_card_input_candidate_locator_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROUTE_CARD_INPUT_CANDIDATE_LOCATOR_DESIGN_AUDIT_STAGE9146.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "route_card_input_candidate_locator_design_audit.json"

NEGATIVE_CASES = [
    "missing_artifact_root",
    "missing_summary_root",
    "missing_arxiv_forbidden_root",
    "missing_no_file_content_rule",
    "missing_no_arxiv_rule",
    "missing_objective_candidate_type",
    "locator_executed",
    "path_inventory_materialized",
    "file_content_read",
    "dataset_rows_loaded",
    "arxiv_accessed",
    "ticket_instance_materialized",
    "route_cards_materialized",
    "training_authorized",
    "runtime_authorized",
    "authority_open",
    "bad_registry_frontier",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9145) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_design(registry(latest=9144))
    cases: dict[str, dict[str, Any]] = {}
    for name in NEGATIVE_CASES:
        candidate = copy.deepcopy(base)
        if name == "missing_artifact_root":
            candidate["allowed_search_roots"].remove("runs/local/artifacts")
        elif name == "missing_summary_root":
            candidate["allowed_search_roots"].remove("runs/summaries")
        elif name == "missing_arxiv_forbidden_root":
            candidate["forbidden_search_roots"].remove("/arxiv")
        elif name == "missing_no_file_content_rule":
            candidate["locator_rules"].remove("no_file_content_reads")
        elif name == "missing_no_arxiv_rule":
            candidate["locator_rules"].remove("no_arxiv_reads")
        elif name == "missing_objective_candidate_type":
            candidate["required_candidate_types"].remove("objective_rows_jsonl")
        elif name == "locator_executed":
            candidate["metrics"]["candidate_locator_executed"] = True
        elif name == "path_inventory_materialized":
            candidate["metrics"]["path_inventory_materialized"] = True
        elif name == "file_content_read":
            candidate["metrics"]["file_content_read"] = True
        elif name == "dataset_rows_loaded":
            candidate["metrics"]["dataset_rows_loaded"] = True
        elif name == "arxiv_accessed":
            candidate["metrics"]["arxiv_accessed"] = True
        elif name == "ticket_instance_materialized":
            candidate["metrics"]["ticket_instance_materialized"] = True
        elif name == "route_cards_materialized":
            candidate["metrics"]["route_cards_materialized_now"] = True
        elif name == "training_authorized":
            candidate["metrics"]["training_authorized"] = True
        elif name == "runtime_authorized":
            candidate["metrics"]["runtime_authorized_flag"] = True
        elif name == "authority_open":
            candidate["authority"]["model_execution_authorized_next"] = True
        cases[name] = candidate

    audited: dict[str, Any] = {}
    for name, candidate in cases.items():
        failures = validate_design(candidate, registry(latest=9999) if name == "bad_registry_frontier" else registry(latest=9144))
        audited[name] = {"failures": failures, "rejected": bool(failures)}
    return audited


def build_audit(registry_card: dict[str, Any] | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    source = load_json(SOURCE_9145)
    design_registry = registry(latest=9144)
    base = build_design(design_registry)
    base_failures = validate_design(base, design_registry)
    negatives = run_negative_cases()
    checks = {
        "source_stage9145_passed": source.get("passed") is True,
        "base_design_passes": base_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "allowed_roots_complete": set(ALLOWED_SEARCH_ROOTS).issubset(set(base["allowed_search_roots"])),
        "forbidden_roots_complete": set(FORBIDDEN_SEARCH_ROOTS).issubset(set(base["forbidden_search_roots"])),
        "candidate_types_complete": set(REQUIRED_CANDIDATE_TYPES).issubset(set(base["required_candidate_types"])),
        "locator_rules_complete": set(LOCATOR_RULES).issubset(set(base["locator_rules"])),
        "locator_not_executed": base["metrics"]["candidate_locator_executed"] is False,
        "path_inventory_not_materialized": base["metrics"]["path_inventory_materialized"] is False,
        "file_content_not_read": base["metrics"]["file_content_read"] is False,
        "arxiv_not_accessed": base["metrics"]["arxiv_accessed"] is False,
        "authority_closed": not any(base["authority"].values()),
        "registry_frontier_stage9145": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9145,
        "authority_counts_zero": not any(((registry_card.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    failures = [key for key, value in checks.items() if value is not True]
    failures.extend(base_failures)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "base_failures": base_failures,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
            "candidate_locator_design_audited": True,
            "candidate_locator_executed": False,
            "path_inventory_materialized": False,
            "file_content_read": False,
            "dataset_rows_loaded": False,
            "arxiv_accessed": False,
            "ticket_instance_materialized": False,
            "real_input_authorized_now": False,
            "real_judge_rows_used": 0,
            "real_ranker_rows_used": 0,
            "real_route_cards_materialized": 0,
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "repository_source_bodies_loaded": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "decision": "Audited route-card input candidate locator design and rejected missing root controls, missing no-read rules, locator execution, path inventory materialization, file-content reads, dataset loading, /arxiv access, ticket instance creation, route-card materialization, training, runtime, and authority openings.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry_json)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Route-card input candidate locator design audit failed.",
        "next_best_step": "Implement metadata-only repo-local path inventory design; do not execute inventory yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9146 Route-Card Input Candidate Locator Design Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Negative cases rejected: `{audit['metrics']['negative_cases_rejected']}/{audit['metrics']['negative_cases']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = summary["passed"]
    registry_json["metrics"] = {
        **(registry_json.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
