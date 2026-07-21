#!/usr/bin/env python3
"""Materialize verifier-mismatch NOT_EXERCISED transition rows."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12037_verifier_mismatch_not_exercised_rows")
ROWS = ROOT / "verifier_mismatch_not_exercised_rows.jsonl"
SUMMARY = ROOT / "verifier_mismatch_not_exercised_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12037_verifier_mismatch_not_exercised_rows.json")
LABELS = list("ABCDEFGH")

OBSERVATIONS: list[dict[str, Any]] = [
    {
        "language_family": "rust",
        "repo_family": "tokenizers",
        "cwd": "/data/repositories/tokenizers",
        "selected_verifier_path": "tokenizers::decoders::ctc::tests::handmade_sample",
        "observed_verifier_path": "tokenizers::decoders::fuse::tests::decode",
        "command": "cargo test --manifest-path /data/repositories/tokenizers/tokenizers/Cargo.toml --features fancy-regex decoders::fuse::tests::decode --quiet",
        "returncode": 0,
        "stdout_tail": "running 1 test; ok. 1 passed; 0 failed; 191 filtered out",
    },
    {
        "language_family": "rust",
        "repo_family": "tokenizers",
        "cwd": "/data/repositories/tokenizers",
        "selected_verifier_path": "tokenizers::decoders::sequence::tests::sequence_basic",
        "observed_verifier_path": "tokenizers::models::unigram::lattice::tests::test_viterbi",
        "command": "cargo test --manifest-path /data/repositories/tokenizers/tokenizers/Cargo.toml --features fancy-regex models::unigram::lattice::tests::test_viterbi --quiet",
        "returncode": 0,
        "stdout_tail": "running 2 tests; ok. 2 passed; 0 failed; 190 filtered out",
    },
    {
        "language_family": "c_cpp",
        "repo_family": "benchmark",
        "cwd": "/data/repositories/benchmark",
        "selected_verifier_path": "CTest::filter_simple_negative_filter_suffix_negative_filter_regex_all_negative",
        "observed_verifier_path": "CTest::filter_regex_begin_filter_regex_end_skip_with_error_test",
        "command": "ctest --test-dir /data/tmp/stage11872_benchmark_build -R '^(filter_regex_begin|filter_regex_end|skip_with_error_test)$' --output-on-failure",
        "returncode": 0,
        "stdout_tail": "3/3 tests passed: filter_regex_begin, filter_regex_end, skip_with_error_test",
    },
    {
        "language_family": "c_cpp",
        "repo_family": "benchmark",
        "cwd": "/data/repositories/benchmark",
        "selected_verifier_path": "CTest::filter_regex_none_filter_regex_begin2_filter_regex_blank_negative",
        "observed_verifier_path": "CTest::filter_suffix_filter_regex_blank_filter_regex_wildcard_options",
        "command": "ctest --test-dir /data/tmp/stage11872_benchmark_build -R '^(filter_suffix|filter_regex_blank|filter_regex_wildcard|options_benchmarks)$' --output-on-failure",
        "returncode": 0,
        "stdout_tail": "4/4 tests passed: filter_suffix, filter_regex_blank, filter_regex_wildcard, options_benchmarks",
    },
    {
        "language_family": "c_cpp",
        "repo_family": "benchmark",
        "cwd": "/data/repositories/benchmark",
        "selected_verifier_path": "CTest::filter_regex_begin_filter_regex_end_skip_with_error_test",
        "observed_verifier_path": "CTest::filter_simple_negative_filter_suffix_negative_filter_regex_all_negative",
        "command": "ctest --test-dir /data/tmp/stage11872_benchmark_build -R '^(filter_simple_negative|filter_suffix_negative|filter_regex_all_negative)$' --output-on-failure",
        "returncode": 0,
        "stdout_tail": "3/3 tests passed: filter_simple_negative, filter_suffix_negative, filter_regex_all_negative",
    },
    {
        "language_family": "c_cpp",
        "repo_family": "benchmark",
        "cwd": "/data/repositories/benchmark",
        "selected_verifier_path": "CTest::filter_suffix_filter_regex_blank_filter_regex_wildcard_options",
        "observed_verifier_path": "CTest::filter_regex_none_filter_regex_begin2_filter_regex_blank_negative",
        "command": "ctest --test-dir /data/tmp/stage11872_benchmark_build -R '^(filter_regex_none|filter_regex_begin2|filter_regex_blank_negative)$' --output-on-failure",
        "returncode": 0,
        "stdout_tail": "3/3 tests passed: filter_regex_blank_negative, filter_regex_none, filter_regex_begin2",
    },
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
    return [
        {
            "label": label,
            "canonical_value": value,
            "value": value,
            "text": text,
            "role": "verifier_transition_status",
            "artifact_type": f"{language}_verifier_status",
        }
        for label, (_, value, text) in zip(LABELS, sorted(keyed))
    ]


def make_row(obs: dict[str, Any]) -> dict[str, Any]:
    semantic = "NOT_EXERCISED"
    material = f"{obs['repo_family']}::{obs['selected_verifier_path']}::{obs['observed_verifier_path']}::{semantic}"
    row_id = f"stage12037::{obs['repo_family']}::{hashlib.sha1(material.encode()).hexdigest()[:12]}::{semantic}"
    opts = options(row_id, obs["language_family"])
    target_label = next(o["label"] for o in opts if o["canonical_value"] == semantic)
    prompt = "\n".join(
        [
            f"Language: {obs['language_family']}",
            "Perspective: transition_verifier_transition",
            "Task: choose the verifier transition for the selected verifier, not merely for any passing sibling command.",
            f"Repository family: {obs['repo_family']}",
            f"Selected verifier: {obs['selected_verifier_path']}",
            f"Observed executed verifier: {obs['observed_verifier_path']}",
            f"Observed command: {obs['command']}",
            f"Return code: {obs['returncode']}",
            f"Output tail: {obs['stdout_tail']}",
            "Options:",
            *[f"{o['label']}. {o['text']}" for o in opts],
            "Answer:",
        ]
    )
    return {
        "row_id": row_id,
        "root_id": row_id,
        "root_lineage_key": f"stage12037::{obs['repo_family']}::{obs['selected_verifier_path']}::{obs['observed_verifier_path']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": obs["repo_family"],
        "repo_family": obs["repo_family"],
        "language_family": obs["language_family"],
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12037_verifier_mismatch_not_exercised_train_support_only",
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
        "verifier_mismatch": {
            "selected_verifier_path": obs["selected_verifier_path"],
            "observed_verifier_path": obs["observed_verifier_path"],
            "observed_returncode": obs["returncode"],
        },
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": True,
            "singleton_options": False,
            "train_support_only": True,
        },
        "standalone_projection_source": {
            "projection_mode": "stage12037_verifier_mismatch_not_exercised_rows",
            "selected_verifier_path": obs["selected_verifier_path"],
            "observed_verifier_transition": semantic,
            "tool_or_verifier_observation": {
                "command": obs["command"],
                "cwd": obs["cwd"],
                "returncode": obs["returncode"],
                "stdout_tail": obs["stdout_tail"],
                "observed_verifier_path": obs["observed_verifier_path"],
                "timed_out": False,
            },
        },
    }


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    rows = [make_row(obs) for obs in OBSERVATIONS]
    write_jsonl(ROWS, rows)
    summary = {
        "stage": "stage12037_verifier_mismatch_not_exercised_rows",
        "rows_path": str(ROWS),
        "admitted_rows": len(rows),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "language_counts": dict(sorted(Counter(r["language_family"] for r in rows).items())),
        "status_counts": dict(sorted(Counter(r["observed_verifier_transition"] for r in rows).items())),
        "repo_family_counts": dict(sorted(Counter(r["repo_family"] for r in rows).items())),
        "decision": "admit_verifier_mismatch_not_exercised_train_support",
        "claim_boundary": "Rows are train-support only. They teach selected-verifier discipline, not model promotion.",
        "next_stage_recommendation": {
            "stage": "stage12038_transition_support_rollup_v26",
            "action": "Merge verifier-mismatch NOT_EXERCISED rows and report remaining floors.",
        },
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
