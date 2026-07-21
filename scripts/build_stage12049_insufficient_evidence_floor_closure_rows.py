#!/usr/bin/env python3
"""Materialize explicit missing-context INSUFFICIENT_EVIDENCE floor-closure rows."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12049_insufficient_evidence_floor_closure_rows")
ROWS = ROOT / "insufficient_evidence_floor_closure_rows.jsonl"
SUMMARY = ROOT / "insufficient_evidence_floor_closure_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12049_insufficient_evidence_floor_closure_rows.json")
LABELS = list("ABCDEFGH")

OBSERVATIONS: list[dict[str, Any]] = [
    {
        "language_family": "python",
        "repo_family": "action-transformer",
        "cwd": "/data/repositories/action-transformer",
        "selected_verifier_path": "tests/test_action_transformer.py",
        "command": "timeout 20 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12049_pytest_cache /data/repositories/action-transformer/tests/test_action_transformer.py",
        "returncode": 2,
        "subreason": "DEPENDENCY_UNAVAILABLE",
        "stdout_tail": "ModuleNotFoundError: No module named 'torch.nn'; collection interrupted before verifier body executed",
    },
    {
        "language_family": "python",
        "repo_family": "action-transformer",
        "cwd": "/data/repositories/action-transformer",
        "selected_verifier_path": "tests/test_hierarchical.py",
        "command": "timeout 20 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12049_pytest_cache /data/repositories/action-transformer/tests/test_hierarchical.py",
        "returncode": 2,
        "subreason": "DEPENDENCY_UNAVAILABLE",
        "stdout_tail": "ModuleNotFoundError: No module named 'torch.nn'; collection interrupted before verifier body executed",
    },
    {
        "language_family": "python",
        "repo_family": "SWE-agent__SWE-agent",
        "cwd": "/data/repositories/SWE-agent__SWE-agent",
        "selected_verifier_path": "tests/test_parsing.py",
        "command": "timeout 20 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12049_pytest_cache /data/repositories/SWE-agent__SWE-agent/tests/test_parsing.py",
        "returncode": 4,
        "subreason": "DEPENDENCY_UNAVAILABLE",
        "stdout_tail": "ImportError while loading conftest; ModuleNotFoundError: No module named 'swerex'",
    },
    {
        "language_family": "python",
        "repo_family": "SWE-agent__mini-swe-agent",
        "cwd": "/data/repositories/SWE-agent__mini-swe-agent",
        "selected_verifier_path": "tests/test_fire.py",
        "command": "timeout 20 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12049_pytest_cache /data/repositories/SWE-agent__mini-swe-agent/tests/test_fire.py",
        "returncode": 4,
        "subreason": "DEPENDENCY_UNAVAILABLE",
        "stdout_tail": "ImportError while loading conftest; ModuleNotFoundError: No module named 'minisweagent'",
    },
    {
        "language_family": "python",
        "repo_family": "AgentLab",
        "cwd": "/data/repositories/AgentLab",
        "selected_verifier_path": "tests/test_main.py",
        "command": "timeout 20 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12049_pytest_cache /data/repositories/AgentLab/tests/test_main.py",
        "returncode": 1,
        "subreason": "DEPENDENCY_UNAVAILABLE",
        "stdout_tail": "ModuleNotFoundError: No module named 'agentlab'; test cannot establish selected verifier behavior",
    },
    {
        "language_family": "python",
        "repo_family": "AgentLab",
        "cwd": "/data/repositories/AgentLab",
        "selected_verifier_path": "tests/llm/test_chat_api.py",
        "command": "timeout 20 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12049_pytest_cache /data/repositories/AgentLab/tests/llm/test_chat_api.py",
        "returncode": 2,
        "subreason": "DEPENDENCY_UNAVAILABLE",
        "stdout_tail": "ModuleNotFoundError: No module named 'agentlab'; collection interrupted before verifier body executed",
    },
    {
        "language_family": "python",
        "repo_family": "lastmile-ai__mcp-agent",
        "cwd": "/data/repositories/lastmile-ai__mcp-agent",
        "selected_verifier_path": "tests/config/test_env_settings.py",
        "command": "timeout 20 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12049_pytest_cache /data/repositories/lastmile-ai__mcp-agent/tests/config/test_env_settings.py",
        "returncode": 2,
        "subreason": "DEPENDENCY_UNAVAILABLE",
        "stdout_tail": "ModuleNotFoundError: No module named 'mcp_agent'; collection interrupted before verifier body executed",
    },
    {
        "language_family": "python",
        "repo_family": "lastmile-ai__mcp-agent",
        "cwd": "/data/repositories/lastmile-ai__mcp-agent",
        "selected_verifier_path": "tests/test_config_exporters.py",
        "command": "timeout 20 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12049_pytest_cache /data/repositories/lastmile-ai__mcp-agent/tests/test_config_exporters.py",
        "returncode": 2,
        "subreason": "DEPENDENCY_UNAVAILABLE",
        "stdout_tail": "ModuleNotFoundError: No module named 'mcp_agent'; collection interrupted before verifier body executed",
    },
    {
        "language_family": "web_js_ts_html",
        "repo_family": "OpenHands__OpenHands",
        "cwd": "/data/repositories/OpenHands__OpenHands",
        "selected_verifier_path": "frontend/__tests__/parse-pr-url.test.ts",
        "command": "timeout 20 ./node_modules/.bin/vitest run --globals frontend/__tests__/parse-pr-url.test.ts",
        "returncode": 127,
        "subreason": "DEPENDENCY_UNAVAILABLE",
        "stdout_tail": "timeout: failed to run command './node_modules/.bin/vitest': No such file or directory",
    },
    {
        "language_family": "web_js_ts_html",
        "repo_family": "openclaw__clawhub",
        "cwd": "/data/repositories/openclaw__clawhub",
        "selected_verifier_path": "package.json#typecheck",
        "command": "timeout 20 npm run typecheck -- --pretty false",
        "returncode": 1,
        "subreason": "MISSING_SELECTED_TEST",
        "stdout_tail": "npm error Missing script: \"typecheck\"; requested verifier script is not available in package.json",
    },
    {
        "language_family": "python",
        "repo_family": "SWE-agent__SWE-ReX",
        "cwd": "/data/repositories/SWE-agent__SWE-ReX",
        "selected_verifier_path": "tests/test_runtime.py",
        "command": "timeout 20 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12049_pytest_cache /data/repositories/SWE-agent__SWE-ReX/tests/test_runtime.py",
        "returncode": 4,
        "subreason": "DEPENDENCY_UNAVAILABLE",
        "stdout_tail": "ImportError while loading conftest; ModuleNotFoundError: No module named 'swerex'",
    },
    {
        "language_family": "python",
        "repo_family": "WorkArena",
        "cwd": "/data/repositories/WorkArena",
        "selected_verifier_path": "tests/test_api.py",
        "command": "timeout 20 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12049_pytest_cache /data/repositories/WorkArena/tests/test_api.py",
        "returncode": 2,
        "subreason": "DEPENDENCY_UNAVAILABLE",
        "stdout_tail": "ModuleNotFoundError: No module named 'browsergym'; collection interrupted before verifier body executed",
    },
    {
        "language_family": "python",
        "repo_family": "OpenHands__software-agent-sdk",
        "cwd": "/data/repositories/OpenHands__software-agent-sdk",
        "selected_verifier_path": "tests/agent_server/test_api.py",
        "command": "timeout 20 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12049_pytest_cache /data/repositories/OpenHands__software-agent-sdk/tests/agent_server/test_api.py",
        "returncode": 4,
        "subreason": "DEPENDENCY_UNAVAILABLE",
        "stdout_tail": "ImportError while loading conftest; ModuleNotFoundError: No module named 'openhands'",
    },
    {
        "language_family": "python",
        "repo_family": "llama-stack",
        "cwd": "/data/repositories/llama-stack",
        "selected_verifier_path": "tests/backward_compat/test_run_config.py",
        "command": "timeout 20 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12049_pytest_cache /data/repositories/llama-stack/tests/backward_compat/test_run_config.py",
        "returncode": 2,
        "subreason": "DEPENDENCY_UNAVAILABLE",
        "stdout_tail": "ModuleNotFoundError: No module named 'llama_stack'; collection interrupted before verifier body executed",
    },
]

TRANSITION_TEXT = {
    "PASS_TO_PASS": "focused verifier executed from local source and passed",
    "PASS_CURRENT_BUILD_AND_RUN": "build and runnable verifier both passed",
    "PASS_CURRENT_BUILD": "build or collection passed but runnable verifier body did not execute",
    "FAIL_TO_PASS": "controlled broken state failed and restored or repaired source passed",
    "NOT_EXERCISED": "command did not exercise or collect the selected verifier",
    "INSUFFICIENT_EVIDENCE": "attempted verifier could not run because required context or dependency was unavailable",
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
    semantic = "INSUFFICIENT_EVIDENCE"
    material = f"{obs['repo_family']}::{obs['selected_verifier_path']}::{obs['subreason']}::{semantic}"
    row_id = f"stage12049::{obs['repo_family']}::{hashlib.sha1(material.encode()).hexdigest()[:12]}::{semantic}"
    opts = options(row_id, obs["language_family"])
    target_label = next(o["label"] for o in opts if o["canonical_value"] == semantic)
    prompt = "\n".join([
        f"Language: {obs['language_family']}",
        "Perspective: transition_verifier_transition",
        "Task: choose the verifier transition supported by the attempted command and missing execution context.",
        f"Repository family: {obs['repo_family']}",
        f"Source root: {obs['cwd']}",
        f"Selected verifier: {obs['selected_verifier_path']}",
        f"Attempted command: {obs['command']}",
        f"Return code: {obs['returncode']}",
        f"Observed blocker category: {obs['subreason']}",
        f"Output tail: {obs['stdout_tail']}",
        "Options:",
        *[f"{o['label']}. {o['text']}" for o in opts],
        "Answer:",
    ])
    return {
        "row_id": row_id,
        "root_id": row_id,
        "root_lineage_key": f"stage12049::{obs['repo_family']}::{obs['selected_verifier_path']}::{obs['subreason']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": obs["repo_family"],
        "repo_family": obs["repo_family"],
        "language_family": obs["language_family"],
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12049_insufficient_evidence_floor_closure_train_support_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "selected_test_anchor": False,
        "verifier_anchor": False,
        "input_text": prompt,
        "prompt_text": prompt,
        "target_text": target_label,
        "decoder_text": target_label,
        "bounded_choice_target_label": target_label,
        "target": {"bounded_choice_target_label": target_label, "decoder_text": target_label, "semantic_value": semantic},
        "opaque_options": opts,
        "observed_verifier_transition": semantic,
        "insufficient_evidence": {
            "subreason": obs["subreason"],
            "selected_verifier_path": obs["selected_verifier_path"],
            "returncode": obs["returncode"],
            "stdout_tail": obs["stdout_tail"],
        },
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": True,
            "singleton_options": False,
            "train_support_only": True,
        },
        "standalone_projection_source": {
            "projection_mode": "stage12049_insufficient_evidence_floor_closure_rows",
            "selected_verifier_path": obs["selected_verifier_path"],
            "observed_verifier_transition": semantic,
            "insufficient_evidence_subreason": obs["subreason"],
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
        "stage": "stage12049_insufficient_evidence_floor_closure_rows",
        "rows_path": str(ROWS),
        "admitted_rows": len(rows),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "language_counts": dict(sorted(Counter(r["language_family"] for r in rows).items())),
        "repo_family_counts": dict(sorted(Counter(r["repo_family"] for r in rows).items())),
        "status_counts": dict(sorted(Counter(r["observed_verifier_transition"] for r in rows).items())),
        "subreason_counts": dict(sorted(Counter(r["insufficient_evidence"]["subreason"] for r in rows).items())),
        "decision": "admit_insufficient_evidence_floor_closure_train_support",
        "claim_boundary": "Rows are train-support only missing-context/dependency cases. They are not strict/source-heldout and are not model progress.",
        "next_stage_recommendation": {
            "stage": "stage12050_transition_support_rollup_v32",
            "action": "Merge INSUFFICIENT_EVIDENCE floor-closure rows and report remaining FAIL_TO_PASS/PASS_TO_PASS floors.",
        },
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
