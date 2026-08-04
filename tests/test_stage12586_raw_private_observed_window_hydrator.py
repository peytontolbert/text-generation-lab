from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12586_raw_private_observed_window_hydrator.py"
SPEC = importlib.util.spec_from_file_location("stage12586", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

SECRET = "sk-super-secret-stage12586-value"


def event(payload: dict[str, object], event_type: str = "response_item") -> dict[str, object]:
    return {"type": event_type, "payload": payload}


def call(tool: str, call_id: str, args: dict[str, object]) -> dict[str, object]:
    return event({"type": "function_call", "name": tool, "call_id": call_id, "arguments": json.dumps(args)})


def output(call_id: str, value: str) -> dict[str, object]:
    return event({"type": "function_call_output", "call_id": call_id, "output": value})


def base_events() -> list[dict[str, object]]:
    patch = "*** Begin Patch\n*** Update File: src/app.py\n@@\n-old\n+new\n*** End Patch"
    return [
        event({"type": "task_started"}, "event_msg"),
        event({"type": "message", "role": "user", "content": "Fix the bug"}),
        call("exec_command", "pre-state", {"cmd": "git status --short", "workdir": "/repo"}),
        output("pre-state", "Process exited with code 0\nFinal output:\n"),
        call("apply_patch", "patch-call", {"patch": patch}),
        output("patch-call", "Success.\nUpdated the following files:\nM src/app.py"),
        call("exec_command", "verify-call", {"cmd": "pytest -q tests/test_app.py", "workdir": "/repo"}),
        output("verify-call", "Process exited with code 0\nFinal output:\n1 passed"),
        call("exec_command", "post-state", {"cmd": "git status --short", "workdir": "/repo"}),
        output("post-state", "Process exited with code 0\nFinal output:\n M src/app.py"),
        event({"type": "message", "role": "assistant", "content": "Implemented and verified."}),
        event({"type": "task_complete"}, "event_msg"),
    ]


def payload_digest(payload: dict[str, object]) -> str:
    return mod.indexed_payload_digest(payload)


def indexed_events(events: list[dict[str, object]], chat_id: str = "chat-1") -> list[dict[str, object]]:
    rows = []
    for line_number, raw_event in enumerate(events, 1):
        payload = raw_event["payload"]
        assert isinstance(payload, dict)
        rows.append(
            {
                "chat_id": chat_id,
                "line_number": line_number,
                "event_id": f"event-{line_number}",
                "payload_digest_redacted": payload_digest(payload),
            }
        )
    return rows


def pair_rows(events: list[dict[str, object]], chat_id: str = "chat-1") -> list[dict[str, object]]:
    outputs: dict[str, int] = {}
    for line_number, raw_event in enumerate(events, 1):
        payload = raw_event["payload"]
        assert isinstance(payload, dict)
        if payload.get("type") in {"function_call_output", "custom_tool_call_output"}:
            outputs[str(payload.get("call_id"))] = line_number
    rows = []
    for line_number, raw_event in enumerate(events, 1):
        payload = raw_event["payload"]
        assert isinstance(payload, dict)
        if payload.get("type") not in {"function_call", "custom_tool_call"}:
            continue
        args = mod.safe_json_object(payload.get("arguments"))
        if not args and isinstance(payload.get("input"), dict):
            args = dict(payload["input"])
        elif not args and isinstance(payload.get("input"), str):
            args = {"input": payload["input"]}
        call_id = str(payload["call_id"])
        rows.append(
            {
                "chat_id": chat_id,
                "call_id": call_id,
                "tool_name": payload["name"],
                "call_line_number": line_number,
                "output_line_number": outputs[call_id],
                "call_event_id": f"event-{line_number}",
                "output_event_id": f"event-{outputs[call_id]}",
                "arguments_digest": mod.sha256_json(args) if args else None,
                "output_digest": payload_digest(events[outputs[call_id] - 1]["payload"]),
                "call_before_output": True,
            }
        )
    return rows


def write_session(path: Path, events: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in events), encoding="utf-8")


