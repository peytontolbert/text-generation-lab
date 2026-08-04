#!/usr/bin/env python3
"""Audit-only full-inventory trajectory prequalification and hydration routing."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12588_full_inventory_trajectory_prequalification"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

INPUTS = {
    "physical_inventory": ROOT / "runs/local/artifacts/stage12256_live_physical_session_inventory_refresh/live_physical_source_records.jsonl",
    "chat_manifests": ROOT / "runs/local/artifacts/stage12258_live_codex_chat_reconstruction_index/per_chat_manifest.jsonl",
    "event_index": ROOT / "runs/local/artifacts/stage12258_live_codex_chat_reconstruction_index/chat_event_index.jsonl",
    "authoritative_pairs": ROOT / "runs/local/artifacts/stage12259_codex_tool_call_observation_pairer/tool_call_observation_pairs.jsonl",
    "task_windows": ROOT / "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner/codex_task_windows.jsonl",
    "repo_state_joins": ROOT / "runs/local/artifacts/stage12314_session_candidate_repo_and_state_joiner/session_candidate_repo_state_join_records.jsonl",
    "trajectory_roots": ROOT / "runs/local/artifacts/stage12585_same_source_observed_trajectory_root_miner/candidate_ledger.jsonl",
    "prior_hydrated_records": ROOT / "runs/local/artifacts/stage12586_raw_private_observed_window_hydrator/raw_private_observed_windows.jsonl",
    "hydration_summary": ROOT / "runs/local/artifacts/stage12586_raw_private_observed_window_hydrator/summary.json",
    "corrected_gate_contract": ROOT / "runs/local/artifacts/stage12587_trajectory_vs_ranking_gate_correction/corrected_gate_contract.json",
    "protected_denylist": ROOT / "configs/software_maintainer/future_eval_identity_denylist_v1.json",
}

PINNED_INPUT_SHA256 = {
    "physical_inventory": "ec9af3f3fbbabe9c78f6483e74688ebb76f506ddd511f6902f14e5b473d44f48",
    "chat_manifests": "9a680ebc64a04c2bd8e4968bd1c046d61843f7a6de7449d9d3f14c05522fb90a",
    "event_index": "31175973e6deff05badf79cbb7be216eb75bb8434b04ee3286bb342cd7346251",
    "authoritative_pairs": "b3eadbf8740b354a360cc822e1c4cdc9071fc1d9159d375c1366681e685b5b37",
    "task_windows": "7e1ceb5f448f7d6dac441e5a9a94c05cb96dbf225a1c590eb015e13e90f09766",
    "repo_state_joins": "f729e20744f6aec75014fdc0944e31679cc51c9cb08c7ea28bcc04a262b634d4",
    "trajectory_roots": "94a01c314f88a01e2e0377ef00b48077966c22fb36c13cc3a722dd33862b41d1",
    "prior_hydrated_records": "9f394a7c68252eb4e63963546869cfcc5aeb51336e0f3eca64a8f73b4bfb8a61",
    "hydration_summary": "7e6c10a43ed371863a090965d6b24aff6a684e6d779c470e6d9e55706fd8a81e",
    "corrected_gate_contract": "1ed451d6d10855771a2a268d57f2c65d4d2b135f1a58ebb9b05697e2c5363a3b",
    "protected_denylist": "1dc55b537a85f1033a842d337ff6bb6124fe0315e62aba520dea3ddc69f860a0",
}

VERIFIER_HEADS = {"pytest", "py.test", "ctest", "vitest", "tsc"}
VERIFIER_KINDS = {"pytest", "python_module_pytest", "ctest", "vitest", "typescript_check", "cargo_test", "go_test", "package_script_check", "bash_syntax_check"}
PROBE_KINDS = {"git_status", "git_diff"}
UNKNOWN = "unknown"
FORBIDDEN_KEYS = {
    "admission", "admitted_episodes", "candidate_actions", "model_input", "model_inputs",
    "projection", "projections", "trainer_manifest", "trainer_manifests", "training_rows",
    "stop_label", "correct_stop", "semantic_state_delta", "verifier_causality", "level3",
}


class GateError(RuntimeError):
    pass


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    return f"{prefix}_{stable_hash(parts)[:20]}"


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.is_file():
        raise GateError(f"required_input_missing:{path.name}")
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GateError(f"malformed_jsonl:{path.name}:{line_number}") from exc
            if not isinstance(row, dict):
                raise GateError(f"non_object_jsonl_row:{path.name}:{line_number}")
            yield row


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError(f"non_object_json:{path.name}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    os.replace(temporary, path)


def index_unique(rows: Iterable[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        identity = str(row.get(key) or "")
        if not identity:
            raise GateError(f"missing_{label}_identity")
        if identity in result:
            raise GateError(f"duplicate_{label}_identity:{identity}")
        result[identity] = row
    return result


def assert_audit_only_shape(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).casefold()
            if key_text in FORBIDDEN_KEYS or key_text.startswith("model_") or key_text.startswith("trainer_"):
                raise GateError(f"forbidden_output_key:{key}")
            if key_text == "training_allowed" and child is not False:
                raise GateError("training_allowed_must_be_false")
            assert_audit_only_shape(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            assert_audit_only_shape(child)
    elif isinstance(value, str):
        if value.startswith("/") or "raw command" in value.casefold() or "raw output" in value.casefold():
            raise GateError("raw_path_command_or_output_string_emitted")


def hash_inputs(paths: Mapping[str, Path]) -> dict[str, str]:
    return {name: file_sha256(path) for name, path in paths.items()}


def verify_hashes(observed: Mapping[str, str], expected: Mapping[str, str] | None) -> None:
    if expected is None:
        return
    for name, expected_hash in expected.items():
        if observed.get(name) != expected_hash:
            raise GateError(f"input_hash_drift:{name}")


def build_sqlite_index(events_path: Path, pairs_path: Path, database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        CREATE TABLE events(chat_id TEXT, line_number INTEGER, event_id TEXT, payload_type TEXT, role TEXT);
        CREATE TABLE pairs(chat_id TEXT, call_line INTEGER, output_line INTEGER, tool_name TEXT, command_head TEXT);
        """
    )
    event_batch: list[tuple[Any, ...]] = []
    for row in iter_jsonl(events_path):
        event_batch.append((row.get("chat_id"), row.get("line_number"), row.get("event_id"), row.get("payload_type"), row.get("role")))
        if len(event_batch) >= 10000:
            connection.executemany("INSERT INTO events VALUES (?,?,?,?,?)", event_batch)
            event_batch.clear()
    if event_batch:
        connection.executemany("INSERT INTO events VALUES (?,?,?,?,?)", event_batch)
    pair_batch: list[tuple[Any, ...]] = []
    for row in iter_jsonl(pairs_path):
        if row.get("call_before_output") is not True:
            continue
        pair_batch.append((row.get("chat_id"), row.get("call_line_number"), row.get("output_line_number"), row.get("tool_name"), row.get("command_head")))
        if len(pair_batch) >= 10000:
            connection.executemany("INSERT INTO pairs VALUES (?,?,?,?,?)", pair_batch)
            pair_batch.clear()
    if pair_batch:
        connection.executemany("INSERT INTO pairs VALUES (?,?,?,?,?)", pair_batch)
    connection.executescript(
        "CREATE INDEX events_window ON events(chat_id,line_number);"
        "CREATE INDEX pairs_window ON pairs(chat_id,call_line);"
    )
    return connection


