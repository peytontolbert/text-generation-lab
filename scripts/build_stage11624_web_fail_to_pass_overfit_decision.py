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
STAGE = 11624
NAME = "stage11624_web_fail_to_pass_overfit_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_fail_to_pass_overfit_decision.json"

REQUEST = ART / "stage11623_web_fail_to_pass_head_overfit_request/web_fail_to_pass_head_overfit_request.json"
PROBE_RESULT = ART / "stage11623_web_fail_to_pass_head_overfit/bounded_decoder_probe/execution_result.json"
GEOMETRY_AUDIT = ART / "stage11622_web_fail_to_pass_repaired_geometry_audit/web_fail_to_pass_repaired_geometry_audit.json"
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
    geometry = load_json(GEOMETRY_AUDIT)
    execution = probe.get("execution_result") if isinstance(probe.get("execution_result"), dict) else probe
    eval_card = execution["bounded_choice_eval"]["eval"]
    correct = int(eval_card.get("constrained_choice_correct") or 0)
    rows = int(eval_card.get("rows") or 0)
    selected_baseline = geometry["compact"]["stage11507_selected"]["encoder_option_retrieval_evidence_judgment_head"]
    rejected_web_head_baseline = geometry["compact"]["stage11617_rejected"]["encoder_option_retrieval_web_task_candidate_head"]
    gates = {
        "same_row_eval_measured": rows == 36,
        "improves_over_selected_retrieval_on_repaired_rows": correct > int(selected_baseline),
        "improves_over_stage11617_web_head_on_repaired_rows": correct > int(rejected_web_head_baseline),
        "does_not_fully_fit_repaired_rows": correct < rows,
        "non_promotable_by_design": request.get("objective_settings", {}).get("bounded_choice_train_head_only") is True,
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "diagnostic_success_partial_head_capacity_but_no_promotion",
        "selected_frontier_remains": {
            "runtime": rel(SELECTED_RUNTIME),
            "scorer": "encoder_option_retrieval_evidence_judgment_head",
        },
        "stage11623_same_row_eval": {
            "correct": correct,
            "rows": rows,
            "accuracy": eval_card.get("constrained_choice_top1_accuracy"),
            "runtime": "runs/local/artifacts/stage11623_web_fail_to_pass_head_overfit/runtime_model/runtime_model_bundle.json",
            "weights_sha256": execution["runtime_model_bundle"]["weights_sha256"],
        },
        "baselines_on_repaired_rows": {
            "stage11507_selected_evidence_judgment_head": selected_baseline,
            "stage11617_rejected_web_task_candidate_head": rejected_web_head_baseline,
            "stage11507_decoder_first_step": geometry["compact"]["stage11507_selected"]["decoder_first_step"],
        },
        "gates": gates,
        "interpretation": [
            "Repairing row geometry removed the all-task abstain collapse and made the controlled rows partially learnable.",
            "Head-only training on the exact same 36 rows improves from 6/36 to 24/36, so the Web task-candidate head has some capacity for this geometry.",
            "Because it cannot fully fit a tiny same-row diagnostic, the next promotable run should not reuse this head/objective unchanged.",
            "This is not a frontier improvement and does not affect the selected Stage11507 runtime.",
        ],
        "next_actions": [
            "Materialize more diverse controlled Web FAIL_TO_PASS roots, including Llama, before any promotable web run.",
            "Improve the Web task-candidate head/objective so it can fit repaired controlled rows near-perfectly in head-only mode before combining with preservation.",
            "Consider task-specific heads or listwise same-root candidate loss for verifier/evidence/minimal-fix instead of one shared Web task head.",
            "Keep Stage11507 as selected frontier until a run preserves residual 7/10 and improves Web heldout above 35/66.",
        ],
        "source_artifacts": {
            "request": rel(REQUEST),
            "probe_result": rel(PROBE_RESULT),
            "geometry_audit": rel(GEOMETRY_AUDIT),
            "selected_runtime": rel(SELECTED_RUNTIME),
        },
        "outputs": {"summary": rel(SUMMARY)},
        "claim_boundary": [
            "Stage11623 is an overfit diagnostic only.",
            "The repaired controlled rows remain train-support only, not strict eval.",
            "No model frontier promotion is authorized by this stage.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "same_row_eval": summary["stage11623_same_row_eval"], "baselines": summary["baselines_on_repaired_rows"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
