#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8882
NAME = "stage8882_tiny_structured_probe_execution_authorization_review"
PREFLIGHT = ROOT / "runs/summaries/stage8864_native_probe_preflight_gate.json"
PLAN = ROOT / "runs/local/artifacts/stage8864_native_probe_preflight_gate/native_probe_preflight_plan.jsonl"
TELEMETRY = ROOT / "runs/summaries/stage8862_native_probe_interpretability_artifact_contract.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TINY_STRUCTURED_PROBE_EXECUTION_AUTHORIZATION_REVIEW_STAGE8882.md"
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_plan(path: Path) -> dict[str, Any]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 1:
        raise SystemExit(f"expected exactly one plan row, got {len(rows)}")
    return rows[0]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    preflight = load_json(PREFLIGHT)
    telemetry = load_json(TELEMETRY)
    plan = load_plan(PLAN)
    review_items = [
        {"item": "preflight_gate_passed", "passed": preflight.get("passed") is True},
        {"item": "telemetry_contract_passed", "passed": telemetry.get("passed") is True},
        {"item": "probe_id_is_stage8890", "passed": str(plan.get("probe_id", "")).startswith("stage8890_")},
        {"item": "execution_not_authorized_now", "passed": plan.get("execution_authorized_now") is False},
        {"item": "structured_aux_only", "passed": plan.get("mode") == "structured_policy_probe" and plan.get("loss_weights", {}).get("structured_aux_weight", 0) > 0},
        {"item": "decoder_ce_closed", "passed": plan.get("loss_weights", {}).get("decoder_ce_weight") == 0.0},
        {"item": "denoise_ce_closed", "passed": plan.get("loss_weights", {}).get("denoise_weight") == 0.0},
        {"item": "tiny_caps", "passed": plan.get("max_train_rows") <= 32 and plan.get("max_eval_rows") <= 16 and plan.get("max_strict_rows") <= 16 and plan.get("max_steps") <= 8},
        {"item": "artifact_gate_required", "passed": (plan.get("post_run_artifact_gate") or {}).get("required") is True},
        {"item": "safe_cleanup_policy", "passed": plan.get("cleanup_policy") == "safe_cleanup_checkpoints_only" and "/arxiv" in plan.get("cleanup_forbidden_paths", [])},
        {"item": "authority_closed_on_plan", "passed": not any((plan.get("authority") or {}).values())},
    ]
    failures = [item for item in review_items if not item["passed"]]
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "review_items": len(review_items),
            "review_failures": len(failures),
            "same_stage_execution_authorized": False,
            "next_stage_tiny_execution_may_be_requested": not failures,
            "model_execution_authorized_next": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "max_train_rows": plan.get("max_train_rows"),
            "max_eval_rows": plan.get("max_eval_rows"),
            "max_strict_rows": plan.get("max_strict_rows"),
            "max_steps": plan.get("max_steps"),
        },
        "review_items": review_items,
        "candidate_probe_plan": plan,
        "decision": "Review card passed for a future tiny structured-policy probe request, but this stage does not execute or authorize execution by itself." if not failures else "Review card failed; do not request execution.",
        "next_best_step": "If the user explicitly authorizes execution in a later stage, build a one-run Stage8890 execution ticket that still requires artifact-gate validation. Do not run from this stage.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "tiny_structured_probe_execution_authorization_review_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8882 Tiny Structured Probe Execution Authorization Review",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Review failures: `{len(failures)}`",
        f"Same-stage execution authorized: `{card['metrics']['same_stage_execution_authorized']}`",
        f"Future execution request may be built: `{card['metrics']['next_stage_tiny_execution_may_be_requested']}`",
        "",
        "This is a review card only. It does not run a model and does not open decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, controller merge, or promotion.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
