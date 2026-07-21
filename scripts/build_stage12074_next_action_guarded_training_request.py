#!/usr/bin/env python3
"""Build Stage12074 guarded next-action transition training request.

This is a request/package stage only. It combines:
- Stage11923 old transition replay/eval/strict manifest,
- Stage12056 v35 verifier-status support rows with repaired option mirroring,
- Stage12073 admitted next-action support rows.

It does not execute training.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
STAGE = 12074
NAME = "stage12074_next_action_guarded_training_request"
OUT = REPO / "runs" / "local" / "artifacts" / NAME
SUMMARIES = REPO / "runs" / "summaries"
SUMMARY = OUT / "next_action_guarded_training_request.json"
SUMMARY_MIRROR = SUMMARIES / f"{NAME}.json"
MANIFEST = OUT / "next_action_guarded_training_manifest.jsonl"
COMMAND_JSON = OUT / "next_action_guarded_training_command.json"

BASE_MANIFEST = REPO / "runs/local/artifacts/stage11923_transition_listwise_head_only_probe_request/transition_listwise_head_only_manifest.jsonl"
V35_ROWS = REPO / "runs/local/artifacts/stage12056_transition_support_rollup_v35/transition_support_rows_v35.jsonl"
V35_AUDIT = REPO / "runs/local/artifacts/stage12057_transition_support_v35_audit/transition_support_v35_audit.json"
NEXT_ACTION_ROWS = REPO / "runs/local/artifacts/stage12073_next_action_support_materializer/next_action_support_rows.jsonl"
NEXT_ACTION_AUDIT = REPO / "runs/summaries/stage12073_next_action_support_materializer.json"
INIT_RUNTIME = REPO / "runs/local/artifacts/stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json"
PRESERVE_RUNTIME = REPO / "runs/local/artifacts/stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
RUNTIME_DIR = REPO / "runs/local/artifacts/stage12075_next_action_guarded_training_probe/runtime_model"
OUTPUT_DIR = REPO / "runs/local/artifacts/stage12075_next_action_guarded_training_probe/bounded_decoder_probe"
TRAIN_SCRIPT = REPO / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = REPO / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = REPO / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = REPO / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = REPO / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"


def rel(path: Path) -> str:
    return str(path.relative_to(REPO))


def load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def split_of(row: dict[str, Any]) -> str:
    return str(row.get("split") or row.get("package_split") or "")


def normalize_support_row(row: dict[str, Any], suffix: str, source: str) -> dict[str, Any]:
    r = dict(row)
    r["split"] = "train"
    r["package_split"] = "train"
    r["train_support_only"] = True
    r["strict_eval_eligible"] = False
    r["source_heldout_admissible"] = False
    r["stage12074_support_source"] = source
    r["stage12074_train_support_only"] = True
    mask = r.get("loss_mask")
    if not isinstance(mask, dict) or not any(bool(v) for v in mask.values()):
        r["loss_mask"] = {
            "bounded_choice_aux": True,
            "decoder_ce": True,
            "structured_aux": True,
            "transition_projection": True,
        }
        r["stage12074_loss_mask_normalized"] = True
    opts = r.get("opaque_options") or []
    sp = dict(r.get("standalone_projection_source") or {})
    if opts and not sp.get("opaque_options"):
        sp["opaque_options"] = opts
        target = r.get("target") or {}
        sp.setdefault("gold_label", target.get("bounded_choice_target_label") or r.get("target_label"))
        sp.setdefault("gold_value", target.get("semantic_value") or target.get("decoder_text"))
        r["standalone_projection_source"] = sp
        r["stage12074_option_mirror_repaired"] = True
    r["row_id"] = f"{r['row_id']}::{suffix}"
    return r


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SUMMARIES.mkdir(parents=True, exist_ok=True)

    base_rows = read_jsonl(BASE_MANIFEST)
    v35_rows = read_jsonl(V35_ROWS)
    next_action_rows = read_jsonl(NEXT_ACTION_ROWS)
    v35_audit = load_json(V35_AUDIT)
    next_action_audit = load_json(NEXT_ACTION_AUDIT)

    old_train = [r for r in base_rows if split_of(r) == "train"]
    eval_rows = [r for r in base_rows if split_of(r) == "eval"]
    strict_rows = [r for r in base_rows if split_of(r) == "strict_eval"]

    replay_rows = []
    for row in old_train:
        r = dict(row)
        r["stage12074_replay_source"] = "stage11923_transition_listwise_head_only_manifest"
        r["row_id"] = f"{r['row_id']}::stage12074_old640_replay"
        replay_rows.append(r)

    verifier_support = [normalize_support_row(r, "stage12074_v35_support", "stage12056_transition_support_v35") for r in v35_rows]
    next_action_support = [normalize_support_row(r, "stage12074_next_action_support", "stage12073_next_action_support") for r in next_action_rows]

    manifest_rows = replay_rows + verifier_support + next_action_support + eval_rows + strict_rows
    write_jsonl(MANIFEST, manifest_rows)

    train_rows = replay_rows + verifier_support + next_action_support
    counts_by_split = collections.Counter(split_of(r) for r in manifest_rows)
    train_task_counts = collections.Counter(r.get("task_type", "unknown") for r in train_rows)
    train_target_counts = collections.Counter(
        (r.get("target") or {}).get("semantic_value")
        or r.get("standalone_projection_source", {}).get("gold_value")
        or "UNKNOWN"
        for r in train_rows
    )
    language_counts = collections.Counter(r.get("language_family", "unknown") for r in next_action_support)
    option_mirror_missing = sum(1 for r in train_rows if r.get("opaque_options") and not r.get("standalone_projection_source", {}).get("opaque_options"))
    unsafe_loss_masks = sum(1 for r in train_rows if not any(bool(v) for v in (r.get("loss_mask") or {}).values()))

    command = [
        "env",
        "CUDA_VISIBLE_DEVICES=2",
        "NVIDIA_VISIBLE_DEVICES=2",
        "AGENTKERNEL_EVAL_DEVICE=cuda:0",
        "AGENTKERNEL_TRAIN_DEVICE=cuda:0",
        "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True",
        "TMPDIR=/data/tmp",
        "TEMP=/data/tmp",
        "TMP=/data/tmp",
        "conda", "run", "-n", "trellis", "python", str(TRAIN_SCRIPT),
        "--repo-root", str(REPO),
        "--manifest", str(MANIFEST),
        "--mode", "bounded_decoder_ce_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG),
        "--tokenizer-json", str(TOKENIZER_JSON),
        "--tokenizer-config", str(TOKENIZER_CONFIG),
        "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows", str(counts_by_split["train"]),
        "--max-eval-rows", str(counts_by_split["eval"]),
        "--max-strict-rows", str(counts_by_split["strict_eval"]),
        "--max-steps", "768",
        "--batch-size", "8",
        "--learning-rate", "8e-5",
        "--max-encoder-tokens", "768",
        "--max-decoder-tokens", "16",
        "--decoder-ce-weight", "0.0",
        "--bounded-choice-aux-weight", "3.0",
        "--bounded-choice-root-group-aux-weight", "0.0",
        "--bounded-choice-aux-source", "encoder_option_retrieval_semantic_candidate_head",
        "--bounded-choice-train-head-only",
        "--bounded-decoder-train-sampler", "task_balanced",
        "--bounded-choice-contrast-weight", "0.4",
        "--bounded-choice-contrast-margin", "0.08",
        "--bounded-choice-same-role-listwise-weight", "0.5",
        "--bounded-choice-verifier-value-listwise-weight", "0.7",
        "--structured-aux-weight", "0.0",
        "--denoise-weight", "0.0",
        "--eos-loss-weight", "1.0",
        "--enable-generation-audit",
        "--max-generation-rows", "8",
        "--max-generation-tokens", "8",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir", str(RUNTIME_DIR),
        "--initialize-from-runtime-model", str(INIT_RUNTIME),
        "--preservation-reference-runtime-model", str(PRESERVE_RUNTIME),
        "--preservation-kl-weight", "4.0",
        "--no-final-checkpoint-export",
        "--output-dir", str(OUTPUT_DIR),
    ]
    write_json(COMMAND_JSON, command)

    gates = {
        "base_manifest_exists": BASE_MANIFEST.exists(),
        "v35_rows_exists": V35_ROWS.exists(),
        "next_action_rows_exists": NEXT_ACTION_ROWS.exists(),
        "init_runtime_exists": INIT_RUNTIME.exists(),
        "preservation_runtime_exists": PRESERVE_RUNTIME.exists(),
        "splits_expected": counts_by_split == {"train": 1151, "eval": 22, "strict_eval": 22},
        "v35_floor_audit_train_ready": bool(v35_audit.get("train_ready_against_floor_and_hard_audit")),
        "next_action_gate_passed": bool(next_action_audit.get("audit", {}).get("passes_minimum_training_gate")),
        "option_mirror_missing_zero": option_mirror_missing == 0,
        "unsafe_loss_masks_zero": unsafe_loss_masks == 0,
        "uses_gpu2_mask": "CUDA_VISIBLE_DEVICES=2" in command and "NVIDIA_VISIBLE_DEVICES=2" in command,
        "head_only_enabled": "--bounded-choice-train-head-only" in command,
    }
    passed = all(gates.values())

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "next_action_guarded_training_request_ready" if passed else "next_action_guarded_training_request_blocked",
        "passed": passed,
        "execute_now": False,
        "hypothesis": "Adding admitted next-action support to old transition replay and v35 verifier-status support can improve the 51/160 next-action bottleneck without losing protected compact gates.",
        "claim_boundary": [
            "This is a request artifact only, not model progress.",
            "Stage12073 rows are train-support-only; promotion requires postrun routed audit.",
            "The selected transition frontier remains Stage11924 until a runtime beats 364/640 and preserves gates.",
        ],
        "row_counts": {
            "train_rows": counts_by_split["train"],
            "old_transition_replay_train_rows": len(replay_rows),
            "v35_verifier_support_rows": len(verifier_support),
            "stage12073_next_action_support_rows": len(next_action_support),
            "eval_rows": counts_by_split["eval"],
            "strict_rows": counts_by_split["strict_eval"],
            "train_task_counts": dict(sorted(train_task_counts.items())),
            "train_target_counts_top20": dict(train_target_counts.most_common(20)),
            "next_action_support_language_counts": dict(sorted(language_counts.items())),
            "option_mirror_missing": option_mirror_missing,
            "unsafe_loss_masks": unsafe_loss_masks,
        },
        "gates_before_execution": gates,
        "promotion_gate": {
            "old_transition_manifest_correct": ">364/640 for progress; >386/640 for same-manifest Gemma win",
            "transition_next_action": ">51/160 required for targeted improvement",
            "protected_filtered_strict": "22/22",
            "protected_filtered_validation": ">=20/22",
            "protected_old_canary_strict": "23/23",
            "protected_old_canary_validation": ">=21/23",
            "protected_residual_bank": ">=7/10",
            "source_heldout_smoke": ">=6/12 retained; >6/12 for transfer progress",
        },
        "training_controls": {
            "gpu": "cuda:2 only via CUDA_VISIBLE_DEVICES=2/NVIDIA_VISIBLE_DEVICES=2 and AGENTKERNEL_*_DEVICE=cuda:0",
            "environment": "conda run -n trellis",
            "init_runtime": rel(INIT_RUNTIME),
            "preservation_reference_runtime": rel(PRESERVE_RUNTIME),
            "head_only": True,
            "sampler": "task_balanced",
            "preservation_kl_weight": 4.0,
            "bounded_choice_aux_source": "encoder_option_retrieval_semantic_candidate_head",
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "summary_mirror": rel(SUMMARY_MIRROR),
            "manifest": rel(MANIFEST),
            "command": rel(COMMAND_JSON),
            "runtime_dir": rel(RUNTIME_DIR),
            "output_dir": rel(OUTPUT_DIR),
        },
        "source_artifacts": {
            "base_stage11923_manifest": rel(BASE_MANIFEST),
            "v35_support_rows": rel(V35_ROWS),
            "v35_audit": rel(V35_AUDIT),
            "stage12073_next_action_rows": rel(NEXT_ACTION_ROWS),
            "stage12073_audit": rel(NEXT_ACTION_AUDIT),
        },
        "next_stage_if_executed": "stage12075_next_action_guarded_training_probe",
        "next_stage_after_execution": "stage12076_next_action_guarded_training_postrun_audit",
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps({"passed": passed, "summary": rel(SUMMARY), "manifest_rows": len(manifest_rows), "train_rows": counts_by_split["train"]}, indent=2))


if __name__ == "__main__":
    main()
