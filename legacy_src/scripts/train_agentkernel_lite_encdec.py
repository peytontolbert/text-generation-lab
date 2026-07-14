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
    "episode_step_denoise_contract_only",
    "episode_step_structured_probe",
    "two_phase_structured_reconnect_probe",
    "two_phase_suffix_denoise_reconnect_probe",
    "tri_phase_suffix_phrase_residual_reconnect_probe",
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
        "suffix_choice_ce",
    },
    "repo_graph_probe": set(),
    "symbol_binding_probe": {"symbol_binding_ce"},
    "edit_localization_probe": {"edit_localization_ce"},
    "patch_operator_probe": {"patch_operator_ce"},
    "verifier_repair_probe": {"verifier_repair_ce"},
    "denoise_repair_probe": {"denoise_ce"},
    "episode_step_denoise_contract_only": set(),
    "episode_step_structured_probe": {
        "episode_repair_outcome_ce",
        "episode_failure_type_ce",
        "episode_boundary_match_ce",
        "episode_target_prefix_match_ce",
        "episode_step_value_mse",
    },
}

MULTILINGUAL_MAINTENANCE_LANGS = ("python", "rust", "c_cpp", "web_js_ts_html")
MULTILINGUAL_MAINTENANCE_SPLITS = ("train", "eval", "strict_eval")
MULTILINGUAL_READINESS_LABEL_KEYS = {
    "edit_localization_probe": "edit_localization_target",
    "patch_operator_probe": "patch_operator",
    "verifier_repair_probe": "verifier_repair_action",
}


STRUCTURED_SINGLE_LOSS_MODE_BY_KEY = {
    "symbol_binding_ce": "symbol_binding_probe",
    "edit_localization_ce": "edit_localization_probe",
    "patch_operator_ce": "patch_operator_probe",
    "verifier_repair_ce": "verifier_repair_probe",
}


def infer_structured_probe_mode(rows: list[dict[str, Any]]) -> tuple[str | None, list[str]]:
    inferred: set[str] = set()
    errors: list[str] = []
    for index, row in enumerate(rows):
        row_id = str(row.get("row_id") or f"row_{index}")
        enabled = [
            key for key, value in normalize_loss_mask(row).items()
            if value and key in STRUCTURED_SINGLE_LOSS_MODE_BY_KEY
        ]
        unique_enabled = sorted(set(enabled))
        if len(unique_enabled) != 1:
            errors.append(f"row {row_id} does not expose exactly one structured task loss")
            continue
        inferred.add(STRUCTURED_SINGLE_LOSS_MODE_BY_KEY[unique_enabled[0]])
    if len(inferred) > 1:
        errors.append(f"mixed structured task modes present: {sorted(inferred)}")
    return (next(iter(inferred)) if len(inferred) == 1 else None, errors)


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
    parser.add_argument("--phase2-manifest", type=Path, default=None, help="Second manifest for audited two-phase probes; currently used by suffix-choice -> residual-denoise reconnect.")
    parser.add_argument("--phase3-manifest", type=Path, default=None, help="Third manifest for audited tri-phase probes; currently used by suffix-choice -> phrase warm-up -> residual reconnect.")
    parser.add_argument("--mode", choices=SUPPORTED_MODES, required=True)
    parser.add_argument("--max-train-rows", type=_positive_int, default=0)
    parser.add_argument("--max-eval-rows", type=_positive_int, default=0)
    parser.add_argument("--max-strict-rows", type=_positive_int, default=0)
    parser.add_argument("--max-steps", type=_positive_int, default=0)
    parser.add_argument("--max-decoder-tokens", type=_positive_int, default=768)
    parser.add_argument("--phase2-max-train-rows", type=_positive_int, default=0)
    parser.add_argument("--phase2-max-eval-rows", type=_positive_int, default=0)
    parser.add_argument("--phase2-max-strict-rows", type=_positive_int, default=0)
    parser.add_argument("--phase2-max-steps", type=_positive_int, default=0)
    parser.add_argument("--phase2-max-decoder-tokens", type=_positive_int, default=0)
    parser.add_argument("--phase3-max-train-rows", type=_positive_int, default=0)
    parser.add_argument("--phase3-max-eval-rows", type=_positive_int, default=0)
    parser.add_argument("--phase3-max-strict-rows", type=_positive_int, default=0)
    parser.add_argument("--phase3-max-steps", type=_positive_int, default=0)
    parser.add_argument("--phase3-max-decoder-tokens", type=_positive_int, default=0)
    parser.add_argument("--decoder-ce-weight", type=float, default=0.0)
    parser.add_argument("--bounded-choice-aux-weight", type=float, default=0.0, help="Optional auxiliary CE over allowed opaque-choice labels for bounded maintainer probes.")
    parser.add_argument("--bounded-choice-aux-source", choices=["decoder_first_step", "encoder_pooled", "encoder_pooled_untied_head", "encoder_option_retrieval", "encoder_option_retrieval_conditioned", "encoder_option_retrieval_verifier_conditioned", "encoder_option_retrieval_evidence_role_map", "encoder_option_retrieval_dynamic_productized", "encoder_option_retrieval_role_bias", "encoder_option_retrieval_pairwise", "encoder_option_retrieval_evidence_pairwise_gated", "encoder_option_retrieval_evidence_ledger_head", "encoder_option_retrieval_evidence_role_head", "encoder_option_retrieval_evidence_judgment_head", "encoder_option_retrieval_evidence_conditioned_gated", "encoder_option_retrieval_evidence_fact_text", "encoder_option_retrieval_evidence_fact_pairwise", "encoder_option_retrieval_semantic_candidate_head", "encoder_option_retrieval_web_task_candidate_head", "encoder_option_retrieval_transition_candidate_head", "encoder_option_retrieval_transition_status_head", "encoder_option_retrieval_semantic_plus_transition_status_head", "encoder_option_retrieval_semantic_plus_transition_candidate_head"], default="decoder_first_step", help="Source of logits for bounded maintainer opaque-choice auxiliary loss.")
    parser.add_argument("--bounded-choice-contrast-weight", type=float, default=0.0, help="Optional contrastive margin loss over audited bounded-choice confusions such as candidate_change_surface versus verifier_and_test_constraint.")
    parser.add_argument("--bounded-choice-contrast-margin", type=float, default=0.05, help="Margin used by the optional bounded-choice contrastive loss.")
    parser.add_argument("--bounded-choice-verifier-value-listwise-weight", type=float, default=0.0, help="Optional CE over same-role verifier candidate values such as PASS/FAIL/NOT_EXERCISED within verifier_outcome rows.")
    parser.add_argument("--bounded-choice-same-role-listwise-weight", type=float, default=0.0, help="Optional CE over options sharing the target semantic role, for same-role candidate identity learning across task families.")
    parser.add_argument("--bounded-choice-root-group-aux-weight", type=float, default=0.0, help="Optional bounded-choice CE averaged by rollout/root group before averaging across groups, for grouped maintainer-root training.")
    parser.add_argument("--bounded-decoder-train-sampler", choices=("cyclic", "task_balanced", "residual_family_balanced", "web_task_family_balanced", "web_gap_root_balanced", "web_gap_same_root_grouped"), default="cyclic", help="Row sampler used inside bounded decoder CE probes. residual_family_balanced oversamples evidence_citation and verifier_outcome lanes; web_task_family_balanced cycles Web task families; web_gap_root_balanced cycles root/rollout groups one row at a time; web_gap_same_root_grouped packs same-root rows into each batch for listwise pressure.")
    parser.add_argument("--bounded-choice-train-head-only", action="store_true", help="Freeze the base model and train only the selected bounded-choice scorer head.")
    parser.add_argument("--eos-loss-weight", type=float, default=1.0, help="Optional EOS token CE multiplier for bounded decoder stabilization probes.")
    parser.add_argument("--structured-aux-weight", type=float, default=0.0)
    parser.add_argument("--denoise-weight", type=float, default=0.0)
    parser.add_argument("--require-loss-mask-enforcement-audit", action="store_true")
    parser.add_argument("--require-native-feature-ablation-audit", action="store_true", help="Require structured probes to emit native grouped mask-rerun feature ablation telemetry instead of proxy attribution.")
    parser.add_argument("--require-counterfactual-obligation-audit", action="store_true")
    parser.add_argument("--no-final-checkpoint-export", action="store_true")
    parser.add_argument("--cleanup-checkpoints-after-probe", action="store_true")
    parser.add_argument("--skip-final-model-save", type=int, choices=(0, 1), default=1)
    parser.add_argument("--allow-runtime-model-save-for-harness", action="store_true", help="Recovery-only escape hatch: permit writing a local runtime model bundle for harness parity while keeping final checkpoint export disabled.")
    parser.add_argument("--runtime-model-save-dir", type=Path, default=None, help="Optional output directory for a recovery-only runtime model bundle.")
    parser.add_argument("--initialize-from-runtime-model", type=Path, default=None, help="Optional saved runtime model bundle or model_state.pt used to initialize bounded decoder CE probes before optimization.")
    parser.add_argument("--preservation-reference-runtime-model", type=Path, default=None, help="Optional frozen runtime model bundle used as a KL preservation reference during bounded decoder CE probes.")
    parser.add_argument("--preservation-kl-weight", type=float, default=0.0, help="Optional KL penalty weight that preserves decoder behavior on non-exempt bounded decoder rows.")
    parser.add_argument("--preservation-exempt-flag", default="preservation_exempt", help="Row field whose truthy value exempts a bounded decoder train row from preservation KL.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", default="bounded_decoder_ce_probe_contract")
    parser.add_argument("--batch-size", type=_positive_int, default=2)
    parser.add_argument("--max-encoder-tokens", type=_positive_int, default=2048)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--phase2-learning-rate", type=float, default=None)
    parser.add_argument("--structured-trainable-profile", choices=("full_non_decoder", "structured_heads_only", "structured_heads_plus_policy"), default="full_non_decoder")
    parser.add_argument("--phase2-structured-trainable-profile", choices=("full_non_decoder", "structured_heads_only", "structured_heads_plus_policy"), default=None)
    parser.add_argument("--eval-interval", type=_positive_int, default=0, help="Optional structured-probe eval interval for checkpoint-selection telemetry; 0 disables interval eval.")
    parser.add_argument(
        "--restore-best-structured-state",
        action="store_true",
        help="Restore the best in-memory structured-probe state selected by interval eval; never exports or promotes a checkpoint.",
    )
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
        "--generation-repetition-guard",
        action="store_true",
        help="During generation audits, choose the best top-k token that does not create immediate degenerate repetition.",
    )
    parser.add_argument("--generation-repetition-guard-top-k", type=_positive_int, default=16)
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


