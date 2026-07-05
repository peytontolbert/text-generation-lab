#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8901
NAME = "stage8901_verified_transition_record_no_mining_compiler_adapter"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "VERIFIED_TRANSITION_RECORD_COMPILER_ADAPTER_STAGE8901.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ADAPTER_CONTRACT = OUT_DIR / "verified_transition_record_no_mining_compiler_adapter_contract.json"
EXAMPLE_OUTPUT = OUT_DIR / "example_compiled_verified_transition_record.json"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

DEFAULT_LOSS_MASK = {
    "train_action_policy": False,
    "train_retrieval_policy": False,
    "train_state_transition": False,
    "train_value_head": False,
    "train_structured_aux": False,
    "train_decoder_ce": False,
    "train_denoise_ce": False,
    "train_runtime_reward": False,
}

REQUIRED_FIELDS = [
    "record_id",
    "schema_version",
    "split",
    "task_family",
    "language_family",
    "state_before",
    "retrieval_context",
    "observation",
    "action",
    "tool_result",
    "verifier_result",
    "state_after",
    "reward_signal",
    "loss_mask",
    "authority",
    "provenance",
    "anti_cheat_contract",
    "telemetry_contract",
]

FORBIDDEN_RAW_KEYS = {
    "raw_source_body",
    "raw_patch_body",
    "raw_decoder_target_text",
    "hidden_eval_answer",
    "runtime_output_body",
    "gemma_score_body",
    "unhashed_commit_message_body",
    "source_body",
    "patch_body",
    "decoder_text",
}

ALLOWED_TASK_FAMILIES = {
    "intent_to_build_strategy",
    "repo_state_graph",
    "symbol_binding",
    "edit_localization",
    "patch_operator",
    "verifier_repair",
    "bounded_decoder_argument",
    "denoise_repair",
    "research_transfer",
}

ALLOWED_SPLITS = {"train", "eval", "strict_eval", "holdout", "schema_only"}

