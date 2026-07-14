#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10966
NAME = "stage10966_successor_family_geometry_decision"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "successor_family_geometry_decision.json"

FAMILY_JSON = ARTIFACTS / "stage10963_expanded_evidence_successor_family" / "expanded_evidence_successor_family.json"
FAMILY_AUDIT_JSON = ARTIFACTS / "stage10964_expanded_successor_family_audit" / "expanded_successor_family_audit.json"
RUNTIME_AUDIT_JSON = ARTIFACTS / "stage10965_expanded_successor_family_runtime_audit" / "expanded_successor_family_runtime_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    family = load_json(FAMILY_JSON)
    audit = load_json(FAMILY_AUDIT_JSON)
    runtime = load_json(RUNTIME_AUDIT_JSON)
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "same_root_geometry_not_sufficient",
        "claim_scope": [
            "Record the geometry-sensitivity result for the expanded fresh Python/C++ successor family.",
            "Set the next frontier after ruling out row-geometry variation on the same three reviewed roots.",
        ],
        "source_artifacts": {
            "family": rel(FAMILY_JSON),
            "family_audit": rel(FAMILY_AUDIT_JSON),
            "runtime_audit": rel(RUNTIME_AUDIT_JSON),
        },
        "headline": {
            "family_rows": (family.get("metrics") or {}).get("row_count"),
            "anticheat_passed": audit.get("passed"),
            "overall_accuracy": (runtime.get("overall") or {}).get("exact_accuracy"),
            "python_queue_accuracy": ((runtime.get("by_queue") or {}).get("python_repository_library_evidence_b_vs_f_replenishment") or {}).get("exact_accuracy"),
            "cpp_gap_queue_accuracy": ((runtime.get("by_queue") or {}).get("cpp_parametergolf_evidence_b_vs_f_replenishment") or {}).get("exact_accuracy"),
            "cpp_control_queue_accuracy": ((runtime.get("by_queue") or {}).get("cpp_agentkernel_counterfamily_evidence_replenishment") or {}).get("exact_accuracy"),
        },
        "findings": [
            "The expanded family is anti-cheat clean and contract-correct.",
            "All eight geometry variants remain flat at 1/3 overall because the model only solves the candidate_change_surface control root.",
            "Raw-versus-ledger and full-versus-contrast reshaping on the same roots does not move the verifier-ledger-positive Python/C++ rows.",
        ],
        "next_honest_branches": [
            "Build genuinely new Python and C/C++ verifier-ledger-positive roots rather than more variants of the same three roots.",
            "Prototype a richer scorer head: evidence-role-specific or pairwise candidate-surface versus verifier-ledger scoring.",
            "Keep Rust replenishment as the next multilingual supply task, and keep web blocked on fresh pure-web selected-test source supply.",
        ],
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
