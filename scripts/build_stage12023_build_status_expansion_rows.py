#!/usr/bin/env python3
"""Materialize build-only and paired build+run transition observations."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12023_build_status_expansion_rows")
ROWS = ROOT / "build_status_expansion_rows.jsonl"
SUMMARY = ROOT / "build_status_expansion_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12023_build_status_expansion_rows.json")
LABELS = list("ABCDEFGH")

OBSERVATIONS: list[dict[str, Any]] = [
    {
        "status": "PASS_CURRENT_BUILD",
        "language_family": "python",
        "repo_family": "einops",
        "cwd": "/data/repositories/einops",
        "selected_verifier_path": "einops/einops.py::py_compile",
        "command": "python -m py_compile /data/repositories/einops/einops/einops.py",
        "returncode": 0,
        "stdout_tail": "py_compile completed with return code 0; no test body was executed",
    },
    {
        "status": "PASS_CURRENT_BUILD",
        "language_family": "python",
        "repo_family": "lastmile-ai__mcp-agent",
        "cwd": "/data/repositories/lastmile-ai__mcp-agent",
        "selected_verifier_path": "src/mcp_agent/config.py::py_compile",
        "command": "python -m py_compile /data/repositories/lastmile-ai__mcp-agent/src/mcp_agent/config.py",
        "returncode": 0,
        "stdout_tail": "py_compile completed with return code 0; no test body was executed",
    },
    {
        "status": "PASS_CURRENT_BUILD",
        "language_family": "rust",
        "repo_family": "tokenizers",
        "cwd": "/data/repositories/tokenizers",
        "selected_verifier_path": "tokenizers/Cargo.toml::cargo check --features fancy-regex",
        "command": "cargo check --manifest-path /data/repositories/tokenizers/tokenizers/Cargo.toml --features fancy-regex --quiet",
        "returncode": 0,
        "stdout_tail": "cargo check completed with return code 0; no test body was executed",
    },
    {
        "status": "PASS_CURRENT_BUILD",
        "language_family": "rust",
        "repo_family": "perftree",
        "cwd": "/data/repositories/perftree",
        "selected_verifier_path": "perftree/Cargo.toml::cargo check",
        "command": "cargo check --manifest-path /data/repositories/perftree/perftree/Cargo.toml --quiet",
        "returncode": 0,
        "stdout_tail": "cargo check completed with return code 0; no test body was executed",
    },
    {
        "status": "PASS_CURRENT_BUILD",
        "language_family": "rust",
        "repo_family": "perftree",
        "cwd": "/data/repositories/perftree",
        "selected_verifier_path": "perftree-cli/Cargo.toml::cargo check",
        "command": "cargo check --manifest-path /data/repositories/perftree/perftree-cli/Cargo.toml --quiet",
        "returncode": 0,
        "stdout_tail": "cargo check completed with return code 0; no test body was executed",
    },
    {
        "status": "PASS_CURRENT_BUILD",
        "language_family": "web_js_ts_html",
        "repo_family": "modelcontextprotocol__typescript-sdk",
        "cwd": "/data/repositories/modelcontextprotocol__typescript-sdk",
        "selected_verifier_path": "@modelcontextprotocol/core::typecheck",
        "command": "pnpm --dir /data/repositories/modelcontextprotocol__typescript-sdk --filter @modelcontextprotocol/core run typecheck",
        "returncode": 0,
        "stdout_tail": "@modelcontextprotocol/core typecheck: tsgo -p tsconfig.json --noEmit completed successfully; no test body was executed",
    },
    {
        "status": "PASS_CURRENT_BUILD",
        "language_family": "web_js_ts_html",
        "repo_family": "modelcontextprotocol__typescript-sdk",
        "cwd": "/data/repositories/modelcontextprotocol__typescript-sdk",
        "selected_verifier_path": "@modelcontextprotocol/client::typecheck",
        "command": "pnpm --dir /data/repositories/modelcontextprotocol__typescript-sdk --filter @modelcontextprotocol/client run typecheck",
        "returncode": 0,
        "stdout_tail": "@modelcontextprotocol/client typecheck: tsgo -p tsconfig.json --noEmit completed successfully; no test body was executed",
    },
    {
        "status": "PASS_CURRENT_BUILD",
        "language_family": "web_js_ts_html",
        "repo_family": "modelcontextprotocol__typescript-sdk",
        "cwd": "/data/repositories/modelcontextprotocol__typescript-sdk",
        "selected_verifier_path": "@modelcontextprotocol/server::typecheck",
        "command": "pnpm --dir /data/repositories/modelcontextprotocol__typescript-sdk --filter @modelcontextprotocol/server run typecheck",
        "returncode": 0,
        "stdout_tail": "@modelcontextprotocol/server typecheck: tsgo -p tsconfig.json --noEmit completed successfully; no test body was executed",
    },
    {
        "status": "PASS_CURRENT_BUILD",
        "language_family": "c_cpp",
        "repo_family": "benchmark",
        "cwd": "/data/repositories/benchmark",
        "selected_verifier_path": "benchmark::cmake-build-target",
        "command": "cmake --build /data/tmp/stage11872_benchmark_build --target benchmark -j2",
        "returncode": 0,
        "stdout_tail": "[100%] Built target benchmark",
    },
    {
        "status": "PASS_CURRENT_BUILD",
        "language_family": "c_cpp",
        "repo_family": "benchmark",
        "cwd": "/data/repositories/benchmark",
        "selected_verifier_path": "filter_test::cmake-build-target",
        "command": "cmake --build /data/tmp/stage11872_benchmark_build --target filter_test -j2",
        "returncode": 0,
        "stdout_tail": "[ 90%] Built target benchmark\n[100%] Built target filter_test",
    },
    {
        "status": "PASS_CURRENT_BUILD_AND_RUN",
        "language_family": "c_cpp",
        "repo_family": "sentencepiece",
        "cwd": "/data/repositories/sentencepiece",
        "selected_verifier_path": "sentencepiece default cmake build + sentencepiece_test",
        "command": "cmake --build /data/tmp/sentencepiece_stage11737_build -j2 && ctest --test-dir /data/tmp/sentencepiece_stage11737_build -R '^sentencepiece_test$' --output-on-failure",
        "returncode": 0,
        "stdout_tail": "Build completed through [100%] Built target spm_test; CTest sentencepiece_test passed with 100% tests passed, 0 tests failed out of 1",
    },
]

REJECTED_PROBES = [
    {
        "repo_family": "openclaw__clawhub",
        "command": "pnpm --dir /data/repositories/openclaw__clawhub run check",
        "returncode": 1,
        "reason": "missing bun runtime, not admissible as PASS_CURRENT_BUILD",
    },
    {
        "repo_family": "git",
        "command": "cargo check --manifest-path /data/repositories/git/contrib/libgit-rs/Cargo.toml --quiet",
        "returncode": 101,
        "reason": "libgit-sys build failed under warnings-as-errors, not a current build pass",
    },
    {
        "repo_family": "tokenizers",
        "command": "cargo check --manifest-path /data/repositories/tokenizers/tokenizers/Cargo.toml --no-default-features --quiet",
        "returncode": 101,
        "reason": "invalid feature surface requires onig or fancy-regex, not a current build pass",
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
    semantic = obs["status"]
    material = f"{obs['repo_family']}::{obs['selected_verifier_path']}::{semantic}"
    row_id = f"stage12023::{obs['repo_family']}::{hashlib.sha1(material.encode()).hexdigest()[:12]}::{semantic}"
    opts = options(row_id, obs["language_family"])
    target_label = next(o["label"] for o in opts if o["canonical_value"] == semantic)
    prompt = "\n".join(
        [
            f"Language: {obs['language_family']}",
            "Perspective: transition_verifier_transition",
            "Task: choose the verifier transition supported by the observed local-source command.",
            f"Repository family: {obs['repo_family']}",
            f"Source root: {obs['cwd']}",
            f"Selected verifier/build artifact: {obs['selected_verifier_path']}",
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
        "root_lineage_key": f"stage12023::{obs['repo_family']}::{obs['selected_verifier_path']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": obs["repo_family"],
        "repo_family": obs["repo_family"],
        "language_family": obs["language_family"],
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12023_build_status_expansion_train_support_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "selected_test_anchor": semantic == "PASS_CURRENT_BUILD_AND_RUN",
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
            "projection_mode": "stage12023_build_status_expansion_rows",
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
        "stage": "stage12023_build_status_expansion_rows",
        "rows_path": str(ROWS),
        "admitted_rows": len(rows),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "language_counts": dict(sorted(Counter(r["language_family"] for r in rows).items())),
        "status_counts": dict(sorted(Counter(r["observed_verifier_transition"] for r in rows).items())),
        "repo_family_counts": dict(sorted(Counter(r["repo_family"] for r in rows).items())),
        "rejected_probe_count": len(REJECTED_PROBES),
        "rejected_probes": REJECTED_PROBES,
        "decision": "admit_build_status_expansion_train_support",
        "claim_boundary": "Rows are train-support only. Rejected probes are documented but not emitted as training rows.",
        "next_stage_recommendation": {
            "stage": "stage12024_transition_support_rollup_v19",
            "action": "Merge build-status rows and report remaining Transition-Root-250 floors.",
        },
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
