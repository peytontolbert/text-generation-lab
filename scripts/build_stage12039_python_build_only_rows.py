#!/usr/bin/env python3
"""Materialize diversified Python PASS_CURRENT_BUILD transition rows."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12039_python_build_only_rows")
ROWS = ROOT / "python_build_only_rows.jsonl"
SUMMARY = ROOT / "python_build_only_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12039_python_build_only_rows.json")
LABELS = list("ABCDEFGH")

OBSERVATIONS: list[dict[str, Any]] = [
    {"repo_family": "Aider-AI__aider", "cwd": "/data/repositories/Aider-AI__aider", "selected_verifier_path": "aider/repo.py::py_compile", "command": "python -m py_compile /data/repositories/Aider-AI__aider/aider/repo.py"},
    {"repo_family": "AgentLab", "cwd": "/data/repositories/AgentLab", "selected_verifier_path": "main.py::py_compile", "command": "python -m py_compile /data/repositories/AgentLab/main.py"},
    {"repo_family": "huggingface__smolagents", "cwd": "/data/repositories/huggingface__smolagents", "selected_verifier_path": "src/smolagents/agents.py::py_compile", "command": "python -m py_compile /data/repositories/huggingface__smolagents/src/smolagents/agents.py"},
    {"repo_family": "modelcontextprotocol__python-sdk", "cwd": "/data/repositories/modelcontextprotocol__python-sdk", "selected_verifier_path": "src/mcp/server/session.py::py_compile", "command": "python -m py_compile /data/repositories/modelcontextprotocol__python-sdk/src/mcp/server/session.py"},
    {"repo_family": "openai__openai-agents-python", "cwd": "/data/repositories/openai__openai-agents-python", "selected_verifier_path": "src/agents/agent.py::py_compile", "command": "python -m py_compile /data/repositories/openai__openai-agents-python/src/agents/agent.py"},
    {"repo_family": "SWE-agent__mini-swe-agent", "cwd": "/data/repositories/SWE-agent__mini-swe-agent", "selected_verifier_path": "src/minisweagent/agents/default.py::py_compile", "command": "python -m py_compile /data/repositories/SWE-agent__mini-swe-agent/src/minisweagent/agents/default.py"},
    {"repo_family": "camel-ai__camel", "cwd": "/data/repositories/camel-ai__camel", "selected_verifier_path": "camel/agents/chat_agent.py::py_compile", "command": "python -m py_compile /data/repositories/camel-ai__camel/camel/agents/chat_agent.py"},
    {"repo_family": "openai__openai-agents-python", "cwd": "/data/repositories/openai__openai-agents-python", "selected_verifier_path": "src/agents/run.py::py_compile", "command": "python -m py_compile /data/repositories/openai__openai-agents-python/src/agents/run.py"},
    {"repo_family": "stanfordnlp__dspy", "cwd": "/data/repositories/stanfordnlp__dspy", "selected_verifier_path": "dspy/clients/lm.py::py_compile", "command": "python -m py_compile /data/repositories/stanfordnlp__dspy/dspy/clients/lm.py"},
    {"repo_family": "pydantic__pydantic-ai", "cwd": "/data/repositories/pydantic__pydantic-ai", "selected_verifier_path": "tests/test_utils.py::py_compile", "command": "python -m py_compile /data/repositories/pydantic__pydantic-ai/tests/test_utils.py"},
    {"repo_family": "llama-stack", "cwd": "/data/repositories/llama-stack", "selected_verifier_path": "tests/backward_compat/test_run_config.py::py_compile", "command": "python -m py_compile /data/repositories/llama-stack/tests/backward_compat/test_run_config.py"},
]

REJECTED_PROBES = [
    {"repo_family": "pydantic__pydantic-ai", "command": "python -m py_compile /data/repositories/pydantic__pydantic-ai/pydantic_ai_slim/pydantic_ai/agent.py", "returncode": 1, "reason": "path did not exist"},
    {"repo_family": "llama-stack", "command": "python -m py_compile /data/repositories/llama-stack/llama_stack/core/server/server.py", "returncode": 1, "reason": "path did not exist"},
    {"repo_family": "sentencepiece", "command": "cmake --build /data/tmp/sentencepiece_stage11737_build --target sentencepiece -j2", "returncode": 2, "reason": "invalid target name; valid replacement was probed but not needed for this batch"},
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
        {"label": label, "canonical_value": value, "value": value, "text": text, "role": "verifier_transition_status", "artifact_type": f"{language}_verifier_status"}
        for label, (_, value, text) in zip(LABELS, sorted(keyed))
    ]


def make_row(obs: dict[str, Any]) -> dict[str, Any]:
    semantic = "PASS_CURRENT_BUILD"
    language = "python"
    material = f"{obs['repo_family']}::{obs['selected_verifier_path']}::{semantic}"
    row_id = f"stage12039::{obs['repo_family']}::{hashlib.sha1(material.encode()).hexdigest()[:12]}::{semantic}"
    opts = options(row_id, language)
    target_label = next(o["label"] for o in opts if o["canonical_value"] == semantic)
    stdout_tail = "py_compile completed with return code 0; no test body was executed"
    prompt = "\n".join(
        [
            f"Language: {language}",
            "Perspective: transition_verifier_transition",
            "Task: choose the verifier transition supported by the observed local-source build/compile command.",
            f"Repository family: {obs['repo_family']}",
            f"Source root: {obs['cwd']}",
            f"Selected verifier/build artifact: {obs['selected_verifier_path']}",
            f"Observed command: {obs['command']}",
            "Return code: 0",
            f"Output tail: {stdout_tail}",
            "Options:",
            *[f"{o['label']}. {o['text']}" for o in opts],
            "Answer:",
        ]
    )
    return {
        "row_id": row_id,
        "root_id": row_id,
        "root_lineage_key": f"stage12039::{obs['repo_family']}::{obs['selected_verifier_path']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": obs["repo_family"],
        "repo_family": obs["repo_family"],
        "language_family": language,
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12039_python_build_only_train_support_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "selected_test_anchor": False,
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
        "standalone_projection_source": {
            "projection_mode": "stage12039_python_build_only_rows",
            "selected_verifier_path": obs["selected_verifier_path"],
            "observed_verifier_transition": semantic,
            "tool_or_verifier_observation": {"command": obs["command"], "cwd": obs["cwd"], "returncode": 0, "stdout_tail": stdout_tail, "timed_out": False},
        },
    }


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    rows = [make_row(obs) for obs in OBSERVATIONS]
    write_jsonl(ROWS, rows)
    summary = {
        "stage": "stage12039_python_build_only_rows",
        "rows_path": str(ROWS),
        "admitted_rows": len(rows),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "language_counts": dict(sorted(Counter(r["language_family"] for r in rows).items())),
        "status_counts": dict(sorted(Counter(r["observed_verifier_transition"] for r in rows).items())),
        "repo_family_counts": dict(sorted(Counter(r["repo_family"] for r in rows).items())),
        "rejected_probe_count": len(REJECTED_PROBES),
        "rejected_probes": REJECTED_PROBES,
        "decision": "admit_python_build_only_train_support",
        "claim_boundary": "Rows are train-support only. They close build-status coverage, not model promotion.",
        "next_stage_recommendation": {"stage": "stage12040_transition_support_rollup_v27", "action": "Merge PASS_CURRENT_BUILD rows and report remaining status floors."},
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
