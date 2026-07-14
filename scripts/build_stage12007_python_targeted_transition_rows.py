#!/usr/bin/env python3
"""Materialize targeted Python verifier observations into transition rows."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12007_python_targeted_transition_rows")
ROWS = ROOT / "python_targeted_transition_rows.jsonl"
SUMMARY = ROOT / "python_targeted_transition_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12007_python_targeted_transition_rows.json")
LABELS = list("ABCDEFGH")

OBSERVATIONS: list[dict[str, Any]] = [
    {
        "repo_family": "einops",
        "cwd": "/data/repositories/einops",
        "selected_verifier_path": "einops/tests/test_parsing.py",
        "command": "python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12007_pytest_cache einops/tests/test_parsing.py",
        "returncode": 0,
        "stdout_tail": ".... [100%]\n4 passed in 0.38s",
        "status": "PASS_TO_PASS",
    },
    {
        "repo_family": "einops",
        "cwd": "/data/repositories/einops",
        "selected_verifier_path": "einops/tests/test_packing.py",
        "command": "env EINOPS_TEST_BACKENDS=numpy python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12007_pytest_cache einops/tests/test_packing.py",
        "returncode": 0,
        "stdout_tail": ".... [100%]\n4 passed in 0.49s",
        "status": "PASS_TO_PASS",
    },
    {
        "repo_family": "code-review-swarm",
        "cwd": "/data/repositories/code-review-swarm",
        "selected_verifier_path": "tests/test_api.py",
        "command": "python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12007_pytest_cache tests/test_api.py",
        "returncode": 2,
        "stdout_tail": "ModuleNotFoundError: No module named 'swarms'",
        "status": "INSUFFICIENT_EVIDENCE",
    },
    {
        "repo_family": "modelcontextprotocol__python-sdk",
        "cwd": "/data/repositories/modelcontextprotocol__python-sdk",
        "selected_verifier_path": "tests/issues/test_342_base64_encoding.py",
        "command": "env PYTHONPATH=/data/repositories/modelcontextprotocol__python-sdk/src python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12007_pytest_cache tests/issues/test_342_base64_encoding.py",
        "returncode": 2,
        "stdout_tail": "TypeError: _TypedDictMeta.__new__() got an unexpected keyword argument 'extra_items'",
        "status": "INSUFFICIENT_EVIDENCE",
    },
    {
        "repo_family": "gym-pybullet-drones",
        "cwd": "/data/repositories/gym-pybullet-drones",
        "selected_verifier_path": "tests/test_build.py",
        "command": "python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12007_pytest_cache tests/test_build.py",
        "returncode": 1,
        "stdout_tail": "ModuleNotFoundError: No module named 'gymnasium'",
        "status": "INSUFFICIENT_EVIDENCE",
    },
    {
        "repo_family": "huggingface__smolagents",
        "cwd": "/data/repositories/huggingface__smolagents",
        "selected_verifier_path": "tests/test_import.py",
        "command": "env PYTHONPATH=/data/repositories/huggingface__smolagents/src python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12007_pytest_cache tests/test_import.py",
        "returncode": 1,
        "stdout_tail": "FileNotFoundError: [Errno 2] No such file or directory: 'uv'",
        "status": "INSUFFICIENT_EVIDENCE",
    },
    {
        "repo_family": "AgentLab",
        "cwd": "/data/repositories/AgentLab",
        "selected_verifier_path": "tests/analyze/test_overlay_utils.py",
        "command": "env PYTHONPATH=/data/repositories/AgentLab/src python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12007_pytest_cache tests/analyze/test_overlay_utils.py",
        "returncode": 2,
        "stdout_tail": "ModuleNotFoundError: No module named 'browsergym'",
        "status": "INSUFFICIENT_EVIDENCE",
    },
    {
        "repo_family": "rembg",
        "cwd": "/data/repositories/rembg",
        "selected_verifier_path": "tests/test_remove.py",
        "command": "python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12007_pytest_cache tests/test_remove.py",
        "returncode": 2,
        "stdout_tail": "ModuleNotFoundError: No module named 'imagehash'",
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
            "artifact_type": "python_pytest_verifier_status",
        }
        for label, (_, value, text) in zip(LABELS, sorted(keyed))
    ]


def make_row(obs: dict[str, Any]) -> dict[str, Any]:
    semantic = obs["status"]
    root_material = f"{obs['repo_family']}::{obs['selected_verifier_path']}::{semantic}"
    row_id = f"stage12007::{obs['repo_family']}::{hashlib.sha1(root_material.encode()).hexdigest()[:12]}::{semantic}"
    opts = options(row_id)
    target_label = next(o["label"] for o in opts if o["canonical_value"] == semantic)
    prompt = "\n".join(
        [
            "Language: python",
            "Perspective: transition_verifier_transition",
            "Task: choose the verifier transition supported by the observed local-source pytest command.",
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
        "root_lineage_key": f"stage12007::{obs['repo_family']}::{obs['selected_verifier_path']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": obs["repo_family"],
        "repo_family": obs["repo_family"],
        "language_family": "python",
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12007_python_targeted_train_support_only",
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
        "target": {
            "bounded_choice_target_label": target_label,
            "decoder_text": target_label,
            "semantic_value": semantic,
        },
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
            "projection_mode": "stage12007_python_targeted_transition_rows",
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
        "stage": "stage12007_python_targeted_transition_rows",
        "rows_path": str(ROWS),
        "admitted_rows": len(rows),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "language_counts": dict(Counter(r["language_family"] for r in rows)),
        "status_counts": dict(sorted(Counter(r["observed_verifier_transition"] for r in rows).items())),
        "repo_family_counts": dict(sorted(Counter(r["repo_family"] for r in rows).items())),
        "decision": "admit_python_targeted_train_support",
        "claim_boundary": "Python rows are train-support only. Underhydrated rows are negative status supervision, not positive verifier success.",
        "next_stage_recommendation": {
            "stage": "stage12008_transition_support_rollup_v11",
            "action": "Merge targeted Python rows and report remaining Transition-Root-250 floors.",
        },
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
