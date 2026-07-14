#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10315
NAME = "stage10315_action_reweight_branch_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "action_reweight_branch_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

RUNS = {
    "stage10303": ROOT / "runs/local/artifacts/stage10304_hf_local_support_probe_audit/hf_local_support_probe_audit.json",
    "stage10308": ROOT / "runs/local/artifacts/stage10308_source_backed_action_support_plus_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json",
    "stage10312": ROOT / "runs/local/artifacts/stage10312_action_taking_reweight_frontloaded_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json",
    "stage10314": ROOT / "runs/local/artifacts/stage10314_balanced_frontloaded_action_reweight_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json",
}

EXECUTIONS = {
    "stage10308": ROOT / "runs/local/artifacts/stage10308_source_backed_action_support_plus_probe/bounded_decoder_probe/execution_result.json",
    "stage10312": ROOT / "runs/local/artifacts/stage10312_action_taking_reweight_frontloaded_probe/bounded_decoder_probe/execution_result.json",
    "stage10314": ROOT / "runs/local/artifacts/stage10314_balanced_frontloaded_action_reweight_probe/bounded_decoder_probe/execution_result.json",
}


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def metrics_from_audit(obj: dict[str, Any]) -> dict[str, Any]:
    if "runs" in obj:
        run = obj["runs"]["stage10303"]
        return {
            "strict": run["strict_eval"],
            "by_lang": run["by_lang"],
            "by_perspective": run["by_perspective"],
        }
    row_cards = obj["row_cards"]
    by_lang: dict[str, list[bool]] = {}
    by_perspective: dict[str, list[bool]] = {}
    by_lang_perspective: dict[str, list[bool]] = {}
    correct = 0
    for row in row_cards:
        ok = bool(row["constrained_choice_match"])
        parts = row["row_id"].split("::")
        lang = parts[-4]
        perspective = parts[-3]
        by_lang.setdefault(lang, []).append(ok)
        by_perspective.setdefault(perspective, []).append(ok)
        by_lang_perspective.setdefault(f"{lang}::{perspective}", []).append(ok)
        correct += 1 if ok else 0
    return {
        "strict": {
            "rows": len(row_cards),
            "constrained_choice_top1_accuracy": correct / len(row_cards),
        },
        "by_lang": [
            {"lang": k, "rows": len(v), "correct": sum(v), "accuracy": sum(v) / len(v)}
            for k, v in sorted(by_lang.items())
        ],
        "by_perspective": [
            {"perspective": k, "rows": len(v), "correct": sum(v), "accuracy": sum(v) / len(v)}
            for k, v in sorted(by_perspective.items())
        ],
        "by_lang_perspective": [
            {"key": k, "rows": len(v), "correct": sum(v), "accuracy": sum(v) / len(v)}
            for k, v in sorted(by_lang_perspective.items())
        ],
    }


def build() -> dict[str, Any]:
    stage10303 = metrics_from_audit(load_json(RUNS["stage10303"]))
    stage10308 = metrics_from_audit(load_json(RUNS["stage10308"]))
    stage10312 = metrics_from_audit(load_json(RUNS["stage10312"]))
    stage10314 = metrics_from_audit(load_json(RUNS["stage10314"]))
    exec10308 = load_json(EXECUTIONS["stage10308"])
    exec10312 = load_json(EXECUTIONS["stage10312"])
    exec10314 = load_json(EXECUTIONS["stage10314"])
    branch = {
        "stage10303_baseline": {
            "strict": stage10303["strict"],
            "by_lang": stage10303["by_lang"],
            "by_perspective": stage10303["by_perspective"],
        },
        "stage10308_source_backed_support_plus": {
            "strict": stage10308["strict"],
            "weights_sha256": exec10308["runtime_model_bundle"]["weights_sha256"],
        },
        "stage10312_action_reweight_frontloaded": {
            "strict": exec10312["bounded_choice_eval"]["strict_eval"],
            "strict_loss": exec10312["eval"]["strict_eval"]["loss"],
            "weights_sha256": exec10312["runtime_model_bundle"]["weights_sha256"],
            "by_lang": stage10312["by_lang"],
            "by_perspective": stage10312["by_perspective"],
            "by_lang_perspective": stage10312["by_lang_perspective"],
        },
        "stage10314_balanced_frontloaded_action_reweight": {
            "strict": exec10314["bounded_choice_eval"]["strict_eval"],
            "strict_loss": exec10314["eval"]["strict_eval"]["loss"],
            "weights_sha256": exec10314["runtime_model_bundle"]["weights_sha256"],
            "by_lang": stage10314["by_lang"],
            "by_perspective": stage10314["by_perspective"],
            "by_lang_perspective": stage10314["by_lang_perspective"],
        },
    }
    verdict = {
        "branch_result": "rejected_for_frontier_promotion",
        "why": [
            "Frontloaded action-taking reweight changes the model state but does not improve the weak Python or web action-taking slices.",
            "Both frontloaded variants keep python::{symptom_localization,patch_impact,minimal_fix_selection,verifier_outcome} at 0 accuracy on strict eval.",
            "Both frontloaded variants keep web::{symptom_localization,patch_impact,minimal_fix_selection} at 0 accuracy on strict eval.",
            "Both frontloaded variants collapse c_cpp::evidence_citation from 1.0 to 0.0, reducing macro constrained-choice accuracy versus the stage10303 baseline.",
        ],
        "recommended_pivot": [
            "Stop iterating on simple decoder-ce frontloaded reweighting for these rows.",
            "Next branch should change the supervision structure or representation for action-taking perspectives rather than just duplicating the same bounded-choice rows.",
            "Keep the unchanged strict frontier and anti-cheat gates; mutate only train-side objective/data structure.",
        ],
    }
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "branch_comparison": branch,
        "verdict": verdict,
    }
    write_json(AUDIT_JSON, payload)
    write_json(SUMMARY, {
        "stage": STAGE,
        "passed": True,
        "audit": str(AUDIT_JSON.relative_to(ROOT)),
        "branch_result": verdict["branch_result"],
    })
    return payload


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    payload = build()
    print(json.dumps({
        "stage": STAGE,
        "passed": True,
        "audit": str(AUDIT_JSON.relative_to(ROOT)),
        "branch_result": payload["verdict"]["branch_result"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
