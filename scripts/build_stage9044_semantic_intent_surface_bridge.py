#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9044
NAME = "stage9044_semantic_intent_surface_bridge"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_8613 = ROOT / "runs/summaries/stage8613_reconstructed_codex_session_training_detail_recovery.json"
SOURCE_8615 = ROOT / "runs/summaries/stage8615_reconstructed_recovered_variable_ledger.json"
ACTION_REGISTRY = ROOT / "docs/SOFTWARE_MAINTAINER_ACTION_FEATURE_REGISTRY.md"
GAP_STATUS = ROOT / "docs/MINING_AND_TRAINING_RECOVERY_GAP_STATUS.md"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SEMANTIC_INTENT_SURFACE_BRIDGE_STAGE9044.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "semantic_intent_surface_bridge.json"

SEMANTIC_SURFACES = [
    "maintainer_answer",
    "repair_plan",
    "bounded_patch_hunk",
    "test_plan",
    "repo_qa_answer",
    "retrieve_more_answer",
    "abstain_unsafe_answer",
    "verifier_failure_summary",
    "symbol_binding_decision",
    "edit_localization_decision",
    "patch_operator_decision",
]
USER_INTENT_FIELDS = [
    "intent_type",
    "requested_output_type",
    "target_language",
    "repo_scope",
    "allowed_imports",
    "blocked_imports",
    "available_repositories",
    "file_creation_allowed",
    "modify_existing_allowed",
    "test_required",
    "verification_mode",
    "risk_tolerance",
    "budget_constraints",
]
ANTI_CHEAT_REQUIREMENTS = [
    "semantic_presentation_not_equal_objective_label",
    "requested_output_type_not_equal_target_action",
    "intent_type_alone_must_not_solve_build_mode",
    "presentation_surface_alone_must_not_solve_repair_surface",
    "direct_target_markers_masked_or_neutralized",
    "shortcut_baseline_required_for_intent_and_surface_fields",
    "counterfactual_sibling_required_when_intent_surface_changes",
]
FUTURE_ROW_FIELDS = [
    "row_id",
    "split",
    "semantic_presentation",
    "user_intent",
    "state_before_ref",
    "retrieval_refs",
    "action_candidates",
    "target_transition",
    "loss_mask",
    "gate_status",
    "authority",
]
FORBIDDEN_NOW = [
    "mine_user_intent_rows_now",
    "materialize_semantic_surface_rows_now",
    "train_intent_surface_heads_now",
    "decoder_ce_for_semantic_surface_now",
    "read_arxiv_body_rows_now",
    "read_repository_source_bodies_now",
    "write_arxiv_now",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    s8613 = load_json(SOURCE_8613)
    s8615 = load_json(SOURCE_8615)
    action_text = text(ACTION_REGISTRY)
    gap_text = text(GAP_STATUS)
    checks = {
        "source_stage8613_present": SOURCE_8613.exists(),
        "source_stage8613_passed": s8613.get("passed") is True,
        "source_stage8613_semantic_recovered": "semantic_presentation" in ((s8613.get("metrics") or {}).get("recovered_groups") or []),
        "source_stage8613_user_intent_recovered": "user_intent" in ((s8613.get("metrics") or {}).get("recovered_groups") or []),
        "source_stage8615_present": SOURCE_8615.exists(),
        "source_stage8615_passed": s8615.get("passed") is True,
        "action_registry_mentions_semantic_presentation": "Semantic Presentation And User Intent" in action_text,
        "action_registry_records_all_surfaces": all(surface in action_text for surface in SEMANTIC_SURFACES),
        "action_registry_records_all_user_intent_fields": all(field in action_text for field in USER_INTENT_FIELDS),
        "gap_status_records_semantic_user_intent": "semantic presentation" in gap_text and "User Intent Fields" in gap_text,
        "anti_cheat_requirements_recorded": len(ANTI_CHEAT_REQUIREMENTS) >= 7,
        "future_row_fields_recorded": len(FUTURE_ROW_FIELDS) >= 11,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "SEMANTIC_INTENT_SURFACE_BRIDGE_CONTRACT_ONLY",
        "semantic_surfaces": SEMANTIC_SURFACES,
        "user_intent_fields": USER_INTENT_FIELDS,
        "anti_cheat_requirements": ANTI_CHEAT_REQUIREMENTS,
        "future_row_fields": FUTURE_ROW_FIELDS,
        "forbidden_now": FORBIDDEN_NOW,
        "checks": checks,
        "metrics": {
            "semantic_surfaces": len(SEMANTIC_SURFACES),
            "user_intent_fields": len(USER_INTENT_FIELDS),
            "anti_cheat_requirements": len(ANTI_CHEAT_REQUIREMENTS),
            "future_row_fields": len(FUTURE_ROW_FIELDS),
            "contract_only": True,
            "semantic_surface_rows_materialized_now": False,
            "user_intent_rows_mined_now": False,
            "intent_surface_heads_training_authorized_now": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "arxiv_body_rows_read_now": False,
            "repository_source_bodies_read_now": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "model_execution_attempted": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Promote recovered semantic-presentation and user-intent variables into the active maintainer row contract without mining or training.",
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "semantic_surface_rows_materialized_now",
        "user_intent_rows_mined_now",
        "intent_surface_heads_training_authorized_now",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "arxiv_body_rows_read_now",
        "repository_source_bodies_read_now",
        "arxiv_write_authorized",
        "training_authorized",
        "model_execution_attempted",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"bridge": str(CARD.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "When future source tickets pass, require semantic_presentation/user_intent shortcut audits before any intent-to-build or bounded-decoder manifest can create gradients.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9044 Semantic Intent Surface Bridge",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This contract promotes recovered semantic-presentation and user-intent fields into the active maintainer row schema.",
        "It does not mine data, read `/arxiv` bodies, materialize rows, run models, or authorize training.",
        "",
        "## Semantic Surfaces",
        "",
        *[f"- `{item}`" for item in SEMANTIC_SURFACES],
        "",
        "## User Intent Fields",
        "",
        *[f"- `{item}`" for item in USER_INTENT_FIELDS],
        "",
        "## Anti-Cheat Requirements",
        "",
        *[f"- `{item}`" for item in ANTI_CHEAT_REQUIREMENTS],
        "",
        f"Next: {summary['next_best_step']}",
        "",
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
