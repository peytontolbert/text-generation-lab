#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from latency_resource_observability import observability_card

STAGE = 8783
NAME = "stage8783_latency_resource_observability_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LATENCY_RESOURCE_OBSERVABILITY_READINESS_STAGE8783.md"
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
ROWS = [
    {"row_id": "ok", "usage": {"latency_ms": 100, "memory_peak_mb": 64, "token_count": 100, "tool_cost": 1}},
    {"row_id": "warn", "usage": {"latency_ms": 900}},
    {"row_id": "block", "usage": {"token_count": 1200}},
]
LIMITS = {"latency_ms": 1000, "token_count": 1000}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_latency_resource_observability.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    sample = observability_card(ROWS, limits=LIMITS)
    sample_path = OUT_DIR / "latency_resource_observability_sample_card.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures = []
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if sample["metrics"]["pass_rows"] != 1:
        failures.append("sample_pass_count_wrong")
    if sample["metrics"]["warning_rows"] != 1:
        failures.append("sample_warning_count_wrong")
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
            "pass_rows": sample["metrics"]["pass_rows"],
            "warning_rows": sample["metrics"]["warning_rows"],
            "blocked_rows": sample["metrics"]["blocked_rows"],
            "budget_violation_rows": sample["metrics"]["budget_violation_rows"],
            "authority_rows": sample["metrics"]["authority_rows"],
            "failures": failures,
        },
        "artifacts": {
            "sample_card": str(sample_path.relative_to(ROOT)),
            "module": "scripts/latency_resource_observability.py",
            "tests": "tests/test_latency_resource_observability.py",
        },
        "decision": (
            "Latency/resource observability is ready as passive telemetry over latency, memory, token, tool-cost, and budget-violation signals."
            if not failures
            else "Latency/resource observability readiness failed."
        ),
        "next_best_step": "Recover repository_universe_builder, then traced_eval_observability.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage8783 Latency Resource Observability Readiness",
                "",
                f"Passed: `{card['passed']}`",
                "",
                "Recovered passive telemetry for controller economics: latency, peak memory, token count, tool cost, tool-call count, warnings, and hard budget violations.",
                "",
                "Authority remains closed. This does not execute tools, mine, train, score, emit source/body, or promote.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