def _consistent(values: Sequence[str], label: str, window_id: str) -> str:
    known = {value for value in values if value and value not in {UNKNOWN, "unknown_from_metadata"}}
    if len(known) > 1:
        raise GateError(f"conflicting_{label}_lineage:{window_id}")
    return next(iter(known), UNKNOWN)


def lineage_by_window(join_rows: Iterable[dict[str, Any]], root_rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, str]]:
    joins: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in join_rows:
        joins[str(row.get("task_window_id") or "")].append(row)
    result: dict[str, dict[str, str]] = {}
    seen: set[tuple[str, str, str, str]] = set()
    for row in root_rows:
        if row.get("canonical_for_dedupe_key") is not True or row.get("exact_same_source_join") is not True or row.get("source_kind") != "same_session_observed_trace":
            continue
        parts = row.get("source_session_root_window") or {}
        source, session, root, window = (str(parts.get(key) or "") for key in ("source", "session", "root", "window"))
        identity = (source, session, root, window)
        if not all(identity): raise GateError("incomplete_source_session_root_window_identity")
        if identity in seen: raise GateError("duplicate_source_session_root_window_identity")
        seen.add(identity)
        exact = [j for j in joins.get(window, []) if str((j.get("source_refs") or {}).get("source_file_hash_compat") or "") == source and str((j.get("source_refs") or {}).get("session_id_hash") or "") == session and str(j.get("canonical_root_id") or "") == root]
        result[window] = {"source": source, "session": session, "root_identity": root, "window": window, "dedupe_key": str(row.get("dedupe_key_sha256") or ""), "repo_family": str(row.get("repo_family") or UNKNOWN), "language_family": str(row.get("language_family") or UNKNOWN), "source_root_label": str(exact[0].get("source_root_label") or UNKNOWN) if exact else UNKNOWN, "exact_tuple_join": bool(exact)}
    return result


