#!/usr/bin/env python3
"""Materialize C++/Rust positive and not-exercised transition observations."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12013_cpp_rust_positive_expansion_rows")
ROWS = ROOT / "cpp_rust_positive_expansion_rows.jsonl"
SUMMARY = ROOT / "cpp_rust_positive_expansion_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12013_cpp_rust_positive_expansion_rows.json")
LABELS = list("ABCDEFGH")

OBSERVATIONS: list[dict[str, Any]] = [
    {
        "language_family": "c_cpp",
        "repo_family": "sentencepiece",
        "cwd": "/data/repositories/sentencepiece",
        "selected_verifier_path": "/data/tmp/sentencepiece_stage11737_build::sentencepiece_test",
        "command": "ctest --test-dir /data/tmp/sentencepiece_stage11737_build -R '^sentencepiece_test$' --output-on-failure",
        "returncode": 0,
        "stdout_tail": "1/1 Test #1: sentencepiece_test ...............   Passed   14.31 sec\n100% tests passed, 0 tests failed out of 1",
        "status": "PASS_CURRENT_BUILD_AND_RUN",
    },
    {
        "language_family": "c_cpp",
        "repo_family": "faiss",
        "cwd": "/data/repositories/faiss",
        "selected_verifier_path": "/data/tmp/stage11766_faiss_cpu_build::ctest -N",
        "command": "ctest --test-dir /data/tmp/stage11766_faiss_cpu_build -N",
        "returncode": 0,
        "stdout_tail": "Test project /data/tmp/stage11766_faiss_cpu_build\n\nTotal Tests: 0",
        "status": "NOT_EXERCISED",
    },
    {
        "language_family": "rust",
        "repo_family": "git",
        "cwd": "/data/repositories/git",
        "selected_verifier_path": "contrib/libgit-rs/Cargo.toml::cargo test --lib",
        "command": "cargo test --manifest-path /data/repositories/git/contrib/libgit-rs/Cargo.toml --lib -- --nocapture",
        "returncode": 0,
        "stdout_tail": "running 1 test\ntest config::tests::load_configs_via_configset ... ok\n\ntest result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out",
        "status": "PASS_TO_PASS",
    },
    {
        "language_family": "rust",
        "repo_family": "git",
        "cwd": "/data/repositories/git",
        "selected_verifier_path": "contrib/libgit-sys/Cargo.toml::cargo test --lib",
        "command": "cargo test --manifest-path /data/repositories/git/contrib/libgit-sys/Cargo.toml --lib -- --nocapture",
        "returncode": 0,
        "stdout_tail": "running 2 tests\ntest tests::sanitized_user_agent_starts_with_git ... ok\ntest tests::user_agent_starts_with_git ... ok\n\ntest result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out",
        "status": "PASS_TO_PASS",
    },
    {
        "language_family": "rust",
        "repo_family": "tokenizers",
        "cwd": "/data/repositories/tokenizers",
        "selected_verifier_path": "tokenizers/Cargo.toml::cargo test --lib --features fancy-regex",
        "command": "cargo test --manifest-path /data/repositories/tokenizers/tokenizers/Cargo.toml --lib --features fancy-regex -- --nocapture",
        "returncode": 0,
        "stdout_tail": "test result: ok. 192 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.11s",
        "status": "PASS_TO_PASS",
    },
    {
        "language_family": "rust",
        "repo_family": "perftree",
        "cwd": "/data/repositories/perftree",
        "selected_verifier_path": "perftree-cli/Cargo.toml::cargo test --bins",
        "command": "cargo test --manifest-path /data/repositories/perftree/perftree-cli/Cargo.toml --bins -- --nocapture",
        "returncode": 0,
        "stdout_tail": "running 0 tests\n\ntest result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out",
        "status": "NOT_EXERCISED",
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
    semantic = obs["status"]
    material = f"{obs['repo_family']}::{obs['selected_verifier_path']}::{semantic}"
    row_id = f"stage12013::{obs['repo_family']}::{hashlib.sha1(material.encode()).hexdigest()[:12]}::{semantic}"
    opts = options(row_id, obs["language_family"])
    target_label = next(o["label"] for o in opts if o["canonical_value"] == semantic)
    prompt = "\n".join(
        [
            f"Language: {obs['language_family']}",
            "Perspective: transition_verifier_transition",
            "Task: choose the verifier transition supported by the observed local-source command.",
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
        "root_lineage_key": f"stage12013::{obs['repo_family']}::{obs['selected_verifier_path']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": obs["repo_family"],
        "repo_family": obs["repo_family"],
        "language_family": obs["language_family"],
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12013_cpp_rust_positive_expansion_train_support_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "selected_test_anchor": True,
        "verifier_anchor": semantic != "INSUFFICIENT_EVIDENCE",
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
            "projection_mode": "stage12013_cpp_rust_positive_expansion_rows",
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
        "stage": "stage12013_cpp_rust_positive_expansion_rows",
        "rows_path": str(ROWS),
        "admitted_rows": len(rows),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "language_counts": dict(sorted(Counter(r["language_family"] for r in rows).items())),
        "status_counts": dict(sorted(Counter(r["observed_verifier_transition"] for r in rows).items())),
        "repo_family_counts": dict(sorted(Counter(r["repo_family"] for r in rows).items())),
        "decision": "admit_cpp_rust_positive_expansion_train_support",
        "claim_boundary": "Rows are train-support only. Positive rows are executable local verifier evidence; no model promotion follows from this artifact.",
        "next_stage_recommendation": {"stage": "stage12014_transition_support_rollup_v14", "action": "Merge C++/Rust expansion rows and report remaining Transition-Root-250 floors."},
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
