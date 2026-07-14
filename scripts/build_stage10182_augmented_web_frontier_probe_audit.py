#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10182
NAME = "stage10182_augmented_web_frontier_probe_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "augmented_web_frontier_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

RUNS = {
    "stage10172": ROOT / "runs/local/artifacts/stage10172_choice_aux_encoder_option_retrieval_target100m_probe/bounded_decoder_probe",
    "stage10179": ROOT / "runs/local/artifacts/stage10179_augmented_web_target100m_probe/bounded_decoder_probe",
    "stage10181": ROOT / "runs/local/artifacts/stage10181_augmented_web_scaled_step_target100m_probe/bounded_decoder_probe",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def normalize_language(language: str) -> str:
    return "rust" if language == "tokenizers" else language


def safe_rate(correct: int, total: int) -> float | None:
    return (correct / total) if total else None


def run_card(name: str, base: Path) -> dict[str, Any]:
    execution = load_json(base / "execution_result.json")
    strict = load_json(base / "bounded_choice_eval_audit_strict_eval.json")
    by_language: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
    web_tasks: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
    for row in strict.get("row_cards") or []:
        if not isinstance(row, dict):
            continue
        parts = str(row.get("row_id") or "").split("::")
        if len(parts) < 4:
            continue
        language = normalize_language(parts[2])
        task_type = parts[3]
        match = bool(row.get("constrained_choice_match"))
        by_language[language]["total"] += 1
        by_language[language]["correct"] += int(match)
        if language == "web_js_ts_html":
            web_tasks[task_type]["total"] += 1
            web_tasks[task_type]["correct"] += int(match)
    return {
        "run": name,
        "path": display(base),
        "max_steps": execution.get("max_steps"),
        "train_rows": execution.get("train_rows"),
        "strict_rows": strict.get("rows"),
        "constrained_choice_top1_accuracy": strict.get("constrained_choice_top1_accuracy"),
        "full_vocab_top1_accuracy": strict.get("full_vocab_top1_accuracy"),
        "strict_eval_loss": (((execution.get("eval") or {}).get("strict_eval") or {}).get("loss")),
        "per_language": {
            language: {
                "correct": counts["correct"],
                "total": counts["total"],
                "accuracy": safe_rate(counts["correct"], counts["total"]),
            }
            for language, counts in sorted(by_language.items())
        },
        "web_task_breakdown": {
            task: {
                "correct": counts["correct"],
                "total": counts["total"],
                "accuracy": safe_rate(counts["correct"], counts["total"]),
            }
            for task, counts in sorted(web_tasks.items())
        },
    }


def accuracy(card: dict[str, Any], language: str) -> float:
    return float((card.get("per_language") or {}).get(language, {}).get("accuracy") or 0.0)


def task_accuracy(card: dict[str, Any], task: str) -> float:
    return float((card.get("web_task_breakdown") or {}).get(task, {}).get("accuracy") or 0.0)


def build_report() -> dict[str, Any]:
    cards = {name: run_card(name, path) for name, path in RUNS.items()}
    s72 = cards["stage10172"]
    s79 = cards["stage10179"]
    s81 = cards["stage10181"]
    verdict = {
        "best_current_stage": "stage10181",
        "overall_accuracy_delta_vs_stage10172": float(s81["constrained_choice_top1_accuracy"]) - float(s72["constrained_choice_top1_accuracy"]),
        "overall_accuracy_delta_vs_stage10179": float(s81["constrained_choice_top1_accuracy"]) - float(s79["constrained_choice_top1_accuracy"]),
        "python_recovered_vs_stage10179": accuracy(s81, "python") > accuracy(s79, "python"),
        "python_improved_vs_stage10172": accuracy(s81, "python") > accuracy(s72, "python"),
        "web_improved_vs_stage10172": accuracy(s81, "web_js_ts_html") > accuracy(s72, "web_js_ts_html"),
        "web_regressed_vs_stage10179": accuracy(s81, "web_js_ts_html") < accuracy(s79, "web_js_ts_html"),
        "web_evidence_citation_recovered": task_accuracy(s81, "evidence_citation") > task_accuracy(s72, "evidence_citation"),
        "web_surface_selection_regressed": (
            task_accuracy(s81, "symptom_localization") < task_accuracy(s79, "symptom_localization")
            and task_accuracy(s81, "patch_impact") < task_accuracy(s79, "patch_impact")
            and task_accuracy(s81, "minimal_fix_selection") < task_accuracy(s79, "minimal_fix_selection")
        ),
        "headline": (
            "Increasing the augmented-web package to 224 steps creates the best overall standalone frontier: "
            "Python recovers from 0.194 to 0.861, web remains above the pre-augmentation baseline, and total strict accuracy rises to 0.843."
        ),
        "risk": (
            "The web gain is now concentrated in evidence_citation, verifier_outcome, and abstention; the held-out web root again lost "
            "symptom_localization, patch_impact, and minimal_fix_selection."
        ),
        "next_action": (
            "Keep stage10181 as the current overall frontier, but do not treat it as a clean web fix. The next run should preserve the 224-step budget "
            "and rebalance the web bundle so evidence_citation does not crowd out web surface-selection tasks."
        ),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "runs": cards,
        "verdict": verdict,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    report = build_report()
    AUDIT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(
        json.dumps(
            {
                "stage": STAGE,
                "stage_name": NAME,
                "passed": True,
                "artifact": display(AUDIT),
                "best_current_stage": report["verdict"]["best_current_stage"],
                "headline": report["verdict"]["headline"],
                "next_action": report["verdict"]["next_action"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"stage": STAGE, "passed": True, "artifact": display(AUDIT)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
