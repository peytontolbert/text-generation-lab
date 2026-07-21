#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12365_candle_rust_display_verifier_blocker"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
LOG_DIR = ROOT / "runs/local/artifacts/stage12365_candle_rust_display_verifier_executor/logs"
STDOUT = LOG_DIR / "candle_display_stdout.log"
STDERR = LOG_DIR / "candle_display_stderr.log"


def sha_file(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stdout = STDOUT.read_text(encoding="utf-8", errors="replace") if STDOUT.exists() else ""
    stderr = STDERR.read_text(encoding="utf-8", errors="replace") if STDERR.exists() else ""
    compile_error = bool(re.search(r"error\\[E\\d+\\]|error:", stderr))
    rand_conflict = "multiple different versions of crate `rand`" in stderr
    blocker = {
        "stage": STAGE,
        "decision": "candle_rust_selected_test_candidate_blocked",
        "training_allowed": False,
        "claim_boundary": "Executor/blocker artifact only. No train-support, strict eval, source-heldout, Level-3, patch, or repair row admitted.",
        "repo_family": "huggingface/candle",
        "language_family": "rust",
        "attempted_command": "CARGO_TARGET_DIR=/tmp/codex-candle-target cargo test --offline -p candle-core --test display_tests display_scalar -- --exact",
        "log_refs": {
            "stdout_sha256": sha_file(STDOUT),
            "stderr_sha256": sha_file(STDERR),
        },
        "blocked_reasons": [
            "focused_verifier_not_reached_compile_failed",
            "local_dependency_version_conflict_rand_half_bf16" if rand_conflict else "compile_error_before_selected_test",
        ],
        "observed_status": {
            "compile_error": compile_error,
            "focused_test_result_observed": False,
            "same_source_selected_test_proof": False,
            "admit_as_selected_test_train_support": False,
        },
        "next_action": "Do not admit Candle display_tests from this command. Find a different non-tokenizers Rust root/command or repair environment in a separate env-repair lane.",
    }
    (OUT / "candle_rust_display_verifier_blocker.json").write_text(json.dumps(blocker, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(blocker, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
