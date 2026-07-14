#!/usr/bin/env python3
"""Materialize additional PASS_TO_PASS-focused transition observations."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12011_pass_to_pass_expansion_rows")
ROWS = ROOT / "pass_to_pass_expansion_rows.jsonl"
SUMMARY = ROOT / "pass_to_pass_expansion_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12011_pass_to_pass_expansion_rows.json")
LABELS = list("ABCDEFGH")

OBSERVATIONS: list[dict[str, Any]] = [
    {
        "language_family": "python",
        "repo_family": "lastmile-ai__mcp-agent",
        "cwd": "/data/repositories/lastmile-ai__mcp-agent",
        "selected_verifier_path": "tests/utils/test_mime_utils.py",
        "command": "env PYTHONPATH=/data/repositories/lastmile-ai__mcp-agent/src python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12011_pytest_cache tests/utils/test_mime_utils.py",
        "returncode": 0,
        "stdout_tail": ".................................... [100%]\n36 passed in 0.36s",
        "status": "PASS_TO_PASS",
    },
    {
        "language_family": "python",
        "repo_family": "llama-models",
        "cwd": "/data/repositories/llama-models",
        "selected_verifier_path": "models/llama3/tests/api/test_tokenizer.py",
        "command": "env PYTHONPATH=/data/repositories/llama-models python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12011_pytest_cache models/llama3/tests/api/test_tokenizer.py",
        "returncode": 0,
        "stdout_tail": "..... [100%]\n5 passed in 0.78s",
        "status": "PASS_TO_PASS",
    },
    {
        "language_family": "python",
        "repo_family": "lastmile-ai__mcp-agent",
        "cwd": "/data/repositories/lastmile-ai__mcp-agent",
        "selected_verifier_path": "tests/utils/test_content_utils.py",
        "command": "env PYTHONPATH=/data/repositories/lastmile-ai__mcp-agent/src python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12011_pytest_cache tests/utils/test_content_utils.py",
        "returncode": 2,
        "stdout_tail": "ModuleNotFoundError: No module named 'mcp'",
        "status": "INSUFFICIENT_EVIDENCE",
    },
    {
        "language_family": "python",
        "repo_family": "llama-stack",
        "cwd": "/data/repositories/llama-stack",
        "selected_verifier_path": "tests/unit/server/test_replace_env_vars.py",
        "command": "env PYTHONPATH=/data/repositories/llama-stack python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12011_pytest_cache tests/unit/server/test_replace_env_vars.py",
        "returncode": 1,
        "stdout_tail": "ImportError: Error importing plugin \"tests.unit.fixtures\": No module named 'llama_stack'",
        "status": "INSUFFICIENT_EVIDENCE",
    },
    {
        "language_family": "python",
        "repo_family": "openai__openai-agents-python",
        "cwd": "/data/repositories/openai__openai-agents-python",
        "selected_verifier_path": "tests/extensions/memory/test_memory_imports.py",
        "command": "env PYTHONPATH=/data/repositories/openai__openai-agents-python/src python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12011_pytest_cache tests/extensions/memory/test_memory_imports.py",
        "returncode": 4,
        "stdout_tail": "ModuleNotFoundError: No module named 'openai'",
        "status": "INSUFFICIENT_EVIDENCE",
    },
    {
        "language_family": "python",
        "repo_family": "x-transformers",
        "cwd": "/data/repositories/x-transformers",
        "selected_verifier_path": "tests/test_x_transformers.py",
        "command": "env PYTHONPATH=/data/repositories/x-transformers python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12011_pytest_cache tests/test_x_transformers.py",
        "returncode": 2,
        "stdout_tail": "ImportError: cannot import name 'nn' from 'torch' (unknown location)",
        "status": "INSUFFICIENT_EVIDENCE",
    },
    {
        "language_family": "python",
        "repo_family": "hyper-connections",
        "cwd": "/data/repositories/hyper-connections",
        "selected_verifier_path": "tests/test_hyper_connections.py",
        "command": "env PYTHONPATH=/data/repositories/hyper-connections python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12011_pytest_cache tests/test_hyper_connections.py",
        "returncode": 2,
        "stdout_tail": "ImportError: cannot import name 'nn' from 'torch' (unknown location)",
        "status": "INSUFFICIENT_EVIDENCE",
    },
    {
        "language_family": "python",
        "repo_family": "titans-pytorch",
        "cwd": "/data/repositories/titans-pytorch",
        "selected_verifier_path": "tests/test_titans.py",
        "command": "env PYTHONPATH=/data/repositories/titans-pytorch python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12011_pytest_cache tests/test_titans.py",
        "returncode": 2,
        "stdout_tail": "ImportError: cannot import name 'nn' from 'torch' (unknown location)",
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
    row_id = f"stage12011::{obs['repo_family']}::{hashlib.sha1(material.encode()).hexdigest()[:12]}::{semantic}"
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
        "root_lineage_key": f"stage12011::{obs['repo_family']}::{obs['selected_verifier_path']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": obs["repo_family"],
        "repo_family": obs["repo_family"],
        "language_family": obs["language_family"],
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12011_pass_to_pass_expansion_train_support_only",
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
            "projection_mode": "stage12011_pass_to_pass_expansion_rows",
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
        "stage": "stage12011_pass_to_pass_expansion_rows",
        "rows_path": str(ROWS),
        "admitted_rows": len(rows),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "language_counts": dict(sorted(Counter(r["language_family"] for r in rows).items())),
        "status_counts": dict(sorted(Counter(r["observed_verifier_transition"] for r in rows).items())),
        "repo_family_counts": dict(sorted(Counter(r["repo_family"] for r in rows).items())),
        "decision": "admit_pass_to_pass_expansion_train_support",
        "claim_boundary": "Rows are train-support only. Positive PASS_TO_PASS rows are executable verifier evidence; underhydrated rows are negative status supervision.",
        "next_stage_recommendation": {"stage": "stage12012_transition_support_rollup_v13", "action": "Merge expansion rows and report remaining Transition-Root-250 floors."},
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
