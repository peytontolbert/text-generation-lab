#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10366
NAME = "stage10366_quarantined_full_visible_runtime_payload"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PAYLOAD = OUT_DIR / "quarantined_full_visible_runtime_payload.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
SOURCE = ROOT / "runs/local/artifacts/stage10365_full_visible_evidence_compact_projection/full_visible_evidence_compact_projection.json"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10359_anchored_citation_plus_pythonverifier_probe/runtime_model/runtime_model_bundle.json"

QUARANTINED_ROW_IDS = {
    "stage10126::tokenizers::tokenizers::rust::evidence_citation::full_visible_compact_bounded",
}


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


def main() -> None:
    source = load_json(SOURCE)
    source_runs = [run for run in source.get("runs") or [] if isinstance(run, dict)]
    runs = []
    quarantined = []
    for run in source_runs:
        rows = [row for row in run.get("rows") or [] if isinstance(row, dict)]
        kept_rows = []
        for row in rows:
            row_id = str(row.get("row_id") or "")
            if row_id in QUARANTINED_ROW_IDS:
                quarantined.append(
                    {
                        "row_id": row_id,
                        "bundle_id": run.get("bundle_id"),
                        "language_family": run.get("language_family"),
                        "reason": "candidate_change_surface_and_gold_symptom_or_call_path_surface_share_the_same_visible_snippet",
                    }
                )
                continue
            kept_rows.append(row)
        if not kept_rows:
            continue
        bundle_id = str(run.get("bundle_id") or "")
        language = str(run.get("language_family") or bundle_id.split("::")[-1])
        runs.append(
            {
                "cell_key": f"full_visible_quarantined::{language}::{bundle_id}",
                "task_pack": {
                    "bundle_id": bundle_id,
                    "task_pack_id": bundle_id,
                    "source_id": bundle_id,
                    "lineage_hash": bundle_id,
                    "split_role": "locked_regression",
                    "train_eligible": False,
                    "promotion_only": True,
                    "hidden_final": False,
                    "language_family": language,
                    "skill_area": "edit_localization",
                    "slice_tags": ["maintainer_bundle", language, "full_visible_compact_bounded", "quarantined"],
                    "thresholds": {"must_compare_100m_and_gemma": True, "projection_only": True},
                    "blocked_training_reason": "full_visible_projection_eval_only",
                    "rows": kept_rows,
                    "maintainer_bundle_mode": True,
                    "projection_mode": "full_visible_compact_bounded_choice_auxiliary",
                    "gold_answers_path": str(run.get("gold_answers_path") or ""),
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
                    "num_predict": 16,
                    "timeout_seconds": 180,
                },
            }
        )
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "source": display(SOURCE),
        "runtime_bundle": display(RUNTIME_BUNDLE),
        "passed": bool(runs),
        "claim_scope": "quarantined full-visible compact-bounded maintainer projection only; repaired evidence visibility with the known ambiguous tokenizers rust citation row removed",
        "eval_hardening": {
            "quarantined_ambiguous_rows": True,
            "projection_only": True,
            "same_task_pack_required": True,
            "saved_runtime_backend": True,
            "skip_writeback_expected": True,
            "primary_maintainer_leaderboard_allowed": False,
        },
        "quarantined_rows": quarantined,
        "metrics": {
            "runs": len(runs),
            "rows": sum(len(((run.get("task_pack") or {}).get("rows") or [])) for run in runs),
            "quarantined_rows": len(quarantined),
            "rows_by_language": {
                language: sum(
                    len(((run.get("task_pack") or {}).get("rows") or []))
                    for run in runs
                    if str(((run.get("task_pack") or {}).get("language_family")) or "") == language
                )
                for language in sorted(
                    {
                        str(((run.get("task_pack") or {}).get("language_family")) or "")
                        for run in runs
                    }
                )
            },
        },
        "runs": runs,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    write_json(PAYLOAD, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": payload["passed"],
            "artifact": display(PAYLOAD),
            "metrics": payload["metrics"],
            "source": display(SOURCE),
            "runtime_bundle": display(RUNTIME_BUNDLE),
        },
    )
    print(json.dumps({"stage": STAGE, "passed": payload["passed"], "artifact": display(PAYLOAD), "metrics": payload["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
