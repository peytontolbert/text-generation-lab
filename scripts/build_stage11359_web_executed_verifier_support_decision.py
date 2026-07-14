#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11359
NAME = "stage11359_web_executed_verifier_support_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_executed_verifier_support_decision.json"
BASELINE = ART / "stage11355_web_executed_verifier_current_runtime_score/web_executed_verifier_current_runtime_score.json"
POST = ART / "stage11358_web_executed_verifier_support_postrun_audit/web_executed_verifier_support_postrun_audit.json"
RUNTIME = ART / "stage11357_web_executed_verifier_support_probe/runtime_model/runtime_model_bundle.json"
FRONTIER = ART / "stage11200_role_focused_residual_probe/runtime_model/runtime_model_bundle.json"


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path):
    return json.loads(path.read_text())


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def metric(card, key):
    return card.get("product_metrics", {}).get(key, {})


def main() -> None:
    base = read_json(BASELINE)
    post = read_json(POST)
    base_exec = metric(base, "web_executed_verifier_train_support")
    post_exec = metric(post, "web_executed_verifier_train_support")
    post_strict = metric(post, "canary_strict")
    post_val = metric(post, "canary_validation")
    post_snippet = metric(post, "web_source_snippet_support")
    improved = (post_exec.get("correct") or 0) > (base_exec.get("correct") or 0)
    canary = post_strict.get("correct") == 22 and post_val.get("correct", 0) >= 20
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "decision": "accept_stage11357_as_diagnostic_support_runtime_keep_stage11200_frontier" if improved and canary else "reject_stage11357_keep_stage11200_frontier",
        "frontier_runtime_kept": rel(FRONTIER),
        "diagnostic_support_runtime": rel(RUNTIME) if improved and canary else None,
        "metrics": {
            "baseline_web_executed_verifier": base_exec,
            "stage11357_web_executed_verifier": post_exec,
            "stage11357_canary_strict": post_strict,
            "stage11357_canary_validation": post_val,
            "stage11357_web_source_snippet_support": post_snippet,
        },
        "gate": {
            "executed_verifier_support_improved": improved,
            "canary_preserved": canary,
            "old_web_source_snippet_still_flat": post_snippet.get("correct") == 7,
            "heldout_promotion_allowed": False,
        },
        "promotion_status": {
            "standalone_frontier_replaced": False,
            "why": "Stage11357 improves executed-verifier train-support rows only. It has no disjoint heldout improvement and old Web source-snippet rows remain flat.",
        },
        "source_artifacts": {"baseline": rel(BASELINE), "postrun_audit": rel(POST), "runtime": rel(RUNTIME), "frontier": rel(FRONTIER)},
        "recommended_next_action": "Build disjoint Web heldout roots from unused Stage11346 candidates, preferably with executed verifier outputs, then compare Stage11200 and diagnostic runtimes without training on those roots.",
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
