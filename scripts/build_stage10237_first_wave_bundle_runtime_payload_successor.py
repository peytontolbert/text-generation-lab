#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/local/artifacts/stage10236_context_pack_python_replenishment_bundle/context_pack_python_replenishment_admitted_manifest.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage10237_first_wave_bundle_runtime_payload_successor"
SUMMARY = ROOT / "runs/summaries/stage10237_first_wave_bundle_runtime_payload_successor.json"
DOC = ROOT / "docs/FIRST_WAVE_BUNDLE_RUNTIME_PAYLOAD_STAGE10237.md"
PINNED_BUNDLE_ID_BY_LANGUAGE = {
    "python": "stage10236::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662::python",
}


def _load_module(module_name: str, script_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _compile_run(builder, bundle: dict, gold_path: Path) -> dict:
    gold = builder.load_json(gold_path)
    answers = [row for row in gold.get("perspective_gold_answers") or [] if isinstance(row, dict)]
    if len(answers) != 8:
        raise RuntimeError(f"gold_answer_count_not_8::{bundle.get('bundle_id')}")
    rows = [builder.compile_row(bundle, answer) for answer in answers]
    task_pack = {
        "bundle_id": bundle["bundle_id"],
        "task_pack_id": bundle["bundle_id"],
        "source_id": bundle["bundle_id"],
        "lineage_hash": bundle["bundle_id"],
        "split_role": "locked_regression",
        "train_eligible": False,
        "promotion_only": True,
        "hidden_final": False,
        "language_family": bundle["language_family"],
        "skill_area": "edit_localization",
        "slice_tags": ["maintainer_bundle", bundle["language_family"], "first_wave", "admitted"],
        "thresholds": {"must_compare_100m_and_gemma": True, "root_scoring_primary": True},
        "blocked_training_reason": "first_wave_admitted_bundle_eval_only",
        "rows": rows,
        "maintainer_bundle_mode": True,
        "gold_answers_path": builder.display(gold_path),
        "selected_tests": list(bundle.get("selected_tests") or []),
        "candidate_paths": list(bundle.get("candidate_paths") or []),
    }
    return {
        "cell_key": bundle["cell_key"],
        "task_pack": task_pack,
        "hundred_m_backend": {
            "kind": "preserved_bundle_prompt_generation",
            "model_bundle_manifest": "/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415/agentkernel_lite_encdec_manifest.json",
            "model_weights": "/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415/model/model.safetensors",
            "tokenizer_json": "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json",
            "tokenizer_config": "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json",
            "max_encoder_tokens": 1024,
            "max_new_tokens": 80,
            "device": "cpu",
        },
        "gemma_backend": {
            "kind": "ollama_generate",
            "model": "gemma3:12b",
            "seed": 0,
            "temperature": 0.0,
        },
    }


def main() -> None:
    builder = _load_module(
        "stage10237_stage10139_builder",
        ROOT / "scripts" / "build_stage10139_first_wave_bundle_runtime_payload.py",
    )
    payload = builder.build_payload(SOURCE)
    source_data = builder.load_json(SOURCE)
    source_rows = [row for row in source_data.get("rows") or [] if isinstance(row, dict)]
    by_bundle_id = {str(row.get("bundle_id") or ""): row for row in source_rows}

    runs = [row for row in payload.get("runs") or [] if isinstance(row, dict)]
    failures = list(payload.get("failures") or [])
    selection_summary = list(payload.get("selection_summary") or [])
    for language, pinned_bundle_id in PINNED_BUNDLE_ID_BY_LANGUAGE.items():
        bundle = by_bundle_id.get(pinned_bundle_id)
        if not bundle:
            failures.append(f"missing_pinned_bundle::{language}::{pinned_bundle_id}")
            continue
        bundle = dict(bundle)
        bundle["cell_key"] = builder.CELL_KEY_BY_LANGUAGE[language]
        gold_path = ROOT / str(bundle.get("perspective_gold_adjudication") or "")
        replacement_run = _compile_run(builder, bundle, gold_path)
        replaced = False
        for idx, run in enumerate(runs):
            task_pack = run.get("task_pack") if isinstance(run.get("task_pack"), dict) else {}
            if str(task_pack.get("language_family") or "") == language:
                runs[idx] = replacement_run
                replaced = True
                break
        if not replaced:
            runs.append(replacement_run)
        replacement_summary = {
            "cell_key": bundle["cell_key"],
            "bundle_id": bundle["bundle_id"],
            "language_family": bundle["language_family"],
            "selected_tests": len(bundle.get("selected_tests") or []),
            "candidate_paths": len(bundle.get("candidate_paths") or []),
            "gold_answers_path": builder.display(gold_path),
        }
        selection_summary = [row for row in selection_summary if row.get("language_family") != language]
        selection_summary.append(replacement_summary)

    payload["runs"] = runs
    payload["selection_summary"] = sorted(selection_summary, key=lambda row: row.get("language_family") or "")
    payload["failures"] = failures
    payload["passed"] = not failures and len(runs) == 4

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    payload_path = OUT_DIR / "first_wave_bundle_runtime_payload.json"
    payload_path.write_text(builder.json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": 10237,
        "stage_name": "stage10237_first_wave_bundle_runtime_payload_successor",
        "passed": payload["passed"],
        "artifacts": {
            "payload": builder.display(payload_path),
            "source": builder.display(SOURCE),
            "doc": builder.display(DOC),
        },
        "metrics": {
            "selected_runs": len(payload.get("runs") or []),
            "languages": sorted({row.get("language_family") for row in payload.get("selection_summary") or []}),
            "failures": len(payload.get("failures") or []),
        },
        "decision": "Recompiled one admitted first-wave maintainer bundle per language from the Stage10236 admitted-manifest successor and pinned the new code_assist Python replenishment bundle into the execution set.",
        "next_best_step": "Run Stage10140 first-wave bundle inference against this successor payload in the Trellis environment and write the reserved machine artifacts.",
        "created_at_utc": builder.now_utc(),
    }
    SUMMARY.write_text(builder.json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10237 First-Wave Bundle Runtime Payload Successor",
                "",
                f"Passed: `{summary['passed']}`",
                f"Selected runs: `{summary['metrics']['selected_runs']}`",
                "",
                summary["decision"],
                "",
                f"Next: {summary['next_best_step']}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(builder.json.dumps({"stage": 10237, "passed": summary["passed"], "payload": builder.display(payload_path), "failures": payload["failures"]}, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
