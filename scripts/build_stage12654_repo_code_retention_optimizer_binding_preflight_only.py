#!/usr/bin/env python3
# Materialize repo/code retention+shortcut and optimizer/trainer binding contracts, without authorizing training.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12654_repo_code_retention_optimizer_binding_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12653 = ROOT / "runs/local/artifacts/stage12653_repo_code_training_run_authorization_preflight_only"
S12653_SUMMARY = ROOT / "runs/summaries/stage12653_repo_code_training_run_authorization_preflight_only.json"
S12653_SCRIPT = ROOT / "scripts/build_stage12653_repo_code_training_run_authorization_preflight_only.py"
S12653_TESTS = ROOT / "tests/test_stage12653_repo_code_training_run_authorization_preflight_only.py"
S12651_MANIFEST = ROOT / "runs/local/artifacts/stage12651_repo_code_curriculum_ingestion_contract_preflight_only/private/repo_code_curriculum_ingest_manifest.jsonl"
CURRICULUM_DOC = ROOT / "docs/MAINTAINER_100M_TRAINING_STAGE_STRUCTURE.md"
TRAINER_SCRIPT = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
LOSS_MASK_CARD = ROOT / "scripts/loss_mask_card.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"

EXPECTED_HASHES = {
    "stage12653_summary": "28e65a0e358803e1041f4bfe6bd3993ec45487b2efb8686ae2b4a2f3bfb4c51f",
    "stage12653_contract": "9fb0409edc829565dc2632f882fe89d2071f16a71daab80d348f11edc03c074f",
    "stage12653_pointer": "9b5f83a181d6a36b1165e59bde51254f6ed3a4f7e6ec10fe8b74e76eb3c335a8",
    "stage12653_private_packet": "8d763ee8a809627e7ce1c1dd276c94b173813e7679ae12e94cce22ff66e8267a",
    "stage12653_script_bytes": "f77b019caf881bf0e1702c152ae23c42f09ff86c9a2558ac7bb82a1b865f4a22",
    "stage12653_tests_bytes": "ac6179fe43b120b5b8ca1f8bcfd4b20e7c030d8f2bcc9ea1456eef169b68ad4e",
    "stage12651_manifest_bytes": "d19e8b0139d1dd179ca369b7db8c4252b8ac4e711855208fd273ec9419a46cb1",
    "stage12651_manifest_semantic": "21b3d427575a7883950600ab93e0980d3f74ad52f146bde58d6eba27144ead79",
    "curriculum_doc_bytes": "cf6204f501f5226c96d9fe892334ac19822f6473b98d4cbcf2dfcb05fd0551af",
    "trainer_script_bytes": "06dc20186a4f4767bfd7c6ccc8209f374d738ec1f8696cabbc2a16472422971a",
    "loss_mask_card_bytes": "b6acd7e6713610818e7e069d859d5756060e2f0c6f7f5c3cc670f8cf3b0ae24c",
    "model_config_bytes": "dda55307003800072d98070a4f744ebd0f8262c5680fa1b0f74c5724b32f5a77",
    "tokenizer_json_bytes": "c268a145d01e26047d7773d9888c13902ab0cbf0e59da333ba2b686fec4ae324",
    "tokenizer_config_bytes": "0987f58448a3163615eb167d93973fa209d7ccb12dd5c7a35c1e8ab166299be0",
    "tokenizer_hashlock_bytes": "04f12bd6bf3cd24b17f9eeba4200f7ff2c99222cd2b38e3f41dc4fa6ab08f1a9",
}
EXPECTED_STAGE12653_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/repo_code_training_run_authorization_preflight.json",
    "summary.json",
]
EXPECTED_LANES = {
    "repo_code_knowledge.repo_capability_profile": 200,
    "repo_code_knowledge.symbol_reference_prediction": 80,
}
EXPECTED_OBJECTIVES = {"repo_code_capability_ce": 200, "source_backed_symbol_binding_ce": 80}
EXPECTED_SPLITS = {"eval": 64, "strict_eval": 63, "train": 153}
RESOLVED_BLOCKERS = (
    "retention_eval_and_shortcut_baseline_plan_not_materialized",
    "optimizer_context_not_bound_to_trainer_implementation",
)
REMAINING_BLOCKERS = (
    "explicit_training_authorization_missing",
    "checkpoint_parent_not_selected",
    "cuda2_only_runtime_contract_not_materialized",
    "training_pack_authorization_review_missing",
)
FALSE_FIELDS = (
    "training_admission_allowed",
    "training_allowed",
    "training_run_allowed",
    "training_admitted",
    "strict_eval_admitted",
    "sealed_eval_admitted",
    "strict_eval_eligible",
    "sealed_eval_eligible",
    "implementation_ready",
    "stage12595_allowed",
    "replay_trustworthy",
    "level_3_materialized",
    "gpu_allocation_requested",
    "cuda2_training_allowed",
    "vm_runner_execution_allowed",
    "runtime_authorized",
    "model_execution_authorized_next",
    "source_emission_authorized",
    "body_emission_authorized",
    "decoder_ce_training_authorized_next",
    "transition_head_training_authorized_next",
    "promotion_ready",
    "optimizer_step_authorized",
)
FORBIDDEN_SUBSTRINGS = (
    "/data/",
    "/arxiv/",
    '"model_input":',
    '"target_text":',
    "source_lineage",
    "source_row_id",
    "source_ref",
    "old_source_ref_path",
    "raw_stream",
    "stdout.raw",
    "stderr.raw",
    "repo_graph_and_symbol_binding",
    "Answer:",
    "PLACEHOLDER",
    "TODO",
    "TBD",
    "<fill",
)


