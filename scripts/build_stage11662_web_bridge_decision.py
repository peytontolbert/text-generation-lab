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
STAGE = 11662
NAME = "stage11662_web_bridge_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_bridge_decision.json"

TRANSFER_AUDIT = ART / "stage11658_web_head_transfer_gap_audit/web_head_transfer_gap_audit.json"
BRIDGE_PACKAGE = ART / "stage11659_web_schema_aligned_bridge_package/web_schema_aligned_bridge_package.json"
BRIDGE_POSTRUN = ART / "stage11661_web_schema_aligned_bridge_postrun_audit/web_schema_aligned_bridge_postrun_audit.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    transfer = load_json(TRANSFER_AUDIT)
    package = load_json(BRIDGE_PACKAGE)
    postrun = load_json(BRIDGE_POSTRUN)
    result = postrun["results"]
    gates = postrun["gates"]
    decision = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "selected_frontier_unchanged": "stage11507 + encoder_option_retrieval_evidence_judgment_head",
        "stage11660_runtime": postrun.get("runtime"),
        "stage11660_runtime_weights_sha256": postrun.get("runtime_weights_sha256"),
        "decision": "schema_alignment_helped_but_head_only_web_bridge_not_promotable",
        "evidence": {
            "stage11657_old_schema_web_heldout": "4/66",
            "stage11661_schema_aligned_web_heldout": f"{result['web_heldout']['correct']}/{result['web_heldout']['rows']}",
            "stage11661_schema_aligned_train_support": f"{result['schema_aligned_bridge_train_support']['correct']}/{result['schema_aligned_bridge_train_support']['rows']}",
            "routed_product_web_frontier": "38/66",
            "gemma_web_reference": "52/66",
            "protected_gates_preserved": all(
                gates[key]
                for key in [
                    "filtered_strict_22_of_22",
                    "old_canary_strict_23_of_23",
                    "filtered_validation_at_least_20_of_22",
                    "old_canary_validation_at_least_21_of_23",
                    "residual_at_least_7_of_10",
                ]
            ),
        },
        "what_was_learned": [
            "Stage11658 confirmed the original Web support package had train/heldout schema and option-value geometry mismatch.",
            "Stage11659 normalized evidence-citation option values to semantic roles and rerendered prompts in a heldout-like style.",
            "Stage11661 improved Web heldout from 4/66 to 17/66 under the Web task head while preserving protected routed gates.",
            "The improvement is real but far below the 38/66 routed frontier and 52/66 Gemma reference.",
        ],
        "stop_conditions": [
            "Do not promote Stage11660.",
            "Do not run another head-only bridge probe on the same 113 roots as a frontier attempt.",
            "Do not claim Web broad transfer from schema-aligned support fit.",
        ],
        "next_best_intervention": {
            "name": "web_heldout_style_root_supply_or_task_specific_web_heads",
            "requirements": [
                "Add fresh Web train roots rendered in the same schema as the heldout rows, not repaired-shell path-handle rows.",
                "Cover MCP and OpenHands heldout task families specifically, including symptom_localization, verifier_outcome, minimal_fix_selection, abstention, and patch_impact.",
                "Prefer task-specific Web heads or routed heads rather than one generic Web task candidate head if aligned support still fails to transfer.",
                "Keep Stage11507 protected gates as hard promotion requirements.",
                "Promotion requires Web heldout >38/66 before comparing to Gemma 52/66.",
            ],
        },
        "source_artifacts": {
            "transfer_audit": rel(TRANSFER_AUDIT),
            "bridge_package": rel(BRIDGE_PACKAGE),
            "bridge_postrun": rel(BRIDGE_POSTRUN),
            "bridge_manifest": package.get("manifest"),
        },
    }
    write_json(SUMMARY, decision)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision["decision"], "evidence": decision["evidence"], "next": decision["next_best_intervention"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
