#!/usr/bin/env python3
"""Resolve every Stage12588 candidate into bounded, non-admitting observations."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12589_raw_private_resolution"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
RAW_ROOT = Path("/home/peyton/.codex/sessions")
INPUTS = {
    "profiles": ROOT / "runs/local/artifacts/stage12588_full_inventory_trajectory_prequalification/full_inventory_prequalification.jsonl",
    "physical_inventory": ROOT / "runs/local/artifacts/stage12256_live_physical_session_inventory_refresh/live_physical_source_records.jsonl",
    "chat_manifests": ROOT / "runs/local/artifacts/stage12258_live_codex_chat_reconstruction_index/per_chat_manifest.jsonl",
    "event_index": ROOT / "runs/local/artifacts/stage12258_live_codex_chat_reconstruction_index/chat_event_index.jsonl",
    "authoritative_pairs": ROOT / "runs/local/artifacts/stage12259_codex_tool_call_observation_pairer/tool_call_observation_pairs.jsonl",
    "task_windows": ROOT / "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner/codex_task_windows.jsonl",
    "prior_records": ROOT / "runs/local/artifacts/stage12586_raw_private_observed_window_hydrator/raw_private_observed_windows.jsonl",
    "protected_denylist": ROOT / "configs/software_maintainer/future_eval_identity_denylist_v1.json",
}
REQUIRED_PROFILE_CHECKS = (
    "literal_task_complete", "user_task_signal", "authoritative_action_observation_pair",
    "observed_edit_pair", "completed_verifier_candidate", "snapshot_metadata_join",
    "prior_batch_identity_clear", "source_not_stage12586_mutated",
)
SAFE_ENUM = re.compile(r"^[a-zA-Z0-9_.:-]+$")
HEX = re.compile(r"^[0-9a-f]{40,64}$")
FORBIDDEN_KEYS = {
    "path", "command", "output", "patch", "text", "url", "secret", "admission",
    "level3", "ranking_eligible", "training_credit", "model_input", "projection",
}
RULE_EXACT_SELECTED_TEST = "REL_EXACT_SELECTED_TEST_PATH_V1"
RULE_CHANGED_TEST = "REL_CHANGED_TARGET_TEST_RELATION_V1"
RULE_REPO_WIDE = "REL_REPO_WIDE_BOUND_ROOT_V1"


class GateError(RuntimeError):
    pass


def _load_hydrator():
    path = ROOT / "scripts/build_stage12586_raw_private_observed_window_hydrator.py"
    spec = importlib.util.spec_from_file_location("stage12586_parser_for_stage12589", path)
    if not spec or not spec.loader:
        raise GateError("stage12586_parser_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


H = _load_hydrator()


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    return f"{prefix}_{stable_hash(parts)[:20]}"


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.is_file():
        raise GateError(f"required_input_missing:{path.name}")
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GateError(f"malformed_jsonl:{path.name}:{number}") from exc
            if not isinstance(row, dict):
                raise GateError(f"non_object_jsonl:{path.name}:{number}")
            yield row


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    os.replace(tmp, path)


def assert_safe_output(value: Any, key: str = "") -> None:
    if isinstance(value, Mapping):
        for child_key, child in value.items():
            folded = str(child_key).casefold()
            if folded in FORBIDDEN_KEYS or any(token in folded for token in ("raw_", "command", "output", "patch", "path")):
                raise GateError(f"forbidden_output_key:{child_key}")
            assert_safe_output(child, str(child_key))
    elif isinstance(value, (list, tuple)):
        for child in value:
            assert_safe_output(child, key)
    elif isinstance(value, str):
        if "/" in value or "\\" in value or "://" in value or not SAFE_ENUM.fullmatch(value):
            raise GateError(f"unsafe_output_string:{key}")
        if any(marker in value.casefold() for marker in ("bearer", "private_key", "api_key", "password")):
            raise GateError(f"secret_like_output:{key}")


def index_unique(rows: Iterable[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        identity = str(row.get(key) or "")
        if not identity or identity in result:
            raise GateError(f"duplicate_or_missing_identity:{key}")
        result[identity] = row
    return result


def prior_exclusions(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "window": set(), "root": set(), "dedupe": set(), "tuple": set(),
        "mutated_source": set(), "source_intervals": defaultdict(list),
        "source_actions": defaultdict(set),
    }
    for row in rows:
        identity = row.get("source_identity") or {}
        source = str(identity.get("source_file_hash_compat") or "")
        session = str(identity.get("session_id_hash") or "")
        root = str(identity.get("root_id") or "")
        window = str(identity.get("task_window_id") or "")
        dedupe = str(identity.get("recomputed_dedupe_key_sha256") or "")
        if not all((source, session, root, window, dedupe)):
            raise GateError("prior_identity_incomplete")
        result["window"].add(window)
        result["root"].add(root)
        result["dedupe"].add(dedupe)
        result["tuple"].add(stable_hash((source, session, root, window)))
        boundary = row.get("task_boundary") or {}
        begin, finish = int(boundary.get("start_line") or 0), int(boundary.get("end_line") or -1)
        if begin > 0 and finish >= begin:
            result["source_intervals"][source].append((begin, finish))
        for edit in (row.get("edit_evidence") or {}).get("observed_edits") or []:
            line = int(edit.get("call_line_number") or 0)
            targets = tuple(sorted(str(value) for value in edit.get("target_path_sha256") or []))
            if line and targets:
                result["source_actions"][source].add(stable_hash((source, line, targets)))
        validation = row.get("source_validation") or {}
        if validation and validation.get("content_hash_match") is not True:
            result["mutated_source"].add(source)
    return result


def candidate_reason(row: Mapping[str, Any], prior: Mapping[str, Any]) -> str | None:
    checks = row.get("structural_checks") or {}
    if not all(checks.get(name) is True for name in REQUIRED_PROFILE_CHECKS):
        return "corrected_profile_prerequisite_failed"
    identity = row.get("identity") or {}
    source = str(identity.get("source_file_hash_compat") or "")
    window = str(row.get("task_window_id") or "")
    if window in prior["window"]:
        return "stage12586_task_window_overlap"
    if source in prior["mutated_source"]:
        return "stage12586_mutated_source"
    return None


def route_universe(rows: Sequence[dict[str, Any]], prior: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Partition every profile; ranks are audit metadata, never hydration caps."""
    seen: set[str] = set()
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in rows:
        window = str(row.get("task_window_id") or "")
        if not window or window in seen:
            raise GateError("duplicate_candidate_identity")
        seen.add(window)
        reason = candidate_reason(row, prior)
        if reason is None:
            eligible.append(row)
        else:
            excluded.append({"task_window_id": window, "exclusion_reason": reason, "selection_credit": False, "training_allowed": False})
    eligible.sort(key=lambda row: (-int(row.get("ranking_score") or 0), str(row["task_window_id"])))
    session_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    selected: list[dict[str, Any]] = []
    for global_rank, row in enumerate(eligible, 1):
        identity = row.get("identity") or {}
        session = str(identity.get("session_identity") or "")
        source = str(identity.get("source_file_hash_compat") or "")
        session_counts[session] += 1
        source_counts[source] += 1
        selected.append({
            "resolution_request_id": stable_id("stage12589_request", row["task_window_id"]),
            "prequalification_id": row["prequalification_id"],
            "task_window_id": row["task_window_id"],
            "chat_id": str(row.get("chat_id") or ""),
            "session_identity": session,
            "source_identity": source,
            "global_rank": global_rank,
            "within_session_rank": session_counts[session],
            "within_source_rank": source_counts[source],
            "partition": "full_universe_review",
            "selection_credit": False,
            "training_allowed": False,
        })
    return selected, excluded


