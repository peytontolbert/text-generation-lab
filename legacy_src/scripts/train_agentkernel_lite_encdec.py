from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from loss_mask_card import LOSS_KEYS, normalize_loss_mask, read_jsonl, validate_loss_mask_row
from counterfactual_obligation_audit import audit_rows as audit_counterfactual_rows
from safe_cleanup import safe_cleanup_checkpoints
from safe_paths import UnsafePathError
from target_implementation_guard import evaluate_implementation_selection


SUPPORTED_MODES = (
    "structured_policy_probe",
    "repo_graph_probe",
    "symbol_binding_probe",
    "edit_localization_probe",
    "patch_operator_probe",
    "verifier_repair_probe",
    "bounded_decoder_ce_probe",
    "denoise_repair_probe",
)

AUTHORITY_FLAGS = (
    "model_execution_authorized_next",
    "decoder_ce_training_authorized_next",
    "runtime_authorized",
    "source_emission_authorized",
    "body_emission_authorized",
    "gemma_execution_authorized_next",
    "harness_execution_authorized_next",
    "scoring_authorized_next",
    "controller_complete_merge_authorized_next",
    "promotion_ready",
)

REQUIRED_BOUNDED_ARTIFACTS = (
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_token_loss.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "internal_token_logit_summary.json",
    "row_dynamics_history.jsonl",
    "eos_length_audit.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
    "sample_generation_audit.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
)

REQUIRED_STRUCTURED_ARTIFACTS = (
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "feature_ablation_attribution.jsonl",
    "activation_patch_recovery.jsonl",
    "row_dynamics_history.jsonl",
    "field_exact_by_cell.json",
    "field_label_vocabs.json",
    "structured_confusion_matrix.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
)

REQUIRED_DENOISE_ARTIFACTS = (
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_token_loss.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "row_dynamics_history.jsonl",
    "denoise_repair_quality_audit.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
    "sample_generation_audit.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
)

STRUCTURED_MODE_ALLOWED_LOSSES = {
    "structured_policy_probe": {
        "surface_role_ce",
        "repair_surface_ce",
        "build_mode_ce",
        "allowed_import_policy_ce",
        "blocked_import_policy_ce",
        "repo_dependency_policy_ce",
        "action_sequence_ce",
        "file_plan_ce",
    },
    "repo_graph_probe": set(),
    "symbol_binding_probe": {"symbol_binding_ce"},
    "edit_localization_probe": {"edit_localization_ce"},
    "patch_operator_probe": {"patch_operator_ce"},
    "verifier_repair_probe": {"verifier_repair_ce"},
    "denoise_repair_probe": {"denoise_ce"},
}


