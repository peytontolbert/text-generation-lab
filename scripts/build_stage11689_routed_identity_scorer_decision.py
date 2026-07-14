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
NAME = "stage11689_routed_identity_scorer_decision"
OUT = ART / NAME
SUMMARY = OUT / "routed_identity_scorer_decision.json"

AUDIT = ART / "stage11688_routed_web_identity_scorer_audit/routed_web_identity_scorer_audit.json"


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
    audit = load_json(AUDIT)
    results = audit["results"]
    gates = {
        "canonical_heldout_improved_over_51": results["canonical_heldout"]["correct"] > 51,
        "original_web_improved_over_routed_38": results["original_web_heldout"]["correct"] > 38,
        "sealed_remaining_improved_over_5": results["sealed_remaining_miss_diagnostics"]["correct"] > 5,
        "filtered_strict_preserved": results["filtered_strict"]["correct"] == 22,
        "filtered_validation_preserved": results["filtered_validation"]["correct"] >= 20,
        "old_canary_strict_preserved": results["old_canary_strict"]["correct"] == 23,
        "old_canary_validation_preserved": results["old_canary_validation"]["correct"] >= 21,
        "residual_bank_preserved": results["residual_bank"]["correct"] >= 7,
    }
    protected_ok = all(
        [
            gates["filtered_strict_preserved"],
            gates["filtered_validation_preserved"],
            gates["old_canary_strict_preserved"],
            gates["old_canary_validation_preserved"],
            gates["residual_bank_preserved"],
        ]
    )
    decision = (
        "canonical_renderer_gain_only_not_product_web_frontier"
        if gates["canonical_heldout_improved_over_51"] and protected_ok and not gates["original_web_improved_over_routed_38"]
        else "routed_identity_scorer_needs_review"
    )
    summary = {
        "stage": 11689,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "scores": {
            "canonical_heldout": score(audit, "canonical_heldout"),
            "original_web_heldout": score(audit, "original_web_heldout"),
            "sealed_remaining_miss_diagnostics": score(audit, "sealed_remaining_miss_diagnostics"),
            "filtered_strict": score(audit, "filtered_strict"),
            "filtered_validation": score(audit, "filtered_validation"),
            "old_canary_strict": score(audit, "old_canary_strict"),
            "old_canary_validation": score(audit, "old_canary_validation"),
            "residual_bank": score(audit, "residual_bank"),
        },
        "gates": gates,
        "route_counts": audit.get("route_counts", {}),
        "interpretation": [
            "The two-runtime route improves canonical-renderer heldout from the prior 51/66 frontier to 53/66 while preserving protected gates.",
            "It does not improve the original Web heldout frontier: original Web remains 28/66, below the routed product scorer baseline of 38/66.",
            "The identity route is not exercised on original Web heldout because those rows do not match the same-role candidate route predicate.",
            "Treat Stage11688 as evidence that same-role identity scoring is useful inside the canonical renderer, not as a promoted broad Web product scorer.",
        ],
        "recommended_next": {
            "stage": "stage11690_canonical_to_original_web_bridge_or_route_expansion",
            "target": "materialize original Web heldout-style rows into canonical role-typed candidate objects, or broaden routing only after a leak-clean predicate fires on original Web rows",
            "promotion_gate": [
                "original Web heldout > 38/66",
                "canonical heldout >= 53/66",
                "filtered strict 22/22",
                "old canary strict 23/23",
                "residual bank >= 7/10",
                "no heldout-root leakage",
            ],
        },
        "claim_boundary": [
            "Supported: canonical-renderer same-role routing can improve canonical Web heldout while preserving protected compact maintainer gates.",
            "Not supported: broad Web heldout improvement, full-product Web generalization, or executable patch/verifier repair improvement.",
        ],
        "source_artifacts": {"audit": rel(AUDIT)},
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "scores": summary["scores"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
