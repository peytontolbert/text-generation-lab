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
NAME = "stage11681_web_counterfactual_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_counterfactual_decision.json"

AUDIT = ART / "stage11680_web_same_role_counterfactual_postrun_audit/web_same_role_counterfactual_postrun_audit.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def score(results: dict[str, Any], key: str) -> str:
    return f"{results[key]['correct']}/{results[key]['rows']}"


def main() -> None:
    audit = load_json(AUDIT)
    results = audit["results"]
    gates = {
        "protected_gates_preserved": audit.get("preservation_ok") is True,
        "canonical_regressed_vs_stage11673": results["canonical_heldout"]["correct"] < 51,
        "original_web_not_frontier": results["original_web_heldout"]["correct"] <= 38,
        "counterfactual_train_fit_weak": results["same_role_counterfactual_train"]["correct"] < 70,
        "sealed_miss_moved": results["sealed_remaining_miss_diagnostics"]["correct"] > 0,
    }
    decision = (
        "stage11679_rejected_counterfactual_rows_overpush_and_underfit"
        if gates["protected_gates_preserved"]
        and gates["canonical_regressed_vs_stage11673"]
        and gates["original_web_not_frontier"]
        and gates["counterfactual_train_fit_weak"]
        else "stage11679_decision_needs_review"
    )
    summary = {
        "stage": 11681,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "scores": {
            "canonical_heldout": score(results, "canonical_heldout"),
            "original_web_heldout": score(results, "original_web_heldout"),
            "sealed_remaining_miss_diagnostics": score(results, "sealed_remaining_miss_diagnostics"),
            "same_role_counterfactual_train": score(results, "same_role_counterfactual_train"),
            "filtered_strict": score(results, "filtered_strict"),
            "old_canary_strict": score(results, "old_canary_strict"),
            "filtered_validation": score(results, "filtered_validation"),
            "old_canary_validation": score(results, "old_canary_validation"),
            "residual_bank": score(results, "residual_bank"),
        },
        "gates": gates,
        "interpretation": [
            "Stage11679 preserved protected gates but is not a frontier candidate.",
            "The added same-role counterfactual rows underfit badly on their own train slice.",
            "The run moved one sealed remaining miss but regressed canonical heldout from 51/66 to 43/66.",
            "Do not promote this runtime. Keep Stage11507/Stage11673 as the relevant selected baselines.",
        ],
        "recommended_next": {
            "stage": "stage11682_same_role_counterfactual_quality_audit",
            "target": "audit why Stage11678 counterfactual train rows score only 23/92 before any further training",
            "focus": [
                "verify target remapping after label shuffle",
                "inspect prompt label order and canonical_candidate_object candidate_id consistency",
                "separate candidate_change_surface identity rows from verifier transition rows",
                "avoid another training run until counterfactual train fit is plausible",
            ],
        },
        "source_artifacts": {"audit": rel(AUDIT)},
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "scores": summary["scores"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
