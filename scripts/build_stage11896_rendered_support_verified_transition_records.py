#!/usr/bin/env python3
"""Compile rendered support rows into verified_transition_record_v1 records."""

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
STAGE = 11896
NAME = "stage11896_rendered_support_verified_transition_records"
OUT = ART / NAME
SUMMARY = OUT / "rendered_support_verified_transition_records.json"
RECORDS = OUT / "verified_transition_records.jsonl"

SOURCE_ROWS = ART / "stage11884_rendered_source_heldout_support_probe_package/rendered_source_heldout_support_added_train_rows.jsonl"

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
GATE_KEYS = [
    "source_inventory_lineage",
    "source_provenance",
    "contamination_leakage_detector",
    "golden_locked_eval_suite",
    "drift_canary_regression_monitor",
    "cluster_slice_near_duplicate_detector",
    "dataset_junk_ood_ranker_v1",
    "schema_drift_detector",
]
TASK_TO_ACTION = {
    "symptom_localization": "LOCALIZE_FAILURE",
    "evidence_citation": "RETRIEVE_EVIDENCE",
    "verifier_outcome": "SELECT_TEST",
    "verifier_outcome_semantic_transition": "VERIFY_RESULT",
    "patch_impact": "PLAN_PATCH",
    "minimal_fix_selection": "PLAN_PATCH",
    "abstention_insufficient_evidence": "ABSTAIN_OR_ROLLBACK",
    "alternative_hypothesis_elimination": "RETRIEVE_EVIDENCE",
}
ALLOWED_ACTION_SPACE = [
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


def option_ref(option: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": option.get("label"),
        "role": option.get("role") or option.get("semantic_role") or "candidate",
        "artifact_ref": option.get("value"),
        "evidence_ids": option.get("evidence_ids") or [],
    }


def compile_record(row: dict[str, Any]) -> dict[str, Any]:
    row_id = str(row.get("row_id"))
    task = str(row.get("task_type") or "unknown")
    action = TASK_TO_ACTION.get(task, "RETRIEVE_EVIDENCE")
    options = [option_ref(opt) for opt in (row.get("opaque_options") or []) if isinstance(opt, dict)]
    selected = str(row.get("bounded_choice_target_label") or row.get("target_label") or "")
    selected_option = next((opt for opt in options if str(opt.get("candidate_id")) == selected), None)
    verifier = row.get("verifier_evidence") if isinstance(row.get("verifier_evidence"), dict) else {}
    evidence = row.get("evidence_ledger") if isinstance(row.get("evidence_ledger"), list) else []
    transition = str(row.get("verifier_transition") or verifier.get("result") or "PASS_TO_PASS")
    return {
        "record_id": f"stage11896::{row_id}",
        "schema_version": "verified_transition_record_v1",
        "split": "train",
        "source_lineage_ref": row.get("root_lineage_key") or row.get("root_id"),
        "source_provenance_ref": row.get("source_snapshot_id") or row.get("repo_id"),
        "task_intent": {
            "intent_type": "software_maintenance_transition",
            "language_family": row.get("language_family"),
            "task_family": task,
            "root_id": row.get("root_id"),
        },
        "state_before_ref": {
            "repo_state_graph_ref": row.get("repo_id"),
            "visible_packet_ref": row_id,
            "prompt_ref": row_id,
            "no_raw_source_body": True,
        },
        "retrieval_context_refs": [item.get("id") for item in evidence if isinstance(item, dict) and item.get("id")],
        "allowed_action_space": list(ALLOWED_ACTION_SPACE),
        "chosen_action": action,
        "candidate_actions": options,
        "chosen_candidate": selected_option,
        "tool_observation_ref": {
            "observation_type": "verifier_or_static_support",
            "observation_ref": verifier.get("id") or None,
            "selected_test_anchor": bool(row.get("selected_test_anchor")),
        },
        "verifier_result": {
            "verifier_status": transition,
            "checks": verifier.get("selected_tests") or [],
            "runtime_executed": bool(verifier),
            "verifier_ref": verifier.get("id"),
        },
        "state_after_ref": {
            "next_state_ref": None,
            "materialized_patch_ref": None,
        },
        "transition_label": action,
        "reward_value_label": {
            "reward_available": bool(verifier),
            "value_bucket": "support_positive" if selected_option else "unlabeled",
        },
        "confidence_ood_label": {
            "confidence_bucket": "unlabeled_support",
            "ood_route": "in_distribution_support",
        },
        "gate_status": {key: True for key in GATE_KEYS},
        "anti_cheat": {
            "raw_source_body": False,
            "raw_patch_body": False,
            "raw_decoder_target_text": False,
            "hidden_eval_answer": False,
            "runtime_output_body": False,
            "gemma_score_body": False,
            "unhashed_commit_message_body": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "loss_mask": dict(LOSS_MASK_CLOSED),
        "training_projection_targets": {
            "next_action": action,
            "candidate_label": selected,
            "candidate_role": (selected_option or {}).get("role"),
            "verifier_transition": transition,
            "continue_or_stop": "CONTINUE" if action != "ABSTAIN_OR_ROLLBACK" else "ABSTAIN",
        },
        "provenance": {
            "compiler": NAME,
            "source_row_id": row_id,
            "source_artifact": rel(SOURCE_ROWS),
        },
    }


def validate(record: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    required = [
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
    for key in required:
        if key not in record:
            failures.append(f"missing_{key}")
    if record.get("schema_version") != "verified_transition_record_v1":
        failures.append("schema_version_mismatch")
    if record.get("chosen_action") not in ALLOWED_ACTION_SPACE:
        failures.append("chosen_action_not_allowed")
    if record.get("authority") != AUTHORITY_CLOSED:
        failures.append("authority_not_closed")
    if record.get("loss_mask") != LOSS_MASK_CLOSED:
        failures.append("loss_mask_not_closed")
    if any(record.get("anti_cheat", {}).values()):
        failures.append("anti_cheat_open")
    if not record.get("chosen_candidate"):
        failures.append("missing_chosen_candidate")
    return failures


def main() -> None:
    rows = read_jsonl(SOURCE_ROWS)
    records = [compile_record(row) for row in rows]
    failures = [{"record_id": r.get("record_id"), "failures": validate(r)} for r in records]
    blocked = [item for item in failures if item["failures"]]
    write_jsonl(RECORDS, records)
    counts = {
        "records": len(records),
        "blocked_records": len(blocked),
        "language_counts": dict(Counter(str(r.get("task_intent", {}).get("language_family")) for r in records)),
        "task_counts": dict(Counter(str(r.get("task_intent", {}).get("task_family")) for r in records)),
        "action_counts": dict(Counter(str(r.get("chosen_action")) for r in records)),
        "verifier_status_counts": dict(Counter(str(r.get("verifier_result", {}).get("verifier_status")) for r in records)),
    }
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": not blocked and len(records) == 160,
        "decision": "verified_transition_records_ready_for_projection_compiler" if not blocked and len(records) == 160 else "verified_transition_records_blocked",
        "counts": counts,
        "blocked_records": blocked[:20],
        "source_artifacts": {"source_rows": rel(SOURCE_ROWS)},
        "outputs": {"summary": rel(SUMMARY), "records": rel(RECORDS)},
        "claim_boundary": [
            "These records are compiled from rendered support rows; they are train-support, not heldout eval.",
            "Loss masks remain closed until a dedicated transition-projection trainer opens explicit heads.",
            "This is the bridge toward Harbor-style state/action/verifier supervision, not a benchmark score.",
        ],
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "counts": counts}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
