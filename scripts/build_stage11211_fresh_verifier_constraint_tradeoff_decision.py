#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11211
NAME = "stage11211_fresh_verifier_constraint_tradeoff_decision"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_verifier_constraint_tradeoff_decision.json"

NO_KL = ARTIFACTS / "stage11208_fresh_verifier_constraint_postrun_audit/fresh_verifier_constraint_postrun_audit.json"
KL = ARTIFACTS / "stage11210_fresh_verifier_constraint_preserved_postrun_audit/fresh_verifier_constraint_preserved_postrun_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def get(payload: dict[str, Any], path: list[str]) -> Any:
    cur: Any = payload
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def compact(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": payload.get("decision"),
        "promotion_gate": payload.get("promotion_gate"),
        "strict": get(payload, ["clean_strict", "row_metric"]),
        "validation": get(payload, ["clean_validation", "row_metric"]),
        "residual": get(payload, ["clean_residual_successor", "productized_result", "row_metric"]),
        "residual_cluster": {
            "clusters": get(payload, ["clean_residual_successor", "productized_result", "cluster_metric", "clusters"]),
            "solved_clusters": get(payload, ["clean_residual_successor", "productized_result", "cluster_metric", "solved_clusters"]),
            "cluster_exact_accuracy": get(payload, ["clean_residual_successor", "productized_result", "cluster_metric", "cluster_exact_accuracy"]),
        },
        "residual_delta_vs_baseline": get(payload, ["clean_residual_successor", "row_accuracy_delta_vs_baseline_100m"]),
        "residual_delta_vs_gemma": get(payload, ["clean_residual_successor", "row_accuracy_delta_vs_gemma"]),
        "misses": {
            "strict": get(payload, ["clean_strict", "misses"]),
            "validation": get(payload, ["clean_validation", "misses"]),
            "residual": get(payload, ["clean_residual_successor", "productized_result", "misses"]),
        },
    }


def main() -> None:
    no_kl = load_json(NO_KL)
    kl = load_json(KL)
    no_kl_compact = compact(no_kl)
    kl_compact = compact(kl)

    no_kl_strict_ok = bool(get(no_kl, ["promotion_gate", "strict_preserved_22_of_22"]))
    no_kl_residual_gain = bool(get(no_kl, ["promotion_gate", "residual_improved_vs_stage11196"]))
    kl_strict_ok = bool(get(kl, ["promotion_gate", "strict_preserved_22_of_22"]))
    kl_residual_gain = bool(get(kl, ["promotion_gate", "residual_improved_vs_stage11196"]))

    decision = "reject_current_fresh_verifier_constraint_branch"
    if no_kl_residual_gain and not no_kl_strict_ok and kl_strict_ok and not kl_residual_gain:
        interpretation = (
            "The fresh verifier/test-constraint rows contain a real but fragile residual signal. "
            "When unconstrained, they move the residual bank from 5/10 to 6/10 but damage the clean strict canary. "
            "When preservation KL is enabled, the canary is restored but the residual movement disappears. "
            "This is a data/objective tradeoff, not a promotable capability gain."
        )
    else:
        interpretation = (
            "The fresh verifier/test-constraint branch did not satisfy both required gates: strict canary "
            "preservation and residual-bank improvement."
        )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": decision,
        "interpretation": interpretation,
        "source_artifacts": {
            "no_kl_postrun": rel(NO_KL),
            "preserved_kl_postrun": rel(KL),
        },
        "comparison": {
            "no_kl_stage11208": no_kl_compact,
            "preserved_kl_stage11210": kl_compact,
        },
        "blocked_claims": [
            "Do not promote Stage11207/11208 because strict regressed to 21/22.",
            "Do not promote Stage11209/11210 because residual stayed at the Stage11196 5/10 baseline.",
            "Do not claim verifier_and_test_constraint is fixed; it remains 0/3 on the clean residual successor under the productized scorer.",
        ],
        "next_required_work": [
            {
                "priority": 1,
                "work": "Build a direct semantic candidate objective for evidence roles instead of relying on generic encoder option retrieval.",
                "reason": "Fresh support rows and KL controls show the signal is not stable under the current scorer objective.",
            },
            {
                "priority": 2,
                "work": "Materialize more root-disjoint verifier_and_test_constraint rows with candidate_change_surface controls, but keep them out of strict until admitted.",
                "reason": "The current added rows are useful support, but not sufficient to move the productized residual bank without canary damage.",
            },
            {
                "priority": 3,
                "work": "Keep Stage11204 rust-only role routing as diagnostic-only.",
                "reason": "It preserves strict and reaches 6/10 residual, but still trails Gemma row accuracy and does not solve verifier_and_test_constraint.",
            },
        ],
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
