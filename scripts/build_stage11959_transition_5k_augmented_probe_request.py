#!/usr/bin/env python3
"""Emit guarded diagnostic probe for Stage11958 augmented Transition-5K rows."""

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
STAGE = 11959
NAME = "stage11959_transition_5k_augmented_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "transition_5k_augmented_probe_request.json"
COMMAND_JSON = OUT / "transition_5k_augmented_command.json"
MANIFEST = OUT / "transition_5k_augmented_manifest.jsonl"

SUPPORT_ROWS = ART / "stage11958_transition_5k_v1_augmented_package/transition_projection_rows_5k_v1_augmented.jsonl"
INIT_RUNTIME = ART / "stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json"
PRESERVATION_RUNTIME = INIT_RUNTIME
RUN_DIR = ART / "stage11960_transition_5k_augmented_probe"
RUNTIME_DIR = RUN_DIR / "runtime_model"
OUTPUT_DIR = RUN_DIR / "bounded_decoder_probe"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def normalize(row: dict[str, Any], tag: str, split: str) -> dict[str, Any]:
    out = dict(row)
    out["row_id"] = f"{row.get('row_id')}::{tag}"
    out["split"] = split
    out["package_split"] = split
    if split == "train":
        out["train_support_only"] = True
        out["strict_eval_eligible"] = False
        out["preservation_exempt"] = True
    source = dict(out.get("standalone_projection_source") or {})
    source.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = source
    label = out.get("bounded_choice_target_label") or out.get("target_label") or out.get("target_text")
    if not isinstance(out.get("target"), dict):
        out["target"] = {
            "decoder_text": out.get("decoder_text") or label,
            "bounded_choice_target_label": label,
            "semantic_value": out.get("semantic_target_value") or out.get("target_value"),
        }
    loss_mask = dict(out.get("loss_mask") or {})
    loss_mask.update({"bounded_choice_aux": True, "structured_aux": True, "transition_projection": True})
    out["loss_mask"] = loss_mask
    return out


def main() -> None:
    rows = read_jsonl(SUPPORT_ROWS)
    train_rows = [normalize(row, "stage11959_train", "train") for row in rows if str(row.get("split")) == "train"]
    eval_rows = [normalize(row, "stage11959_eval", "eval") for row in rows if str(row.get("split")) == "validation"]
    strict_rows = [normalize(row, "stage11959_strict", "strict_eval") for row in rows if str(row.get("split")) == "strict_eval"]
    manifest_rows = train_rows + eval_rows + strict_rows
    write_jsonl(MANIFEST, manifest_rows)

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
        str(len(train_rows)),
        "--max-eval-rows",
        str(len(eval_rows)),
        "--max-strict-rows",
        str(len(strict_rows)),
        "--max-steps",
        "1400",
        "--batch-size",
        "8",
        "--learning-rate",
        "8e-5",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "16",
        "--decoder-ce-weight",
        "0.0",
        "--bounded-choice-aux-weight",
        "2.5",
        "--bounded-choice-root-group-aux-weight",
        "0.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval_semantic_candidate_head",
        "--bounded-choice-train-head-only",
        "--bounded-decoder-train-sampler",
        "task_balanced",
        "--bounded-choice-contrast-weight",
        "0.2",
        "--bounded-choice-contrast-margin",
        "0.08",
        "--bounded-choice-same-role-listwise-weight",
        "0.5",
        "--bounded-choice-verifier-value-listwise-weight",
        "0.9",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--eos-loss-weight",
        "1.0",
        "--enable-generation-audit",
        "--max-generation-rows",
        "8",
        "--max-generation-tokens",
        "8",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(RUNTIME_DIR),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(PRESERVATION_RUNTIME),
        "--preservation-kl-weight",
        "6.0",
        "--no-final-checkpoint-export",
        "--output-dir",
        str(OUTPUT_DIR),
    ]
    train_counter = Counter(row.get("task_type") for row in train_rows)
    label_counter = Counter(row.get("bounded_choice_target_label") for row in train_rows)
    gates = {
        "uses_gpu2_mask": "CUDA_VISIBLE_DEVICES=2" in command and "NVIDIA_VISIBLE_DEVICES=2" in command,
        "init_runtime_stage11924_exists": INIT_RUNTIME.exists(),
        "preservation_runtime_stage11924_exists": PRESERVATION_RUNTIME.exists(),
        "head_only_enabled": "--bounded-choice-train-head-only" in command,
        "semantic_candidate_head": "encoder_option_retrieval_semantic_candidate_head" in command,
        "train_rows_5176": len(train_rows) == 5176,
        "eval_rows_248": len(eval_rows) == 248,
        "strict_rows_356": len(strict_rows) == 356,
        "four_transition_tasks_in_train": set(train_counter) == {
            "transition_next_action",
            "transition_candidate_selection",
            "transition_verifier_transition",
            "transition_continue_or_stop",
        },
        "counterfactual_labels_present": any(label in label_counter for label in {"G", "H", "I"}),
    }
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": all(gates.values()),
        "decision": "transition_5k_augmented_probe_request_ready" if all(gates.values()) else "transition_5k_augmented_probe_request_blocked",
        "command": command,
        "gates_before_execution": gates,
        "row_counts": {
            "train_rows": len(train_rows),
            "eval_rows": len(eval_rows),
            "strict_rows": len(strict_rows),
            "manifest_rows": len(manifest_rows),
            "train_task_counts": dict(train_counter),
            "train_target_label_counts_top20": dict(label_counter.most_common(20)),
        },
        "hypothesis": "Verifier-status and continue/stop failures persist because scarce VERIFIER_REMOVED, INSUFFICIENT_EVIDENCE, and NOT_EXERCISED statuses are under-trained.",
        "intervention": "Initialize from Stage11924, preserve against Stage11924, train only semantic candidate head on Stage11958 train rows with verifier-value listwise pressure.",
        "promotion_gate": {
            "old_transition_640": ">=364/640",
            "stage11958_validation": "improve over Stage11924 and preserve clean rows",
            "stage11958_strict": "improve over Stage11924 and preserve clean rows",
            "filtered_strict": "22/22",
            "old_canary_strict": "23/23",
            "residual_bank": ">=7/10",
            "source_heldout_smoke": ">=6/12",
        },
        "source_artifacts": {
            "support_rows": rel(SUPPORT_ROWS),
            "manifest": rel(MANIFEST),
            "initialize_from_runtime_model": rel(INIT_RUNTIME),
            "preservation_reference_runtime_model": rel(PRESERVATION_RUNTIME),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "command": rel(COMMAND_JSON),
            "output_dir": rel(OUTPUT_DIR),
            "runtime_dir": rel(RUNTIME_DIR),
        },
        "claim_boundary": [
            "This is a diagnostic train-support probe, not a source-heldout frontier claim.",
            "Counterfactual rows do not count as new roots.",
            "Promotion requires postrun routed audit plus same-manifest Gemma comparison if it beats 386/640.",
        ],
    }
    write_json(COMMAND_JSON, {"command": command})
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "passed": artifact["passed"], "row_counts": artifact["row_counts"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
