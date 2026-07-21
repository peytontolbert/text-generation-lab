#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12296_horizon_enriched_transition_projection_qc"
HORIZON = ROOT / "runs/local/artifacts/stage12271_horizon_slice_miner_pilot/horizon_slice_candidates.jsonl"
LEDGER_SUMMARY = ROOT / "runs/summaries/stage12295_transition_function_ledger.json"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def projection_rows():
    for row in iter_jsonl(HORIZON) or []:
        allowed = row.get("allowed_projection_families", [])
        source_root_label = row.get("source_refs", {}).get("source_root_label")
        root_repaired = bool(source_root_label)
        blocked_reasons = []
        if not root_repaired:
            blocked_reasons.append("missing_source_root_label")
        if not row.get("candidate_action_set", {}).get("future_actions_masked"):
            blocked_reasons.append("future_actions_not_masked")
        if row.get("guardrails", {}).get("raw_tool_output_emitted"):
            blocked_reasons.append("raw_tool_output_emitted")
        if row.get("guardrails", {}).get("raw_tool_arguments_emitted"):
            blocked_reasons.append("raw_tool_arguments_emitted")
        if row.get("guardrails", {}).get("raw_patch_body_emitted"):
            blocked_reasons.append("raw_patch_body_emitted")

        for family in allowed:
            task_family = {
                "next_action": "transition_next_action",
                "candidate_action_rank": "transition_candidate_action_rank",
                "state_update": "transition_state_update",
                "verifier_interpretation": "transition_verifier_transition",
                "continue_or_stop": "transition_continue_or_stop",
                "evidence_role": "transition_evidence_role",
                "patch_selection": "transition_patch_selection",
                "verifier_transition": "transition_verifier_transition",
                "repair_vs_continue": "transition_continue_or_stop",
            }.get(family, f"transition_{family}")
            yield {
                "schema_version": "horizon_enriched_transition_projection_candidate_v1",
                "stage": STAGE,
                "row_id": f"{row['horizon_slice_id']}::{task_family}",
                "source_horizon_slice_id": row["horizon_slice_id"],
                "source_transition_id": row.get("lineage", {}).get("transition_id"),
                "task_family": task_family,
                "horizon_label": row.get("horizon_label"),
                "validation_level": row.get("admission", {}).get("validation_level"),
                "root_lineage_key": row.get("lineage", {}).get("root_lineage_key"),
                "split_group_id": row.get("lineage", {}).get("split_group_id"),
                "source_refs": {
                    "chat_id": row.get("source_refs", {}).get("chat_id"),
                    "task_window_id": row.get("source_refs", {}).get("task_window_id"),
                    "snapshot_id": row.get("source_refs", {}).get("snapshot_id"),
                    "source_file_hash_compat": row.get("source_refs", {}).get("source_file_hash_compat"),
                    "source_root_label_present": root_repaired,
                },
                "pre_action_fields": {
                    "state_before": row.get("state_before"),
                    "candidate_action_set": row.get("candidate_action_set"),
                },
                "target_only_fields": {
                    "chosen_action": row.get("chosen_action"),
                    "observation": row.get("observation"),
                    "state_update": row.get("state_update"),
                    "stop_continue": row.get("stop_continue"),
                    "verifier_linkage": row.get("verifier_linkage"),
                },
                "admission": {
                    "train_support_allowed": False,
                    "strict_eval_eligible": False,
                    "source_heldout_admissible": False,
                    "external_comparable_patch_trace_countable": False,
                    "external_fail_to_pass_countable": False,
                    "blocked_reasons": blocked_reasons or ["requires_projection_qc_and_root_split_assignment"],
                },
                "visibility_masks": row.get("visibility_masks"),
                "guardrails": row.get("guardrails"),
            }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = list(projection_rows())
    with (OUT / "horizon_enriched_projection_candidates.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    ledger_summary = read_json(LEDGER_SUMMARY)
    blocked_counts: Counter[str] = Counter()
    for row in rows:
        blocked_counts.update(row["admission"]["blocked_reasons"])

    summary = {
        "stage": STAGE,
        "decision": "horizon_enriched_projection_candidates_ready_training_blocked",
        "claim_boundary": "Richer horizon transition projection candidates only. Not admitted train rows until source-root repair and projection QC pass.",
        "projection_candidates": len(rows),
        "task_family_counts": dict(Counter(row["task_family"] for row in rows)),
        "horizon_counts": dict(Counter(row["horizon_label"] for row in rows)),
        "validation_level_counts": dict(Counter(row["validation_level"] for row in rows)),
        "blocked_reason_counts": dict(blocked_counts),
        "stage12295_context": {
            "ledger_records": ledger_summary.get("ledger_records"),
            "train_support_rows": ledger_summary.get("train_support_rows"),
            "train_validation_level_counts": ledger_summary.get("train_validation_level_counts"),
            "qc_note": "Stage12295 V1 rows provide scale; Stage12296 horizon rows provide richer transition structure but need source-root repair.",
        },
        "admitted_rows": 0,
        "training_rows_emitted": 0,
        "external_comparable_patch_trace_rows": 0,
        "external_fail_to_pass_rows": 0,
        "guardrails": {
            "raw_message_text_emitted": False,
            "raw_tool_arguments_emitted": False,
            "raw_tool_output_emitted": False,
            "raw_patch_body_emitted": False,
            "raw_source_path_emitted": False,
        },
        "next_stage": "stage12297_horizon_source_root_repair_and_projection_admission",
        "training_allowed": False,
    }
    (OUT / "horizon_enriched_transition_projection_qc_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUT / "HORIZON_ENRICHED_TRANSITION_PROJECTION_QC_STAGE12296.md").write_text(
        "# Stage12296 Horizon-Enriched Transition Projection QC\n\n"
        + "This stage converts Stage12271 horizon slices into projection candidates. It emits no training rows.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
