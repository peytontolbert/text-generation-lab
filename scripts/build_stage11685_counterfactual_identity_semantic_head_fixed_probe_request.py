#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11685_counterfactual_identity_semantic_head_fixed_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "counterfactual_identity_semantic_head_fixed_probe_request.json"

MANIFEST = ART / "stage11678_web_remaining_miss_counterfactual_builder/web_same_role_identity_counterfactual_train.jsonl"
QUALITY = ART / "stage11682_same_role_counterfactual_quality_audit/same_role_counterfactual_quality_audit.json"
INIT_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ART / "stage11685_counterfactual_identity_semantic_head_fixed_probe"
RUNTIME_DIR = RUN_DIR / "runtime_model"
OUTPUT_DIR = RUN_DIR / "bounded_decoder_probe"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    rows = load_jsonl(MANIFEST)
    quality = load_json(QUALITY)
    task_counts = Counter(str(row.get("task_type") or "unknown") for row in rows)
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
        str(len(rows)),
        "--max-eval-rows",
        "0",
        "--max-strict-rows",
        "0",
        "--max-steps",
        "1536",
        "--batch-size",
        "8",
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
        "--bounded-choice-root-group-aux-weight",
        "2.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval_semantic_candidate_head",
        "--bounded-choice-train-head-only",
        "--bounded-decoder-train-sampler",
        "web_gap_same_root_grouped",
        "--bounded-choice-contrast-weight",
        "0.0",
        "--bounded-choice-verifier-value-listwise-weight",
        "1.0",
        "--bounded-choice-same-role-listwise-weight",
        "1.0",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--eos-loss-weight",
        "4.0",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(RUNTIME_DIR),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--no-final-checkpoint-export",
        "--output-dir",
        str(OUTPUT_DIR),
    ]
    gates = {
        "manifest_exists": MANIFEST.exists(),
        "quality_audit_static_clean": quality.get("gates", {}).get("static_remap_clean") is True,
        "quality_audit_all_rows_sampled_before": quality.get("gates", {}).get("all_counterfactual_rows_sampled") is True,
        "quality_audit_prior_fit_failed": quality.get("gates", {}).get("counterfactual_train_fit_acceptable") is False,
        "init_runtime_exists": INIT_RUNTIME.exists(),
        "row_count_92": len(rows) == 92,
        "uses_gpu2_mask": "CUDA_VISIBLE_DEVICES=2" in command,
        "uses_semantic_candidate_head": "encoder_option_retrieval_semantic_candidate_head" in command,
        "head_only": "--bounded-choice-train-head-only" in command,
    }
    summary = {
        "stage": 11685,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "stage11685_probe_ready" if all(gates.values()) else "stage11685_probe_blocked",
        "manifest": rel(MANIFEST),
        "quality_audit": rel(QUALITY),
        "init_runtime": rel(INIT_RUNTIME),
        "run_dir": rel(RUN_DIR),
        "runtime_dir": rel(RUNTIME_DIR),
        "output_dir": rel(OUTPUT_DIR),
        "row_counts": {"rows": len(rows), "task_type": dict(task_counts)},
        "command": command,
        "command_string": " ".join(command),
        "gates_before_execution": gates,
        "claim_boundary": [
            "This is a diagnostic fit test for a separate semantic candidate head on clean same-role counterfactual rows after fixing nested opaque-option synchronization.",
            "It is not promotable Web frontier training by itself.",
            "If this cannot fit the 92-row clean slice, a stronger/different identity scorer architecture is required.",
        ],
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "gates": gates, "row_counts": summary["row_counts"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
