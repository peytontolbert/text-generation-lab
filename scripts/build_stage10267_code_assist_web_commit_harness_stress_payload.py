#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10267
NAME = "stage10267_code_assist_web_commit_harness_stress_payload"
SOURCE = ROOT / "runs/local/artifacts/stage10266_code_assist_web_commit_compact_support_package/code_assist_web_commit_admitted_manifest.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PAYLOAD = OUT_DIR / "code_assist_web_commit_harness_stress_payload.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10224_bundle_coherence_counterbalance_probe/runtime_model/runtime_model_bundle.json"


def _load_module(module_name: str, script_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


PROJECTION = _load_module(
    "stage10267_stage10143_projection",
    ROOT / "scripts" / "build_stage10143_compact_bounded_bundle_projection.py",
)


def main() -> None:
    projection = PROJECTION.build_payload(SOURCE)
    rows = []
    bundle_ids: list[str] = []
    gold_paths: list[str] = []
    excluded_rows: list[str] = []
    for run in projection.get("runs") or []:
        if not isinstance(run, dict):
            continue
        task_pack = run.get("task_pack") if isinstance(run.get("task_pack"), dict) else {}
        language = str(task_pack.get("language_family") or "")
        if language != "web_js_ts_html":
            continue
        bundle_id = str(task_pack.get("bundle_id") or "")
        if bundle_id and bundle_id not in bundle_ids:
            bundle_ids.append(bundle_id)
        gold_path = str(task_pack.get("gold_answers_path") or "")
        if gold_path and gold_path not in gold_paths:
            gold_paths.append(gold_path)
        for row in task_pack.get("rows") or []:
            if not isinstance(row, dict):
                continue
            option_count = len(row.get("opaque_options") or [])
            if option_count < 2:
                excluded_rows.append(f"{row.get('row_id')}::degenerate_option_count_{option_count}")
                continue
            rows.append(row)
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": PROJECTION.now_utc(),
        "source": PROJECTION.display(SOURCE),
        "runtime_bundle": PROJECTION.display(RUNTIME_BUNDLE),
        "passed": bool(rows),
        "claim_scope": "repo-overlap web stress eval only; adjudicated compact-bounded code_assist commit bundles compared on the same task pack for saved-runtime 100M versus live gemma3:12b",
        "eval_hardening": {
            "primary_maintainer_leaderboard_allowed": False,
            "projection_only": True,
            "repo_overlap_non_headline": True,
            "same_task_pack_as_gemma": True,
            "saved_runtime_backend": True,
            "skip_writeback_expected": True,
            "source_heldout_claim_allowed": False,
            "single_option_rows_excluded": True,
        },
        "metrics": {
            "runs": 1 if rows else 0,
            "rows": len(rows),
            "bundle_count": len(bundle_ids),
            "rows_by_language": {"web_js_ts_html": len(rows)} if rows else {},
            "excluded_rows": len(excluded_rows),
        },
        "excluded_rows": excluded_rows,
        "runs": [
            {
                "cell_key": "full_product_harness::web_js_ts_html::edit_localization",
                "task_pack": {
                    "bundle_id": "stage10267::code_assist_web_commit_repo_overlap::web_js_ts_html",
                    "task_pack_id": "stage10267::code_assist_web_commit_repo_overlap::web_js_ts_html",
                    "source_id": "stage10267::code_assist_web_commit_repo_overlap::web_js_ts_html",
                    "lineage_hash": "stage10267::code_assist_web_commit_repo_overlap::web_js_ts_html",
                    "split_role": "locked_regression",
                    "train_eligible": False,
                    "promotion_only": True,
                    "hidden_final": False,
                    "language_family": "web_js_ts_html",
                    "skill_area": "edit_localization",
                    "slice_tags": [
                        "maintainer_bundle",
                        "web_js_ts_html",
                        "compact_bounded",
                        "repo_overlap",
                        "stress_eval",
                        "code_assist",
                    ],
                    "thresholds": {"must_compare_100m_and_gemma": True, "projection_only": True},
                    "blocked_training_reason": "repo_overlap_web_stress_eval_only",
                    "rows": rows,
                    "maintainer_bundle_mode": True,
                    "projection_mode": "compact_bounded_choice_auxiliary",
                    "bundle_ids": bundle_ids,
                    "gold_answers_paths": gold_paths,
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
        ]
        if rows
        else [],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    PAYLOAD.write_text(PROJECTION.json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(
        PROJECTION.json.dumps(
            {
                "stage": STAGE,
                "passed": payload["passed"],
                "artifact": PROJECTION.display(PAYLOAD),
                "metrics": payload["metrics"],
                "source": PROJECTION.display(SOURCE),
                "runtime_bundle": PROJECTION.display(RUNTIME_BUNDLE),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        PROJECTION.json.dumps(
            {
                "stage": STAGE,
                "passed": payload["passed"],
                "artifact": PROJECTION.display(PAYLOAD),
                "metrics": payload["metrics"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
