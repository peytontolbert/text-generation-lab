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
STAGE = 11626
NAME = "stage11626_web_fail_to_pass_stronger_overfit_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_fail_to_pass_stronger_overfit_decision.json"

REQUEST = ART / "stage11625_web_fail_to_pass_stronger_head_overfit_request/web_fail_to_pass_stronger_head_overfit_request.json"
PROBE_RESULT = ART / "stage11625_web_fail_to_pass_stronger_head_overfit/bounded_decoder_probe/execution_result.json"
PREV_DECISION = ART / "stage11624_web_fail_to_pass_overfit_decision/web_fail_to_pass_overfit_decision.json"
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


def main() -> None:
    request = load_json(REQUEST)
    probe = load_json(PROBE_RESULT)
    previous = load_json(PREV_DECISION)
    execution = probe.get("execution_result") if isinstance(probe.get("execution_result"), dict) else probe
    eval_card = execution["bounded_choice_eval"]["eval"]
    correct = int(eval_card.get("constrained_choice_correct") or 0)
    rows = int(eval_card.get("rows") or 0)
    gates = {
        "same_row_eval_measured": rows == 36,
        "fully_fits_repaired_rows": correct == rows == 36,
        "improves_over_stage11623": correct > int(previous["stage11623_same_row_eval"]["correct"]),
        "head_only_non_promotable": request.get("objective_settings", {}).get("bounded_choice_train_head_only") is True,
        "strict_eval_disabled": request.get("gates", {}).get("strict_disabled") is True,
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "head_capacity_confirmed_no_frontier_promotion",
        "selected_frontier_remains": {
            "runtime": rel(SELECTED_RUNTIME),
            "scorer": "encoder_option_retrieval_evidence_judgment_head",
            "reason": "Stage11625 is a same-row head-only overfit diagnostic, not a heldout-preserving frontier run.",
        },
        "stage11625_same_row_eval": {
            "correct": correct,
            "rows": rows,
            "accuracy": eval_card.get("constrained_choice_top1_accuracy"),
            "runtime": "runs/local/artifacts/stage11625_web_fail_to_pass_stronger_head_overfit/runtime_model/runtime_model_bundle.json",
            "weights_sha256": execution["runtime_model_bundle"]["weights_sha256"],
        },
        "comparison": {
            "stage11507_selected_repaired_rows": "6/36",
            "stage11623_head_only_256_steps": f"{previous['stage11623_same_row_eval']['correct']}/{previous['stage11623_same_row_eval']['rows']}",
            "stage11625_head_only_1024_steps": f"{correct}/{rows}",
        },
        "gates": gates,
        "interpretation": [
            "The repaired controlled FAIL_TO_PASS row geometry is representable by the Web task-candidate head.",
            "Stage11623 underfit at 24/36; Stage11625 reaches 36/36 by increasing optimization strength.",
            "This supports using repaired geometry and stronger head optimization in a future guarded package, but only with preservation and heldout gates.",
            "It does not prove Web heldout generalization and does not change the selected frontier.",
        ],
        "next_actions": [
            "Build a guarded Web package using repaired FAIL_TO_PASS geometry plus existing heldout/protected sets, but do not use same-row overfit settings directly.",
            "Materialize additional Llama controlled FAIL_TO_PASS roots before a serious promotable Web run; current repaired roots are OpenHands-only.",
            "If running a guarded probe before more materialization, use lower LR plus preservation KL and audit Web heldout, residual, filtered strict, and old canary.",
            "Keep Stage11507 selected until a run preserves residual 7/10 and improves Web heldout above 35/66.",
        ],
        "source_artifacts": {
            "request": rel(REQUEST),
            "probe_result": rel(PROBE_RESULT),
            "previous_decision": rel(PREV_DECISION),
            "selected_runtime": rel(SELECTED_RUNTIME),
        },
        "outputs": {"summary": rel(SUMMARY)},
        "claim_boundary": [
            "Stage11625 is non-promotable by design.",
            "The exact repaired rows are used for both train and eval.",
            "No broad Web, harness, or Gemma comparison claim is supported by this diagnostic.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "same_row_eval": summary["stage11625_same_row_eval"], "comparison": summary["comparison"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
