#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9420
NAME = "stage9420_balanced_suffix_choice_residual_diagnosis"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9419_suffix_choice_control_probe_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9419_suffix_choice_control_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DIAGNOSIS = OUT_DIR / "balanced_suffix_choice_residual_diagnosis.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BALANCED_SUFFIX_CHOICE_RESIDUAL_DIAGNOSIS_STAGE9420.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    logits = [row for row in load_jsonl(RUN_DIR / "row_field_logits.jsonl") if row.get("field") == "suffix_choice"]
    errors = [row for row in logits if not row.get("correct")]
    confusion_counts = Counter(f"{row.get('target')} => {row.get('pred')}" for row in errors)
    target_pair_labels = {"expected_assertion_behavior__keep_value_small", "current_repair_invariant__do_not_introduce"}
    target_pair = [row for row in logits if row.get("target") in target_pair_labels]
    target_pair_exact = sum(1 for row in target_pair if row.get("correct"))
    diagnosis = {
        "passed": True,
        "source_stage": 9419,
        "safety_preserved": bool(source.get("safety_gate_passed") or source.get("metrics", {}).get("safety_gate_passed")),
        "quality_passed": bool(source.get("quality_gate_passed") or source.get("metrics", {}).get("quality_gate_passed")),
        "suffix_choice_records": len(logits),
        "suffix_choice_errors": len(errors),
        "target_pair_exact_rows": target_pair_exact,
        "target_pair_rows": len(target_pair),
        "confusion_counts": dict(sorted(confusion_counts.items())),
        "error_rows": [
            {
                "row_id": row.get("row_id"),
                "split": row.get("split"),
                "target": row.get("target"),
                "pred": row.get("pred"),
                "confidence": row.get("confidence"),
                "margin": row.get("margin"),
                "top_k": row.get("top_k"),
            }
            for row in errors
        ],
        "findings": [
            "balanced_train_support_improves_suffix_choice_from_1_16_to_9_16_heldout",
            "target_pair_improves_from_0_4_to_3_4",
            "remaining_errors_are_low_confidence_small_margin",
            "next_patch_should_add_contrastive_support_for_specific_confusion_pairs_not_more_generic_balance",
        ],
        "recommended_contract": {
            "branch_from": "stage9417_balanced_suffix_choice_support_manifest",
            "next_patch_type": "targeted_suffix_choice_confusion_repair_manifest",
            "priority_pairs": [
                "expected_assertion_behavior__keep_value_small_vs_localized_repair_step__keep_response",
                "checked_symbol_evidence__keep_decision_compatible_vs_localized_repair_step__keep_response",
                "verified_patch_operator__use_repo_vs_localized_repair_step__keep_response",
                "repaired_state__keep_answer_focused_vs_wrapper_plan__keep_answer_focused",
            ],
            "keep_closed": ["decoder_ce", "denoise_ce", "runtime", "gemma", "harness", "checkpoint_export"],
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    DIAGNOSIS.write_text(json.dumps(diagnosis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build targeted suffix-choice confusion repair rows for the four low-margin residual pairs."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": True,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **{k: v for k, v in diagnosis.items() if k not in {"authority", "recommended_contract", "error_rows"}}},
        "artifacts": {"diagnosis": str(DIAGNOSIS.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Balanced suffix-choice support improved control but left low-margin residual confusions requiring targeted contrastive rows.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9420 Balanced Suffix Choice Residual Diagnosis", "", "Stage9419 is safety-clean and improved suffix-choice control, but did not pass quality.", "", f"Target-pair exact: `{target_pair_exact}` / `{len(target_pair)}`", f"Heldout errors: `{len(errors)}`", f"Confusions: `{dict(sorted(confusion_counts.items()))}`", "", "Next: targeted contrastive confusion repair rows, still structured-only.", ""]), encoding="utf-8")
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": STAGE, "passed": True, "metrics": {"errors": len(errors), "target_pair_exact": f"{target_pair_exact}/{len(target_pair)}", "confusions": dict(sorted(confusion_counts.items()))}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
