#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from query_expansion_rewriter import query_expansion_card

STAGE = 8791
NAME = "stage8791_query_expansion_rewriter_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "QUERY_EXPANSION_REWRITER_READINESS_STAGE8791.md"
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
    {"row_id": "expand", "intent": "fix auth failure", "symbol": "validate_user", "error": "AssertionError expected 403 got 200", "api": "FastAPI Depends", "language": "python"},
    {"row_id": "hold"},
    {"row_id": "block", "target_label": "CORRECT_PRIOR", "intent": "fix"},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_query_expansion_rewriter.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    sample = query_expansion_card(ROWS)
    sample_path = OUT_DIR / "query_expansion_rewriter_sample_card.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures = []
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if sample["metrics"]["pass_rows"] != 1:
        failures.append("sample_pass_count_wrong")
    if sample["metrics"]["hold_rows"] != 1:
        failures.append("sample_hold_count_wrong")
    if sample["metrics"]["blocked_rows"] != 1:
        failures.append("sample_block_count_wrong")
    if sample["metrics"]["leak_or_target_rows"] != 1:
        failures.append("sample_leak_count_wrong")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "sample_rows": len(ROWS),
            "query_variant_count": sample["metrics"]["query_variant_count"],
            "pass_rows": sample["metrics"]["pass_rows"],
            "hold_rows": sample["metrics"]["hold_rows"],
            "blocked_rows": sample["metrics"]["blocked_rows"],
            "leak_or_target_rows": sample["metrics"]["leak_or_target_rows"],
            "authority_rows": sample["metrics"]["authority_rows"],
            "failures": failures,
        },
        "artifacts": {
            "sample_card": str(sample_path.relative_to(ROOT)),
            "module": "scripts/query_expansion_rewriter.py",
            "tests": "tests/test_query_expansion_rewriter.py",
        },
        "decision": (
            "Query expansion rewriter is ready as a no-authority, shortcut-safe query variant generator from visible intent/symbol/error/API/path/language hints."
            if not failures
            else "Query expansion rewriter readiness failed."
        ),
        "next_best_step": "Rerun the parallel recovery readiness audit; if clean, reconcile registry/central graph in one controlled pass.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage8791 Query Expansion Rewriter Readiness",
                "",
                f"Passed: `{card['passed']}`",
                "",
                "Recovered a controlled query expansion rewriter for retrieval: variants are generated only from visible intent, symbol, error, API, path, language, and test-name hints.",
                "",
                "Rows exposing target labels or clean target state are blocked as query-expansion leaks.",
                "",
                "Authority remains closed. This does not execute retrieval, train, score, emit source/body, or promote.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
