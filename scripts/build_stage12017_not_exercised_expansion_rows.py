#!/usr/bin/env python3
"""Materialize additional NOT_EXERCISED transition observations."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12017_not_exercised_expansion_rows")
ROWS = ROOT / "not_exercised_expansion_rows.jsonl"
SUMMARY = ROOT / "not_exercised_expansion_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12017_not_exercised_expansion_rows.json")
LABELS = list("ABCDEFGH")

OBSERVATIONS: list[dict[str, Any]] = [
    {
        "language_family": "c_cpp",
        "repo_family": "sentencepiece",
        "cwd": "/data/repositories/sentencepiece",
        "selected_verifier_path": "/data/tmp/sentencepiece_stage11737_build::definitely_no_sentencepiece_test",
        "command": "ctest --test-dir /data/tmp/sentencepiece_stage11737_build -R '^definitely_no_sentencepiece_test$' --output-on-failure",
        "returncode": 0,
        "stdout_tail": "Test project /data/tmp/sentencepiece_stage11737_build\nNo tests were found!!!",
    },
    {
        "language_family": "c_cpp",
        "repo_family": "benchmark",
        "cwd": "/data/repositories/benchmark",
        "selected_verifier_path": "/data/tmp/stage11872_benchmark_build::definitely_no_benchmark_test",
        "command": "ctest --test-dir /data/tmp/stage11872_benchmark_build -R '^definitely_no_benchmark_test$' --output-on-failure",
        "returncode": 0,
        "stdout_tail": "Test project /data/tmp/stage11872_benchmark_build\nNo tests were found!!!",
    },
    {
        "language_family": "rust",
        "repo_family": "git",
        "cwd": "/data/repositories/git",
        "selected_verifier_path": "Cargo.toml::definitely_no_git_test_filter",
        "command": "cargo test --manifest-path /data/repositories/git/Cargo.toml definitely_no_git_test_filter -- --nocapture",
        "returncode": 0,
        "stdout_tail": "running 0 tests\n\ntest result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 2 filtered out",
    },
    {
        "language_family": "rust",
        "repo_family": "tokenizers",
        "cwd": "/data/repositories/tokenizers",
        "selected_verifier_path": "tokenizers/Cargo.toml::definitely_no_tokenizers_test_filter",
        "command": "cargo test --manifest-path /data/repositories/tokenizers/tokenizers/Cargo.toml --features fancy-regex definitely_no_tokenizers_test_filter -- --nocapture",
        "returncode": 0,
        "stdout_tail": "multiple test binaries ran 0 tests; examples include 0 passed, 0 failed, 192 filtered out in src/lib.rs and 0 passed in integration test binaries",
    },
    {
        "language_family": "web_js_ts_html",
        "repo_family": "openclaw__clawhub",
        "cwd": "/data/repositories/openclaw__clawhub",
        "selected_verifier_path": "src/__tests__/definitely-no-test-file.test.ts",
        "command": "env VITE_CONVEX_URL=https://example.invalid ./node_modules/.bin/vitest run src/__tests__/definitely-no-test-file.test.ts",
        "returncode": 1,
        "stdout_tail": "No test files found, exiting with code 1\nfilter: src/__tests__/definitely-no-test-file.test.ts",
    },
    {
        "language_family": "web_js_ts_html",
        "repo_family": "modelcontextprotocol__typescript-sdk",
        "cwd": "/data/repositories/modelcontextprotocol__typescript-sdk",
        "selected_verifier_path": "packages/core/test/definitely-no-test-file.test.ts",
        "command": "./node_modules/.bin/vitest run --globals packages/core/test/definitely-no-test-file.test.ts",
        "returncode": 1,
        "stdout_tail": "No test files found, exiting with code 1\nfilter: packages/core/test/definitely-no-test-file.test.ts",
    },
    {
        "language_family": "python",
        "repo_family": "einops",
        "cwd": "/data/repositories/einops",
        "selected_verifier_path": "tests/definitely_no_test_file.py",
        "command": "python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12017_pytest_cache tests/definitely_no_test_file.py",
        "returncode": 4,
        "stdout_tail": "ERROR: file or directory not found: tests/definitely_no_test_file.py\n\nno tests ran in 0.26s",
    },
    {
        "language_family": "python",
        "repo_family": "lastmile-ai__mcp-agent",
        "cwd": "/data/repositories/lastmile-ai__mcp-agent",
        "selected_verifier_path": "tests/utils/test_mime_utils.py::definitely_no_test_case",
        "command": "env PYTHONPATH=/data/repositories/lastmile-ai__mcp-agent/src python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12017_pytest_cache tests/utils/test_mime_utils.py::definitely_no_test_case",
        "returncode": 4,
        "stdout_tail": "ERROR: not found: tests/utils/test_mime_utils.py::definitely_no_test_case\nno tests ran in 0.32s",
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
    keyed = [
        (hashlib.sha256(f"{row_id}::{value}".encode()).hexdigest(), value, text)
        for value, text in TRANSITION_TEXT.items()
    ]
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
    material = f"{obs['repo_family']}::{obs['selected_verifier_path']}::{semantic}"
    row_id = f"stage12017::{obs['repo_family']}::{hashlib.sha1(material.encode()).hexdigest()[:12]}::{semantic}"
    opts = options(row_id, obs["language_family"])
    target_label = next(o["label"] for o in opts if o["canonical_value"] == semantic)
    prompt = "\n".join(
        [
            f"Language: {obs['language_family']}",
            "Perspective: transition_verifier_transition",
            "Task: choose the verifier transition supported by the observed command.",
            f"Repository family: {obs['repo_family']}",
            f"Source root: {obs['cwd']}",
            f"Selected verifier: {obs['selected_verifier_path']}",
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
        "root_lineage_key": f"stage12017::{obs['repo_family']}::{obs['selected_verifier_path']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": obs["repo_family"],
        "repo_family": obs["repo_family"],
        "language_family": obs["language_family"],
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12017_not_exercised_expansion_train_support_only",
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
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": True,
            "singleton_options": False,
            "train_support_only": True,
        },
        "standalone_projection_source": {
            "projection_mode": "stage12017_not_exercised_expansion_rows",
            "selected_verifier_path": obs["selected_verifier_path"],
            "observed_verifier_transition": semantic,
            "tool_or_verifier_observation": {
                "command": obs["command"],
                "cwd": obs["cwd"],
                "returncode": obs["returncode"],
                "stdout_tail": obs["stdout_tail"],
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
        "stage": "stage12017_not_exercised_expansion_rows",
        "rows_path": str(ROWS),
        "admitted_rows": len(rows),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "language_counts": dict(sorted(Counter(r["language_family"] for r in rows).items())),
        "status_counts": dict(Counter(r["observed_verifier_transition"] for r in rows)),
        "repo_family_counts": dict(sorted(Counter(r["repo_family"] for r in rows).items())),
        "decision": "admit_not_exercised_expansion_train_support",
        "claim_boundary": "Rows are train-support only and specifically teach no verifier body executed. No model promotion follows from this artifact.",
        "next_stage_recommendation": {"stage": "stage12018_transition_support_rollup_v16", "action": "Merge NOT_EXERCISED expansion rows and report remaining Transition-Root-250 floors."},
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
