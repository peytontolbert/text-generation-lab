#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10902
NAME = "stage10902_python_verifier_transition_candidate_slice"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "python_verifier_transition_candidate_slice.json"
STRICT_ROWS_JSONL = OUT_DIR / "strict_candidate_rows.jsonl"

CANDIDATE_ONE = ARTIFACTS / "stage10894_code_assist_python_verifier_transition_strict_candidate" / "strict_candidate_rows.jsonl"
CANDIDATE_TWO = ARTIFACTS / "stage10900_code_assist_hf_local_python_verifier_transition_strict_candidate" / "strict_candidate_rows.jsonl"
AUDIT_ONE = ARTIFACTS / "stage10895_code_assist_python_verifier_transition_strict_candidate_audit" / "code_assist_python_verifier_transition_strict_candidate_audit.json"
AUDIT_TWO = ARTIFACTS / "stage10901_code_assist_hf_local_python_verifier_transition_strict_candidate_audit" / "code_assist_hf_local_python_verifier_transition_strict_candidate_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    rows = [*load_jsonl(CANDIDATE_ONE), *load_jsonl(CANDIDATE_TWO)]
    audit_one = load_json(AUDIT_ONE)
    audit_two = load_json(AUDIT_TWO)
    for row in rows:
        row["split"] = "strict_eval_candidate_slice"
        row["slice_id"] = "stage10902::python_verifier_transition_candidates"

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_verifier_transition_candidate_slice_ready",
        "claim_scope": [
            "Bundle the two reviewed fresh Python verifier-transition candidate rows into one small candidate slice for runtime-vs-Gemma diagnostic scoring.",
            "Keep the slice explicitly non-promotable and separate from the 23-row reviewed v2.7 strict baseline.",
        ],
        "metrics": {
            "candidate_rows": len(rows),
            "distinct_source_roots": len({str(row.get('source_root_id') or '') for row in rows}),
        },
        "row_ids": [str(row.get("row_id") or "") for row in rows],
        "candidate_quality_notes": [
            "stage10894 is the stronger cross-test opaque verifier-transition row.",
            "stage10900 is a same-test semantic verifier-transition row with weaker shortcut posture but useful contrast pressure.",
        ],
        "source_audits": {
            "stage10894": rel(AUDIT_ONE),
            "stage10900": rel(AUDIT_TWO),
        },
        "next_best_step": "Run the current standalone runtime and Gemma on this 2-row candidate slice to test whether the verifier-transition miss is isolated to one root or repeats across a second fresh semantic row.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "strict_rows_jsonl": rel(STRICT_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_jsonl(STRICT_ROWS_JSONL, rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