def route_batch(rows: Sequence[dict[str, Any]], prior: Mapping[str, Any], target: int = 80, cap: int = 3) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    del target, cap
    return route_universe(rows, prior)

def _normalized(value: str, workdir: str = "") -> str | None:
    return H._normalize_target(value, workdir)


def _subject(path: str) -> tuple[str, str] | None:
    pure = PurePosixPath(path)
    stem = pure.stem.casefold()
    is_test = stem.startswith("test_") or stem.endswith("_test") or "tests" in pure.parts
    if not is_test:
        return None
    stem = re.sub(r"^(test_|spec_)", "", stem)
    stem = re.sub(r"(_test|_spec)$", "", stem)
    if len(stem) < 3:
        return None
    return (stem, pure.suffix.casefold())


def strong_relevance(edit_targets: Sequence[str], verifier_targets: Sequence[str], verifier_kind: str, bound_root: bool) -> tuple[str, str | None]:
    edit_set, verifier_set = set(edit_targets), set(verifier_targets)
    exact = sorted(edit_set & verifier_set)
    if exact and any(_subject(path) for path in exact):
        return "resolved", RULE_EXACT_SELECTED_TEST
    for changed in sorted(edit_set):
        changed_stem = PurePosixPath(changed).stem.casefold()
        for selected in sorted(verifier_set):
            subject = _subject(selected)
            if subject and subject == (changed_stem, PurePosixPath(changed).suffix.casefold()):
                return "resolved", RULE_CHANGED_TEST
    repo_wide = verifier_kind in {"pytest", "python_module_pytest", "cargo_test", "go_test", "ctest", "typescript_check", "package_script_check"}
    if not verifier_targets and repo_wide and bound_root:
        return "resolved", RULE_REPO_WIDE
    return "unresolved", None


