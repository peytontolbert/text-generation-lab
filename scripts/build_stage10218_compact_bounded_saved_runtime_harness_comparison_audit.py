#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10218
NAME = "stage10218_compact_bounded_saved_runtime_harness_comparison_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "compact_bounded_saved_runtime_harness_comparison_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
OLD = ROOT / "runs/local/artifacts/stage10197_compact_bounded_saved_runtime_harness_multilingual_reparsed/first_wave_bundle_inference_summary.json"
NEW = ROOT / "runs/local/artifacts/stage10217_compact_bounded_saved_runtime_harness_multilingual/first_wave_bundle_inference_summary.json"
RUNTIME = ROOT / "runs/local/artifacts/stage10215_python_contrast_counterbalance_probe/runtime_model/runtime_model_bundle.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def by_cell(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = [row for row in summary.get("results") or [] if isinstance(row, dict)]
    return {str(row.get("cell_key") or ""): row for row in rows}


def macro_accuracy(index: dict[str, dict[str, Any]], key: str) -> float:
    vals = [float(((row.get(key) or {}).get("accuracy") or 0.0)) for row in index.values()]
    return sum(vals) / len(vals) if vals else 0.0


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    old_summary = load_json(OLD)
    new_summary = load_json(NEW)
    old_index = by_cell(old_summary)
    new_index = by_cell(new_summary)
    comparison = []
    for cell_key in sorted(set(old_index) | set(new_index)):
        old_row = old_index.get(cell_key, {})
        new_row = new_index.get(cell_key, {})
        comparison.append({
            "cell_key": cell_key,
            "old_100m_accuracy": float(((old_row.get("hundred_m") or {}).get("accuracy") or 0.0)),
            "new_100m_accuracy": float(((new_row.get("hundred_m") or {}).get("accuracy") or 0.0)),
            "delta_100m": float(((new_row.get("hundred_m") or {}).get("accuracy") or 0.0)) - float(((old_row.get("hundred_m") or {}).get("accuracy") or 0.0)),
            "old_gemma_accuracy": float(((old_row.get("gemma12b") or {}).get("accuracy") or 0.0)),
            "new_gemma_accuracy": float(((new_row.get("gemma12b") or {}).get("accuracy") or 0.0)),
            "delta_gemma": float(((new_row.get("gemma12b") or {}).get("accuracy") or 0.0)) - float(((old_row.get("gemma12b") or {}).get("accuracy") or 0.0)),
        })
    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(new_index),
        "old_summary": display(OLD),
        "new_summary": display(NEW),
        "runtime_bundle": display(RUNTIME),
        "claim_scope": "diagnostic compact-bounded harness projection only; compares prior saved-runtime harness replay against current stage10215 saved-runtime harness run",
        "metrics": {
            "old_100m_macro": macro_accuracy(old_index, "hundred_m"),
            "new_100m_macro": macro_accuracy(new_index, "hundred_m"),
            "delta_100m_macro": macro_accuracy(new_index, "hundred_m") - macro_accuracy(old_index, "hundred_m"),
            "old_gemma_macro": macro_accuracy(old_index, "gemma12b"),
            "new_gemma_macro": macro_accuracy(new_index, "gemma12b"),
            "delta_gemma_macro": macro_accuracy(new_index, "gemma12b") - macro_accuracy(old_index, "gemma12b"),
        },
        "per_cell": comparison,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps({"stage": STAGE, "passed": audit["passed"], "artifact": display(AUDIT), "metrics": audit["metrics"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "artifact": display(AUDIT), "metrics": audit["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
