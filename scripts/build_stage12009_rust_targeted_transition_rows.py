#!/usr/bin/env python3
"""Materialize targeted Rust verifier observations into transition rows."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12009_rust_targeted_transition_rows")
ROWS = ROOT / "rust_targeted_transition_rows.jsonl"
SUMMARY = ROOT / "rust_targeted_transition_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12009_rust_targeted_transition_rows.json")
LABELS = list("ABCDEFGH")

OBSERVATIONS: list[dict[str, Any]] = [
    {
        "repo_family": "git",
        "cwd": "/data/repositories/git",
        "selected_verifier_path": "Cargo.toml::cargo test --lib",
        "command": "cargo test --manifest-path /data/repositories/git/Cargo.toml --lib -- --nocapture",
        "returncode": 0,
        "stdout_tail": "running 2 tests\ntest varint::tests::test_encode_varint ... ok\ntest varint::tests::test_decode_varint ... ok\n\ntest result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out",
        "status": "PASS_TO_PASS",
    },
    {
        "repo_family": "perftree",
        "cwd": "/data/repositories/perftree",
        "selected_verifier_path": "perftree/Cargo.toml::cargo test --lib",
        "command": "cargo test --manifest-path /data/repositories/perftree/perftree/Cargo.toml --lib -- --nocapture",
        "returncode": 0,
        "stdout_tail": "running 0 tests\n\ntest result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out",
        "status": "NOT_EXERCISED",
    },
    {
        "repo_family": "tokenizers",
        "cwd": "/data/repositories/tokenizers",
        "selected_verifier_path": "tokenizers/Cargo.toml::cargo test --lib --no-default-features",
        "command": "cargo test --manifest-path /data/repositories/tokenizers/tokenizers/Cargo.toml --lib --no-default-features -- --nocapture",
        "returncode": 101,
        "stdout_tail": "compile_error!(\"One of the `onig`, or `fancy-regex` features must be enabled\"); error: could not compile `tokenizers` (lib test) due to previous errors",
        "status": "INSUFFICIENT_EVIDENCE",
    },
    {
        "repo_family": "candle",
        "cwd": "/data/repositories/candle",
        "selected_verifier_path": "candle-datasets/Cargo.toml::cargo test --lib",
        "command": "cargo test --manifest-path /data/repositories/candle/candle-datasets/Cargo.toml --lib -- --nocapture",
        "returncode": 101,
        "stdout_tail": "error[E0277]: the trait bound `half::bf16: SampleBorrow<half::bf16>` is not satisfied; error: could not compile `candle-core` (lib) due to previous errors",
        "status": "INSUFFICIENT_EVIDENCE",
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


def options(row_id: str) -> list[dict[str, str]]:
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
            "artifact_type": "rust_cargo_verifier_status",
        }
        for label, (_, value, text) in zip(LABELS, sorted(keyed))
    ]


def make_row(obs: dict[str, Any]) -> dict[str, Any]:
    semantic = obs["status"]
    material = f"{obs['repo_family']}::{obs['selected_verifier_path']}::{semantic}"
    row_id = f"stage12009::{obs['repo_family']}::{hashlib.sha1(material.encode()).hexdigest()[:12]}::{semantic}"
    opts = options(row_id)
    target_label = next(o["label"] for o in opts if o["canonical_value"] == semantic)
    prompt = "\n".join(
        [
            "Language: rust",
            "Perspective: transition_verifier_transition",
            "Task: choose the verifier transition supported by the observed local-source Cargo command.",
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
        "root_lineage_key": f"stage12009::{obs['repo_family']}::{obs['selected_verifier_path']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": obs["repo_family"],
        "repo_family": obs["repo_family"],
        "language_family": "rust",
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12009_rust_targeted_train_support_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "selected_test_anchor": semantic != "INSUFFICIENT_EVIDENCE",
        "verifier_anchor": semantic not in {"INSUFFICIENT_EVIDENCE"},
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
            "projection_mode": "stage12009_rust_targeted_transition_rows",
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
        "stage": "stage12009_rust_targeted_transition_rows",
        "rows_path": str(ROWS),
        "admitted_rows": len(rows),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "language_counts": dict(Counter(r["language_family"] for r in rows)),
        "status_counts": dict(sorted(Counter(r["observed_verifier_transition"] for r in rows).items())),
        "repo_family_counts": dict(sorted(Counter(r["repo_family"] for r in rows).items())),
        "decision": "admit_rust_targeted_train_support",
        "claim_boundary": "Rust rows are train-support only. Underhydrated compile rows are negative status supervision, not positive verifier success.",
        "next_stage_recommendation": {
            "stage": "stage12010_transition_support_rollup_v12",
            "action": "Merge targeted Rust rows and report remaining Transition-Root-250 floors.",
        },
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
