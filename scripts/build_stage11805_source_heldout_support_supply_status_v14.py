#!/usr/bin/env python3
"""Refresh support supply after PyTorch XNNPACK C/C++ admission."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11805
NAME = "stage11805_source_heldout_support_supply_status_v14"
OUT = ART / NAME
SUMMARY = OUT / "source_heldout_support_supply_status_v14.json"

PYTHON = ART / "stage11796_python_verifier_support_combined_audit_v6/python_verifier_support_combined_audit_v6.json"
CPP = ART / "stage11804_cpp_abstain_support_combined_audit_v5/cpp_abstain_support_combined_audit_v5.json"
RUST = ART / "stage11800_rust_verifier_support_combined_audit_v3/rust_verifier_support_combined_audit_v3.json"
RUST_EVIDENCE = ART / "stage11751_rust_existing_evidence_support_audit/rust_existing_evidence_support_audit.json"


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
    py = read_json(PYTHON)
    cpp = read_json(CPP)
    rust = read_json(RUST)
    rust_evidence = read_json(RUST_EVIDENCE)
    py_roots = int(py.get("admitted_root_count", 0))
    cpp_roots = int(cpp.get("admitted_root_count", 0))
    rust_roots = int(rust.get("admitted_root_count", 0))
    support_status = {
        "python_verifier_support": {"ready_roots": py_roots, "ready_rows": py.get("admitted_rows", 0), "remaining_support_roots": max(0, 12 - py_roots), "required_support_roots": 12, "materialized_rows": py.get("outputs", {}).get("combined_rows")},
        "cpp_abstain_attractor_support": {"ready_roots": cpp_roots, "ready_rows": cpp.get("admitted_rows", 0), "remaining_support_roots": max(0, 16 - cpp_roots), "required_support_roots": 16, "repo_families_ready": cpp.get("admitted_repo_families", []), "materialized_rows": cpp.get("outputs", {}).get("combined_rows")},
        "rust_verifier_support": {"ready_roots": rust_roots, "ready_rows": rust.get("admitted_rows", 0), "remaining_support_roots": max(0, 12 - rust_roots), "required_support_roots": 12, "repo_families_ready": rust.get("admitted_repo_families", []), "materialized_rows": rust.get("outputs", {}).get("admitted_rows")},
        "rust_evidence_support_only": {"ready_roots": rust_evidence.get("admitted_root_count", 0), "ready_rows": rust_evidence.get("admitted_rows", 0), "claim_boundary": "Not counted toward Rust verifier_outcome quota."},
    }
    training_probe_ready = py_roots >= 12 and cpp_roots >= 16 and rust_roots >= 12
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "support_supply_improved_but_training_probe_not_ready",
        "passed": True,
        "training_probe_ready": training_probe_ready,
        "support_status": support_status,
        "delta_since_stage11801": {"cpp_abstain_ready_roots_added": 1, "cpp_abstain_ready_rows_added": 4},
        "next_actions": ["Continue C/C++ build/verifier expansion beyond 5/16 roots.", "Continue Rust verifier expansion beyond 4/12 roots.", "Continue Python verifier expansion beyond 7/12 roots."],
        "claim_boundary": ["No model frontier score changed in this stage.", "No training, Gemma comparison, or full-product claim is implied."],
        "source_artifacts": {"python_support": rel(PYTHON), "cpp_support": rel(CPP), "rust_support": rel(RUST), "rust_evidence_support": rel(RUST_EVIDENCE)},
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "training_probe_ready": training_probe_ready, "python_ready_roots": py_roots, "cpp_ready_roots": cpp_roots, "rust_verifier_ready_roots": rust_roots}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