class ProbeContractError(ValueError):
    pass


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recovered AgentKernel Lite encoder-decoder trainer command surface. "
            "This scaffold validates probe contracts only; it does not execute model training."
        )
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--mode", choices=SUPPORTED_MODES, required=True)
    parser.add_argument("--max-train-rows", type=_positive_int, default=0)
    parser.add_argument("--max-eval-rows", type=_positive_int, default=0)
    parser.add_argument("--max-strict-rows", type=_positive_int, default=0)
    parser.add_argument("--max-steps", type=_positive_int, default=0)
    parser.add_argument("--max-decoder-tokens", type=_positive_int, default=768)
    parser.add_argument("--decoder-ce-weight", type=float, default=0.0)
    parser.add_argument("--eos-loss-weight", type=float, default=1.0, help="Optional EOS token CE multiplier for bounded decoder stabilization probes.")
    parser.add_argument("--structured-aux-weight", type=float, default=0.0)
    parser.add_argument("--denoise-weight", type=float, default=0.0)
    parser.add_argument("--require-loss-mask-enforcement-audit", action="store_true")
    parser.add_argument("--require-counterfactual-obligation-audit", action="store_true")
    parser.add_argument("--no-final-checkpoint-export", action="store_true")
    parser.add_argument("--cleanup-checkpoints-after-probe", action="store_true")
    parser.add_argument("--skip-final-model-save", type=int, choices=(0, 1), default=1)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", default="bounded_decoder_ce_probe_contract")
    parser.add_argument("--batch-size", type=_positive_int, default=2)
    parser.add_argument("--max-encoder-tokens", type=_positive_int, default=256)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--enable-generation-audit", action="store_true", help="Run bounded greedy generation quality audit after authorized bounded decoder CE probes.")
    parser.add_argument("--max-generation-rows", type=_positive_int, default=8)
    parser.add_argument("--max-generation-tokens", type=_positive_int, default=96)
    parser.add_argument(
        "--generation-prefix-field",
        default=None,
        help="Optional dotted manifest field used to prime decoder generation during audits, for example model_input.copy_prefix_span.",
    )
    parser.add_argument(
        "--generation-audit-splits",
        default="eval,strict_eval",
        help="Comma-separated splits sampled by generation audit. Defaults to eval,strict_eval; use train,eval,strict_eval only for memorization diagnostics.",
    )
    parser.add_argument(
        "--implementation",
        choices=("scaffold", "transformer"),
        default="transformer",
        help=(
            "Select recovered model implementation for authorized probes. The recovered 100M target "
            "contract requires transformer; scaffold is retained only for legacy interface tests."
        ),
    )
    parser.add_argument(
        "--probe-scale",
        choices=("tiny_transformer", "target_100m"),
        default="tiny_transformer",
        help=(
            "Select runtime model scale for explicitly authorized probes. tiny_transformer is the "
            "safe default for path validation; target_100m requires --model-config and the recovered "
            "1506-token tokenizer."
        ),
    )
    parser.add_argument(
        "--model-config",
        type=Path,
        default=None,
        help="Optional recovered 100M target model config JSON for --probe-scale target_100m.",
    )
    parser.add_argument("--tokenizer-json", type=Path, default=None, help="Optional recovered tokenizer.json for authorized probes; default is byte fallback.")
    parser.add_argument("--tokenizer-config", type=Path, default=None, help="Optional tokenizer_config.json paired with --tokenizer-json.")
    parser.add_argument(
        "--tokenizer-hashlock",
        type=Path,
        default=REPO_ROOT / "configs" / "tokenizer" / "agentkernel_bpe_1506_recovered_pointer.json",
        help="Tokenizer hashlock JSON required for --probe-scale target_100m.",
    )
    parser.add_argument("--execution-authorized-for-recovery-probe", action="store_true", help="Explicitly run the recovered probe implementation selected by --probe-scale. Requires all contract checks to pass.")
    parser.add_argument(
        "--contract-only",
        action="store_true",
        help="Validate the runtime contract and emit non-executing audit artifacts.",
    )
    return parser.parse_args()


def _row_split(row: dict[str, Any]) -> str:
    split = row.get("split") or row.get("package_split") or "train"
    if split == "strict":
        return "strict_eval"
    return str(split)


def _row_authority(row: dict[str, Any]) -> dict[str, bool]:
    authority = row.get("authority")
    if isinstance(authority, dict):
        source = authority
    else:
        source = row
    return {flag: bool(source.get(flag, False)) for flag in AUTHORITY_FLAGS}


