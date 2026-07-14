#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10186
NAME = "stage10186_hybrid_web_surface_rebalanced_probe_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "hybrid_web_surface_rebalanced_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

RUNS = {
    "stage10181": ROOT / "runs/local/artifacts/stage10181_augmented_web_scaled_step_target100m_probe/bounded_decoder_probe",
    "stage10185": ROOT / "runs/local/artifacts/stage10185_hybrid_web_surface_rebalanced_target100m_probe/bounded_decoder_probe",
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


def run_finished(base: Path) -> bool:
    return (base / "execution_result.json").exists() and (base / "bounded_choice_eval_audit_strict_eval.json").exists()


def run_card(name: str, base: Path) -> dict[str, Any]:
    finished = run_finished(base)
    card: dict[str, Any] = {
        "run": name,
        "path": display(base),
        "finished": finished,
    }
    if not finished:
        return card
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
    card.update(
        {
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
    )
    return card


def accuracy(card: dict[str, Any], language: str) -> float:
    return float((card.get("per_language") or {}).get(language, {}).get("accuracy") or 0.0)


def task_accuracy(card: dict[str, Any], task: str) -> float:
    return float((card.get("web_task_breakdown") or {}).get(task, {}).get("accuracy") or 0.0)


def build_report() -> dict[str, Any]:
    cards = {name: run_card(name, path) for name, path in RUNS.items()}
    if not cards["stage10185"]["finished"]:
        return {
            "stage": STAGE,
            "stage_name": NAME,
            "created_at_utc": now_utc(),
            "passed": False,
            "runs": cards,
            "blocked_reason": "stage10185_not_finished",
        }
    base = cards["stage10181"]
    new = cards["stage10185"]
    verdict = {
        "baseline_stage": "stage10181",
        "candidate_stage": "stage10185",
        "overall_accuracy_delta": float(new["constrained_choice_top1_accuracy"]) - float(base["constrained_choice_top1_accuracy"]),
        "python_accuracy_delta": accuracy(new, "python") - accuracy(base, "python"),
        "rust_accuracy_delta": accuracy(new, "rust") - accuracy(base, "rust"),
        "c_cpp_accuracy_delta": accuracy(new, "c_cpp") - accuracy(base, "c_cpp"),
        "web_accuracy_delta": accuracy(new, "web_js_ts_html") - accuracy(base, "web_js_ts_html"),
        "web_symptom_delta": task_accuracy(new, "symptom_localization") - task_accuracy(base, "symptom_localization"),
        "web_patch_delta": task_accuracy(new, "patch_impact") - task_accuracy(base, "patch_impact"),
        "web_minimal_fix_delta": task_accuracy(new, "minimal_fix_selection") - task_accuracy(base, "minimal_fix_selection"),
        "web_evidence_delta": task_accuracy(new, "evidence_citation") - task_accuracy(base, "evidence_citation"),
        "headline": (
            "Stage10185 tests whether narrowing code_assist to verifier/abstention and duplicating the frontend bddy web surface-selection tasks can "
            "recover held-out web symptom/patch/minimal-fix behavior without giving back the stage10181 multilingual gains."
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
                "passed": report["passed"],
                "artifact": display(AUDIT),
                "blocked_reason": report.get("blocked_reason"),
                "verdict": report.get("verdict"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"stage": STAGE, "passed": report["passed"], "artifact": display(AUDIT), "blocked_reason": report.get("blocked_reason")}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
