#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10268
NAME = "stage10268_web_augmented_admitted_projection_runtime_payload"
BASE_SOURCE = ROOT / "runs/local/artifacts/stage10236_context_pack_python_replenishment_bundle/context_pack_python_replenishment_admitted_manifest.json"
WEB_SOURCE = ROOT / "runs/local/artifacts/stage10266_code_assist_web_commit_compact_support_package/code_assist_web_commit_admitted_manifest.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MERGED_MANIFEST = OUT_DIR / "web_augmented_admitted_manifest.json"
PAYLOAD = OUT_DIR / "web_augmented_admitted_projection_runtime_payload.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10224_bundle_coherence_counterbalance_probe/runtime_model/runtime_model_bundle.json"


def _load_module(module_name: str, script_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


PROJECTION = _load_module(
    "stage10268_stage10143_projection",
    ROOT / "scripts" / "build_stage10143_compact_bounded_bundle_projection.py",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def merge_rows() -> list[dict[str, Any]]:
    base = [row for row in (load_json(BASE_SOURCE).get("rows") or []) if isinstance(row, dict)]
    web = [row for row in (load_json(WEB_SOURCE).get("rows") or []) if isinstance(row, dict)]
    merged: dict[str, dict[str, Any]] = {}
    for row in base + web:
        bundle_id = str(row.get("bundle_id") or "")
        if not bundle_id:
            continue
        updated = dict(row)
        claim_boundary = dict(updated.get("claim_boundary") or {})
        if bundle_id.startswith("stage10264::code_assist_git_commit::"):
            claim_boundary.update(
                {
                    "repo_overlap_non_headline": True,
                    "source_heldout_claim_allowed": False,
                    "runtime_successor_augmented_web_support": True,
                }
            )
            updated["claim_boundary"] = claim_boundary
        merged[bundle_id] = updated
    return [merged[key] for key in sorted(merged)]


def filter_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    kept: list[dict[str, Any]] = []
    excluded: list[str] = []
    for row in rows:
        option_count = len(row.get("opaque_options") or [])
        if option_count < 2:
            excluded.append(f"{row.get('row_id')}::degenerate_option_count_{option_count}")
            continue
        kept.append(row)
    return kept, excluded


def main() -> None:
    merged_rows = merge_rows()
    merged_manifest = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(merged_rows),
        "rows": merged_rows,
        "metrics": {
            "bundle_count": len(merged_rows),
            "bundle_count_by_language": {
                language: sum(1 for row in merged_rows if str(row.get("language_family") or "") == language)
                for language in sorted({str(row.get("language_family") or "") for row in merged_rows})
            },
            "augmented_web_bundles": sum(
                1 for row in merged_rows if str(row.get("bundle_id") or "").startswith("stage10264::code_assist_git_commit::")
            ),
        },
        "base_source": display(BASE_SOURCE),
        "web_source": display(WEB_SOURCE),
        "claim_scope": "adjudicated compact-bounded maintainer projection successor with two additional repo-overlap web support bundles; non-headline web augmentation only",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    MERGED_MANIFEST.write_text(json.dumps(merged_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    payload = PROJECTION.build_payload(MERGED_MANIFEST)
    runs = []
    excluded_rows: list[str] = []
    for run in payload.get("runs") or []:
        if not isinstance(run, dict):
            continue
        task_pack = dict(run.get("task_pack") or {})
        rows = [row for row in task_pack.get("rows") or [] if isinstance(row, dict)]
        kept_rows, dropped = filter_rows(rows)
        excluded_rows.extend(dropped)
        if not kept_rows:
            continue
        task_pack["rows"] = kept_rows
        task_pack["row_count_after_filter"] = len(kept_rows)
        task_pack["excluded_rows"] = dropped
        updated = dict(run)
        updated["task_pack"] = task_pack
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

    payload.update(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "source": display(MERGED_MANIFEST),
            "passed": bool(runs),
            "claim_scope": "adjudicated compact-bounded maintainer projection only; saved bounded-choice 100M runtime versus live gemma3:12b on the multilingual admitted successor with additional repo-overlap web support bundles",
            "eval_hardening": {
                "adjudicated_bundles_only": True,
                "primary_maintainer_leaderboard_allowed": False,
                "projection_only": True,
                "saved_runtime_backend": True,
                "skip_writeback_expected": True,
                "repo_overlap_web_non_headline": True,
                "single_option_rows_excluded": True,
            },
            "runtime_bundle": display(RUNTIME_BUNDLE),
            "excluded_rows": excluded_rows,
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
                    for language in sorted({str(((run.get("task_pack") or {}).get("language_family")) or "") for run in runs})
                },
                "augmented_web_bundles": sum(
                    1 for run in runs if str(((run.get("task_pack") or {}).get("bundle_id")) or "").startswith("stage10264::code_assist_git_commit::")
                ),
                "excluded_rows": len(excluded_rows),
            },
        }
    )
    PAYLOAD.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(
        json.dumps(
            {
                "stage": STAGE,
                "passed": payload["passed"],
                "artifact": display(PAYLOAD),
                "merged_manifest": display(MERGED_MANIFEST),
                "metrics": payload["metrics"],
                "excluded_rows": excluded_rows,
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
                "stage": STAGE,
                "passed": payload["passed"],
                "artifact": display(PAYLOAD),
                "merged_manifest": display(MERGED_MANIFEST),
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
