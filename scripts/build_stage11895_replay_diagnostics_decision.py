#!/usr/bin/env python3
"""Decision summary for rendered support learnability/replay diagnostics."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11895
NAME = "stage11895_replay_diagnostics_decision"
OUT = ART / NAME
SUMMARY = OUT / "replay_diagnostics_decision.json"

SUPPORT_ONLY = ART / "stage11891_support_only_learnability_postrun_audit/support_only_learnability_postrun_audit.json"
PROTECTED_REPLAY = ART / "stage11894_protected_replay_postrun_audit/protected_replay_postrun_audit.json"
RENDERED_PACKAGE = ART / "stage11884_rendered_source_heldout_support_probe_package/rendered_source_heldout_support_probe_package.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def score(summary: dict[str, Any], key: str) -> str:
    item = summary["results"][key]
    return f"{item['correct']}/{item['rows']}"


def main() -> None:
    support_only = load_json(SUPPORT_ONLY)
    protected_replay = load_json(PROTECTED_REPLAY)
    rendered = load_json(RENDERED_PACKAGE)
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "mechanism_proven_build_disjoint_replay_or_transition_record_pipeline_next",
        "findings": {
            "stage11884_rendering_fix": {
                "decision": rendered.get("decision"),
                "rendered_support_rows": rendered.get("row_counts", {}).get("rendered_support_rows"),
                "pre_options_target_value_leaks": rendered.get("renderer_audit", {}).get("pre_options_target_value_leak_count"),
            },
            "stage11891_support_only": {
                "decision": support_only.get("decision"),
                "rendered_support_train": score(support_only, "rendered_added_support_train"),
                "filtered_strict": score(support_only, "filtered_strict"),
                "old_canary_strict": score(support_only, "old_canary_strict"),
                "residual_bank": score(support_only, "residual_bank"),
                "interpretation": "Rendered support is learnable, but without replay it catastrophically overwrites protected scorer geometry.",
            },
            "stage11894_protected_replay": {
                "decision": protected_replay.get("decision"),
                "rendered_support_train": score(protected_replay, "rendered_added_support_train"),
                "filtered_strict": score(protected_replay, "filtered_strict"),
                "old_canary_strict": score(protected_replay, "old_canary_strict"),
                "filtered_validation": score(protected_replay, "filtered_validation"),
                "old_canary_validation": score(protected_replay, "old_canary_validation"),
                "residual_bank": score(protected_replay, "residual_bank"),
                "source_heldout_smoke": score(protected_replay, "verifier_grounded_source_heldout_smoke"),
                "interpretation": "Protected replay preserves gates and improves residual to 9/10 while partially fitting support, but is non-promotable due protected train/eval overlap.",
            },
        },
        "selected_frontier_status": {
            "selected_frontier_remains": "stage11507 + encoder_option_retrieval_evidence_judgment_head",
            "stage11893_not_promotable": True,
            "reason": "trained on protected replay copies; source-heldout smoke also remains weak",
        },
        "next_required_work": [
            "Compile rendered support roots into verified_transition_record_v1 objects so future training targets action/evidence/verifier transitions, not only answer labels.",
            "Build disjoint protected-analogue replay rows to replace direct protected replay before any promotable guarded run.",
            "Use the protected-replay recipe as a mechanism template: support rows preservation_exempt=true, analogue replay preservation_exempt=false, high bounded aux, no decoder CE.",
            "Do not claim source-heldout breadth from the current support rows; C/C++ still includes repeated google_benchmark family roots.",
        ],
        "source_artifacts": {
            "support_only_audit": rel(SUPPORT_ONLY),
            "protected_replay_audit": rel(PROTECTED_REPLAY),
            "rendered_package": rel(RENDERED_PACKAGE),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "selected_frontier_remains": artifact["selected_frontier_status"]["selected_frontier_remains"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
