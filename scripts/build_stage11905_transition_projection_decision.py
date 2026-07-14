#!/usr/bin/env python3
"""Summarize transition-projection diagnostics and choose the next safe path."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11905
NAME = "stage11905_transition_projection_decision"
OUT = ART / NAME
SUMMARY = OUT / "transition_projection_decision.json"

BASELINE = ART / "stage11898_transition_projection_baseline_audit/transition_projection_baseline_audit.json"
SUPPORT_ONLY = ART / "stage11901_transition_projection_support_only_postrun_audit/transition_projection_support_only_postrun_audit.json"
PROTECTED_REPLAY = ART / "stage11904_transition_projection_protected_replay_postrun_audit/transition_projection_protected_replay_postrun_audit.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def metric(summary: dict[str, Any], runtime_name: str, rowset: str) -> dict[str, Any]:
    item = summary["results"][runtime_name][rowset]
    return {"correct": item.get("correct"), "rows": item.get("rows"), "accuracy": item.get("accuracy")}


def main() -> None:
    baseline = read_json(BASELINE)
    support_only = read_json(SUPPORT_ONLY)
    protected = read_json(PROTECTED_REPLAY)
    selected = "stage11507_selected_frontier"
    support_runtime = "stage11900_transition_projection_support_only"
    protected_runtime = "stage11903_transition_projection_protected_replay"
    facts = {
        "selected_frontier_projection": metric(baseline, selected, "all_transition_projection_rows"),
        "support_only_projection": metric(support_only, support_runtime, "all_transition_projection_rows"),
        "protected_replay_projection": metric(protected, protected_runtime, "all_transition_projection_rows"),
        "protected_replay_filtered_strict": metric(protected, protected_runtime, "protected::filtered_strict"),
        "protected_replay_old_canary_strict": metric(protected, protected_runtime, "protected::old_canary_strict"),
        "protected_replay_filtered_validation": metric(protected, protected_runtime, "protected::filtered_validation"),
        "protected_replay_old_canary_validation": metric(protected, protected_runtime, "protected::old_canary_validation"),
        "protected_replay_residual": metric(protected, protected_runtime, "protected::residual_bank"),
        "protected_replay_smoke": metric(protected, protected_runtime, "protected::verifier_grounded_source_heldout_smoke"),
    }
    next_requirements = {
        "replace_protected_replay": True,
        "disjoint_analogue_replay_required": True,
        "source_heldout_smoke_must_not_regress": True,
        "minimum_projection_fit_gate": ">= 320/640",
        "protected_gate_targets": {
            "filtered_strict": "22/22",
            "old_canary_strict": "23/23",
            "filtered_validation": ">=20/22",
            "old_canary_validation": ">=21/23",
            "residual_bank": ">=7/10",
            "verifier_grounded_source_heldout_smoke": ">=6/12",
        },
    }
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "mechanism_proven_but_nonpromotable_build_disjoint_analogue_replay_next",
        "facts": facts,
        "interpretation": [
            "Stage11897 transition projections expose a real missing interface: selected frontier scores 115/640.",
            "Stage11900 support-only training proves learnability at 428/640 but destroys protected gates.",
            "Stage11903 protected replay preserves strict/canary/residual and reaches 341/640, proving coexistence is possible under replay/KL.",
            "Stage11903 is not promotable because protected rows were trained and source-heldout smoke regressed from 6/12 to 3/12.",
        ],
        "next_stage_requirements": next_requirements,
        "source_artifacts": {
            "baseline": rel(BASELINE),
            "support_only": rel(SUPPORT_ONLY),
            "protected_replay": rel(PROTECTED_REPLAY),
        },
        "outputs": {"summary": rel(SUMMARY)},
        "claim_boundary": [
            "Current selected frontier remains Stage11507 for promotable claims.",
            "Stage11903 is a mechanism proof only.",
            "The next valid promotion attempt must use disjoint analogue replay or heldout-safe transition supervision, not protected replay.",
        ],
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "facts": facts}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
