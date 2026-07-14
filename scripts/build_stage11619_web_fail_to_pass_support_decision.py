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
STAGE = 11619
NAME = "stage11619_web_fail_to_pass_support_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_fail_to_pass_support_decision.json"

AUDIT = ART / "stage11618_web_fail_to_pass_support_postrun_audit/web_fail_to_pass_support_postrun_audit.json"
REQUEST = ART / "stage11617_web_fail_to_pass_support_probe_request/web_fail_to_pass_support_probe_request.json"
SELECTED_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compact(results: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, metric in results.items():
        out[name] = f"{metric.get('correct')}/{metric.get('rows')}"
    return out


def main() -> None:
    audit = load_json(AUDIT)
    request = load_json(REQUEST)
    results = audit["results"]
    gates = audit["gates"]
    passed_promotion = all(audit.get("promotion_gates", {}).values())
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "reject_stage11617_keep_stage11507",
        "promotion_passed": passed_promotion,
        "selected_frontier_remains": {
            "runtime": rel(SELECTED_RUNTIME),
            "scorer": "encoder_option_retrieval_evidence_judgment_head",
            "reason": "Stage11617 regressed residual and Web heldout under the Web task-candidate head.",
        },
        "stage11617_result": {
            "runtime": audit["runtime"],
            "scorer": audit["scorer"],
            "compact": compact(results),
            "failed_gates": [name for name, passed in gates.items() if not passed],
            "objective_settings": request.get("objective_settings"),
        },
        "interpretation": [
            "Controlled FAIL_TO_PASS support rows executed and were anti-cheat admitted, but the Web task-candidate head did not learn them under this objective.",
            "The run preserved filtered and old canary gates, but residual dropped from the selected frontier 7/10 to 6/10.",
            "Web heldout dropped from the selected frontier 35/66 to 29/66, so this is not Web generalization progress.",
            "Controlled support scored 0/36 under the same Web task-candidate scorer, which indicates a scorer/objective/row-geometry mismatch rather than useful absorption of the new data.",
        ],
        "next_actions": [
            "Do not run another broad full-model Web task-head probe on the same 36 rows.",
            "Audit why the Web task-candidate head scores controlled FAIL_TO_PASS rows at 0/36 despite full coverage.",
            "Before more training, add a row-geometry audit that checks semantic candidate features for each task family and verifies the gold option is the highest-scoring candidate under the initialized Stage11507 feature space only when expected.",
            "If continuing this lane, try a tiny head-only overfit diagnostic on these 36 rows with no promotion path, solely to verify the head can represent the controlled rows; do not touch the selected frontier.",
            "Materialize more diverse Web FAIL_TO_PASS roots before another promotable Web run; six OpenHands roots are not enough and Llama remains absent from controlled mutation support.",
        ],
        "claim_boundary": [
            "Stage11617 is a rejected diagnostic.",
            "The selected frontier remains Stage11507.",
            "Controlled mutation rows remain train-support material only, not headline eval.",
        ],
        "source_artifacts": {
            "request": rel(REQUEST),
            "postrun_audit": rel(AUDIT),
            "stage11617_runtime": audit["runtime"],
            "selected_runtime": rel(SELECTED_RUNTIME),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "stage11617_result": summary["stage11617_result"], "next_actions": summary["next_actions"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