def is_verifier_head(value: Any) -> bool:
    basename = Path(str(value or "")).name.casefold()
    return basename in VERIFIER_HEADS or basename.endswith("pytest")


def is_verifier_pair(pair: Mapping[str, Any]) -> bool:
    explicit = str(pair.get("recognized_verifier_invocation") or "")
    return explicit in VERIFIER_KINDS if explicit else is_verifier_head(pair.get("command_head"))


def state_probe_kind(pair: Mapping[str, Any]) -> str | None:
    explicit = str(pair.get("recognized_state_probe") or pair.get("state_probe_kind") or "")
    return explicit if explicit in PROBE_KINDS else None


def prior_identities(rows: Iterable[dict[str, Any]]) -> dict[str, set[Any]]:
    result = {key: set() for key in ("task_window", "root", "dedupe", "tuple", "mutated_source")}
    for row in rows:
        identity = row.get("source_identity") or {}
        source, session, root, window = (str(identity.get(key) or "") for key in ("source_file_hash_compat", "session_id_hash", "root_id", "task_window_id"))
        dedupe = str(identity.get("recomputed_dedupe_key_sha256") or "")
        if not all((source, session, root, window, dedupe)):
            raise GateError("stage12586_record_identity_incomplete")
        result["task_window"].add(window); result["root"].add(root); result["dedupe"].add(dedupe); result["tuple"].add((source, session, root, window))
        if (row.get("source_validation") or {}).get("content_hash_match") is not True:
            result["mutated_source"].add(source)
    return result


def terminal_supply_policy(verifier_status: str) -> dict[str, Any]:
    failed = verifier_status == "failed"
    return {
        "terminal_observed": True,
        "terminal_normative_label_emitted": False,
        "needs_stop_policy_review": failed or verifier_status in {UNKNOWN, "running", "incomplete"},
        "supply_class": "negative_or_recovery" if failed else "outcome_review_pending",
        "failed_trajectory_excluded": False,
    }