def _root_binding(args: Mapping[str, Any], manifest: Mapping[str, Any]) -> tuple[bool, str | None]:
    workdir = str(args.get("workdir") or "")
    if not workdir or not Path(workdir).is_absolute():
        return False, None
    hints = [str(item[0]) for key in ("cwd_hints_top", "workspace_root_hints_top") for item in manifest.get(key, []) if isinstance(item, list) and item]
    bound = workdir in hints
    return bound, stable_hash(workdir) if bound else None


def _base_atom(request: Mapping[str, Any], atom_index: int) -> dict[str, Any]:
    return {
        "record_type": "stage12589_bounded_atom_resolution_v2",
        "resolution_record_id": stable_id("stage12589_atom", request.get("resolution_request_id"), atom_index),
        "resolution_request_id": request.get("resolution_request_id"),
        "task_window_id": request.get("task_window_id"),
        "atom_index": atom_index,
        "global_rank": request.get("global_rank"),
        "within_source_rank": request.get("within_source_rank", 1),
        "source_validation": "unresolved",
        "edit_resolution": "unresolved",
        "verifier_resolution": "unresolved",
        "verifier_status": "unresolved",
        "verifier_relevance": "unresolved",
        "semantic_rule_id": "none",
        "ordered_pre_post_probe_observed": "unresolved",
        "root_binding": "unresolved",
        "protected_resolution": "unresolved",
        "terminal_observed": False,
        "normative_policy_correctness": "unresolved",
        "positive_stop_target_allowed": False,
        "supply_class": "blocked",
        "classification": "blocked",
        "blocker_reasons": [],
        "ambiguous": False,
        "level3_allowed": False,
        "admission_allowed": False,
        "training_allowed": False,
        "ranking_credit_allowed": False,
    }


def read_source_snapshot(path: Path, source: str) -> tuple[dict[str, Any] | None, list[str]]:
    if H.sha1_text(str(path)) != source:
        return None, ["physical_source_identity_mismatch"]
    try:
        stat = path.stat()
        content = path.read_bytes()
    except OSError:
        return None, ["physical_source_unreadable"]
    return {
        "content_sha256": hashlib.sha256(content).hexdigest(),
        "size": stat.st_size,
        "mtime": H.iso_utc(stat.st_mtime),
        "lines": content.splitlines(keepends=True),
    }, []


