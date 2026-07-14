#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10244
NAME = "stage10244_compact_bounded_saved_runtime_harness_payload_successor"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PAYLOAD = OUT_DIR / "compact_bounded_saved_runtime_harness_payload_successor.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
SOURCE = ROOT / "runs/local/artifacts/stage10240_admitted_projection_runtime_payload_successor/admitted_projection_runtime_payload_successor.json"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10224_bundle_coherence_counterbalance_probe/runtime_model/runtime_model_bundle.json"
CELL_KEY_BY_LANGUAGE = {
    "python": "full_product_harness::python::edit_localization",
    "rust": "full_product_harness::rust::edit_localization",
    "c_cpp": "full_product_harness::c_cpp::edit_localization",
    "web_js_ts_html": "full_product_harness::web_js_ts_html::edit_localization",
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


def build_payload() -> dict[str, Any]:
    source = load_json(SOURCE)
    source_runs = [row for row in source.get("runs") or [] if isinstance(row, dict)]
    grouped: dict[str, list[dict[str, Any]]] = {}
    bundle_ids_by_language: dict[str, list[str]] = {}
    for run in source_runs:
        task_pack = run.get("task_pack") if isinstance(run.get("task_pack"), dict) else {}
        language = str(task_pack.get("language_family") or "")
        if language not in CELL_KEY_BY_LANGUAGE:
            continue
        rows = [row for row in task_pack.get("rows") or [] if isinstance(row, dict)]
        grouped.setdefault(language, []).extend(rows)
        bundle_id = str(task_pack.get("bundle_id") or "")
        if bundle_id:
            bundle_ids_by_language.setdefault(language, []).append(bundle_id)
    runs = []
    row_counts: dict[str, int] = {}
    for language, cell_key in CELL_KEY_BY_LANGUAGE.items():
        rows = grouped.get(language) or []
        if not rows:
            continue
        row_counts[language] = len(rows)
        bundle_ids = sorted(set(bundle_ids_by_language.get(language) or []))
        runs.append(
            {
                "cell_key": cell_key,
                "task_pack": {
                    "bundle_id": f"stage10240_saved_runtime_compact_bounded::{language}",
                    "task_pack_id": f"stage10240_saved_runtime_compact_bounded::{language}",
                    "source_id": f"stage10240_saved_runtime_compact_bounded::{language}",
                    "lineage_hash": f"stage10240_saved_runtime_compact_bounded::{language}",
                    "split_role": "locked_regression",
                    "train_eligible": False,
                    "promotion_only": True,
                    "hidden_final": False,
                    "language_family": language,
                    "skill_area": "edit_localization",
                    "slice_tags": ["maintainer_bundle", language, "compact_bounded", "saved_runtime", "diagnostic_harness", "stage10240_refresh"],
                    "thresholds": {"must_compare_100m_and_gemma": True, "projection_only": True},
                    "blocked_training_reason": "saved_runtime_bounded_choice_diagnostic_only",
                    "rows": rows,
                    "maintainer_bundle_mode": True,
                    "projection_mode": "compact_bounded_choice_auxiliary",
                    "bundle_ids": bundle_ids,
                },
                "hundred_m_backend": {
                    "kind": "preserved_bounded_choice_scoring",
                    "runtime_model_bundle": str(RUNTIME_BUNDLE),
                    "bounded_choice_aux_source": "encoder_option_retrieval",
                    "max_encoder_tokens": 768,
                    "device": "cuda",
                },
                "gemma_backend": {
                    "kind": "ollama_generate",
                    "model": "gemma3:12b",
                    "seed": 0,
                    "temperature": 0.0,
                    "num_predict": 8,
                    "timeout_seconds": 120,
                },
            }
        )
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(runs),
        "source_payload": display(SOURCE),
        "runtime_bundle": display(RUNTIME_BUNDLE),
        "claim_scope": "diagnostic compact bounded maintainer projection only; refreshed admitted-manifest successor grouped by language for the full-product harness packet path using the stage10224 saved runtime backend",
        "eval_hardening": {
            "primary_maintainer_leaderboard_allowed": False,
            "projection_only": True,
            "same_task_pack_as_gemma": True,
            "saved_runtime_backend": True,
            "writes_reserved_harness_packet_paths": True,
        },
        "metrics": {
            "runs": len(runs),
            "rows": sum(row_counts.values()),
            "row_counts_by_language": row_counts,
        },
        "runs": runs,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    PAYLOAD.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps({"stage": STAGE, "passed": payload["passed"], "artifact": display(PAYLOAD), "metrics": payload["metrics"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": STAGE, "passed": payload["passed"], "artifact": display(PAYLOAD), "metrics": payload["metrics"]}, indent=2, sort_keys=True))
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