def prequalify_window(
    window: Mapping[str, Any], events: Sequence[Mapping[str, Any]], pairs: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any] | None, physical: Mapping[str, Any] | None,
    lineage: Mapping[str, str] | None, protected: Mapping[str, set[str]], prior: Mapping[str, set[Any]] | None = None,
) -> dict[str, Any]:
    window_id = str(window.get("task_window_id") or "")
    chat_id = str(window.get("chat_id") or "")
    source = str(window.get("source_file_hash_compat") or "")
    session = str(window.get("session_id_hint") or "")
    if not window_id or not chat_id or not source or not session:
        raise GateError("window_source_session_identity_missing")
    manifest = manifest or {}
    physical = physical or {}
    lineage = lineage or {}
    prior = prior or {key: set() for key in ("task_window", "root", "dedupe", "tuple", "mutated_source")}

    terminal_events = [event for event in events if event.get("payload_type") == "task_complete"]
    aborted_events = [event for event in events if event.get("payload_type") == "turn_aborted"]
    literal_complete = window.get("terminal_status") == "task_complete" and len(terminal_events) == 1 and not aborted_events
    user_signal = any(event.get("role") == "user" or event.get("payload_type") == "user_message" for event in events)
    authoritative_pairs = [pair for pair in pairs if int(pair.get("call_line") or pair.get("call_line_number") or 0) < int(pair.get("output_line") or pair.get("output_line_number") or 0)]
    edit_pairs = [pair for pair in authoritative_pairs if pair.get("tool_name") == "apply_patch"]
    verifier_pairs = [pair for pair in authoritative_pairs if is_verifier_pair(pair)]
    anchor = max((int(pair.get("output_line") or pair.get("output_line_number") or 0) for pair in edit_pairs), default=None)
    post_edit_verifiers = [pair for pair in verifier_pairs if anchor is not None and int(pair.get("call_line") or pair.get("call_line_number") or 0) > anchor]
    explicit_no_edit_candidate = not edit_pairs and bool(verifier_pairs)
    verifier_anchor = anchor if anchor is not None else min((int(pair.get("call_line") or pair.get("call_line_number") or 0) for pair in verifier_pairs), default=None)
    probe_pairs = [pair for pair in authoritative_pairs if state_probe_kind(pair)]
    pre_probes = [pair for pair in probe_pairs if verifier_anchor is not None and int(pair.get("output_line") or pair.get("output_line_number") or 0) < verifier_anchor]
    post_anchor = max((int(pair.get("output_line") or pair.get("output_line_number") or 0) for pair in (post_edit_verifiers or verifier_pairs)), default=verifier_anchor)
    post_probes = [pair for pair in probe_pairs if post_anchor is not None and int(pair.get("call_line") or pair.get("call_line_number") or 0) > post_anchor]

    snapshot_join = bool(
        manifest and physical
        and manifest.get("source_file_hash_compat") == source
        and physical.get("source_file_hash_compat") == source
    )
    root_identity = str(lineage.get("root_identity") or UNKNOWN)
    repo_family = str(lineage.get("repo_family") or UNKNOWN)
    language_family = str(lineage.get("language_family") or UNKNOWN)
    source_root = str(lineage.get("source_root_label") or physical.get("source_root_label") or UNKNOWN)
    protected_kinds: list[str] = []
    if repo_family != UNKNOWN and repo_family.casefold() in protected["repo_family"]:
        protected_kinds.append("repo_family")
    if root_identity != UNKNOWN and root_identity in protected["root_identity"]:
        protected_kinds.append("root_identity")
    if source in protected.get("source_path_hash", set()):
        protected_kinds.append("source_path_hash")

    checks = {
        "literal_task_complete": literal_complete,
        "user_task_signal": user_signal,
        "authoritative_action_observation_pair": bool(authoritative_pairs),
        "observed_edit_pair": bool(edit_pairs),
        "completed_verifier_candidate": bool(post_edit_verifiers) if edit_pairs else bool(verifier_pairs),
        "pre_repo_state_probe_candidate": bool(pre_probes),
        "post_repo_state_probe_candidate": bool(post_probes),
        "snapshot_metadata_join": snapshot_join,
        "exact_source_session_root_window_join": bool(lineage.get("exact_tuple_join")) and (source, stable_hash(session)[:24], root_identity, window_id) == (str(lineage.get("source") or ""), str(lineage.get("session") or ""), root_identity, str(lineage.get("window") or "")),
        "known_source_root": source_root != UNKNOWN,
        "known_repo_family": repo_family != UNKNOWN,
        "known_language_family": language_family not in {UNKNOWN, "unknown_from_metadata"},
        "protected_clearance_known": source_root != UNKNOWN and repo_family != UNKNOWN and root_identity != UNKNOWN,
        "source_not_stage12586_mutated": source not in prior["mutated_source"],
        "prior_batch_identity_clear": not (window_id in prior["task_window"] or root_identity in prior["root"] or str(lineage.get("dedupe_key") or "") in prior["dedupe"] or (source, stable_hash(session)[:24], root_identity, window_id) in prior["tuple"]),
    }
    blockers = sorted(name for name, passed in checks.items() if not passed)
    raw_review: list[str] = []
    if edit_pairs:
        raw_review.append("edit_success_and_payload_observation")
    elif explicit_no_edit_candidate:
        raw_review.append("explicit_no_edit_evidence")
    if verifier_pairs:
        raw_review.extend(("verifier_terminal_completion_and_status", "verifier_relevance_to_edit_or_task"))
    if pre_probes or post_probes:
        raw_review.append("repo_state_probe_semantics_and_success")

    score = (
        100 * int(not blockers) + 20 * min(len(edit_pairs), 3) + 12 * min(len(post_edit_verifiers), 3)
        + 8 * int(bool(pre_probes)) + 8 * int(bool(post_probes)) + 4 * int(repo_family != UNKNOWN)
        + 2 * int(language_family != UNKNOWN)
    )
    policy = terminal_supply_policy(UNKNOWN)
    return {
        "record_type": "stage12588_structural_prequalification_v1",
        "prequalification_id": stable_id("stage12588_prequalification", window_id, source, session, root_identity),
        "task_window_id": window_id,
        "chat_id": chat_id,
        "identity": {
            "source_file_hash_compat": source,
            "session_identity": stable_hash(session)[:24],
            "source_root_label": source_root,
            "root_identity": root_identity,
            "repo_family": repo_family,
            "language_family": language_family,
            "repo_known_for_diversity_credit": repo_family != UNKNOWN,
            "language_known_for_diversity_credit": language_family != UNKNOWN,
        },
        "terminal_observation": {
            "terminal_observed": policy["terminal_observed"] and literal_complete,
            "lifecycle": "task_complete" if literal_complete else str(window.get("terminal_status") or UNKNOWN),
            "normative_label_emitted": policy["terminal_normative_label_emitted"],
            "needs_stop_policy_review": policy["needs_stop_policy_review"],
        },
        "trajectory_supply": {
            "status": policy["supply_class"],
            "failed_trajectory_excluded": policy["failed_trajectory_excluded"],
            "failed_verifier_policy": "preserve_as_negative_or_recovery_supply",
        },
        "evidence_shape": {
            "authoritative_pair_count": len(authoritative_pairs),
            "observed_edit_pair_candidate_count": len(edit_pairs),
            "explicit_no_edit_evidence_candidate": explicit_no_edit_candidate,
            "post_edit_verifier_candidate_count": len(post_edit_verifiers),
            "verifier_candidate_count": len(verifier_pairs),
            "pre_repo_state_probe_candidate_count": len(pre_probes),
            "post_repo_state_probe_candidate_count": len(post_probes),
        },
        "structural_checks": checks,
        "trajectory_atom_prequalification": {
            "structurally_capable": not blockers,
            "blockers": blockers,
            "raw_private_review_required": sorted(set(raw_review)),
        },
        "ranking_eligibility": {"eligible": False, "candidate_alternative_count": 0},
        "protected_overlap": {"overlap": bool(protected_kinds), "matched_identity_kinds": protected_kinds},
        "prior_overlap": {"overlap": not checks["prior_batch_identity_clear"]},
        "ranking_score": score,
        "training_allowed": False,
    }


