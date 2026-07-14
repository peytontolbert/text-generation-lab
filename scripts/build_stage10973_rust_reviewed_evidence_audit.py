#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10973
NAME = "stage10973_rust_reviewed_evidence_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "rust_reviewed_evidence_audit.json"
BUNDLE_ROWS = ARTIFACTS / "stage10972_rust_reviewed_evidence_bundle" / "bundle_rows.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    rows = load_jsonl(BUNDLE_ROWS)
    bundle_counts: dict[str, int] = defaultdict(int)
    missing_gold_visibility = []
    identical_candidate_and_symptom = []
    missing_selected_test_anchor = []
    missing_option_projection = []

    for row in rows:
        row_id = str(row.get("row_id") or "")
        bundle_counts[str(row.get("bundle_id") or "unknown")] += 1
        prompt = str(row.get("prompt_text") or row.get("input_text") or "")
        evidence_block = ""
        if "Evidence:\n" in prompt and "\nOptions:\n" in prompt:
            evidence_block = prompt.split("Evidence:\n", 1)[1].split("\nOptions:\n", 1)[0]
        evidence_lines = [line.strip() for line in evidence_block.splitlines() if line.strip()]
        gold_value = str(((row.get("standalone_projection_source") or {}).get("gold_value") or ""))
        selected_tests = list(row.get("selected_tests") or [])
        projection = dict(row.get("standalone_projection_source") or {})
        if not projection.get("opaque_options"):
            missing_option_projection.append(row_id)
        if gold_value and not any(line.startswith(gold_value) for line in evidence_lines):
            missing_gold_visibility.append(row_id)
        if selected_tests and gold_value in {"verifier_and_test_constraint", "symptom_or_call_path_analogue"} and not any(test in prompt for test in selected_tests):
            missing_selected_test_anchor.append(row_id)
        candidate_line = next((line for line in evidence_lines if line.startswith("candidate_change_surface")), "")
        symptom_line = next((line for line in evidence_lines if line.startswith("symptom_or_call_path_analogue")), "")
        if candidate_line and symptom_line and candidate_line == symptom_line:
            identical_candidate_and_symptom.append(row_id)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not any([missing_gold_visibility, identical_candidate_and_symptom, missing_selected_test_anchor, missing_option_projection]),
        "source_bundle_rows": rel(BUNDLE_ROWS),
        "metrics": {
            "rows": len(rows),
            "bundle_counts": dict(sorted(bundle_counts.items())),
            "missing_gold_visibility_rows": len(missing_gold_visibility),
            "identical_candidate_and_symptom_rows": len(identical_candidate_and_symptom),
            "missing_selected_test_anchor_rows": len(missing_selected_test_anchor),
            "missing_option_projection_rows": len(missing_option_projection),
        },
        "row_ids": {
            "missing_gold_visibility": missing_gold_visibility,
            "identical_candidate_and_symptom": identical_candidate_and_symptom,
            "missing_selected_test_anchor": missing_selected_test_anchor,
            "missing_option_projection": missing_option_projection,
        },
        "findings": [
            "This audit checks the reviewed Rust bundle for the evidence-role collapse that previously affected Rust citation rows.",
            "A passing result means gold evidence is visible, selected-test anchors survive on symptom/verifier-ledger packets, and the model-visible candidate and symptom evidence lines are not textually identical.",
        ],
    }
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
