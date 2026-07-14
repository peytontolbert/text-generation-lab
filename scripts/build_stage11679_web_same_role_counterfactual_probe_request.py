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
NAME = "stage11679_web_same_role_counterfactual_probe_request"
OUT = ART / NAME
MANIFEST = OUT / "web_canonical_plus_same_role_counterfactual_train.jsonl"
SUMMARY = OUT / "web_same_role_counterfactual_probe_request.json"

CANONICAL_TRAIN = ART / "stage11663_web_canonical_renderer_package/web_canonical_train_support.jsonl"
COUNTERFACTUAL_TRAIN = ART / "stage11678_web_remaining_miss_counterfactual_builder/web_same_role_identity_counterfactual_train.jsonl"
COUNTERFACTUAL_PACKAGE = ART / "stage11678_web_remaining_miss_counterfactual_builder/web_remaining_miss_counterfactual_package.json"
INIT_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ART / "stage11679_web_same_role_counterfactual_probe"
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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    canonical = load_jsonl(CANONICAL_TRAIN)
    counterfactual = load_jsonl(COUNTERFACTUAL_TRAIN)
    package = load_json(COUNTERFACTUAL_PACKAGE)
    rows = canonical + counterfactual
    write_jsonl(MANIFEST, rows)
    row_ids = [row.get("row_id") for row in rows]
    roots_by_split = Counter(str(row.get("split_component") or row.get("package_split") or row.get("split")) for row in rows)
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
        "encoder_option_retrieval_web_task_candidate_head",
        "--bounded-choice-train-head-only",
        "--bounded-decoder-train-sampler",
        "web_gap_same_root_grouped",
        "--bounded-choice-contrast-weight",
        "0.5",
        "--bounded-choice-contrast-margin",
        "0.08",
        "--bounded-choice-verifier-value-listwise-weight",
        "1.0",
        "--bounded-choice-same-role-listwise-weight",
        "0.75",
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
        "canonical_train_exists": CANONICAL_TRAIN.exists(),
        "counterfactual_train_exists": COUNTERFACTUAL_TRAIN.exists(),
        "counterfactual_package_ready": package.get("decision") == "stage11678_ready_for_probe_request",
        "init_runtime_exists": INIT_RUNTIME.exists(),
        "combined_rows_expected": len(rows) == len(canonical) + len(counterfactual) and len(rows) == 426,
        "row_ids_unique": len(row_ids) == len(set(row_ids)),
        "uses_gpu2_mask": "CUDA_VISIBLE_DEVICES=2" in command,
        "head_only": "--bounded-choice-train-head-only" in command,
        "same_root_grouped_sampler": "web_gap_same_root_grouped" in command,
        "decoder_ce_disabled": "--decoder-ce-weight" in command and command[command.index("--decoder-ce-weight") + 1] == "0.0",
        "same_role_listwise_weight_nonzero": "--bounded-choice-same-role-listwise-weight" in command
        and float(command[command.index("--bounded-choice-same-role-listwise-weight") + 1]) > 0.0,
    }
    summary = {
        "stage": 11679,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "stage11679_probe_ready" if all(gates.values()) else "stage11679_probe_blocked",
        "manifest": rel(MANIFEST),
        "canonical_train": rel(CANONICAL_TRAIN),
        "counterfactual_train": rel(COUNTERFACTUAL_TRAIN),
        "counterfactual_package": rel(COUNTERFACTUAL_PACKAGE),
        "init_runtime": rel(INIT_RUNTIME),
        "run_dir": rel(RUN_DIR),
        "runtime_dir": rel(RUNTIME_DIR),
        "output_dir": rel(OUTPUT_DIR),
        "row_counts": {
            "combined": len(rows),
            "canonical": len(canonical),
            "counterfactual": len(counterfactual),
            "task_type": dict(task_counts),
            "split_component": dict(roots_by_split),
        },
        "command": command,
        "command_string": " ".join(command),
        "gates_before_execution": gates,
        "claim_boundary": [
            "This is a head-only diagnostic training request using canonical train rows plus Stage11678 train-support-only same-role counterfactuals.",
            "No Stage11678 sealed diagnostic rows are included in training.",
            "Promotion requires a postrun audit proving canonical heldout improves beyond 51/66, original Web heldout beats 38/66 for Web frontier progress, and protected gates remain preserved.",
        ],
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "gates": gates, "row_counts": summary["row_counts"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
