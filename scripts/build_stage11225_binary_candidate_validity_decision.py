#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11225
NAME = "stage11225_binary_candidate_validity_decision"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "binary_candidate_validity_decision.json"
COMPARISON = ARTIFACTS / "stage11224_binary_candidate_validity_same_manifest_comparison/binary_candidate_validity_same_manifest_comparison.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def nested(payload: dict[str, Any], keys: list[str]) -> Any:
    cur: Any = payload
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def main() -> None:
    comparison = load_json(COMPARISON)
    base_pos = nested(comparison, ["base_100m", "by_binary_target", "DECISIVE_EVIDENCE_ITEM", "exact_accuracy"])
    binary_pos = nested(comparison, ["binary_support_100m", "by_binary_target", "DECISIVE_EVIDENCE_ITEM", "exact_accuracy"])
    gemma_pos = nested(comparison, ["gemma12b", "by_binary_target", "DECISIVE_EVIDENCE_ITEM", "exact_accuracy"])
    base_overall = nested(comparison, ["base_100m", "overall", "exact_accuracy"])
    binary_overall = nested(comparison, ["binary_support_100m", "overall", "exact_accuracy"])
    gemma_overall = nested(comparison, ["gemma12b", "overall", "exact_accuracy"])
    decision = "reject_current_binary_candidate_validity_training_interface"
    passed = base_pos == 0.0 and binary_pos == 0.0
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": passed,
        "decision": decision,
        "source_artifacts": {"comparison": rel(COMPARISON)},
        "key_result": {
            "base_100m_overall": base_overall,
            "binary_support_100m_overall": binary_overall,
            "gemma12b_overall": gemma_overall,
            "base_100m_positive_decisive_accuracy": base_pos,
            "binary_support_100m_positive_decisive_accuracy": binary_pos,
            "gemma12b_positive_decisive_accuracy": gemma_pos,
        },
        "interpretation": [
            "The 100M scorer achieves high row accuracy by predicting the negative class for every binary candidate.",
            "Stage11220 binary support did not change the baseline behavior on this diagnostic eval.",
            "Gemma is lower overall but recognizes decisive positives, so the 100M's binary interface is not yet a credible evidence-validity capability.",
            "Do not scale this binary formulation without class-balanced positive training and a scorer objective that rewards positive evidence recognition.",
        ],
        "recommended_next_work": [
            "Build root-disjoint binary candidate-validity rows with balanced positives/negatives per batch.",
            "Train/evaluate with positive recall and root-solved metrics as hard gates, not overall accuracy alone.",
            "Keep the clean strict 22/22 canary and residual 5/10 bank as regression gates.",
            "Do not promote Stage11220 or the current binary candidate-validity interface as a frontier gain.",
        ],
        "outputs": {"summary_json": rel(SUMMARY_JSON)},
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
