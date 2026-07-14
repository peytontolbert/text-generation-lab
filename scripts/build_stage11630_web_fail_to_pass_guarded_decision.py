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
STAGE = 11630
NAME = "stage11630_web_fail_to_pass_guarded_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_fail_to_pass_guarded_decision.json"

REQUEST = ART / "stage11628_web_fail_to_pass_guarded_probe_request/web_fail_to_pass_guarded_probe_request.json"
AUDIT = ART / "stage11629_web_fail_to_pass_guarded_postrun_audit/web_fail_to_pass_guarded_postrun_audit.json"
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
    return {name: f"{metric.get('correct')}/{metric.get('rows')}" for name, metric in results.items()}


def main() -> None:
    request = load_json(REQUEST)
    audit = load_json(AUDIT)
    compact_results = compact(audit["results"])
    failed_gates = [name for name, passed in audit["gates"].items() if not passed]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "reject_stage11628_keep_stage11507",
        "selected_frontier_remains": {
            "runtime": rel(SELECTED_RUNTIME),
            "scorer": "encoder_option_retrieval_evidence_judgment_head",
            "reason": "Stage11628 did not improve Web heldout and regressed residual below 7/10.",
        },
        "stage11628_result": {
            "runtime": audit["runtime"],
            "scorer": audit["scorer"],
            "compact": compact_results,
            "failed_gates": failed_gates,
            "objective_settings": request.get("objective_settings"),
        },
        "interpretation": [
            "The repaired controlled FAIL_TO_PASS rows are partially learned: controlled support reaches 18/48.",
            "The learning does not transfer to Web heldout: 32/66 is below the selected Stage11507 baseline of 35/66.",
            "The run preserves canary strict/validation gates but regresses residual from 7/10 to 6/10.",
            "This means the current shared Web task-candidate head/full-model objective is not a promotable Web path yet.",
        ],
        "next_actions": [
            "Do not rerun the same full-model Web task-head recipe on this package.",
            "Try staged/frozen training: first fit the Web head on repaired support, then freeze encoder and audit heldout, or add task-specific heads.",
            "Add more Llama/OpenHands controlled roots before attempting another promotable Web heldout run.",
            "Keep Stage11507 selected until residual stays >=7/10 and Web heldout exceeds 35/66.",
        ],
        "source_artifacts": {
            "request": rel(REQUEST),
            "audit": rel(AUDIT),
            "selected_runtime": rel(SELECTED_RUNTIME),
        },
        "outputs": {"summary": rel(SUMMARY)},
        "claim_boundary": [
            "Stage11628 is rejected diagnostic/probe output.",
            "Controlled mutation rows remain train-support only.",
            "No Web or broad maintainer claim is upgraded.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "stage11628_result": summary["stage11628_result"], "next_actions": summary["next_actions"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
