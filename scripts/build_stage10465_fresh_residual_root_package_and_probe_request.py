#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10465
NAME = "stage10465_fresh_residual_root_package_and_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "fresh_residual_root_package_and_probe_request.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PROMOTION_GATE = ROOT / "runs/local/artifacts/stage10461_reviewed_v27_residual_promotion_gate/reviewed_v27_residual_promotion_gate.json"
EXPANSION_REQUEST = ROOT / "runs/local/artifacts/stage10462_fresh_residual_root_expansion_request/fresh_residual_root_expansion_request.json"
PYTHON_INVENTORY = ROOT / "runs/local/artifacts/stage10463_python_verifier_fresh_root_inventory/python_verifier_fresh_root_inventory.json"
RUST_INVENTORY = ROOT / "runs/local/artifacts/stage10464_rust_citation_fresh_root_inventory/rust_citation_fresh_root_inventory.json"
LIVE_BASELINE = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
LIVE_HEADLINE = ROOT / "runs/local/artifacts/stage10424_reviewed_multilingual_v27_comparison_audit/reviewed_multilingual_v27_comparison_audit.json"
DIAGNOSTIC_REQUEST = ROOT / "runs/local/artifacts/stage10459_same_surface_contrast_probe_request/same_surface_contrast_probe_request.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    gate = load_json(PROMOTION_GATE)
    expansion = load_json(EXPANSION_REQUEST)
    python_inventory = load_json(PYTHON_INVENTORY)
    rust_inventory = load_json(RUST_INVENTORY)
    baseline = load_json(LIVE_BASELINE)
    headline = load_json(LIVE_HEADLINE)
    diagnostic = load_json(DIAGNOSTIC_REQUEST)

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "fresh_residual_root_package_required_before_next_promotable_probe",
        "claim_scope": [
            "Convert the residual plateau into a root-disjoint expansion plan instead of another same-surface finetune loop.",
            "Preserve the honest reviewed v2.7 headline while preparing the next promotable support package for the two surviving residual skills.",
        ],
        "source_artifacts": {
            "live_strict_baseline": display(LIVE_BASELINE),
            "live_same_manifest_headline": display(LIVE_HEADLINE),
            "residual_promotion_gate": display(PROMOTION_GATE),
            "fresh_root_expansion_request": display(EXPANSION_REQUEST),
            "python_inventory": display(PYTHON_INVENTORY),
            "rust_inventory": display(RUST_INVENTORY),
            "same_surface_diagnostic_request": display(DIAGNOSTIC_REQUEST),
        },
        "current_live_baseline": {
            "strict_accuracy": baseline["constrained_choice_top1_accuracy"],
            "strict_rows": baseline["rows"],
            "same_manifest_headline": headline.get("current_claim", {}),
        },
        "residual_targets": {
            "python_verifier_outcome": python_inventory["current_live_residual"],
            "rust_evidence_citation": rust_inventory["current_live_residual"],
        },
        "next_package_contract": {
            "minimum_fresh_roots": {
                "python_verifier_outcome": expansion["root_requirements"]["python_verifier_outcome"]["minimum_new_roots"],
                "rust_evidence_citation": expansion["root_requirements"]["rust_evidence_citation"]["minimum_new_roots"],
            },
            "must_be_root_disjoint": True,
            "must_exclude_same_surface_from_promotable_support": True,
            "same_surface_tokenizers_rows": {
                "allowed_role": "diagnostic_only",
                "source_request": display(DIAGNOSTIC_REQUEST),
            },
            "must_attach_metadata": [
                "repo_id",
                "repo_family",
                "root_id",
                "language_family",
                "task_type",
                "selected_test_anchor_present",
                "verifier_anchor_present",
                "same_surface_diagnostic_support",
                "strict_eval_eligible",
            ],
        },
        "probe_request_requirements": [
            "initialize from the live stage10422 runtime model unless a newer promotable baseline exists",
            "separate promotable fresh-root support from any same-surface diagnostic support",
            "evaluate against the repaired v2.7 strict overlay with the same scorer policy used by the live headline",
            "attach a fresh-root holdout audit for both residual skills",
            "report row-level regressions relative to the live 22/24 baseline",
            "report whether either residual moved off its current wrong semantic attractor",
        ],
        "promotion_gate_requirements": gate["required_for_future_promotion"],
        "diagnostic_status": {
            "same_surface_request_exists": True,
            "same_surface_request_decision": diagnostic["decision"],
            "promotion_use": "forbidden",
        },
        "recommended_next_stage_names": [
            "stage10466_python_verifier_fresh_root_builder",
            "stage10467_rust_citation_fresh_root_builder",
            "stage10468_fresh_residual_root_support_package",
            "stage10469_fresh_residual_root_probe_request",
            "stage10470_fresh_residual_root_probe_audit",
        ],
    }

    write_json(REQUEST_JSON, request)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": request["decision"],
            "request": display(REQUEST_JSON),
        },
    )
    print(json.dumps(request, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
