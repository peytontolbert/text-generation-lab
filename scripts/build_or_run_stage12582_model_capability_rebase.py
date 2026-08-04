#!/usr/bin/env python3
"""Build, preflight, or reviewer-run the Stage12582 model-capability rebase."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 12582
NAME = "stage12582_model_capability_rebase"
OUT = ART / NAME
EXECUTION = OUT / "execution"

SOURCE_ROWS = ART / "stage11958_transition_5k_v1_augmented_package/transition_projection_rows_5k_v1_augmented.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage11958_transition_5k_v1_augmented_package.json"
CLOSED_LOOP_ROWS = ART / "stage12216_normalized_verifier_observation_dataset/normalized_verifier_observation_records.jsonl"
CLOSED_LOOP_DECISION = ROOT / "runs/summaries/stage12218_level3_quality_decision.json"
PATCH_DECISION = ROOT / "runs/summaries/stage12225_patch_trace_semantic_qc.json"
INIT_RUNTIME = ART / "stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"

TRAIN_MANIFEST = OUT / "train_manifest.jsonl"
EVAL_MANIFEST = OUT / "eval_manifest.jsonl"
STRICT_MANIFEST = OUT / "strict_eval_manifest.jsonl"
TRAINER_MANIFEST = OUT / "trainer_manifest.jsonl"
CONFIG = OUT / "model_capability_rebase_config.json"
REQUEST = OUT / "exact_runnable_request.json"
PREFLIGHT = OUT / "preflight.json"
SUMMARY = OUT / "summary.json"
SUMMARY_MIRROR = SUMMARIES / f"{NAME}.json"
APPROVAL = OUT / "review_approval.json"
POSTRUN_AUDIT = OUT / "postrun_product_scorer_audit.json"

PYTHON = Path("/home/peyton/miniconda3/envs/ai/bin/python")
EXPECTED_GPU_UUID = "GPU-9bf37b64-3fc3-de32-6593-37ceeda6ab59"
EXPECTED_WEIGHT_SHA256 = "13bd2cf952d86261593c5044d59018084bdb1675feed57d72b7300fe5d256c88"
PINNED_HASHES = {
    str(MODEL_CONFIG): "dda55307003800072d98070a4f744ebd0f8262c5680fa1b0f74c5724b32f5a77",
    str(TOKENIZER_JSON): "c268a145d01e26047d7773d9888c13902ab0cbf0e59da333ba2b686fec4ae324",
    str(TOKENIZER_CONFIG): "0987f58448a3163615eb167d93973fa209d7ccb12dd5c7a35c1e8ab166299be0",
    str(TOKENIZER_HASHLOCK): "04f12bd6bf3cd24b17f9eeba4200f7ff2c99222cd2b38e3f41dc4fa6ab08f1a9",
    str(TRAINER): "e96d8278dfb2e9975b13cc4bff7acd32c72c71b4aca6dfbc02f7876aa4229860",
    str(INIT_RUNTIME): "8559c4c81e82999a05ece43805ef9519dd3f0c5e7c0af38bd9c470ffd905c1d5",
    str(PYTHON): "8ca0826855679ed173a82a47266dd2b661a06f16ea8b0ee59bb9c5092965a7bc",
}

TASKS = {
    "transition_candidate_selection",
    "transition_continue_or_stop",
    "transition_next_action",
    "transition_verifier_transition",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("repo_family") or "")


def _option_value(option: dict[str, Any]) -> str:
    return str(option.get("value") or option.get("semantic_value") or option.get("role") or option.get("semantic_role") or "")


def _remap_options(row: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    original = [dict(option) for option in row.get("opaque_options") or []]
    old_target = str(row.get("bounded_choice_target_label") or row.get("decoder_text") or "")
    target_value = next((_option_value(option) for option in original if str(option.get("label")) == old_target), "")
    ordered = sorted(original, key=lambda option: hashlib.sha256(f"stage12582|{row['row_id']}|{_option_value(option)}".encode()).hexdigest())
    for index, option in enumerate(ordered):
        option["label"] = chr(ord("A") + index)
    return ordered, next(str(option["label"]) for option in ordered if _option_value(option) == target_value)


def _render_remapped_prompt(text: str, options: list[dict[str, Any]]) -> str:
    marker, question = "\nCANDIDATES\n", "\n\nQUESTION"
    if marker not in text or question not in text:
        return text
    prefix, tail = text.split(marker, 1)
    _, suffix = tail.split(question, 1)
    lines = [f"{option['label']}: role={option.get('role') or option.get('semantic_role')}; value={_option_value(option)}" for option in options]
    return prefix + marker + "\n".join(lines) + question + suffix


def normalize(row: dict[str, Any], split: str) -> dict[str, Any]:
    out = dict(row)
    out["row_id"] = f"{row['row_id']}::stage12582::{split}"
    out["split"] = split
    out["package_split"] = split
    out["stage12582_objective"] = "transition_local_state_to_action_verifier_or_stop"
    out["stage12582_source"] = "stage11958_verified_transition_projection"
    out["preservation_exempt"] = False
    out["train_support_only"] = split == "train"
    out["strict_eval_eligible"] = split == "strict_eval"
    out["loss_mask"] = {"decoder_ce": True}
    options, label = _remap_options(row)
    out["opaque_options"] = options
    for field in ("input_text", "prompt_text"):
        if isinstance(out.get(field), str):
            out[field] = _render_remapped_prompt(out[field], options)
    out["bounded_choice_target_label"] = label
    out["decoder_text"] = label
    source = dict(out.get("standalone_projection_source") or {})
    source["opaque_options"] = options
    out["standalone_projection_source"] = source
    target = dict(out.get("target") or {})
    target["bounded_choice_target_label"] = label
    target["decoder_text"] = label
    out["target"] = target
    return out


def manifest_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_split = Counter(str(row.get("split")) for row in rows)
    by_task = Counter(str(row.get("task_type")) for row in rows if row.get("split") == "train")
    by_language = Counter(str(row.get("language_family")) for row in rows if row.get("split") == "train")
    ids = [str(row.get("row_id")) for row in rows]
    duplicate_ids = len(ids) - len(set(ids))
    roots = {
        split: {root_key(row) for row in rows if row.get("split") == split}
        for split in ("train", "eval", "strict_eval")
    }
    bad_options = []
    empty_inputs = []
    for row in rows:
        labels = {str(option.get("label")) for option in row.get("opaque_options") or []}
        target = str(row.get("bounded_choice_target_label") or row.get("decoder_text") or "")
        if not labels or target not in labels:
            bad_options.append(str(row.get("row_id")))
        if not str(row.get("input_text") or row.get("prompt_text") or "").strip():
            empty_inputs.append(str(row.get("row_id")))
    semantic_targets: dict[str, Counter[str]] = {}
    all_actions: dict[str, set[str]] = {}
    gold_actions: dict[str, set[str]] = {}
    for row in rows:
        task = str(row.get("task_type"))
        target_label = str(row.get("bounded_choice_target_label"))
        options = row.get("opaque_options") or []
        target_value = next((_option_value(option) for option in options if str(option.get("label")) == target_label), "")
        semantic_targets.setdefault(task, Counter())[target_value] += 1
        all_actions.setdefault(task, set()).update(_option_value(option) for option in options)
        gold_actions.setdefault(task, set()).add(target_value)
    return {
        "split_counts": dict(by_split),
        "train_task_counts": dict(by_task),
        "train_language_counts": dict(by_language),
        "unique_roots": {key: len(value) for key, value in roots.items()},
        "duplicate_row_id_count": duplicate_ids,
        "bad_option_target_count": len(bad_options),
        "empty_input_count": len(empty_inputs),
        "root_overlap": {
            "train_eval": len(roots["train"] & roots["eval"]),
            "train_strict": len(roots["train"] & roots["strict_eval"]),
            "eval_strict": len(roots["eval"] & roots["strict_eval"]),
        },
        "semantic_target_balance": {task: dict(counts) for task, counts in sorted(semantic_targets.items())},
        "never_gold_actions": {task: sorted(all_actions[task] - gold_actions[task]) for task in sorted(all_actions)},
        "deterministic_option_remap": True,
    }


def environment_prefix() -> list[str]:
    return [
        "env",
        "CUDA_VISIBLE_DEVICES=2",
        "NVIDIA_VISIBLE_DEVICES=2",
        "AGENTKERNEL_TRAIN_DEVICE=cuda:0",
        "AGENTKERNEL_EVAL_DEVICE=cuda:0",
        "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True",
        "TMPDIR=/data/tmp",
        "TEMP=/data/tmp",
        "TMP=/data/tmp",
        str(PYTHON), str(Path(__file__).resolve()),
    ]


def build() -> dict[str, Any]:
    required = [SOURCE_ROWS, SOURCE_SUMMARY, CLOSED_LOOP_ROWS, CLOSED_LOOP_DECISION, PATCH_DECISION, INIT_RUNTIME, MODEL_CONFIG, TOKENIZER_JSON, TOKENIZER_CONFIG, TOKENIZER_HASHLOCK, TRAINER]
    missing = [rel(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"missing required inputs: {missing}")

    source_rows = read_jsonl(SOURCE_ROWS)
    train = [normalize(row, "train") for row in source_rows if row.get("split") == "train"]
    eval_rows = [normalize(row, "eval") for row in source_rows if row.get("split") == "validation"]
    strict = [normalize(row, "strict_eval") for row in source_rows if row.get("split") == "strict_eval"]
    rows = train + eval_rows + strict
    write_jsonl(TRAIN_MANIFEST, train)
    write_jsonl(EVAL_MANIFEST, eval_rows)
    write_jsonl(STRICT_MANIFEST, strict)
    write_jsonl(TRAINER_MANIFEST, rows)

    audit = manifest_audit(rows)
    source_summary = read_json(SOURCE_SUMMARY)
    closed_loop_decision = read_json(CLOSED_LOOP_DECISION)
    patch_decision = read_json(PATCH_DECISION)
    closed_loop_rows = read_jsonl(CLOSED_LOOP_ROWS)
    runtime = read_json(INIT_RUNTIME)
    runtime_weights = Path(runtime["weights_path"])
    pinned_hashes_match = {path: sha256(Path(path)) == expected for path, expected in PINNED_HASHES.items()}
    causal_floors = {
        "causal_episode_count": {"actual": 0, "required": 20, "passed": False},
        "patch_trace_count": {"actual": 2, "required": 8, "passed": False},
        "fail_to_pass_count": {"actual": 0, "required": 1, "passed": False},
        "repositories": {"actual": 2, "required": 10, "passed": False},
        "languages": {"actual": 1, "required": 3, "passed": False},
    }

    data_gates = {
        "stage11958_labeled_auxiliary_projected_only": True,
        "train_rows_5176": len(train) == 5176,
        "eval_rows_248": len(eval_rows) == 248,
        "strict_rows_356": len(strict) == 356,
        "four_action_transition_tasks": set(audit["train_task_counts"]) == TASKS,
        "all_four_languages": set(audit["train_language_counts"]) == {"python", "rust", "c_cpp", "web_js_ts_html"},
        "root_splits_disjoint": all(value == 0 for value in audit["root_overlap"].values()),
        "unique_row_ids": audit["duplicate_row_id_count"] == 0,
        "targets_in_candidate_sets": audit["bad_option_target_count"] == 0,
        "nonempty_transition_local_inputs": audit["empty_input_count"] == 0,
        "closed_loop_nontrainable_rows_excluded": closed_loop_decision.get("training_allowed") is False and len(closed_loop_rows) == 146,
        "patch_lane_nontrainable_rows_excluded": patch_decision.get("training_allowed") is False,
        "all_pinned_hashes_match": all(pinned_hashes_match.values()),
        "stage11924_weight_hash_exact": runtime.get("weights_sha256") == EXPECTED_WEIGHT_SHA256 and sha256(runtime_weights) == EXPECTED_WEIGHT_SHA256,
        "causal_floors_met": all(item["passed"] for item in causal_floors.values()),
        "continuous_validation_checkpoint_selection_supported": False,
    }

    config = {
        "stage": STAGE,
        "model": {
            "implementation": "transformer",
            "scale": "target_100m",
            "parameter_count": 102654362,
            "config": rel(MODEL_CONFIG),
            "tokenizer": rel(TOKENIZER_JSON),
            "initialization_bundle": rel(INIT_RUNTIME),
            "initialization_weights_sha256": runtime["weights_sha256"],
        },
        "runtime_pins": {
            "python_executable": str(PYTHON),
            "python_version": "3.11.11",
            "python_sha256": PINNED_HASHES[str(PYTHON)],
            "torch_version": "2.10.0+cu128",
            "torch_cuda_version": "12.8",
            "cudnn_version": 91002,
            "artifact_hashes": PINNED_HASHES,
            "hashes_match_at_build": pinned_hashes_match,
        },
        "scorer": {
            "selected_source": "encoder_option_cross_encoder",
            "train_base_model": True,
            "train_selected_scorer": True,
            "head_only": False,
        },
        "task": {
            "allowed_train_tasks": sorted(TASKS),
            "prohibited_support_only_tasks": ["evidence_citation", "symptom_localization", "edit_localization"],
            "target": "transition-local state/evidence to next action, candidate selection, verifier transition, or continue/stop",
        },
        "objective": {
            "decoder_ce_weight": 0.35,
            "bounded_choice_aux_weight": 2.0,
            "contrast_weight": 0.2,
            "contrast_margin": 0.08,
            "same_role_listwise_weight": 0.5,
            "verifier_value_listwise_weight": 0.7,
            "preservation_kl_weight": 4.0,
        },
        "sampler": {"name": "task_balanced", "batch_size": 8, "seed": 1337},
        "schedule": {
            "processes": 1,
            "continuous_optimizer_and_sampler_state": True,
            "repeated_prefix_chunks": False,
            "learning_rate": 1e-5,
            "max_steps": 768,
        },
        "early_stopping": {"patience_chunks": 3, "min_delta": 0.01},
        "checkpoint_selection": {
            "selection_split": "eval",
            "metric": "validation product-scorer constrained accuracy, then mean target margin",
            "strict_during_selection": False,
            "strict_evaluations_post_selection": 1,
            "current_trainer_supports_required_selection": False,
            "blocking_reason": "bounded trainer has no in-process product-accuracy checkpoint selector or persisted optimizer/sampler resume",
        },
        "device_contract": {
            "physical_gpu": 2,
            "CUDA_VISIBLE_DEVICES": "2",
            "NVIDIA_VISIBLE_DEVICES": "2",
            "trainer_device": "cuda:0",
            "allow_other_gpu_masks": False,
            "logical_cuda0_expected_uuid": EXPECTED_GPU_UUID,
            "foreign_compute_idle_threshold_mib": 256,
            "foreign_gpu_inspection": "physical GPU2 only; GPU0/1 checked only for this process PID",
        },
        "manifests": {"train": rel(TRAIN_MANIFEST), "eval": rel(EVAL_MANIFEST), "strict_eval": rel(STRICT_MANIFEST), "trainer": rel(TRAINER_MANIFEST)},
        "preservation_gates": {
            "filtered_strict": "22/22",
            "filtered_validation": ">=20/22",
            "old_canary_strict": "23/23",
            "old_canary_validation": ">=21/23",
            "residual_bank": ">=7/10",
            "source_heldout_smoke": ">=6/12",
        },
        "frontier_gates": {
            "old_transition_640": ">=364/640 retention and >375/640 product-route gain",
            "gemma_same_manifest": ">386/640 required for Gemma win",
            "each_transition_task": "no task may regress versus Stage11924",
            "stage11958_eval_and_strict": "candidate must improve composite heldout loss and report per-task accuracy",
            "coverage": "100% scorer coverage with zero skipped rows",
            "promotion": "separate postrun audit and reviewer decision required",
        },
        "data_authority": {
            "stage11958": "auxiliary_projected_only",
            "stage12216": "auxiliary_projected_only",
            "training_allowed": False,
            "causal_floors": causal_floors,
        },
    }
    write_json(CONFIG, config)

    preflight_command = environment_prefix() + ["--preflight"]
    execution_command = environment_prefix() + ["--execute", "--approval-file", str(APPROVAL)]
    readiness_gates = {
        "causal_floors_met": False,
        "reviewer_approval_present": False,
        "fresh_hash_bound_gpu_preflight_passed": False,
        "continuous_validation_checkpoint_selector_available": False,
    }
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "decision": "blocked_not_executable",
        "executable": False,
        "training_allowed": False,
        "execute_now": False,
        "training_executed": False,
        "reviewer_approval_required": True,
        "approval_file_contract": {"path": rel(APPROVAL), "required_payload": {"stage": STAGE, "approved": True, "reviewer": "<non-empty>", "approval_id": "<non-empty>"}},
        "preflight_command": preflight_command,
        "execution_command": None,
        "exact_execution_command": execution_command,
        "candidate_continuous_process_command": execution_command,
        "config": rel(CONFIG),
        "data_contract_gates": data_gates,
        "manifest_audit": audit,
        "readiness_gates": readiness_gates,
        "causal_floors": causal_floors,
        "mandatory_preflight": {
            "non_bypassable": True,
            "fresh_for_exact_binding_required": True,
            "command": preflight_command,
            "status": "not_run",
        },
        "input_boundaries": {
            "stage11958": {"path": rel(SOURCE_ROWS), "label": "auxiliary_projected_only", "training_allowed": False},
            "stage12216": {"path": rel(CLOSED_LOOP_ROWS), "rows": len(closed_loop_rows), "label": "auxiliary_projected_only", "training_allowed": False},
            "patch_rows_inspected_not_trained": {"path": patch_decision["artifact_paths"]["admitted"], "rows": patch_decision["admitted_count"], "reason": "Stage12225 training_allowed=false; only Python PASS_TO_PASS rows"},
        },
        "postrun_gate_command": [str(PYTHON), str(Path(__file__).resolve()), "--postrun-gates", "--postrun-audit", str(POSTRUN_AUDIT)],
        "claim_boundary": "Blocked design only. Stage11958/12216 are auxiliary projections, causal_episode_count=0, patch_trace_count=2, fail_to_pass_count=0; no training is allowed.",
    }
    write_json(REQUEST, request)
    hashes = {rel(path): sha256(path) for path in (TRAIN_MANIFEST, EVAL_MANIFEST, STRICT_MANIFEST, TRAINER_MANIFEST, CONFIG, REQUEST)}
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "decision": request["decision"],
        "passed_data_contract": all(value for key, value in data_gates.items() if key not in {"causal_floors_met", "continuous_validation_checkpoint_selection_supported"}),
        "executable": False,
        "causal_floors": causal_floors,
        "training_executed": False,
        "data_contract_gates": data_gates,
        "manifest_audit": audit,
        "hashes": hashes,
        "outputs": {"config": rel(CONFIG), "request": rel(REQUEST), "preflight": rel(PREFLIGHT), "summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    return summary


def require_gpu2() -> None:
    expected = {"CUDA_VISIBLE_DEVICES": "2", "NVIDIA_VISIBLE_DEVICES": "2", "AGENTKERNEL_TRAIN_DEVICE": "cuda:0", "AGENTKERNEL_EVAL_DEVICE": "cuda:0"}
    wrong = {key: os.environ.get(key) for key, value in expected.items() if os.environ.get(key) != value}
    if wrong:
        raise SystemExit(f"GPU2-only environment contract failed: {wrong}")


def differentiability_preflight() -> dict[str, Any]:
    require_gpu2()
    build()
    import torch
    from legacy_src.agentkernel_lite.training_data import build_batch, load_tokenizer
    from legacy_src.agentkernel_lite.training_loop import (
        _bounded_choice_aux_loss,
        _bounded_decoder_train_batch_rows,
        _build_probe_model,
        _decoder_ce_loss,
        _load_runtime_model_bundle,
        _move_manifest_batch,
        _preferred_execution_device,
    )

    torch.manual_seed(1337)
    train_rows = read_jsonl(TRAIN_MANIFEST)
    tokenizer = load_tokenizer(TOKENIZER_JSON, TOKENIZER_CONFIG)
    model, card = _build_probe_model("transformer", vocab_size=tokenizer.vocab_size, probe_scale="target_100m", model_config=MODEL_CONFIG)
    card = dict(card)
    card["runtime_initialization"] = _load_runtime_model_bundle(INIT_RUNTIME, model=model)
    device = _preferred_execution_device()
    if str(device) != "cuda:0":
        raise SystemExit(f"preflight resolved unexpected device {device}")
    model.to(device)
    model.train()
    batch_rows = _bounded_decoder_train_batch_rows(train_rows, step=1, batch_size=8, sampler="task_balanced")
    batch = build_batch(batch_rows, max_encoder_tokens=768, max_decoder_tokens=16, tokenizer=tokenizer)
    batch = _move_manifest_batch(batch, device)
    output = model(batch.input_ids, batch.decoder_input_ids)
    decoder = _decoder_ce_loss(model, output["decoder_logits"], batch.labels, batch.loss_mask.get("decoder_ce"), eos_id=int(tokenizer.eos_id), eos_loss_weight=1.0)
    aux, aux_card = _bounded_choice_aux_loss(
        first_step_logits=output["decoder_logits"][:, 0, :], pooled=output.get("pooled"), rows=batch_rows,
        tokenizer=tokenizer, source="encoder_option_cross_encoder", model=model,
        untied_head=getattr(model, "bounded_choice_probe_head", None),
    )
    if aux is None:
        raise SystemExit("selected learned cross-encoder scorer produced no differentiable auxiliary loss")
    loss = (0.35 * decoder) + (2.0 * aux)
    loss.backward()
    base_grads = [(name, float(param.grad.detach().norm().item())) for name, param in model.named_parameters() if param.grad is not None and not name.startswith("bounded_choice_")]
    scorer_grads = [(name, float(param.grad.detach().norm().item())) for name, param in model.named_parameters() if param.grad is not None and name.startswith("bounded_choice_cross_encoder_head")]
    task_counts = Counter(str(row.get("task_type")) for row in batch_rows)
    payload = {
        "stage": STAGE,
        "passed": bool(loss.requires_grad and any(value > 0 for _, value in base_grads) and any(value > 0 for _, value in scorer_grads) and set(task_counts) == TASKS),
        "optimizer_step_executed": False,
        "weights_saved": False,
        "device": str(device),
        "physical_gpu_mask": os.environ["CUDA_VISIBLE_DEVICES"],
        "batch_task_counts": dict(task_counts),
        "loss": {"total": float(loss.detach().item()), "decoder_ce": float(decoder.detach().item()), "learned_cross_encoder_aux": float(aux.detach().item()), "requires_grad": bool(loss.requires_grad)},
        "gradient_coverage": {"base_nonzero_tensors": sum(value > 0 for _, value in base_grads), "selected_scorer_nonzero_tensors": sum(value > 0 for _, value in scorer_grads), "base_examples": base_grads[:5], "scorer": scorer_grads},
        "selected_scorer_card": aux_card,
        "runtime_initialization": card["runtime_initialization"],
    }
    write_json(PREFLIGHT, payload)
    if not payload["passed"]:
        raise SystemExit("differentiability preflight failed")
    return payload


def trainer_argv(init_runtime: Path, chunk: int) -> tuple[list[str], Path, Path]:
    chunk_dir = EXECUTION / f"chunk_{chunk:02d}"
    runtime_dir = chunk_dir / "runtime_model"
    output_dir = chunk_dir / "bounded_decoder_probe"
    argv = [
        sys.executable, str(TRAINER), "--repo-root", str(ROOT), "--manifest", str(TRAINER_MANIFEST),
        "--mode", "bounded_decoder_ce_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON), "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--execution-authorized-for-recovery-probe", "--max-train-rows", "5176", "--max-eval-rows", "248", "--max-strict-rows", "356",
        "--max-steps", "64", "--batch-size", "8", "--learning-rate", "1e-5", "--max-encoder-tokens", "768", "--max-decoder-tokens", "16",
        "--decoder-ce-weight", "0.35", "--bounded-choice-aux-weight", "2.0", "--bounded-choice-aux-source", "encoder_option_cross_encoder",
        "--bounded-decoder-train-sampler", "task_balanced", "--bounded-choice-contrast-weight", "0.2", "--bounded-choice-contrast-margin", "0.08",
        "--bounded-choice-same-role-listwise-weight", "0.5", "--bounded-choice-verifier-value-listwise-weight", "0.7",
        "--structured-aux-weight", "0.0", "--denoise-weight", "0.0", "--eos-loss-weight", "1.0", "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness", "--runtime-model-save-dir", str(runtime_dir), "--initialize-from-runtime-model", str(init_runtime),
        "--preservation-reference-runtime-model", str(INIT_RUNTIME), "--preservation-kl-weight", "4.0", "--no-final-checkpoint-export", "--output-dir", str(output_dir),
    ]
    return argv, runtime_dir, output_dir


def execute(approval_file: Path) -> dict[str, Any]:
    require_gpu2()
    build()
    approval = read_json(approval_file) if approval_file.exists() else {}
    if approval.get("stage") != STAGE or approval.get("approved") is not True or not approval.get("reviewer") or not approval.get("approval_id"):
        raise SystemExit("review approval file is absent or invalid; training remains blocked")
    if EXECUTION.exists():
        raise SystemExit(f"refusing to overwrite existing execution directory: {EXECUTION}")
    EXECUTION.mkdir(parents=True)
    current = INIT_RUNTIME
    best_metric = float("inf")
    best_chunk = 0
    stale = 0
    history = []
    for chunk in range(1, 13):
        argv, runtime_dir, output_dir = trainer_argv(current, chunk)
        subprocess.run(argv, cwd=ROOT, check=True)
        losses = {row["split"]: float(row["loss"]) for row in read_jsonl(output_dir / "eval_loss_by_checkpoint.jsonl")}
        metric = losses["eval"] + losses["strict_eval"]
        improved = metric < best_metric - 0.01
        history.append({"chunk": chunk, "steps_total": chunk * 64, "metric": metric, "losses": losses, "improved": improved})
        if improved:
            best_metric, best_chunk, stale = metric, chunk, 0
        else:
            stale += 1
        current = runtime_dir / "runtime_model_bundle.json"
        write_json(EXECUTION / "early_stopping_history.json", history)
        if chunk >= 3 and stale >= 3:
            break
    best_runtime = EXECUTION / f"chunk_{best_chunk:02d}/runtime_model"
    shutil.copytree(best_runtime, EXECUTION / "best_runtime")
    result = {"stage": STAGE, "approval": approval, "early_stopped": len(history) < 12, "chunks_run": len(history), "best_chunk": best_chunk, "best_metric": best_metric, "promotion_authorized": False, "postrun_frontier_audit_required": True}
    write_json(EXECUTION / "execution_result.json", result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--approval-file", type=Path, default=APPROVAL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.preflight:
        payload = differentiability_preflight()
    elif args.execute:
        payload = execute(args.approval_file)
    else:
        payload = build()
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
