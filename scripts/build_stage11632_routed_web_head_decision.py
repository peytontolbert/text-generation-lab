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
STAGE = 11632
NAME = "stage11632_routed_web_head_decision"
OUT = ART / NAME
SUMMARY = OUT / "routed_web_head_decision.json"

HEAD_AUDIT = ART / "stage11631_web_head_only_transfer_audit/web_head_only_transfer_audit.json"
SELECTED_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
WEB_HEAD_RUNTIME = ART / "stage11625_web_fail_to_pass_stronger_head_overfit/runtime_model/runtime_model_bundle.json"


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
    audit = load_json(HEAD_AUDIT)
    results = audit["results"]
    routed_candidate = {
        "web_heldout": f"{results['web_heldout']['correct']}/{results['web_heldout']['rows']}",
        "web_successor_strict": f"{results['web_successor_strict']['correct']}/{results['web_successor_strict']['rows']}",
        "controlled_fail_to_pass_support": f"{results['controlled_fail_to_pass_support']['correct']}/{results['controlled_fail_to_pass_support']['rows']}",
        "protected_sets_use_stage11507_selected": {
            "filtered_strict": "22/22",
            "filtered_validation": "20/22",
            "old_canary_strict": "23/23",
            "old_canary_validation": "21/23",
            "residual_bank": "7/10",
        },
    }
    gates = {
        "web_head_beats_stage11507_web_heldout": results["web_heldout"]["correct"] > 35 and results["web_heldout"]["rows"] == 66,
        "web_head_improves_successor": results["web_successor_strict"]["correct"] >= 30 and results["web_successor_strict"]["rows"] == 36,
        "web_head_fits_controlled_support": results["controlled_fail_to_pass_support"]["correct"] == 48 and results["controlled_fail_to_pass_support"]["rows"] == 48,
        "global_web_head_not_safe": results["residual_bank"]["correct"] < 7 or results["filtered_strict"]["correct"] < 22,
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "build_routed_product_scorer_audit_next",
        "routed_candidate": routed_candidate,
        "gates": gates,
        "interpretation": [
            "The Stage11625 Web head is useful for Web rows: Web heldout improves from Stage11507 35/66 to 38/66.",
            "The same head is unsafe globally: residual drops to 1/10 and protected strict drops to 7/22.",
            "The next valid experiment is a routed scorer/product policy: use Stage11507 selected scorer for existing compact maintainer canaries and the Web task-candidate head only for Web FAIL_TO_PASS/Web heldout routing.",
            "This is a system-composition path, not a single-weight promotion yet.",
        ],
        "next_actions": [
            "Build Stage11633 routed scorer audit with explicit routing rules and no retraining.",
            "Require the routed audit to report protected Stage11507 gates plus Web-head heldout gains in one machine-readable card.",
            "If routed audit passes, decide whether to productize multi-scorer runtime or train a single model to distill the routed behavior.",
        ],
        "source_artifacts": {
            "head_audit": rel(HEAD_AUDIT),
            "selected_runtime": rel(SELECTED_RUNTIME),
            "web_head_runtime": rel(WEB_HEAD_RUNTIME),
        },
        "outputs": {"summary": rel(SUMMARY)},
        "claim_boundary": [
            "No single standalone model frontier is promoted by this decision.",
            "A routed product scorer may be useful for harness/product scoring, but must be audited separately.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "routed_candidate": routed_candidate, "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