def rank_requests(rows: Sequence[dict[str, Any]], target: int = 300, chat_cap: int = 3, repo_fraction_cap: float = 0.15) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = sorted(
        (row for row in rows if row["trajectory_atom_prequalification"]["structurally_capable"] and not row["protected_overlap"]["overlap"]),
        key=lambda row: (-int(row["ranking_score"]), row["task_window_id"]),
    )
    selected: list[dict[str, Any]] = []
    overflow: list[dict[str, Any]] = []
    chat_counts: Counter[str] = Counter()
    session_counts: Counter[str] = Counter()
    repo_counts: Counter[str] = Counter()
    known_repo_limit = max(1, math.floor(target * repo_fraction_cap))
    for row in eligible:
        chat = row["chat_id"]
        session = row["identity"]["session_identity"]
        repo = row["identity"]["repo_family"]
        reason = None
        if len(selected) >= target:
            reason = "target_capacity_overflow"
        elif chat_counts[chat] >= chat_cap or session_counts[session] >= chat_cap:
            reason = "chat_session_cap_overflow"
        elif repo != UNKNOWN and repo_counts[repo] >= known_repo_limit:
            reason = "known_repo_family_cap_overflow"
        if reason:
            overflow.append({
                "task_window_id": row["task_window_id"], "prequalification_id": row["prequalification_id"],
                "overflow_reason": reason, "permanent_source_exclusion": False, "training_allowed": False,
            })
            continue
        selected.append({
            "request_rank": len(selected) + 1,
            "task_window_id": row["task_window_id"],
            "prequalification_id": row["prequalification_id"],
            "chat_id": chat,
            "identity": row["identity"],
            "raw_private_review_required": row["trajectory_atom_prequalification"]["raw_private_review_required"],
            "terminal_observed": row["terminal_observation"]["terminal_observed"],
            "needs_stop_policy_review": row["terminal_observation"]["needs_stop_policy_review"],
            "candidate_alternative_count": 0,
            "ranking_eligible": False,
            "training_allowed": False,
        })
        chat_counts[chat] += 1
        session_counts[session] += 1
        if repo != UNKNOWN:
            repo_counts[repo] += 1
    # A partially filled pool can make a target-relative cap too permissive.
    # Demote the lowest-ranked excess rows until the final pool itself complies.
    while selected:
        final_repo_counts = Counter(
            row["identity"]["repo_family"]
            for row in selected
            if row["identity"]["repo_family"] != UNKNOWN
        )
        violating = {
            repo for repo, count in final_repo_counts.items()
            if count / len(selected) > repo_fraction_cap
        }
        if not violating:
            break
        index = max(
            idx for idx, row in enumerate(selected)
            if row["identity"]["repo_family"] in violating
        )
        demoted = selected.pop(index)
        overflow.append({
            "task_window_id": demoted["task_window_id"],
            "prequalification_id": demoted["prequalification_id"],
            "overflow_reason": "known_repo_family_final_fraction_overflow",
            "permanent_source_exclusion": False,
            "training_allowed": False,
        })
    for rank, row in enumerate(selected, 1):
        row["request_rank"] = rank
    return selected, overflow