def _target_token_len(row: dict[str, Any]) -> int | None:
    for key in ("decoder_token_len", "target_token_len", "target_tokens", "decoder_tokens"):
        value = row.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _decoder_target_text(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    for value in (target.get("decoder_text"), row.get("decoder_text"), target.get("target_ref"), row.get("target_ref")):
        if isinstance(value, str):
            return value
    return ""


def _nested_manifest_value(row: dict[str, Any], path: str | None) -> str:
    if not path:
        return ""
    value: Any = row
    for part in str(path).split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return ""
    return value if isinstance(value, str) else ""


def validate_generation_prefix_contract(args: argparse.Namespace, rows: list[dict[str, Any]]) -> list[str]:
    generation_prefix_field = getattr(args, "generation_prefix_field", None)
    if not generation_prefix_field:
        return []
    errors: list[str] = []
    if not args.enable_generation_audit:
        errors.append("--generation-prefix-field requires --enable-generation-audit")
    if args.max_generation_tokens < 8:
        errors.append("--generation-prefix-field requires --max-generation-tokens >= 8")
    bad_rows = []
    for index, row in enumerate(rows):
        row_id = str(row.get("row_id") or index)
        prefix = _nested_manifest_value(row, generation_prefix_field)
        target = _decoder_target_text(row)
        if not prefix:
            bad_rows.append({"row_id": row_id, "reason": "missing_prefix"})
            continue
        if len(prefix.split()) > 8 or len(prefix) > 96:
            bad_rows.append({"row_id": row_id, "reason": "prefix_over_cap", "prefix": prefix})
            continue
        if prefix == target:
            bad_rows.append({"row_id": row_id, "reason": "full_target_prefix"})
            continue
        if target and not target.startswith(prefix):
            bad_rows.append({"row_id": row_id, "reason": "prefix_not_target_start", "prefix": prefix})
    if bad_rows:
        errors.append(f"invalid generation prefix rows present: {len(bad_rows)}")
    return errors


def _manifest_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_target_100m_files(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if args.probe_scale != "target_100m":
        return errors
    if args.model_config is None:
        errors.append("--probe-scale target_100m requires --model-config")
    elif not args.model_config.is_file():
        errors.append(f"model config does not exist: {args.model_config}")
    if args.tokenizer_json is None:
        errors.append("--probe-scale target_100m requires --tokenizer-json")
    elif not args.tokenizer_json.is_file():
        errors.append(f"tokenizer json does not exist: {args.tokenizer_json}")
    if args.tokenizer_config is None:
        errors.append("--probe-scale target_100m requires --tokenizer-config")
    elif not args.tokenizer_config.is_file():
        errors.append(f"tokenizer config does not exist: {args.tokenizer_config}")
    if args.tokenizer_hashlock is None:
        errors.append("--probe-scale target_100m requires --tokenizer-hashlock")
    elif not args.tokenizer_hashlock.is_file():
        errors.append(f"tokenizer hashlock does not exist: {args.tokenizer_hashlock}")
    elif args.tokenizer_json is not None and args.tokenizer_json.is_file() and args.tokenizer_config is not None and args.tokenizer_config.is_file():
        payload = json.loads(args.tokenizer_hashlock.read_text(encoding="utf-8"))
        expected = payload.get("sha256") if isinstance(payload.get("sha256"), dict) else {}
        expected_json = expected.get("tokenizer_json")
        expected_config = expected.get("tokenizer_config")
        if expected_json and _sha256_file(args.tokenizer_json) != expected_json:
            errors.append("tokenizer json sha256 mismatch against hashlock")
        if expected_config and _sha256_file(args.tokenizer_config) != expected_config:
            errors.append("tokenizer config sha256 mismatch against hashlock")
    return errors


def load_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ProbeContractError(f"manifest does not exist: {path}")
    return read_jsonl(path)


def validate_bounded_decoder_ce_probe(args: argparse.Namespace, rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    split_counts = {"train": 0, "eval": 0, "strict_eval": 0, "other": 0}
    loss_counts = {key: 0 for key in LOSS_KEYS}
    authority_rows: list[str] = []
    over_cap_rows: list[str] = []
    unsafe_loss_rows: list[dict[str, Any]] = []
    empty_target_rows: list[str] = []
    implementation_guard = evaluate_implementation_selection(str(getattr(args, "implementation", "transformer")))

    if not implementation_guard["allowed_for_recovered_100m_target"]:
        errors.extend(str(error) for error in implementation_guard["errors"])
    errors.extend(_validate_target_100m_files(args))
    if args.decoder_ce_weight <= 0:
        errors.append("bounded decoder CE probe requires --decoder-ce-weight > 0")
    if args.eos_loss_weight < 1.0:
        errors.append("bounded decoder CE probe requires --eos-loss-weight >= 1.0")
    if args.structured_aux_weight != 0:
        errors.append("bounded decoder CE probe requires --structured-aux-weight 0")
    if args.denoise_weight != 0:
        errors.append("bounded decoder CE probe requires --denoise-weight 0")
    if not args.require_loss_mask_enforcement_audit:
        errors.append("--require-loss-mask-enforcement-audit is required")
    if not args.no_final_checkpoint_export:
        errors.append("--no-final-checkpoint-export is required")
    if args.skip_final_model_save != 1:
        errors.append("--skip-final-model-save 1 is required")
    errors.extend(validate_generation_prefix_contract(args, rows))

    for index, row in enumerate(rows):
        row_id = str(row.get("row_id") or f"row_{index}")
        split = _row_split(row)
        split_counts[split if split in split_counts else "other"] += 1
        mask = normalize_loss_mask(row)
        for key, value in mask.items():
            loss_counts[key] += int(value)
        enabled = [key for key, value in mask.items() if value]
        if enabled != ["decoder_ce"]:
            unsafe_loss_rows.append({"row_id": row_id, "enabled_losses": enabled})
        mask_errors = validate_loss_mask_row(row, allow_decoder_ce=True, allow_denoise=False, allow_runtime=False)
        if mask_errors:
            unsafe_loss_rows.append({"row_id": row_id, "mask_errors": mask_errors})
        auth = _row_authority(row)
        if any(auth.values()):
            authority_rows.append(row_id)
        target_text = _decoder_target_text(row)
        if not target_text.strip():
            empty_target_rows.append(row_id)
        token_len = _target_token_len(row)
        if token_len is not None and token_len > args.max_decoder_tokens:
            over_cap_rows.append(row_id)

    if split_counts["train"] > args.max_train_rows:
        errors.append(f"train rows {split_counts['train']} exceed cap {args.max_train_rows}")
    if split_counts["eval"] > args.max_eval_rows:
        errors.append(f"eval rows {split_counts['eval']} exceed cap {args.max_eval_rows}")
    if split_counts["strict_eval"] > args.max_strict_rows:
        errors.append(f"strict rows {split_counts['strict_eval']} exceed cap {args.max_strict_rows}")
    if split_counts["other"]:
        errors.append(f"unexpected split rows: {split_counts['other']}")
    if authority_rows:
        errors.append(f"authority rows present: {len(authority_rows)}")
    if over_cap_rows:
        errors.append(f"target token over-cap rows present: {len(over_cap_rows)}")
    if empty_target_rows:
        errors.append(f"empty decoder target rows present: {len(empty_target_rows)}")
    if unsafe_loss_rows:
        errors.append(f"unsafe loss-mask rows present: {len(unsafe_loss_rows)}")

    return {
        "passed": not errors,
        "errors": errors,
        "mode": args.mode,
        "manifest": str(args.manifest),
        "manifest_sha256": _manifest_hash(args.manifest),
        "row_ids": [str(row.get("row_id") or index) for index, row in enumerate(rows)],
        "rows": len(rows),
        "split_counts": split_counts,
        "loss_counts": loss_counts,
        "authority_rows": len(authority_rows),
        "authority_row_ids": authority_rows[:50],
        "over_cap_rows": len(over_cap_rows),
        "over_cap_row_ids": over_cap_rows[:50],
        "empty_target_rows": len(empty_target_rows),
        "empty_target_row_ids": empty_target_rows[:50],
        "unsafe_loss_rows": len(unsafe_loss_rows),
        "unsafe_loss_row_examples": unsafe_loss_rows[:50],
        "weights": {
            "decoder_ce_weight": args.decoder_ce_weight,
            "eos_loss_weight": args.eos_loss_weight,
            "structured_aux_weight": args.structured_aux_weight,
            "denoise_weight": args.denoise_weight,
        },
        "implementation": str(getattr(args, "implementation", "transformer")),
        "probe_scale": str(getattr(args, "probe_scale", "tiny_transformer")),
        "implementation_contract": {
            "target_implementation_guard": implementation_guard,
            "scaffold": bool(getattr(args, "implementation", "transformer") == "scaffold"),
            "transformer_module": "legacy_src/agentkernel_lite/modeling_transformer.py",
            "transformer_execution_requires_explicit_authorization": True,
            "model_config": str(args.model_config) if args.model_config else None,
            "target_100m_requires_model_config": args.probe_scale == "target_100m",
        },
        "tokenizer_contract": {
            "tokenizer_json": str(args.tokenizer_json) if args.tokenizer_json else None,
            "tokenizer_config": str(args.tokenizer_config) if args.tokenizer_config else None,
            "tokenizer_hashlock": str(args.tokenizer_hashlock) if args.tokenizer_hashlock else None,
            "byte_fallback_used_when_unset": args.tokenizer_json is None,
            "target_100m_vocab_size": 1506,
        },
        "caps": {
            "max_train_rows": args.max_train_rows,
            "max_eval_rows": args.max_eval_rows,
            "max_strict_rows": args.max_strict_rows,
            "max_steps": args.max_steps,
            "max_decoder_tokens": args.max_decoder_tokens,
            "eos_loss_weight": args.eos_loss_weight,
        },
        "final_checkpoint_export_disabled": bool(args.no_final_checkpoint_export),
        "final_model_save_skipped": args.skip_final_model_save == 1,
        "cleanup_requested": bool(args.cleanup_checkpoints_after_probe),
        "generation_audit_requested": bool(args.enable_generation_audit),
        "max_generation_rows": int(args.max_generation_rows),
        "max_generation_tokens": int(args.max_generation_tokens),
        "generation_prefix_field": getattr(args, "generation_prefix_field", None),
        "generation_audit_splits": getattr(args, "generation_audit_splits", "eval,strict_eval"),
        "model_execution_attempted": False,
    }



def validate_structured_probe(args: argparse.Namespace, rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    allowed_losses = STRUCTURED_MODE_ALLOWED_LOSSES.get(args.mode, set())
    split_counts = {"train": 0, "eval": 0, "strict_eval": 0, "other": 0}
    loss_counts = {key: 0 for key in LOSS_KEYS}
    authority_rows: list[str] = []
    unsafe_loss_rows: list[dict[str, Any]] = []
    implementation_guard = evaluate_implementation_selection(str(getattr(args, "implementation", "transformer")))

    if not implementation_guard["allowed_for_recovered_100m_target"]:
        errors.extend(str(error) for error in implementation_guard["errors"])
    errors.extend(_validate_target_100m_files(args))
    if args.decoder_ce_weight != 0:
        errors.append("structured probes require --decoder-ce-weight 0")
    if args.mode != "denoise_repair_probe" and args.denoise_weight != 0:
        errors.append("non-denoise structured probes require --denoise-weight 0")
    if args.mode == "denoise_repair_probe" and args.denoise_weight <= 0:
        errors.append("denoise repair probe requires --denoise-weight > 0")
    if args.mode != "repo_graph_probe" and args.mode != "denoise_repair_probe" and args.structured_aux_weight <= 0:
        errors.append("structured probe requires --structured-aux-weight > 0")
    if not args.require_loss_mask_enforcement_audit:
        errors.append("--require-loss-mask-enforcement-audit is required")
    if not args.no_final_checkpoint_export:
        errors.append("--no-final-checkpoint-export is required")
    if args.skip_final_model_save != 1:
        errors.append("--skip-final-model-save 1 is required")
    errors.extend(validate_generation_prefix_contract(args, rows))

    for index, row in enumerate(rows):
        row_id = str(row.get("row_id") or f"row_{index}")
        split = _row_split(row)
        split_counts[split if split in split_counts else "other"] += 1
        mask = normalize_loss_mask(row)
        enabled = {key for key, value in mask.items() if value}
        for key, value in mask.items():
            loss_counts[key] += int(value)
        if not enabled:
            unsafe_loss_rows.append({"row_id": row_id, "enabled_losses": []})
        forbidden = enabled - allowed_losses
        if forbidden:
            unsafe_loss_rows.append({"row_id": row_id, "forbidden_losses": sorted(forbidden), "enabled_losses": sorted(enabled)})
        mask_errors = validate_loss_mask_row(
            row,
            allow_decoder_ce=False,
            allow_denoise=args.mode == "denoise_repair_probe",
            allow_runtime=False,
        )
        if mask_errors:
            unsafe_loss_rows.append({"row_id": row_id, "mask_errors": mask_errors})
        auth = _row_authority(row)
        if any(auth.values()):
            authority_rows.append(row_id)

    if split_counts["train"] > args.max_train_rows:
        errors.append(f"train rows {split_counts['train']} exceed cap {args.max_train_rows}")
    if split_counts["eval"] > args.max_eval_rows:
        errors.append(f"eval rows {split_counts['eval']} exceed cap {args.max_eval_rows}")
    if split_counts["strict_eval"] > args.max_strict_rows:
        errors.append(f"strict rows {split_counts['strict_eval']} exceed cap {args.max_strict_rows}")
    if split_counts["other"]:
        errors.append(f"unexpected split rows: {split_counts['other']}")
    if authority_rows:
        errors.append(f"authority rows present: {len(authority_rows)}")
    if unsafe_loss_rows:
        errors.append(f"unsafe loss-mask rows present: {len(unsafe_loss_rows)}")

    counterfactual_card = None
    if args.require_counterfactual_obligation_audit:
        counterfactual_card = audit_counterfactual_rows(rows)
        if not counterfactual_card.get("counterfactual_obligations_complete"):
            errors.append("counterfactual obligations are incomplete")

    return {
        "passed": not errors,
        "errors": errors,
        "mode": args.mode,
        "manifest": str(args.manifest),
        "manifest_sha256": _manifest_hash(args.manifest),
        "row_ids": [str(row.get("row_id") or index) for index, row in enumerate(rows)],
        "rows": len(rows),
        "split_counts": split_counts,
        "loss_counts": loss_counts,
        "allowed_losses": sorted(allowed_losses),
        "authority_rows": len(authority_rows),
        "authority_row_ids": authority_rows[:50],
        "unsafe_loss_rows": len(unsafe_loss_rows),
        "unsafe_loss_row_examples": unsafe_loss_rows[:50],
        "counterfactual_obligation_audit_required": bool(args.require_counterfactual_obligation_audit),
        "counterfactual_obligation_card": counterfactual_card,
        "weights": {
            "decoder_ce_weight": args.decoder_ce_weight,
            "eos_loss_weight": args.eos_loss_weight,
            "structured_aux_weight": args.structured_aux_weight,
            "denoise_weight": args.denoise_weight,
        },
        "implementation": str(getattr(args, "implementation", "transformer")),
        "probe_scale": str(getattr(args, "probe_scale", "tiny_transformer")),
        "implementation_contract": {
            "target_implementation_guard": implementation_guard,
            "scaffold": bool(getattr(args, "implementation", "transformer") == "scaffold"),
            "transformer_module": "legacy_src/agentkernel_lite/modeling_transformer.py",
            "transformer_execution_requires_explicit_authorization": True,
            "model_config": str(args.model_config) if args.model_config else None,
            "target_100m_requires_model_config": args.probe_scale == "target_100m",
        },
        "tokenizer_contract": {
            "tokenizer_json": str(args.tokenizer_json) if args.tokenizer_json else None,
            "tokenizer_config": str(args.tokenizer_config) if args.tokenizer_config else None,
            "tokenizer_hashlock": str(args.tokenizer_hashlock) if args.tokenizer_hashlock else None,
            "byte_fallback_used_when_unset": args.tokenizer_json is None,
            "target_100m_vocab_size": 1506,
        },
        "caps": {
            "max_train_rows": args.max_train_rows,
            "max_eval_rows": args.max_eval_rows,
            "max_strict_rows": args.max_strict_rows,
            "max_steps": args.max_steps,
            "max_decoder_tokens": args.max_decoder_tokens,
        },
        "final_checkpoint_export_disabled": bool(args.no_final_checkpoint_export),
        "final_model_save_skipped": args.skip_final_model_save == 1,
        "cleanup_requested": bool(args.cleanup_checkpoints_after_probe),
        "generation_audit_requested": bool(args.enable_generation_audit),
        "max_generation_rows": int(args.max_generation_rows),
        "max_generation_tokens": int(args.max_generation_tokens),
        "generation_prefix_field": getattr(args, "generation_prefix_field", None),
        "generation_audit_splits": getattr(args, "generation_audit_splits", "eval,strict_eval"),
        "model_execution_attempted": False,
    }

def validate_contract(args: argparse.Namespace, rows: list[dict[str, Any]]) -> dict[str, Any]:
    repo = args.repo_root.resolve()
    out = args.output_dir.resolve()
    if not str(out).startswith(str(repo) + "/"):
        raise ProbeContractError(f"output_dir must be under repo_root: {out} not under {repo}")
    if args.mode == "bounded_decoder_ce_probe":
        return validate_bounded_decoder_ce_probe(args, rows)
    if args.mode in STRUCTURED_MODE_ALLOWED_LOSSES:
        return validate_structured_probe(args, rows)
    raise ProbeContractError(f"mode {args.mode} is not supported by the recovered contract validator")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def emit_contract_artifacts(args: argparse.Namespace, card: dict[str, Any]) -> None:
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    marker = out / ".agentkernel_probe_output"
    marker.write_text(f"run_id={args.run_id}\nmode={args.mode}\ncontract_only=true\n", encoding="utf-8")
    _write_json(out / "probe_contract_audit.json", card)
    _write_json(
        out / "cleanup_proof.json",
        {
            "cleanup_requested": bool(args.cleanup_checkpoints_after_probe),
            "cleanup_executed": False,
            "cleanup_reason": "contract-only trainer scaffold does not create checkpoints",
            "run_id": args.run_id,
            "output_dir": str(out.resolve()),
        },
    )
    if args.mode == "bounded_decoder_ce_probe":
        required_artifacts = REQUIRED_BOUNDED_ARTIFACTS
    elif args.mode == "denoise_repair_probe":
        required_artifacts = REQUIRED_DENOISE_ARTIFACTS
    else:
        required_artifacts = REQUIRED_STRUCTURED_ARTIFACTS
    for artifact in required_artifacts:
        path = out / artifact
        if path.name == "cleanup_proof.json":
            continue
        if path.suffix == ".jsonl":
            path.write_text("", encoding="utf-8")
        else:
            _write_json(
                path,
                {
                    "artifact": path.name,
                    "contract_only": True,
                    "model_execution_attempted": False,
                    "note": "placeholder emitted by recovered trainer scaffold",
                },
            )
    if args.cleanup_checkpoints_after_probe:
        try:
            cleanup = safe_cleanup_checkpoints(
                repo_root=args.repo_root,
                output_dir=args.output_dir,
                run_id=args.run_id,
                dry_run=True,
            )
        except UnsafePathError as exc:
            raise ProbeContractError(f"safe cleanup dry-run refused: {exc}") from exc
        _write_json(out / "cleanup_dry_run.json", cleanup)



def run_authorized_recovery_probe(args: argparse.Namespace, rows: list[dict[str, Any]], card: dict[str, Any]) -> dict[str, Any]:
    if not card.get("passed"):
        raise ProbeContractError("cannot execute recovery probe because contract did not pass")
    if args.no_final_checkpoint_export is not True or args.skip_final_model_save != 1:
        raise ProbeContractError("checkpoint export must remain disabled")
    legacy_src = REPO_ROOT / "legacy_src"
    if str(legacy_src) not in sys.path:
        sys.path.insert(0, str(legacy_src))
    from agentkernel_lite.training_loop import run_bounded_decoder_ce_probe, run_denoise_repair_probe, run_structured_aux_probe

    common = dict(
        rows=rows,
        output_dir=args.output_dir,
        run_id=args.run_id,
        max_train_rows=args.max_train_rows,
        max_eval_rows=args.max_eval_rows,
        max_strict_rows=args.max_strict_rows,
        max_steps=args.max_steps,
        batch_size=args.batch_size,
        max_encoder_tokens=args.max_encoder_tokens,
        max_decoder_tokens=args.max_decoder_tokens,
        learning_rate=args.learning_rate,
        implementation=args.implementation,
        probe_scale=args.probe_scale,
        model_config=args.model_config,
        tokenizer_json=args.tokenizer_json,
        tokenizer_config=args.tokenizer_config,
    )
    if args.mode == "bounded_decoder_ce_probe":
        result = run_bounded_decoder_ce_probe(
            **common,
            enable_generation_audit=args.enable_generation_audit,
            max_generation_rows=args.max_generation_rows,
            max_generation_tokens=args.max_generation_tokens,
            eos_loss_weight=args.eos_loss_weight,
            generation_prefix_field=args.generation_prefix_field,
            generation_audit_splits=args.generation_audit_splits,
        )
    elif args.mode == "denoise_repair_probe":
        result = run_denoise_repair_probe(
            **common,
            eos_loss_weight=args.eos_loss_weight,
            enable_generation_audit=args.enable_generation_audit,
            max_generation_rows=args.max_generation_rows,
            max_generation_tokens=args.max_generation_tokens,
            generation_prefix_field=args.generation_prefix_field,
            generation_audit_splits=args.generation_audit_splits,
        )
    elif args.mode in STRUCTURED_MODE_ALLOWED_LOSSES and args.mode != "repo_graph_probe":
        result = run_structured_aux_probe(mode=args.mode, **common)
    else:
        raise ProbeContractError(f"execution is not restored for mode: {args.mode}")
    _write_json(args.output_dir / "execution_result.json", result)
    return result

def main() -> None:
    args = parse_args()
    rows = load_manifest(args.manifest)
    card = validate_contract(args, rows)
    emit_contract_artifacts(args, card)
    print(json.dumps(card, indent=2, sort_keys=True))
    if not card["passed"]:
        raise SystemExit(1)
    if args.contract_only:
        return
    if not args.execution_authorized_for_recovery_probe:
        raise SystemExit(
            "contract validated, but model execution is disabled unless --execution-authorized-for-recovery-probe is present"
        )
    result = run_authorized_recovery_probe(args, rows, card)
    print(json.dumps({"execution_result": result}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
