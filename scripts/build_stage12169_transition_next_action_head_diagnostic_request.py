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
NAME = "stage12169_transition_next_action_head_diagnostic_request"
OUT = ART / NAME
SUMMARY = OUT / "transition_next_action_head_diagnostic_request.json"
COMMAND_JSON = OUT / "training_command.json"
MANIFEST = OUT / "transition_next_action_head_diagnostic_manifest.jsonl"

BASE = ART / "stage11923_transition_listwise_head_only_probe_request/transition_listwise_head_only_manifest.jsonl"
EXPANSION = ART / "stage12155_selected_test_counterfactual_expansion_package/expanded_counterfactual_rows.jsonl"
FILTERED_VALIDATION = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl"
FILTERED_STRICT = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
INIT_RUNTIME = ART / "stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json"
PRESERVATION_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ART / "stage12170_transition_next_action_head_diagnostic_probe"
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


def split_of(row: dict[str, Any]) -> str:
    return str(row.get("split") or row.get("package_split") or "")


def target_value(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    return str(
        row.get("semantic_target_value")
        or row.get("target_value")
        or target.get("semantic_value")
        or target.get("decoder_text")
        or row.get("bounded_choice_target_label")
        or row.get("target_label")
        or ""
    )


def normalize_train_row(row: dict[str, Any], source: str) -> dict[str, Any]:
    out = dict(row)
    out["row_id"] = f"{row.get('row_id')}::stage12169_next_action_head"
    out["split"] = "train"
    out["package_split"] = "train"
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["stage12169_source"] = source
    out["stage12169_train_target"] = "transition_next_action_only"
    out["preservation_exempt"] = source == "stage12155_counterfactual_next_action"
    source_payload = dict(out.get("standalone_projection_source") or {})
    source_payload.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = source_payload
    # The bounded-decoder probe preflight requires the manifest loss mask to
    # normalize to decoder_ce only; bounded-choice aux is controlled by command
    # weights/source, not by adding custom loss-mask keys here.
    out["loss_mask"] = {"decoder_ce": True}
    return out


def protected_copy(row: dict[str, Any], split: str) -> dict[str, Any]:
    out = dict(row)
    out["split"] = split
    out["package_split"] = split
    out["stage12169_protected_eval"] = True
    out["loss_mask"] = {"decoder_ce": True}
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base_rows = read_jsonl(BASE)
    expansion_rows = read_jsonl(EXPANSION)
    eval_rows = [protected_copy(row, "eval") for row in read_jsonl(FILTERED_VALIDATION)]
    strict_rows = [protected_copy(row, "strict_eval") for row in read_jsonl(FILTERED_STRICT)]

    base_next_action = [
        normalize_train_row(row, "stage11923_transition_next_action_replay")
        for row in base_rows
        if split_of(row) == "train" and row.get("task_type") == "transition_next_action"
    ]
    expansion_next_action = [
        normalize_train_row(row, "stage12155_counterfactual_next_action")
        for row in expansion_rows
        if split_of(row) == "train" and row.get("task_type") == "transition_next_action"
    ]
    train_rows = base_next_action + expansion_next_action
    all_rows = train_rows + eval_rows + strict_rows

    ids = [row.get("row_id") for row in all_rows]
    duplicate_ids = sorted({row_id for row_id in ids if ids.count(row_id) > 1})
    if duplicate_ids:
        raise SystemExit(f"duplicate row ids: {duplicate_ids[:5]}")
    if any(row.get("task_type") != "transition_next_action" for row in train_rows):
        raise SystemExit("non-next_action train row found")

    write_jsonl(MANIFEST, all_rows)

    split_counts = Counter(split_of(row) for row in all_rows)
    train_lang_counts = Counter(row.get("language_family") for row in train_rows)
    train_root_counts = Counter(row.get("root_id") or row.get("source_root_id") for row in train_rows)
    train_source_counts = Counter(row.get("stage12169_source") for row in train_rows)
    target_counts = Counter(target_value(row) for row in train_rows)

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
        "conda", "run", "-n", "trellis",
        "python", str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
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
        "--max-train-rows", str(len(train_rows)),
        "--max-eval-rows", str(len(eval_rows)),
        "--max-strict-rows", str(len(strict_rows)),
        "--max-steps", "160",
        "--batch-size", "8",
        "--learning-rate", "5e-5",
        "--max-encoder-tokens", "768",
        "--max-decoder-tokens", "16",
        "--decoder-ce-weight", "0.0",
        "--bounded-choice-aux-weight", "3.0",
        "--bounded-choice-root-group-aux-weight", "0.0",
        "--bounded-choice-aux-source", "encoder_option_retrieval_semantic_plus_transition_next_action_head",
        "--bounded-choice-train-head-only",
        "--bounded-decoder-train-sampler", "cyclic",
        "--bounded-choice-contrast-weight", "0.0",
        "--bounded-choice-contrast-margin", "0.08",
        "--bounded-choice-same-role-listwise-weight", "0.0",
        "--bounded-choice-verifier-value-listwise-weight", "0.0",
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
        "--preservation-reference-runtime-model", str(PRESERVATION_RUNTIME),
        "--preservation-kl-weight", "4.0",
        "--no-final-checkpoint-export",
        "--output-dir", str(OUTPUT_DIR),
    ]

    gates = {
        "base_manifest_exists": BASE.exists(),
        "expansion_manifest_exists": EXPANSION.exists(),
        "init_runtime_exists": INIT_RUNTIME.exists(),
        "preservation_runtime_exists": PRESERVATION_RUNTIME.exists(),
        "train_rows_next_action_only": all(row.get("task_type") == "transition_next_action" for row in train_rows),
        "base_next_action_rows_160": len(base_next_action) == 160,
        "expansion_next_action_rows_36": len(expansion_next_action) == 36,
        "four_train_languages_present": len(train_lang_counts) == 4,
        "train_roots_at_least_9": len(train_root_counts) >= 9,
        "target_diversity_at_least_4": len(target_counts) >= 4,
        "protected_eval_rows_22": len(eval_rows) == 22,
        "protected_strict_rows_22": len(strict_rows) == 22,
        "gpu2_only_command": "CUDA_VISIBLE_DEVICES=2" in command and "NVIDIA_VISIBLE_DEVICES=2" in command,
        "new_next_action_source_selected": "encoder_option_retrieval_semantic_plus_transition_next_action_head" in command,
        "head_only_enabled": "--bounded-choice-train-head-only" in command,
        "no_richer_losses_claimed": "0.0" in command,
    }

    request = {
        "stage": NAME,
        "created_at_utc": now(),
        "decision": "request_only_ready_for_guarded_stage12170_execution" if all(gates.values()) else "blocked_before_training",
        "execute_now": False,
        "training_allowed_by_request": False,
        "promotion_eligible": False,
        "claim_boundary": "Diagnostic request only. It tests whether a frozen-semantic, task-specific transition_next_action residual head can avoid Stage12160/12165 shared-head interference.",
        "command": command,
        "command_json": rel(COMMAND_JSON),
        "manifest": rel(MANIFEST),
        "run_dir": rel(RUN_DIR),
        "runtime_output": rel(RUNTIME_DIR),
        "probe_output": rel(OUTPUT_DIR),
        "source_artifacts": {
            "base_manifest": rel(BASE),
            "expansion_manifest": rel(EXPANSION),
            "filtered_validation": rel(FILTERED_VALIDATION),
            "filtered_strict": rel(FILTERED_STRICT),
            "initialize_from_runtime_model": rel(INIT_RUNTIME),
            "preservation_reference_runtime_model": rel(PRESERVATION_RUNTIME),
        },
        "row_counts": {
            "total_rows": len(all_rows),
            "train_rows": len(train_rows),
            "eval_rows": len(eval_rows),
            "strict_rows": len(strict_rows),
            "base_next_action_train_rows": len(base_next_action),
            "expansion_next_action_train_rows": len(expansion_next_action),
            "train_unique_roots": len(train_root_counts),
        },
        "train_language_counts": dict(sorted(train_lang_counts.items())),
        "train_source_counts": dict(sorted(train_source_counts.items())),
        "train_target_counts": dict(sorted(target_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "gates_before_execution": gates,
        "promotion_or_rejection_gates_after_execution": {
            "reject_if_transition_total_below_stage11924_364": True,
            "reject_if_transition_next_action_below_stage11924_51": True,
            "reject_if_stage12099_route_375_not_matched_or_explained": True,
            "reject_if_filtered_strict_below_22_22": True,
            "reject_if_filtered_validation_below_20_22": True,
            "reject_if_old_canary_strict_below_23_23": True,
            "reject_if_old_canary_validation_below_21_23": True,
            "reject_if_residual_below_7_10": True,
            "reject_if_source_heldout_smoke_below_6_12": True,
        },
        "why_this_avoids_prior_failure_mode": [
            "Only transition_next_action rows are trainable; candidate_selection/continue/verifier rows are not included in train.",
            "The new source applies bounded_choice_transition_next_action_head only when task_type is transition_next_action.",
            "Head-only training updates only bounded_choice_transition_next_action_head for the semantic_plus source; the semantic candidate head remains frozen.",
            "Richer contrast/listwise losses are set to zero because this request is testing scorer isolation first, not another mixed-objective support packet.",
        ],
        "training_executed": False,
    }
    write_json(COMMAND_JSON, {"command": command})
    write_json(SUMMARY, request)
    write_json(OUT / "summary.json", request)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": request["decision"], "row_counts": request["row_counts"], "target_counts": request["train_target_counts"], "gates_passed": all(gates.values())}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
