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
STAGE = 11462
NAME = "stage11462_post_rust_breadth_frontier_decision"
OUT = ART / NAME
SUMMARY = OUT / "post_rust_breadth_frontier_decision.json"

SAFE = ART / "stage11446_safe_frontier_scorer_selection_decision/stage11446_safe_frontier_scorer_selection_decision.json"
COMPARISON = ART / "stage11447_selected_runtime_same_manifest_gemma_comparison/stage11447_selected_runtime_same_manifest_gemma_comparison.json"
RUST_READY = ART / "stage11455_rust_breadth_support_probe_readiness_decision/rust_breadth_support_probe_readiness_decision.json"
AGGRESSIVE = ART / "stage11458_rust_breadth_support_postrun_audit/rust_breadth_support_postrun_audit.json"
CONSERVATIVE = ART / "stage11461_conservative_rust_breadth_postrun_audit/conservative_rust_breadth_postrun_audit.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def product_metrics(audit: dict[str, Any]) -> dict[str, Any]:
    product = (audit.get("scored") or {}).get("encoder_option_retrieval") or {}
    return {
        "filtered_strict": (product.get("filtered_strict") or {}).get("correct"),
        "filtered_strict_rows": (product.get("filtered_strict") or {}).get("rows"),
        "filtered_validation": (product.get("filtered_validation") or {}).get("correct"),
        "filtered_validation_rows": (product.get("filtered_validation") or {}).get("rows"),
        "old_canary_strict": (product.get("old_canary_strict") or {}).get("correct"),
        "old_canary_strict_rows": (product.get("old_canary_strict") or {}).get("rows"),
        "residual_bank": (product.get("residual_bank") or {}).get("correct"),
        "residual_bank_rows": (product.get("residual_bank") or {}).get("rows"),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    safe = read_json(SAFE)
    comparison = read_json(COMPARISON)
    rust_ready = read_json(RUST_READY)
    aggressive = read_json(AGGRESSIVE)
    conservative = read_json(CONSERVATIVE)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "keep_stage11444_as_selected_frontier_after_rust_breadth_diagnostics",
        "selected_frontier": {
            "runtime_bundle": "runs/local/artifacts/stage11444_targeted_residual_role_support_probe/runtime_model/runtime_model_bundle.json",
            "scorer": "encoder_option_retrieval",
            "weights_sha256": "094b2da23adeb46ae8c8be5244902c746962dda96019d1c64c3676b16b77e162",
        },
        "selected_frontier_evidence": {
            "same_manifest_gemma_comparison": comparison.get("metrics"),
            "safe_scorer_decision": safe.get("decision"),
        },
        "rust_breadth_data_status": {
            "readiness_decision": rust_ready.get("decision"),
            "counts": rust_ready.get("counts"),
            "quality_gate": rust_ready.get("quality_gate"),
        },
        "rejected_runtimes": {
            "stage11457_aggressive_rust_breadth": {
                "weights_sha256": aggressive.get("runtime_weights_sha256"),
                "decision": aggressive.get("decision"),
                "product_metrics": product_metrics(aggressive),
                "promotion_gates": aggressive.get("promotion_gates"),
            },
            "stage11460_conservative_rust_breadth": {
                "weights_sha256": conservative.get("runtime_weights_sha256"),
                "decision": conservative.get("decision"),
                "product_metrics": product_metrics(conservative),
                "promotion_gates": conservative.get("promotion_gates"),
            },
        },
        "interpretation": [
            "Rust materialization is no longer the immediate data-supply blocker: Stage11455 made a probe-ready breadth package.",
            "The aggressive Rust breadth run over-shifted evidence predictions and regressed strict/canary/residual.",
            "The conservative run preserved residual at 5/10 but still regressed strict and old canary by one row, so it is diagnostic only.",
            "Do not replace the Stage11444 selected standalone runtime until a run preserves 23/23 old canary, 22/22 filtered strict, and improves residual beyond 5/10.",
        ],
        "recommended_next_action": (
            "Treat Rust breadth rows as validated support inventory. The next model-side attempt should target the remaining "
            "Python verifier row and residual evidence rows with a scorer/objective change or explicit replay-preservation, "
            "not another broad Rust update."
        ),
        "source_artifacts": {
            "safe_frontier_decision": rel(SAFE),
            "same_manifest_gemma_comparison": rel(COMPARISON),
            "rust_breadth_readiness": rel(RUST_READY),
            "aggressive_postrun": rel(AGGRESSIVE),
            "conservative_postrun": rel(CONSERVATIVE),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "selected_frontier": summary["selected_frontier"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
