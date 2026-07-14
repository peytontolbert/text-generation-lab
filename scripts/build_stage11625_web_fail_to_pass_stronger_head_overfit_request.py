#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11625
NAME = "stage11625_web_fail_to_pass_stronger_head_overfit_request"
OUT = ART / NAME
SUMMARY = OUT / "web_fail_to_pass_stronger_head_overfit_request.json"
MANIFEST = OUT / "web_fail_to_pass_stronger_head_overfit_manifest.jsonl"
COMMAND = OUT / "web_fail_to_pass_stronger_head_overfit_command.json"

ROWS = ART / "stage11621_web_fail_to_pass_row_geometry_repair/web_fail_to_pass_geometry_repaired_train_support.jsonl"
INIT_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
PROBE = ART / "stage11625_web_fail_to_pass_stronger_head_overfit/bounded_decoder_probe"
RUNTIME_OUT = ART / "stage11625_web_fail_to_pass_stronger_head_overfit/runtime_model"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def normalize(row: dict[str, Any], split: str) -> dict[str, Any]:
    out = dict(row)
    out["split"] = split
    out.setdefault("prompt_text", out.get("input_text") or "")
    out.setdefault("decoder_text", out.get("target_text") or out.get("bounded_choice_target_label") or "")
    out["loss_mask"] = {"decoder_ce": True, "bounded_choice_aux": True}
    out["expected_enabled_loss"] = "bounded_choice_aux+bounded_choice_contrast"
    source = dict(out.get("standalone_projection_source") or {})
    source.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = source
    out["target"] = {
        "decoder_text": out.get("decoder_text"),
        "bounded_choice_target_label": out.get("bounded_choice_target_label") or out.get("target_text"),
        "semantic_value": out.get("semantic_target_value") or out.get("target_semantic_value"),
    }
    return out


def main() -> None:
    source_rows = load_jsonl(ROWS)
    train = [normalize(row, "train") for row in source_rows]
    eval_rows = [normalize(row, "eval") for row in source_rows]
    manifest = train + eval_rows
    command = [
        "env",
        "CUDA_VISIBLE_DEVICES=2",
        "NVIDIA_VISIBLE_DEVICES=2",
        "AGENTKERNEL_EVAL_DEVICE=cuda:0",
        "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True",
        "TMPDIR=/data/tmp",
        "TEMP=/data/tmp",
        "TMP=/data/tmp",
        "conda",
        "run",
        "-n",
        "trellis",
        "python",
        str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(MANIFEST),
        "--mode",
        "bounded_decoder_ce_probe",
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        str(ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"),
        "--tokenizer-json",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),
        "--tokenizer-config",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),
        "--tokenizer-hashlock",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows",
        str(len(train)),
        "--max-eval-rows",
        str(len(eval_rows)),
        "--max-strict-rows",
        "0",
        "--max-steps",
        "1024",
        "--batch-size",
        "6",
        "--learning-rate",
        "3e-4",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "16",
        "--decoder-ce-weight",
        "0.0",
        "--bounded-choice-aux-weight",
        "3.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval_web_task_candidate_head",
        "--bounded-choice-train-head-only",
        "--bounded-decoder-train-sampler",
        "web_task_family_balanced",
        "--bounded-choice-contrast-weight",
        "0.5",
        "--bounded-choice-contrast-margin",
        "0.08",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--eos-loss-weight",
        "4.0",
        "--enable-generation-audit",
        "--max-generation-rows",
        "6",
        "--max-generation-tokens",
        "8",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(RUNTIME_OUT),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--no-final-checkpoint-export",
        "--output-dir",
        str(PROBE),
    ]
    gates = {
        "row_count_36": len(source_rows) == 36,
        "same_rows_train_eval": len(train) == len(eval_rows) == 36,
        "gpu2_mask_present": "CUDA_VISIBLE_DEVICES=2" in command and "NVIDIA_VISIBLE_DEVICES=2" in command,
        "head_only_enabled": "--bounded-choice-train-head-only" in command,
        "decoder_ce_disabled": "--decoder-ce-weight" in command and command[command.index("--decoder-ce-weight") + 1] == "0.0",
        "strict_disabled": "--max-strict-rows" in command and command[command.index("--max-strict-rows") + 1] == "0",
        "stronger_than_stage11623": "--max-steps" in command and command[command.index("--max-steps") + 1] == "1024",
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "stronger_head_only_overfit_ready" if all(gates.values()) else "stronger_head_only_overfit_blocked",
        "gates": gates,
        "metrics": {"source_rows": len(source_rows), "manifest_rows": len(manifest)},
        "objective_settings": {
            "bounded_choice_aux_source": "encoder_option_retrieval_web_task_candidate_head",
            "bounded_choice_train_head_only": True,
            "decoder_ce_weight": 0.0,
            "bounded_choice_aux_weight": 3.0,
            "bounded_choice_contrast_weight": 0.5,
            "bounded_choice_contrast_margin": 0.08,
            "learning_rate": "3e-4",
            "max_steps": 1024,
            "batch_size": 6,
        },
        "claim_boundary": [
            "This is a non-promotable stronger overfit sanity check.",
            "The same repaired controlled rows are intentionally used as train and eval.",
            "A high score only proves head/objective representability; it is not frontier progress.",
        ],
        "source_artifacts": {"rows": rel(ROWS), "init_runtime": rel(INIT_RUNTIME)},
        "outputs": {"manifest": rel(MANIFEST), "command": rel(COMMAND), "summary": rel(SUMMARY), "runtime_model": rel(RUNTIME_OUT)},
        "command": command,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(MANIFEST, manifest)
    write_json(COMMAND, {"command": command})
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "gates": gates, "objective_settings": summary["objective_settings"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