def events_from_snapshot(snapshot: Mapping[str, Any], source: str, start_line: int, end_line: int,
                         manifest: Mapping[str, Any], inventory: Mapping[str, Any]) -> tuple[dict[int, dict[str, Any]], list[str]]:
    blockers: list[str] = []
    expected_sizes = {int(value) for value in (manifest.get("file_size_bytes"), inventory.get("file_size_bytes")) if isinstance(value, int)}
    if expected_sizes and int(snapshot["size"]) not in expected_sizes:
        blockers.append("physical_source_size_mutated")
    expected_mtimes = {str(value) for value in (manifest.get("mtime_utc"), inventory.get("mtime_utc")) if value}
    if expected_mtimes and str(snapshot["mtime"]) not in expected_mtimes:
        blockers.append("physical_source_mtime_mutated")
    expected_sha = str(manifest.get("file_content_sha256") or "")
    if not expected_sha or str(snapshot["content_sha256"]) != expected_sha:
        blockers.append("physical_source_content_sha256_mutated")
    lines = snapshot["lines"]
    if start_line < 1 or end_line < start_line or end_line > len(lines):
        blockers.append("task_window_lines_missing_from_raw_source")
    if blockers:
        return {}, sorted(set(blockers))
    events: dict[int, dict[str, Any]] = {}
    for line_number in range(start_line, end_line + 1):
        try:
            value = json.loads(lines[line_number - 1].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            blockers.append("raw_window_json_parse_failure")
            continue
        if not isinstance(value, dict):
            blockers.append("raw_window_non_object_event")
        else:
            events[line_number] = value
    return events, sorted(set(blockers))


def _parse_actions(events: Mapping[int, dict[str, Any]], indexed_rows: Sequence[dict[str, Any]],
                   pair_rows: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    blockers: list[str] = []
    indexed = {int(row["line_number"]): row for row in indexed_rows}
    if any(not H._indexed_event_matches(events.get(line, {}), row) for line, row in indexed.items()):
        blockers.append("raw_event_index_digest_mismatch")
    pairs: dict[tuple[str, int], dict[str, Any]] = {}
    for pair in pair_rows:
        key = (str(pair.get("call_id") or ""), int(pair.get("call_line_number") or 0))
        if key in pairs:
            raise GateError("duplicate_authoritative_pair_identity")
        pairs[key] = pair
    outputs: defaultdict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    calls: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    for line, event in sorted(events.items()):
        payload = H.payload_of(event)
        if payload.get("type") in {"function_call", "custom_tool_call"}:
            args = H.safe_json_object(payload.get("arguments"))
            if not args and isinstance(payload.get("input"), dict):
                args = dict(payload["input"])
            elif not args and isinstance(payload.get("input"), str):
                args = {"input": payload["input"]}
            calls.append((line, payload, args))
        elif payload.get("type") in {"function_call_output", "custom_tool_call_output"}:
            outputs[str(payload.get("call_id") or "")].append((line, payload))
    actions: list[dict[str, Any]] = []
    for sequence, (line, payload, args) in enumerate(calls, 1):
        call_id, tool = str(payload.get("call_id") or ""), str(payload.get("name") or "")
        pair, observed = pairs.get((call_id, line)), outputs.get(call_id, [])
        if not pair or not observed:
            continue
        out_line, out_payload = observed[0]
        call_index, output_index = indexed.get(line, {}), indexed.get(out_line, {})
        valid = bool(
            int(pair.get("output_line_number") or 0) == out_line
            and pair.get("call_before_output") is not False
            and str(pair.get("tool_name") or "") == tool
            and str(pair.get("call_event_id") or "") == str(call_index.get("event_id") or "")
            and str(pair.get("output_event_id") or "") == str(output_index.get("event_id") or "")
            and str(pair.get("output_digest") or "") == str(output_index.get("payload_digest_redacted") or "")
        )
        if not valid or (pair.get("arguments_digest") and H.sha256_json(args) != str(pair["arguments_digest"])):
            blockers.append("authoritative_pair_raw_join_mismatch")
            continue
        command = str(args.get("cmd") or "") if tool == "exec_command" else ""
        actions.append({
            "line": line, "output_line": out_line, "sequence": sequence, "tool": tool,
            "args": args, "payload": payload, "command": command,
            "status": H.output_status(out_payload.get("output"), tool_name=tool),
            "private_output": H.content_text(out_payload.get("output")),
        })
    origins: dict[str, dict[str, Any]] = {}
    for action in actions:
        if action["tool"] == "exec_command":
            match = H.RUNNING_RE.search(action["private_output"])
            if match:
                origins[match.group("session")] = action
        elif action["tool"] == "write_stdin":
            origin = origins.get(str(action["args"].get("session_id") or ""))
            if origin:
                origin["private_output"] += "\n" + action["private_output"]
                origin["status"] = H.output_status(origin["private_output"])
            else:
                blockers.append("write_stdin_originating_command_missing")
    return actions, blockers


def _protected_clearance(actions: Sequence[dict[str, Any]], manifest: Mapping[str, Any],
                         protected: Mapping[str, set[str]]) -> tuple[str, str | None]:
    workdirs = {str(action["args"].get("workdir") or "") for action in actions if action["args"].get("workdir")}
    if len(workdirs) != 1:
        return "unresolved", None
    workdir = next(iter(workdirs))
    if not Path(workdir).is_absolute():
        return "unresolved", None
    hints = {str(item[0]) for key in ("cwd_hints_top", "workspace_root_hints_top") for item in manifest.get(key, []) if isinstance(item, list) and item}
    if workdir not in hints:
        return "unresolved", None
    root_id = stable_id("canonical_root", workdir)
    family = Path(workdir).name.casefold()
    overlap = (
        workdir in protected.get("source_path", set())
        or root_id in protected.get("root_identity", set())
        or family in {value.casefold() for value in protected.get("repo_family", set())}
    )
    return ("overlap" if overlap else "clear"), root_id


def resolve_window(request: Mapping[str, Any], profile: Mapping[str, Any], window: Mapping[str, Any],
                   manifest: Mapping[str, Any], inventory: Mapping[str, Any], indexed_rows: Sequence[dict[str, Any]],
                   pair_rows: Sequence[dict[str, Any]], raw_path: Path | None, protected: Mapping[str, set[str]],
                   prior: Mapping[str, Any] | None = None, mapping_blockers: Sequence[str] = (),
                   snapshot: Mapping[str, Any] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source = str(request.get("source_identity") or "")
    window_id = str(request.get("task_window_id") or "")
    parent_blockers = list(mapping_blockers)
    if window_id in (prior or {}).get("window", set()):
        parent_blockers.append("stage12586_task_window_overlap")
    begin, finish = int(window.get("start_line") or 0), int(window.get("end_line") or -1)
    intervals = (prior or {}).get("source_intervals", {}).get(source, [])
    if any(max(begin, old_begin) <= min(finish, old_finish) for old_begin, old_finish in intervals):
        parent_blockers.append("stage12586_physical_source_interval_overlap")
    if not raw_path or snapshot is None:
        if not raw_path:
            parent_blockers.append("physical_source_unavailable")
        else:
            snapshot, snapshot_blockers = read_source_snapshot(raw_path, source)
            parent_blockers.extend(snapshot_blockers)
    events: dict[int, dict[str, Any]] = {}
    if snapshot is not None:
        events, validation_blockers = events_from_snapshot(snapshot, source, begin, finish, manifest, inventory)
        parent_blockers.extend(validation_blockers)
    actions, action_blockers = _parse_actions(events, indexed_rows, pair_rows) if events else ([], [])
    parent_blockers.extend(action_blockers)
    clearance, root_id = _protected_clearance(actions, manifest, protected)
    if clearance == "overlap":
        parent_blockers.append("protected_identity_overlap")
    elif clearance != "clear":
        parent_blockers.append("protected_identity_unresolved")
    session = str((profile.get("identity") or {}).get("session_identity") or "")
    if root_id:
        dedupe = stable_hash({"source": source, "session": session, "root": root_id, "window": window_id})
        identity_tuple = stable_hash((source, session, root_id, window_id))
        if root_id in (prior or {}).get("root", set()):
            parent_blockers.append("stage12586_root_identity_overlap")
        if dedupe in (prior or {}).get("dedupe", set()) or identity_tuple in (prior or {}).get("tuple", set()):
            parent_blockers.append("stage12586_dedupe_tuple_overlap")
    edits: list[dict[str, Any]] = []
    for action in actions:
        fact = H.patch_fact(action["tool"], action["payload"], action["args"], call_line=action["line"], sequence=action["sequence"])
        if fact is None and action["tool"] == "exec_command":
            fact = H._exec_edit_fact(action["command"], action["args"], call_line=action["line"], sequence=action["sequence"])
        if fact and action["status"]["status"] == "passed":
            action_hash = stable_hash((source, action["line"], tuple(sorted(fact["target_path_sha256"]))))
            edits.append({**action, "targets": list(fact["_targets"]), "action_hash": action_hash})
            if action_hash in (prior or {}).get("source_actions", {}).get(source, set()):
                parent_blockers.append("stage12586_physical_action_identity_overlap")
    terminal_line = int(window.get("end_line") or -1)
    terminal = H.payload_of(events.get(terminal_line, {})) if events else {}
    terminal_observed = bool(
        terminal.get("type") == "task_complete" and window.get("terminal_status") == "task_complete"
        and str({int(row["line_number"]): row for row in indexed_rows}.get(terminal_line, {}).get("event_id") or "") == str(window.get("terminal_event_id") or "")
    )
    if not terminal_observed:
        parent_blockers.append("literal_task_complete_not_reobserved")
    atoms: list[dict[str, Any]] = []
    for atom_index, edit in enumerate(edits, 1):
        atom = _base_atom(request, atom_index)
        blockers = list(parent_blockers)
        atom["source_validation"] = "current_hash_size_mtime_verified" if snapshot is not None and not any("source_" in value and "overlap" not in value for value in parent_blockers) else "unresolved"
        atom["edit_resolution"] = "exact_paired_success"
        atom["terminal_observed"] = terminal_observed
        atom["protected_resolution"] = clearance
        atom["root_binding"] = "single_authoritative_root" if root_id else "unresolved"
        next_edit_line = edits[atom_index]["line"] if atom_index < len(edits) else terminal_line + 1
        lower_bound = edits[atom_index - 2]["line"] if atom_index > 1 else begin - 1
        segment_actions = [action for action in actions if edit["line"] < action["line"] < next_edit_line]
        verifiers = []
        for action in segment_actions:
            kind = H.verifier_kind(action["command"]) if action["tool"] == "exec_command" else None
            if kind and action["status"]["status"] in {"passed", "failed"}:
                bound, _ = _root_binding(action["args"], manifest)
                targets = H._verifier_targets(action["command"], str(action["args"].get("workdir") or ""))
                relevance, rule = strong_relevance(edit["targets"], targets, kind, bound)
                verifiers.append((action, relevance, rule))
        if not verifiers:
            blockers.append("terminal_completed_verifier_missing_before_next_edit")
            if atom_index < len(edits):
                blockers.append("multi_edit_segmentation_ambiguous")
                atom["ambiguous"] = True
        else:
            verifier, relevance, rule = verifiers[-1]
            atom["verifier_resolution"] = "terminal_completed"
            atom["verifier_status"] = verifier["status"]["status"]
            atom["verifier_relevance"] = "strong_rule_resolved" if relevance == "resolved" else "unresolved"
            atom["semantic_rule_id"] = rule or "none"
            if relevance != "resolved":
                blockers.append("terminal_verifier_strong_relevance_unresolved")
                if any(item[1] == "resolved" for item in verifiers[:-1]):
                    blockers.append("later_verifier_superseded_positive_observation")
            if verifier["status"]["status"] != "passed":
                blockers.append("terminal_verifier_failed_negative_observation")
                if any(item[0]["status"]["status"] == "passed" and item[1] == "resolved" for item in verifiers[:-1]):
                    blockers.append("later_verifier_superseded_positive_observation")
            probes = []
            for action in actions:
                probe = H.state_probe_kind(action["command"]) if action["tool"] == "exec_command" else None
                bound, digest = _root_binding(action["args"], manifest)
                if probe and bound and action["status"]["status"] == "passed":
                    probes.append((action["line"], digest))
            pre = [probe for probe in probes if lower_bound < probe[0] < edit["line"]]
            post = [probe for probe in probes if verifier["line"] < probe[0] < next_edit_line]
            if pre and post and pre[-1][1] == post[0][1]:
                atom["ordered_pre_post_probe_observed"] = "observed"
            else:
                blockers.append("ordered_pre_post_probe_observation_unresolved")
        atom["blocker_reasons"] = sorted(set(blockers))
        if not atom["blocker_reasons"]:
            atom["classification"] = "resolved_observed_atom_candidate"
            atom["supply_class"] = "observed_positive_outcome_candidate"
        elif atom["verifier_status"] == "failed":
            atom["supply_class"] = "unresolved_negative_observation"
        assert_safe_output(atom)
        atoms.append(atom)
    if not edits:
        parent_blockers.append("exact_successful_edit_not_resolved")
    parent = {
        "record_type": "stage12589_parent_window_resolution_v2",
        "parent_resolution_id": stable_id("stage12589_parent", request.get("resolution_request_id")),
        "resolution_request_id": request.get("resolution_request_id"),
        "task_window_id": window_id,
        "bounded_atom_count": len(atoms),
        "resolved_atom_count": sum(atom["classification"] == "resolved_observed_atom_candidate" for atom in atoms),
        "blocked_atom_count": sum(atom["classification"] == "blocked" for atom in atoms),
        "ambiguous_atom_count": sum(bool(atom["ambiguous"]) for atom in atoms),
        "resolution": "resolved" if atoms and all(atom["classification"] == "resolved_observed_atom_candidate" for atom in atoms) else "blocked_or_ambiguous",
        "blocker_reasons": sorted(set(parent_blockers + [reason for atom in atoms for reason in atom["blocker_reasons"]])),
        "level3_allowed": False, "admission_allowed": False, "training_allowed": False, "ranking_credit_allowed": False,
    }
    assert_safe_output(parent)
    return atoms, parent


def resolve_private(request: Mapping[str, Any], profile: Mapping[str, Any], window: Mapping[str, Any], manifest: Mapping[str, Any],
                    inventory: Mapping[str, Any], indexed_rows: Sequence[dict[str, Any]], pair_rows: Sequence[dict[str, Any]],
                    raw_path: Path | None, protected: Mapping[str, set[str]], mapping_blockers: Sequence[str] = ()) -> dict[str, Any]:
    atoms, parent = resolve_window(request, profile, window, manifest, inventory, indexed_rows, pair_rows, raw_path, protected, mapping_blockers=mapping_blockers)
    return atoms[0] if atoms else {**_base_atom(request, 0), "blocker_reasons": parent["blocker_reasons"]}

def execute(*, inputs: Mapping[str, Path] = INPUTS, out: Path = OUT, summary_path: Path = SUMMARY,
            raw_root: Path = RAW_ROOT, target: int = 80) -> dict[str, Any]:
    del target
    prior = prior_exclusions(iter_jsonl(inputs["prior_records"]))
    profiles = list(iter_jsonl(inputs["profiles"]))
    requests, excluded = route_universe(profiles, prior)
    profile_by_window = {str(row["task_window_id"]): row for row in profiles}
    wanted_windows = {str(row["task_window_id"]) for row in requests}
    windows = {str(row["task_window_id"]): row for row in iter_jsonl(inputs["task_windows"]) if str(row.get("task_window_id")) in wanted_windows}
    chats = {str(window.get("chat_id")) for window in windows.values()}
    manifests = {str(row["chat_id"]): row for row in iter_jsonl(inputs["chat_manifests"]) if str(row.get("chat_id")) in chats}
    sources = {str(row["source_identity"]) for row in requests}
    inventory = {str(row["source_file_hash_compat"]): row for row in iter_jsonl(inputs["physical_inventory"]) if str(row.get("source_file_hash_compat")) in sources}
    resolved_paths, mapping_blockers = H.resolve_source_paths(raw_root, inventory, sources)
    event_rows: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    ranges = {chat: [(int(window["start_line"]), int(window["end_line"]), wid) for wid, window in windows.items() if str(window.get("chat_id")) == chat] for chat in chats}
    for row in iter_jsonl(inputs["event_index"]):
        chat, line = str(row.get("chat_id") or ""), int(row.get("line_number") or 0)
        for begin, finish, wid in ranges.get(chat, []):
            if begin <= line <= finish:
                event_rows[wid].append(row)
    pairs: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in iter_jsonl(inputs["authoritative_pairs"]):
        chat = str(row.get("chat_id") or "")
        call_line, output_line = int(row.get("call_line_number") or 0), int(row.get("output_line_number") or 0)
        for begin, finish, wid in ranges.get(chat, []):
            if begin <= call_line <= output_line <= finish:
                pairs[wid].append(row)
    deny = json.loads(inputs["protected_denylist"].read_text(encoding="utf-8")).get("deny") or {}
    protected = {key: {str(value) for value in values} for key, values in deny.items()}
    snapshots: dict[str, Mapping[str, Any] | None] = {}
    snapshot_blockers: dict[str, list[str]] = {}
    for source in sorted(sources):
        raw_path = resolved_paths.get(source)
        if raw_path:
            snapshots[source], snapshot_blockers[source] = read_source_snapshot(raw_path, source)
        else:
            snapshots[source], snapshot_blockers[source] = None, ["physical_source_unavailable"]
    atom_records: list[dict[str, Any]] = []
    parent_records: list[dict[str, Any]] = []
    for request in sorted(requests, key=lambda row: (str(row["source_identity"]), int(row["within_source_rank"]))):
        wid, source = str(request["task_window_id"]), str(request["source_identity"])
        window = windows.get(wid, {})
        manifest = manifests.get(str(window.get("chat_id") or ""), {})
        atoms, parent = resolve_window(
            request, profile_by_window[wid], window, manifest, inventory.get(source, {}), event_rows[wid], pairs[wid],
            resolved_paths.get(source), protected, prior=prior,
            mapping_blockers=sorted(set(mapping_blockers.get(source, []) + snapshot_blockers.get(source, []))),
            snapshot=snapshots.get(source),
        )
        atom_records.extend(atoms)
        parent_records.append(parent)
    blockers = Counter(reason for atom in atom_records for reason in atom["blocker_reasons"])
    for parent in parent_records:
        if not parent["bounded_atom_count"]:
            blockers.update(parent["blocker_reasons"])
    resolved_count = sum(row["classification"] == "resolved_observed_atom_candidate" for row in atom_records)
    ambiguous_count = sum(bool(row["ambiguous"]) for row in atom_records)
    blocked_count = sum(row["classification"] == "blocked" for row in atom_records)
    summary = {
        "stage": STAGE,
        "status": "raw_private_resolution_complete",
        "candidate_universe_count": len(requests),
        "source_group_count": len(sources),
        "source_current_read_count": len(sources),
        "windows_reviewed": len(parent_records),
        "bounded_atoms_proposed": len(atom_records),
        "resolved_observed_atom_candidate_count": resolved_count,
        "blocked_atom_count": blocked_count,
        "ambiguous_atom_count": ambiguous_count,
        "blocked_or_ambiguous_window_count": sum(parent["resolution"] != "resolved" for parent in parent_records),
        "excluded_profile_count": len(excluded),
        "blocker_histogram": [{"reason": reason, "count": count} for reason, count in sorted(blockers.items())],
        "stage12588_structurally_capable_count_preserved": 0,
        "level3_allowed": False,
        "admission_allowed": False,
        "training_allowed": False,
        "ranking_credit_allowed": False,
    }
    for value in (requests, excluded, atom_records, parent_records, summary):
        assert_safe_output(value)
    write_jsonl(out / "full_universe_review.jsonl", requests)
    write_jsonl(out / "excluded_profiles.jsonl", excluded)
    write_jsonl(out / "safe_resolution_records.jsonl", atom_records)
    write_jsonl(out / "parent_window_resolutions.jsonl", parent_records)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    report = (
        "# Stage12589 Raw-Private Resolution\n\n"
        f"Reviewed `{len(parent_records)}` windows from the full `{len(requests)}`-candidate universe across `{len(sources)}` source reads. "
        f"Proposed `{len(atom_records)}` bounded atoms: `{resolved_count}` resolved, `{blocked_count}` blocked, and `{ambiguous_count}` ambiguous.\n\n"
        "Policy correctness remains unresolved, positive STOP targets are disabled, and all records remain non-Level3, non-admitting, non-ranking, and training-disabled.\n"
    )
    (out / "STAGE12589_RAW_PRIVATE_RESOLUTION.md").write_text(report, encoding="utf-8")
    return summary

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=80)
    args = parser.parse_args()
    summary = execute(target=args.target)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
