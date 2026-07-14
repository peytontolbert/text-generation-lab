#!/usr/bin/env python3
"""Summarize current source-heldout failure support supply after new audits."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11752
NAME = "stage11752_source_heldout_support_supply_status"
OUT = ART / NAME
SUMMARY = OUT / "source_heldout_support_supply_status.json"

PYTHON = ART / "stage11750_python_verifier_support_combined_audit/python_verifier_support_combined_audit.json"
RUST_EVIDENCE = ART / "stage11751_rust_existing_evidence_support_audit/rust_existing_evidence_support_audit.json"
PYTHON_FEAS = ART / "stage11747_python_verifier_feasibility_expansion/python_verifier_feasibility_expansion.json"
REPAIRED_FEAS = ART / "stage11748_python_repaired_verifier_feasibility/python_repaired_verifier_feasibility.json"
REQUEST = ART / "stage11742_source_heldout_failure_support_request/source_heldout_failure_support_request.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    python = read_json(PYTHON)
    rust_evidence = read_json(RUST_EVIDENCE)
    python_feas = read_json(PYTHON_FEAS)
    repaired_feas = read_json(REPAIRED_FEAS)
    request = read_json(REQUEST)

    python_ready = int(python.get("admitted_root_count", 0))
    rust_evidence_ready = int(rust_evidence.get("admitted_root_count", 0))
    status = {
        "python_verifier_support": {
            "ready_roots": python_ready,
            "ready_rows": python.get("admitted_rows", 0),
            "required_support_roots": 12,
            "remaining_support_roots": max(0, 12 - python_ready),
            "strict_analogue_roots_ready": 0,
            "required_strict_analogue_roots": 4,
            "materialized_rows": python.get("outputs", {}).get("combined_rows"),
        },
        "rust_verifier_support": {
            "ready_roots": 0,
            "required_support_roots": 12,
            "remaining_support_roots": 12,
            "strict_analogue_roots_ready": 0,
            "required_strict_analogue_roots": 4,
            "note": "No true verifier_outcome selected-inline-test Rust support roots were admitted in this turn.",
        },
        "rust_evidence_support_only": {
            "ready_roots": rust_evidence_ready,
            "ready_rows": rust_evidence.get("admitted_rows", 0),
            "admitted_rows": rust_evidence.get("outputs", {}).get("admitted_rows"),
            "claim_boundary": "Useful for evidence-role support, not counted toward Rust verifier_outcome quota.",
        },
        "cpp_abstain_attractor_support": {
            "ready_roots": 0,
            "required_support_roots": 16,
            "remaining_support_roots": 16,
            "strict_analogue_roots_ready": 0,
            "required_strict_analogue_roots": 4,
        },
    }
    training_probe_ready = (
        status["python_verifier_support"]["ready_roots"] >= 12
        and status["rust_verifier_support"]["ready_roots"] >= 12
        and status["cpp_abstain_attractor_support"]["ready_roots"] >= 16
    )
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "support_supply_improved_but_training_probe_not_ready",
        "passed": True,
        "training_probe_ready": training_probe_ready,
        "support_status": status,
        "new_findings": [
            "Python verifier lane now has two clean admitted train-support roots.",
            "Stage11747 found no new direct passing Python roots, but repaired probing recovered model-stack as materializable.",
            "Tokenizers Python bindings passed after cwd repair but remain diagnostic/quarantined due tokenizers overlap.",
            "Existing Rust rows provide three roots of evidence-candidate support, but not true selected-inline-test verifier_outcome support.",
        ],
        "next_actions": [
            "Find or repair at least 10 more clean Python verifier support roots.",
            "Materialize true Rust verifier_outcome selected-inline-test roots rather than evidence-only rows.",
            "Run C/C++ build/verifier probes for abstain-attractor support roots.",
            "Do not train a source-heldout successor probe until support quotas or a deliberately smaller diagnostic gate is declared.",
        ],
        "claim_boundary": [
            "No model frontier score changed in this support-supply stage.",
            "No Gemma comparison is implied.",
            "This is dataset/admission progress toward source-heldout failure repair.",
        ],
        "source_artifacts": {
            "request": rel(REQUEST),
            "python_combined_audit": rel(PYTHON),
            "rust_evidence_audit": rel(RUST_EVIDENCE),
            "python_feasibility_expansion": rel(PYTHON_FEAS),
            "repaired_python_feasibility": rel(REPAIRED_FEAS),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": artifact["decision"],
                "training_probe_ready": training_probe_ready,
                "python_ready_roots": python_ready,
                "rust_evidence_support_only_roots": rust_evidence_ready,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
