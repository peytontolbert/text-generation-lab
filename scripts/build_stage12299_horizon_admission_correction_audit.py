#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12299_horizon_admission_correction_audit"
S12297 = ROOT / "runs/summaries/stage12297_horizon_source_root_repair_and_projection_admission.json"
S12298 = ROOT / "runs/summaries/stage12298_transition_training_package_candidate.json"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def read_json(path: Path) -> dict:
    if not path.exists():
        return {"missing": True, "path": str(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    s12297 = read_json(S12297)
    s12298 = read_json(S12298)

    summary = {
        "stage": STAGE,
        "decision": "block_stage12297_and_stage12298_training_admission",
        "training_allowed": False,
        "admitted_rows": 0,
        "training_rows_emitted": 0,
        "corrected_interpretation": (
            "Stage12297 repaired source-root lineage, but lineage repair alone is not sufficient "
            "to admit horizon rows for training. Stage12271 horizon labels remain candidate/weak "
            "projection labels. They require projection QC and semantic/causal review before any "
            "training package can use them."
        ),
        "blocked_prior_outputs": {
            "stage12297_previous_admitted_train_support_rows": s12297.get("admitted_train_support_rows"),
            "stage12298_previous_package_rows": s12298.get("package_rows"),
        },
        "why_blocked": [
            "root hints prove repo-family lineage, not semantic verifier/action correctness",
            "Stage12271 stop/state labels are weak or placeholder labels",
            "next_action/rank rows still need projection QC to avoid observed-action imitation shortcuts",
            "self-research dominates the raw horizon pool and must not leak into claims",
            "patch/verifier temporal rows still lack exact causal proof",
        ],
        "replacement_contract": {
            "next_stage": "stage12300_root_repaired_horizon_projection_candidates",
            "emit_all_root_repaired_projection_candidates": True,
            "training_rows_emitted": 0,
            "admitted_rows": 0,
            "block_reason": "requires_projection_qc_and_semantic_causal_review",
            "preserve_original_ids": [
                "horizon_slice_id",
                "lineage.transition_id",
                "source_refs.task_window_id",
            ],
            "add_repaired_fields": [
                "source_root_label_present",
                "root_recovery",
                "repaired_split_group_id",
                "repaired_root_lineage_key",
            ],
        },
        "proof_counts": {
            "strict_eval_eligible": 0,
            "source_heldout_admissible": 0,
            "external_comparable_patch_trace_countable": 0,
            "external_fail_to_pass_countable": 0,
        },
        "raw_output_emitted": False,
    }
    (OUT / "horizon_admission_correction_audit.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUT / "HORIZON_ADMISSION_CORRECTION_AUDIT_STAGE12299.md").write_text(
        "# Stage12299 Horizon Admission Correction Audit\n\n"
        + "Stage12297/12298 are blocked for training. Root repair is necessary but not sufficient for admission.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
