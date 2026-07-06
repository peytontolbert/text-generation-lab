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
STAGE = 8964
NAME = "stage8964_focused_manifest_counterbalance_design_no_mining"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FOCUSED_MANIFEST_COUNTERBALANCE_DESIGN_NO_MINING_STAGE8964.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "focused_manifest_counterbalance_design_no_mining.json"
TEMPLATE_ROWS = OUT_DIR / "counterbalance_template_rows_non_trainable.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8963_focused_manifest_patch_queue_interpretation.json"

COUNTERBALANCE_CELLS = [
    {
        "cell_id": "decode_allowed_true_evidence_missing_not_retrieve",
        "breaks_combo": "decode_allowed+evidence_state",
        "required_target_variation": "non_retrieve_obligation_with_missing_evidence_marker_controlled",
        "template_only": True,
    },
    {
        "cell_id": "decode_allowed_false_evidence_direct_retrieve",
        "breaks_combo": "decode_allowed+evidence_state",
        "required_target_variation": "retrieve_obligation_without_decode_permission_shortcut",
        "template_only": True,
    },
    {
        "cell_id": "budget_bad_evidence_missing_not_boundary",
        "breaks_combo": "decoder_budget_ok+evidence_state",
        "required_target_variation": "missing_evidence_obligation_with_budget_bad_controlled",
        "template_only": True,
    },
    {
        "cell_id": "budget_ok_evidence_direct_boundary_like",
        "breaks_combo": "decoder_budget_ok+evidence_state",
        "required_target_variation": "boundary_obligation_without_budget_bad_shortcut",
        "template_only": True,
    },
]

NEUTRAL_EVIDENCE_FEATURES = [
    "has_visible_goal_constraint",
    "has_evidence_sufficiency_reason",
    "has_budget_reason_not_label",
    "has_surface_independent_task_description",
    "has_non_label_failure_signal",
    "has_expected_action_rationale",
]

TRAINABILITY_GATES = [
    "strongest_single_feature_exact_below_0_8",
    "strongest_combo_feature_exact_below_0_8",
    "majority_baseline_recorded",
    "counterbalance_cells_present",
    "neutral_evidence_features_present",
    "counterfactual_obligations_complete",
    "authority_rows_zero",
    "decoder_denoise_runtime_losses_closed_until_authorized",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def template_rows() -> list[dict[str, Any]]:
    rows = []
    for cell in COUNTERBALANCE_CELLS:
        rows.append({
            "template_row_id": f"template::{cell['cell_id']}",
            "cell_id": cell["cell_id"],
            "breaks_combo": cell["breaks_combo"],
            "required_target_variation": cell["required_target_variation"],
            "neutral_evidence_features_required": list(NEUTRAL_EVIDENCE_FEATURES),
            "trainable_now": False,
            "template_only": True,
            "data_mining_authorized": False,
            "training_authorized": False,
            "authority": dict(AUTHORITY_CLOSED),
        })
    return rows


def build_design(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    rows = template_rows()
    checks = {
        "source_stage8963_passed": source.get("passed") is True,
        "source_manifest_not_trainable": (source.get("metrics") or {}).get("manifest_trainable_now") is False,
        "counterbalance_cells_recorded": len(COUNTERBALANCE_CELLS) >= 4,
        "each_shortcut_combo_has_counterbalance": {"decode_allowed+evidence_state", "decoder_budget_ok+evidence_state"}.issubset({row["breaks_combo"] for row in COUNTERBALANCE_CELLS}),
        "neutral_features_recorded": len(NEUTRAL_EVIDENCE_FEATURES) >= 6,
        "trainability_gates_recorded": len(TRAINABILITY_GATES) >= 8,
        "template_rows_non_trainable": all(row["trainable_now"] is False for row in rows),
        "template_rows_authority_closed": all(not any(row["authority"].values()) for row in rows),
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8963": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 8963,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "COUNTERBALANCE_DESIGN_NO_MINING",
        "source_stage": 8963,
        "counterbalance_cells": COUNTERBALANCE_CELLS,
        "neutral_evidence_features": NEUTRAL_EVIDENCE_FEATURES,
        "trainability_gates": TRAINABILITY_GATES,
        "checks": checks,
        "metrics": {
            "counterbalance_cells": len(COUNTERBALANCE_CELLS),
            "neutral_evidence_features": len(NEUTRAL_EVIDENCE_FEATURES),
            "trainability_gates": len(TRAINABILITY_GATES),
            "template_rows": len(rows),
            "trainable_rows": 0,
            "actual_execution_authorized_next": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "template_rows": rows,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Focused manifest counterbalance design is recorded as non-trainable templates only. Actual rows must be sourced or constructed later under a separate no-mining/audit gate before any trainability claim.",
    }


def validate_design(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8963, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["actual_execution_authorized_next", "model_execution_attempted", "runtime_authorized_flag", "training_authorized", "data_mining_authorized", "decoder_ce_authorized", "denoise_ce_authorized", "arxiv_read_authorized_for_compiler", "arxiv_write_authorized"]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    if card["metrics"].get("trainable_rows") != 0:
        failures.append("trainable_rows")
    return failures


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_design(registry)
    failures = validate_design(card, registry)
    rows = card.pop("template_rows")
    DESIGN.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(TEMPLATE_ROWS, rows)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": failures,
            **card["metrics"],
        },
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "template_rows": str(TEMPLATE_ROWS.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "If needed, build a no-mining counterbalance fixture audit from repo-local rows only; do not mine or train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8964 Focused Manifest Counterbalance Design No-Mining",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage records non-trainable counterbalance templates for the focused manifest combo-shortcut issue.",
        "",
        f"Counterbalance cells: `{card['metrics']['counterbalance_cells']}`",
        f"Neutral evidence features: `{card['metrics']['neutral_evidence_features']}`",
        f"Trainable rows: `{card['metrics']['trainable_rows']}`",
        "",
        "No mining, model execution, decoder CE, denoise CE, runtime, checkpoint export, or training is authorized.",
        "",
    ]), encoding="utf-8")
    rows_registry = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows_registry.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows_registry = sorted(rows_registry, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows_registry
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows_registry),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8964 Focused Manifest Counterbalance Design No-Mining"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8964 records non-trainable counterbalance templates for the focused manifest combo-shortcut issue. It does not mine rows or make the manifest trainable.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
