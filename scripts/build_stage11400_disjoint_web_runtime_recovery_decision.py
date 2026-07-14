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
STAGE = 11400
NAME = "stage11400_disjoint_web_runtime_recovery_decision"
OUT = ART / NAME
SUMMARY = OUT / "disjoint_web_runtime_recovery_decision.json"

FEASIBILITY = ART / "stage11399_disjoint_web_runtime_feasibility_and_queue/disjoint_web_runtime_feasibility_and_queue.json"
POSTRUN = ART / "stage11397_openhands_support_postrun_audit/openhands_support_postrun_audit.json"
DIAG_DECISION = ART / "stage11398_openhands_support_diagnostic_decision/openhands_support_diagnostic_decision.json"


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def main() -> None:
    feasibility = read_json(FEASIBILITY)
    postrun = read_json(POSTRUN)
    diag = read_json(DIAG_DECISION)
    blockers = feasibility.get("runtime_blockers") or []
    blocker_types = sorted({str(item.get("blocker")) for item in blockers if item.get("blocker")})
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "decision": "pause_disjoint_web_row_materialization_until_js_runtime_recovered",
        "frontier_runtime_remains": diag.get("frontier_runtime_remains"),
        "latest_useful_diagnostic_runtime": diag.get("candidate_runtime"),
        "why_not_more_training_now": [
            "Stage11396 improved OpenHands heldout from 4/18 to 9/18 but still trails Gemma 18/18.",
            "The next Web roots must be disjoint from OpenHands/MCP/Sourcebot/Llama Stack to avoid repo-family overfitting.",
            "Stage11399 identified two priority disjoint OpenClaw candidates but focused verifier execution is blocked by local JS runtime/dependency state.",
            "No synthetic or static-only rows should be admitted for a Web claim.",
        ],
        "current_web_signal": {
            "stage11200_openhands_heldout": postrun.get("base_heldout"),
            "stage11396_openhands_heldout": postrun.get("candidate_heldout"),
            "heldout_delta_stage11396_minus_stage11200": postrun.get("heldout_delta"),
            "gemma_same_manifest_from_stage11392": diag.get("gemma12b_same_manifest"),
        },
        "runtime_blockers": blockers,
        "blocker_types": blocker_types,
        "required_runtime_recovery": [
            {
                "repo_family": "openclaw_openclaw",
                "requirement": "Node >=22.13 with pnpm 11.1.0 or an equivalent pinned pnpm runtime that can run the repo lockfile.",
                "evidence_needed": "focused Vitest log for extensions/qa-lab/src/model-switch-eval.test.ts or another selected non-trivial QA-lab verifier.",
            },
            {
                "repo_family": "openclaw_clawhub",
                "requirement": "Bun runtime or fully installed npm/vitest dependencies for clawhub.",
                "evidence_needed": "focused Vitest/Bun log for convex/skills.versions.public.test.ts or another selected non-trivial clawhub verifier.",
            },
        ],
        "admission_policy": {
            "trainable_now": False,
            "scoreable_now": False,
            "emit_rows_before_runtime_recovery": False,
            "reason": "Maintainer-grade Web rows require executed or recovered verifier output plus selected source/test evidence; current disjoint candidates lack executable verifier logs.",
        },
        "next_allowed_steps": [
            "Explicitly approve/install Node 22.13+ and/or Bun, then rerun Stage11399 verifier attempts.",
            "If runtime install is not allowed, find already-hydrated disjoint Web repos with real unit verifier logs.",
            "After raw verifier logs exist, materialize six-perspective Web rows and run leak/root-overlap audits before training.",
        ],
        "source_artifacts": {
            "stage11397_postrun": rel(POSTRUN),
            "stage11398_decision": rel(DIAG_DECISION),
            "stage11399_feasibility": rel(FEASIBILITY),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "blocker_types": blocker_types}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
