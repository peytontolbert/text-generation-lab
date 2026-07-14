#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11651_web_gap_grouped_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "web_gap_grouped_probe_request.json"
MANIFEST = ART / "stage11648_web_gap_grouped_admission_compiler/web_gap_grouped_probe_manifest.jsonl"
STAGE11648 = ART / "stage11648_web_gap_grouped_admission_compiler/web_gap_grouped_admission_compiler.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage11648 = load_json(STAGE11648)
    rows = sum(1 for _ in MANIFEST.open("r", encoding="utf-8")) if MANIFEST.exists() else 0
    output_dir = ART / "stage11651_web_gap_grouped_probe/bounded_decoder_probe"
    runtime_dir = ART / "stage11651_web_gap_grouped_probe/runtime_model"
    command = [
        "env", "CUDA_VISIBLE_DEVICES=2", "NVIDIA_VISIBLE_DEVICES=2", "AGENTKERNEL_EVAL_DEVICE=cuda:0",
        "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True", "TMPDIR=/data/tmp", "TEMP=/data/tmp", "TMP=/data/tmp",
        "conda", "run", "-n", "trellis", "python", str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
        "--repo-root", str(ROOT),
        "--manifest", str(MANIFEST),
        "--mode", "bounded_decoder_ce_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", str(ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"),
        "--tokenizer-json", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),
        "--tokenizer-config", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),
        "--tokenizer-hashlock", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows", str(rows),
        "--max-eval-rows", "0",
        "--max-strict-rows", "0",
        "--max-steps", "512",
        "--batch-size", "8",
        "--learning-rate", "2e-7",
        "--max-encoder-tokens", "768",
        "--max-decoder-tokens", "16",
        "--decoder-ce-weight", "0.04",
        "--bounded-choice-aux-weight", "1.0",
        "--bounded-choice-root-group-aux-weight", "2.0",
        "--bounded-choice-aux-source", "encoder_option_retrieval_web_task_candidate_head",
        "--bounded-decoder-train-sampler", "web_gap_root_balanced",
        "--bounded-choice-contrast-weight", "0.5",
        "--bounded-choice-contrast-margin", "0.08",
        "--structured-aux-weight", "0.0",
        "--denoise-weight", "0.0",
        "--eos-loss-weight", "4.0",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir", str(runtime_dir),
        "--initialize-from-runtime-model", str(ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"),
        "--preservation-reference-runtime-model", str(ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"),
        "--preservation-kl-weight", "8.0",
        "--no-final-checkpoint-export",
        "--output-dir", str(output_dir),
    ]
    gates = {
        "stage11648_ready": stage11648.get("decision") == "web_gap_grouped_training_request_ready",
        "manifest_rows_113": rows == 113,
        "root_group_flag_present": "--bounded-choice-root-group-aux-weight" in command,
        "root_balanced_sampler_present": "web_gap_root_balanced" in command,
        "gpu2_mask_present": "CUDA_VISIBLE_DEVICES=2" in command,
        "runtime_path_stage11651": "stage11651_web_gap_grouped_probe" in str(runtime_dir),
    }
    summary = {
        "stage": 11651,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "web_gap_grouped_probe_request_ready" if all(gates.values()) else "web_gap_grouped_probe_request_blocked",
        "gates": gates,
        "command": command,
        "metrics": {"manifest_rows": rows, "admitted_roots": stage11648.get("metrics", {}).get("admitted_roots"), "admitted_rows": stage11648.get("metrics", {}).get("admitted_rows")},
        "source_artifacts": {"stage11648": rel(STAGE11648), "manifest": rel(MANIFEST)},
        "outputs": {"summary": rel(SUMMARY), "runtime_dir": rel(runtime_dir), "output_dir": rel(output_dir)},
        "promotion_gates_after_run": ["filtered strict 22/22", "old canary strict 23/23", "residual >=7/10", "web heldout >38/66", "same-manifest Gemma reference remains 52/66"],
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "gates": gates, "metrics": summary["metrics"]}, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
