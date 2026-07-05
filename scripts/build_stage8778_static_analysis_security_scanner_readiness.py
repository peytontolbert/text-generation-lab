#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from static_analysis_security_scanner import scan_rows

STAGE = 8778
NAME = "stage8778_static_analysis_security_scanner_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STATIC_ANALYSIS_SECURITY_SCANNER_READINESS_STAGE8778.md"
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
    {"row_id": "safe", "code": "def add(a, b):\n    return a + b\n"},
    {"row_id": "review", "code": "DEBUG = True\n"},
    {"row_id": "block_eval", "code": "value = eval(user_input)\n"},
    {"row_id": "block_shell", "code": "subprocess.run(cmd, shell=True)\n"},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_static_analysis_security_scanner.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    sample = scan_rows(ROWS)
    sample_path = OUT_DIR / "static_analysis_security_scanner_sample_card.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures = []
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if sample["metrics"]["pass_rows"] != 1:
        failures.append("sample_pass_count_wrong")
    if sample["metrics"]["review_rows"] != 1:
        failures.append("sample_review_count_wrong")
    if sample["metrics"]["blocked_rows"] != 2:
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
            "review_rows": sample["metrics"]["review_rows"],
            "blocked_rows": sample["metrics"]["blocked_rows"],
            "finding_count": sample["metrics"]["finding_count"],
            "failures": failures,
        },
        "artifacts": {
            "sample_card": str(sample_path.relative_to(ROOT)),
            "module": "scripts/static_analysis_security_scanner.py",
            "tests": "tests/test_static_analysis_security_scanner.py",
        },
        "decision": (
            "Static analysis security scanner is ready as a no-runtime gate for high-risk code/config rows."
            if not failures
            else "Static analysis security scanner readiness failed."
        ),
        "next_best_step": (
            "Attach static_analysis_security_scanner to the central graph when the commit/reconcile path is clear; "
            "attach static_analysis_security_scanner to central graph, then recover source-backed verifier-repair builder."
        ),
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage8778 Static Analysis Security Scanner Readiness",
                "",
                f"Passed: `{card['passed']}`",
                "",
                "Recovered a no-runtime scanner for high-risk code/config patterns such as eval/exec, shell=True, unsafe pickle/yaml loading, hardcoded secrets, and debug flags.",
                "",
                "Routes: `PASS_STATIC_SECURITY_SCAN`, `HOLD_SECURITY_REVIEW`, and `BLOCK_SECURITY_RISK`.",
                "",
                "Authority remains closed. This does not execute code, mine, train, score, emit source/body, or promote.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
