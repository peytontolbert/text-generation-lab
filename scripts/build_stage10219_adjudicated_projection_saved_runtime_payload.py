#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10219
NAME = "stage10219_adjudicated_projection_saved_runtime_payload"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PAYLOAD = OUT_DIR / "adjudicated_projection_saved_runtime_payload.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
SOURCE = ROOT / "runs/local/artifacts/stage10143_compact_bounded_bundle_projection/compact_bounded_bundle_projection.json"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10215_python_contrast_counterbalance_probe/runtime_model/runtime_model_bundle.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE)
    runs = []
    metrics = {"runs": 0, "rows": 0, "rows_by_language": {}}
    for run in [r for r in source.get("runs") or [] if isinstance(r, dict)]:
        task_pack = dict(run.get("task_pack") or {})
        rows = [row for row in task_pack.get("rows") or [] if isinstance(row, dict)]
        language = str(task_pack.get("language_family") or "")
        metrics["runs"] += 1
        metrics["rows"] += len(rows)
        metrics["rows_by_language"][language] = metrics["rows_by_language"].get(language, 0) + len(rows)
        runs.append(
            {
                "cell_key": str(run.get("cell_key") or ""),
                "task_pack": task_pack,
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
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(runs),
        "source_projection": display(SOURCE),
        "runtime_bundle": display(RUNTIME_BUNDLE),
        "claim_scope": "adjudicated compact-bounded maintainer projection only; current saved-runtime 100M constrained-choice scoring versus live gemma3:12b on the admitted 8-bundle projection",
        "eval_hardening": {
            "primary_maintainer_leaderboard_allowed": False,
            "projection_only": True,
            "adjudicated_bundles_only": True,
            "saved_runtime_backend": True,
            "skip_writeback_expected": True,
        },
        "metrics": metrics,
        "runs": runs,
    }
    PAYLOAD.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps({"stage": STAGE, "passed": payload["passed"], "artifact": display(PAYLOAD), "metrics": metrics}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": STAGE, "passed": payload["passed"], "artifact": display(PAYLOAD), "metrics": metrics}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
