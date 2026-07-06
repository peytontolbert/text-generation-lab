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
STAGE = 8963
NAME = "stage8963_focused_manifest_patch_queue_interpretation"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FOCUSED_MANIFEST_PATCH_QUEUE_INTERPRETATION_STAGE8963.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "focused_manifest_patch_queue_interpretation.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8962_focused_manifest_audit_only_compiler_refresh.json"
SHORTCUT_CARD = ROOT / "runs/local/artifacts/stage8962_focused_manifest_audit_only_compiler_refresh/compiler_outputs/shortcut_baseline_card.json"
PATCH_QUEUE = ROOT / "runs/local/artifacts/stage8962_focused_manifest_audit_only_compiler_refresh/compiler_outputs/dataset_patch_queue.jsonl"

REPAIR_REQUIREMENTS = [
    "add_rows_where_decode_allowed_and_evidence_state_combo_no_longer_solves_obligation_type",
    "add_rows_where_decoder_budget_ok_and_evidence_state_combo_no_longer_solves_obligation_type",
    "counterbalance_missing_evidence_with_multiple_obligation_types",
    "counterbalance_budget_bad_with_multiple_obligation_types",
    "add_neutral_non_label_evidence_features",
    "rerun_shortcut_baselines_before_trainability",
]

TRAINABILITY_DECISION = {
    "manifest_trainable_now": False,
    "reason": "combo_feature_shortcut_exact_1_0",
    "single_feature_baseline_ok": True,
    "combo_feature_baseline_ok": False,
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    shortcut = load_json(SHORTCUT_CARD)
    patch_queue = load_jsonl(PATCH_QUEUE)
    combo = shortcut.get("combo_feature_exact") or {}
    strongest_combo = float(shortcut.get("strongest_combo_feature_exact", 0.0) or 0.0)
    strongest_single = float(shortcut.get("strongest_single_feature_exact", 0.0) or 0.0)
    checks = {
        "source_stage8962_passed": source.get("passed") is True,
        "patch_queue_present": len(patch_queue) == 1,
        "patch_queue_reason_shortcut": patch_queue[0].get("reason") == "shortcut_dominance" if patch_queue else False,
        "single_feature_below_ceiling": strongest_single < float(shortcut.get("ceiling", 0.8) or 0.8),
        "combo_feature_hits_exact": strongest_combo == 1.0,
        "training_blocked_by_shortcut_dominance": shortcut.get("training_blocked_by_shortcut_dominance") is True,
        "repair_requirements_recorded": len(REPAIR_REQUIREMENTS) >= 6,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8962": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 8962,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "FOCUSED_MANIFEST_PATCH_QUEUE_INTERPRETATION",
        "source_stage": 8962,
        "shortcut_summary": {
            "ceiling": shortcut.get("ceiling"),
            "majority_exact": shortcut.get("majority_exact"),
            "strongest_single_feature_exact": strongest_single,
            "strongest_combo_feature_exact": strongest_combo,
            "combo_feature_exact": combo,
        },
        "patch_queue": patch_queue,
        "repair_requirements": REPAIR_REQUIREMENTS,
        "trainability_decision": TRAINABILITY_DECISION,
        "checks": checks,
        "metrics": {
            "patch_queue_rows": len(patch_queue),
            "strongest_single_feature_exact": strongest_single,
            "strongest_combo_feature_exact": strongest_combo,
            "combo_exact_1_0_rows": sum(1 for value in combo.values() if float(value) == 1.0),
            "repair_requirements": len(REPAIR_REQUIREMENTS),
            "manifest_trainable_now": False,
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
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "The focused manifest is useful for audit plumbing but not trainable: two-feature shortcut baselines recover the target exactly. It needs counterbalanced neutral evidence rows before it can support model gradients.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8962, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["manifest_trainable_now", "actual_execution_authorized_next", "model_execution_attempted", "runtime_authorized_flag", "training_authorized", "data_mining_authorized", "decoder_ce_authorized", "denoise_ce_authorized", "arxiv_read_authorized_for_compiler", "arxiv_write_authorized"]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card, registry)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        "artifacts": {"card": str(CARD.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "If continuing this branch, build a no-mining counterbalance design for the focused manifest shortcut pairs. Do not train this manifest.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8963 Focused Manifest Patch Queue Interpretation",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "The focused manifest is useful for audit plumbing but not trainable yet. Single-feature shortcuts are below ceiling, but two-feature combo shortcuts solve the target exactly.",
        "",
        f"Strongest single-feature exact: `{card['metrics']['strongest_single_feature_exact']}`",
        f"Strongest combo-feature exact: `{card['metrics']['strongest_combo_feature_exact']}`",
        f"Manifest trainable now: `{card['metrics']['manifest_trainable_now']}`",
        "",
        "No mining, model execution, decoder CE, denoise CE, runtime, checkpoint export, or training is authorized.",
        "",
    ]), encoding="utf-8")
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
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8963 Focused Manifest Patch Queue Interpretation"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8963 interprets the focused manifest audit patch queue: combo-feature shortcut baselines solve the tiny target exactly, so the manifest is not trainable until counterbalanced neutral evidence rows are designed and audited.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
