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
STAGE = 11660
NAME = "stage11660_web_schema_aligned_bridge_head_only_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "web_schema_aligned_bridge_head_only_probe_request.json"

MANIFEST = ART / "stage11659_web_schema_aligned_bridge_package/web_schema_aligned_bridge_manifest.jsonl"
INIT_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ART / "stage11660_web_schema_aligned_bridge_head_only_probe"
RUNTIME_DIR = RUN_DIR / "runtime_model"
OUTPUT_DIR = RUN_DIR / "bounded_decoder_probe"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    rows = load_jsonl(MANIFEST)
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
        "113",
        "--max-eval-rows",
        "0",
        "--max-strict-rows",
        "0",
        "--max-steps",
        "768",
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
        "encoder_option_retrieval_web_task_candidate_head",
        "--bounded-choice-train-head-only",
        "--bounded-decoder-train-sampler",
        "web_gap_same_root_grouped",
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
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "web_schema_aligned_bridge_head_only_probe_ready",
        "manifest": rel(MANIFEST),
        "init_runtime": rel(INIT_RUNTIME),
        "run_dir": rel(RUN_DIR),
        "runtime_dir": rel(RUNTIME_DIR),
        "output_dir": rel(OUTPUT_DIR),
        "command": command,
        "command_string": " ".join(command),
        "row_counts": {
            "rows": len(rows),
            "unique_roots": len({str(row.get("root_lineage_key") or row.get("root_id")) for row in rows}),
            "task_counts": dict(sorted({task: sum(1 for row in rows if row.get("task_type") == task) for task in {row.get("task_type") for row in rows}}.items())),
        },
        "gates_before_execution": {
            "manifest_exists": MANIFEST.exists(),
            "init_runtime_exists": INIT_RUNTIME.exists(),
            "uses_gpu2_mask": "CUDA_VISIBLE_DEVICES=2" in command,
            "head_only": "--bounded-choice-train-head-only" in command,
            "same_root_grouped_sampler": "web_gap_same_root_grouped" in command,
            "decoder_ce_disabled": "--decoder-ce-weight" in command and command[command.index("--decoder-ce-weight") + 1] == "0.0",
        },
        "claim_boundary": [
            "This request is diagnostic and tests whether schema-aligned bridge rows transfer better than Stage11648 shell geometry.",
            "It is not a promotion unless a postrun routed audit beats Web heldout 38/66 while preserving protected gates.",
            "The train roots are reused Stage11648 support roots; OpenHands/Llama heldout rows remain untouched.",
        ],
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "gates": summary["gates_before_execution"], "row_counts": summary["row_counts"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
