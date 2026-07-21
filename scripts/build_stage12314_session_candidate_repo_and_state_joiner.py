#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12314_session_candidate_repo_and_state_joiner"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12312 = (
    ROOT
    / "runs/local/artifacts/stage12312_session_episode_graph_candidate_expansion"
    / "expanded_episode_graph_candidates.jsonl"
)
WINDOWS = (
    ROOT
    / "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner"
    / "codex_task_windows.jsonl"
)
MANIFESTS = (
    ROOT
    / "runs/local/artifacts/stage12258_live_codex_chat_reconstruction_index"
    / "per_chat_manifest.jsonl"
)
PHYSICAL = (
    ROOT
    / "runs/local/artifacts/stage12256_live_physical_session_inventory_refresh"
    / "live_physical_source_records.jsonl"
)
PATH_HASH = (
    ROOT
    / "runs/local/artifacts/stage12255_physical_session_path_hash_rehydrator"
    / "path_hash_attachment_index.jsonl"
)

HASH_SALT = "stage12314_no_raw_path_or_text_join_v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def stable_hash(value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{HASH_SALT}:{payload}".encode("utf-8")).hexdigest()[:24]


def by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row.get(key)
        if value:
            out[str(value)] = row
    return out


def make_join_record(
    candidate: dict[str, Any],
    window_by_id: dict[str, dict[str, Any]],
    manifest_by_chat: dict[str, dict[str, Any]],
    physical_by_hash: dict[str, dict[str, Any]],
    path_hash_by_hash: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source_refs = candidate.get("source_refs") or {}
    task_window_id = candidate.get("task_window_id") or source_refs.get("task_window_id")
    window = window_by_id.get(str(task_window_id), {})
    chat_id = window.get("chat_id")
    manifest = manifest_by_chat.get(str(chat_id), {}) if chat_id else {}
    source_hash = (
        source_refs.get("source_file_hash_compat")
        or window.get("source_file_hash_compat")
        or manifest.get("source_file_hash_compat")
    )
    physical = physical_by_hash.get(str(source_hash), {}) if source_hash else {}
    path_hash = path_hash_by_hash.get(str(source_hash), {}) if source_hash else {}

    source_hash_match = bool(
        source_hash
        and window.get("source_file_hash_compat") == source_hash
        and manifest.get("source_file_hash_compat") == source_hash
    )
    snapshot_match = bool(
        window.get("snapshot_id")
        and manifest.get("snapshot_id")
        and window.get("snapshot_id") == manifest.get("snapshot_id")
    )
    cwd_hint_hash = stable_hash(manifest.get("cwd_hints_top"))
    workspace_hint_hash = stable_hash(manifest.get("workspace_root_hints_top"))

    ordered_events = candidate.get("ordered_events") or {}
    coarse_state = candidate.get("state_before") or {}
    ordered_patch_and_verifier_refs = bool(
        ordered_events.get("monotonic_line_order")
        and (ordered_events.get("patch_pair_count") or 0) > 0
        and (ordered_events.get("verifier_like_pair_count") or 0) > 0
    )

    blockers = [
        "repo_family_not_semantically_recovered",
        "transition_local_state_ledger_missing",
        "verifier_status_class_missing",
        "patch_applicability_or_no_patch_reason_missing",
        "state_delta_proof_missing",
        "stop_continue_proof_missing",
        "semantic_rule_id_missing",
        "transition_function_key_missing",
    ]
    if not task_window_id or not window:
        blockers.append("task_window_join_missing")
    if not chat_id or not manifest:
        blockers.append("chat_manifest_join_missing")
    if not physical:
        blockers.append("physical_source_join_missing")
    if not path_hash:
        blockers.append("path_hash_join_missing")
    if not source_hash_match:
        blockers.append("source_hash_consistency_missing")
    if not snapshot_match:
        blockers.append("snapshot_consistency_missing")
    if not cwd_hint_hash and not workspace_hint_hash:
        blockers.append("cwd_or_workspace_hint_hash_missing")
    if not ordered_patch_and_verifier_refs:
        blockers.append("ordered_patch_and_verifier_refs_missing")
    if coarse_state.get("state_code_exact") or coarse_state.get("semantic_rule_id"):
        blockers.append("unexpected_exact_state_claim_review_required")

    record_id = "stage12314::" + hashlib.sha256(
        f"{candidate.get('candidate_id')}:{task_window_id}".encode("utf-8")
    ).hexdigest()[:16]
    return {
        "stage": STAGE,
        "record_type": "session_candidate_repo_state_join_record",
        "join_record_id": record_id,
        "candidate_id": candidate.get("candidate_id"),
        "task_window_id": task_window_id,
        "canonical_root_id": candidate.get("canonical_root_id"),
        "language_family": candidate.get("language_family") or "unknown",
        "source_root_label": candidate.get("source_root_label") or path_hash.get("source_root_label"),
        "source_refs": {
            "chat_id_hash": stable_hash(chat_id),
            "session_id_hash": stable_hash(window.get("session_id_hint") or manifest.get("session_id_hint")),
            "source_file_hash_compat": source_hash,
            "physical_source_id_hash": stable_hash(physical.get("physical_source_id")),
            "relative_path_hash": path_hash.get("relative_path_hash") or manifest.get("relative_path_hash"),
            "raw_path_emitted": False,
            "raw_text_emitted": False,
            "raw_tool_arguments_emitted": False,
            "raw_tool_output_emitted": False,
            "raw_patch_body_emitted": False,
        },
        "join_status": {
            "task_window_joined": bool(window),
            "chat_manifest_joined": bool(manifest),
            "physical_source_joined": bool(physical),
            "path_hash_joined": bool(path_hash),
            "source_hash_match": source_hash_match,
            "snapshot_match": snapshot_match,
            "cwd_hint_hash": cwd_hint_hash,
            "workspace_hint_hash": workspace_hint_hash,
            "cwd_or_workspace_hint_available": bool(cwd_hint_hash or workspace_hint_hash),
            "ordered_patch_and_verifier_refs": ordered_patch_and_verifier_refs,
        },
        "window_evidence_shape": {
            "event_count": window.get("event_count") or ordered_events.get("event_count"),
            "paired_tool_call_count": window.get("paired_tool_call_count")
            or ordered_events.get("paired_tool_call_count"),
            "patch_pair_count": window.get("patch_pair_count") or ordered_events.get("patch_pair_count"),
            "verifier_like_pair_count": window.get("verifier_like_pair_count")
            or ordered_events.get("verifier_like_pair_count"),
            "has_command_observation": bool(window.get("has_command_observation")),
            "has_patch_ref": bool(window.get("has_patch_ref")),
            "has_verifier_like_ref": bool(window.get("has_verifier_like_ref")),
            "terminal_status": window.get("terminal_status"),
        },
        "level3_proof_status": {
            "level3_candidate": False,
            "reason": "joins_exist_but_transition_local_state_and_verifier_status_not_proven",
            "repo_family_recovered": False,
            "verifier_status_proven": False,
            "patch_or_no_patch_proven": False,
            "state_delta_proven": False,
            "stop_continue_proven": False,
        },
        "admission": {
            "training_allowed": False,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "level3_admitted": False,
            "patch_trace_admitted": False,
        },
        "blocked_reasons": sorted(set(blockers)),
        "claim_boundary": "Join-enriched candidate only. No raw text/path/output/patch body emitted and no training/eval admission.",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    candidates = read_jsonl(STAGE12312)
    windows = read_jsonl(WINDOWS)
    manifests = read_jsonl(MANIFESTS)
    physical_sources = read_jsonl(PHYSICAL)
    path_hashes = read_jsonl(PATH_HASH)

    window_by_id = by_key(windows, "task_window_id")
    manifest_by_chat = by_key(manifests, "chat_id")
    physical_by_hash = by_key(physical_sources, "source_file_hash_compat")
    path_hash_by_hash: dict[str, dict[str, Any]] = {}
    for row in path_hashes:
        for key in ["source_file_hash_compat", "attach_key_for_derivative_source_file_hash"]:
            value = row.get(key)
            if value:
                path_hash_by_hash[str(value)] = row

    records = [
        make_join_record(candidate, window_by_id, manifest_by_chat, physical_by_hash, path_hash_by_hash)
        for candidate in candidates
    ]
    write_jsonl(OUT / "session_candidate_repo_state_join_records.jsonl", records)

    blocker_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    join_counts: defaultdict[str, int] = defaultdict(int)
    unique_hint_hashes = set()
    for record in records:
        language_counts[record["language_family"]] += 1
        blocker_counts.update(record["blocked_reasons"])
        for key, value in record["join_status"].items():
            if isinstance(value, bool) and value:
                join_counts[key] += 1
        for key in ["cwd_hint_hash", "workspace_hint_hash"]:
            value = record["join_status"].get(key)
            if value:
                unique_hint_hashes.add(value)

    summary = {
        "stage": STAGE,
        "decision": "session_candidates_join_enriched_training_still_blocked",
        "claim_boundary": "Repo/state join artifact only. It emits no raw paths, raw text, raw commands, raw outputs, patch bodies, train rows, or eval rows.",
        "training_allowed": False,
        "candidate_records": len(records),
        "training_rows_emitted": 0,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "language_counts": dict(language_counts),
        "join_true_counts": dict(join_counts),
        "unique_cwd_or_workspace_hint_hashes": len(unique_hint_hashes),
        "blocked_reason_counts": dict(blocker_counts),
        "subagent_findings_encoded": [
            "100/100 candidates should join to task windows/manifests/source hashes when indexes are present.",
            "Cwd/workspace hints may be hashed for routing but raw paths must not be emitted.",
            "Patch+verifier co-presence is not proof of verifier status, patch applicability, or state delta.",
        ],
        "next_stage": {
            "stage": "stage12316_transition_local_event_joiner",
            "purpose": "Use event/tool indices within each joined window to classify verifier status, patch/no-patch proof, state delta, and stop/continue without raw text leakage.",
            "training_allowed": False,
        },
    }
    (OUT / "session_candidate_repo_state_join_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "SESSION_CANDIDATE_REPO_STATE_JOINER_STAGE12314.md").write_text(
        "# Stage12314 Session Candidate Repo/State Joiner\n\n"
        "This stage enriches Stage12312 session candidates with no-content joins to task windows, chat manifests, physical source records, and path-hash records.\n\n"
        "It intentionally admits zero rows. The join proves index connectivity, not Level-3 maintainer causality.\n\n"
        "## Hard Boundary\n\n"
        "- No raw cwd/path, chat text, tool arguments/output, command text, or patch body is emitted.\n"
        "- Patch and verifier references remain co-presence until transition-local event proof classifies status and state delta.\n"
        "- `repo_family` remains unrecovered unless a leak-safe allowlisted mapping is introduced later.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
