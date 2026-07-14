#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10461
NAME = "stage10461_reviewed_v27_residual_promotion_gate"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GATE_JSON = OUT_DIR / "reviewed_v27_residual_promotion_gate.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASELINE_AUDIT = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
CANDIDATE_AUDIT = ROOT / "runs/local/artifacts/stage10456_reviewed_v27_narrow_residual_support_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
LEAK_AUDIT = ROOT / "runs/local/artifacts/stage10437_repaired_v27_strict_overlay_eval_hacking_audit/repaired_v27_strict_overlay_eval_hacking_audit.json"
NARROW_AUDIT = ROOT / "runs/local/artifacts/stage10457_narrow_residual_probe_audit/narrow_residual_probe_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    baseline = load_json(BASELINE_AUDIT)
    candidate = load_json(CANDIDATE_AUDIT)
    leak = load_json(LEAK_AUDIT)
    narrow = load_json(NARROW_AUDIT)

    base_rows = {row["row_id"]: row for row in baseline["row_cards"]}
    cand_rows = {row["row_id"]: row for row in candidate["row_cards"]}
    regressions = []
    for row_id, base_row in base_rows.items():
        cand_row = cand_rows[row_id]
        if base_row["constrained_choice_match"] and not cand_row["constrained_choice_match"]:
            regressions.append(
                {
                    "row_id": row_id,
                    "baseline_pred": base_row["constrained_choice_top1_label"],
                    "candidate_pred": cand_row["constrained_choice_top1_label"],
                    "target": cand_row["target_text"],
                }
            )

    baseline_acc = baseline["constrained_choice_top1_accuracy"]
    candidate_acc = candidate["constrained_choice_top1_accuracy"]
    beat_baseline = candidate_acc > baseline_acc
    zero_new_regressions = len(regressions) == 0
    leak_summary = leak.get("summary") or {}
    leak_rows = leak_summary.get("rows_with_prompt_target_leak")
    no_leak_hygiene = leak_rows == 0
    fresh_disjoint_root_evidence = False

    criteria = {
        "beats_22_of_24_baseline": {
            "passed": beat_baseline,
            "candidate_accuracy": candidate_acc,
            "baseline_accuracy": baseline_acc,
        },
        "zero_new_regressions": {
            "passed": zero_new_regressions,
            "regression_count": len(regressions),
            "regressions": regressions,
        },
        "passes_on_fresh_disjoint_roots": {
            "passed": fresh_disjoint_root_evidence,
            "reason": "no fresh disjoint residual-root comparison artifact is attached yet",
        },
        "repaired_overlay_no_leak_hygiene": {
            "passed": no_leak_hygiene,
            "rows_with_prompt_target_leak": leak_rows,
            "audited_overlay_rows": leak_summary.get("rows"),
        },
    }

    gate = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": all(item["passed"] for item in criteria.values()),
        "decision": "promotion_rejected_until_fresh_root_improvement",
        "claim_scope": [
            "Gate any residual-support run before it can affect the promotable v2.7 headline.",
            "Require a strict improvement over the 22/24 repaired-overlay baseline, zero new regressions, fresh disjoint-root success, and leak-clean overlay hygiene.",
        ],
        "source_artifacts": {
            "baseline_strict_audit": display(BASELINE_AUDIT),
            "candidate_strict_audit": display(CANDIDATE_AUDIT),
            "overlay_leak_audit": display(LEAK_AUDIT),
            "candidate_run_audit": display(NARROW_AUDIT),
        },
        "criteria": criteria,
        "current_candidate_summary": {
            "candidate_accuracy": candidate_acc,
            "baseline_accuracy": baseline_acc,
            "changed_rows": narrow.get("changed_rows"),
            "remaining_misses": narrow.get("remaining_misses"),
        },
        "required_for_future_promotion": [
            "Strict constrained accuracy must exceed 22/24.",
            "Regression count must remain zero relative to the live repaired-overlay baseline.",
            "A fresh disjoint residual-root artifact must show the same improvement on unseen roots.",
            "Overlay leak audit must remain clean.",
        ],
    }

    write_json(GATE_JSON, gate)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": gate["passed"],
            "decision": gate["decision"],
            "gate": display(GATE_JSON),
        },
    )
    print(json.dumps(gate, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
