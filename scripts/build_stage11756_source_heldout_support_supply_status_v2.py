#!/usr/bin/env python3
"""Refresh source-heldout failure support supply after C/C++ admission."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11756
NAME = "stage11756_source_heldout_support_supply_status_v2"
OUT = ART / NAME
SUMMARY = OUT / "source_heldout_support_supply_status_v2.json"

PYTHON = ART / "stage11750_python_verifier_support_combined_audit/python_verifier_support_combined_audit.json"
RUST_EVIDENCE = ART / "stage11751_rust_existing_evidence_support_audit/rust_existing_evidence_support_audit.json"
CPP = ART / "stage11755_cpp_abstain_support_admission_audit/cpp_abstain_support_admission_audit.json"
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
    cpp = read_json(CPP)

    python_roots = int(python.get("admitted_root_count", 0))
    cpp_roots = int(cpp.get("admitted_root_count", 0))
    rust_evidence_roots = int(rust_evidence.get("admitted_root_count", 0))

    support_status = {
        "python_verifier_support": {
            "ready_roots": python_roots,
            "ready_rows": python.get("admitted_rows", 0),
            "required_support_roots": 12,
            "remaining_support_roots": max(0, 12 - python_roots),
            "strict_analogue_roots_ready": 0,
            "required_strict_analogue_roots": 4,
            "materialized_rows": python.get("outputs", {}).get("combined_rows"),
        },
        "cpp_abstain_attractor_support": {
            "ready_roots": cpp_roots,
            "ready_rows": cpp.get("admitted_rows", 0),
            "required_support_roots": 16,
            "remaining_support_roots": max(0, 16 - cpp_roots),
            "strict_analogue_roots_ready": 0,
            "required_strict_analogue_roots": 4,
            "materialized_rows": cpp.get("outputs", {}).get("admitted_rows"),
        },
        "rust_verifier_support": {
            "ready_roots": 0,
            "required_support_roots": 12,
            "remaining_support_roots": 12,
            "strict_analogue_roots_ready": 0,
            "required_strict_analogue_roots": 4,
            "note": "No true verifier_outcome selected-inline-test Rust support roots are admitted yet.",
        },
        "rust_evidence_support_only": {
            "ready_roots": rust_evidence_roots,
            "ready_rows": rust_evidence.get("admitted_rows", 0),
            "materialized_rows": rust_evidence.get("outputs", {}).get("admitted_rows"),
            "claim_boundary": "Useful for evidence-role support, not counted toward Rust verifier_outcome quota.",
        },
    }
    training_probe_ready = (
        python_roots >= 12
        and cpp_roots >= 16
        and support_status["rust_verifier_support"]["ready_roots"] >= 12
    )
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "support_supply_improved_but_training_probe_not_ready",
        "passed": True,
        "training_probe_ready": training_probe_ready,
        "support_status": support_status,
        "delta_since_stage11752": {
            "cpp_ready_roots_added": cpp_roots,
            "cpp_ready_rows_added": cpp.get("admitted_rows", 0),
        },
        "next_actions": [
            "Continue finding clean Python verifier roots; current ready roots are 2/12.",
            "Continue C/C++ build/verifier materialization; current ready roots are 1/16.",
            "Build true Rust selected-inline-test verifier_outcome roots; current ready roots are 0/12.",
            "Do not run a promotion training probe until the declared support geometry is materially closer to quota or a small diagnostic gate is explicitly scoped.",
        ],
        "claim_boundary": [
            "No model frontier score changed in this stage.",
            "This stage records support-supply progress only.",
            "No Gemma or full-product claim is implied.",
        ],
        "source_artifacts": {
            "request": rel(REQUEST),
            "python_support": rel(PYTHON),
            "cpp_support": rel(CPP),
            "rust_evidence_support": rel(RUST_EVIDENCE),
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
                "python_ready_roots": python_roots,
                "cpp_ready_roots": cpp_roots,
                "rust_verifier_ready_roots": 0,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
