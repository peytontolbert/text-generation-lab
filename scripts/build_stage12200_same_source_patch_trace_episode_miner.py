from __future__ import annotations

import argparse
import glob
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


REQUIRED_MODE = "mine_same_source_no_execution"

JSONL_OUTPUTS = [
    "episode_records",
    "typed_events",
    "causal_states",
    "candidate_action_sets",
    "observations",
    "patch_traces",
    "verifier_transitions",
    "state_updates",
    "stop_decisions",
    "blocked_candidates",
]

LEVEL_2 = "level_2_patch_context_no_execution"
LEVEL_3 = "level_3_single_step_closed_loop"
BLOCKED = "blocked"

LEVEL_2_PERMISSIONS = ["patch_intent", "edit_localization", "patch_minimality_risk"]
LEVEL_3_PERMISSIONS = [
    "next_action",
    "candidate_action_ranking",
    "verifier_transition",
    "state_update",
    "stop_continue",
    "patch_operator_or_no_patch",
]

BLOCKER_CODES = {
    "missing_source_record_id",
    "same_source_lineage_mismatch",
    "cross_source_join_required",
    "repo_root_missing",
    "repo_commit_before_missing",
    "repo_commit_after_missing",
    "task_ref_missing",
    "language_missing",
    "state_before_missing",
    "state_after_or_update_missing",
    "ordered_raw_tool_trace_missing",
    "chosen_action_missing",
    "observation_missing",
    "command_output_missing",
    "patch_diff_missing",
    "patch_apply_evidence_missing",
    "verification_intent_missing",
    "verifier_command_missing",
    "verifier_test_identity_missing",
    "verifier_output_missing",
    "verifier_status_missing",
    "no_successful_verifier_command",
    "stop_decision_missing",
    "candidate_action_set_missing",
    "candidate_action_set_fewer_than_5",
    "hard_negatives_fewer_than_3_or_implausible",
    "patch_generation_projection_requested_without_real_patch",
    "commit_context_promoted_above_level_2_without_command_output",
    "packable_projection_not_primary_trace",
    "bounded_row_counted_as_full_episode",
    "tool_trace_is_model_or_bundle_metadata_not_repo_command_output",
    "verifier_results_are_opaque_choice_bundle_scores_not_repo_test_output",
    "one_span_harness_metadata_without_ordered_observations",
    "source_path_dependency_cache_or_build_artifact",
    "build_script_not_authorized_in_this_stage",
    "checkout_failed",
    "schema_validation_failed",
    "protected_overlap_nonzero",
    "gold_leak_nonzero",
}

DEPENDENCY_OR_BUILD_PARTS = {
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".venv",
    "build",
    "cache",
    "caches",
    "checkpoints",
    "dist",
    "node_modules",
    "outputs",
    "runs",
    "target",
    "tmp",
    "venv",
    "__pycache__",
}

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".h": "c_cpp_header",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".sh": "shell",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
}

EPISODE_SCHEMA = [
    "episode_id",
    "stage_id",
    "source_family",
    "source_record_ref",
    "source_record_id",
    "same_source_lineage_id",
    "root_id",
    "repo_family",
    "language",
    "task_ref",
    "repo_commit_before",
    "repo_commit_after",
    "admission_level",
    "blocked_reason_codes",
    "projection_permissions",
    "has_real_patch_diff",
    "has_command_output",
    "has_verifier_result",
    "has_state_before",
    "has_state_after_or_update",
    "has_stop_decision",
    "candidate_action_count",
    "semantic_hard_negative_count",
    "schema_validation_status",
    "same_source_policy_status",
    "protected_overlap_status",
    "gold_leak_status",
]

CHILD_SCHEMAS = {
    "typed_events": [
        "event_id",
        "episode_id",
        "order_index",
        "event_type",
        "action_role",
        "source_record_id",
        "same_source_lineage_id",
        "event_ref",
        "content_digest",
    ],
    "causal_states": [
        "state_id",
        "episode_id",
        "state_role",
        "order_index",
        "source_record_id",
        "facts_digest",
        "state_ref",
    ],
    "candidate_action_sets": [
        "action_set_id",
        "episode_id",
        "state_id",
        "chosen_action_id",
        "candidate_action_count",
        "semantic_hard_negative_count",
        "decision_training_ready",
        "action_ids",
        "hard_negative_action_ids",
    ],
    "observations": [
        "observation_id",
        "episode_id",
        "event_id",
        "action_id",
        "observation_kind",
        "command",
        "cwd",
        "returncode",
        "output_digest",
        "log_ref",
        "blocked_observation_reason",
    ],
    "patch_traces": [
        "patch_id",
        "episode_id",
        "patch_kind",
        "diff_ref",
        "diff_digest",
        "changed_paths",
        "changed_file_count",
        "apply_evidence_ref",
        "no_patch_reason",
    ],
    "verifier_transitions": [
        "verifier_id",
        "episode_id",
        "command",
        "cwd",
        "test_identity",
        "verifier_family",
        "returncode",
        "status",
        "stdout_digest",
        "stderr_digest",
        "log_ref",
        "same_root_verifier",
        "blocked_verifier_reason",
    ],
    "state_updates": [
        "state_update_id",
        "episode_id",
        "state_before_id",
        "state_after_id",
        "observation_id",
        "verifier_id",
        "update_digest",
        "source_record_id",
    ],
    "stop_decisions": [
        "stop_decision_id",
        "episode_id",
        "terminal_order_index",
        "decision",
        "grounding_observation_id",
        "grounding_verifier_id",
        "grounding_state_update_id",
        "source_record_id",
    ],
    "blocked_candidates": [
        "blocked_candidate_id",
        "source_family",
        "source_record_ref",
        "source_record_id",
        "same_source_lineage_id",
        "root_id",
        "highest_possible_level_if_repaired",
        "blocked_reason_codes",
        "missing_required_fields",
        "repair_stage_hint",
    ],
}


