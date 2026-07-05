#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8884
NAME = "stage8884_no_execution_denoise_authorization_review"
SOURCES = {
    "denoise_controls": ROOT / "runs/summaries/stage8811_output_repair_denoise_controls_shortcut_gate.json",
    "verifier_targets": ROOT / "runs/summaries/stage8873_verifier_guided_repair_target_materialization_audit.json",
    "denoise_contract": ROOT / "runs/summaries/stage8731_denoise_diffusion_repair_contract_readiness.json",
    "telemetry_contract": ROOT / "runs/summaries/stage8862_native_probe_interpretability_artifact_contract.json",
}
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NO_EXECUTION_DENOISE_AUTHORIZATION_REVIEW_STAGE8884.md"
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


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cards = {name: load(path) for name, path in SOURCES.items()}
    review_items = [
        {"item": "denoise_controls_passed", "passed": cards["denoise_controls"].get("passed") is True},
        {"item": "verifier_targets_passed", "passed": cards["verifier_targets"].get("passed") is True},
        {"item": "denoise_contract_passed", "passed": cards["denoise_contract"].get("passed") is True},
        {"item": "telemetry_contract_passed", "passed": cards["telemetry_contract"].get("passed") is True},
        {"item": "denoise_ce_still_closed", "passed": cards["verifier_targets"].get("metrics", {}).get("denoise_ce_eligible_now_rows") == 0},
        {"item": "runtime_still_closed", "passed": cards["verifier_targets"].get("metrics", {}).get("runtime_verifier_execution_eligible_now_rows") == 0},
        {"item": "target_text_not_in_manifest", "passed": cards["verifier_targets"].get("metrics", {}).get("target_text_copied_to_manifest_rows") == 0},
        {"item": "shortcut_gate_clean", "passed": cards["denoise_controls"].get("metrics", {}).get("max_proxy_single", 1.0) < 0.66 and cards["denoise_controls"].get("metrics", {}).get("max_proxy_combo", 1.0) < 0.66},
    ]
    failures = [item for item in review_items if not item["passed"]]
    authorization_design = {
        "mode": "denoise_repair_probe",
        "execution_authorized_now": False,
        "future_review_only": True,
        "allowed_future_loss": "denoise_ce_only_after_separate_ticket",
        "required_before_any_denoise_ce": [
            "explicit_user_authorization",
            "one_run_ticket",
            "loss_mask_runtime_assertions",
            "target_store_resolver_readonly",
            "artifact_gate_required",
            "no_runtime_verifier_execution",
            "cleanup_checkpoint_policy",
        ],
        "forbidden_now": [
            "model_execution",
            "denoise_ce_training",
            "decoder_ce_training",
            "runtime_verifier_execution",
            "source_body_emission",
            "gemma_harness_scoring",
            "checkpoint_export",
            "promotion",
        ],
    }
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
            "denoise_ce_eligible_now_rows": 0,
            "runtime_verifier_execution_eligible_now_rows": 0,
            "same_stage_execution_authorized": False,
            "same_stage_denoise_ce_authorized": False,
            "future_no_execution_design_ready": not failures,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
        },
        "review_items": review_items,
        "authorization_design": authorization_design,
        "decision": "No-execution denoise authorization review passed. It defines prerequisites for a future ticket but opens no denoise CE/runtime authority." if not failures else "No-execution denoise authorization review failed.",
        "next_best_step": "If denoise is pursued later, build a separate one-run ticket and keep runtime verifier execution closed. Do not run from this stage.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "no_execution_denoise_authorization_review_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8884 No-Execution Denoise Authorization Review",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Review failures: `{len(failures)}`",
        "Same-stage denoise CE authorized: `False`",
        "Same-stage runtime verifier execution authorized: `False`",
        "",
        "This is review/design only. It opens no execution or training authority.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