TELEMETRY_REQUIRED = [
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_gradient_norms.jsonl",
    "feature_ablation_attribution.jsonl",
    "module_delta_norms.json",
    "failure_bucket_card.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def contains_forbidden_raw_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in FORBIDDEN_RAW_KEYS:
                return True
            if contains_forbidden_raw_key(nested):
                return True
    elif isinstance(value, list):
        return any(contains_forbidden_raw_key(item) for item in value)
    return False


def example_candidate() -> dict[str, Any]:
    return {
        "record_id": "vtr_adapter_example_0001",
        "split": "schema_only",
        "task_family": "symbol_binding",
        "language_family": "python",
        "state_before_ref": "repo_state_graph:opaque_graph_ref_0001",
        "retrieval_refs": ["source_inventory:opaque_symbol_card_0001"],
        "observation_ref": "observation:not_run_schema_only",
        "action_label": "BIND_SYMBOL",
        "action_arguments": {"query_node_id": "node_local_001", "candidate_target_ids": ["node_local_002"]},
        "tool_result_ref": "tool_result:not_run_schema_only",
        "verifier_status": "NOT_RUN",
        "state_after_ref": "repo_state_graph:expected_next_state_ref_only",
        "reward_label": "unlabeled_schema_only",
        "provenance_refs": ["stage8900_validation_contract"],
        "anti_cheat": {
            "target_coded_id": False,
            "split_overlap": False,
            "hidden_reference": False,
            "shortcut_label_visible": False,
            "raw_body_visible": False,
        },
        "route": "KEEP_STRUCTURED_SCHEMA_ONLY",
    }


def compile_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    anti_cheat = dict(candidate.get("anti_cheat") or {})
    raw_body_detected = contains_forbidden_raw_key(candidate)
    anti_cheat.setdefault("target_coded_id", False)
    anti_cheat.setdefault("split_overlap", False)
    anti_cheat.setdefault("hidden_reference", False)
    anti_cheat.setdefault("shortcut_label_visible", False)
    anti_cheat["raw_body_visible"] = bool(anti_cheat.get("raw_body_visible")) or raw_body_detected
    return {
        "record_id": candidate.get("record_id"),
        "schema_version": "verified_transition_record_v1",
        "split": candidate.get("split", "schema_only"),
        "task_family": candidate.get("task_family"),
        "language_family": candidate.get("language_family", "unknown"),
        "state_before": {"ref": candidate.get("state_before_ref"), "materialized_body_included": False},
        "retrieval_context": {"refs": list(candidate.get("retrieval_refs") or []), "hidden_material_included": False},
        "observation": {"ref": candidate.get("observation_ref"), "normalized": candidate.get("observation_normalized", {})},
        "action": {"label": candidate.get("action_label"), "arguments": candidate.get("action_arguments", {})},
        "tool_result": {"ref": candidate.get("tool_result_ref"), "runtime_executed": False},
        "verifier_result": {"status": candidate.get("verifier_status", "NOT_RUN"), "refs": list(candidate.get("verifier_refs") or []), "runtime_executed": False},
        "state_after": {"ref": candidate.get("state_after_ref"), "materialized_patch_included": False},
        "reward_signal": {"label": candidate.get("reward_label", "unlabeled_schema_only"), "value": candidate.get("reward_value")},
        "loss_mask": dict(DEFAULT_LOSS_MASK),
        "authority": dict(AUTHORITY_CLOSED),
        "provenance": {"refs": list(candidate.get("provenance_refs") or []), "compiler": NAME, "route": candidate.get("route", "schema_only")},
        "anti_cheat_contract": anti_cheat,
        "telemetry_contract": {"required_artifacts": TELEMETRY_REQUIRED, "fail_if_missing_or_empty": True},
    }


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        failures.append("missing_required_fields")
    if record.get("schema_version") != "verified_transition_record_v1":
        failures.append("schema_version_mismatch")
    if record.get("split") not in ALLOWED_SPLITS:
        failures.append("split_not_allowed")
    if record.get("task_family") not in ALLOWED_TASK_FAMILIES:
        failures.append("task_family_not_allowed")
    if record.get("authority") != AUTHORITY_CLOSED:
        failures.append("authority_not_closed")
    if any(record.get("loss_mask", {}).values()):
        failures.append("loss_mask_open")
    if contains_forbidden_raw_key(record):
        failures.append("forbidden_raw_key_present")
    anti = record.get("anti_cheat_contract") or {}
    if any(bool(value) for value in anti.values()):
        failures.append("anti_cheat_flag_open")
    if (record.get("tool_result") or {}).get("runtime_executed"):
        failures.append("runtime_executed")
    if (record.get("verifier_result") or {}).get("runtime_executed"):
        failures.append("verifier_runtime_executed")
    telemetry = ((record.get("telemetry_contract") or {}).get("required_artifacts") or [])
    if set(TELEMETRY_REQUIRED) - set(telemetry):
        failures.append("telemetry_artifacts_missing")
    return {"passed": not failures, "failures": failures, "missing_required_fields": missing}


def build_contract() -> dict[str, Any]:
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "adapter_mode": "no_mining_schema_only",
        "input": "candidate transition object with refs only; no dataset walk and no raw source/body fields",
        "output_schema": "verified_transition_record_v1",
        "required_input_refs": ["state_before_ref", "retrieval_refs", "observation_ref", "tool_result_ref", "state_after_ref", "provenance_refs"],
        "forbidden_raw_keys": sorted(FORBIDDEN_RAW_KEYS),
        "authority_default": AUTHORITY_CLOSED,
        "loss_mask_default": DEFAULT_LOSS_MASK,
        "allowed_task_families": sorted(ALLOWED_TASK_FAMILIES),
        "allowed_splits": sorted(ALLOWED_SPLITS),
        "telemetry_required": TELEMETRY_REQUIRED,
        "hard_runtime_assertions": [
            "input_contains_no_forbidden_raw_keys",
            "compiled_record_has_all_required_fields",
            "authority_closed",
            "loss_mask_closed",
            "runtime_not_executed",
            "telemetry_contract_present",
            "refs_only_no_materialized_hidden_body",
        ],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    contract = build_contract()
    candidate = example_candidate()
    record = compile_candidate(candidate)
    audit = validate_record(record)
    failures = list(audit["failures"])
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = (registry.get("metrics") or {}).get("latest_stage")
    if latest not in {8900, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    ADAPTER_CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    EXAMPLE_OUTPUT.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            "example_record_validation_passed": audit["passed"],
            "required_fields": len(REQUIRED_FIELDS),
            "forbidden_raw_keys": len(FORBIDDEN_RAW_KEYS),
            "allowed_task_families": len(ALLOWED_TASK_FAMILIES),
            "loss_mask_open_fields": sum(1 for value in record["loss_mask"].values() if value),
            "manifest_row_count": 0,
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_walk_authorized": False,
            "data_mining_authorized": False,
        },
        "artifacts": {
            "adapter_contract": str(ADAPTER_CONTRACT.relative_to(ROOT)),
            "example_compiled_record": str(EXAMPLE_OUTPUT.relative_to(ROOT)),
        },
        "decision": "No-mining compiler adapter contract passed and compiled a closed example verified transition record." if not failures else "No-mining compiler adapter contract failed.",
        "next_best_step": "Build a no-mining adapter audit over existing synthetic/schema-only candidates, then only later consider source-backed rows after inventory and authority gates pass.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8901 Verified Transition Record No-Mining Compiler Adapter",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage defines the no-mining compiler adapter from candidate transition objects into `verified_transition_record_v1`.",
        "",
        "The adapter accepts refs-only candidate objects, rejects raw source/patch/decoder/runtime/Gemma bodies, emits closed authority, and keeps all loss masks false by default.",
        "",
        "This is still schema-only. It emits one example compiled record for validation, not a training manifest and not mined data.",
        "",
        "This opens no model execution, training, decoder CE, denoise CE, runtime, `/arxiv` walk, data mining, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, or promotion.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8901 Verified Transition Record No-Mining Compiler Adapter"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8901 defines the no-mining adapter that turns refs-only candidate transition objects into `verified_transition_record_v1`. It rejects raw source/patch/decoder/runtime/Gemma bodies, keeps authority closed, and keeps all losses disabled by default.",
            "",
            "This is the first compiler bridge after the schema contract, but it does not mine data or create trainable rows.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
