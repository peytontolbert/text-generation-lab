from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_session_episode_seed_candidates import build_session_episode_seed_candidates  # noqa: E402


def test_build_session_episode_seed_candidates_extracts_patch_and_verify_sessions(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    events.write_text(
        "\n".join(
            [
                json.dumps({"source_root_label": "codex_sessions", "session_id_hint": "s1", "normalized_event_type": "patch_applied", "tool_name": "apply_patch", "repo_hint": "repo_a", "file_path_refs": ["src/app.py"]}),
                json.dumps({"source_root_label": "codex_sessions", "session_id_hint": "s1", "normalized_event_type": "verification_command", "tool_name": "exec_command", "repo_hint": "repo_a", "file_path_refs": ["tests/test_app.py"]}),
                json.dumps({"source_root_label": "codex_sessions", "session_id_hint": "s2", "normalized_event_type": "assistant_message", "tool_name": "", "repo_hint": "", "file_path_refs": []}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    seeds, summary = build_session_episode_seed_candidates(normalized_events_path=events)

    assert summary["session_count"] == 2
    assert summary["seed_count"] == 1
    assert summary["route_counts"]["PATCH_PLUS_VERIFY"] == 1
    seed = seeds[0]
    assert seed["seed_type"] == "session_episode"
    assert seed["repo_hint"] == "repo_a"
    assert seed["changes"][0]["path"] == "src/app.py"
    assert "Changed files:" in seed["goal"]
    assert "Verification targets:" in seed["goal"]


def test_build_session_episode_seed_candidates_uses_execution_traces_for_goal_and_metadata(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    events.write_text(
        "\n".join(
            [
                json.dumps({"source_root_label": "codex_sessions", "session_id_hint": "s1", "normalized_event_type": "patch_applied", "tool_name": "apply_patch", "repo_hint": "repo_a", "file_path_refs": ["src/app.py"]}),
                json.dumps({"source_root_label": "codex_sessions", "session_id_hint": "s1", "normalized_event_type": "assistant_message", "tool_name": "", "repo_hint": "repo_a", "file_path_refs": []}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    traces = tmp_path / "traces.jsonl"
    traces.write_text(
        json.dumps(
            {
                "source_root_label": "codex_sessions",
                "session_id_hint": "s1",
                "repo_hint": "repo_a",
                "command_head": "pytest",
                "file_path_refs": ["src/app.py", "tests/test_app.py"],
                "runtime_trace": {"failure_type": "test_assertion_failure", "exception_type": "AssertionError"},
                "trace_id": "t1",
                "signal_kind": "verification",
                "exit_code": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    seeds, summary = build_session_episode_seed_candidates(
        normalized_events_path=events,
        execution_traces_path=traces,
        require_execution_traces=True,
        min_trace_rows=1,
    )

    assert summary["seed_count"] == 1
    seed = seeds[0]
    assert "Observed failure types: test_assertion_failure" in seed["goal"]
    assert "Observed exception types: AssertionError" in seed["goal"]
    assert seed["metadata"]["trace_count"] == 1
    assert seed["metadata"]["trace_verification_targets"] == ["tests/test_app.py"]


def test_build_session_episode_seed_candidates_requires_traces_when_requested(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    events.write_text(
        json.dumps({"source_root_label": "codex_sessions", "session_id_hint": "s1", "normalized_event_type": "patch_applied", "tool_name": "apply_patch", "repo_hint": "repo_a", "file_path_refs": ["src/app.py"]})
        + "\n",
        encoding="utf-8",
    )

    seeds, summary = build_session_episode_seed_candidates(
        normalized_events_path=events,
        execution_traces_path=tmp_path / "missing.jsonl",
        require_execution_traces=True,
        min_trace_rows=1,
    )

    assert seeds == []
    assert summary["route_counts"]["SKIP_NO_EXECUTION_TRACES"] == 1
