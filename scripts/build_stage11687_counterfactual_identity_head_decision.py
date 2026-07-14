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
NAME = "stage11687_counterfactual_identity_head_decision"
OUT = ART / NAME
SUMMARY = OUT / "counterfactual_identity_head_decision.json"

BUGGY = ART / "stage11684_counterfactual_identity_semantic_head_postrun_audit/counterfactual_identity_semantic_head_postrun_audit.json"
FIXED = ART / "stage11686_counterfactual_identity_semantic_head_fixed_postrun_audit/counterfactual_identity_semantic_head_fixed_postrun_audit.json"
QUALITY = ART / "stage11682_same_role_counterfactual_quality_audit/same_role_counterfactual_quality_audit.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def score(summary: dict[str, Any], key: str) -> str:
    result = summary["results"][key]
    return f"{result['correct']}/{result['rows']}"


def main() -> None:
    buggy = load_json(BUGGY)
    fixed = load_json(FIXED)
    quality = load_json(QUALITY)
    gates = {
        "bug_found_nested_options_stale": quality.get("gates", {}).get("static_remap_clean") is True
        and buggy["results"]["same_role_counterfactual_train"]["correct"] < fixed["results"]["same_role_counterfactual_train"]["correct"],
        "fixed_head_fits_counterfactual_train": fixed["results"]["same_role_counterfactual_train"]["correct"] == 92,
        "fixed_head_moves_sealed_diagnostics": fixed["results"]["sealed_remaining_miss_diagnostics"]["correct"] > buggy["results"]["sealed_remaining_miss_diagnostics"]["correct"],
        "protected_gates_preserved": all(
            [
                fixed["results"]["filtered_strict"]["correct"] == 22,
                fixed["results"]["old_canary_strict"]["correct"] == 23,
                fixed["results"]["filtered_validation"]["correct"] == 20,
                fixed["results"]["old_canary_validation"]["correct"] == 21,
                fixed["results"]["residual_bank"]["correct"] == 7,
            ]
        ),
        "not_web_frontier": fixed["results"]["original_web_heldout"]["correct"] <= 38,
        "not_canonical_frontier": fixed["results"]["canonical_heldout"]["correct"] <= 51,
    }
    decision = (
        "identity_head_validated_as_fit_path_not_promoted"
        if gates["fixed_head_fits_counterfactual_train"]
        and gates["fixed_head_moves_sealed_diagnostics"]
        and gates["protected_gates_preserved"]
        and gates["not_web_frontier"]
        else "identity_head_decision_needs_review"
    )
    summary = {
        "stage": 11687,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "scores": {
            "buggy_stage11684": {
                "same_role_counterfactual_train": score(buggy, "same_role_counterfactual_train"),
                "sealed_remaining_miss_diagnostics": score(buggy, "sealed_remaining_miss_diagnostics"),
                "canonical_heldout": score(buggy, "canonical_heldout"),
                "original_web_heldout": score(buggy, "original_web_heldout"),
            },
            "fixed_stage11686": {
                "same_role_counterfactual_train": score(fixed, "same_role_counterfactual_train"),
                "sealed_remaining_miss_diagnostics": score(fixed, "sealed_remaining_miss_diagnostics"),
                "canonical_heldout": score(fixed, "canonical_heldout"),
                "original_web_heldout": score(fixed, "original_web_heldout"),
                "filtered_strict": score(fixed, "filtered_strict"),
                "old_canary_strict": score(fixed, "old_canary_strict"),
                "residual_bank": score(fixed, "residual_bank"),
            },
        },
        "gates": gates,
        "interpretation": [
            "The Stage11678 underfit was caused by stale nested standalone_projection_source.opaque_options, not by impossible counterfactual geometry.",
            "After synchronizing nested and row-level options, the semantic candidate head fits the 92-row same-role identity slice exactly.",
            "The fitted identity head moves sealed canonical misses from 1/15 to 5/15 but does not transfer broadly: canonical heldout is 27/66 and original Web is 9/66 under that scorer.",
            "Do not promote Stage11685. Use the finding to build a routed identity scorer for same-role candidate rows, then test with preservation gates.",
        ],
        "recommended_next": {
            "stage": "stage11688_routed_web_identity_scorer_audit_or_probe",
            "target": "route same-role candidate identity rows to the semantic identity head while keeping normal Web rows on the current Web task head",
            "promotion_gate": [
                "canonical heldout > 51/66",
                "original Web heldout > 38/66 for Web frontier progress",
                "filtered strict 22/22",
                "old canary strict 23/23",
                "residual bank >= 7/10",
            ],
        },
        "source_artifacts": {"buggy": rel(BUGGY), "fixed": rel(FIXED), "quality": rel(QUALITY)},
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "scores": summary["scores"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
