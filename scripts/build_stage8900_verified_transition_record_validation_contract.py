#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8900
NAME = "stage8900_verified_transition_record_validation_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "VERIFIED_TRANSITION_RECORD_VALIDATION_CONTRACT_STAGE8900.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCE_SUMMARIES = [
    ROOT / "runs/summaries/stage8897_transition_compression_thesis_graph_attachment.json",
    ROOT / "runs/summaries/stage8898_policy_evolution_knowledge_transfer_graph_attachment.json",
]

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

LOSS_MASK_CLOSED = {
    "structured_aux": False,
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
    "preference": False,
}

REQUIRED_FIELDS = [
    "record_id",
    "schema_version",
    "split",
    "source_lineage_ref",
    "source_provenance_ref",
    "task_intent",
    "state_before_ref",
    "retrieval_context_refs",
    "allowed_action_space",
    "chosen_action",
    "tool_observation_ref",
    "verifier_result",
    "state_after_ref",
    "transition_label",
    "reward_value_label",
    "confidence_ood_label",
    "gate_status",
    "anti_cheat",
    "authority",
    "loss_mask",
]

FORBIDDEN_VISIBLE_FIELDS = [
    "raw_source_body",
    "raw_patch_body",
    "raw_decoder_target_text",
    "hidden_eval_answer",
    "runtime_output_body",
    "gemma_score_body",
    "unhashed_commit_message_body",
]

REQUIRED_GATE_KEYS = [
    "source_inventory_lineage",
    "source_provenance",
    "contamination_leakage_detector",
    "golden_locked_eval_suite",
    "drift_canary_regression_monitor",
    "cluster_slice_near_duplicate_detector",
    "dataset_junk_ood_ranker_v1",
    "schema_drift_detector",
]

