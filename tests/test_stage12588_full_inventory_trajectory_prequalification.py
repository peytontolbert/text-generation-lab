from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12588_full_inventory_trajectory_prequalification.py"
SPEC = importlib.util.spec_from_file_location("stage12588", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def fixture(*, terminal: str = "task_complete", edit: bool = True, post_probe: bool = True, verifier_head: str = "pytest"):
    window = {
        "task_window_id": "window-1", "chat_id": "chat-1", "source_file_hash_compat": "a" * 40,
        "session_id_hint": "session-1", "terminal_status": terminal,
    }
    events = [
        {"line_number": 1, "payload_type": "task_started", "role": ""},
        {"line_number": 2, "payload_type": "user_message", "role": "user"},
        {"line_number": 12, "payload_type": terminal, "role": ""},
    ]
    pairs = [{"call_line": 3, "output_line": 4, "tool_name": "exec_command", "command_head": "git", "recognized_state_probe": "git_status"}]
    if edit:
        pairs.append({"call_line": 5, "output_line": 6, "tool_name": "apply_patch", "command_head": None})
    pairs.append({"call_line": 7, "output_line": 8, "tool_name": "exec_command", "command_head": verifier_head})
    if post_probe:
        pairs.append({"call_line": 9, "output_line": 10, "tool_name": "exec_command", "command_head": "git", "recognized_state_probe": "git_diff"})
    manifest = {"source_file_hash_compat": "a" * 40, "file_size_bytes": 10, "mtime_utc": "2026-01-01T00:00:00Z"}
    physical = {"source_file_hash_compat": "a" * 40, "file_size_bytes": 10, "mtime_utc": "2026-01-01T00:00:00Z", "source_root_label": "codex_sessions"}
    lineage = {
        "source": "a" * 40, "session": mod.stable_hash("session-1")[:24], "root_identity": "root-1",
        "window": "window-1", "repo_family": "repo-1", "language_family": "python",
        "source_root_label": "codex_sessions", "exact_tuple_join": True,
    }
    protected = {"repo_family": set(), "root_identity": set()}
    return window, events, pairs, manifest, physical, lineage, protected


def qualify(**kwargs):
    values = fixture(**kwargs)
    return mod.prequalify_window(*values)


def test_task_complete_is_required_and_turn_aborted_is_not_prequalified() -> None:
    complete = qualify()
    assert complete["structural_checks"]["literal_task_complete"] is True
    assert complete["terminal_observation"]["normative_label_emitted"] is False
    aborted = qualify(terminal="turn_aborted")
    assert aborted["structural_checks"]["literal_task_complete"] is False
    assert "literal_task_complete" in aborted["trajectory_atom_prequalification"]["blockers"]


def test_no_edit_is_only_an_evidence_candidate_pending_private_review() -> None:
    row = qualify(edit=False)
    assert row["evidence_shape"]["explicit_no_edit_evidence_candidate"] is True
    assert "explicit_no_edit_evidence" in row["trajectory_atom_prequalification"]["raw_private_review_required"]
    assert row["evidence_shape"]["observed_edit_pair_candidate_count"] == 0


def test_pathless_verifier_keeps_completion_and_relevance_uncertain() -> None:
    row = qualify(verifier_head="pytest")
    required = row["trajectory_atom_prequalification"]["raw_private_review_required"]
    assert "verifier_terminal_completion_and_status" in required
    assert "verifier_relevance_to_edit_or_task" in required
    assert "verifier_causality" not in json.dumps(row)


def test_only_explicit_verifier_heads_are_verifier_candidates() -> None:
    assert mod.is_verifier_head("pytest") is True
    assert mod.is_verifier_head("/redacted/environment/pytest") is True
    for generic_head in ("python", "/redacted/environment/python", "bash", "node", "npm"):
        assert mod.is_verifier_head(generic_head) is False
    assert mod.is_verifier_head("sed") is False


def test_explicit_verifier_metadata_is_authoritative() -> None:
    assert mod.is_verifier_pair({"command_head": "python", "recognized_verifier_invocation": "python_module_pytest"}) is True
    assert mod.is_verifier_pair({"command_head": "python"}) is False


def test_failed_verifier_terminal_is_not_correct_stop_and_is_preserved() -> None:
    policy = mod.terminal_supply_policy("failed")
    assert policy["terminal_observed"] is True
    assert policy["terminal_normative_label_emitted"] is False
    assert policy["needs_stop_policy_review"] is True
    assert policy["supply_class"] == "negative_or_recovery"
    assert policy["failed_trajectory_excluded"] is False


def synthetic_row(index: int, chat: str, repo: str = mod.UNKNOWN, language: str = mod.UNKNOWN):
    row = qualify()
    row["task_window_id"] = f"window-{index:04d}"
    row["prequalification_id"] = f"prequal-{index:04d}"
    row["chat_id"] = chat
    row["identity"]["session_identity"] = f"session-{chat}"
    row["identity"]["repo_family"] = repo
    row["identity"]["language_family"] = language
    row["identity"]["repo_known_for_diversity_credit"] = repo != mod.UNKNOWN
    row["identity"]["language_known_for_diversity_credit"] = language != mod.UNKNOWN
    return row


def test_caps_route_overflow_and_do_not_permanently_exclude() -> None:
    rows = [synthetic_row(i, "chat-a") for i in range(8)]
    rows += [synthetic_row(100 + i, f"chat-{i}", "dominant") for i in range(8)]
    rows += [synthetic_row(200 + i, f"other-{i}", f"repo-{i}") for i in range(12)]
    selected, overflow = mod.rank_requests(rows, target=20, chat_cap=3, repo_fraction_cap=0.15)
    assert sum(row["chat_id"] == "chat-a" for row in selected) <= 3
    assert sum(row["identity"]["repo_family"] == "dominant" for row in selected) <= 3
    assert overflow and all(row["permanent_source_exclusion"] is False for row in overflow)


def test_session_cap_applies_across_distinct_chat_ids() -> None:
    rows = [synthetic_row(i, f"chat-{i}") for i in range(8)]
    for row in rows:
        row["identity"]["session_identity"] = "shared-session"
    selected, overflow = mod.rank_requests(rows, target=30, chat_cap=3)
    assert len(selected) == 3
    assert len(overflow) == 5
    assert {row["overflow_reason"] for row in overflow} == {"chat_session_cap_overflow"}


def test_unknown_identity_gets_no_diversity_credit() -> None:
    rows = [synthetic_row(1, "chat-a"), synthetic_row(2, "chat-b", "known", "python")]
    report = mod.dominance(rows, "repo_family")
    assert report["unknown_count"] == 1
    assert report["unknown_excluded_from_diversity_credit"] is True
    assert report["top_known"] == [{"identity": "known", "count": 1, "fraction": 0.5}]


def test_duplicate_root_composite_hard_fails() -> None:
    root = {
        "canonical_for_dedupe_key": True, "exact_same_source_join": True,
        "source_kind": "same_session_observed_trace",
        "repo_family": "repo", "language_family": "python",
        "source_session_root_window": {"source": "s", "session": "x", "root": "r", "window": "w"},
    }
    with pytest.raises(mod.GateError, match="duplicate_source_session_root_window_identity"):
        mod.lineage_by_window([], [root, dict(root)])


def test_no_forbidden_model_or_training_shapes() -> None:
    row = qualify()
    mod.assert_audit_only_shape(row)
    serialized = json.dumps(row, sort_keys=True)
    assert row["training_allowed"] is False
    assert row["ranking_eligibility"] == {"eligible": False, "candidate_alternative_count": 0}
    for key in mod.FORBIDDEN_KEYS:
        assert f'"{key}"' not in serialized
    with pytest.raises(mod.GateError, match="forbidden_output_key"):
        mod.assert_audit_only_shape({"model_input": "x", "training_allowed": False})


def test_protected_overlap_cannot_enter_selection() -> None:
    row = qualify()
    row["protected_overlap"] = {"overlap": True, "matched_identity_kinds": ["repo_family"]}
    selected, _ = mod.rank_requests([row], target=30)
    assert selected == []


def test_input_hash_drift_hard_fails() -> None:
    with pytest.raises(mod.GateError, match="input_hash_drift:windows"):
        mod.verify_hashes({"windows": "changed"}, {"windows": "expected"})


def test_generated_artifact_contract_and_exact_counts() -> None:
    summary = json.loads((mod.OUT / "summary.json").read_text(encoding="utf-8"))
    rows = list(mod.iter_jsonl(mod.OUT / "full_inventory_prequalification.jsonl"))
    selected = list(mod.iter_jsonl(mod.OUT / "selected_hydration_requests.jsonl"))
    overflow = list(mod.iter_jsonl(mod.OUT / "hydration_request_overflow.jsonl"))
    assert summary["funnel_counts"]["all_task_windows_scanned"] == len(rows) == 23936
    assert summary["funnel_counts"]["selected_hydration_requests"] == len(selected) == 0
    assert summary["funnel_counts"]["overflow_requests"] == len(overflow)
    assert summary["funnel_counts"]["candidate_alternatives"] == 0
    assert summary["funnel_counts"]["ranking_eligible"] == 0
    assert summary["dominance"]["chat"]["maximum_selected_per_chat"] <= 3
    assert summary["dominance"]["chat"]["maximum_selected_per_session"] <= 3
    assert all(row["training_allowed"] is False for row in rows + selected + overflow)
    assert not any(row["protected_overlap"]["overlap"] for row in rows if row["task_window_id"] in {item["task_window_id"] for item in selected})
    mod.assert_audit_only_shape(summary)
