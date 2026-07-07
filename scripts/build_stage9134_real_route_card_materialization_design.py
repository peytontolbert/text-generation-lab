#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9124_route_card_schema_recovery_design import (
        ANTI_CHEAT_FIELDS,
        OBJECTIVE_FAMILIES,
        REQUIRED_ROUTE_FIELDS,
        ROUTE_ENUM,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9124_route_card_schema_recovery_design import (  # type: ignore
        ANTI_CHEAT_FIELDS,
        OBJECTIVE_FAMILIES,
        REQUIRED_ROUTE_FIELDS,
        ROUTE_ENUM,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9134
NAME = "stage9134_real_route_card_materialization_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9133 = ROOT / "runs/summaries/stage9133_synthetic_route_to_loss_mask_translator_smoke_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_ROUTE_CARD_MATERIALIZATION_DESIGN_STAGE9134.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "real_route_card_materialization_design.json"

REQUIRED_INPUTS = [
    "objective_rows_jsonl",
    "judge_rows_jsonl",
    "junk_ranker_rows_jsonl",
    "shortcut_baseline_card_json",
    "counterfactual_obligation_card_json",
    "source_lineage_card_json",
]

REQUIRED_OUTPUTS = [
    "route_cards.jsonl",
    "route_card_materialization_audit.json",
    "route_reason_counts.json",
    "route_cell_card.json",
    "route_to_loss_ready_blocker_card.json",
]

JOIN_KEYS = [
    "row_id",
    "semantic_key",
    "source_manifest",
    "split",
    "objective_family",
]

BLOCKERS = [
    "missing_judge_row",
    "missing_ranker_row",
    "missing_source_lineage",
    "shortcut_dominance",
    "counterfactual_obligation_incomplete",
    "label_leak_detected",
    "split_overlap_detected",
    "authority_open",
    "raw_text_forbidden_violation",
    "target_in_input",
    "unknown_route",
    "missing_required_route_field",
]

ROUTE_SOURCE_RULES = {
    "KEEP_STRUCTURED": "ranker recommended KEEP_STRUCTURED and structured anti-cheat passes",
    "KEEP_BOUNDED_DECODER": "ranker recommended KEEP_BOUNDED_DECODER plus deterministic budget/decode facts pass",
    "HOLD_LONG_OUTPUT": "target_over_decoder_budget, long_blob, or html_doc_fragment route",
    "USE_FOR_DENOISE_REPAIR": "internal-token, short/junk, repetition, or verifier-repair route",
    "USE_AS_NEGATIVE": "internal control negative, short-output negative, or abstain/block route",
    "NEEDS_RETRIEVAL": "missing/removed evidence with decode blocked",
    "QUARANTINE_LABEL_CONFLICT": "authority, duplicate, label conflict, leakage, or unresolved judge conflict",
    "DROP_DUPLICATE": "semantic duplicate outside selected split/cell",
    "NEEDS_HUMAN_REVIEW": "judge/ranker disagreement, missing evidence, or ambiguous route",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_design(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9133)
    checks = {
        "source_stage9133_passed": source.get("passed") is True,
        "required_inputs_recorded": len(REQUIRED_INPUTS) >= 6,
        "required_outputs_recorded": len(REQUIRED_OUTPUTS) >= 5,
        "join_keys_recorded": len(JOIN_KEYS) >= 5,
        "blockers_recorded": len(BLOCKERS) >= 12,
        "all_route_enums_have_source_rules": set(ROUTE_SOURCE_RULES) == set(ROUTE_ENUM),
        "required_route_fields_reused": len(REQUIRED_ROUTE_FIELDS) >= 20,
        "objective_families_reused": len(OBJECTIVE_FAMILIES) >= 9,
        "anti_cheat_fields_reused": len(ANTI_CHEAT_FIELDS) >= 6,
        "registry_frontier_stage9133": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9133,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "REAL_ROUTE_CARD_MATERIALIZATION_DESIGN_NO_REAL_DATA_NO_EXECUTION",
        "required_inputs": list(REQUIRED_INPUTS),
        "required_outputs": list(REQUIRED_OUTPUTS),
        "join_keys": list(JOIN_KEYS),
        "blockers": list(BLOCKERS),
        "route_source_rules": dict(ROUTE_SOURCE_RULES),
        "route_card_required_fields": list(REQUIRED_ROUTE_FIELDS),
        "route_enum": list(ROUTE_ENUM),
        "objective_families": list(OBJECTIVE_FAMILIES),
        "anti_cheat_fields": list(ANTI_CHEAT_FIELDS),
        "checks": checks,
        "metrics": {
            "required_inputs": len(REQUIRED_INPUTS),
            "required_outputs": len(REQUIRED_OUTPUTS),
            "join_keys": len(JOIN_KEYS),
            "blockers": len(BLOCKERS),
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "dataset_rows_loaded": False,
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
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Designed real route-card materialization from judge/ranker outputs. This stage does not load real rows or materialize real route cards; it only defines inputs, joins, blockers, outputs, and route source rules.",
    }


def validate_design(design: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in design["checks"].items() if value is not True]
    if any((design.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9133, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for item in REQUIRED_INPUTS:
        if item not in design.get("required_inputs", []):
            failures.append(f"missing_required_input:{item}")
    for item in REQUIRED_OUTPUTS:
        if item not in design.get("required_outputs", []):
            failures.append(f"missing_required_output:{item}")
    for route in ROUTE_ENUM:
        if route not in design.get("route_source_rules", {}):
            failures.append(f"missing_route_source_rule:{route}")
    for blocker in BLOCKERS:
        if blocker not in design.get("blockers", []):
            failures.append(f"missing_blocker:{blocker}")
    for key in [
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "loss_mask_cards_materialized_now",
        "compiler_handoff_ready_now",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "trainer_executed_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]:
        if design["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    design = build_design(registry)
    failures = validate_design(design, registry)
    DESIGN.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **design["metrics"]},
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": design["decision"] if not failures else "Real route-card materialization design failed.",
        "next_best_step": "Audit real route-card materialization design before implementing any real route-card runner.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9134 Real Route-Card Materialization Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Designs the non-executing bridge from judge/ranker outputs to real route cards.",
        "",
        "Required inputs:",
        "",
        *[f"- `{item}`" for item in REQUIRED_INPUTS],
        "",
        "Required outputs:",
        "",
        *[f"- `{item}`" for item in REQUIRED_OUTPUTS],
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