def _edit_localization_safe_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
    return (
        state.get("task_observation"),
        state.get("visible_locality_evidence"),
        state.get("file_extension"),
        state.get("context_config_visible"),
        state.get("context_entrypoint_visible"),
        state.get("context_symbol_names_visible"),
        state.get("context_tests_visible"),
    )


def _patch_operator_safe_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    corrupted = row.get("corrupted_state") if isinstance(row.get("corrupted_state"), dict) else {}
    scope = corrupted.get("target_scope_features") if isinstance(corrupted.get("target_scope_features"), dict) else {}
    return (
        corrupted.get("localized_edit_need"),
        corrupted.get("file_extension"),
        scope.get("bounded_patch_required"),
        scope.get("has_visible_config"),
        scope.get("has_visible_import_policy"),
        scope.get("has_visible_test"),
    )


def _verifier_repair_safe_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    query = row.get("query") if isinstance(row.get("query"), dict) else {}
    return (query.get("query_kind"),)


def assess_multilingual_surface_readiness(mode: str, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    label_key = MULTILINGUAL_READINESS_LABEL_KEYS.get(mode)
    if label_key is None:
        return None
    langs = {str(row.get("language_family") or "") for row in rows}
    splits = {_row_split(row) for row in rows}
    if not all(lang in langs for lang in MULTILINGUAL_MAINTENANCE_LANGS):
        return None
    if not all(split in splits for split in MULTILINGUAL_MAINTENANCE_SPLITS):
        return None

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        lang = str(row.get("language_family") or "")
        split = _row_split(row)
        if lang not in MULTILINGUAL_MAINTENANCE_LANGS or split not in MULTILINGUAL_MAINTENANCE_SPLITS:
            continue
        grouped.setdefault((lang, split), []).append(row)

    bucket_cards: dict[str, Any] = {}
    failed_buckets: list[str] = []
    target_literal_rows: list[str] = []
    for lang in MULTILINGUAL_MAINTENANCE_LANGS:
        for split in MULTILINGUAL_MAINTENANCE_SPLITS:
            bucket = grouped.get((lang, split), [])
            labels = sorted(
                {
                    str((row.get("clean_state") or {}).get(label_key) or "")
                    for row in bucket
                    if isinstance(row.get("clean_state"), dict) and str((row.get("clean_state") or {}).get(label_key) or "")
                }
            )
            if mode == "edit_localization_probe":
                safe_signatures = {_edit_localization_safe_signature(row) for row in bucket}
            elif mode == "patch_operator_probe":
                safe_signatures = {_patch_operator_safe_signature(row) for row in bucket}
            else:
                safe_signatures = {_verifier_repair_safe_signature(row) for row in bucket}
            target_literal_count = 0
            if mode == "edit_localization_probe":
                for row in bucket:
                    text = json.dumps(row.get("input_state") if isinstance(row.get("input_state"), dict) else {}, sort_keys=True)
                    if "TARGET_" in text:
                        target_literal_rows.append(str(row.get("row_id") or ""))
                        target_literal_count += 1
            signature_to_labels: dict[tuple[Any, ...], set[str]] = {}
            for row in bucket:
                clean_state = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
                label = str(clean_state.get(label_key) or "")
                if not label:
                    continue
                if mode == "edit_localization_probe":
                    signature = _edit_localization_safe_signature(row)
                elif mode == "patch_operator_probe":
                    signature = _patch_operator_safe_signature(row)
                else:
                    signature = _verifier_repair_safe_signature(row)
                signature_to_labels.setdefault(signature, set()).add(label)
            colliding_signatures = {
                signature: sorted(bound_labels)
                for signature, bound_labels in signature_to_labels.items()
                if len(bound_labels) > 1
            }
            surface_separates_labels = bool(labels) and not colliding_signatures and len(safe_signatures) >= len(labels)
            optional_empty_train_bucket = split == "train" and not bucket
            if (not surface_separates_labels or target_literal_count) and not optional_empty_train_bucket:
                failed_buckets.append(f"{lang}:{split}")
            bucket_cards[f"{lang}:{split}"] = {
                "rows": len(bucket),
                "label_count": len(labels),
                "safe_signature_unique_count": len(safe_signatures),
                "surface_separates_labels": surface_separates_labels,
                "signature_collision_count": len(colliding_signatures),
                "colliding_signatures": {
                    json.dumps(list(signature), sort_keys=True): bound_labels
                    for signature, bound_labels in colliding_signatures.items()
                },
                "target_label_literal_rows": target_literal_count,
                "optional_empty_train_bucket": optional_empty_train_bucket,
            }

    passed = not failed_buckets and not target_literal_rows
    return {
        "applied": True,
        "mode": mode,
        "passed": passed,
        "failed_bucket_count": len(failed_buckets),
        "failed_buckets": failed_buckets,
        "target_label_literal_row_count": len(target_literal_rows),
        "target_label_literal_row_ids": target_literal_rows[:50],
        "buckets": bucket_cards,
        "rule": "Every multilingual maintenance language/split bucket must expose encoder-visible, non-label evidence that separates the target labels before training is considered win-ready.",
    }


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
    if args.decoder_ce_weight < 0:
        errors.append("bounded decoder CE probe requires --decoder-ce-weight >= 0")
    if args.decoder_ce_weight == 0 and args.bounded_choice_aux_weight <= 0 and args.bounded_choice_root_group_aux_weight <= 0:
        errors.append("bounded decoder CE probe requires decoder CE, bounded choice aux, or root-group bounded choice aux weight")
    if args.eos_loss_weight < 1.0:
        errors.append("bounded decoder CE probe requires --eos-loss-weight >= 1.0")
    if args.structured_aux_weight != 0:
        errors.append("bounded decoder CE probe requires --structured-aux-weight 0")
    if args.bounded_choice_aux_weight < 0:
        errors.append("bounded decoder CE probe requires --bounded-choice-aux-weight >= 0")
    if args.bounded_choice_contrast_weight < 0:
        errors.append("bounded decoder CE probe requires --bounded-choice-contrast-weight >= 0")
    if args.bounded_choice_contrast_margin < 0:
        errors.append("bounded decoder CE probe requires --bounded-choice-contrast-margin >= 0")
    if args.bounded_choice_verifier_value_listwise_weight < 0:
        errors.append("bounded decoder CE probe requires --bounded-choice-verifier-value-listwise-weight >= 0")
    if args.bounded_choice_same_role_listwise_weight < 0:
        errors.append("bounded decoder CE probe requires --bounded-choice-same-role-listwise-weight >= 0")
    if args.bounded_choice_root_group_aux_weight < 0:
        errors.append("bounded decoder CE probe requires --bounded-choice-root-group-aux-weight >= 0")
    if args.bounded_choice_aux_source not in {"decoder_first_step", "encoder_pooled", "encoder_pooled_untied_head", "encoder_option_retrieval", "encoder_option_retrieval_conditioned", "encoder_option_retrieval_verifier_conditioned", "encoder_option_retrieval_evidence_role_map", "encoder_option_retrieval_dynamic_productized", "encoder_option_retrieval_role_bias", "encoder_option_retrieval_pairwise", "encoder_option_retrieval_evidence_pairwise_gated", "encoder_option_retrieval_evidence_ledger_head", "encoder_option_retrieval_evidence_role_head", "encoder_option_retrieval_evidence_judgment_head", "encoder_option_retrieval_evidence_conditioned_gated", "encoder_option_retrieval_evidence_fact_text", "encoder_option_retrieval_evidence_fact_pairwise", "encoder_option_retrieval_semantic_candidate_head", "encoder_option_retrieval_web_task_candidate_head", "encoder_option_retrieval_transition_candidate_head", "encoder_option_retrieval_transition_status_head", "encoder_option_retrieval_semantic_plus_transition_status_head", "encoder_option_retrieval_semantic_plus_transition_candidate_head"}:
        errors.append("bounded decoder CE probe requires supported --bounded-choice-aux-source")
    if args.denoise_weight != 0:
        errors.append("bounded decoder CE probe requires --denoise-weight 0")
    if not args.require_loss_mask_enforcement_audit:
        errors.append("--require-loss-mask-enforcement-audit is required")
    if not args.no_final_checkpoint_export:
        errors.append("--no-final-checkpoint-export is required")
    if args.skip_final_model_save != 1:
        errors.append("--skip-final-model-save 1 is required")
    if args.runtime_model_save_dir is not None and not args.allow_runtime_model_save_for_harness:
        errors.append("--runtime-model-save-dir requires --allow-runtime-model-save-for-harness")
    if args.initialize_from_runtime_model is not None and args.mode != "bounded_decoder_ce_probe":
        errors.append("--initialize-from-runtime-model is only supported for bounded_decoder_ce_probe")
    if args.initialize_from_runtime_model is not None and not Path(args.initialize_from_runtime_model).exists():
        errors.append("--initialize-from-runtime-model path does not exist")
    errors.extend(validate_generation_prefix_contract(args, rows))
    if getattr(args, "generation_repetition_guard", False) and not args.enable_generation_audit:
        errors.append("--generation-repetition-guard requires --enable-generation-audit")

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
            "bounded_choice_aux_weight": args.bounded_choice_aux_weight,
            "bounded_choice_contrast_weight": args.bounded_choice_contrast_weight,
            "bounded_choice_contrast_margin": args.bounded_choice_contrast_margin,
            "eos_loss_weight": args.eos_loss_weight,
            "structured_aux_weight": args.structured_aux_weight,
            "denoise_weight": args.denoise_weight,
            "eval_interval": args.eval_interval,
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
        "generation_repetition_guard": bool(getattr(args, "generation_repetition_guard", False)),
        "generation_repetition_guard_top_k": int(getattr(args, "generation_repetition_guard_top_k", 16)),
        "runtime_model_save_requested": args.runtime_model_save_dir is not None,
        "runtime_model_save_authorized": bool(args.allow_runtime_model_save_for_harness),
        "runtime_model_save_dir": str(args.runtime_model_save_dir) if args.runtime_model_save_dir else None,
        "initialize_from_runtime_model": str(args.initialize_from_runtime_model) if args.initialize_from_runtime_model else None,
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
    contract_only_no_loss_probe = (
        bool(getattr(args, "contract_only", False))
        and int(getattr(args, "max_steps", 1)) == 0
        and float(getattr(args, "decoder_ce_weight", 1.0)) == 0.0
        and float(getattr(args, "structured_aux_weight", 1.0)) == 0.0
        and float(getattr(args, "denoise_weight", 1.0)) == 0.0
        and rows
        and all(bool(row.get("candidate_only_no_loss")) for row in rows)
    )
    episode_step_contract_only_probe = (
        bool(getattr(args, "contract_only", False))
        and args.mode == "episode_step_denoise_contract_only"
        and int(getattr(args, "max_steps", 1)) == 0
        and float(getattr(args, "decoder_ce_weight", 1.0)) == 0.0
        and float(getattr(args, "structured_aux_weight", 1.0)) == 0.0
        and float(getattr(args, "denoise_weight", 1.0)) == 0.0
        and rows
        and all(str(row.get("transition_schema")) == "episode_step_suffix_transition_v1" for row in rows)
    )

    if not implementation_guard["allowed_for_recovered_100m_target"]:
        errors.extend(str(error) for error in implementation_guard["errors"])
    errors.extend(_validate_target_100m_files(args))
    if args.decoder_ce_weight != 0:
        errors.append("structured probes require --decoder-ce-weight 0")
    if args.mode != "denoise_repair_probe" and args.denoise_weight != 0:
        errors.append("non-denoise structured probes require --denoise-weight 0")
    if args.mode == "denoise_repair_probe" and args.denoise_weight <= 0 and not contract_only_no_loss_probe:
        errors.append("denoise repair probe requires --denoise-weight > 0")
    if args.mode == "episode_step_denoise_contract_only" and not episode_step_contract_only_probe:
        errors.append("episode-step denoise contract-only mode requires --contract-only, --max-steps 0, all weights 0, and episode_step_suffix_transition_v1 rows")
    if args.mode == "episode_step_structured_probe" and not all(str(row.get("transition_schema")) == "episode_step_suffix_transition_v1" for row in rows):
        errors.append("episode-step structured probe requires episode_step_suffix_transition_v1 rows")
    if args.mode not in {"repo_graph_probe", "denoise_repair_probe", "episode_step_denoise_contract_only"} and args.structured_aux_weight <= 0:
        errors.append("structured probe requires --structured-aux-weight > 0")
    if not args.require_loss_mask_enforcement_audit:
        errors.append("--require-loss-mask-enforcement-audit is required")
    if not args.no_final_checkpoint_export:
        errors.append("--no-final-checkpoint-export is required")
    if args.skip_final_model_save != 1:
        errors.append("--skip-final-model-save 1 is required")
    if args.restore_best_structured_state:
        if args.eval_interval <= 0:
            errors.append("--restore-best-structured-state requires --eval-interval > 0")
        if args.max_eval_rows <= 0 or args.max_strict_rows <= 0:
            errors.append("--restore-best-structured-state requires eval and strict row caps")
        if not args.no_final_checkpoint_export or args.skip_final_model_save != 1:
            errors.append("--restore-best-structured-state requires checkpoint export to remain disabled")
    errors.extend(validate_generation_prefix_contract(args, rows))
    if getattr(args, "generation_repetition_guard", False) and not args.enable_generation_audit:
        errors.append("--generation-repetition-guard requires --enable-generation-audit")

    for index, row in enumerate(rows):
        row_id = str(row.get("row_id") or f"row_{index}")
        split = _row_split(row)
        split_counts[split if split in split_counts else "other"] += 1
        mask = normalize_loss_mask(row)
        enabled = {key for key, value in mask.items() if value}
        for key, value in mask.items():
            loss_counts[key] += int(value)
        row_allows_no_loss = (contract_only_no_loss_probe and bool(row.get("candidate_only_no_loss"))) or episode_step_contract_only_probe
        if not enabled and not row_allows_no_loss:
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
            if row_allows_no_loss:
                mask_errors = [error for error in mask_errors if error != "no losses enabled"]
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

    multilingual_surface_readiness = assess_multilingual_surface_readiness(args.mode, rows)
    if multilingual_surface_readiness is not None and not multilingual_surface_readiness.get("passed"):
        errors.append(
            "multilingual surface readiness failed: encoder-visible evidence does not separate labels in every language/split bucket"
        )

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
        "multilingual_surface_readiness": multilingual_surface_readiness,
        "native_feature_ablation_audit_required": bool(args.require_native_feature_ablation_audit),
        "native_feature_ablation_artifact": "feature_ablation_attribution.jsonl",
        "weights": {
            "decoder_ce_weight": args.decoder_ce_weight,
            "eos_loss_weight": args.eos_loss_weight,
            "structured_aux_weight": args.structured_aux_weight,
            "denoise_weight": args.denoise_weight,
            "eval_interval": args.eval_interval,
            "restore_best_structured_state": bool(args.restore_best_structured_state),
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
        "generation_repetition_guard": bool(getattr(args, "generation_repetition_guard", False)),
        "generation_repetition_guard_top_k": int(getattr(args, "generation_repetition_guard_top_k", 16)),
        "model_execution_attempted": False,
        "episode_step_contract_only_probe": bool(episode_step_contract_only_probe),
    }


def _namespace_with(args: argparse.Namespace, **updates: Any) -> argparse.Namespace:
    values = dict(vars(args))
    values.update(updates)
    return argparse.Namespace(**values)



def validate_tri_phase_suffix_phrase_residual_reconnect_probe(args: argparse.Namespace, rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    phase2_rows: list[dict[str, Any]] = []
    phase3_rows: list[dict[str, Any]] = []
    if args.phase2_manifest is None:
        errors.append("tri-phase reconnect requires --phase2-manifest for phrase suffix warm-up")
    else:
        try:
            phase2_rows = load_manifest(args.phase2_manifest)
        except Exception as exc:  # noqa: BLE001 - surface contract error in audit card.
            errors.append(f"phase2 manifest load failed: {exc}")
    if args.phase3_manifest is None:
        errors.append("tri-phase reconnect requires --phase3-manifest for full residual suffix ladder")
    else:
        try:
            phase3_rows = load_manifest(args.phase3_manifest)
        except Exception as exc:  # noqa: BLE001 - surface contract error in audit card.
            errors.append(f"phase3 manifest load failed: {exc}")

    if args.decoder_ce_weight != 0:
        errors.append("tri-phase reconnect requires --decoder-ce-weight 0")
    if args.structured_aux_weight <= 0:
        errors.append("tri-phase reconnect phase1 requires --structured-aux-weight > 0")
    if args.denoise_weight <= 0:
        errors.append("tri-phase reconnect phase2/phase3 requires --denoise-weight > 0")
    if args.phase2_max_train_rows <= 0 or args.phase2_max_eval_rows <= 0 or args.phase2_max_strict_rows <= 0:
        errors.append("tri-phase reconnect requires positive phase2 row caps")
    if args.phase3_max_train_rows <= 0 or args.phase3_max_eval_rows <= 0 or args.phase3_max_strict_rows <= 0:
        errors.append("tri-phase reconnect requires positive phase3 row caps")
    if args.phase2_max_steps <= 0 and not args.contract_only:
        errors.append("tri-phase reconnect execution requires --phase2-max-steps > 0")
    if args.phase3_max_steps <= 0 and not args.contract_only:
        errors.append("tri-phase reconnect execution requires --phase3-max-steps > 0")
    if args.phase2_max_decoder_tokens <= 0:
        errors.append("tri-phase reconnect requires --phase2-max-decoder-tokens > 0")
    if args.phase3_max_decoder_tokens <= 0:
        errors.append("tri-phase reconnect requires --phase3-max-decoder-tokens > 0")
    if not args.restore_best_structured_state:
        errors.append("tri-phase reconnect requires --restore-best-structured-state for phase1")
    if args.eval_interval <= 0:
        errors.append("tri-phase reconnect requires --eval-interval > 0")
    if getattr(args, "generation_repetition_guard", False) and not args.enable_generation_audit:
        errors.append("--generation-repetition-guard requires --enable-generation-audit")

    phase1_args = _namespace_with(
        args,
        mode="structured_policy_probe",
        denoise_weight=0.0,
        decoder_ce_weight=0.0,
        phase2_manifest=None,
        phase3_manifest=None,
        generation_prefix_field=None,
    )
    phase1_card = validate_structured_probe(phase1_args, rows)
    if not phase1_card.get("passed"):
        errors.append("phase1 structured contract failed")

    phase2_args = _namespace_with(
        args,
        mode="denoise_repair_probe",
        manifest=args.phase2_manifest if args.phase2_manifest is not None else args.manifest,
        max_train_rows=args.phase2_max_train_rows,
        max_eval_rows=args.phase2_max_eval_rows,
        max_strict_rows=args.phase2_max_strict_rows,
        max_steps=args.phase2_max_steps,
        max_decoder_tokens=args.phase2_max_decoder_tokens,
        structured_aux_weight=0.0,
        decoder_ce_weight=0.0,
    )
    phase2_card = validate_structured_probe(phase2_args, phase2_rows) if phase2_rows else {"passed": False, "errors": ["phase2 rows unavailable"]}
    if not phase2_card.get("passed"):
        errors.append("phase2 phrase denoise contract failed")

    phase3_args = _namespace_with(
        args,
        mode="denoise_repair_probe",
        manifest=args.phase3_manifest if args.phase3_manifest is not None else args.manifest,
        max_train_rows=args.phase3_max_train_rows,
        max_eval_rows=args.phase3_max_eval_rows,
        max_strict_rows=args.phase3_max_strict_rows,
        max_steps=args.phase3_max_steps,
        max_decoder_tokens=args.phase3_max_decoder_tokens,
        structured_aux_weight=0.0,
        decoder_ce_weight=0.0,
    )
    phase3_card = validate_structured_probe(phase3_args, phase3_rows) if phase3_rows else {"passed": False, "errors": ["phase3 rows unavailable"]}
    if not phase3_card.get("passed"):
        errors.append("phase3 full residual denoise contract failed")

    return {
        "passed": not errors,
        "errors": errors,
        "mode": args.mode,
        "manifest": str(args.manifest),
        "manifest_sha256": _manifest_hash(args.manifest),
        "phase2_manifest": str(args.phase2_manifest) if args.phase2_manifest else None,
        "phase2_manifest_sha256": _manifest_hash(args.phase2_manifest) if args.phase2_manifest and args.phase2_manifest.exists() else None,
        "phase3_manifest": str(args.phase3_manifest) if args.phase3_manifest else None,
        "phase3_manifest_sha256": _manifest_hash(args.phase3_manifest) if args.phase3_manifest and args.phase3_manifest.exists() else None,
        "rows": len(rows) + len(phase2_rows) + len(phase3_rows),
        "phase1_rows": len(rows),
        "phase2_rows": len(phase2_rows),
        "phase3_rows": len(phase3_rows),
        "phase1_contract": phase1_card,
        "phase2_contract": phase2_card,
        "phase3_contract": phase3_card,
        "weights": {
            "decoder_ce_weight": args.decoder_ce_weight,
            "structured_aux_weight": args.structured_aux_weight,
            "denoise_weight": args.denoise_weight,
            "phase1_max_steps": args.max_steps,
            "phase2_max_steps": args.phase2_max_steps,
            "phase3_max_steps": args.phase3_max_steps,
            "eval_interval": args.eval_interval,
            "restore_best_structured_state": bool(args.restore_best_structured_state),
        },
        "caps": {
            "phase1_max_train_rows": args.max_train_rows,
            "phase1_max_eval_rows": args.max_eval_rows,
            "phase1_max_strict_rows": args.max_strict_rows,
            "phase1_max_decoder_tokens": args.max_decoder_tokens,
            "phase2_max_train_rows": args.phase2_max_train_rows,
            "phase2_max_eval_rows": args.phase2_max_eval_rows,
            "phase2_max_strict_rows": args.phase2_max_strict_rows,
            "phase2_max_decoder_tokens": args.phase2_max_decoder_tokens,
            "phase3_max_train_rows": args.phase3_max_train_rows,
            "phase3_max_eval_rows": args.phase3_max_eval_rows,
            "phase3_max_strict_rows": args.phase3_max_strict_rows,
            "phase3_max_decoder_tokens": args.phase3_max_decoder_tokens,
        },
        "final_checkpoint_export_disabled": bool(args.no_final_checkpoint_export),
        "final_model_save_skipped": args.skip_final_model_save == 1,
        "cleanup_requested": bool(args.cleanup_checkpoints_after_probe),
        "generation_audit_requested": bool(args.enable_generation_audit),
        "max_generation_rows": int(args.max_generation_rows),
        "max_generation_tokens": int(args.max_generation_tokens),
        "generation_prefix_field": getattr(args, "generation_prefix_field", None),
        "generation_audit_splits": getattr(args, "generation_audit_splits", "eval,strict_eval"),
        "generation_repetition_guard": bool(getattr(args, "generation_repetition_guard", False)),
        "generation_repetition_guard_top_k": int(getattr(args, "generation_repetition_guard_top_k", 16)),
        "model_execution_attempted": False,
        "contract_only": bool(args.contract_only),
    }

def validate_two_phase_structured_reconnect_probe(args: argparse.Namespace, rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    if args.phase2_manifest is None:
        errors.append("two-phase structured reconnect requires --phase2-manifest")
        phase2_rows: list[dict[str, Any]] = []
    else:
        try:
            phase2_rows = load_manifest(args.phase2_manifest)
        except Exception as exc:  # noqa: BLE001 - surface contract error in audit card.
            errors.append(f"phase2 manifest load failed: {exc}")
            phase2_rows = []

    if args.decoder_ce_weight != 0:
        errors.append("two-phase structured reconnect requires --decoder-ce-weight 0")
    if args.structured_aux_weight <= 0:
        errors.append("two-phase structured reconnect requires --structured-aux-weight > 0")
    if args.denoise_weight != 0:
        errors.append("two-phase structured reconnect requires --denoise-weight 0")
    if args.phase2_max_train_rows <= 0 or args.phase2_max_eval_rows <= 0 or args.phase2_max_strict_rows <= 0:
        errors.append("two-phase structured reconnect requires positive phase2 row caps")
    if args.phase2_max_steps <= 0 and not args.contract_only:
        errors.append("two-phase structured reconnect execution requires --phase2-max-steps > 0")
    if args.phase2_max_decoder_tokens <= 0:
        errors.append("two-phase structured reconnect requires --phase2-max-decoder-tokens > 0")
    if not args.restore_best_structured_state:
        errors.append("two-phase structured reconnect requires --restore-best-structured-state for phase1")
    if args.eval_interval <= 0:
        errors.append("two-phase structured reconnect requires --eval-interval > 0")

    phase1_mode, phase1_mode_errors = infer_structured_probe_mode(rows)
    phase2_mode, phase2_mode_errors = infer_structured_probe_mode(phase2_rows) if phase2_rows else (None, ["phase2 rows unavailable"])
    errors.extend(phase1_mode_errors)
    errors.extend(phase2_mode_errors)
    if phase1_mode and phase2_mode and phase1_mode != phase2_mode:
        errors.append(f"phase1/phase2 structured modes differ: {phase1_mode} vs {phase2_mode}")

    phase1_args = _namespace_with(
        args,
        mode=phase1_mode or "edit_localization_probe",
        denoise_weight=0.0,
        decoder_ce_weight=0.0,
        phase2_manifest=None,
        generation_prefix_field=None,
    )
    phase1_card = validate_structured_probe(phase1_args, rows)
    if not phase1_card.get("passed"):
        errors.append("phase1 structured contract failed")

    phase2_args = _namespace_with(
        args,
        mode=phase2_mode or phase1_mode or "edit_localization_probe",
        manifest=args.phase2_manifest if args.phase2_manifest is not None else args.manifest,
        max_train_rows=args.phase2_max_train_rows,
        max_eval_rows=args.phase2_max_eval_rows,
        max_strict_rows=args.phase2_max_strict_rows,
        max_steps=args.phase2_max_steps,
        max_decoder_tokens=args.phase2_max_decoder_tokens,
        denoise_weight=0.0,
        decoder_ce_weight=0.0,
    )
    phase2_card = validate_structured_probe(phase2_args, phase2_rows) if phase2_rows else {"passed": False, "errors": ["phase2 rows unavailable"]}
    if not phase2_card.get("passed"):
        errors.append("phase2 structured contract failed")

    return {
        "passed": not errors,
        "errors": errors,
        "mode": args.mode,
        "manifest": str(args.manifest),
        "manifest_sha256": _manifest_hash(args.manifest),
        "phase2_manifest": str(args.phase2_manifest) if args.phase2_manifest else None,
        "phase2_manifest_sha256": _manifest_hash(args.phase2_manifest) if args.phase2_manifest and args.phase2_manifest.exists() else None,
        "rows": len(rows) + len(phase2_rows),
        "phase1_rows": len(rows),
        "phase2_rows": len(phase2_rows),
        "phase1_mode": phase1_mode,
        "phase2_mode": phase2_mode,
        "phase1_contract": phase1_card,
        "phase2_contract": phase2_card,
        "weights": {
            "decoder_ce_weight": args.decoder_ce_weight,
            "structured_aux_weight": args.structured_aux_weight,
            "denoise_weight": args.denoise_weight,
            "phase1_max_steps": args.max_steps,
            "phase2_max_steps": args.phase2_max_steps,
            "phase2_learning_rate": args.phase2_learning_rate if args.phase2_learning_rate is not None else args.learning_rate,
            "eval_interval": args.eval_interval,
            "restore_best_structured_state": bool(args.restore_best_structured_state),
            "structured_trainable_profile": args.structured_trainable_profile,
            "phase2_structured_trainable_profile": args.phase2_structured_trainable_profile or args.structured_trainable_profile,
        },
        "caps": {
            "phase1_max_train_rows": args.max_train_rows,
            "phase1_max_eval_rows": args.max_eval_rows,
            "phase1_max_strict_rows": args.max_strict_rows,
            "phase1_max_decoder_tokens": args.max_decoder_tokens,
            "phase2_max_train_rows": args.phase2_max_train_rows,
            "phase2_max_eval_rows": args.phase2_max_eval_rows,
            "phase2_max_strict_rows": args.phase2_max_strict_rows,
            "phase2_max_decoder_tokens": args.phase2_max_decoder_tokens,
        },
        "final_checkpoint_export_disabled": bool(args.no_final_checkpoint_export),
        "final_model_save_skipped": args.skip_final_model_save == 1,
        "cleanup_requested": bool(args.cleanup_checkpoints_after_probe),
        "generation_audit_requested": bool(args.enable_generation_audit),
        "max_generation_rows": int(args.max_generation_rows),
        "max_generation_tokens": int(args.max_generation_tokens),
        "generation_prefix_field": getattr(args, "generation_prefix_field", None),
        "generation_audit_splits": getattr(args, "generation_audit_splits", "eval,strict_eval"),
        "generation_repetition_guard": bool(getattr(args, "generation_repetition_guard", False)),
        "generation_repetition_guard_top_k": int(getattr(args, "generation_repetition_guard_top_k", 16)),
        "model_execution_attempted": False,
        "contract_only": bool(getattr(args, "contract_only", False)),
        "two_phase_in_memory_required": True,
        "checkpoint_export_allowed_between_phases": False,
    }


def validate_two_phase_suffix_denoise_reconnect_probe(args: argparse.Namespace, rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    if args.phase2_manifest is None:
        errors.append("two-phase suffix/denoise reconnect requires --phase2-manifest")
        phase2_rows: list[dict[str, Any]] = []
    else:
        try:
            phase2_rows = load_manifest(args.phase2_manifest)
        except Exception as exc:  # noqa: BLE001 - surface contract error in audit card.
            errors.append(f"phase2 manifest load failed: {exc}")
            phase2_rows = []

    if args.decoder_ce_weight != 0:
        errors.append("two-phase suffix/denoise reconnect requires --decoder-ce-weight 0")
    if args.structured_aux_weight <= 0:
        errors.append("two-phase suffix/denoise reconnect phase1 requires --structured-aux-weight > 0")
    if args.denoise_weight <= 0:
        errors.append("two-phase suffix/denoise reconnect phase2 requires --denoise-weight > 0")
    if args.phase2_max_train_rows <= 0 or args.phase2_max_eval_rows <= 0 or args.phase2_max_strict_rows <= 0:
        errors.append("two-phase suffix/denoise reconnect requires positive phase2 row caps")
    if args.phase2_max_steps <= 0 and not args.contract_only:
        errors.append("two-phase suffix/denoise reconnect execution requires --phase2-max-steps > 0")
    if args.phase2_max_decoder_tokens <= 0:
        errors.append("two-phase suffix/denoise reconnect requires --phase2-max-decoder-tokens > 0")
    if not args.restore_best_structured_state:
        errors.append("two-phase suffix/denoise reconnect requires --restore-best-structured-state for phase1")
    if args.eval_interval <= 0:
        errors.append("two-phase suffix/denoise reconnect requires --eval-interval > 0")
    if getattr(args, "generation_repetition_guard", False) and not args.enable_generation_audit:
        errors.append("--generation-repetition-guard requires --enable-generation-audit")

    phase1_args = _namespace_with(
        args,
        mode="structured_policy_probe",
        denoise_weight=0.0,
        decoder_ce_weight=0.0,
        phase2_manifest=None,
        generation_prefix_field=None,
    )
    phase1_card = validate_structured_probe(phase1_args, rows)
    if not phase1_card.get("passed"):
        errors.append("phase1 structured contract failed")

    phase2_args = _namespace_with(
        args,
        mode="denoise_repair_probe",
        manifest=args.phase2_manifest if args.phase2_manifest is not None else args.manifest,
        max_train_rows=args.phase2_max_train_rows,
        max_eval_rows=args.phase2_max_eval_rows,
        max_strict_rows=args.phase2_max_strict_rows,
        max_steps=args.phase2_max_steps,
        max_decoder_tokens=args.phase2_max_decoder_tokens,
        structured_aux_weight=0.0,
        decoder_ce_weight=0.0,
    )
    phase2_card = validate_structured_probe(phase2_args, phase2_rows) if phase2_rows else {"passed": False, "errors": ["phase2 rows unavailable"]}
    if not phase2_card.get("passed"):
        errors.append("phase2 denoise contract failed")

    return {
        "passed": not errors,
        "errors": errors,
        "mode": args.mode,
        "manifest": str(args.manifest),
        "manifest_sha256": _manifest_hash(args.manifest),
        "phase2_manifest": str(args.phase2_manifest) if args.phase2_manifest else None,
        "phase2_manifest_sha256": _manifest_hash(args.phase2_manifest) if args.phase2_manifest and args.phase2_manifest.exists() else None,
        "rows": len(rows) + len(phase2_rows),
        "phase1_rows": len(rows),
        "phase2_rows": len(phase2_rows),
        "phase1_contract": phase1_card,
        "phase2_contract": phase2_card,
        "weights": {
            "decoder_ce_weight": args.decoder_ce_weight,
            "structured_aux_weight": args.structured_aux_weight,
            "denoise_weight": args.denoise_weight,
            "phase1_max_steps": args.max_steps,
            "phase2_max_steps": args.phase2_max_steps,
            "eval_interval": args.eval_interval,
            "restore_best_structured_state": bool(args.restore_best_structured_state),
        },
        "caps": {
            "phase1_max_train_rows": args.max_train_rows,
            "phase1_max_eval_rows": args.max_eval_rows,
            "phase1_max_strict_rows": args.max_strict_rows,
            "phase1_max_decoder_tokens": args.max_decoder_tokens,
            "phase2_max_train_rows": args.phase2_max_train_rows,
            "phase2_max_eval_rows": args.phase2_max_eval_rows,
            "phase2_max_strict_rows": args.phase2_max_strict_rows,
            "phase2_max_decoder_tokens": args.phase2_max_decoder_tokens,
        },
        "final_checkpoint_export_disabled": bool(args.no_final_checkpoint_export),
        "final_model_save_skipped": args.skip_final_model_save == 1,
        "cleanup_requested": bool(args.cleanup_checkpoints_after_probe),
        "generation_audit_requested": bool(args.enable_generation_audit),
        "max_generation_rows": int(args.max_generation_rows),
        "max_generation_tokens": int(args.max_generation_tokens),
        "generation_prefix_field": getattr(args, "generation_prefix_field", None),
        "generation_audit_splits": getattr(args, "generation_audit_splits", "eval,strict_eval"),
        "generation_repetition_guard": bool(getattr(args, "generation_repetition_guard", False)),
        "generation_repetition_guard_top_k": int(getattr(args, "generation_repetition_guard_top_k", 16)),
        "model_execution_attempted": False,
        "contract_only": bool(getattr(args, "contract_only", False)),
        "two_phase_in_memory_required": True,
        "checkpoint_export_allowed_between_phases": False,
    }


def validate_contract(args: argparse.Namespace, rows: list[dict[str, Any]]) -> dict[str, Any]:
    repo = args.repo_root.resolve()
    out = args.output_dir.resolve()
    if not str(out).startswith(str(repo) + "/"):
        raise ProbeContractError(f"output_dir must be under repo_root: {out} not under {repo}")
    if args.mode == "bounded_decoder_ce_probe":
        return validate_bounded_decoder_ce_probe(args, rows)
    if args.mode == "tri_phase_suffix_phrase_residual_reconnect_probe":
        return validate_tri_phase_suffix_phrase_residual_reconnect_probe(args, rows)
    if args.mode == "two_phase_structured_reconnect_probe":
        return validate_two_phase_structured_reconnect_probe(args, rows)
    if args.mode == "two_phase_suffix_denoise_reconnect_probe":
        return validate_two_phase_suffix_denoise_reconnect_probe(args, rows)
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
    marker.write_text(f"run_id={args.run_id}\nmode={args.mode}\ncontract_only={str(bool(args.contract_only)).lower()}\n", encoding="utf-8")
    _write_json(out / "probe_contract_audit.json", card)
    if not args.contract_only:
        return
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
            cleanup = {
                "cleanup_requested": True,
                "cleanup_executed": False,
                "cleanup_reason": f"unsafe_path:{exc}",
                "run_id": args.run_id,
                "output_dir": str(out),
            }
        _write_json(out / "cleanup_dry_run.json", cleanup)

def persist_execution_telemetry(args: argparse.Namespace, card: dict[str, Any], result: dict[str, Any]) -> None:
    out = args.output_dir.resolve()
    repo_root = args.repo_root.resolve()
    executed_card = dict(card)
    executed_card["model_execution_attempted"] = True
    executed_card["contract_only"] = False
    executed_card["runtime_executed"] = bool(result.get("runtime_executed"))
    executed_card["gemma_executed"] = bool(result.get("gemma_executed"))
    executed_card["harness_executed"] = bool(result.get("harness_executed"))
    executed_card["final_checkpoint_exported"] = bool(result.get("final_checkpoint_exported"))
    executed_card["execution_result_path"] = str((out / "execution_result.json").relative_to(repo_root))
    _write_json(out / "probe_contract_audit.json", executed_card)
    marker = out / ".agentkernel_probe_output"
    marker.write_text(f"run_id={args.run_id}\nmode={args.mode}\ncontract_only=false\n", encoding="utf-8")


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
    from agentkernel_lite.training_loop import run_bounded_decoder_ce_probe, run_denoise_repair_probe, run_structured_aux_probe, run_tri_phase_suffix_phrase_residual_reconnect_probe, run_two_phase_structured_reconnect_probe, run_two_phase_suffix_denoise_reconnect_probe

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
    if args.mode == "tri_phase_suffix_phrase_residual_reconnect_probe":
        if args.phase2_manifest is None or args.phase3_manifest is None:
            raise ProbeContractError("tri-phase execution requires --phase2-manifest and --phase3-manifest")
        phase2_rows = load_manifest(args.phase2_manifest)
        phase3_rows = load_manifest(args.phase3_manifest)
        result = run_tri_phase_suffix_phrase_residual_reconnect_probe(
            phase1_rows=rows,
            phase2_rows=phase2_rows,
            phase3_rows=phase3_rows,
            output_dir=args.output_dir,
            run_id=args.run_id,
            max_train_rows=args.max_train_rows,
            max_eval_rows=args.max_eval_rows,
            max_strict_rows=args.max_strict_rows,
            max_steps=args.max_steps,
            phase2_max_train_rows=args.phase2_max_train_rows,
            phase2_max_eval_rows=args.phase2_max_eval_rows,
            phase2_max_strict_rows=args.phase2_max_strict_rows,
            phase2_max_steps=args.phase2_max_steps,
            phase3_max_train_rows=args.phase3_max_train_rows,
            phase3_max_eval_rows=args.phase3_max_eval_rows,
            phase3_max_strict_rows=args.phase3_max_strict_rows,
            phase3_max_steps=args.phase3_max_steps,
            batch_size=args.batch_size,
            max_encoder_tokens=args.max_encoder_tokens,
            max_decoder_tokens=args.max_decoder_tokens,
            phase2_max_decoder_tokens=args.phase2_max_decoder_tokens,
            phase3_max_decoder_tokens=args.phase3_max_decoder_tokens,
            learning_rate=args.learning_rate,
            implementation=args.implementation,
            probe_scale=args.probe_scale,
            model_config=args.model_config,
            tokenizer_json=args.tokenizer_json,
            tokenizer_config=args.tokenizer_config,
            eval_interval=args.eval_interval,
            eos_loss_weight=args.eos_loss_weight,
            enable_generation_audit=args.enable_generation_audit,
            max_generation_rows=args.max_generation_rows,
            max_generation_tokens=args.max_generation_tokens,
            generation_prefix_field=args.generation_prefix_field,
            generation_audit_splits=args.generation_audit_splits,
            generation_repetition_guard=args.generation_repetition_guard,
            generation_repetition_guard_top_k=args.generation_repetition_guard_top_k,
            decoder_ce_weight=args.decoder_ce_weight,
            bounded_choice_aux_weight=args.bounded_choice_aux_weight,
            bounded_choice_aux_source=args.bounded_choice_aux_source,
        )
    elif args.mode == "two_phase_structured_reconnect_probe":
        if args.phase2_manifest is None:
            raise ProbeContractError("two-phase structured execution requires --phase2-manifest")
        phase2_rows = load_manifest(args.phase2_manifest)
        phase1_mode, phase1_mode_errors = infer_structured_probe_mode(rows)
        phase2_mode, phase2_mode_errors = infer_structured_probe_mode(phase2_rows)
        if phase1_mode_errors or phase2_mode_errors or phase1_mode != phase2_mode or phase1_mode is None:
            raise ProbeContractError(
                "two-phase structured execution requires one shared structured task mode across both manifests"
            )
        result = run_two_phase_structured_reconnect_probe(
            phase1_rows=rows,
            phase2_rows=phase2_rows,
            phase1_mode=phase1_mode,
            phase2_mode=phase2_mode,
            output_dir=args.output_dir,
            run_id=args.run_id,
            max_train_rows=args.max_train_rows,
            max_eval_rows=args.max_eval_rows,
            max_strict_rows=args.max_strict_rows,
            max_steps=args.max_steps,
            phase2_max_train_rows=args.phase2_max_train_rows,
            phase2_max_eval_rows=args.phase2_max_eval_rows,
            phase2_max_strict_rows=args.phase2_max_strict_rows,
            phase2_max_steps=args.phase2_max_steps,
            batch_size=args.batch_size,
            max_encoder_tokens=args.max_encoder_tokens,
            max_decoder_tokens=args.max_decoder_tokens,
            phase2_max_decoder_tokens=args.phase2_max_decoder_tokens,
            learning_rate=args.learning_rate,
            phase2_learning_rate=args.phase2_learning_rate,
            implementation=args.implementation,
            structured_trainable_profile=args.structured_trainable_profile,
            phase2_structured_trainable_profile=args.phase2_structured_trainable_profile,
            probe_scale=args.probe_scale,
            model_config=args.model_config,
            tokenizer_json=args.tokenizer_json,
            tokenizer_config=args.tokenizer_config,
            eval_interval=args.eval_interval,
        )
    elif args.mode == "two_phase_suffix_denoise_reconnect_probe":
        if args.phase2_manifest is None:
            raise ProbeContractError("two-phase execution requires --phase2-manifest")
        phase2_rows = load_manifest(args.phase2_manifest)
        result = run_two_phase_suffix_denoise_reconnect_probe(
            phase1_rows=rows,
            phase2_rows=phase2_rows,
            output_dir=args.output_dir,
            run_id=args.run_id,
            max_train_rows=args.max_train_rows,
            max_eval_rows=args.max_eval_rows,
            max_strict_rows=args.max_strict_rows,
            max_steps=args.max_steps,
            phase2_max_train_rows=args.phase2_max_train_rows,
            phase2_max_eval_rows=args.phase2_max_eval_rows,
            phase2_max_strict_rows=args.phase2_max_strict_rows,
            phase2_max_steps=args.phase2_max_steps,
            batch_size=args.batch_size,
            max_encoder_tokens=args.max_encoder_tokens,
            max_decoder_tokens=args.max_decoder_tokens,
            phase2_max_decoder_tokens=args.phase2_max_decoder_tokens,
            learning_rate=args.learning_rate,
            implementation=args.implementation,
            probe_scale=args.probe_scale,
            model_config=args.model_config,
            tokenizer_json=args.tokenizer_json,
            tokenizer_config=args.tokenizer_config,
            eval_interval=args.eval_interval,
            eos_loss_weight=args.eos_loss_weight,
            enable_generation_audit=args.enable_generation_audit,
            max_generation_rows=args.max_generation_rows,
            max_generation_tokens=args.max_generation_tokens,
            generation_prefix_field=args.generation_prefix_field,
            generation_audit_splits=args.generation_audit_splits,
            generation_repetition_guard=args.generation_repetition_guard,
            generation_repetition_guard_top_k=args.generation_repetition_guard_top_k,
            bounded_choice_aux_weight=args.bounded_choice_aux_weight,
        )
    elif args.mode == "bounded_decoder_ce_probe":
        result = run_bounded_decoder_ce_probe(
            **common,
            enable_generation_audit=args.enable_generation_audit,
            max_generation_rows=args.max_generation_rows,
            max_generation_tokens=args.max_generation_tokens,
            eos_loss_weight=args.eos_loss_weight,
            generation_prefix_field=args.generation_prefix_field,
            generation_audit_splits=args.generation_audit_splits,
            generation_repetition_guard=args.generation_repetition_guard,
            generation_repetition_guard_top_k=args.generation_repetition_guard_top_k,
            decoder_ce_weight=args.decoder_ce_weight,
            bounded_choice_aux_weight=args.bounded_choice_aux_weight,
            bounded_choice_aux_source=args.bounded_choice_aux_source,
            bounded_choice_contrast_weight=args.bounded_choice_contrast_weight,
            bounded_choice_contrast_margin=args.bounded_choice_contrast_margin,
            bounded_choice_verifier_value_listwise_weight=args.bounded_choice_verifier_value_listwise_weight,
            bounded_choice_same_role_listwise_weight=args.bounded_choice_same_role_listwise_weight,
            bounded_choice_root_group_aux_weight=args.bounded_choice_root_group_aux_weight,
            bounded_decoder_train_sampler=args.bounded_decoder_train_sampler,
            bounded_choice_train_head_only=args.bounded_choice_train_head_only,
            initialize_from_runtime_model=args.initialize_from_runtime_model,
            preservation_reference_runtime_model=args.preservation_reference_runtime_model,
            preservation_kl_weight=args.preservation_kl_weight,
            preservation_exempt_flag=args.preservation_exempt_flag,
            runtime_model_save_dir=args.runtime_model_save_dir,
            runtime_model_save_metadata={
                "model_config": str(args.model_config) if args.model_config else None,
                "tokenizer_json": str(args.tokenizer_json) if args.tokenizer_json else None,
                "tokenizer_config": str(args.tokenizer_config) if args.tokenizer_config else None,
                "tokenizer_hashlock": str(args.tokenizer_hashlock) if args.tokenizer_hashlock else None,
                "run_id": str(args.run_id),
                "mode": str(args.mode),
                "probe_scale": str(args.probe_scale),
                "implementation": str(args.implementation),
                "bounded_choice_aux_source": str(args.bounded_choice_aux_source),
                "bounded_choice_contrast_weight": float(args.bounded_choice_contrast_weight),
                "bounded_choice_contrast_margin": float(args.bounded_choice_contrast_margin),
                "bounded_choice_verifier_value_listwise_weight": float(args.bounded_choice_verifier_value_listwise_weight),
                "bounded_choice_same_role_listwise_weight": float(args.bounded_choice_same_role_listwise_weight),
                "bounded_choice_root_group_aux_weight": float(args.bounded_choice_root_group_aux_weight),
                "bounded_decoder_train_sampler": str(args.bounded_decoder_train_sampler),
                "bounded_choice_train_head_only": bool(args.bounded_choice_train_head_only),
            },
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
            generation_repetition_guard=args.generation_repetition_guard,
            generation_repetition_guard_top_k=args.generation_repetition_guard_top_k,
        )
    elif args.mode in STRUCTURED_MODE_ALLOWED_LOSSES and args.mode != "repo_graph_probe":
        result = run_structured_aux_probe(
            mode=args.mode,
            eval_interval=args.eval_interval,
            restore_best_structured_state=args.restore_best_structured_state,
            require_native_feature_ablation_audit=args.require_native_feature_ablation_audit,
            structured_trainable_profile=args.structured_trainable_profile,
            **common,
        )
    else:
        raise ProbeContractError(f"execution is not restored for mode: {args.mode}")
    if args.mode == "bounded_decoder_ce_probe":
        required_artifacts = REQUIRED_BOUNDED_ARTIFACTS
    elif args.mode == "denoise_repair_probe":
        required_artifacts = REQUIRED_DENOISE_ARTIFACTS
    else:
        required_artifacts = REQUIRED_STRUCTURED_ARTIFACTS
    runtime_artifact_status = {}
    for name in required_artifacts:
        path = args.output_dir / name
        exists = path.exists()
        bytes_written = path.stat().st_size if exists else 0
        runtime_artifact_status[name] = {"exists": exists, "bytes": bytes_written}
    result["runtime_artifact_status"] = runtime_artifact_status
    result["required_artifacts_written"] = all(
        status["exists"] and (not name.endswith(".jsonl") or status["bytes"] > 0)
        for name, status in runtime_artifact_status.items()
    )
    _write_json(args.output_dir / "execution_result.json", result)
    return result

def main() -> None:
    args = parse_args()
    args.repo_root = args.repo_root.resolve()
    args.output_dir = args.output_dir.resolve()
    if getattr(args, "manifest", None) is not None and not args.manifest.is_absolute():
        args.manifest = (args.repo_root / args.manifest).resolve()
    if getattr(args, "phase2_manifest", None) is not None and args.phase2_manifest is not None and not args.phase2_manifest.is_absolute():
        args.phase2_manifest = (args.repo_root / args.phase2_manifest).resolve()
    if getattr(args, "phase3_manifest", None) is not None and args.phase3_manifest is not None and not args.phase3_manifest.is_absolute():
        args.phase3_manifest = (args.repo_root / args.phase3_manifest).resolve()
    if getattr(args, "model_config", None) is not None and args.model_config is not None and not args.model_config.is_absolute():
        args.model_config = (args.repo_root / args.model_config).resolve()
    if getattr(args, "tokenizer_json", None) is not None and args.tokenizer_json is not None and not args.tokenizer_json.is_absolute():
        args.tokenizer_json = (args.repo_root / args.tokenizer_json).resolve()
    if getattr(args, "tokenizer_config", None) is not None and args.tokenizer_config is not None and not args.tokenizer_config.is_absolute():
        args.tokenizer_config = (args.repo_root / args.tokenizer_config).resolve()
    if getattr(args, "tokenizer_hashlock", None) is not None and args.tokenizer_hashlock is not None and not args.tokenizer_hashlock.is_absolute():
        args.tokenizer_hashlock = (args.repo_root / args.tokenizer_hashlock).resolve()
    if getattr(args, "runtime_model_save_dir", None) is not None and args.runtime_model_save_dir is not None and not args.runtime_model_save_dir.is_absolute():
        args.runtime_model_save_dir = (args.repo_root / args.runtime_model_save_dir).resolve()
    if getattr(args, "initialize_from_runtime_model", None) is not None and args.initialize_from_runtime_model is not None and not args.initialize_from_runtime_model.is_absolute():
        args.initialize_from_runtime_model = (args.repo_root / args.initialize_from_runtime_model).resolve()
    if getattr(args, "preservation_reference_runtime_model", None) is not None and args.preservation_reference_runtime_model is not None and not args.preservation_reference_runtime_model.is_absolute():
        args.preservation_reference_runtime_model = (args.repo_root / args.preservation_reference_runtime_model).resolve()
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
    persist_execution_telemetry(args, card, result)
    print(json.dumps({"execution_result": result}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
