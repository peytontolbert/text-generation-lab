#!/usr/bin/env python3
"""Materialize real-repo NOT_EXERCISED observations from zero-test filters."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12027_not_exercised_real_filter_rows")
ROWS = ROOT / "not_exercised_real_filter_rows.jsonl"
SUMMARY = ROOT / "not_exercised_real_filter_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12027_not_exercised_real_filter_rows.json")
LABELS = list("ABCDEFGH")

OBSERVATIONS: list[dict[str, Any]] = [
    {
        "language_family": "python",
        "repo_family": "einops",
        "cwd": "/data/repositories/einops",
        "selected_verifier_path": "einops/tests/test_ops.py -k stage12027_no_such_case",
        "command": "env EINOPS_TEST_BACKENDS=numpy python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12027_pytest_cache /data/repositories/einops/einops/tests/test_ops.py -k stage12027_no_such_case",
        "returncode": 5,
        "stdout_tail": "24 deselected in 0.42s",
    },
    {
        "language_family": "python",
        "repo_family": "lastmile-ai__mcp-agent",
        "cwd": "/data/repositories/lastmile-ai__mcp-agent",
        "selected_verifier_path": "tests/config/test_env_settings.py -k stage12027_no_such_case",
        "command": "env PYTHONPATH=/data/repositories/lastmile-ai__mcp-agent/src python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12027_pytest_cache /data/repositories/lastmile-ai__mcp-agent/tests/config/test_env_settings.py -k stage12027_no_such_case",
        "returncode": 5,
        "stdout_tail": "2 deselected in 0.65s",
    },
    {
        "language_family": "rust",
        "repo_family": "perftree",
        "cwd": "/data/repositories/perftree",
        "selected_verifier_path": "perftree/Cargo.toml::stage12027_no_such_case",
        "command": "cargo test --manifest-path /data/repositories/perftree/perftree/Cargo.toml stage12027_no_such_case --quiet",
        "returncode": 0,
        "stdout_tail": "running 0 tests\n\ntest result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out",
    },
    {
        "language_family": "rust",
        "repo_family": "tokenizers",
        "cwd": "/data/repositories/tokenizers",
        "selected_verifier_path": "tokenizers/Cargo.toml::stage12027_no_such_case",
        "command": "cargo test --manifest-path /data/repositories/tokenizers/tokenizers/Cargo.toml --features fancy-regex stage12027_no_such_case --quiet",
        "returncode": 0,
        "stdout_tail": "multiple test binaries ran 0 tests; examples include 0 passed, 0 failed, 192 filtered out and 0 passed in integration test binaries",
    },
    {
        "language_family": "c_cpp",
        "repo_family": "benchmark",
        "cwd": "/data/repositories/benchmark",
        "selected_verifier_path": "/data/tmp/stage11872_benchmark_build::stage12027_no_such_benchmark_test",
        "command": "ctest --test-dir /data/tmp/stage11872_benchmark_build -R '^stage12027_no_such_benchmark_test$' --output-on-failure",
        "returncode": 0,
        "stdout_tail": "Test project /data/tmp/stage11872_benchmark_build\nNo tests were found!!!",
    },
    {
        "language_family": "c_cpp",
        "repo_family": "sentencepiece",
        "cwd": "/data/repositories/sentencepiece",
        "selected_verifier_path": "/data/tmp/sentencepiece_stage11737_build::stage12027_no_such_sentencepiece_test",
        "command": "ctest --test-dir /data/tmp/sentencepiece_stage11737_build -R '^stage12027_no_such_sentencepiece_test$' --output-on-failure",
        "returncode": 0,
        "stdout_tail": "Test project /data/tmp/sentencepiece_stage11737_build\nNo tests were found!!!",
    },
    {
        "language_family": "web_js_ts_html",
        "repo_family": "modelcontextprotocol__typescript-sdk",
        "cwd": "/data/repositories/modelcontextprotocol__typescript-sdk",
        "selected_verifier_path": "packages/core/test/shared/uriTemplate.test.ts -t stage12027_no_such_case",
        "command": "./node_modules/.bin/vitest run --globals /data/repositories/modelcontextprotocol__typescript-sdk/packages/core/test/shared/uriTemplate.test.ts -t stage12027_no_such_case",
        "returncode": 0,
        "stdout_tail": "Test Files  1 skipped (1)\n      Tests  38 skipped (38)\n   Duration  255ms (transform 96ms, setup 0ms, import 111ms, tests 0ms, environment 0ms)",
    },
    {
        "language_family": "web_js_ts_html",
        "repo_family": "openclaw__clawhub",
        "cwd": "/data/repositories/openclaw__clawhub",
        "selected_verifier_path": "convex/lib/searchText.test.ts -t stage12027_no_such_case",
        "command": "env VITE_CONVEX_URL=https://example.invalid ./node_modules/.bin/vitest run /data/repositories/openclaw__clawhub/convex/lib/searchText.test.ts -t stage12027_no_such_case",
        "returncode": 0,
        "stdout_tail": "Test Files  1 skipped (1)\n      Tests  14 skipped (14)\n   Duration  253ms (transform 51ms, setup 34ms, import 41ms, tests 0ms, environment 0ms)",
    },
    {
        "language_family": "web_js_ts_html",
        "repo_family": "modelcontextprotocol__typescript-sdk",
        "cwd": "/data/repositories/modelcontextprotocol__typescript-sdk",
        "selected_verifier_path": "packages/core/test/types.test.ts -t stage12027_no_such_case",
        "command": "./node_modules/.bin/vitest run --globals /data/repositories/modelcontextprotocol__typescript-sdk/packages/core/test/types.test.ts -t stage12027_no_such_case",
        "returncode": 0,
        "stdout_tail": "Test Files  1 skipped (1)\n      Tests  56 skipped (56)\n   Duration  563ms (transform 253ms, setup 0ms, import 399ms, tests 0ms, environment 0ms)",
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
    material = f"{obs['repo_family']}::{obs['selected_verifier_path']}::{semantic}"
    row_id = f"stage12027::{obs['repo_family']}::{hashlib.sha1(material.encode()).hexdigest()[:12]}::{semantic}"
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
        "root_lineage_key": f"stage12027::{obs['repo_family']}::{obs['selected_verifier_path']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": obs["repo_family"],
        "repo_family": obs["repo_family"],
        "language_family": obs["language_family"],
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12027_not_exercised_real_filter_train_support_only",
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
            "projection_mode": "stage12027_not_exercised_real_filter_rows",
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
        "stage": "stage12027_not_exercised_real_filter_rows",
        "rows_path": str(ROWS),
        "admitted_rows": len(rows),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "language_counts": dict(sorted(Counter(r["language_family"] for r in rows).items())),
        "status_counts": dict(sorted(Counter(r["observed_verifier_transition"] for r in rows).items())),
        "repo_family_counts": dict(sorted(Counter(r["repo_family"] for r in rows).items())),
        "decision": "admit_not_exercised_real_filter_train_support",
        "claim_boundary": "Rows are train-support only and teach zero/skipped/deselected verifier execution. No model promotion follows from this artifact.",
        "next_stage_recommendation": {
            "stage": "stage12028_transition_support_rollup_v21",
            "action": "Merge real-filter NOT_EXERCISED rows and report remaining Transition-Root-250 floors.",
        },
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
