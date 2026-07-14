#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11677_web_same_role_listwise_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_same_role_listwise_decision.json"

BASELINE = ART / "stage11673_web_canonical_verifier_value_listwise_postrun_audit/web_canonical_verifier_value_listwise_postrun_audit.json"
SAME_ROLE = ART / "stage11676_web_canonical_same_role_listwise_postrun_audit/web_canonical_same_role_listwise_postrun_audit.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def score(summary: dict[str, Any], label: str) -> dict[str, Any]:
    results = summary["results"]
    return {
        "label": label,
        "canonical_heldout": f"{results['canonical_heldout']['correct']}/{results['canonical_heldout']['rows']}",
        "original_web_heldout": f"{results['original_web_heldout']['correct']}/{results['original_web_heldout']['rows']}",
        "web_successor_strict": f"{results['web_successor_strict']['correct']}/{results['web_successor_strict']['rows']}",
        "filtered_strict": f"{results['filtered_strict']['correct']}/{results['filtered_strict']['rows']}",
        "old_canary_strict": f"{results['old_canary_strict']['correct']}/{results['old_canary_strict']['rows']}",
        "filtered_validation": f"{results['filtered_validation']['correct']}/{results['filtered_validation']['rows']}",
        "old_canary_validation": f"{results['old_canary_validation']['correct']}/{results['old_canary_validation']['rows']}",
        "residual_bank": f"{results['residual_bank']['correct']}/{results['residual_bank']['rows']}",
    }


def main() -> None:
    baseline = load_json(BASELINE)
    same_role = load_json(SAME_ROLE)
    baseline_misses = {miss["row_id"]: miss for miss in baseline["results"]["canonical_heldout"].get("misses", [])}
    same_role_misses = {miss["row_id"]: miss for miss in same_role["results"]["canonical_heldout"].get("misses", [])}
    fixed = sorted(set(baseline_misses) - set(same_role_misses))
    new_misses = sorted(set(same_role_misses) - set(baseline_misses))
    gates = {
        "protected_gates_preserved": all(
            [
                same_role["results"]["filtered_strict"]["correct"] == 22,
                same_role["results"]["old_canary_strict"]["correct"] == 23,
                same_role["results"]["filtered_validation"]["correct"] == 20,
                same_role["results"]["old_canary_validation"]["correct"] == 21,
                same_role["results"]["residual_bank"]["correct"] == 7,
            ]
        ),
        "canonical_heldout_improved_over_stage11673": same_role["results"]["canonical_heldout"]["correct"]
        > baseline["results"]["canonical_heldout"]["correct"],
        "original_web_improved_over_stage11673": same_role["results"]["original_web_heldout"]["correct"]
        > baseline["results"]["original_web_heldout"]["correct"],
        "no_new_canonical_misses": not new_misses,
        "same_role_objective_was_active": same_role["training_objective_summary"]["same_role_listwise"]["applicable_rows_total"] > 0,
    }
    original_web_correct = int(same_role["results"]["original_web_heldout"]["correct"])
    canonical_correct = int(same_role["results"]["canonical_heldout"]["correct"])
    if not gates["protected_gates_preserved"]:
        decision = "same_role_listwise_rejected_protected_gate_regression"
    elif gates["same_role_objective_was_active"] and canonical_correct <= 51 and original_web_correct <= 38:
        decision = "same_role_listwise_rejected_no_frontier_gain"
    elif gates["same_role_objective_was_active"] and canonical_correct > 51 and original_web_correct <= 38:
        decision = "same_role_listwise_canonical_only_gain_not_web_frontier"
    elif gates["same_role_objective_was_active"] and original_web_correct > 38:
        decision = "same_role_listwise_candidate_web_frontier_gain_requires_review"
    else:
        decision = "same_role_listwise_decision_needs_review"
    summary = {
        "stage": 11677,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "baseline": score(baseline, "stage11673_verifier_value_listwise"),
        "same_role": score(same_role, "stage11676_same_role_listwise"),
        "gates": gates,
        "fixed_canonical_misses": fixed,
        "new_canonical_misses": new_misses,
        "remaining_canonical_misses": list(same_role_misses.values()),
        "training_objective_summary": same_role["training_objective_summary"],
        "interpretation": [
            "The generic same-role listwise objective was active and preserved all protected gates.",
            "It did not improve canonical heldout beyond Stage11673.",
            "It recovered original Web heldout from Stage11673's 27/66 to 28/66, but this only matches an earlier baseline and remains below the >38/66 Web frontier gate.",
            "Do not promote Stage11675/11676 over Stage11673 or the selected Stage11507 frontier.",
            "The next useful intervention should change the data geometry or scorer architecture, not repeat same-package listwise tuning.",
        ],
        "recommended_next": {
            "stage": "stage11678_web_remaining_miss_counterfactual_builder",
            "target": "materialize counterfactual same-role candidate identity rows for the remaining canonical misses, with heldout roots separated before training",
            "minimum_gate": [
                "canonical heldout > 51/66",
                "original Web heldout > 38/66 for Web frontier progress",
                "filtered strict 22/22",
                "old canary strict 23/23",
                "residual bank >= 7/10",
            ],
        },
        "source_artifacts": {"baseline": rel(BASELINE), "same_role": rel(SAME_ROLE)},
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "gates": gates, "fixed": fixed, "new_misses": new_misses}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
