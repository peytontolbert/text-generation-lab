#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10190
NAME = "stage10190_compact_bounded_harness_payload_from_frozen_stage10172"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PAYLOAD = OUT_DIR / "compact_bounded_harness_payload_from_frozen_stage10172.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
PACKAGE = ROOT / "runs/local/artifacts/stage10149_v27_standalone_compact_permutation_balanced_package/standalone_compact_permutation_balanced_package.json"
AUDIT = ROOT / "runs/local/artifacts/stage10172_choice_aux_encoder_option_retrieval_target100m_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
CELL_KEY_BY_LANGUAGE = {
    "python": "full_product_harness::python::edit_localization",
    "rust": "full_product_harness::rust::edit_localization",
    "c_cpp": "full_product_harness::c_cpp::edit_localization",
    "web_js_ts_html": "full_product_harness::web_js_ts_html::edit_localization",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_payload() -> dict[str, Any]:
    package = load_json(PACKAGE)
    eval_rows = load_jsonl(ROOT / str(package.get("eval_dataset_path") or ""))
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in eval_rows:
        language = str(row.get("language_family") or "")
        if language not in CELL_KEY_BY_LANGUAGE:
            continue
        grouped.setdefault(language, []).append(row)
    runs = []
    row_counts: dict[str, int] = {}
    for language, cell_key in CELL_KEY_BY_LANGUAGE.items():
        rows = grouped.get(language) or []
        if not rows:
            continue
        row_counts[language] = len(rows)
        bundle_ids = sorted({str(row.get("bundle_id") or "") for row in rows})
        runs.append(
            {
                "cell_key": cell_key,
                "task_pack": {
                    "bundle_id": f"stage10172_frozen_compact_bounded::{language}",
                    "task_pack_id": f"stage10172_frozen_compact_bounded::{language}",
                    "source_id": f"stage10172_frozen_compact_bounded::{language}",
                    "lineage_hash": f"stage10172_frozen_compact_bounded::{language}",
                    "split_role": "locked_regression",
                    "train_eligible": False,
                    "promotion_only": True,
                    "hidden_final": False,
                    "language_family": language,
                    "skill_area": "edit_localization",
                    "slice_tags": ["maintainer_bundle", language, "compact_bounded", "frozen_100m", "diagnostic_harness"],
                    "thresholds": {"must_compare_100m_and_gemma": True, "projection_only": True},
                    "blocked_training_reason": "frozen_bounded_choice_diagnostic_only",
                    "rows": rows,
                    "maintainer_bundle_mode": True,
                    "projection_mode": "compact_bounded_choice_auxiliary",
                    "bundle_ids": bundle_ids,
                },
                "hundred_m_backend": {
                    "kind": "frozen_bounded_choice_audit",
                    "bounded_choice_audit_path": str(AUDIT),
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
        "source_package": display(PACKAGE),
        "frozen_hundred_m_audit": display(AUDIT),
        "claim_scope": "diagnostic compact bounded maintainer projection only; frozen stage10172 100M constrained-choice outputs versus live gemma3:12b same-row outputs",
        "eval_hardening": {
            "primary_maintainer_leaderboard_allowed": False,
            "projection_only": True,
            "same_task_pack_as_gemma": True,
            "frozen_hundred_m_backend": True,
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


if __name__ == "__main__":
    main()
