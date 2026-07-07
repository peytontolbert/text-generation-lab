#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9126_route_to_loss_translation_contract_design import (
        FORBIDDEN_TRANSLATIONS,
        LOSS_AUTHORITY_RULES,
        ROUTE_TO_LOSSES,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9126_route_to_loss_translation_contract_design import (  # type: ignore
        FORBIDDEN_TRANSLATIONS,
        LOSS_AUTHORITY_RULES,
        ROUTE_TO_LOSSES,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9159
NAME = "stage9159_route_to_loss_readiness_refresh_after_inventory_gates"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9151 = ROOT / "runs/summaries/stage9151_route_card_candidate_quality_gate_contract.json"
SOURCE_9153 = ROOT / "runs/summaries/stage9153_route_card_materialization_preflight_quality_gate_design_audit.json"
SOURCE_9157 = ROOT / "runs/summaries/stage9157_repo_local_inventory_final_authorization_design_audit.json"
SOURCE_9158 = ROOT / "runs/summaries/stage9158_compiler_trainer_no_data_readiness_matrix.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROUTE_TO_LOSS_READINESS_REFRESH_AFTER_INVENTORY_GATES_STAGE9159.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "route_to_loss_readiness_refresh_after_inventory_gates.json"

REQUIRED_UPSTREAM_GATES = [
    "stage9151_candidate_quality_gate_contract_passed",
    "stage9153_route_card_preflight_quality_gate_audit_passed",
    "stage9157_inventory_final_authorization_audit_passed",
    "stage9158_compiler_trainer_no_data_matrix_passed",
    "metadata_inventory_output_exists_and_audited",
    "route_card_materialization_audit_passed",
    "route_cards_schema_validated",
    "route_cards_quality_gate_attached",
    "loss_mask_schema_audit_passed",
]

TRANSLATION_BLOCKERS = [
    "metadata_inventory_not_executed",
    "route_cards_not_materialized",
    "route_card_materialization_audit_missing",
    "route_card_candidate_quality_gate_not_applied_to_real_candidates",
    "loss_mask_schema_not_refreshed_after_new_gates",
    "trainer_input_completeness_not_refreshed",
]

READINESS_OUTPUTS_BLOCKED = [
    "route_to_loss_translation_status.json",
    "route_loss_to_trainer_loss_map.json",
    "loss_mask_cards.jsonl",
    "loss_mask_authority_audit.json",
    "trainer_dry_run_input.json",
]

NEGATIVE_CASES = [
    "source_stage9151_missing",
    "source_stage9153_missing",
    "source_stage9157_missing",
    "source_stage9158_missing",
    "missing_upstream_gate",
    "missing_translation_blocker",
    "missing_blocked_output",
    "route_cards_materialized",
    "translation_ready",
    "loss_masks_materialized",
    "compiler_handoff_ready",
    "trainer_ready",
    "training_authorized",
    "decoder_ce_authorized",
    "denoise_ce_authorized",
    "runtime_authorized",
    "authority_open",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(
    source_9151: dict[str, Any] | None = None,
    source_9153: dict[str, Any] | None = None,
    source_9157: dict[str, Any] | None = None,
    source_9158: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_9151 = source_9151 if source_9151 is not None else load_json(SOURCE_9151)
    source_9153 = source_9153 if source_9153 is not None else load_json(SOURCE_9153)
    source_9157 = source_9157 if source_9157 is not None else load_json(SOURCE_9157)
    source_9158 = source_9158 if source_9158 is not None else load_json(SOURCE_9158)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "card_type": "route_to_loss_readiness_refresh_after_inventory_gates_v1",
        "source_stage_passes": {
            "stage9151": source_9151.get("passed") is True,
            "stage9153": source_9153.get("passed") is True,
            "stage9157": source_9157.get("passed") is True,
            "stage9158": source_9158.get("passed") is True,
        },
        "route_to_losses": json.loads(json.dumps(ROUTE_TO_LOSSES)),
        "loss_authority_rules": json.loads(json.dumps(LOSS_AUTHORITY_RULES)),
        "forbidden_translations": list(FORBIDDEN_TRANSLATIONS),
        "required_upstream_gates": list(REQUIRED_UPSTREAM_GATES),
        "translation_blockers": list(TRANSLATION_BLOCKERS),
        "readiness_outputs_blocked": list(READINESS_OUTPUTS_BLOCKED),
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "refresh_only": True,
            "source_stage9151_passed": source_9151.get("passed") is True,
            "source_stage9153_passed": source_9153.get("passed") is True,
            "source_stage9157_passed": source_9157.get("passed") is True,
            "source_stage9158_passed": source_9158.get("passed") is True,
            "routes": len(ROUTE_TO_LOSSES),
            "loss_authority_rules": len(LOSS_AUTHORITY_RULES),
            "forbidden_translations": len(FORBIDDEN_TRANSLATIONS),
            "required_upstream_gates": len(REQUIRED_UPSTREAM_GATES),
            "translation_blockers": len(TRANSLATION_BLOCKERS),
            "readiness_outputs_blocked": len(READINESS_OUTPUTS_BLOCKED),
            "metadata_inventory_executed_now": False,
            "metadata_path_inventory_materialized_now": False,
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "trainer_dry_run_ready_now": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_accessed": False,
            "file_content_read": False,
            "dataset_rows_loaded": False,
            "cleanup_authorized_now": False,
        },
        "decision": (
            "Route-to-loss readiness is refreshed against the new inventory and "
            "route-card quality gates. Translation remains blocked until real route "
            "cards exist and pass the quality/materialization audits."
        ),
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    metrics = card.get("metrics") or {}
    source_passes = card.get("source_stage_passes") or {}
    for stage in ["stage9151", "stage9153", "stage9157", "stage9158"]:
        if source_passes.get(stage) is not True:
            failures.append(f"{stage}_not_passed")
    for route in ROUTE_TO_LOSSES:
        if route not in card.get("route_to_losses", {}):
            failures.append(f"missing_route_translation:{route}")
    for rule in LOSS_AUTHORITY_RULES:
        if rule not in card.get("loss_authority_rules", {}):
            failures.append(f"missing_loss_authority_rule:{rule}")
    for forbidden in FORBIDDEN_TRANSLATIONS:
        if forbidden not in card.get("forbidden_translations", []):
            failures.append(f"missing_forbidden_translation:{forbidden}")
    for gate in REQUIRED_UPSTREAM_GATES:
        if gate not in card.get("required_upstream_gates", []):
            failures.append(f"missing_upstream_gate:{gate}")
    for blocker in TRANSLATION_BLOCKERS:
        if blocker not in card.get("translation_blockers", []):
            failures.append(f"missing_translation_blocker:{blocker}")
    for output in READINESS_OUTPUTS_BLOCKED:
        if output not in card.get("readiness_outputs_blocked", []):
            failures.append(f"missing_blocked_output:{output}")
    if "decoder_ce" not in card["route_to_losses"].get("KEEP_BOUNDED_DECODER", []):
        failures.append("bounded_decoder_missing_decoder_ce")
    for route in [
        "KEEP_STRUCTURED",
        "HOLD_LONG_OUTPUT",
        "USE_AS_NEGATIVE",
        "NEEDS_RETRIEVAL",
        "QUARANTINE_LABEL_CONFLICT",
        "DROP_DUPLICATE",
        "NEEDS_HUMAN_REVIEW",
    ]:
        if "decoder_ce" in card["route_to_losses"].get(route, []):
            failures.append(f"forbidden_decoder_ce_route:{route}")
    for route in ["QUARANTINE_LABEL_CONFLICT", "DROP_DUPLICATE", "NEEDS_HUMAN_REVIEW"]:
        if card["route_to_losses"].get(route) != []:
            failures.append(f"quarantine_route_has_loss:{route}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    false_keys = [
        "metadata_inventory_executed_now",
        "metadata_path_inventory_materialized_now",
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "loss_mask_cards_materialized_now",
        "compiler_handoff_ready_now",
        "trainer_dry_run_ready_now",
        "trainer_executed_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_accessed",
        "file_content_read",
        "dataset_rows_loaded",
        "cleanup_authorized_now",
    ]
    for key in false_keys:
        if metrics.get(key) is not False:
            failures.append(key)
    return failures


def run_negative_cases() -> dict[str, Any]:
    base = build_card()
    cases: dict[str, dict[str, Any]] = {}
    for name in NEGATIVE_CASES:
        candidate = copy.deepcopy(base)
        if name == "source_stage9151_missing":
            candidate["source_stage_passes"]["stage9151"] = False
            candidate["metrics"]["source_stage9151_passed"] = False
        elif name == "source_stage9153_missing":
            candidate["source_stage_passes"]["stage9153"] = False
            candidate["metrics"]["source_stage9153_passed"] = False
        elif name == "source_stage9157_missing":
            candidate["source_stage_passes"]["stage9157"] = False
            candidate["metrics"]["source_stage9157_passed"] = False
        elif name == "source_stage9158_missing":
            candidate["source_stage_passes"]["stage9158"] = False
            candidate["metrics"]["source_stage9158_passed"] = False
        elif name == "missing_upstream_gate":
            candidate["required_upstream_gates"].remove("route_cards_quality_gate_attached")
        elif name == "missing_translation_blocker":
            candidate["translation_blockers"].remove("route_cards_not_materialized")
        elif name == "missing_blocked_output":
            candidate["readiness_outputs_blocked"].remove("loss_mask_cards.jsonl")
        elif name == "route_cards_materialized":
            candidate["metrics"]["route_cards_materialized_now"] = True
        elif name == "translation_ready":
            candidate["metrics"]["route_to_loss_translation_ready_now"] = True
        elif name == "loss_masks_materialized":
            candidate["metrics"]["loss_mask_cards_materialized_now"] = True
        elif name == "compiler_handoff_ready":
            candidate["metrics"]["compiler_handoff_ready_now"] = True
        elif name == "trainer_ready":
            candidate["metrics"]["trainer_dry_run_ready_now"] = True
        elif name == "training_authorized":
            candidate["metrics"]["training_authorized"] = True
        elif name == "decoder_ce_authorized":
            candidate["metrics"]["decoder_ce_authorized"] = True
        elif name == "denoise_ce_authorized":
            candidate["metrics"]["denoise_ce_authorized"] = True
        elif name == "runtime_authorized":
            candidate["metrics"]["runtime_authorized_flag"] = True
        elif name == "authority_open":
            candidate["authority"]["model_execution_authorized_next"] = True
        cases[name] = candidate
    return {
        name: {"failures": validate_card(candidate), "rejected": bool(validate_card(candidate))}
        for name, candidate in cases.items()
    }


def build_summary() -> dict[str, Any]:
    card = build_card()
    failures = validate_card(card)
    negatives = run_negative_cases()
    checks = {
        "card_passes": failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "quality_gate_required": "route_cards_quality_gate_attached" in card["required_upstream_gates"],
        "inventory_output_required": "metadata_inventory_output_exists_and_audited" in card["required_upstream_gates"],
        "translation_blocked": "route_cards_not_materialized" in card["translation_blockers"],
        "authority_closed": not any(card["authority"].values()),
    }
    all_failures = [key for key, value in checks.items() if value is not True]
    all_failures.extend(failures)
    passed = not all_failures
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "checks": checks,
        "failures": all_failures,
        "card": card,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **card["metrics"],
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
        },
        "decision": card["decision"] if passed else "Route-to-loss readiness refresh failed validation.",
        "next_best_step": "Design loss-mask materialization preflight against refreshed route-to-loss blockers; still do not materialize loss masks or train.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = build_summary()
    CARD.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    public_summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **summary["metrics"], "failures": summary["failures"]},
        "artifacts": {"card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": summary["decision"],
        "next_best_step": summary["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(public_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9159 Route-To-Loss Readiness Refresh After Inventory Gates",
        "",
        f"Passed: `{public_summary['passed']}`",
        "",
        "Refreshes route-to-loss prerequisites after the repo-local inventory and route-card quality gates.",
        "",
        f"Required upstream gates: `{summary['metrics']['required_upstream_gates']}`",
        f"Translation blockers: `{summary['metrics']['translation_blockers']}`",
        f"Negative cases rejected: `{summary['metrics']['negative_cases_rejected']}/{summary['metrics']['negative_cases']}`",
        "",
        f"Next: {public_summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME and row.get("stage") != STAGE]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": public_summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": public_summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = public_summary["passed"]
    registry_json["metrics"] = {
        **(registry_json.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": public_summary["next_best_step"],
        "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(public_summary, indent=2, sort_keys=True))
    raise SystemExit(0 if public_summary["passed"] else 1)


if __name__ == "__main__":
    main()
