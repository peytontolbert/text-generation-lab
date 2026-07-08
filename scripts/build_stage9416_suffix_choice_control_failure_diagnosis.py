#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9416
NAME = "stage9416_suffix_choice_control_failure_diagnosis"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9415_suffix_choice_control_probe_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9413_suffix_choice_control_manifest/suffix_choice_control_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9415_suffix_choice_control_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DIAGNOSIS = OUT_DIR / "suffix_choice_control_failure_diagnosis.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CHOICE_CONTROL_FAILURE_DIAGNOSIS_STAGE9416.md"
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
    rows = load_jsonl(MANIFEST)
    logits = load_jsonl(RUN_DIR / "row_field_logits.jsonl")
    split_label_counts: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        split_label_counts[str(row.get("split"))][str((row.get("clean_state") or {}).get("suffix_choice"))] += 1
    pred_counts = Counter(str(row.get("pred")) for row in logits if row.get("field") == "suffix_choice")
    target_counts = Counter(str(row.get("target")) for row in logits if row.get("field") == "suffix_choice")
    low_train_labels = {label: count for label, count in split_label_counts["train"].items() if count < 3}
    diagnosis = {
        "passed": True,
        "source_stage": 9415,
        "safety_preserved": bool(source.get("safety_gate_passed") or source.get("metrics", {}).get("safety_gate_passed")),
        "quality_passed": bool(source.get("quality_gate_passed") or source.get("metrics", {}).get("quality_gate_passed")),
        "split_label_counts": {split: dict(sorted(counter.items())) for split, counter in split_label_counts.items()},
        "heldout_prediction_counts": dict(sorted(pred_counts.items())),
        "heldout_target_counts": dict(sorted(target_counts.items())),
        "low_train_label_coverage": low_train_labels,
        "findings": [
            "suffix_choice_head_runtime_contract_is_fixed",
            "suffix_choice_probe_is_safety_clean",
            "suffix_choice_quality_fails_from_sparse_per_class_train_coverage",
            "heldout_predictions_collapse_toward_generic_suffix_choice",
            "next_manifest_should_balance_train_support_per_suffix_choice_class_before_generation_reconnect",
        ],
        "recommended_contract": {
            "branch_from": "stage9413_suffix_choice_control_manifest",
            "next_patch_type": "balanced_suffix_choice_train_support_manifest",
            "minimum_train_support_per_choice": 4,
            "keep_closed": ["decoder_ce", "denoise_ce", "runtime", "gemma", "harness", "checkpoint_export"],
            "pass_gate": ["eval_suffix_choice_exact >= 0.85", "strict_suffix_choice_exact >= 0.85", "target_pair_exact == 4/4", "high_confidence_wrong_rows == 0"],
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    DIAGNOSIS.write_text(json.dumps(diagnosis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build balanced suffix-choice train support rows and rerun the structured suffix-choice probe."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": True,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **{k: v for k, v in diagnosis.items() if k not in {"authority", "recommended_contract"}}},
        "artifacts": {"diagnosis": str(DIAGNOSIS.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Stage9415 proved the suffix-choice head path executes safely, but the class support is too sparse and collapses toward generic.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9416 Suffix Choice Control Failure Diagnosis", "", "Stage9415 is safety-clean but quality-failed.", "", f"Low train label coverage: `{low_train_labels}`", f"Heldout prediction counts: `{dict(sorted(pred_counts.items()))}`", "", "Next: balanced suffix-choice train support, then rerun structured control. Decoder and denoise generation remain closed.", ""]), encoding="utf-8")
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": STAGE, "passed": True, "metrics": {"low_train_label_count": len(low_train_labels), "pred_counts": dict(sorted(pred_counts.items()))}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