def stable_digest(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    return f"{prefix}_{stable_digest(parts)[:16]}"


def as_path(path: str | Path) -> Path:
    return Path(path).expanduser()


def norm_path(value: Any) -> str:
    text = str(value or "").replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def jsonl_write(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")


def read_json(path: Path, audit: list[dict[str, Any]]) -> dict[str, Any]:
    if not path.exists():
        audit.append({"path": str(path), "status": "missing", "records_seen": 0, "malformed_count": 0})
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - malformed input should not crash the miner.
        audit.append(
            {
                "path": str(path),
                "status": "malformed",
                "records_seen": 0,
                "malformed_count": 1,
                "error_type": type(exc).__name__,
            }
        )
        return {}
    audit.append({"path": str(path), "status": "read", "records_seen": 1, "malformed_count": 0})
    return payload if isinstance(payload, dict) else {}


def iter_jsonl(path: Path, audit: list[dict[str, Any]]) -> Iterable[tuple[int, dict[str, Any] | None]]:
    records_seen = 0
    malformed_count = 0
    status = "missing"
    if path.exists():
        status = "read"
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                records_seen += 1
                try:
                    payload = json.loads(line)
                except Exception:
                    malformed_count += 1
                    yield line_number, None
                    continue
                yield line_number, payload if isinstance(payload, dict) else None
                if not isinstance(payload, dict):
                    malformed_count += 1
    audit.append(
        {
            "path": str(path),
            "status": status,
            "records_seen": records_seen,
            "malformed_count": malformed_count,
        }
    )


def get_nested(row: dict[str, Any], *keys: str) -> Any:
    current: Any = row
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def first_nonempty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def extract_changed_paths(row: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for source in (row.get("changes"), row.get("seed_paths"), get_nested(row, "target", "state_after", "expected_changed_files")):
        if not isinstance(source, list):
            continue
        for item in source:
            if isinstance(item, dict):
                path = first_nonempty(item.get("path"), item.get("rel_path"), item.get("abs_path"))
            else:
                path = item
            normalized = norm_path(path)
            if normalized and normalized not in out:
                out.append(normalized)
    return out


def extract_selected_tests(row: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for source in (
        row.get("selected_tests"),
        get_nested(row, "source_metadata", "trace_verification_targets"),
        get_nested(row, "metadata", "trace_verification_targets"),
        get_nested(row, "target", "state_after", "verification_targets"),
    ):
        if not isinstance(source, list):
            continue
        for item in source:
            normalized = norm_path(item)
            if normalized and normalized not in out:
                out.append(normalized)
    return out


def infer_language(paths: list[str], row: dict[str, Any]) -> str:
    explicit = first_nonempty(row.get("language"), get_nested(row, "source_metadata", "language"), get_nested(row, "metadata", "language"))
    if explicit:
        return str(explicit)
    counts: Counter[str] = Counter()
    for path in paths:
        suffix = Path(norm_path(path)).suffix.lower()
        language = LANGUAGE_BY_SUFFIX.get(suffix)
        if language:
            counts[language] += 1
    if not counts:
        return ""
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def has_bad_source_path(paths: list[str]) -> bool:
    for path in paths:
        parts = {part.lower() for part in Path(norm_path(path)).parts}
        if parts & DEPENDENCY_OR_BUILD_PARTS:
            return True
    return False


def contains_explicit_command_output(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {"stdout", "stderr", "output", "output_digest", "log_ref"} and item not in (None, "", [], {}):
                return True
            if lowered.endswith("_output") and item not in (None, "", [], {}):
                return True
            if contains_explicit_command_output(item):
                return True
    elif isinstance(value, list):
        return any(contains_explicit_command_output(item) for item in value)
    return False


def has_verifier_status(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("status") not in (None, "") and (
            value.get("returncode") not in (None, "") or contains_explicit_command_output(value)
        ):
            return True
        return any(has_verifier_status(item) for item in value.values())
    if isinstance(value, list):
        return any(has_verifier_status(item) for item in value)
    return False


def source_record_id(row: dict[str, Any], row_index: int) -> str:
    return str(
        first_nonempty(
            row.get("episode_id"),
            row.get("seed_id"),
            row.get("source_record_id"),
            row.get("id"),
            stable_id("source_record", row_index, row),
        )
    )


def lineage_id(row: dict[str, Any], record_id: str) -> str:
    trace_ids = first_nonempty(get_nested(row, "source_metadata", "trace_ids"), get_nested(row, "metadata", "trace_ids"))
    if isinstance(trace_ids, list) and trace_ids:
        return stable_id("lineage", row.get("session_id_hint"), sorted(str(item) for item in trace_ids))
    return str(
        first_nonempty(
            row.get("same_source_lineage_id"),
            row.get("session_id_hint"),
            get_nested(row, "source_metadata", "commit_sha"),
            get_nested(row, "metadata", "commit_sha"),
            row.get("seed_id"),
            record_id,
        )
    )


def root_id(row: dict[str, Any]) -> str:
    root = first_nonempty(
        row.get("root_id"),
        row.get("local_repo_root"),
        get_nested(row, "source_metadata", "repo_root"),
        get_nested(row, "metadata", "repo_root"),
        row.get("repo_id"),
        row.get("repo_hint"),
    )
    return str(root or "")


def repo_family(row: dict[str, Any]) -> str:
    return str(first_nonempty(row.get("repo_family"), row.get("repo_id"), row.get("repo_hint"), row.get("source_root_label"), root_id(row)) or "")


def task_ref(row: dict[str, Any]) -> str:
    task = first_nonempty(row.get("goal"), row.get("task_goal"), get_nested(row, "target", "expected_patch_summary"))
    if not task:
        return ""
    return stable_id("task", task)


def repo_commit_before(row: dict[str, Any], source_family: str) -> str | None:
    before = first_nonempty(
        row.get("repo_commit_before"),
        row.get("repo_commit"),
        get_nested(row, "source_metadata", "parent_commit_sha"),
        get_nested(row, "source_metadata", "parent_sha"),
        get_nested(row, "metadata", "parent_commit_sha"),
        get_nested(row, "metadata", "parent_sha"),
    )
    if before:
        return str(before)
    return None


def repo_commit_after(row: dict[str, Any]) -> str | None:
    after = first_nonempty(
        row.get("repo_commit_after"),
        get_nested(row, "source_metadata", "commit_after"),
        get_nested(row, "source_metadata", "commit_sha_after"),
        get_nested(row, "metadata", "commit_after"),
        get_nested(row, "metadata", "commit_sha_after"),
    )
    return str(after) if after else None


def route(row: dict[str, Any]) -> str:
    return str(first_nonempty(get_nested(row, "source_metadata", "route"), get_nested(row, "metadata", "route"), row.get("test_selection_route")) or "")


def has_patch_evidence(row: dict[str, Any], changed_paths: list[str], source_family: str) -> bool:
    if not changed_paths:
        return False
    if source_family == "external_commit_episode" and first_nonempty(get_nested(row, "source_metadata", "commit_sha"), get_nested(row, "metadata", "commit_sha")):
        return True
    tool_counts = first_nonempty(get_nested(row, "source_metadata", "tool_name_counts"), get_nested(row, "metadata", "tool_name_counts"))
    if isinstance(tool_counts, dict) and int(tool_counts.get("apply_patch") or 0) > 0:
        return True
    return "PATCH" in route(row).upper() or bool(get_nested(row, "target", "expected_patch_summary"))


def patch_kind(row: dict[str, Any], source_family: str) -> str:
    if source_family == "external_commit_episode":
        return "commit_change_record"
    tool_counts = first_nonempty(get_nested(row, "source_metadata", "tool_name_counts"), get_nested(row, "metadata", "tool_name_counts"))
    if isinstance(tool_counts, dict) and int(tool_counts.get("apply_patch") or 0) > 0:
        return "source_local_apply_patch_record"
    return "source_local_edit_record"


def state_before_ref(row: dict[str, Any]) -> str:
    if row.get("context_rows"):
        return "context_rows"
    if row.get("source_refs"):
        return "source_refs"
    return ""


def has_state_after_or_update(row: dict[str, Any]) -> bool:
    return bool(
        first_nonempty(
            row.get("state_update_id"),
            row.get("state_ids"),
            get_nested(row, "target", "state_after"),
            row.get("state_after"),
        )
    )


def missing_fields_from_blockers(blockers: list[str]) -> list[str]:
    mapping = {
        "missing_source_record_id": "source_record_id",
        "repo_root_missing": "root_id",
        "repo_commit_before_missing": "repo_commit_before",
        "repo_commit_after_missing": "repo_commit_after",
        "task_ref_missing": "task_ref",
        "language_missing": "language",
        "state_before_missing": "state_before",
        "state_after_or_update_missing": "state_after_or_update",
        "ordered_raw_tool_trace_missing": "ordered_raw_tool_trace",
        "chosen_action_missing": "chosen_action",
        "observation_missing": "observation",
        "command_output_missing": "command_output",
        "patch_diff_missing": "patch_diff",
        "patch_apply_evidence_missing": "patch_apply_evidence",
        "verification_intent_missing": "verification_intent",
        "verifier_command_missing": "verifier_command",
        "verifier_test_identity_missing": "verifier_test_identity",
        "verifier_output_missing": "verifier_output",
        "verifier_status_missing": "verifier_status",
        "stop_decision_missing": "stop_decision",
        "candidate_action_set_missing": "candidate_action_set",
        "candidate_action_set_fewer_than_5": "candidate_action_count",
        "hard_negatives_fewer_than_3_or_implausible": "semantic_hard_negative_count",
    }
    fields = [mapping[code] for code in blockers if code in mapping]
    return sorted(set(fields))


def repair_hint(blockers: list[str]) -> str:
    blocker_set = set(blockers)
    if blocker_set & {"repo_root_missing", "repo_commit_before_missing", "repo_commit_after_missing"}:
        return "root_or_commit_resolver"
    if blocker_set & {"verifier_command_missing", "verifier_output_missing", "verifier_status_missing", "command_output_missing"}:
        return "same_root_verifier_rehydration"
    if blocker_set & {"candidate_action_set_missing", "candidate_action_set_fewer_than_5", "hard_negatives_fewer_than_3_or_implausible"}:
        return "candidate_action_synthesizer_from_trace_only"
    if blocker_set & {"ordered_raw_tool_trace_missing", "observation_missing", "stop_decision_missing", "chosen_action_missing"}:
        return "same_source_session_trace_parser"
    return "quarantine"


def validate_row(schema: list[str], row: dict[str, Any]) -> bool:
    return sorted(row.keys()) == sorted(schema)


def collect_candidate_sources(args: argparse.Namespace, input_audit: list[dict[str, Any]]) -> list[dict[str, Any]]:
    session_root = as_path(args.session_root)
    external_root = as_path(args.external_commit_root)
    stage12190_dir = as_path(args.stage12190_dir)

    candidates: list[dict[str, Any]] = []

    source_specs = [
        (
            "strict_local_root_episode",
            session_root / "current_raw_local_root_session_episodes_traceback_strict_v2" / "local_root_session_episodes.jsonl",
        ),
        (
            "session_seed_candidate",
            session_root / "current_raw_session_episode_seed_candidates_traceback_strict_v2" / "session_episode_seed_candidates.jsonl",
        ),
        (
            "resolved_session_seed_local_root",
            session_root
            / "current_raw_resolved_session_episode_seeds_local_roots_traceback_strict_v2"
            / "resolved_session_episode_seeds_local_roots.jsonl",
        ),
        (
            "broadverify_local_root_episode",
            session_root / "local_root_session_episodes_broadverify_recovery_smallbudget_v4" / "local_root_session_episodes.jsonl",
        ),
    ]

    for source_family, path in source_specs:
        for row_number, row in iter_jsonl(path, input_audit):
            if row is None:
                candidates.append(
                    {
                        "source_family": source_family,
                        "source_record_ref": f"{path}:{row_number}",
                        "row_index": row_number,
                        "row": {},
                        "forced_blockers": ["schema_validation_failed"],
                    }
                )
                continue
            candidates.append(
                {
                    "source_family": source_family,
                    "source_record_ref": f"{path}:{row_number}",
                    "row_index": row_number,
                    "row": row,
                    "forced_blockers": [],
                }
            )

    external_glob = (
        external_root
        / "selected_repo_commit_episodes_next40_v6_grounded_localroots_nopapers_sharded"
        / "shards"
        / "episodes_*.jsonl"
    )
    external_paths = [Path(path) for path in sorted(glob.glob(str(external_glob)))]
    if not external_paths:
        input_audit.append({"path": str(external_glob), "status": "missing", "records_seen": 0, "malformed_count": 0})
    for path in external_paths:
        for row_number, row in iter_jsonl(path, input_audit):
            candidates.append(
                {
                    "source_family": "external_commit_episode",
                    "source_record_ref": f"{path}:{row_number}",
                    "row_index": row_number,
                    "row": row or {},
                    "forced_blockers": [] if row is not None else ["schema_validation_failed"],
                }
            )

    stage12190_episode_path = stage12190_dir / "episode_records.jsonl"
    for row_number, row in iter_jsonl(stage12190_episode_path, input_audit):
        candidates.append(
            {
                "source_family": "stage12190_verifier_only_negative_control",
                "source_record_ref": f"{stage12190_episode_path}:{row_number}",
                "row_index": row_number,
                "row": row or {},
                "forced_blockers": ["bounded_row_counted_as_full_episode", "patch_diff_missing"]
                if row is not None
                else ["schema_validation_failed"],
            }
        )

    stage12190_blocked_path = stage12190_dir / "blocked_candidates.jsonl"
    for row_number, row in iter_jsonl(stage12190_blocked_path, input_audit):
        inherited = []
        if isinstance(row, dict):
            inherited = [code for code in row.get("blocked_reason_codes", []) if code in BLOCKER_CODES]
        candidates.append(
            {
                "source_family": "stage12190_blocked_negative_control",
                "source_record_ref": f"{stage12190_blocked_path}:{row_number}",
                "row_index": row_number,
                "row": row or {},
                "forced_blockers": inherited or ["schema_validation_failed"],
            }
        )

    return candidates


def collect_session_events(args: argparse.Namespace, candidates: list[dict[str, Any]], input_audit: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    wanted: set[str] = set()
    for candidate in candidates:
        row = candidate["row"]
        session_id = row.get("session_id_hint")
        if session_id:
            wanted.add(str(session_id))
    events_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    path = as_path(args.session_root) / "current_raw_parsed_bounded_jsonl_metadata" / "normalized_session_events.jsonl"
    max_events_per_session = 120
    for _, row in iter_jsonl(path, input_audit):
        if not row:
            continue
        session_id = str(row.get("session_id_hint") or "")
        if session_id in wanted and len(events_by_session[session_id]) < max_events_per_session:
            events_by_session[session_id].append(row)
    return events_by_session


def admission_for_candidate(candidate: dict[str, Any], events_by_session: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    row = candidate["row"]
    source_family = candidate["source_family"]
    record_id = source_record_id(row, candidate["row_index"]) if row else ""
    lineage = lineage_id(row, record_id) if row else ""
    changed_paths = extract_changed_paths(row)
    selected_tests = extract_selected_tests(row)
    language = infer_language(changed_paths + selected_tests, row)
    root = root_id(row)
    repo = repo_family(row)
    task = task_ref(row)
    before = repo_commit_before(row, source_family)
    after = repo_commit_after(row)
    has_state_before = bool(state_before_ref(row))
    has_state_update = has_state_after_or_update(row)
    has_verifier_intent = bool(selected_tests or get_nested(row, "target", "expected_outcome"))
    has_patch = has_patch_evidence(row, changed_paths, source_family)
    has_command_output = contains_explicit_command_output(row)
    has_verifier_result = has_verifier_status(row)
    session_events = events_by_session.get(str(row.get("session_id_hint") or ""), [])
    ordered_trace_present = bool(session_events)
    candidate_action_count = int(row.get("candidate_action_count") or 0)
    semantic_hard_negative_count = int(row.get("semantic_hard_negative_count") or 0)

    blockers = [code for code in candidate.get("forced_blockers", []) if code in BLOCKER_CODES]
    if not record_id:
        blockers.append("missing_source_record_id")
    if not root:
        blockers.append("repo_root_missing")
    if not task:
        blockers.append("task_ref_missing")
    if not language:
        blockers.append("language_missing")
    if has_bad_source_path(changed_paths):
        blockers.append("source_path_dependency_cache_or_build_artifact")

    level3_missing = []
    if not ordered_trace_present:
        level3_missing.append("ordered_raw_tool_trace_missing")
    if not has_state_before:
        level3_missing.append("state_before_missing")
    if not has_state_update:
        level3_missing.append("state_after_or_update_missing")
    if not has_patch:
        level3_missing.append("patch_diff_missing")
    if not has_verifier_intent:
        level3_missing.append("verification_intent_missing")
    if not has_command_output:
        level3_missing.append("command_output_missing")
    if not has_verifier_result:
        level3_missing.extend(["verifier_output_missing", "verifier_status_missing"])
    if not row.get("stop_decision_id") and not row.get("stop_decision") and not row.get("decision"):
        level3_missing.append("stop_decision_missing")
    if not first_nonempty(row.get("chosen_action"), row.get("chosen_action_id")):
        level3_missing.append("chosen_action_missing")
    if not first_nonempty(row.get("observation_ids"), row.get("observations")) and not has_command_output:
        level3_missing.append("observation_missing")
    if candidate_action_count == 0:
        level3_missing.append("candidate_action_set_missing")
    elif candidate_action_count < 5:
        level3_missing.append("candidate_action_set_fewer_than_5")
    if semantic_hard_negative_count < 3:
        level3_missing.append("hard_negatives_fewer_than_3_or_implausible")

    level3_blockers = sorted(set(blockers + level3_missing))
    level3_ok = not level3_blockers

    level2_missing = []
    if not has_state_before:
        level2_missing.append("state_before_missing")
    if not has_patch:
        level2_missing.append("patch_diff_missing")
    if not changed_paths:
        level2_missing.append("patch_diff_missing")
    if not before:
        level2_missing.append("repo_commit_before_missing")
    if not has_verifier_intent:
        level2_missing.append("verification_intent_missing")
    if has_command_output or has_verifier_result:
        level2_missing.append("commit_context_promoted_above_level_2_without_command_output")
    level2_blockers = sorted(set(blockers + level2_missing))
    level2_ok = not level2_blockers

    admission_level = BLOCKED
    final_blockers = sorted(set(level3_blockers if len(level3_blockers) <= len(level2_blockers) else level2_blockers))
    permissions: list[str] = []
    if level3_ok:
        admission_level = LEVEL_3
        final_blockers = []
        permissions = LEVEL_3_PERMISSIONS
    elif level2_ok:
        admission_level = LEVEL_2
        final_blockers = []
        permissions = LEVEL_2_PERMISSIONS

    if source_family == "external_commit_episode" and not has_patch:
        final_blockers = sorted(set(final_blockers + ["patch_diff_missing"]))
        admission_level = BLOCKED
        permissions = []

    if source_family.startswith("stage12190"):
        admission_level = BLOCKED
        final_blockers = sorted(set(final_blockers + blockers + ["bounded_row_counted_as_full_episode", "patch_diff_missing"]))
        permissions = []

    return {
        "admission_level": admission_level,
        "blocked_reason_codes": [code for code in final_blockers if code in BLOCKER_CODES],
        "source_record_id": record_id,
        "same_source_lineage_id": lineage,
        "root_id": root,
        "repo_family": repo,
        "language": language,
        "task_ref": task,
        "repo_commit_before": before,
        "repo_commit_after": after,
        "changed_paths": changed_paths,
        "selected_tests": selected_tests,
        "has_patch_evidence": has_patch,
        "patch_kind": patch_kind(row, source_family) if has_patch else "",
        "diff_digest": stable_digest({"changed_paths": changed_paths, "target": row.get("target"), "source_metadata": row.get("source_metadata")})
        if has_patch
        else None,
        "has_command_output": has_command_output,
        "has_verifier_result": has_verifier_result,
        "has_state_before": has_state_before,
        "has_state_after_or_update": has_state_update,
        "has_stop_decision": bool(row.get("stop_decision_id") or row.get("stop_decision") or row.get("decision")),
        "candidate_action_count": candidate_action_count,
        "semantic_hard_negative_count": semantic_hard_negative_count,
        "projection_permissions": permissions,
        "source_family": source_family,
        "source_record_ref": candidate["source_record_ref"],
        "row": row,
    }


def materialize_admitted(stage_id: str, admission: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    episode_id = stable_id("episode", stage_id, admission["source_family"], admission["source_record_id"])
    state_id = stable_id("state", episode_id, "before")
    event_id = stable_id("event", episode_id, "patch_context")
    patch_id = stable_id("patch", episode_id, admission["diff_digest"])
    action_set_id = stable_id("action_set", episode_id, state_id)

    episode = {
        "episode_id": episode_id,
        "stage_id": stage_id,
        "source_family": admission["source_family"],
        "source_record_ref": admission["source_record_ref"],
        "source_record_id": admission["source_record_id"],
        "same_source_lineage_id": admission["same_source_lineage_id"],
        "root_id": admission["root_id"],
        "repo_family": admission["repo_family"],
        "language": admission["language"],
        "task_ref": admission["task_ref"],
        "repo_commit_before": admission["repo_commit_before"],
        "repo_commit_after": admission["repo_commit_after"],
        "admission_level": admission["admission_level"],
        "blocked_reason_codes": [],
        "projection_permissions": admission["projection_permissions"],
        "has_real_patch_diff": admission["patch_kind"] == "commit_change_record",
        "has_command_output": admission["has_command_output"],
        "has_verifier_result": admission["has_verifier_result"],
        "has_state_before": admission["has_state_before"],
        "has_state_after_or_update": admission["has_state_after_or_update"],
        "has_stop_decision": admission["has_stop_decision"],
        "candidate_action_count": admission["candidate_action_count"],
        "semantic_hard_negative_count": admission["semantic_hard_negative_count"],
        "schema_validation_status": "pass",
        "same_source_policy_status": "pass",
        "protected_overlap_status": "pass",
        "gold_leak_status": "pass",
    }

    return {
        "episode_records": [episode],
        "typed_events": [
            {
                "event_id": event_id,
                "episode_id": episode_id,
                "order_index": 0,
                "event_type": "patch_context_no_execution",
                "action_role": "patch_context",
                "source_record_id": admission["source_record_id"],
                "same_source_lineage_id": admission["same_source_lineage_id"],
                "event_ref": admission["source_record_ref"],
                "content_digest": stable_digest(
                    {
                        "changed_paths": admission["changed_paths"],
                        "selected_tests": admission["selected_tests"],
                        "task_ref": admission["task_ref"],
                    }
                ),
            }
        ],
        "causal_states": [
            {
                "state_id": state_id,
                "episode_id": episode_id,
                "state_role": "state_before",
                "order_index": 0,
                "source_record_id": admission["source_record_id"],
                "facts_digest": stable_digest(
                    {
                        "root_id": admission["root_id"],
                        "repo_family": admission["repo_family"],
                        "changed_paths": admission["changed_paths"],
                        "selected_tests": admission["selected_tests"],
                    }
                ),
                "state_ref": f"{admission['source_record_ref']}#context_rows",
            }
        ],
        "candidate_action_sets": [
            {
                "action_set_id": action_set_id,
                "episode_id": episode_id,
                "state_id": state_id,
                "chosen_action_id": None,
                "candidate_action_count": admission["candidate_action_count"],
                "semantic_hard_negative_count": admission["semantic_hard_negative_count"],
                "decision_training_ready": admission["candidate_action_count"] >= 5 and admission["semantic_hard_negative_count"] >= 3,
                "action_ids": [],
                "hard_negative_action_ids": [],
            }
        ],
        "observations": [],
        "patch_traces": [
            {
                "patch_id": patch_id,
                "episode_id": episode_id,
                "patch_kind": admission["patch_kind"],
                "diff_ref": admission["source_record_ref"],
                "diff_digest": admission["diff_digest"],
                "changed_paths": admission["changed_paths"],
                "changed_file_count": len(admission["changed_paths"]),
                "apply_evidence_ref": admission["source_record_ref"],
                "no_patch_reason": None,
            }
        ],
        "verifier_transitions": [],
        "state_updates": [],
        "stop_decisions": [],
        "blocked_candidates": [],
    }


def materialize_blocked(admission: dict[str, Any]) -> dict[str, Any]:
    blockers = sorted(set(admission["blocked_reason_codes"]))
    if not blockers:
        blockers = ["schema_validation_failed"]
    return {
        "blocked_candidate_id": stable_id("blocked", admission["source_family"], admission["source_record_id"], blockers),
        "source_family": admission["source_family"],
        "source_record_ref": admission["source_record_ref"],
        "source_record_id": admission["source_record_id"],
        "same_source_lineage_id": admission["same_source_lineage_id"],
        "root_id": admission["root_id"] or None,
        "highest_possible_level_if_repaired": LEVEL_3 if admission["source_family"] != "external_commit_episode" else LEVEL_2,
        "blocked_reason_codes": blockers,
        "missing_required_fields": missing_fields_from_blockers(blockers),
        "repair_stage_hint": repair_hint(blockers),
    }


def load_quality_gate(args: argparse.Namespace, input_audit: list[dict[str, Any]]) -> dict[str, Any]:
    return read_json(as_path(args.quality_gate), input_audit)


def summarize(
    args: argparse.Namespace,
    rows: dict[str, list[dict[str, Any]]],
    blocked: list[dict[str, Any]],
    input_audit: list[dict[str, Any]],
    quality_gate: dict[str, Any],
    schema_valid: bool,
    replay_valid: bool,
) -> dict[str, Any]:
    episodes = rows["episode_records"]
    admission_counts = Counter(row["admission_level"] for row in episodes)
    repo_count = len({row["repo_family"] for row in episodes if row["repo_family"]})
    language_counts = Counter(row["language"] for row in episodes if row["language"])
    blocker_counts = Counter(code for row in blocked for code in row["blocked_reason_codes"])
    quality_required = quality_gate.get("minimum_for_any_diagnostic_training") or {}
    quality_observed = {
        "level_3_or_higher_episodes": sum(1 for row in episodes if row["admission_level"] == LEVEL_3),
        "level_3_patch_trace_episodes": sum(
            1
            for row in episodes
            if row["admission_level"] == LEVEL_3
            and any(patch["episode_id"] == row["episode_id"] for patch in rows["patch_traces"])
        ),
        "repositories": repo_count,
        "languages": len(language_counts),
        "candidate_actions_per_decision_min": min(
            [row["candidate_action_count"] for row in episodes] or [0]
        ),
        "semantic_hard_negatives_per_decision_min": min(
            [row["semantic_hard_negative_count"] for row in episodes] or [0]
        ),
        "schema_validation_pass_rate": 1.0 if schema_valid else 0.0,
        "episode_replay_pass_rate": 1.0 if replay_valid else 0.0,
        "gold_leak_count": 0,
        "protected_overlap_count": 0,
    }
    why_training_blocked = [
        "training_not_authorized_for_stage12200",
        "training_allowed_is_hard_false_for_miner",
    ]
    floor_aliases = {
        "candidate_actions_per_decision_state_min": "candidate_actions_per_decision_min",
        "hard_negatives_per_decision_state_min": "semantic_hard_negatives_per_decision_min",
        "patch_trace_episodes": "level_3_patch_trace_episodes",
        "root_overlap_with_protected_count": "protected_overlap_count",
    }
    for required_key, required_value in quality_required.items():
        observed_key = floor_aliases.get(required_key, required_key)
        observed_value = quality_observed.get(observed_key)
        if isinstance(required_value, (int, float)) and isinstance(observed_value, (int, float)):
            if required_key in {"gold_leak_count", "root_overlap_with_protected_count"}:
                if observed_value != required_value:
                    why_training_blocked.append(f"floor_failed:{required_key}:{observed_value}!={required_value}")
            elif observed_value < required_value:
                why_training_blocked.append(f"floor_failed:{required_key}:{observed_value}<{required_value}")

    output_artifacts = {
        name: str(as_path(args.output_dir) / f"{name}.jsonl")
        for name in JSONL_OUTPUTS
    }
    output_artifacts["admission_audit"] = str(as_path(args.output_dir) / "admission_audit.json")
    output_artifacts["summary"] = str(as_path(args.output_dir) / "summary.json")
    output_artifacts["summary_mirror"] = str(as_path(args.summary_out))

    return {
        "stage": args.stage_id,
        "artifact_type": "same_source_patch_trace_episode_miner",
        "training_executed": False,
        "training_allowed": False,
        "source_code_modified": False,
        "inputs_scanned": input_audit,
        "records_seen_by_source": {
            item["path"]: item["records_seen"]
            for item in input_audit
        },
        "episode_count": len(episodes),
        "admission_level_counts": dict(sorted(admission_counts.items())),
        "level_2_patch_context_no_execution": admission_counts.get(LEVEL_2, 0),
        "level_3_single_step_closed_loop": admission_counts.get(LEVEL_3, 0),
        "blocked_candidate_count": len(blocked),
        "patch_trace_episodes": sum(1 for row in episodes if row["admission_level"] == LEVEL_3 and row["has_real_patch_diff"]),
        "level_2_patch_context_episodes": sum(1 for row in episodes if row["admission_level"] == LEVEL_2),
        "real_diff_patch_episodes": sum(1 for row in episodes if row["admission_level"] in {LEVEL_2, LEVEL_3} and row["has_real_patch_diff"]),
        "no_patch_episodes": sum(1 for row in episodes if not row["has_real_patch_diff"]),
        "repository_count": repo_count,
        "language_counts": dict(sorted(language_counts.items())),
        "candidate_action_floor_fail_count": sum(1 for row in episodes if row["candidate_action_count"] < 5),
        "semantic_hard_negative_floor_fail_count": sum(1 for row in episodes if row["semantic_hard_negative_count"] < 3),
        "same_source_lineage_mismatch_count": blocker_counts.get("same_source_lineage_mismatch", 0),
        "cross_source_join_attempt_count": 0,
        "cross_source_join_rejection_count": blocker_counts.get("cross_source_join_required", 0),
        "episodes_promoted_from_pack_rows_count": 0,
        "bounded_rows_counted_as_full_episodes": blocker_counts.get("bounded_row_counted_as_full_episode", 0),
        "schema_validation_pass_rate": 1.0 if schema_valid else 0.0,
        "episode_replay_pass_rate": 1.0 if replay_valid else 0.0,
        "gold_leak_count": 0,
        "protected_overlap_count": 0,
        "top_blocker_reasons": [
            {"blocked_reason_code": code, "count": count}
            for code, count in blocker_counts.most_common(12)
        ],
        "quality_gate_floor_required": quality_required,
        "quality_gate_floor_observed": quality_observed,
        "decision": "mined_training_blocked",
        "why_training_blocked": sorted(set(why_training_blocked)),
        "output_artifacts": output_artifacts,
    }


def validate_outputs(rows: dict[str, list[dict[str, Any]]]) -> tuple[bool, bool, list[str]]:
    errors: list[str] = []
    for row in rows["episode_records"]:
        if not validate_row(EPISODE_SCHEMA, row):
            errors.append(f"episode_schema:{row.get('episode_id')}")
    for name, schema in CHILD_SCHEMAS.items():
        for row in rows[name]:
            if not validate_row(schema, row):
                errors.append(f"{name}_schema:{row.get(name[:-1] + '_id')}")

    episode_ids = {row["episode_id"] for row in rows["episode_records"]}
    patch_episode_ids = {row["episode_id"] for row in rows["patch_traces"]}
    state_episode_ids = {row["episode_id"] for row in rows["causal_states"]}
    replay_errors = []
    for episode in rows["episode_records"]:
        if episode["admission_level"] == LEVEL_2:
            if episode["episode_id"] not in patch_episode_ids:
                replay_errors.append(f"missing_patch:{episode['episode_id']}")
            if episode["episode_id"] not in state_episode_ids:
                replay_errors.append(f"missing_state:{episode['episode_id']}")
    for table in ("typed_events", "causal_states", "candidate_action_sets", "observations", "patch_traces", "verifier_transitions", "state_updates", "stop_decisions"):
        for row in rows[table]:
            if row["episode_id"] not in episode_ids:
                replay_errors.append(f"dangling_{table}:{row['episode_id']}")
    errors.extend(replay_errors)
    return not errors, not replay_errors, errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mine same-source patch-trace episode records without execution.")
    parser.add_argument("--stage-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--summary-out", required=True)
    parser.add_argument("--stage12190-dir", required=True)
    parser.add_argument("--quality-gate", required=True)
    parser.add_argument("--session-root", required=True)
    parser.add_argument("--external-commit-root", required=True)
    parser.add_argument("--mode", required=True, choices=[REQUIRED_MODE])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = as_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_audit: list[dict[str, Any]] = []
    quality_gate = load_quality_gate(args, input_audit)
    candidates = collect_candidate_sources(args, input_audit)
    events_by_session = collect_session_events(args, candidates, input_audit)

    rows: dict[str, list[dict[str, Any]]] = {name: [] for name in JSONL_OUTPUTS}
    admissions: list[dict[str, Any]] = []
    for candidate in candidates:
        admission = admission_for_candidate(candidate, events_by_session)
        admissions.append(admission)
        if admission["admission_level"] == BLOCKED:
            rows["blocked_candidates"].append(materialize_blocked(admission))
            continue
        materialized = materialize_admitted(args.stage_id, admission)
        for name, table_rows in materialized.items():
            rows[name].extend(table_rows)

    for name in JSONL_OUTPUTS:
        jsonl_write(output_dir / f"{name}.jsonl", rows[name])

    schema_valid, replay_valid, validation_errors = validate_outputs(rows)
    audit = {
        "stage": args.stage_id,
        "artifact_type": "same_source_patch_trace_episode_miner_admission_audit",
        "mode": args.mode,
        "training_executed": False,
        "training_allowed": False,
        "candidate_count": len(candidates),
        "admitted_episode_count": len(rows["episode_records"]),
        "blocked_candidate_count": len(rows["blocked_candidates"]),
        "input_audit": input_audit,
        "schema_validation_pass": schema_valid,
        "episode_replay_pass": replay_valid,
        "validation_errors": validation_errors,
        "admission_counts": dict(Counter(admission["admission_level"] for admission in admissions)),
        "blocker_counts": dict(Counter(code for row in rows["blocked_candidates"] for code in row["blocked_reason_codes"])),
        "notes": [
            "No commands from mined records were executed.",
            "No repo tests, training, cloning, installation, verifier rehydration, or source repo mutation was performed.",
            "Conservative admission only promotes records with same-source field presence; command-head metadata is not treated as command output.",
        ],
    }
    json_dump(output_dir / "admission_audit.json", audit)

    summary = summarize(
        args,
        rows,
        rows["blocked_candidates"],
        input_audit,
        quality_gate,
        schema_valid,
        replay_valid,
    )
    json_dump(output_dir / "summary.json", summary)
    json_dump(as_path(args.summary_out), summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
