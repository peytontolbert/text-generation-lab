#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10278_frontier_runtime_bundle_probe/runtime_model/runtime_model_bundle.json"

PROJECTION_SOURCE = ROOT / "runs/local/artifacts/stage10236_context_pack_python_replenishment_bundle/context_pack_python_replenishment_admitted_manifest.json"
PROJECTION_OUT_DIR = ROOT / "runs/local/artifacts/stage10279_frontier_saved_runtime_projection_payload"
PROJECTION_PAYLOAD = PROJECTION_OUT_DIR / "frontier_saved_runtime_projection_payload.json"
PROJECTION_SUMMARY = ROOT / "runs/summaries/stage10279_frontier_saved_runtime_projection_payload.json"

HARNESS_OUT_DIR = ROOT / "runs/local/artifacts/stage10280_frontier_saved_runtime_harness_payload"
HARNESS_PAYLOAD = HARNESS_OUT_DIR / "frontier_saved_runtime_harness_payload.json"
HARNESS_SUMMARY = ROOT / "runs/summaries/stage10280_frontier_saved_runtime_harness_payload.json"
HANDOFF_BUNDLE = ROOT / "runs/local/artifacts/stage10081_canonical_harness_backend_handoff_bundle/canonical_harness_backend_handoff_bundle.json"

CELL_KEY_BY_LANGUAGE = {
    "python": "full_product_harness::python::edit_localization",
    "rust": "full_product_harness::rust::edit_localization",
    "c_cpp": "full_product_harness::c_cpp::edit_localization",
    "web_js_ts_html": "full_product_harness::web_js_ts_html::edit_localization",
}


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_projection_payload() -> dict[str, Any]:
    projection = _load_module(
        "stage10279_stage10143_projection",
        ROOT / "scripts" / "build_stage10143_compact_bounded_bundle_projection.py",
    )
    payload = projection.build_payload(PROJECTION_SOURCE)
    runs = []
    for run in payload.get("runs") or []:
        if not isinstance(run, dict):
            continue
        updated = dict(run)
        updated["hundred_m_backend"] = {
            "kind": "preserved_bounded_choice_scoring",
            "runtime_model_bundle": str(RUNTIME_BUNDLE),
            "bounded_choice_aux_source": "encoder_option_retrieval",
            "max_encoder_tokens": 768,
            "device": "cuda",
        }
        updated["gemma_backend"] = {
            "kind": "ollama_generate",
            "model": "gemma3:12b",
            "seed": 0,
            "temperature": 0.0,
            "num_predict": 8,
            "timeout_seconds": 120,
        }
        runs.append(updated)
    return {
        "stage": 10279,
        "stage_name": "stage10279_frontier_saved_runtime_projection_payload",
        "created_at_utc": now_utc(),
        "passed": bool(runs) and RUNTIME_BUNDLE.exists(),
        "source": projection.display(PROJECTION_SOURCE),
        "claim_scope": "adjudicated compact-bounded maintainer projection only; current frontier-equivalent saved runtime bundle scored against live gemma3:12b",
        "eval_hardening": {
            "adjudicated_bundles_only": True,
            "projection_only": True,
            "saved_runtime_backend": True,
            "same_task_pack_as_gemma": True,
            "skip_writeback_expected": True,
        },
        "runtime_bundle": display(RUNTIME_BUNDLE),
        "runs": runs,
        "metrics": {
            "runs": len(runs),
            "rows": sum(len(((run.get("task_pack") or {}).get("rows") or [])) for run in runs),
            "rows_by_language": {
                language: sum(
                    len(((run.get("task_pack") or {}).get("rows") or []))
                    for run in runs
                    if str(((run.get("task_pack") or {}).get("language_family")) or "") == language
                )
                for language in sorted(
                    {str(((run.get("task_pack") or {}).get("language_family")) or "") for run in runs}
                )
            },
        },
    }


def build_harness_payload() -> dict[str, Any]:
    source = load_json(PROJECTION_PAYLOAD)
    handoff = load_json(HANDOFF_BUNDLE)
    handoff_cells = {
        str(cell.get("cell_key") or ""): cell
        for cell in handoff.get("handoff_cells") or []
        if isinstance(cell, dict)
    }
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
        handoff_cell = handoff_cells.get(cell_key) or {}
        row_counts[language] = len(rows)
        bundle_ids = sorted(set(bundle_ids_by_language.get(language) or []))
        runs.append(
            {
                "cell_key": cell_key,
                "task_pack": {
                    "bundle_id": f"stage10279_saved_runtime_compact_bounded::{language}",
                    "task_pack_id": str(handoff_cell.get("task_pack_id") or ""),
                    "source_id": str(handoff_cell.get("source_id") or ""),
                    "lineage_hash": str(handoff_cell.get("lineage_hash") or ""),
                    "split_role": "locked_regression",
                    "train_eligible": False,
                    "promotion_only": True,
                    "hidden_final": False,
                    "language_family": str(handoff_cell.get("language_family") or language),
                    "skill_area": str(handoff_cell.get("skill_area") or "edit_localization"),
                    "slice_tags": [
                        "maintainer_bundle",
                        language,
                        "compact_bounded",
                        "saved_runtime",
                        "diagnostic_harness",
                        "frontier_runtime",
                    ],
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
        "stage": 10280,
        "stage_name": "stage10280_frontier_saved_runtime_harness_payload",
        "created_at_utc": now_utc(),
        "passed": bool(runs) and RUNTIME_BUNDLE.exists(),
        "source_payload": display(PROJECTION_PAYLOAD),
        "runtime_bundle": display(RUNTIME_BUNDLE),
        "handoff_bundle": display(HANDOFF_BUNDLE),
        "claim_scope": "diagnostic compact bounded maintainer projection only; current frontier-equivalent saved runtime bundle grouped by language for the harness packet path against live gemma3:12b",
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
    PROJECTION_OUT_DIR.mkdir(parents=True, exist_ok=True)
    HARNESS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTION_SUMMARY.parent.mkdir(parents=True, exist_ok=True)

    projection_payload = build_projection_payload()
    PROJECTION_PAYLOAD.write_text(json.dumps(projection_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    PROJECTION_SUMMARY.write_text(
        json.dumps(
            {
                "stage": 10279,
                "passed": projection_payload["passed"],
                "artifact": display(PROJECTION_PAYLOAD),
                "metrics": projection_payload["metrics"],
                "runtime_bundle": display(RUNTIME_BUNDLE),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    harness_payload = build_harness_payload()
    HARNESS_PAYLOAD.write_text(json.dumps(harness_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    HARNESS_SUMMARY.write_text(
        json.dumps(
            {
                "stage": 10280,
                "passed": harness_payload["passed"],
                "artifact": display(HARNESS_PAYLOAD),
                "metrics": harness_payload["metrics"],
                "runtime_bundle": display(RUNTIME_BUNDLE),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "projection_stage": 10279,
                "projection_artifact": display(PROJECTION_PAYLOAD),
                "harness_stage": 10280,
                "harness_artifact": display(HARNESS_PAYLOAD),
                "runtime_bundle_exists": RUNTIME_BUNDLE.exists(),
            },
            indent=2,
            sort_keys=True,
        )
    )

    if not projection_payload["passed"] or not harness_payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