def fixture(tmp_path: Path, events: list[dict[str, object]] | None = None) -> dict[str, object]:
    events = events or base_events()
    codex_root = tmp_path / "sessions"
    raw_path = codex_root / "2026" / "session.jsonl"
    write_session(raw_path, events)
    source = mod.sha1_text(str(raw_path))
    content_sha = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    mtime = datetime.fromtimestamp(raw_path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    session_hint = "rollout-fixture-session"
    session_hash = mod.stage12314_session_hash(session_hint)
    components = {
        "source": source,
        "session": session_hash,
        "root": "canonical_root_fixture",
        "window": "window-1",
    }
    candidate = {
        "candidate_id": "candidate-1",
        "canonical_for_dedupe_key": True,
        "duplicate_of": None,
        "exact_same_source_join": True,
        "source_kind": "same_session_observed_trace",
        "source_session_root_window": components,
        "dedupe_key_sha256": mod.stable_hash(components),
    }
    window = {
        "task_window_id": "window-1",
        "chat_id": "chat-1",
        "source_file_hash_compat": source,
        "session_id_hint": session_hint,
        "start_line": 1,
        "end_line": len(events),
        "line_count": len(events),
        "start_event_id": "event-1",
        "terminal_event_id": f"event-{len(events)}",
        "terminal_status": "task_complete",
        "boundary_confidence": "lifecycle_exact",
    }
    manifest = {
        "chat_id": "chat-1",
        "source_file_hash_compat": source,
        "session_id_hint": session_hint,
        "file_content_sha256": content_sha,
        "file_size_bytes": raw_path.stat().st_size,
        "mtime_utc": mtime,
    }
    inventory = {
        "source_file_hash_compat": source,
        "physical_source_id": "physical-1",
        "source_root_label": "codex_sessions",
        "source_kind": "codex_session_jsonl",
        "relative_path_hash": mod.sha1_text(str(raw_path.relative_to(codex_root))),
        "file_size_bytes": raw_path.stat().st_size,
        "mtime_utc": mtime,
    }
    return {
        "candidate": candidate,
        "window": window,
        "manifest": manifest,
        "inventory": inventory,
        "event_rows": indexed_events(events),
        "pair_rows": pair_rows(events),
        "raw_path": raw_path,
        "codex_root": codex_root,
        "events": events,
    }


def hydrate(values: dict[str, object]) -> dict[str, object]:
    return mod.hydrate_window(
        values["candidate"],
        values["window"],
        values["manifest"],
        values["inventory"],
        values["event_rows"],
        values["pair_rows"],
        values["raw_path"],
    )


def test_complete_hydrated_core_has_success_proofs_and_no_authority(tmp_path: Path) -> None:
    values = fixture(tmp_path)
    resolved, blockers = mod.resolve_source_paths(
        values["codex_root"], {values["inventory"]["source_file_hash_compat"]: values["inventory"]}, {values["inventory"]["source_file_hash_compat"]}
    )
    assert resolved == {values["inventory"]["source_file_hash_compat"]: values["raw_path"]}
    assert blockers[values["inventory"]["source_file_hash_compat"]] == []
    record = hydrate(values)
    assert record["blocked_reasons"] == []
    assert record["classification"] == {
        "hydrated_core_status": "HYDRATED_CORE",
        "level3_status": "NOT_EVALUATED",
        "floors_credited": False,
    }
    assert record["training_allowed"] is False
    assert record["edit_evidence"]["observed_edits"][0]["paired_success_proof"] is True
    assert record["verifier_status_counts"] == {
        "passed": 1,
        "failed": 0,
        "incomplete": 0,
        "relevant_post_edit_completed": 1,
    }
    assert all(fact["repo_probe_success"] is True for fact in record["transition_local_facts"]["pre_transition_facts"])


def test_failed_patch_call_is_not_an_observed_mutation(tmp_path: Path) -> None:
    events = base_events()
    events[5] = output("patch-call", "Failed to find expected lines in src/app.py")
    record = hydrate(fixture(tmp_path, events))
    assert record["edit_evidence"]["observed_edits"] == []
    assert "edit_payload_or_explicit_no_patch_reason_missing" in record["blocked_reasons"]


def test_wrapped_apply_patch_exit_zero_is_an_observed_mutation(tmp_path: Path) -> None:
    events = base_events()
    events[5] = output(
        "patch-call",
        "Exit code: 0\nWall time: 0 seconds\nOutput:\nSuccess. Updated the following files:\nM src/app.py",
    )
    record = hydrate(fixture(tmp_path, events))
    assert record["edit_evidence"]["observed_edits"][0]["paired_success_proof"] is True
    assert record["blocked_reasons"] == []


@pytest.mark.parametrize(
    ("value", "expected_status"),
    [
        (
            "Exit code: 1\nWall time: 0 seconds\nOutput:\nSuccess. Updated the following files:\nM src/app.py",
            "failed",
        ),
        ("Process running with session ID 42\nSuccess. Updated the following files:\nM src/app.py", "running"),
        ("Diagnostic says Exit code: 0 and success, but no terminal wrapper was emitted.", "unknown"),
    ],
)
def test_apply_patch_output_does_not_promote_failure_or_nonterminal_text(value: str, expected_status: str) -> None:
    assert mod.output_status(value, tool_name="apply_patch")["status"] == expected_status


def test_multiline_apply_patch_success_preserves_all_edits_and_chronology(tmp_path: Path) -> None:
    events = base_events()
    second_patch = "*** Begin Patch\n*** Update File: src/app.py\n@@\n-new\n+newer\n*** End Patch"
    failed_patch = "*** Begin Patch\n*** Update File: src/app.py\n@@\n-missing\n+ignored\n*** End Patch"
    events[6:6] = [
        call("apply_patch", "failed-patch", {"patch": failed_patch}),
        output("failed-patch", "Failed to find expected lines in src/app.py"),
        call("apply_patch", "second-patch", {"patch": second_patch}),
        output("second-patch", "Success. Updated the following files:\nM src/app.py"),
    ]
    record = hydrate(fixture(tmp_path, events))
    edits = record["edit_evidence"]["observed_edits"]
    assert [edit["call_line_number"] for edit in edits] == [5, 9]
    assert [edit["action_sequence"] for edit in edits] == [2, 4]
    assert record["transition_local_facts"]["first_transition_line"] == 5
    assert record["transition_local_facts"]["last_transition_line"] == 9
    assert all(edit["paired_success_proof"] is True for edit in edits)


def test_named_artifact_multiline_apply_patch_regression() -> None:
    records = mod.read_jsonl(mod.OUT / "raw_private_observed_windows.jsonl")
    record = next(
        row
        for row in records
        if row["hydration_record_id"] == "stage12586_hydration_cd1106a20f50909097f7"
    )
    edits = record["edit_evidence"]["observed_edits"]
    assert [(edit["call_line_number"], edit["action_sequence"]) for edit in edits] == [(129, 41)]
    assert record["transition_local_facts"]["first_transition_line"] == 129
    assert record["transition_local_facts"]["last_transition_line"] == 129
    assert record["source_validation"]["observed_mtime_utc"] == "2026-07-15T15:55:00Z"
    assert "observed_mtime if not blockers else None_utc" not in record["source_validation"]


def test_successful_exec_mutation_requires_and_retains_paired_proof(tmp_path: Path) -> None:
    events = base_events()
    events[4] = call("exec_command", "patch-call", {"cmd": "printf new > src/app.py", "workdir": "/repo"})
    events[5] = output("patch-call", "Process exited with code 0\nFinal output:\n")
    record = hydrate(fixture(tmp_path, events))
    edit = record["edit_evidence"]["observed_edits"][0]
    assert edit["edit_format"] == "exec_command_mutation"
    assert edit["paired_success_proof"] is True
    assert record["blocked_reasons"] == []


def test_python_heredoc_comparisons_are_not_edits_but_literal_writes_are() -> None:
    read_only = "python - <<'PY'\nprint(1 > 0)\nPY"
    assert mod._exec_edit_fact(read_only, {"workdir": "/repo"}, call_line=1, sequence=1) is None
    writer = "python - <<'PY'\nfrom pathlib import Path\np = Path('src/app.py')\np.write_text('new')\nPY"
    fact = mod._exec_edit_fact(writer, {"workdir": "/repo"}, call_line=1, sequence=1)
    assert fact is not None
    assert fact["_targets"] == ["src/app.py"]

def test_write_stdin_completion_is_joined_to_originating_verifier(tmp_path: Path) -> None:
    events = base_events()
    events[7] = output("verify-call", "Process running with session ID 42")
    events[8:8] = [
        call("write_stdin", "stdin-call", {"session_id": 42, "chars": ""}),
        output("stdin-call", "Process exited with code 0\nFinal output:\n1 passed"),
    ]
    record = hydrate(fixture(tmp_path, events))
    verifier = record["verifier_observations"][0]
    origin = next(action for action in record["ordered_tool_actions"] if action["action_id"] == verifier["action_id"])
    continuation = next(action for action in record["ordered_tool_actions"] if action["tool_name"] == "write_stdin")
    assert verifier["status"] == "passed"
    assert verifier["completed"] is True
    assert continuation["originating_action_id"] == origin["action_id"]
    assert origin["continuation_action_ids"] == [continuation["action_id"]]


def test_running_verifier_is_incomplete_and_failed_verifier_is_separate(tmp_path: Path) -> None:
    running = base_events()
    running[7] = output("verify-call", "Process running with session ID 42")
    running_record = hydrate(fixture(tmp_path / "running", running))
    assert running_record["verifier_status_counts"]["incomplete"] == 1
    assert running_record["verifier_observations"] == []
    assert running_record["verifier_audit_observations"][0]["completed"] is False
    assert "completed_verifier_invocation_not_observed" in running_record["blocked_reasons"]

    failed = base_events()
    failed[7] = output("verify-call", "Process exited with code 1\nFinal output:\n1 failed")
    failed_record = hydrate(fixture(tmp_path / "failed", failed))
    assert failed_record["verifier_status_counts"]["failed"] == 1
    assert failed_record["verifier_status_counts"]["passed"] == 0
    assert failed_record["failed_verifier_observations"] == failed_record["verifier_observations"]
    assert failed_record["verifier_observations"][0]["failed"] is True


def test_verifier_relevance_requires_patch_test_target_linkage(tmp_path: Path) -> None:
    events = base_events()
    events[6] = call("exec_command", "verify-call", {"cmd": "pytest -q tests/test_other.py", "workdir": "/repo"})
    record = hydrate(fixture(tmp_path, events))
    assert record["verifier_observations"] == []
    assert record["verifier_audit_observations"][0]["patch_test_target_linked"] is False
    assert "post_edit_relevant_verifier_not_observed" in record["blocked_reasons"]


def test_only_successful_repository_probes_form_pre_and_post_state(tmp_path: Path) -> None:
    events = base_events()
    events[3] = output("pre-state", "Process exited with code 1\nFinal output:\nfatal")
    events[9] = output("post-state", "Process exited with code 1\nFinal output:\nfatal")
    record = hydrate(fixture(tmp_path, events))
    facts = record["transition_local_facts"]
    assert facts["pre_transition_facts"] == []
    assert facts["post_transition_facts"] == []
    assert "pre_transition_successful_repo_probe_missing" in record["blocked_reasons"]
    assert "post_transition_successful_repo_probe_missing" in record["blocked_reasons"]


@pytest.mark.parametrize(
    ("mutation", "blocker"),
    [
        (lambda row: row["candidate"]["source_session_root_window"].update(session="forged"), "recomputed_session_identity_mismatch"),
        (lambda row: row["candidate"].update(dedupe_key_sha256="0" * 64), "recomputed_dedupe_identity_mismatch"),
        (lambda row: row["candidate"]["source_session_root_window"].update(root="forged"), "recomputed_root_identity_invalid"),
    ],
)
def test_session_root_and_dedupe_are_recomputed(tmp_path: Path, mutation, blocker: str) -> None:
    values = fixture(tmp_path)
    mutation(values)
    record = hydrate(values)
    assert blocker in record["blocked_reasons"]
    assert record["source_identity"]["same_source_join_validated"] is False


def test_execute_recomputes_duplicate_root_and_dedupe_and_is_deterministic(tmp_path: Path) -> None:
    values = fixture(tmp_path / "source")
    duplicate = copy.deepcopy(values["candidate"])
    duplicate["candidate_id"] = "candidate-2"
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    candidate_path = inputs / "candidates.jsonl"
    physical_path = inputs / "physical.jsonl"
    chat_path = inputs / "chats.jsonl"
    event_path = inputs / "events.jsonl"
    pair_path = inputs / "pairs.jsonl"
    window_path = inputs / "windows.jsonl"
    mod.write_jsonl(candidate_path, [values["candidate"], duplicate])
    mod.write_jsonl(physical_path, [values["inventory"]])
    mod.write_jsonl(chat_path, [values["manifest"]])
    mod.write_jsonl(event_path, values["event_rows"])
    mod.write_jsonl(pair_path, values["pair_rows"])
    mod.write_jsonl(window_path, [values["window"]])
    kwargs = {
        "out": tmp_path / "out",
        "summary_path": tmp_path / "summary.json",
        "candidate_path": candidate_path,
        "physical_path": physical_path,
        "chat_path": chat_path,
        "event_path": event_path,
        "pair_path": pair_path,
        "window_path": window_path,
        "codex_root": values["codex_root"],
        "expected_canonical_count": 2,
    }
    first = mod.execute(**kwargs)
    first_bytes = {path.name: path.read_bytes() for path in sorted(kwargs["out"].iterdir())}
    second = mod.execute(**kwargs)
    second_bytes = {path.name: path.read_bytes() for path in sorted(kwargs["out"].iterdir())}
    rows = mod.read_jsonl(kwargs["out"] / "raw_private_observed_windows.jsonl")
    assert first == second
    assert first_bytes == second_bytes
    assert first["identity_recomputation"]["root_identity_unique"] is False
    assert first["identity_recomputation"]["dedupe_identity_unique"] is False
    assert all("duplicate_recomputed_root_identity" in row["blocked_reasons"] for row in rows)
    assert all("duplicate_recomputed_dedupe_identity" in row["blocked_reasons"] for row in rows)

def test_raw_secrets_and_absolute_paths_are_never_serialized(tmp_path: Path) -> None:
    events = base_events()
    events[1]["payload"]["content"] = f"Fix the bug {SECRET} /home/private/source.py"
    events[4]["payload"]["arguments"] = json.dumps(
        {"patch": f"*** Begin Patch\n*** Update File: src/app.py\n@@\n-old\n+{SECRET}\n*** End Patch"}
    )
    values = fixture(tmp_path, events)
    record = hydrate(values)
    serialized = json.dumps(record, sort_keys=True)
    assert SECRET not in serialized
    assert "/home/private/source.py" not in serialized
    assert "Fix the bug" not in serialized
    assert "*** Begin Patch" not in serialized
    with pytest.raises(mod.GateError, match="secret_like_value"):
        mod.assert_safe_shape({"digest_looking_key": SECRET})
    with pytest.raises(mod.GateError, match="absolute_path_value"):
        mod.assert_safe_shape({"innocent_key": "/repo/source.py"})


def test_source_mutation_blocks_before_window_parsing(tmp_path: Path) -> None:
    values = fixture(tmp_path)
    with values["raw_path"].open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"secret": SECRET}) + "\n")
    os.utime(values["raw_path"], None)
    record = hydrate(values)
    assert "physical_source_content_sha256_mutated" in record["blocked_reasons"]
    assert record["source_validation"]["content_hash_match"] is False
    assert record["ordered_tool_actions"] == []
    assert SECRET not in json.dumps(record, sort_keys=True)
    assert record["source_validation"]["observed_content_sha256"] is None
    assert record["source_validation"]["observed_file_size_bytes"] is None
    with values["raw_path"].open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"more": "mutated"}) + "\n")
    second = hydrate(values)
    assert second == record


def test_cross_chat_pair_join_is_rejected(tmp_path: Path) -> None:
    values = fixture(tmp_path)
    values["pair_rows"][1]["chat_id"] = "chat-2"
    record = hydrate(values)
    assert "authoritative_pair_raw_join_mismatch" in record["blocked_reasons"]


def test_canonical_selection_excludes_replay_only() -> None:
    natural = {
        "candidate_id": "natural",
        "canonical_for_dedupe_key": True,
        "duplicate_of": None,
        "exact_same_source_join": True,
        "source_kind": "same_session_observed_trace",
    }
    replay = {"candidate_id": "replay", "canonical_for_dedupe_key": True, "source_kind": "patch_effect_replay"}
    selected, excluded = mod.select_canonical([natural, replay], expected_count=2)
    assert selected == [natural]
    assert excluded == [replay]


def test_forbidden_shapes_and_enabled_training_are_rejected() -> None:
    for key in mod.FORBIDDEN_OUTPUT_KEYS:
        with pytest.raises(mod.GateError, match="forbidden_output_key"):
            mod.assert_safe_shape({"nested": [{key: True}]})
    with pytest.raises(mod.GateError, match="training_allowed_must_be_explicit_false"):
        mod.assert_safe_shape({"training_allowed": True})
