#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/local/artifacts/stage10236_context_pack_python_replenishment_bundle/context_pack_python_replenishment_admitted_manifest.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage10240_admitted_projection_runtime_payload_successor"
PAYLOAD = OUT_DIR / "admitted_projection_runtime_payload_successor.json"
SUMMARY = ROOT / "runs/summaries/stage10240_admitted_projection_runtime_payload_successor.json"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10224_bundle_coherence_counterbalance_probe/runtime_model/runtime_model_bundle.json"


def _load_module(module_name: str, script_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def main() -> None:
    projection = _load_module(
        "stage10240_stage10143_projection",
        ROOT / "scripts" / "build_stage10143_compact_bounded_bundle_projection.py",
    )
    payload = projection.build_payload(SOURCE)
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
    payload.update(
        {
            "stage": 10240,
            "stage_name": "stage10240_admitted_projection_runtime_payload_successor",
            "source": projection.display(SOURCE),
            "passed": bool(runs),
            "claim_scope": "adjudicated compact-bounded maintainer projection only; refreshed admitted-manifest successor scored with the stage10224 saved bounded-choice runtime versus live gemma3:12b",
            "eval_hardening": {
                "adjudicated_bundles_only": True,
                "primary_maintainer_leaderboard_allowed": False,
                "projection_only": True,
                "saved_runtime_backend": True,
                "skip_writeback_expected": True,
            },
            "runtime_bundle": projection.display(RUNTIME_BUNDLE),
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
                        {
                            str(((run.get("task_pack") or {}).get("language_family")) or "")
                            for run in runs
                        }
                    )
                },
            },
        }
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    PAYLOAD.write_text(projection.json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(
        projection.json.dumps(
            {
                "stage": 10240,
                "passed": payload["passed"],
                "artifact": projection.display(PAYLOAD),
                "metrics": payload["metrics"],
                "source": projection.display(SOURCE),
                "runtime_bundle": projection.display(RUNTIME_BUNDLE),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        projection.json.dumps(
            {
                "stage": 10240,
                "passed": payload["passed"],
                "artifact": projection.display(PAYLOAD),
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
