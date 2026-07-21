#!/usr/bin/env python3
"""Decide Stage12059 guarded transition training result."""
from __future__ import annotations

import collections
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
NAME = "stage12061_guarded_transition_training_decision"
OUT = ART / NAME
SUMMARY = OUT / "guarded_transition_training_decision.json"
AUDIT = ART / "stage12060_guarded_transition_training_postrun_audit/guarded_transition_training_postrun_audit.json"
BASE_CARD = ART / "stage12060_guarded_transition_training_postrun_audit/stage11924_transition_listwise_head_only/bounded_choice_eval_audit_transition_projection__semantic_candidate_head.json"
POST_CARD = ART / "stage12060_guarded_transition_training_postrun_audit/stage12059_guarded_transition_training/bounded_choice_eval_audit_transition_projection__semantic_candidate_head.json"
REQUEST = ART / "stage12058_guarded_transition_training_request/guarded_transition_training_request.json"
TRAIN_RESULT = ART / "stage12059_guarded_transition_training_probe/bounded_decoder_probe/execution_result.json"


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def load(p: Path) -> Any:
    return json.loads(p.read_text())


def rows_by_id(card: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(r.get("row_id")): r for r in card.get("row_cards") or []}


def task_from_row_id(row_id: str) -> str:
    for task in ["next_action", "candidate_selection", "verifier_transition", "continue_or_stop"]:
        if row_id.endswith(f"::{task}") or f"::{task}::" in row_id:
            return f"transition_{task}"
    return "unknown"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SUM.mkdir(parents=True, exist_ok=True)
    audit = load(AUDIT)
    req = load(REQUEST)
    train = load(TRAIN_RESULT)
    base = rows_by_id(load(BASE_CARD))
    post = rows_by_id(load(POST_CARD))
    common = sorted(set(base) & set(post))
    gained = []
    lost = []
    unchanged_wrong = []
    unchanged_right = []
    for row_id in common:
        b = base[row_id].get("constrained_choice_match") is True
        p = post[row_id].get("constrained_choice_match") is True
        rec = {
            "row_id": row_id,
            "task_family": task_from_row_id(row_id),
            "target": post[row_id].get("bounded_choice_target_label"),
            "base_pred": base[row_id].get("constrained_choice_top1_label"),
            "post_pred": post[row_id].get("constrained_choice_top1_label"),
        }
        if not b and p:
            gained.append(rec)
        elif b and not p:
            lost.append(rec)
        elif b and p:
            unchanged_right.append(rec)
        else:
            unchanged_wrong.append(rec)

    by_task = {}
    for label, items in [("gained", gained), ("lost", lost), ("unchanged_wrong", unchanged_wrong), ("unchanged_right", unchanged_right)]:
        c = collections.Counter(i["task_family"] for i in items)
        for task, n in c.items():
            by_task.setdefault(task, {})[label] = n
    for task in by_task:
        for key in ["gained", "lost", "unchanged_wrong", "unchanged_right"]:
            by_task[task].setdefault(key, 0)

    stage11924 = audit["results"]["stage11924_transition_listwise_head_only"]["transition_projection_routed"]
    stage12059 = audit["results"]["stage12059_guarded_transition_training"]["transition_projection_routed"]
    protected_preserved = all(
        audit["gates"][k]
        for k in [
            "filtered_strict_preserved",
            "filtered_validation_preserved",
            "old_canary_strict_preserved",
            "old_canary_validation_preserved",
            "residual_preserved",
            "smoke_preserved",
        ]
    )
    retained = audit["gates"]["transition_projection_retains_stage11924_baseline"]
    beats_gemma = audit["gates"]["transition_projection_beats_gemma_386"]
    if protected_preserved and beats_gemma:
        decision = "promote_after_gemma_confirmation"
    elif protected_preserved and retained:
        decision = "retain_candidate_but_no_gemma_win"
    else:
        decision = "reject_stage12059_keep_stage11924_selected_transition_frontier"

    payload = {
        "stage": 12061,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "decision": decision,
        "selected_transition_frontier_after_decision": "stage11924_transition_listwise_head_only_probe",
        "rejected_runtime": "stage12059_guarded_transition_training_probe" if decision.startswith("reject") else None,
        "reason": [
            "Stage12059 preserved compact/protected gates but failed transition retention against Stage11924.",
            "Stage12059 scored 360/640 on old transition projection; Stage11924 remains 364/640 and Gemma remains 386/640.",
            "The v35 support supply is useful data construction, but this training recipe did not convert it into a transition-frontier improvement.",
        ],
        "scores": {
            "stage11924_transition": stage11924,
            "stage12059_transition": stage12059,
            "gemma_same_manifest_reference": {"correct": 386, "rows": 640},
            "protected_gates_preserved": protected_preserved,
        },
        "flip_analysis": {
            "common_rows": len(common),
            "gained_rows": len(gained),
            "lost_rows": len(lost),
            "unchanged_wrong_rows": len(unchanged_wrong),
            "unchanged_right_rows": len(unchanged_right),
            "net_correct_delta": len(gained) - len(lost),
            "by_task_family": dict(sorted(by_task.items())),
            "gained_examples": gained[:20],
            "lost_examples": lost[:20],
        },
        "training_facts": {
            "runtime_executed": train.get("runtime_executed"),
            "runtime_model_saved": train.get("runtime_model_saved"),
            "runtime_bundle": rel(ART / "stage12059_guarded_transition_training_probe/runtime_model/runtime_model_bundle.json"),
            "loss_rows": sum(1 for _ in open(ART / "stage12059_guarded_transition_training_probe/bounded_decoder_probe/loss_by_step.jsonl")),
            "train_rows": train.get("train_rows"),
            "request_train_rows": req.get("row_counts", {}).get("train_rows"),
        },
        "next_recommendation": {
            "do_not_promote_stage12059": True,
            "do_not_run_same_recipe_again": True,
            "recommended_next_stage": "stage12062_transition_v35_integration_ablation_request",
            "hypothesis_to_test": "The 311 verifier-status support rows are too concentrated into transition_verifier_transition and were mixed with old replay in a way that slightly damages old transition retention; test lower support weight or train only the verifier-transition/status head without touching next_action/candidate/continue boundaries.",
            "minimum_next_gates": {
                "old_transition_640": ">=364 before any promotion; >386 for Gemma win",
                "protected_filtered_strict": "22/22",
                "protected_old_strict": "23/23",
                "residual": ">=7/10",
                "source_heldout_smoke": ">=6/12",
            },
        },
        "source_artifacts": {
            "request": rel(REQUEST),
            "train_result": rel(TRAIN_RESULT),
            "audit": rel(AUDIT),
            "base_card": rel(BASE_CARD),
            "post_card": rel(POST_CARD),
        },
        "outputs": {"summary": rel(SUMMARY), "summary_mirror": f"runs/summaries/{NAME}.json"},
    }
    SUMMARY.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    (SUM / f"{NAME}.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": decision, "scores": payload["scores"], "flip_analysis": {k: payload["flip_analysis"][k] for k in ["gained_rows", "lost_rows", "net_correct_delta"]}}, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
