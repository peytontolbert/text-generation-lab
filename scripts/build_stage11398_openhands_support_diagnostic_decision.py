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
STAGE = 11398
NAME = "stage11398_openhands_support_diagnostic_decision"
OUT = ART / NAME
SUMMARY = OUT / "openhands_support_diagnostic_decision.json"

POSTRUN = ART / "stage11397_openhands_support_postrun_audit/openhands_support_postrun_audit.json"
GEMMA = ART / "stage11392_openhands_web_same_manifest_gemma_comparison/openhands_web_same_manifest_gemma_comparison.json"


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def main() -> None:
    postrun = read_json(POSTRUN)
    gemma = read_json(GEMMA)
    base = postrun["base_heldout"]
    candidate = postrun["candidate_heldout"]
    gemma_metric = gemma["gemma12b"]
    candidate_acc = candidate.get("exact_accuracy")
    gemma_acc = gemma_metric.get("exact_accuracy")
    gemma_gap = None if candidate_acc is None or gemma_acc is None else candidate_acc - gemma_acc
    strict_ok = not postrun.get("strict_regressed")
    validation_ok = not postrun.get("validation_regressed")
    heldout_improved = (postrun.get("heldout_delta") or 0) > 0
    beats_gemma = gemma_gap is not None and gemma_gap > 0
    promote_frontier = bool(heldout_improved and strict_ok and validation_ok and beats_gemma)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "decision": "do_not_promote_stage11396_frontier",
        "diagnostic_decision": "stage11396_is_useful_web_support_direction" if heldout_improved else "stage11396_rejected_no_heldout_gain",
        "frontier_runtime_remains": "stage11200_role_focused_residual_probe",
        "candidate_runtime": "stage11396_openhands_support_diagnostic_probe",
        "claim_scope": "OpenHands Web verifier smoke slice only; same broad project family support and heldout, not a broad Web or multilingual claim",
        "base_stage11200_heldout": base,
        "candidate_stage11396_heldout": candidate,
        "heldout_delta_stage11396_minus_stage11200": postrun.get("heldout_delta"),
        "gemma12b_same_manifest": gemma_metric,
        "delta_stage11396_minus_gemma12b": gemma_gap,
        "strict_canary_preserved": strict_ok,
        "validation_canary_preserved_or_improved": validation_ok,
        "promotion_gate": {
            "heldout_improved": heldout_improved,
            "strict_canary_preserved": strict_ok,
            "validation_canary_preserved_or_improved": validation_ok,
            "beats_gemma_same_manifest": beats_gemma,
            "promote_frontier": promote_frontier,
        },
        "interpretation": (
            "Stage11396 more than doubles the 100M score on the sealed OpenHands slice from 4/18 to 9/18 "
            "without canary regression, but Gemma remains 18/18. Treat this as evidence that targeted Web "
            "verifier support is the right direction, not as a frontier or public Web win."
        ),
        "recommended_next_action": (
            "Materialize broader disjoint Web verifier roots outside the current OpenHands/MCP/Sourcebot families, "
            "then rerun the same same-manifest 100M-vs-Gemma comparison."
        ),
        "source_artifacts": {
            "postrun_audit": rel(POSTRUN),
            "gemma_comparison": rel(GEMMA),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["promotion_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