def dominance(rows: Sequence[dict[str, Any]], field: str) -> dict[str, Any]:
    counts = Counter(str(row["identity"].get(field) or UNKNOWN) for row in rows)
    known = {key: value for key, value in counts.items() if key != UNKNOWN}
    top_known = sorted(known.items(), key=lambda item: (-item[1], item[0]))[:10]
    return {
        "counts": dict(sorted(counts.items())),
        "top_known": [{"identity": key, "count": value, "fraction": value / len(rows) if rows else 0.0} for key, value in top_known],
        "unknown_count": counts[UNKNOWN],
        "unknown_excluded_from_diversity_credit": True,
    }


def execute(
    *, inputs: Mapping[str, Path] = INPUTS, out: Path = OUT, summary_path: Path = SUMMARY,
    expected_hashes: Mapping[str, str] | None = PINNED_INPUT_SHA256, target: int = 300,
) -> dict[str, Any]:
    before_hashes = hash_inputs(inputs)
    verify_hashes(before_hashes, expected_hashes)
    manifests = index_unique(iter_jsonl(inputs["chat_manifests"]), "chat_id", "chat")
    physical = index_unique(iter_jsonl(inputs["physical_inventory"]), "source_file_hash_compat", "source")
    lineage = lineage_by_window(iter_jsonl(inputs["repo_state_joins"]), iter_jsonl(inputs["trajectory_roots"]))
    prior = prior_identities(iter_jsonl(inputs["prior_hydrated_records"]))
    deny = read_json(inputs["protected_denylist"]).get("deny") or {}
    protected = {
        "repo_family": {str(value).casefold() for value in deny.get("repo_family", [])},
        "root_identity": {str(value) for value in deny.get("root_identity", [])},
        "source_path_hash": {hashlib.sha1(str(value).encode()).hexdigest() for value in deny.get("source_path", [])},
    }

    rows: list[dict[str, Any]] = []
    seen_windows: set[str] = set()
    seen_composites: set[tuple[str, str, str, str]] = set()
    with tempfile.TemporaryDirectory(prefix="stage12588_") as temporary:
        database_path = Path(temporary) / "indexed_metadata.sqlite"
        connection = build_sqlite_index(inputs["event_index"], inputs["authoritative_pairs"], database_path)
        try:
            for window in iter_jsonl(inputs["task_windows"]):
                window_id = str(window.get("task_window_id") or "")
                if window_id in seen_windows:
                    raise GateError(f"duplicate_window_identity:{window_id}")
                seen_windows.add(window_id)
                chat_id = str(window.get("chat_id") or "")
                start, end = int(window.get("start_line") or 0), int(window.get("end_line") or 0)
                event_rows = [
                    {"line_number": row[0], "event_id": row[1], "payload_type": row[2], "role": row[3]}
                    for row in connection.execute(
                        "SELECT line_number,event_id,payload_type,role FROM events WHERE chat_id=? AND line_number BETWEEN ? AND ? ORDER BY line_number",
                        (chat_id, start, end),
                    )
                ]
                pair_rows = [
                    {"call_line": row[0], "output_line": row[1], "tool_name": row[2], "command_head": row[3]}
                    for row in connection.execute(
                        "SELECT call_line,output_line,tool_name,command_head FROM pairs WHERE chat_id=? AND call_line BETWEEN ? AND ? AND output_line BETWEEN ? AND ? ORDER BY call_line",
                        (chat_id, start, end, start, end),
                    )
                ]
                manifest = manifests.get(chat_id)
                source = str(window.get("source_file_hash_compat") or "")
                row = prequalify_window(window, event_rows, pair_rows, manifest, physical.get(source), lineage.get(window_id), protected, prior)
                composite = (
                    row["identity"]["source_file_hash_compat"], row["identity"]["session_identity"],
                    row["identity"]["root_identity"], row["task_window_id"],
                )
                if composite in seen_composites:
                    raise GateError("duplicate_source_session_root_window_identity")
                seen_composites.add(composite)
                rows.append(row)
        finally:
            connection.close()

    selected, overflow = rank_requests(rows, target=target)
    if any(item.get("prior_overlap") for item in selected):
        raise GateError("selected_prior_overlap_nonzero")
    if any(row["protected_overlap"]["overlap"] for row in rows if row["task_window_id"] in {item["task_window_id"] for item in selected}):
        raise GateError("protected_overlap_in_selected_pool")

    blockers = Counter(reason for row in rows for reason in row["trajectory_atom_prequalification"]["blockers"])
    exact_complete = sum(row["structural_checks"]["literal_task_complete"] for row in rows)
    user_signal = sum(row["structural_checks"]["user_task_signal"] for row in rows)
    paired = sum(row["structural_checks"]["authoritative_action_observation_pair"] for row in rows)
    edit_or_no_edit = sum(row["structural_checks"]["observed_edit_pair"] for row in rows)
    verifier = sum(row["structural_checks"]["completed_verifier_candidate"] for row in rows)
    pre_probe = sum(row["structural_checks"]["pre_repo_state_probe_candidate"] for row in rows)
    post_probe = sum(row["structural_checks"]["post_repo_state_probe_candidate"] for row in rows)
    immutable = sum(row["structural_checks"]["snapshot_metadata_join"] for row in rows)
    capable = sum(row["trajectory_atom_prequalification"]["structurally_capable"] for row in rows)
    conversion = read_json(inputs["hydration_summary"])["counts"]
    conversion_numerator = int(conversion["hydrated_core_records"])
    conversion_denominator = int(conversion["hydration_records"])
    estimated_yield = len(selected) * conversion_numerator / conversion_denominator
    overflow_counts = Counter(row["overflow_reason"] for row in overflow)
    selected_source_rows = [next(row for row in rows if row["task_window_id"] == item["task_window_id"]) for item in selected]
    selected_chat_counts = Counter(item["chat_id"] for item in selected)
    selected_session_counts = Counter(item["identity"]["session_identity"] for item in selected)
    summary = {
        "stage": STAGE,
        "record_type": "stage12588_full_inventory_trajectory_prequalification_summary_v1",
        "status": "AUDIT_ONLY_FULL_INVENTORY_PREQUALIFICATION_COMPLETE",
        "decision": "hydration_requests_prequalified_no_trajectory_or_ranking_admission",
        "claim_boundary": "Structural metadata prequalification and hydration routing only. Payload-dependent completion, relevance, edit/no-edit evidence, probe success, and outcome policy remain private-review questions. Terminal lifecycle is observed behavior, not a normative stop target.",
        "training_allowed": False,
        "funnel_counts": {
            "all_task_windows_scanned": len(rows),
            "literal_task_complete": exact_complete,
            "user_task_signal": user_signal,
            "authoritative_action_observation_pair": paired,
            "observed_edit_pair": edit_or_no_edit,
            "completed_verifier_candidate": verifier,
            "pre_repo_state_probe_candidate": pre_probe,
            "post_repo_state_probe_candidate": post_probe,
            "snapshot_metadata_join": immutable,
            "structurally_capable": capable,
            "selected_hydration_requests": len(selected),
            "overflow_requests": len(overflow),
            "candidate_alternatives": 0,
            "ranking_eligible": 0,
        },
        "blocker_histogram": dict(sorted(blockers.items())),
        "overflow_histogram": dict(sorted(overflow_counts.items())),
        "dominance": {
            "chat": {
                "counts": dict(sorted(selected_chat_counts.items())),
                "top": [
                    {"identity": key, "count": value, "fraction": value / len(selected)}
                    for key, value in selected_chat_counts.most_common(10)
                ],
                "maximum_selected_per_chat": max(selected_chat_counts.values(), default=0),
                "maximum_selected_per_session": max(selected_session_counts.values(), default=0),
            },
            "repo": dominance(selected_source_rows, "repo_family"),
            "language": dominance(selected_source_rows, "language_family"),
        },
        "sampling_caps": {"target": target, "maximum_per_chat_session": 3, "maximum_known_repo_family_fraction": 0.15, "caps_are_permanent_source_exclusions": False},
        "estimated_raw_private_hydration_yield": {
            "label": "estimate_only_using_stage12586_observed_conversion_not_a_guarantee",
            "stage12586_observed_numerator": conversion_numerator,
            "stage12586_observed_denominator": conversion_denominator,
            "observed_rate": conversion_numerator / conversion_denominator,
            "selected_request_count": len(selected),
            "estimated_yield": estimated_yield,
        },
        "terminal_outcome_contract": {
            "task_complete_is_normative_stop_label": False,
            "failed_relevant_verifier_trajectory_excluded": False,
            "failed_relevant_verifier_supply": "negative_or_recovery",
            "needs_stop_policy_review_required_after_failed_verifier": True,
        },
        "mutation_and_hash_checks": {"input_hashes_before": before_hashes, "input_hashes_after": {}, "all_inputs_unchanged": False},
        "guardrails": {
            "raw_paths_emitted": False, "raw_text_emitted": False, "raw_commands_emitted": False,
            "raw_outputs_emitted": False, "candidate_alternatives_emitted": False,
            "ranking_eligibility_emitted": False, "training_artifacts_emitted": False,
        },
    }
    after_hashes = hash_inputs(inputs)
    if after_hashes != before_hashes:
        raise GateError("input_hash_drift_during_execution")
    summary["mutation_and_hash_checks"]["input_hashes_after"] = after_hashes
    summary["mutation_and_hash_checks"]["all_inputs_unchanged"] = True
    assert_audit_only_shape(rows)
    assert_audit_only_shape(selected)
    assert_audit_only_shape(overflow)
    assert_audit_only_shape(summary)
    write_jsonl(out / "full_inventory_prequalification.jsonl", rows)
    write_jsonl(out / "selected_hydration_requests.jsonl", selected)
    write_jsonl(out / "hydration_request_overflow.jsonl", overflow)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    report = (
        "# Stage12588 Full-Inventory Trajectory Prequalification\n\n"
        "Audit-only structural prequalification. It does not repeat the Stage12263 25-window pilot.\n\n"
        f"Scanned `{len(rows)}` windows, structurally prequalified `{capable}`, selected `{len(selected)}` hydration requests, and queued `{len(overflow)}` overflow requests.\n\n"
        "`task_complete` is a literal terminal observation, never a correct-STOP target. Failed relevant-verifier trajectories remain negative/recovery supply and require stop-policy review.\n\n"
        "No private payload, path, command, output, candidate alternative, ranking eligibility, admission, or training artifact is emitted.\n"
    )
    (out / "STAGE12588_FULL_INVENTORY_TRAJECTORY_PREQUALIFICATION.md").write_text(report, encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=300)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = execute(target=args.target)
    print(json.dumps(summary["funnel_counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