TRANSITION_LABELS = [
    "LOCALIZE_FAILURE",
    "RETRIEVE_EVIDENCE",
    "BIND_SYMBOL",
    "SELECT_TEST",
    "PLAN_PATCH",
    "APPLY_PATCH_ABSTRACT",
    "VERIFY_RESULT",
    "REPAIR_AFTER_FAILURE",
    "ABSTAIN_OR_ROLLBACK",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def example_record() -> dict[str, Any]:
    return {
        "record_id": "vtr_example_closed_schema_only",
        "schema_version": "verified_transition_record_v1",
        "split": "schema_only",
        "source_lineage_ref": "source_inventory_lineage:required_ref_only",
        "source_provenance_ref": "source_provenance:required_ref_only",
        "task_intent": {
            "intent_type": "software_maintenance_transition",
            "intent_ref": "opaque_intent_ref_only",
        },
        "state_before_ref": {
            "repo_state_graph_ref": "artifact_ref_only",
            "visible_packet_ref": "artifact_ref_only",
            "no_raw_source_body": True,
        },
        "retrieval_context_refs": [],
        "allowed_action_space": list(TRANSITION_LABELS),
        "chosen_action": "RETRIEVE_EVIDENCE",
        "tool_observation_ref": {
            "observation_type": "not_run_schema_only",
            "observation_ref": None,
        },
        "verifier_result": {
            "verifier_status": "not_run_schema_only",
            "checks": [],
            "runtime_executed": False,
        },
        "state_after_ref": {
            "next_state_ref": None,
            "materialized_patch_ref": None,
        },
        "transition_label": "RETRIEVE_EVIDENCE",
        "reward_value_label": {
            "reward_available": False,
            "value_bucket": "unlabeled_schema_only",
        },
        "confidence_ood_label": {
            "confidence_bucket": "unlabeled_schema_only",
            "ood_route": "unknown_schema_only",
        },
        "gate_status": {key: False for key in REQUIRED_GATE_KEYS},
        "anti_cheat": {field: False for field in FORBIDDEN_VISIBLE_FIELDS},
        "authority": dict(AUTHORITY_CLOSED),
        "loss_mask": dict(LOSS_MASK_CLOSED),
    }


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    missing_fields = [field for field in REQUIRED_FIELDS if field not in record]
    visible_forbidden = [field for field in FORBIDDEN_VISIBLE_FIELDS if bool((record.get("anti_cheat") or {}).get(field))]
    missing_gate_keys = [key for key in REQUIRED_GATE_KEYS if key not in (record.get("gate_status") or {})]
    authority_open = any((record.get("authority") or {}).values())
    loss_open = any((record.get("loss_mask") or {}).values())
    runtime_open = bool(((record.get("verifier_result") or {}).get("runtime_executed")))
    failures = []
    if missing_fields:
        failures.append("missing_required_fields")
    if visible_forbidden:
        failures.append("forbidden_visible_fields")
    if missing_gate_keys:
        failures.append("missing_gate_keys")
    if authority_open:
        failures.append("authority_open")
    if loss_open:
        failures.append("loss_open")
    if runtime_open:
        failures.append("runtime_open")
    return {
        "passed": not failures,
        "failures": failures,
        "missing_fields": missing_fields,
        "visible_forbidden": visible_forbidden,
        "missing_gate_keys": missing_gate_keys,
        "authority_open": authority_open,
        "loss_open": loss_open,
        "runtime_open": runtime_open,
    }


def build_contract_card(registry: dict[str, Any], source_cards: list[dict[str, Any]]) -> dict[str, Any]:
    record = example_record()
    validation = validate_record(record)
    failures = list(validation["failures"])
    for source in source_cards:
        if source.get("passed") is not True:
            failures.append(f"source_failed:{source.get('stage_name')}")
        if any((source.get("authority") or {}).values()):
            failures.append(f"source_authority_open:{source.get('stage_name')}")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if latest not in {8899, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            "required_fields": len(REQUIRED_FIELDS),
            "forbidden_visible_fields": len(FORBIDDEN_VISIBLE_FIELDS),
            "required_gate_keys": len(REQUIRED_GATE_KEYS),
            "transition_labels": len(TRANSITION_LABELS),
            "example_record_validation_passed": validation["passed"],
            "loss_rows": 0,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
            "data_mining_authorized": False,
            "arxiv_walk_authorized": False,
        },
        "required_fields": REQUIRED_FIELDS,
        "required_gate_keys": REQUIRED_GATE_KEYS,
        "transition_labels": TRANSITION_LABELS,
        "forbidden_visible_fields": FORBIDDEN_VISIBLE_FIELDS,
        "example_record": record,
        "decision": "Verified transition record contract passed as schema-only/no-execution. It gives the curriculum compiler a canonical target object before mining or training." if not failures else "Verified transition record contract failed.",
        "next_best_step": "Use this contract to build a no-mining compiler adapter next; do not emit training rows or open losses until rows pass gates and explicit authorization exists.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main() -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    source_cards = [load_json(path) for path in SOURCE_SUMMARIES]
    card = build_contract_card(registry, source_cards)
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8900 Verified Transition Record Validation Contract",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage defines the canonical schema-only object that future curriculum compiler work should emit before any dataset rebuilding or training.",
        "",
        "A verified transition record contains state-before refs, retrieval refs, action space, chosen action, tool observation ref, verifier result, state-after ref, transition label, reward/value label, confidence/OOD label, gate status, anti-cheat flags, authority, and loss masks.",
        "",
        "It is schema-only and opens no model execution, training, decoder CE, denoise CE, runtime, mining, `/arxiv` walk, source/body emission, Gemma, harness, scoring, controller merge, checkpoint export, or promotion.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8900 Verified Transition Record Validation Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8900 validates the verified transition record as the canonical schema-only target for future curriculum compiler work: state-before refs, retrieval refs, action, tool observation, verifier result, state-after ref, transition label, reward/value, confidence/OOD, gate status, anti-cheat, authority, and loss masks.",
            "",
            "This does not emit training rows or open execution/losses. It gives future no-mining compiler adapters a concrete object to target before any scale-up.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
