#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from traced_eval_observability import trace_observability_card

STAGE = 8786
NAME = "stage8786_traced_eval_observability_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRACED_EVAL_OBSERVABILITY_READINESS_STAGE8786.md"
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
SPAN = {"span_id": "s1", "span_type": "tool", "name": "read_file"}
ROWS = [
    {"eval_id": "ok", "spans": [SPAN], "metric_events": [{"metric": "exact", "value": 1.0}]},
    {"eval_id": "fail", "spans": [SPAN], "failure_type": "symbol_binding_failure"},
    {"eval_id": "review", "spans": []},
    {"eval_id": "block", "spans": [SPAN], "target_answer_included": True},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_traced_eval_observability.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    sample = trace_observability_card(ROWS)
    sample_path = OUT_DIR / "traced_eval_observability_sample_card.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures = []
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if sample["metrics"]["failure_packet_rows"] != 1:
        failures.append("sample_failure_packet_count_wrong")
    if sample["metrics"]["dataset_patch_eligible_rows"] != 1:
        failures.append("sample_dataset_patch_eligible_count_wrong")
    if sample["metrics"]["blocked_rows"] != 1:
        failures.append("sample_block_count_wrong")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "sample_rows": len(ROWS),
            "pass_trace_rows": sample["metrics"]["pass_trace_rows"],
            "failure_packet_rows": sample["metrics"]["failure_packet_rows"],
            "schema_review_rows": sample["metrics"]["schema_review_rows"],
            "blocked_rows": sample["metrics"]["blocked_rows"],
            "dataset_patch_eligible_rows": sample["metrics"]["dataset_patch_eligible_rows"],
            "authority_rows": sample["metrics"]["authority_rows"],
            "failures": failures,
        },
        "artifacts": {
            "sample_card": str(sample_path.relative_to(ROOT)),
            "module": "scripts/traced_eval_observability.py",
            "tests": "tests/test_traced_eval_observability.py",
        },
        "decision": (
            "Traced eval observability is ready as a shared no-authority trace schema for eval harness, dataset judge, and curriculum compiler handoff."
            if not failures
            else "Traced eval observability readiness failed."
        ),
        "next_best_step": "Rerun a module/submodule readiness audit after reconciling concurrent registry and central spine edits.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage8786 Traced Eval Observability Readiness",
                "",
                f"Passed: `{card['passed']}`",
                "",
                "Recovered a shared trace schema with trace IDs, span trees, metric events, failure packets, and dataset-patch links.",
                "",
                "Failure traces can become dataset-patch eligible only when they are not locked, hidden, target-answer leaking, or raw-source leaking.",
                "",
                "Authority remains closed. This does not train, mine, execute, score, emit source/body, or promote.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