class Stage12654PreflightError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12654PreflightError("json_object_required:" + path.name)
    return value


def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Stage12654PreflightError(f"jsonl_object_required:{line_number}")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def false_fields() -> dict[str, bool]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if record.get(field) is not False:
            raise Stage12654PreflightError(f"{label}_gate_drift:{field}")


def assert_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12654PreflightError(f"{label}_leak_or_drift:{needle}")


def count_by(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get(field)) for row in rows).items()))


def load_inputs() -> dict[str, Any]:
    emitted = sorted(path.relative_to(S12653).as_posix() for path in S12653.rglob("*") if path.is_file())
    if emitted != EXPECTED_STAGE12653_ARTIFACTS:
        raise Stage12654PreflightError("stage12653_artifact_manifest_drift")
    summary = read_json(S12653 / "summary.json")
    external = read_json(S12653_SUMMARY)
    contract = read_json(S12653 / "contract.json")
    pointer = read_json(S12653 / "digest_pointer.json")
    private = read_json(S12653 / "private/repo_code_training_run_authorization_preflight.json")
    manifest_bytes = S12651_MANIFEST.read_bytes()
    manifest = read_jsonl_bytes(manifest_bytes)
    if summary != external:
        raise Stage12654PreflightError("stage12653_external_summary_mismatch")
    for label, value in (
        ("stage12653_summary", summary),
        ("stage12653_contract", contract),
        ("stage12653_pointer", pointer),
        ("stage12653_private_packet", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise Stage12654PreflightError("pin_drift:" + label)
    for label, path in (
        ("stage12653_script_bytes", S12653_SCRIPT),
        ("stage12653_tests_bytes", S12653_TESTS),
        ("stage12651_manifest_bytes", S12651_MANIFEST),
        ("curriculum_doc_bytes", CURRICULUM_DOC),
        ("trainer_script_bytes", TRAINER_SCRIPT),
        ("loss_mask_card_bytes", LOSS_MASK_CARD),
        ("model_config_bytes", MODEL_CONFIG),
        ("tokenizer_json_bytes", TOKENIZER_JSON),
        ("tokenizer_config_bytes", TOKENIZER_CONFIG),
        ("tokenizer_hashlock_bytes", TOKENIZER_HASHLOCK),
    ):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12654PreflightError("pin_drift:" + label)
    if stable_hash(manifest) != EXPECTED_HASHES["stage12651_manifest_semantic"]:
        raise Stage12654PreflightError("pin_drift:stage12651_manifest_semantic")
    if pointer.get("contract_sha256") != stable_hash(contract) or pointer.get("private_packet_sha256") != stable_hash(private):
        raise Stage12654PreflightError("stage12653_pointer_hash_drift")
    blockers = tuple(summary.get("authorization_blockers") or ())
    for blocker in RESOLVED_BLOCKERS + REMAINING_BLOCKERS:
        if blocker not in blockers:
            raise Stage12654PreflightError("stage12653_blocker_missing:" + blocker)
    if summary.get("next_required_action") != "stage12654_repo_code_training_authorization_independent_review_only":
        raise Stage12654PreflightError("stage12653_next_action_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12653_" + label)
        assert_sanitized(record, "stage12653_" + label)
    return {"stage12653_summary": summary, "manifest": manifest}


def build_retention_plan(manifest: list[dict[str, Any]]) -> dict[str, Any]:
    if len(manifest) != 280:
        raise Stage12654PreflightError("manifest_count_drift")
    if count_by(manifest, "split") != EXPECTED_SPLITS:
        raise Stage12654PreflightError("split_count_drift")
    if count_by(manifest, "curriculum_lane") != EXPECTED_LANES:
        raise Stage12654PreflightError("lane_count_drift")
    if count_by(manifest, "training_objective") != EXPECTED_OBJECTIVES:
        raise Stage12654PreflightError("objective_count_drift")
    train_ids = [str(row["ingest_row_id"]) for row in manifest if row.get("split") == "train"]
    eval_ids = [str(row["ingest_row_id"]) for row in manifest if row.get("split") == "eval"]
    strict_ids = [str(row["ingest_row_id"]) for row in manifest if row.get("split") == "strict_eval"]
    for row in manifest:
        assert_sanitized(row, "ingest_manifest_row")
        if row.get("trainer_consumable") is not True:
            raise Stage12654PreflightError("trainer_consumable_drift")
        if row.get("training_allowed") is not False or row.get("optimizer_step_authorized") is not False:
            raise Stage12654PreflightError("manifest_gate_drift")
    return {
        "record_type": "stage12654_private_retention_eval_shortcut_baseline_plan_v1",
        **false_fields(),
        "retention_eval_and_shortcut_baseline_plan_materialized": True,
        "retention_eval_allowed_next": False,
        "shortcut_baseline_execution_allowed_next": False,
        "plan_scope": "stage_01_repo_and_code_knowledge_nonsealed_eval_plan_only",
        "train_rows_in_scope": len(train_ids),
        "eval_rows_reserved_for_retention": len(eval_ids),
        "strict_eval_rows_reserved_not_admitted": len(strict_ids),
        "split_counts": EXPECTED_SPLITS,
        "lane_counts": EXPECTED_LANES,
        "objective_counts": EXPECTED_OBJECTIVES,
        "row_set_hashes": {
            "train_ingest_ids_sha256": stable_hash(train_ids),
            "eval_ingest_ids_sha256": stable_hash(eval_ids),
            "strict_eval_ingest_ids_sha256": stable_hash(strict_ids),
        },
        "retention_metrics_plan": [
            {"metric": "repo_capability_eval_loss_delta", "split": "eval", "rows": 64, "threshold_policy": "must_not_regress_against_parent_checkpoint_when_selected"},
            {"metric": "symbol_binding_eval_loss_delta", "split": "eval", "rows": 64, "threshold_policy": "must_not_regress_against_parent_checkpoint_when_selected"},
            {"metric": "old_language_retention_proxy", "split": "eval", "rows": 64, "threshold_policy": "report_only_until_parent_checkpoint_bound"},
        ],
        "shortcut_baseline_plan": [
            {"baseline": "lane_majority_by_split", "purpose": "detect label/lane imbalance shortcuts", "must_be_beaten_before_training_admission": True},
            {"baseline": "objective_prior_by_split", "purpose": "detect objective prior shortcut", "must_be_beaten_before_training_admission": True},
            {"baseline": "source_hash_blind_template_probe", "purpose": "detect memorized manifest-order/template shortcut", "must_be_beaten_before_training_admission": True},
            {"baseline": "symbol_query_surface_only", "purpose": "detect symbol binding shortcut without graph evidence", "must_be_beaten_before_training_admission": True},
        ],
        "sealed_eval_boundary": "strict_eval_rows_are_reserved_not_admitted_and_must_not_drive_training_admission",
    }


def build_optimizer_binding(summary: Mapping[str, Any], manifest: list[dict[str, Any]]) -> dict[str, Any]:
    run_contract = summary.get("optimizer_run_contract")
    if not isinstance(run_contract, dict):
        raise Stage12654PreflightError("stage12653_optimizer_run_contract_missing")
    if run_contract.get("trainer_implementation") is not None or run_contract.get("optimizer_and_context") is not None:
        raise Stage12654PreflightError("stage12653_unexpected_optimizer_binding_present")
    loss_keys = tuple(json.loads(json.dumps(["surface_role_ce", "repair_surface_ce", "build_mode_ce", "allowed_import_policy_ce", "blocked_import_policy_ce", "repo_dependency_policy_ce", "action_sequence_ce", "file_plan_ce", "symbol_binding_ce", "edit_localization_ce", "patch_operator_ce", "verifier_repair_ce", "suffix_choice_ce", "episode_repair_outcome_ce", "episode_failure_type_ce", "episode_boundary_match_ce", "episode_target_prefix_match_ce", "episode_step_value_mse", "decoder_ce", "denoise_ce", "runtime_reward"])))
    unsupported_objectives = sorted(set(EXPECTED_OBJECTIVES) - {"source_backed_symbol_binding_ce"})
    command_template = [
        "python",
        rel(TRAINER_SCRIPT),
        "--repo-root",
        ".",
        "--manifest",
        rel(S12651_MANIFEST),
        "--mode",
        "symbol_binding_probe",
        "--max-train-rows",
        "153",
        "--max-eval-rows",
        "64",
        "--max-strict-rows",
        "63",
        "--max-steps",
        "0",
        "--decoder-ce-weight",
        "0",
        "--structured-aux-weight",
        "1.0",
        "--denoise-weight",
        "0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--skip-final-model-save",
        "1",
        "--implementation",
        "transformer",
        "--probe-scale",
        "target_100m",
        "--model-config",
        rel(MODEL_CONFIG),
        "--tokenizer-json",
        rel(TOKENIZER_JSON),
        "--tokenizer-config",
        rel(TOKENIZER_CONFIG),
        "--tokenizer-hashlock",
        rel(TOKENIZER_HASHLOCK),
        "--output-dir",
        "runs/local/artifacts/stage12654_contract_only_trainer_probe_preview",
        "--run-id",
        "stage12654_contract_only_no_execution",
        "--contract-only",
    ]
    return {
        "record_type": "stage12654_private_optimizer_trainer_binding_contract_v1",
        **false_fields(),
        "optimizer_context_bound_to_trainer_implementation": True,
        "trainer_execution_contract_ready": False,
        "trainer_execution_contract_ready_blocker": "repo_code_capability_objective_adapter_required_before_execution_contract_can_pass",
        "trainer_implementation": rel(TRAINER_SCRIPT),
        "trainer_script_sha256": EXPECTED_HASHES["trainer_script_bytes"],
        "trainer_supported_loss_keys_sha256": stable_hash(list(loss_keys)),
        "supported_current_loss_keys": list(loss_keys),
        "stage12651_objectives": EXPECTED_OBJECTIVES,
        "unsupported_objectives_for_current_trainer_loss_keys": unsupported_objectives,
        "optimizer_and_context": {
            "optimizer": "AdamW",
            "learning_rate": 5e-5,
            "batch_size": 2,
            "max_encoder_tokens": 2048,
            "max_decoder_tokens": 768,
            "max_steps": 0,
            "trainable_profile": "full_non_decoder",
            "checkpoint_export": "disabled",
            "final_model_save": "disabled",
            "model_execution": "not_authorized",
            "gpu_policy": "CUDA_VISIBLE_DEVICES=2 required later; no allocation in this stage",
        },
        "model_config": rel(MODEL_CONFIG),
        "model_config_sha256": EXPECTED_HASHES["model_config_bytes"],
        "tokenizer_json": rel(TOKENIZER_JSON),
        "tokenizer_json_sha256": EXPECTED_HASHES["tokenizer_json_bytes"],
        "tokenizer_config": rel(TOKENIZER_CONFIG),
        "tokenizer_config_sha256": EXPECTED_HASHES["tokenizer_config_bytes"],
        "tokenizer_hashlock": rel(TOKENIZER_HASHLOCK),
        "tokenizer_hashlock_sha256": EXPECTED_HASHES["tokenizer_hashlock_bytes"],
        "contract_only_command_template": command_template,
        "manifest_rows_bound": len(manifest),
        "manifest_semantic_sha256": EXPECTED_HASHES["stage12651_manifest_semantic"],
    }


def build_packet(inputs: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    summary12653 = inputs["stage12653_summary"]
    manifest = list(inputs["manifest"])
    retention_plan = build_retention_plan(manifest)
    optimizer_binding = build_optimizer_binding(summary12653, manifest)
    true_fields = {
        "repo_code_knowledge_stage_complete": True,
        "dataset_rows_admitted": True,
        "repo_code_rows_admitted": True,
        "repo_code_training_pack_materialized": True,
        "training_pack_materialized": True,
        "training_examples_materialized": True,
        "training_pack_reviewed": True,
        "training_pack_review_passed": True,
        "curriculum_ingestion_contract_materialized": True,
        "curriculum_ingest_manifest_reviewed": True,
        "curriculum_ingest_manifest_review_passed": True,
        "separate_training_admission_required": True,
        "retention_eval_and_shortcut_baseline_plan_materialized": True,
        "optimizer_context_bound_to_trainer_implementation": True,
        "stage12654_retention_optimizer_binding_preflight_performed": True,
    }
    private = {
        "record_type": "stage12654_private_retention_optimizer_binding_packet_v1",
        **false_fields(),
        **true_fields,
        "reviewed_input_hashes": EXPECTED_HASHES,
        "retention_plan_sha256": stable_hash(retention_plan),
        "optimizer_binding_sha256": stable_hash(optimizer_binding),
        "remaining_authorization_blockers": list(REMAINING_BLOCKERS),
        "resolved_authorization_blockers": list(RESOLVED_BLOCKERS),
        "risk_register": [
            "repo_code_capability_ce_is_not_yet_native_to_legacy_loss_mask_keys",
            "parent_checkpoint_still_unselected",
            "cuda2_runtime_contract_still_unmaterialized",
            "explicit_user_training_authorization_still_missing",
        ],
    }
    contract = {
        "record_type": "stage12654_public_retention_optimizer_binding_contract_v1",
        **false_fields(),
        **true_fields,
        "retention_plan_sha256": stable_hash(retention_plan),
        "optimizer_binding_sha256": stable_hash(optimizer_binding),
        "private_packet_sha256": stable_hash(private),
        "model_ready_training_rows": 280,
        "train_rows_available": 153,
        "eval_rows_reserved": 64,
        "strict_eval_rows_reserved_not_admitted": 63,
        "remaining_authorization_blocker_count": len(REMAINING_BLOCKERS),
        "remaining_authorization_blockers": list(REMAINING_BLOCKERS),
        "resolved_authorization_blockers": list(RESOLVED_BLOCKERS),
        "trainer_execution_contract_ready": False,
        "trainer_execution_contract_ready_blocker": optimizer_binding["trainer_execution_contract_ready_blocker"],
        "next_required_action": "stage12655_repo_code_optimizer_binding_independent_review_only",
    }
    summary = {
        "record_type": "stage12654_public_retention_optimizer_binding_summary_v1",
        **false_fields(),
        **true_fields,
        "stage": STAGE,
        "decision": "RETENTION_PLAN_AND_OPTIMIZER_BINDING_MATERIALIZED_REVIEW_REQUIRED_NO_TRAINING",
        "model_ready_training_rows": 280,
        "train_rows_available": 153,
        "eval_rows_reserved": 64,
        "strict_eval_rows_reserved_not_admitted": 63,
        "remaining_authorization_blocker_count": len(REMAINING_BLOCKERS),
        "remaining_authorization_blockers": list(REMAINING_BLOCKERS),
        "resolved_authorization_blockers": list(RESOLVED_BLOCKERS),
        "trainer_execution_contract_ready": False,
        "trainer_execution_contract_ready_blocker": optimizer_binding["trainer_execution_contract_ready_blocker"],
        "retention_plan_sha256": stable_hash(retention_plan),
        "optimizer_binding_sha256": stable_hash(optimizer_binding),
        "private_packet_sha256": stable_hash(private),
        "contract_sha256": stable_hash(contract),
        "next_required_action": "stage12655_repo_code_optimizer_binding_independent_review_only",
    }
    pointer = {
        "record_type": "stage12654_public_retention_optimizer_binding_pointer_v1",
        **false_fields(),
        **true_fields,
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "retention_plan_sha256": stable_hash(retention_plan),
        "optimizer_binding_sha256": stable_hash(optimizer_binding),
        "reviewed_stage12653_summary_sha256": EXPECTED_HASHES["stage12653_summary"],
        "reviewed_stage12651_manifest_sha256": EXPECTED_HASHES["stage12651_manifest_semantic"],
    }
    for label, record in (
        ("summary", summary),
        ("contract", contract),
        ("pointer", pointer),
        ("private", private),
        ("retention_plan", retention_plan),
        ("optimizer_binding", optimizer_binding),
    ):
        check_false(record, label)
        assert_sanitized(record, label)
    return summary, contract, private, pointer, {"retention_plan": retention_plan, "optimizer_binding": optimizer_binding}


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, contract, private, pointer, private_docs = build_packet(load_inputs())
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/repo_code_retention_eval_shortcut_baseline_plan.json", private_docs["retention_plan"])
    write_json(out / "private/repo_code_optimizer_trainer_binding_contract.json", private_docs["optimizer_binding"])
    write_json(out / "private/repo_code_retention_optimizer_binding_packet.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
