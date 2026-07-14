#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11352
NAME = "stage11352_web_static_verifier_support_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_static_verifier_support_decision.json"
BASELINE = ART / "stage11348_web_static_verifier_current_runtime_score/web_static_verifier_current_runtime_score.json"
POST = ART / "stage11351_web_static_verifier_support_postrun_audit/web_static_verifier_support_postrun_audit.json"
STAGE11350_RUNTIME = ART / "stage11350_web_static_verifier_support_probe/runtime_model/runtime_model_bundle.json"
FRONTIER_RUNTIME = ART / "stage11200_role_focused_residual_probe/runtime_model/runtime_model_bundle.json"


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path):
    return json.loads(path.read_text())


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def metric(card: dict, key: str) -> dict:
    return card.get("product_metrics", {}).get(key, {})


def main() -> None:
    base = read_json(BASELINE)
    post = read_json(POST)
    base_web = metric(base, "web_static_verifier_train_support")
    post_web = metric(post, "web_static_verifier_train_support")
    post_strict = metric(post, "canary_strict")
    post_val = metric(post, "canary_validation")
    post_snippet = metric(post, "web_source_snippet_support")
    improved = (post_web.get("correct") or 0) > (base_web.get("correct") or 0)
    canary_preserved = post_strict.get("correct") == 22 and post_val.get("correct", 0) >= 20
    old_web_not_moved = post_snippet.get("correct") == 7
    decision = "accept_stage11350_as_diagnostic_support_runtime_keep_stage11200_frontier" if improved and canary_preserved else "reject_stage11350_keep_stage11200_frontier"
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "decision": decision,
        "frontier_runtime_kept": rel(FRONTIER_RUNTIME),
        "diagnostic_support_runtime": rel(STAGE11350_RUNTIME) if improved and canary_preserved else None,
        "promotion_status": {
            "standalone_frontier_replaced": False,
            "why": "Stage11350 improves only train-support Web static-verifier rows. It has no fresh heldout Web strict improvement and older Web source-snippet support remains 7/21.",
        },
        "metrics": {
            "baseline_web_static_verifier": base_web,
            "stage11350_web_static_verifier": post_web,
            "stage11350_canary_strict": post_strict,
            "stage11350_canary_validation": post_val,
            "stage11350_web_source_snippet_support": post_snippet,
        },
        "gate": {
            "support_slice_improved": improved,
            "canary_preserved": canary_preserved,
            "old_web_source_snippet_still_flat": old_web_not_moved,
            "heldout_promotion_allowed": False,
        },
        "source_artifacts": {
            "baseline": rel(BASELINE),
            "postrun_audit": rel(POST),
            "stage11350_runtime": rel(STAGE11350_RUNTIME),
            "stage11200_frontier_runtime": rel(FRONTIER_RUNTIME),
        },
        "recommended_next_action": "Execute or recover verifier outputs for Stage11347 roots, then create a disjoint Web heldout slice. Do not promote Stage11350 as the frontier without heldout movement.",
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
