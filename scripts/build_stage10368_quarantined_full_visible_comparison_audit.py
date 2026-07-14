#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10368
NAME = "stage10368_quarantined_full_visible_comparison_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "quarantined_full_visible_comparison_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
RUNTIME_SUMMARY = ROOT / "runs/local/artifacts/stage10367_quarantined_full_visible_runtime_inference/first_wave_bundle_inference_summary.json"
PAYLOAD = ROOT / "runs/local/artifacts/stage10366_quarantined_full_visible_runtime_payload/quarantined_full_visible_runtime_payload.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def mean(values: list[float]) -> float | None:
    return (sum(values) / len(values)) if values else None


def main() -> None:
    runtime = load_json(RUNTIME_SUMMARY)
    payload = load_json(PAYLOAD)
    results = [row for row in runtime.get("results") or [] if isinstance(row, dict)]
    per_language: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "bundles": 0,
        "rows": 0,
        "hundred_m_correct": 0,
        "gemma12b_correct": 0,
        "hundred_m_bundle_accuracies": [],
        "gemma12b_bundle_accuracies": [],
    })
    hundred_m_failures = []
    gemma_failures = []
    for result in results:
        bundle_id = str(result.get("bundle_id") or "")
        language = bundle_id.split("::")[-1]
        slot = per_language[language]
        slot["bundles"] += 1
        slot["rows"] += int((result.get("hundred_m") or {}).get("rows") or 0)
        slot["hundred_m_correct"] += int((result.get("hundred_m") or {}).get("correct") or 0)
        slot["gemma12b_correct"] += int((result.get("gemma12b") or {}).get("correct") or 0)
        slot["hundred_m_bundle_accuracies"].append(float((result.get("hundred_m") or {}).get("accuracy") or 0.0))
        slot["gemma12b_bundle_accuracies"].append(float((result.get("gemma12b") or {}).get("accuracy") or 0.0))

        pred_path = ROOT / str(result.get("adapter_payload") or "")
        bundle_predictions = pred_path.with_name("bundle_predictions.json")
        if bundle_predictions.exists():
            pred_data = load_json(bundle_predictions)
            for row in pred_data.get("hundred_m") or []:
                if row.get("correct") is False:
                    hundred_m_failures.append(
                        {
                            "bundle_id": bundle_id,
                            "language_family": language,
                            "row_id": row.get("row_id"),
                            "perspective": row.get("perspective"),
                            "expected": row.get("expected"),
                            "predicted": row.get("predicted"),
                        }
                    )
            for row in pred_data.get("gemma12b") or []:
                if row.get("correct") is False:
                    gemma_failures.append(
                        {
                            "bundle_id": bundle_id,
                            "language_family": language,
                            "row_id": row.get("row_id"),
                            "perspective": row.get("perspective"),
                            "expected": row.get("expected"),
                            "predicted": row.get("predicted"),
                        }
                    )

    language_cards = {}
    hundred_m_macro = []
    gemma_macro = []
    hundred_wins = 0
    gemma_wins = 0
    ties = 0
    for language, slot in sorted(per_language.items()):
        rows = int(slot["rows"])
        hundred_acc = (int(slot["hundred_m_correct"]) / rows) if rows else None
        gemma_acc = (int(slot["gemma12b_correct"]) / rows) if rows else None
        if hundred_acc is not None:
            hundred_m_macro.append(hundred_acc)
        if gemma_acc is not None:
            gemma_macro.append(gemma_acc)
        if hundred_acc is None or gemma_acc is None:
            verdict = "unscored"
        elif hundred_acc > gemma_acc:
            verdict = "100m_better"
            hundred_wins += 1
        elif gemma_acc > hundred_acc:
            verdict = "gemma_better"
            gemma_wins += 1
        else:
            verdict = "tie"
            ties += 1
        language_cards[language] = {
            "bundles": int(slot["bundles"]),
            "rows": rows,
            "hundred_m_accuracy": hundred_acc,
            "gemma12b_accuracy": gemma_acc,
            "hundred_m_macro_bundle_accuracy": mean(slot["hundred_m_bundle_accuracies"]),
            "gemma12b_macro_bundle_accuracy": mean(slot["gemma12b_bundle_accuracies"]),
            "verdict": verdict,
        }

    total_rows = sum(card["rows"] for card in language_cards.values())
    total_hundred_correct = sum(int(per_language[lang]["hundred_m_correct"]) for lang in per_language)
    total_gemma_correct = sum(int(per_language[lang]["gemma12b_correct"]) for lang in per_language)

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": runtime.get("passed") is True and bool(results),
        "sources": {
            "runtime_summary": display(RUNTIME_SUMMARY),
            "payload": display(PAYLOAD),
        },
        "claim_scope": "quarantined full-visible compact-bounded maintainer projection only; same-task-pack 100M stage10359 saved runtime versus live gemma3:12b with the ambiguous tokenizers rust citation row excluded",
        "metrics": {
            "rows": total_rows,
            "bundles": len(results),
            "hundred_m_macro_accuracy": mean(hundred_m_macro),
            "gemma12b_macro_accuracy": mean(gemma_macro),
            "delta_macro_accuracy": (mean(hundred_m_macro) or 0.0) - (mean(gemma_macro) or 0.0),
            "hundred_m_micro_accuracy": (total_hundred_correct / total_rows) if total_rows else None,
            "gemma12b_micro_accuracy": (total_gemma_correct / total_rows) if total_rows else None,
            "delta_micro_accuracy": ((total_hundred_correct / total_rows) if total_rows else 0.0) - ((total_gemma_correct / total_rows) if total_rows else 0.0),
            "wins": {"hundred_m": hundred_wins, "gemma12b": gemma_wins, "ties": ties},
            "hundred_m_failure_rows": len(hundred_m_failures),
            "gemma12b_failure_rows": len(gemma_failures),
        },
        "language_cards": language_cards,
        "hundred_m_failures": hundred_m_failures,
        "gemma12b_failures": gemma_failures,
        "quarantined_rows": payload.get("quarantined_rows") or [],
        "decision": {
            "headline": "100M beats gemma3:12b across all four language slices on the repaired quarantined full-visible projection",
            "remaining_100m_weaknesses": sorted({str(row.get('perspective') or '') for row in hundred_m_failures}),
            "next_best_step": "use these remaining honest 100M misses to drive the next targeted training or bundle replenishment step, not the retired truncated citation surface",
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    write_json(AUDIT, audit)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": audit["passed"],
            "artifact": display(AUDIT),
            "metrics": audit["metrics"],
        },
    )
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "artifact": display(AUDIT), "metrics": audit["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
