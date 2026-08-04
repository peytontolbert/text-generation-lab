#!/usr/bin/env python3
"""Mine and classify bounded same-session trajectory roots without admission."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12585_same_source_observed_trajectory_root_miner"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

RECOVERY_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12388_transition_local_candidate_recovery"
    / "transition_local_candidate_recovery_records.jsonl"
)
JOIN_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12314_session_candidate_repo_and_state_joiner"
    / "session_candidate_repo_state_join_records.jsonl"
)
TASK_WINDOWS = (
    ROOT
    / "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner"
    / "codex_task_windows.jsonl"
)
STAGE12583_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12583_causal_episode_microfactory"
    / "causal_candidates.jsonl"
)
STAGE12584_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12584_biome_causal_replay"
    / "raw_private_candidate.jsonl"
)
PROTECTED_DENYLIST = ROOT / "configs/software_maintainer/future_eval_identity_denylist_v1.json"

CLASSIFICATIONS = {
    "observed_level3",
    "observed_level4",
    "patch_effect_replay_only",
    "level2_patch_context",
    "blocked",
}
REPLAY_ONLY_STAGES = {
    "stage12583_causal_episode_microfactory",
    "stage12584_biome_causal_replay",
}
FORBIDDEN_OUTPUT_KEYS = {
    "model_input",
    "model_inputs",
    "trainer_manifest",
    "trainer_manifests",
    "projection",
    "projections",
    "admission",
    "admissions",
    "admitted_episodes",
    "admitted_training_projections",
    "candidate_actions",
}
FLOORS = {"level3_plus": 20, "patch_trace_episodes": 8, "repositories": 10}


class GateError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    return f"{prefix}_{stable_hash(parts)[:20]}"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise GateError(f"required_input_missing:{path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GateError(f"malformed_jsonl:{path}:{line_number}") from exc
            if not isinstance(row, dict):
                raise GateError(f"non_object_jsonl_row:{path}:{line_number}")
            rows.append(row)
    return rows


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GateError(f"required_input_missing:{path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError(f"non_object_json:{path}")
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


def assert_no_forbidden_output_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in FORBIDDEN_OUTPUT_KEYS:
                raise GateError(f"forbidden_output_key:{key}")
            assert_no_forbidden_output_keys(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_forbidden_output_keys(child)


def index_unique(rows: list[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = str(row.get(key) or "")
        if not value:
            continue
        if value in result:
            raise GateError(f"duplicate_{label}_identity:{value}")
        result[value] = row
    return result


def load_protected_identities(payload: dict[str, Any]) -> dict[str, set[str]]:
    deny = payload.get("deny")
    if not isinstance(deny, dict):
        raise GateError("protected_denylist_schema_invalid")
    return {
        "repo_family": {str(item).casefold() for item in deny.get("repo_family", [])},
        "source_path": {str(item) for item in deny.get("source_path", [])},
        "root_identity": {str(item) for item in deny.get("root_identity", [])},
    }


def protected_overlap(
    *, repo_family: str, source_path: str, root_identity: str, protected: dict[str, set[str]]
) -> dict[str, Any]:
    matches: list[str] = []
    if repo_family and repo_family.casefold() in protected["repo_family"]:
        matches.append("repo_family")
    if source_path and source_path in protected["source_path"]:
        matches.append("source_path")
    if root_identity and root_identity in protected["root_identity"]:
        matches.append("root_identity")
    return {"overlap": bool(matches), "matched_identity_kinds": sorted(matches)}


def evidence_blockers(candidate: dict[str, Any]) -> list[str]:
    evidence = candidate["evidence"]
    blockers: list[str] = []
    required = {
        "observed_task": "observed_task_missing",
        "ordered_action": "ordered_action_missing",
        "command_tool_observation": "command_tool_observation_missing",
        "verifier_result": "verifier_result_missing_or_unproven",
        "state_after": "state_after_missing_or_unproven",
        "stop_continue": "stop_continue_missing_or_unproven",
    }
    for field, blocker in required.items():
        if evidence.get(field) is not True:
            blockers.append(blocker)
    if not (evidence.get("patch_trace") is True or evidence.get("explicit_no_patch_reason") is True):
        blockers.append("patch_trace_or_explicit_no_patch_reason_missing")
    if evidence.get("historical_candidate_set") is not True:
        blockers.append("historical_candidate_set_missing")
    if evidence.get("candidate_set_committed_pre_outcome") is not True:
        blockers.append("candidate_set_not_committed_pre_outcome")
    if evidence.get("candidate_set_derived_from_after_diff") is not False:
        blockers.append("candidate_set_after_diff_leakage_or_unknown")
    if int(evidence.get("candidate_action_count") or 0) < 1:
        blockers.append("candidate_action_set_empty")
    if candidate["source_kind"] != "same_session_observed_trace":
        blockers.append("not_same_session_observed_trace")
    if candidate["protected_overlap"]["overlap"]:
        blockers.append("protected_identity_overlap")
    return sorted(set(blockers))


def classify_candidate(candidate: dict[str, Any]) -> tuple[str, list[str]]:
    stage = str(candidate.get("provenance_stage") or "")
    if stage in REPLAY_ONLY_STAGES or candidate.get("source_kind") == "patch_effect_replay":
        return "patch_effect_replay_only", ["replay_effect_not_historically_observed_policy_trajectory"]

    blockers = evidence_blockers(candidate)
    if blockers:
        evidence = candidate["evidence"]
        level2_ready = all(
            (
                evidence.get("observed_task") is True,
                evidence.get("patch_context") is True,
                evidence.get("verifier_intent") is True,
                evidence.get("command_tool_observation") is not True,
                evidence.get("historical_candidate_set") is True,
                evidence.get("candidate_set_committed_pre_outcome") is True,
                evidence.get("candidate_set_derived_from_after_diff") is False,
                int(evidence.get("candidate_action_count") or 0) >= 1,
                not candidate["protected_overlap"]["overlap"],
            )
        )
        if level2_ready:
            return "level2_patch_context", blockers
        return "blocked", blockers

    decision_states = int(candidate["evidence"].get("decision_state_count") or 0)
    return ("observed_level4" if decision_states >= 2 else "observed_level3"), []


def _missing_identity(label: str, recovery_id: str) -> str:
    return f"missing_{label}_{stable_hash(recovery_id)[:16]}"


def normalize_same_session_candidate(
    recovery: dict[str, Any],
    join: dict[str, Any] | None,
    window: dict[str, Any] | None,
    protected: dict[str, set[str]],
) -> dict[str, Any]:
    recovery_id = str(recovery.get("recovery_record_id") or stable_id("recovery", recovery))
    expected_join_id = str(recovery.get("source_join_record_id") or "")
    task_window_id = str(recovery.get("task_window_id") or "")
    identity = recovery.get("identity_recovery") if isinstance(recovery.get("identity_recovery"), dict) else {}
    transition = recovery.get("transition_recovery") if isinstance(recovery.get("transition_recovery"), dict) else {}
    command_result = (
        transition.get("command_result_candidate")
        if isinstance(transition.get("command_result_candidate"), dict)
        else {}
    )
    verifier_transition = (
        transition.get("verifier_transition_candidate")
        if isinstance(transition.get("verifier_transition_candidate"), dict)
        else {}
    )
    state_update = (
        transition.get("state_update_candidate")
        if isinstance(transition.get("state_update_candidate"), dict)
        else {}
    )
    stop = (
        transition.get("stop_decision_candidate")
        if isinstance(transition.get("stop_decision_candidate"), dict)
        else {}
    )
    join_refs = join.get("source_refs", {}) if isinstance(join, dict) else {}
    join_shape = join.get("window_evidence_shape", {}) if isinstance(join, dict) else {}

    exact_join = bool(
        join
        and str(join.get("join_record_id") or "") == expected_join_id
        and str(join.get("task_window_id") or "") == task_window_id
        and window
        and str(window.get("task_window_id") or "") == task_window_id
        and str(window.get("source_file_hash_compat") or "")
        == str(join_refs.get("source_file_hash_compat") or "")
    )
    source_id = str(join_refs.get("source_file_hash_compat") or _missing_identity("source", recovery_id))
    session_id = str(join_refs.get("session_id_hash") or _missing_identity("session", recovery_id))
    root_id = str(identity.get("root_id_candidate") or (join or {}).get("canonical_root_id") or _missing_identity("root", recovery_id))
    window_id = task_window_id or _missing_identity("window", recovery_id)
    repo_family = str(identity.get("repo_family_candidate") or "unknown")

    verifier_status = str(verifier_transition.get("verifier_status_class") or "")
    verifier_events = int(command_result.get("verifier_event_count") or 0)
    patch_events = int(command_result.get("patch_event_count") or 0)
    stop_label = str(stop.get("stop_continue_label") or "")
    observed_task = bool(window and window.get("has_user_signal") is True and exact_join)
    ordered_action = bool(
        exact_join
        and int((window or {}).get("paired_tool_call_count") or 0) > 0
        and int((window or {}).get("start_line") or 0) <= int((window or {}).get("end_line") or -1)
    )
    command_observation = bool(
        exact_join
        and join_shape.get("has_command_observation") is True
        and int(join_shape.get("paired_tool_call_count") or 0) > 0
    )
    verifier_result = bool(
        exact_join
        and verifier_events > 0
        and verifier_status
        not in {"", "NO_VERIFIER_OBSERVED", "VERIFIER_STATUS_UNKNOWN"}
    )
    stop_continue = bool(exact_join and stop_label in {"STOP_SIGNAL_OBSERVED", "CONTINUE_SIGNAL_OBSERVED"})

    # Stage12388 has state and patch *candidates*, not reviewed state_after or patch content/digests.
    evidence = {
        "observed_task": observed_task,
        "ordered_action": ordered_action,
        "command_tool_observation": command_observation,
        "verifier_result": verifier_result,
        "state_after": bool(state_update.get("state_after_proven") is True),
        "stop_continue": stop_continue,
        "patch_trace": bool(command_result.get("patch_content_or_digest_proven") is True),
        "explicit_no_patch_reason": bool(transition.get("explicit_no_patch_reason_proven") is True),
        "patch_context": patch_events > 0,
        "verifier_intent": bool(join_shape.get("has_verifier_like_ref") is True),
        "historical_candidate_set": False,
        "candidate_set_committed_pre_outcome": False,
        "candidate_set_derived_from_after_diff": False,
        "candidate_action_count": 0,
        "decision_state_count": 0,
    }
    overlap = protected_overlap(
        repo_family=repo_family,
        source_path="",
        root_identity=root_id,
        protected=protected,
    )
    dedupe_components = {
        "source": source_id,
        "session": session_id,
        "root": root_id,
        "window": window_id,
    }
    candidate = {
        "candidate_id": stable_id("stage12585_candidate", recovery_id, dedupe_components),
        "record_type": "stage12585_observed_trajectory_root_candidate_v1",
        "source_kind": "same_session_observed_trace",
        "provenance_stage": "stage12388_transition_local_candidate_recovery",
        "upstream_record_id": recovery_id,
        "exact_same_source_join": exact_join,
        "source_session_root_window": dedupe_components,
        "dedupe_key_sha256": stable_hash(dedupe_components),
        "repo_family": repo_family,
        "language_family": str(identity.get("language_candidate") or "unknown"),
        "evidence": evidence,
        "observed_effect_summary": {
            "patch_event_count": patch_events,
            "verifier_event_count": verifier_events,
            "verifier_status_class": verifier_status or "MISSING",
            "stop_continue_label": stop_label or "MISSING",
        },
        "protected_overlap": overlap,
        "raw_content_emitted": False,
        "training_allowed": False,
    }
    classification, blockers = classify_candidate(candidate)
    if not exact_join:
        blockers = sorted(set(blockers + ["exact_source_session_window_join_missing_or_mismatched"]))
        classification = "blocked"
    candidate["classification_preview"] = classification
    candidate["blockers"] = blockers
    return candidate


def normalize_replay_candidate(
    row: dict[str, Any], provenance_stage: str, protected: dict[str, set[str]]
) -> dict[str, Any]:
    if provenance_stage not in REPLAY_ONLY_STAGES:
        raise GateError(f"unexpected_replay_stage:{provenance_stage}")
    if provenance_stage == "stage12583_causal_episode_microfactory":
        source = row.get("source") if isinstance(row.get("source"), dict) else {}
        source_path = str(source.get("repository") or "")
        root_identity = str(row.get("episode_id") or provenance_stage)
        repo_family = Path(source_path).name or "unknown"
        upstream_id = root_identity
    else:
        source_path = ""
        root_identity = str(row.get("source_identity_sha256") or provenance_stage)
        repo_family = "biome"
        upstream_id = str(row.get("candidate_identity_sha256") or root_identity)
    overlap = protected_overlap(
        repo_family=repo_family,
        source_path=source_path,
        root_identity=root_identity,
        protected=protected,
    )
    components = {
        "source": provenance_stage,
        "session": upstream_id,
        "root": root_identity,
        "window": "replay_effect_window",
    }
    candidate = {
        "candidate_id": stable_id("stage12585_candidate", provenance_stage, upstream_id),
        "record_type": "stage12585_patch_effect_replay_candidate_v1",
        "source_kind": "patch_effect_replay",
        "provenance_stage": provenance_stage,
        "upstream_record_id": upstream_id,
        "exact_same_source_join": False,
        "source_session_root_window": components,
        "dedupe_key_sha256": stable_hash(components),
        "repo_family": repo_family,
        "language_family": "unknown",
        "evidence": {
            "observed_task": False,
            "ordered_action": False,
            "command_tool_observation": True,
            "verifier_result": True,
            "state_after": True,
            "stop_continue": True,
            "patch_trace": True,
            "explicit_no_patch_reason": False,
            "patch_context": True,
            "verifier_intent": True,
            "historical_candidate_set": False,
            "candidate_set_committed_pre_outcome": False,
            "candidate_set_derived_from_after_diff": provenance_stage == "stage12583_causal_episode_microfactory",
            "candidate_action_count": 0,
            "decision_state_count": 0,
        },
        "observed_effect_summary": {"effect_replayed": True, "historical_trajectory_observed": False},
        "protected_overlap": overlap,
        "raw_content_emitted": False,
        "training_allowed": False,
    }
    classification, blockers = classify_candidate(candidate)
    candidate["classification_preview"] = classification
    candidate["blockers"] = blockers
    return candidate


def build_ledgers(
    *,
    recovery_rows: list[dict[str, Any]],
    join_rows: list[dict[str, Any]],
    window_rows: list[dict[str, Any]],
    replay12583_rows: list[dict[str, Any]],
    replay12584_rows: list[dict[str, Any]],
    protected_payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    protected = load_protected_identities(protected_payload)
    joins = index_unique(join_rows, "join_record_id", "join")
    windows = index_unique(window_rows, "task_window_id", "window")
    candidates: list[dict[str, Any]] = []
    for recovery in recovery_rows:
        join_id = str(recovery.get("source_join_record_id") or "")
        window_id = str(recovery.get("task_window_id") or "")
        candidates.append(
            normalize_same_session_candidate(
                recovery, joins.get(join_id), windows.get(window_id), protected
            )
        )
    candidates.extend(
        normalize_replay_candidate(row, "stage12583_causal_episode_microfactory", protected)
        for row in replay12583_rows
    )
    candidates.extend(
        normalize_replay_candidate(row, "stage12584_biome_causal_replay", protected)
        for row in replay12584_rows
    )
    candidates.sort(key=lambda row: (row["dedupe_key_sha256"], row["candidate_id"]))

    first_by_key: dict[str, str] = {}
    classifications: list[dict[str, Any]] = []
    for candidate in candidates:
        dedupe_key = candidate["dedupe_key_sha256"]
        duplicate_of = first_by_key.get(dedupe_key)
        if duplicate_of is None:
            first_by_key[dedupe_key] = candidate["candidate_id"]
        classification = candidate["classification_preview"]
        blockers = list(candidate["blockers"])
        if duplicate_of is not None:
            classification = "blocked"
            blockers = sorted(set(blockers + ["duplicate_source_session_root_window"]))
        if classification not in CLASSIFICATIONS:
            raise GateError(f"invalid_classification:{classification}")
        candidate["duplicate_of"] = duplicate_of
        candidate["canonical_for_dedupe_key"] = duplicate_of is None
        classifications.append(
            {
                "candidate_id": candidate["candidate_id"],
                "record_type": "stage12585_trajectory_classification_v1",
                "classification": classification,
                "blockers": blockers,
                "duplicate_of": duplicate_of,
                "protected_overlap": candidate["protected_overlap"]["overlap"],
                "counts_toward_level3_plus_floor": bool(
                    duplicate_of is None
                    and not candidate["protected_overlap"]["overlap"]
                    and classification in {"observed_level3", "observed_level4"}
                ),
                "counts_toward_patch_trace_floor": bool(
                    duplicate_of is None
                    and not candidate["protected_overlap"]["overlap"]
                    and classification in {"observed_level3", "observed_level4"}
                    and candidate["evidence"]["patch_trace"] is True
                ),
                "counts_toward_repository_floor": bool(
                    duplicate_of is None
                    and not candidate["protected_overlap"]["overlap"]
                    and classification in {"observed_level3", "observed_level4"}
                ),
                "training_allowed": False,
            }
        )
    assert_no_forbidden_output_keys(candidates)
    assert_no_forbidden_output_keys(classifications)
    return candidates, classifications


def _dominance(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    counts = Counter(str(row.get(key) or "unknown") for row in rows)
    total = sum(counts.values())
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    leader, leader_count = ordered[0] if ordered else (None, 0)
    return {
        "denominator": total,
        "distinct_count": len(counts),
        "largest_identity": leader,
        "largest_count": leader_count,
        "largest_share": round(leader_count / total, 6) if total else 0.0,
        "counts": dict(sorted(counts.items())),
    }


def build_summary(
    candidates: list[dict[str, Any]],
    classifications: list[dict[str, Any]],
    input_digests: dict[str, str],
) -> dict[str, Any]:
    by_id = {row["candidate_id"]: row for row in candidates}
    canonical = [row for row in candidates if row["canonical_for_dedupe_key"]]
    class_counts = Counter(row["classification"] for row in classifications)
    level3_rows = [row for row in classifications if row["counts_toward_level3_plus_floor"]]
    patch_rows = [row for row in classifications if row["counts_toward_patch_trace_floor"]]
    repos = sorted({by_id[row["candidate_id"]]["repo_family"] for row in level3_rows})
    observed = {
        "level3_plus": len(level3_rows),
        "patch_trace_episodes": len(patch_rows),
        "repositories": len(repos),
    }
    floor_status = {
        name: {
            "required": required,
            "observed": observed[name],
            "deficit": max(0, required - observed[name]),
            "met": observed[name] >= required,
        }
        for name, required in FLOORS.items()
    }
    same_session_canonical = [
        row for row in canonical if row["source_kind"] == "same_session_observed_trace"
    ]
    root_rows = [
        {"root": row["source_session_root_window"]["root"]} for row in same_session_canonical
    ]
    blocker_counts: Counter[str] = Counter()
    for row in classifications:
        blocker_counts.update(row["blockers"])
    summary = {
        "stage": STAGE,
        "status": "TRAJECTORY_FLOORS_MET" if all(item["met"] for item in floor_status.values()) else "TRAJECTORY_FLOORS_UNMET",
        "decision": "audit_only_no_training",
        "claim_boundary": (
            "Same-session observed trace classification only. Replay effects, uncommitted candidate sets, "
            "unreviewed state candidates, and patch-status-only records count zero toward trajectory floors."
        ),
        "training_allowed": False,
        "training_executed": False,
        "execution_contract": {"cpu_only": True, "conda_environment": "ai", "external_commands_run": False},
        "artifact_contract": {
            "candidate_ledger": "candidate_ledger.jsonl",
            "classification_ledger": "classification_ledger.jsonl",
            "model_facing_artifacts_emitted": False,
            "trainer_artifacts_emitted": False,
            "derived_target_artifacts_emitted": False,
            "records_authorized_for_use": 0,
        },
        "counts": {
            "input_candidates": len(candidates),
            "unique_source_session_root_windows": len(canonical),
            "duplicates": len(candidates) - len(canonical),
            "protected_overlap_candidates": sum(
                bool(row["protected_overlap"]["overlap"]) for row in canonical
            ),
            "classifications": {name: class_counts.get(name, 0) for name in sorted(CLASSIFICATIONS)},
            "stage12583_stage12584_floor_contribution": 0,
        },
        "floor_status": floor_status,
        "repositories_counted_toward_floor": repos,
        "deduplication": {
            "key": ["source", "session", "root", "window"],
            "canonical_count": len(canonical),
            "duplicate_count": len(candidates) - len(canonical),
        },
        "dominance": {
            "candidate_repo_family": _dominance(same_session_canonical, "repo_family"),
            "candidate_root": _dominance(root_rows, "root"),
            "floor_repo_family": _dominance(
                [by_id[row["candidate_id"]] for row in level3_rows], "repo_family"
            ),
            "self_repo_candidate_count": sum(
                row["repo_family"] == "agentkernel-seq2seq-text-lab"
                for row in same_session_canonical
            ),
        },
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "protected_overlap_policy": {
            "denylist": str(PROTECTED_DENYLIST.relative_to(ROOT)),
            "overlap_excluded_from_all_floors": True,
        },
        "input_sha256": dict(sorted(input_digests.items())),
    }
    assert_no_forbidden_output_keys(summary)
    return summary


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def execute(
    *,
    out: Path = OUT,
    summary_path: Path = SUMMARY,
    recovery_path: Path = RECOVERY_RECORDS,
    join_path: Path = JOIN_RECORDS,
    windows_path: Path = TASK_WINDOWS,
    stage12583_path: Path = STAGE12583_RECORDS,
    stage12584_path: Path = STAGE12584_RECORDS,
    denylist_path: Path = PROTECTED_DENYLIST,
) -> dict[str, Any]:
    input_paths = {
        "recovery_records": recovery_path,
        "join_records": join_path,
        "task_windows": windows_path,
        "stage12583_records": stage12583_path,
        "stage12584_records": stage12584_path,
        "protected_denylist": denylist_path,
    }
    candidates, classifications = build_ledgers(
        recovery_rows=read_jsonl(recovery_path),
        join_rows=read_jsonl(join_path),
        window_rows=read_jsonl(windows_path),
        replay12583_rows=read_jsonl(stage12583_path),
        replay12584_rows=read_jsonl(stage12584_path),
        protected_payload=read_json(denylist_path),
    )
    summary = build_summary(
        candidates,
        classifications,
        {name: file_sha256(path) for name, path in input_paths.items()},
    )
    write_jsonl(out / "candidate_ledger.jsonl", candidates)
    write_jsonl(out / "classification_ledger.jsonl", classifications)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    parser.add_argument("--recovery-records", type=Path, default=RECOVERY_RECORDS)
    parser.add_argument("--join-records", type=Path, default=JOIN_RECORDS)
    parser.add_argument("--task-windows", type=Path, default=TASK_WINDOWS)
    parser.add_argument("--stage12583-records", type=Path, default=STAGE12583_RECORDS)
    parser.add_argument("--stage12584-records", type=Path, default=STAGE12584_RECORDS)
    parser.add_argument("--protected-denylist", type=Path, default=PROTECTED_DENYLIST)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = execute(
        out=args.out,
        summary_path=args.summary,
        recovery_path=args.recovery_records,
        join_path=args.join_records,
        windows_path=args.task_windows,
        stage12583_path=args.stage12583_records,
        stage12584_path=args.stage12584_records,
        denylist_path=args.protected_denylist,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
