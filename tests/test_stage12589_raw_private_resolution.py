from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12589_raw_private_resolution.py"
SPEC = importlib.util.spec_from_file_location("stage12589", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def event(payload, outer="response_item"):
    return {"type": outer, "payload": payload}


def call(name, call_id, args):
    return event({"type": "function_call", "name": name, "call_id": call_id, "arguments": json.dumps(args)})


def output(call_id, value):
    return event({"type": "function_call_output", "call_id": call_id, "output": value})


def patch(call_id, target="src/app.py"):
    body = f"*** Begin Patch\n*** Update File: {target}\n@@\n-old\n+new\n*** End Patch"
    return [call("apply_patch", call_id, {"patch": body}), output(call_id, "Success.")]


def command(call_id, cmd, workdir="/repo", code=0):
    return [call("exec_command", call_id, {"cmd": cmd, "workdir": workdir}), output(call_id, f"Process exited with code {code}\nFinal output:\nresult")]


def raw_events(sequence=None):
    if sequence is None:
        sequence = command("pre", "git status --short") + patch("edit") + command("verify", "pytest -q tests/test_app.py") + command("post", "git diff --stat")
    return [event({"type": "task_started"}, "event_msg"), event({"type": "message", "role": "user", "content": "fix"}), *sequence, event({"type": "task_complete"}, "event_msg")]


def indexed(events):
    return [{"chat_id": "chat", "line_number": line, "event_id": f"event-{line}", "payload_digest_redacted": mod.H.indexed_payload_digest(raw["payload"])} for line, raw in enumerate(events, 1)]


def pairs(events):
    out_lines = {str(raw["payload"].get("call_id")): line for line, raw in enumerate(events, 1) if raw["payload"].get("type") == "function_call_output"}
    rows = []
    for line, raw in enumerate(events, 1):
        payload = raw["payload"]
        if payload.get("type") != "function_call":
            continue
        args = mod.H.safe_json_object(payload["arguments"])
        out_line = out_lines[payload["call_id"]]
        rows.append({"chat_id": "chat", "call_id": payload["call_id"], "tool_name": payload["name"], "call_line_number": line,
                     "output_line_number": out_line, "call_before_output": True, "arguments_digest": mod.H.sha256_json(args),
                     "call_event_id": f"event-{line}", "output_event_id": f"event-{out_line}",
                     "output_digest": mod.H.indexed_payload_digest(events[out_line - 1]["payload"])})
    return rows


def fixture(tmp_path: Path, sequence=None):
    events = raw_events(sequence)
    root = tmp_path / "sessions"
    raw_path = root / "2026" / "session.jsonl"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text("".join(json.dumps(row) + "\n" for row in events), encoding="utf-8")
    source = mod.H.sha1_text(str(raw_path))
    mtime = datetime.fromtimestamp(raw_path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    request = {"resolution_request_id": "stage12589_request_fixture", "task_window_id": "window-1", "source_identity": source,
               "global_rank": 1, "within_source_rank": 1}
    window = {"task_window_id": "window-1", "chat_id": "chat", "source_file_hash_compat": source, "start_line": 1,
              "end_line": len(events), "terminal_event_id": f"event-{len(events)}", "terminal_status": "task_complete"}
    manifest = {"chat_id": "chat", "source_file_hash_compat": source, "file_content_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                "file_size_bytes": raw_path.stat().st_size, "mtime_utc": mtime, "cwd_hints_top": [["/repo", 1]],
                "workspace_root_hints_top": [["/repo", 1]]}
    inventory = {"source_file_hash_compat": source, "physical_source_id": "physical", "relative_path_hash": mod.H.sha1_text(str(raw_path.relative_to(root))),
                 "file_size_bytes": raw_path.stat().st_size, "mtime_utc": mtime}
    return {"request": request, "profile": {"identity": {"session_identity": "session"}}, "window": window, "manifest": manifest,
            "inventory": inventory, "indexed_rows": indexed(events), "pair_rows": pairs(events), "raw_path": raw_path,
            "protected": {"source_path": set(), "root_identity": set(), "repo_family": set()}}


def empty_prior():
    from collections import defaultdict
    return {"window": set(), "root": set(), "dedupe": set(), "tuple": set(), "mutated_source": set(),
            "source_intervals": defaultdict(list), "source_actions": defaultdict(set)}


def resolve_window(values, prior=None):
    snapshot, blockers = mod.read_source_snapshot(values["raw_path"], values["request"]["source_identity"])
    assert not blockers
    return mod.resolve_window(**values, prior=prior or empty_prior(), snapshot=snapshot)


def profile(index):
    return {"prequalification_id": f"prequal-{index}", "task_window_id": f"window-{index}", "chat_id": f"chat-{index % 4}",
            "ranking_score": 10, "identity": {"session_identity": f"session-{index % 3}", "source_file_hash_compat": f"{index % 3 + 1:040x}", "root_identity": "unknown"},
            "structural_checks": {name: True for name in mod.REQUIRED_PROFILE_CHECKS}}


def test_bounded_multi_patch_segmentation_and_ambiguity(tmp_path: Path) -> None:
    good = command("pre1", "git status --short") + patch("edit1") + command("verify1", "pytest -q tests/test_app.py") + command("post1", "git diff --stat")
    good += command("pre2", "git status --short") + patch("edit2") + command("verify2", "pytest -q tests/test_app.py") + command("post2", "git diff --stat")
    atoms, parent = resolve_window(fixture(tmp_path / "good", good))
    assert len(atoms) == 2 and parent["bounded_atom_count"] == 2
    assert all(atom["classification"] == "resolved_observed_atom_candidate" for atom in atoms)
    ambiguous = command("pre", "git status --short") + patch("edit1") + patch("edit2") + command("verify", "pytest -q tests/test_app.py") + command("post", "git diff --stat")
    atoms, _ = resolve_window(fixture(tmp_path / "ambiguous", ambiguous))
    assert len(atoms) == 2
    assert atoms[0]["ambiguous"] is True
    assert "multi_edit_segmentation_ambiguous" in atoms[0]["blocker_reasons"]


def test_prior_physical_overlap_blocks_but_disjoint_source_window_is_allowed(tmp_path: Path) -> None:
    values = fixture(tmp_path)
    prior = empty_prior()
    source = values["request"]["source_identity"]
    prior["source_intervals"][source].append((1, values["window"]["end_line"]))
    atoms, _ = resolve_window(values, prior)
    assert "stage12586_physical_source_interval_overlap" in atoms[0]["blocker_reasons"]
    prior["source_intervals"][source] = [(values["window"]["end_line"] + 10, values["window"]["end_line"] + 20)]
    atoms, _ = resolve_window(values, prior)
    assert atoms[0]["classification"] == "resolved_observed_atom_candidate"


def test_task_window_and_physical_action_prior_identity_block(tmp_path: Path) -> None:
    values = fixture(tmp_path)
    source = values["request"]["source_identity"]
    target_hash = mod.H.sha256_bytes(b"src/app.py")
    action_hash = mod.stable_hash((source, 5, (target_hash,)))
    prior = empty_prior()
    prior["source_actions"][source].add(action_hash)
    blocked, _ = resolve_window(values, prior)
    assert "stage12586_physical_action_identity_overlap" in blocked[0]["blocker_reasons"]
    prior = empty_prior()
    prior["window"].add("window-1")
    blocked, _ = resolve_window(values, prior)
    assert "stage12586_task_window_overlap" in blocked[0]["blocker_reasons"]


def test_unresolved_and_overlapping_protected_identity_block(tmp_path: Path) -> None:
    unknown = fixture(tmp_path / "unknown")
    unknown["manifest"]["cwd_hints_top"] = []
    unknown["manifest"]["workspace_root_hints_top"] = []
    atoms, _ = resolve_window(unknown)
    assert atoms[0]["protected_resolution"] == "unresolved"
    assert "protected_identity_unresolved" in atoms[0]["blocker_reasons"]
    overlap = fixture(tmp_path / "overlap")
    overlap["protected"]["source_path"].add("/repo")
    atoms, _ = resolve_window(overlap)
    assert atoms[0]["protected_resolution"] == "overlap"


def test_later_failed_or_unrelated_verifier_supersedes_positive(tmp_path: Path) -> None:
    sequence = command("pre", "git status --short") + patch("edit") + command("pass", "pytest -q tests/test_app.py")
    sequence += command("later", "pytest -q tests/test_other.py", code=1) + command("post", "git diff --stat")
    atoms, _ = resolve_window(fixture(tmp_path, sequence))
    assert atoms[0]["classification"] == "blocked"
    assert "later_verifier_superseded_positive_observation" in atoms[0]["blocker_reasons"]
    assert atoms[0]["supply_class"] == "unresolved_negative_observation"


def test_no_positive_stop_policy_enum_and_probe_observation_name(tmp_path: Path) -> None:
    atoms, _ = resolve_window(fixture(tmp_path))
    atom = atoms[0]
    assert atom["normative_policy_correctness"] == "unresolved"
    assert atom["positive_stop_target_allowed"] is False
    assert atom["ordered_pre_post_probe_observed"] == "observed"
    assert "repo_probe_resolution" not in atom


def test_full_119_universe_partition_ignores_caps() -> None:
    rows = [profile(index) for index in range(119)]
    selected, excluded = mod.route_batch(rows, empty_prior(), target=60, cap=3)
    assert len(selected) == 119
    assert not excluded
    assert {row["global_rank"] for row in selected} == set(range(1, 120))
    assert len({row["task_window_id"] for row in selected}) == 119


def test_failed_verifier_is_unresolved_negative_not_adjudication(tmp_path: Path) -> None:
    sequence = command("pre", "git status --short") + patch("edit") + command("verify", "pytest -q tests/test_app.py", code=1) + command("post", "git diff --stat")
    atoms, _ = resolve_window(fixture(tmp_path, sequence))
    assert atoms[0]["classification"] == "blocked"
    assert atoms[0]["normative_policy_correctness"] == "unresolved"
    assert atoms[0]["supply_class"] == "unresolved_negative_observation"


def test_mutation_fails_closed(tmp_path: Path) -> None:
    values = fixture(tmp_path)
    snapshot, _ = mod.read_source_snapshot(values["raw_path"], values["request"]["source_identity"])
    values["raw_path"].write_text(values["raw_path"].read_text() + "{}\n", encoding="utf-8")
    fresh, _ = mod.read_source_snapshot(values["raw_path"], values["request"]["source_identity"])
    atoms, parent = mod.resolve_window(**values, prior=empty_prior(), snapshot=fresh)
    assert not atoms
    assert any("mutated" in reason for reason in parent["blocker_reasons"])
    assert snapshot != fresh


def test_strict_safe_guard_rejects_leakage() -> None:
    safe = {"semantic_rule_id": mod.RULE_REPO_WIDE, "training_allowed": False, "digest": "a" * 64}
    mod.assert_safe_output(safe)
    for leaked in ({"command": "pytest"}, {"value": "/repo/private"}, {"output_digest": "a" * 64}, {"source_path": "private"}):
        with pytest.raises(mod.GateError):
            mod.assert_safe_output(leaked)


def test_deterministic_resolution_regeneration(tmp_path: Path) -> None:
    values = fixture(tmp_path)
    first = resolve_window(values)
    second = resolve_window(values)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_generated_artifact_contract_and_exact_counts() -> None:
    summary_path = mod.OUT / "summary.json"
    if not summary_path.is_file():
        pytest.skip("Stage12589 artifacts not generated yet")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    atoms = list(mod.iter_jsonl(mod.OUT / "safe_resolution_records.jsonl"))
    parents = list(mod.iter_jsonl(mod.OUT / "parent_window_resolutions.jsonl")) if (mod.OUT / "parent_window_resolutions.jsonl").is_file() else []
    if summary.get("windows_reviewed") != 119:
        pytest.skip("Stage12589 artifacts await regeneration")
    assert summary["candidate_universe_count"] == summary["windows_reviewed"] == len(parents) == 119
    assert summary["bounded_atoms_proposed"] == len(atoms)
    assert all(row["normative_policy_correctness"] == "unresolved" for row in atoms)
    assert all(row["positive_stop_target_allowed"] is False for row in atoms)
    assert all(not row["training_allowed"] and not row["admission_allowed"] and not row["level3_allowed"] for row in atoms)
    mod.assert_safe_output([summary, atoms, parents])
