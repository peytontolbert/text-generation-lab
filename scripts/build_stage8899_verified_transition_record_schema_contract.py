#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8899
NAME = "stage8899_verified_transition_record_schema_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "VERIFIED_TRANSITION_RECORD_SCHEMA_STAGE8899.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SCHEMA_PATH = OUT_DIR / "verified_transition_record_v1_schema.json"
LOSS_CARD_PATH = OUT_DIR / "verified_transition_record_v1_loss_mask_contract.json"

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

REQUIRED_TOP_LEVEL_FIELDS = [
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

LOSS_MASK_FIELDS = [
    "train_action_policy",
    "train_retrieval_policy",
    "train_state_transition",
    "train_value_head",
    "train_structured_aux",
    "train_decoder_ce",
    "train_denoise_ce",
    "train_runtime_reward",
]

ACTION_SPACE = [
    "RETRIEVE_CONTEXT",
    "READ_FILE",
    "BIND_SYMBOL",
    "LOCALIZE_EDIT",
    "PREDICT_PATCH_OPERATOR",
    "GENERATE_BOUNDED_ARGUMENT",
    "APPLY_PATCH",
    "RUN_VERIFIER",
    "DIAGNOSE_FAILURE",
    "REPAIR_PATCH",
    "ABSTAIN_UNSAFE",
    "FINISH_VERIFIED",
]

VERIFIER_STATES = [
    "NOT_RUN",
    "PASS",
    "FAIL_SYNTAX",
    "FAIL_TEST",
    "FAIL_LINT",
    "FAIL_TYPECHECK",
    "FAIL_GROUNDING",
    "FAIL_DEPENDENCY",
    "FAIL_SECURITY",
    "INCONCLUSIVE",
]

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


def build_schema() -> dict[str, Any]:
    return {
        "schema_version": "verified_transition_record_v1",
        "description": "Canonical no-authority software-maintenance transition record: state + retrieved evidence + action + observation + verifier result + next state.",
        "required_top_level_fields": REQUIRED_TOP_LEVEL_FIELDS,
        "field_contract": {
            "record_id": "Opaque stable ID; must not encode target label, action, split, or verifier result.",
            "schema_version": "Must equal verified_transition_record_v1.",
            "split": "train|eval|strict_eval|holdout; split must be assigned before model input serialization.",
            "task_family": "Intent/build, repo graph, symbol binding, edit localization, patch operator, verifier repair, bounded argument, denoise repair, or research transfer.",
            "language_family": "python|rust|c_family|web_js_ts_html|mixed|unknown.",
            "state_before": "Structured state object. No raw source/body unless route explicitly permits and authority remains closed for this schema stage.",
            "retrieval_context": "References to retrieved evidence cards, source inventory IDs, API cards, paper operator cards, or repo graph nodes. Store refs, not hidden material.",
            "observation": "Tool/test/error/log/static-analysis observation normalized into typed fields.",
            "action": "Typed next operation with action_label and bounded arguments.",
            "tool_result": "Result from the action if available; use NOT_RUN for design/pre-execution rows.",
            "verifier_result": "Typed verifier state and evidence refs. Must not be inferred from target-coded fields.",
            "state_after": "Expected or observed next structured state. For supervised rows, must be verifier-backed or explicitly marked synthetic_teacher_pending_verification.",
            "reward_signal": "pass/fail/helpful/harmful/inconclusive plus value labels where available.",
            "loss_mask": "Declares which losses this row is authorized to train. Forbidden losses must be false by default.",
            "authority": "Per-row authority flags. Defaults closed. Cannot override registry authority.",
            "provenance": "Source lineage, license/security/risk refs, teacher/verifier refs, and generation method.",
            "anti_cheat_contract": "No target-coded IDs, no shortcut labels, no split overlap, no hidden refs, no raw leak in forbidden fields.",
            "telemetry_contract": "Required telemetry artifacts for any probe consuming this record.",
        },
        "action_space": ACTION_SPACE,
        "verifier_states": VERIFIER_STATES,
        "loss_mask_fields": LOSS_MASK_FIELDS,
        "authority_default": AUTHORITY_CLOSED,
        "telemetry_required": TELEMETRY_REQUIRED,
        "hard_gates": {
            "authority_rows": 0,
            "raw_source_rows_without_route": 0,
            "target_coded_id_rows": 0,
            "split_overlap_rows": 0,
            "loss_mask_missing_rows": 0,
            "forbidden_loss_enabled_rows": 0,
            "verifier_result_label_leak_rows": 0,
            "retrieval_context_hidden_material_rows": 0,
        },
    }


def build_loss_contract() -> dict[str, Any]:
    return {
        "schema_version": "verified_transition_record_v1_loss_mask_contract",
        "default_loss_mask": {field: False for field in LOSS_MASK_FIELDS},
        "route_allowed_losses": {
            "KEEP_STRUCTURED": ["train_action_policy", "train_retrieval_policy", "train_state_transition", "train_value_head", "train_structured_aux"],
            "KEEP_BOUNDED_DECODER": ["train_decoder_ce"],
            "USE_FOR_DENOISE_REPAIR": ["train_denoise_ce"],
            "USE_AS_NEGATIVE": ["train_action_policy", "train_value_head", "train_structured_aux"],
            "HOLD_LONG_OUTPUT": ["train_action_policy", "train_value_head"],
            "NEEDS_RETRIEVAL": ["train_retrieval_policy", "train_action_policy"],
            "QUARANTINE_LABEL_CONFLICT": [],
        },
        "forbidden_without_explicit_future_authority": [
            "train_decoder_ce",
            "train_denoise_ce",
            "train_runtime_reward",
        ],
        "runtime_assertions": [
            "row_ids_match_manifest",
            "loss_mask_present_for_every_row",
            "forbidden_losses_zero_unless_stage_authority_says_otherwise",
            "decoder_ce_only_on_budget_safe_rows",
            "denoise_ce_only_on_repair_rows",
            "runtime_reward_never_active_in_no_execution_probe",
        ],
    }


def validate_schema(schema: dict[str, Any], loss_contract: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if schema.get("required_top_level_fields") != REQUIRED_TOP_LEVEL_FIELDS:
        failures.append("required_top_level_fields_changed")
    if set(schema.get("authority_default", {})) != set(AUTHORITY_CLOSED):
        failures.append("authority_default_keys_mismatch")
    if any(schema["authority_default"].values()):
        failures.append("authority_default_not_closed")
    if set(loss_contract.get("default_loss_mask", {})) != set(LOSS_MASK_FIELDS):
        failures.append("loss_mask_keys_mismatch")
    if any(loss_contract["default_loss_mask"].values()):
        failures.append("default_loss_mask_not_closed")
    if "verified_transition_record_v1" != schema.get("schema_version"):
        failures.append("schema_version_mismatch")
    if "runtime_reward_never_active_in_no_execution_probe" not in loss_contract.get("runtime_assertions", []):
        failures.append("missing_runtime_reward_assertion")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = (registry.get("metrics") or {}).get("latest_stage")
    if latest not in {8898, STAGE, 8900}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    schema = build_schema()
    loss_contract = build_loss_contract()
    failures = validate_schema(schema, loss_contract, registry)
    SCHEMA_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LOSS_CARD_PATH.write_text(json.dumps(loss_contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            "required_top_level_field_count": len(REQUIRED_TOP_LEVEL_FIELDS),
            "loss_mask_field_count": len(LOSS_MASK_FIELDS),
            "action_space_count": len(ACTION_SPACE),
            "verifier_state_count": len(VERIFIER_STATES),
            "telemetry_required_count": len(TELEMETRY_REQUIRED),
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_walk_authorized": False,
            "data_mining_authorized": False,
            "manifest_row_count": 0,
        },
        "artifacts": {
            "schema": str(SCHEMA_PATH.relative_to(ROOT)),
            "loss_mask_contract": str(LOSS_CARD_PATH.relative_to(ROOT)),
        },
        "decision": "Materialized verified_transition_record_v1 schema contract with loss-mask defaults closed." if not failures else "Verified transition record schema contract failed validation.",
        "next_best_step": "Use this schema as the target for future compiler/data builders; do not mine or train until builders emit schema-valid records with closed authority and audited loss masks.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8899 Verified Transition Record Schema Contract",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage materializes `verified_transition_record_v1`, the canonical record shape for future software-maintenance training data.",
        "",
        "A record is not raw code or raw paper text. It is: state_before + retrieval refs + observation + typed action + tool result + verifier result + state_after + reward/value + loss mask + provenance + anti-cheat contract.",
        "",
        "Loss masks default closed. Decoder CE, denoise CE, and runtime reward remain forbidden unless a future explicit authority stage opens them for a specific route.",
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
    marker = "## Stage8899 Verified Transition Record Schema Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8899 materializes `verified_transition_record_v1` as the central object for future compiler output. It captures state, retrieval refs, observations, typed actions, verifier results, next state, reward/value signals, loss masks, provenance, anti-cheat constraints, and telemetry requirements.",
            "",
            "All loss masks default closed. Future data builders must prove schema validity and loss-mask authority before any row can create gradients.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
