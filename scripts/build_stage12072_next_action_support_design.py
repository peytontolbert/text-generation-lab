#!/usr/bin/env python3
"""Emit the next-action support design request.

Stage12071 found that the v35 transition support package had zero
transition_next_action rows and that the selected transition scorer collapses
next-action misses to PLAN_PATCH/RETRIEVE_EVIDENCE.  This stage records the
data construction contract required before another transition training probe.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 12072
STAGE_NAME = "stage12072_next_action_support_design"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / STAGE_NAME
SUMMARY_PATH = ROOT / "runs" / "summaries" / f"{STAGE_NAME}.json"

ATLAS = ROOT / "runs/summaries/stage12071_next_action_gap_atlas.json"
MISS_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12071_next_action_gap_atlas"
    / "transition_next_action_miss_rows.jsonl"
)
V35 = (
    ROOT
    / "runs/local/artifacts/stage12056_transition_support_rollup_v35"
    / "transition_support_rows_v35.jsonl"
)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def count_existing_next_action_support() -> dict[str, Any]:
    rows = list(iter_jsonl(V35))
    next_action = [r for r in rows if r.get("task_type") == "transition_next_action"]
    target_counts = Counter(
        (r.get("target") or {}).get("semantic_value")
        or r.get("standalone_projection_source", {}).get("gold_value")
        for r in next_action
    )
    language_counts = Counter(r.get("language_family") for r in next_action)
    return {
        "source": str(V35.relative_to(ROOT)),
        "all_rows": len(rows),
        "transition_next_action_rows": len(next_action),
        "transition_next_action_unique_roots": len({r.get("root_id") for r in next_action}),
        "target_counts": dict(target_counts),
        "language_counts": dict(language_counts),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    atlas = read_json(ATLAS)
    misses = list(iter_jsonl(MISS_ROWS))
    existing = count_existing_next_action_support()

    confusion_counts = Counter((m["target_value"], m["baseline_pred_value"]) for m in misses)
    target_counts = Counter(m["target_value"] for m in misses)
    language_counts = Counter(m["language_family"] for m in misses)
    status_counts = Counter(m["observed_status"] for m in misses)

    # Quotas intentionally include actions that were not dominant targets in the
    # frozen miss set. Those are needed as counterexamples so PLAN_PATCH and
    # VERIFY_RESULT are learned as state-conditioned actions, not priors.
    target_row_quotas = {
        "ABSTAIN_OR_ROLLBACK": 35,
        "SELECT_TEST": 35,
        "LOCALIZE_FAILURE": 30,
        "RETRIEVE_EVIDENCE": 30,
        "PLAN_PATCH": 25,
        "VERIFY_RESULT": 25,
        "REPAIR_AFTER_FAILURE": 20,
    }
    language_root_quotas = {
        "python": 20,
        "c_cpp": 20,
        "rust": 20,
        "web_js_ts_html": 20,
    }
    verifier_state_quotas = {
        "pre_verifier_no_selected_test": 30,
        "selected_test_known_not_run": 30,
        "verifier_pass_current_state": 30,
        "verifier_removed_or_insufficient": 30,
        "verifier_failed_requires_repair": 30,
        "post_patch_verify_needed": 25,
        "completion_gate_abstain_or_rollback": 25,
    }

    row_contract = {
        "required_fields": [
            "root_id",
            "root_lineage_key",
            "repo_id",
            "language_family",
            "task_type=transition_next_action",
            "milestone_state",
            "observed_status",
            "selected_test_anchor",
            "visible_source_evidence",
            "visible_verifier_evidence",
            "opaque_options",
            "standalone_projection_source.opaque_options",
            "target.semantic_value",
            "anti_cheat",
            "loss_mask",
        ],
        "candidate_values": [
            "LOCALIZE_FAILURE",
            "RETRIEVE_EVIDENCE",
            "BIND_SYMBOL",
            "SELECT_TEST",
            "PLAN_PATCH",
            "APPLY_PATCH_ABSTRACT",
            "VERIFY_RESULT",
            "REPAIR_AFTER_FAILURE",
            "ABSTAIN_OR_ROLLBACK",
        ],
        "anti_cheat_required": {
            "deterministic_option_shuffle": True,
            "target_label_not_visible_before_options": True,
            "no_postfix_source_in_preaction_state": True,
            "root_split_isolated": True,
            "candidate_values_not_order_shortcut": True,
        },
        "loss_mask": {
            "bounded_choice_aux": True,
            "decoder_ce": True,
            "structured_aux": True,
            "transition_projection": True,
        },
    }

    generator_specs = [
        {
            "name": "premature_patch_negative",
            "fixes_confusions": [
                "ABSTAIN_OR_ROLLBACK<-PLAN_PATCH",
                "RETRIEVE_EVIDENCE<-PLAN_PATCH",
                "SELECT_TEST<-PLAN_PATCH",
                "LOCALIZE_FAILURE<-PLAN_PATCH",
            ],
            "row_shape": "State lacks sufficient verifier/test evidence; PLAN_PATCH is a hard negative and the gold is retrieve/select/localize/abstain.",
            "minimum_rows": 80,
        },
        {
            "name": "premature_retrieve_negative",
            "fixes_confusions": [
                "LOCALIZE_FAILURE<-RETRIEVE_EVIDENCE",
                "SELECT_TEST<-RETRIEVE_EVIDENCE",
                "PLAN_PATCH<-RETRIEVE_EVIDENCE",
            ],
            "row_shape": "State already contains enough evidence for a concrete next action; RETRIEVE_EVIDENCE is a hard negative.",
            "minimum_rows": 45,
        },
        {
            "name": "post_failure_repair_boundary",
            "fixes_confusions": [
                "REPAIR_AFTER_FAILURE missing from current miss targets",
                "VERIFY_RESULT missing from current miss targets",
            ],
            "row_shape": "Verifier has failed or patch has been applied; gold alternates between REPAIR_AFTER_FAILURE and VERIFY_RESULT.",
            "minimum_rows": 45,
        },
        {
            "name": "completion_gate_abstain_boundary",
            "fixes_confusions": [
                "ABSTAIN_OR_ROLLBACK<-PLAN_PATCH",
                "ABSTAIN_OR_ROLLBACK<-RETRIEVE_EVIDENCE",
            ],
            "row_shape": "Evidence is insufficient, verifier was removed, or state is unsafe; gold is ABSTAIN_OR_ROLLBACK.",
            "minimum_rows": 30,
        },
    ]

    support_request = {
        "stage": STAGE,
        "stage_name": STAGE_NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "do_not_train_yet": True,
        "selected_transition_frontier": "stage11924_transition_listwise_head_only_probe",
        "current_transition_score": {
            "stage11924": "364/640",
            "gemma_same_manifest": "386/640",
            "stage12068_composite": "364/640 retention only",
        },
        "problem_statement": {
            "weakest_family": "transition_next_action",
            "current_accuracy": "51/160",
            "miss_count": 109,
            "observed_collapse": "All baseline next-action misses predict PLAN_PATCH or RETRIEVE_EVIDENCE.",
            "existing_v35_next_action_support": existing,
        },
        "miss_analysis": {
            "by_target_value": dict(target_counts),
            "by_language": dict(language_counts),
            "by_observed_status": dict(status_counts),
            "by_confusion": [
                {"target_value": k[0], "pred_value": k[1], "count": v}
                for k, v in confusion_counts.most_common()
            ],
        },
        "support_construction_contract": {
            "minimum_rows": 200,
            "minimum_unique_roots": 80,
            "target_row_quotas": target_row_quotas,
            "language_root_quotas": language_root_quotas,
            "verifier_state_quotas": verifier_state_quotas,
            "repo_family_cap": "max(15 rows, 10% of next-action support rows) per repo family",
            "row_contract": row_contract,
            "generator_specs": generator_specs,
        },
        "admission_gates": [
            "zero train/eval/protected root overlap",
            "all rows have mirrored standalone_projection_source.opaque_options",
            "all rows have non-singleton opaque options",
            "selected_test_anchor present when target is SELECT_TEST or VERIFY_RESULT",
            "verifier evidence present when target depends on verifier state",
            "PLAN_PATCH positive rows require enough evidence to patch; PLAN_PATCH negative rows must explicitly show missing prerequisite",
            "ABSTAIN_OR_ROLLBACK positive rows require concrete insufficiency/safety condition",
        ],
        "next_stage": {
            "recommended": "stage12073_next_action_support_materializer",
            "purpose": "materialize rows from this contract; do not launch training until admission gates pass",
            "training_after_materialization_gate": {
                "transition_next_action_rows": ">=200",
                "unique_roots": ">=80",
                "language_roots_each": ">=15",
                "protected_replay_included": True,
                "expected_probe_goal": "old transition >364/640 while preserving compact gates; Gemma win still requires >386/640",
            },
        },
        "source_artifacts": {
            "atlas": str(ATLAS.relative_to(ROOT)),
            "miss_rows": str(MISS_ROWS.relative_to(ROOT)),
            "v35_support": str(V35.relative_to(ROOT)),
        },
    }

    out_path = OUT_DIR / "next_action_support_design.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(support_request, f, indent=2, sort_keys=True)
        f.write("\n")
    with SUMMARY_PATH.open("w", encoding="utf-8") as f:
        json.dump(support_request, f, indent=2, sort_keys=True)
        f.write("\n")

    print(json.dumps(support_request, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
