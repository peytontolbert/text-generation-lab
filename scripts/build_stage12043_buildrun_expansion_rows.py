#!/usr/bin/env python3
"""Materialize paired build/typecheck plus focused verifier transition rows."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12043_buildrun_expansion_rows")
ROWS = ROOT / "buildrun_expansion_rows.jsonl"
SUMMARY = ROOT / "buildrun_expansion_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12043_buildrun_expansion_rows.json")
LABELS = list("ABCDEFGH")

OBSERVATIONS: list[dict[str, Any]] = [
    {"language_family": "python", "repo_family": "Python", "cwd": "/data/repositories/Python", "selected_verifier_path": "py_compile maths/factorial.py + maths/test_factorial.py", "command": "python -m py_compile /data/repositories/Python/maths/factorial.py && python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12043_pytest_cache /data/repositories/Python/maths/test_factorial.py", "stdout_tail": "py_compile completed; pytest reported 10 passed in 0.36s"},
    {"language_family": "python", "repo_family": "Python", "cwd": "/data/repositories/Python", "selected_verifier_path": "py_compile maths/prime_check.py + maths/test_prime_check.py", "command": "python -m py_compile /data/repositories/Python/maths/prime_check.py && python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12043_pytest_cache /data/repositories/Python/maths/test_prime_check.py", "stdout_tail": "py_compile completed; pytest reported 2 passed in 0.35s"},
    {"language_family": "rust", "repo_family": "tokenizers", "cwd": "/data/repositories/tokenizers", "selected_verifier_path": "cargo check fancy-regex + decoders::fuse::tests::decode", "command": "cargo check --manifest-path /data/repositories/tokenizers/tokenizers/Cargo.toml --features fancy-regex --quiet && cargo test --manifest-path /data/repositories/tokenizers/tokenizers/Cargo.toml --features fancy-regex decoders::fuse::tests::decode --quiet", "stdout_tail": "cargo check completed; cargo test ran 1 test and passed with 191 filtered out"},
    {"language_family": "rust", "repo_family": "tokenizers", "cwd": "/data/repositories/tokenizers", "selected_verifier_path": "cargo check fancy-regex + decoders::sequence::tests::sequence_basic", "command": "cargo check --manifest-path /data/repositories/tokenizers/tokenizers/Cargo.toml --features fancy-regex --quiet && cargo test --manifest-path /data/repositories/tokenizers/tokenizers/Cargo.toml --features fancy-regex decoders::sequence::tests::sequence_basic --quiet", "stdout_tail": "cargo check completed; cargo test ran 1 test and passed with 191 filtered out"},
    {"language_family": "rust", "repo_family": "tokenizers", "cwd": "/data/repositories/tokenizers", "selected_verifier_path": "cargo check fancy-regex + models::unigram::lattice::tests::test_viterbi", "command": "cargo check --manifest-path /data/repositories/tokenizers/tokenizers/Cargo.toml --features fancy-regex --quiet && cargo test --manifest-path /data/repositories/tokenizers/tokenizers/Cargo.toml --features fancy-regex models::unigram::lattice::tests::test_viterbi --quiet", "stdout_tail": "cargo check completed; cargo test ran 2 tests and passed with 190 filtered out"},
    {"language_family": "c_cpp", "repo_family": "benchmark", "cwd": "/data/repositories/benchmark", "selected_verifier_path": "cmake filter_test build + CTest filter_regex_begin/filter_regex_end/skip_with_error_test", "command": "cmake --build /data/tmp/stage11872_benchmark_build --target filter_test -j2 && ctest --test-dir /data/tmp/stage11872_benchmark_build -R '^(filter_regex_begin|filter_regex_end|skip_with_error_test)$' --output-on-failure", "stdout_tail": "Built target filter_test; CTest reported 3/3 tests passed"},
    {"language_family": "c_cpp", "repo_family": "benchmark", "cwd": "/data/repositories/benchmark", "selected_verifier_path": "cmake filter_test build + CTest filter_simple_negative/filter_suffix_negative/filter_regex_all_negative", "command": "cmake --build /data/tmp/stage11872_benchmark_build --target filter_test -j2 && ctest --test-dir /data/tmp/stage11872_benchmark_build -R '^(filter_simple_negative|filter_suffix_negative|filter_regex_all_negative)$' --output-on-failure", "stdout_tail": "Built target filter_test; CTest reported 3/3 tests passed"},
    {"language_family": "c_cpp", "repo_family": "benchmark", "cwd": "/data/repositories/benchmark", "selected_verifier_path": "cmake filter_test build + CTest filter_regex_none/filter_regex_begin2/filter_regex_blank_negative", "command": "cmake --build /data/tmp/stage11872_benchmark_build --target filter_test -j2 && ctest --test-dir /data/tmp/stage11872_benchmark_build -R '^(filter_regex_none|filter_regex_begin2|filter_regex_blank_negative)$' --output-on-failure", "stdout_tail": "Built target filter_test; CTest reported 3/3 tests passed"},
    {"language_family": "web_js_ts_html", "repo_family": "modelcontextprotocol__typescript-sdk", "cwd": "/data/repositories/modelcontextprotocol__typescript-sdk", "selected_verifier_path": "@modelcontextprotocol/core typecheck + packages/core/test/shared/transport.test.ts", "command": "pnpm --dir /data/repositories/modelcontextprotocol__typescript-sdk --filter @modelcontextprotocol/core run typecheck && ./node_modules/.bin/vitest run --globals packages/core/test/shared/transport.test.ts", "stdout_tail": "typecheck completed; Vitest reported 1 file passed and 13 tests passed"},
    {"language_family": "web_js_ts_html", "repo_family": "modelcontextprotocol__typescript-sdk", "cwd": "/data/repositories/modelcontextprotocol__typescript-sdk", "selected_verifier_path": "@modelcontextprotocol/core typecheck + packages/core/test/shared/customMethods.test.ts", "command": "pnpm --dir /data/repositories/modelcontextprotocol__typescript-sdk --filter @modelcontextprotocol/core run typecheck && ./node_modules/.bin/vitest run --globals packages/core/test/shared/customMethods.test.ts", "stdout_tail": "typecheck completed; Vitest reported 1 file passed and 13 tests passed"},
]

REJECTED_PROBES = [
    {"repo_family": "NousResearch__hermes-agent", "command": "python -m py_compile /data/repositories/NousResearch__hermes-agent/hermes/retry.py && pytest tests/test_retry_utils.py", "returncode": 1, "reason": "compile path was invalid; not admitted"},
]

TRANSITION_TEXT = {
    "PASS_TO_PASS": "focused verifier executed from local source and passed",
    "PASS_CURRENT_BUILD_AND_RUN": "build and runnable verifier both passed",
    "PASS_CURRENT_BUILD": "build or collection passed but runnable verifier body did not execute",
    "FAIL_TO_PASS": "controlled broken state failed and restored or repaired source passed",
    "NOT_EXERCISED": "command did not exercise or collect the selected verifier",
    "INSUFFICIENT_EVIDENCE": "environment is underhydrated so no trustworthy transition is available",
    "FAIL_TO_FAIL": "verifier failed in the current local source state",
    "VERIFIER_REMOVED": "verifier evidence was removed and the row should abstain",
}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def options(row_id: str, language: str) -> list[dict[str, str]]:
    keyed = [(hashlib.sha256(f"{row_id}::{value}".encode()).hexdigest(), value, text) for value, text in TRANSITION_TEXT.items()]
    return [{"label": label, "canonical_value": value, "value": value, "text": text, "role": "verifier_transition_status", "artifact_type": f"{language}_verifier_status"} for label, (_, value, text) in zip(LABELS, sorted(keyed))]


def make_row(obs: dict[str, Any]) -> dict[str, Any]:
    semantic = "PASS_CURRENT_BUILD_AND_RUN"
    material = f"{obs['repo_family']}::{obs['selected_verifier_path']}::{semantic}"
    row_id = f"stage12043::{obs['repo_family']}::{hashlib.sha1(material.encode()).hexdigest()[:12]}::{semantic}"
    opts = options(row_id, obs["language_family"])
    target_label = next(o["label"] for o in opts if o["canonical_value"] == semantic)
    prompt = "\n".join([
        f"Language: {obs['language_family']}",
        "Perspective: transition_verifier_transition",
        "Task: choose the verifier transition supported by paired build/typecheck and runnable verifier evidence.",
        f"Repository family: {obs['repo_family']}",
        f"Source root: {obs['cwd']}",
        f"Selected verifier/build pair: {obs['selected_verifier_path']}",
        f"Observed command: {obs['command']}",
        "Return code: 0",
        f"Output tail: {obs['stdout_tail']}",
        "Options:",
        *[f"{o['label']}. {o['text']}" for o in opts],
        "Answer:",
    ])
    return {
        "row_id": row_id,
        "root_id": row_id,
        "root_lineage_key": f"stage12043::{obs['repo_family']}::{obs['selected_verifier_path']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": obs["repo_family"],
        "repo_family": obs["repo_family"],
        "language_family": obs["language_family"],
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12043_buildrun_expansion_train_support_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "selected_test_anchor": True,
        "verifier_anchor": True,
        "input_text": prompt,
        "prompt_text": prompt,
        "target_text": target_label,
        "decoder_text": target_label,
        "bounded_choice_target_label": target_label,
        "target": {"bounded_choice_target_label": target_label, "decoder_text": target_label, "semantic_value": semantic},
        "opaque_options": opts,
        "observed_verifier_transition": semantic,
        "anti_cheat": {"deterministic_option_shuffle": True, "target_label_not_visible_before_options": True, "target_value_not_visible_before_options": True, "singleton_options": False, "train_support_only": True},
        "standalone_projection_source": {"projection_mode": "stage12043_buildrun_expansion_rows", "selected_verifier_path": obs["selected_verifier_path"], "observed_verifier_transition": semantic, "tool_or_verifier_observation": {"command": obs["command"], "cwd": obs["cwd"], "returncode": 0, "stdout_tail": obs["stdout_tail"], "timed_out": False}},
    }


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    rows = [make_row(obs) for obs in OBSERVATIONS]
    write_jsonl(ROWS, rows)
    summary = {
        "stage": "stage12043_buildrun_expansion_rows",
        "rows_path": str(ROWS),
        "admitted_rows": len(rows),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "language_counts": dict(sorted(Counter(r["language_family"] for r in rows).items())),
        "status_counts": dict(sorted(Counter(r["observed_verifier_transition"] for r in rows).items())),
        "repo_family_counts": dict(sorted(Counter(r["repo_family"] for r in rows).items())),
        "rejected_probe_count": len(REJECTED_PROBES),
        "rejected_probes": REJECTED_PROBES,
        "decision": "admit_buildrun_expansion_train_support",
        "claim_boundary": "Rows are train-support only. No model promotion follows from this artifact.",
        "next_stage_recommendation": {"stage": "stage12044_transition_support_rollup_v29", "action": "Merge build+run rows and report remaining status floors."},
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
