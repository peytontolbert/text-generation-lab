#!/usr/bin/env python3
"""Recover hash-only original source-stage locator refs for Stage12505 blockers.

Stage12506 is a fail-closed preflight. It reads canonical Stage12505 blocked
items and Stage12504 work items, then attempts to prove source-stage locator
coverage by replaying Stage12500 identity hashes over the Stage12385 combined
selected-test ledger and joining the matched row back to its original
source_stage artifact. It never runs extraction, emits handoff jobs, admits
rows, or writes raw commands/source/diffs/verifier text.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12506_source_stage_locator_recovery_preflight"
OUT_REL = Path("runs/local/artifacts") / STAGE
SUMMARY_REL = Path("runs/summaries") / f"{STAGE}.json"

STAGE12504 = "stage12504_private_extractor_source_locator_worklist"
STAGE12504_WORKLIST_REL = (
    Path("runs/local/artifacts")
    / STAGE12504
    / "private_extractor_source_locator_worklist.jsonl"
)
STAGE12504_SUMMARY_REL = Path("runs/summaries") / f"{STAGE12504}.json"

STAGE12505 = "stage12505_ai_env_extraction_handoff_or_blocker"
STAGE12505_BLOCKERS_REL = (
    Path("runs/local/artifacts")
    / STAGE12505
    / "ai_env_private_extraction_handoff_blockers.jsonl"
)
STAGE12505_SUMMARY_REL = Path("runs/summaries") / f"{STAGE12505}.json"

STAGE12500_SALT = "stage12500_closed_loop_candidate_packet_router"
STAGE12385_ROWS_REL = (
    Path("runs/local/artifacts/stage12385_combined_train_support_ledger_v15_dedup")
    / "combined_selected_test_rows_v15_dedup.jsonl"
)

CONTEXT_ONLY_STAGES = {
    "stage12500_closed_loop_candidate_packet_router",
    "stage12502_authoritative_private_semantic_extraction_request_preflight",
    "stage12503_private_semantic_extraction_return_validator",
    STAGE12504,
    STAGE12505,
    STAGE,
}
SOURCE_FILE_SUFFIXES = {".json", ".jsonl"}
SOURCE_PROOF_KEYS = {
    "source_row_id_hash",
    "row_id_hash",
    "source_ref_hash",
    "root_or_window_hash",
}
SAFE_HASH_RE = re.compile(r"[0-9a-f]{12,64}")
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output|commit:)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)

FALSE_GUARDS = {
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
    "network_performed_by_stage": False,
    "policy_label_materialized": False,
    "level3_atom_materialized": False,
    "patch_trace_materialized": False,
    "stage12503_return_materialized": False,
    "stage12503_return_file_written": False,
    "handoff_jobs_emitted": False,
}
ZERO_GUARDS = {
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "level3_atom_count": 0,
    "patch_trace_admitted": 0,
    "patch_trace_rows": 0,
    "stage12496_return_records_written": 0,
    "stage12503_return_records_written": 0,
    "policy_labels_emitted": 0,
    "proof_rows_emitted": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
    "handoff_job_count": 0,
}


class RawLeakError(ValueError):
    """Raised when a public Stage12506 output contains raw-looking content."""


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def stage12500_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE12500_SALT}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def scan_raw_leaks(value: Any) -> list[str]:
    issues: list[str] = []
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(stable_hash(value))
    elif isinstance(value, dict):
        for child in value.values():
            issues.extend(scan_raw_leaks(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan_raw_leaks(child))
    return issues


def enforce_no_raw_leaks(value: Any) -> None:
    issues = scan_raw_leaks(value)
    if issues:
        raise RawLeakError(f"stage12506 raw leak guard rejected {len(issues)} public field(s)")


def source_files_for_stage(root: Path, stage: str) -> list[Path]:
    stage_dir = root / "runs/local/artifacts" / stage
    if stage in CONTEXT_ONLY_STAGES or not stage_dir.exists():
        return []
    return sorted(
        path
        for path in stage_dir.rglob("*")
        if path.is_file() and path.suffix in SOURCE_FILE_SUFFIXES
    )


def stage12500_row_identity(row: dict[str, Any]) -> dict[str, str]:
    root_id = row.get("root_id") or (row.get("source_refs") or {}).get("task_window_id") or row.get("source_row_id")
    return {
        "row_id_hash": stage12500_hash(row.get("row_id") or row.get("source_row_id")),
        "source_row_id_hash": stage12500_hash(row.get("source_row_id") or row.get("row_id")),
        "root_or_window_hash": stage12500_hash(root_id),
        "source_ref_hash": stage12500_hash(row.get("source_refs") or {}),
    }


def stage12500_packet_identity(row: dict[str, Any]) -> dict[str, str]:
    return {
        "packet_id_hash": stage12500_hash(
            {
                "source": "selected_test_transition_support",
                "row": row.get("row_id") or row.get("source_row_id"),
            }
        ),
        **stage12500_row_identity(row),
    }


def load_stage12385_rows(root: Path) -> list[dict[str, Any]]:
    return read_jsonl(root / STAGE12385_ROWS_REL)


def stage12385_match_for_request(
    root: Path,
    row: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, bool]]:
    verification = {
        "unique_stage12385_match": False,
        "packet_id_hash_match": False,
        "row_id_hash_match": False,
        "source_row_id_hash_match": False,
        "root_or_window_hash_match": False,
        "source_ref_hash_match": False,
        "unique_source_stage_artifact_match": False,
    }
    matches: list[tuple[dict[str, Any], dict[str, str]]] = []
    for source_row in load_stage12385_rows(root):
        identity = stage12500_packet_identity(source_row)
        if identity.get("packet_id_hash") == row.get("packet_id_hash"):
            matches.append((source_row, identity))
    if len(matches) != 1:
        return None, verification

    source_row, identity = matches[0]
    lookup = safe_lookup_hashes(row)
    verification["unique_stage12385_match"] = True
    for key in [
        "packet_id_hash",
        "row_id_hash",
        "source_row_id_hash",
        "root_or_window_hash",
        "source_ref_hash",
    ]:
        verification[f"{key}_match"] = identity.get(key) == (lookup.get(key) or row.get(key))
    return source_row, verification


def source_row_matches(candidate: dict[str, Any], source_row: dict[str, Any]) -> bool:
    if candidate.get("row_id") and source_row.get("row_id"):
        if candidate.get("row_id") == source_row.get("row_id"):
            return True
    if candidate.get("source_row_id") and source_row.get("source_row_id"):
        if candidate.get("source_row_id") == source_row.get("source_row_id"):
            return True
    if (
        candidate.get("root_id") == source_row.get("root_id")
        and candidate.get("task_family") == source_row.get("task_family")
        and candidate.get("repo_family") == source_row.get("repo_family")
    ):
        return True
    if candidate.get("supersedes_row_id") and candidate.get("supersedes_row_id") == source_row.get("row_id"):
        return True
    if source_row.get("supersedes_row_id") and source_row.get("supersedes_row_id") == candidate.get("row_id"):
        return True
    return False


def row_is_preferred_train_support(candidate: dict[str, Any]) -> bool:
    admission = candidate.get("admission") or {}
    if admission.get("train_support_allowed") is False:
        return False
    if admission.get("training_allowed") is False:
        return False
    if candidate.get("blocked_reasons"):
        return False
    return True


def original_source_stage_matches(
    root: Path,
    source_stage: str,
    source_row: dict[str, Any],
) -> list[tuple[Path, dict[str, Any]]]:
    matches: list[tuple[Path, dict[str, Any]]] = []
    for artifact in source_files_for_stage(root, source_stage):
        if artifact.suffix == ".jsonl":
            for candidate in read_jsonl(artifact):
                if source_row_matches(candidate, source_row):
                    matches.append((artifact, candidate))
        else:
            candidate = read_json(artifact)
            if source_row_matches(candidate, source_row):
                matches.append((artifact, candidate))
    preferred = [(artifact, row) for artifact, row in matches if row_is_preferred_train_support(row)]
    return preferred or matches


def direct_source_stage_identity_match(
    root: Path,
    row: dict[str, Any],
) -> tuple[Path, dict[str, Any], dict[str, bool]] | None:
    source_stage = row.get("source_stage")
    if not isinstance(source_stage, str):
        return None
    lookup = safe_lookup_hashes(row)
    matches: list[tuple[Path, dict[str, Any], dict[str, bool]]] = []
    for artifact in source_files_for_stage(root, source_stage):
        rows = read_jsonl(artifact) if artifact.suffix == ".jsonl" else [read_json(artifact)]
        for candidate in rows:
            identity = stage12500_packet_identity(candidate)
            if identity.get("packet_id_hash") != row.get("packet_id_hash"):
                continue
            verification = {
                "unique_stage12385_match": False,
                "packet_id_hash_match": True,
                "row_id_hash_match": identity.get("row_id_hash") == lookup.get("row_id_hash"),
                "source_row_id_hash_match": identity.get("source_row_id_hash") == lookup.get("source_row_id_hash"),
                "root_or_window_hash_match": identity.get("root_or_window_hash") == lookup.get("root_or_window_hash"),
                "source_ref_hash_match": identity.get("source_ref_hash") == lookup.get("source_ref_hash"),
                "unique_source_stage_artifact_match": False,
                "direct_source_stage_identity_match": True,
            }
            if all(verification[k] for k in ["row_id_hash_match", "source_row_id_hash_match", "root_or_window_hash_match", "source_ref_hash_match"]):
                matches.append((artifact, candidate, verification))
    preferred = [match for match in matches if row_is_preferred_train_support(match[1])]
    matches = preferred or matches
    if len(matches) != 1:
        return None
    artifact, candidate, verification = matches[0]
    verification["unique_source_stage_artifact_match"] = True
    return artifact, candidate, verification


def recovered_source_locator_refs_by_identity_replay(
    root: Path,
    row: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, bool], list[str]]:
    source_stage = row.get("source_stage")
    blockers: list[str] = []
    refs: list[dict[str, Any]] = []
    stage12385_row, verification = stage12385_match_for_request(root, row)
    recovery_method = "replay_stage12500_identity_over_stage12385_then_unique_row_join_to_source_stage_artifact"
    if stage12385_row is None:
        direct_match = direct_source_stage_identity_match(root, row)
        if direct_match is None:
            blockers.append("stage12385_or_direct_source_stage_identity_replay_match_missing_or_nonunique")
            return refs, verification, blockers
        artifact, stage12385_row, verification = direct_match
        matched_row = stage12385_row
        recovery_method = "replay_stage12500_identity_over_original_source_stage_artifact"
    else:
        if not all(
            verification.get(key)
            for key in [
                "packet_id_hash_match",
                "row_id_hash_match",
                "source_row_id_hash_match",
                "root_or_window_hash_match",
                "source_ref_hash_match",
            ]
        ):
            blockers.append("stage12500_identity_replay_verification_failed")
        if stage12385_row.get("stage") != source_stage:
            blockers.append("stage12385_source_stage_mismatch")

        source_matches = original_source_stage_matches(root, str(source_stage), stage12385_row)
        verification["unique_source_stage_artifact_match"] = len(source_matches) == 1
        if len(source_matches) != 1:
            blockers.append("original_source_stage_row_match_missing_or_nonunique")
            return refs, verification, blockers

        artifact, matched_row = source_matches[0]
    content_hash = file_hash(artifact)
    row_locator_hash = stable_hash(
        {
            "source_stage": source_stage,
            "stage12385_packet_id_hash": row.get("packet_id_hash"),
            "source_row_identity": stage12500_packet_identity(stage12385_row),
        }
    )
    refs.append(
        {
            "record_type": "stage12506_recovered_source_stage_locator_ref_v1",
            "artifact_stage": source_stage,
            "locator_id_hash": stable_hash({"request": row.get("request_id_hash"), "row": row_locator_hash}),
            "artifact_locator_hash": stable_hash(
                {
                    "stage": source_stage,
                    "artifact_role_hash": stable_hash({"stage": source_stage, "role": artifact.name}),
                    "content": content_hash,
                }
            ),
            "artifact_file_role_hash": stable_hash({"stage": source_stage, "role": artifact.name}),
            "artifact_content_hash": content_hash,
            "row_locator_hash": row_locator_hash,
            "matched_row_key_names": sorted(
                key
                for key in ["row_id", "source_row_id", "root_id", "task_family", "repo_family"]
                if matched_row.get(key) == stage12385_row.get(key) and matched_row.get(key) is not None
            ),
            "recovery_method": recovery_method,
            "public_safe_hash_locator_only": True,
            "raw_locator_values_emitted": False,
        }
    )
    return refs, verification, blockers


def safe_lookup_hashes(row: dict[str, Any]) -> dict[str, str]:
    values: dict[str, Any] = {}
    values.update(row.get("hash_lookup_keys") or {})
    for key in [
        "request_id_hash",
        "audit_item_id_hash",
        "work_item_id_hash",
        "packet_id_hash",
        "root_or_window_hash",
    ]:
        values.setdefault(key, row.get(key))
    return {
        key: value
        for key, value in values.items()
        if isinstance(key, str) and isinstance(value, str) and SAFE_HASH_RE.fullmatch(value)
    }


def context_locator_count(row: dict[str, Any], blocker: dict[str, Any] | None) -> int:
    if blocker and isinstance(blocker.get("context_locator_ref_count"), int):
        return blocker["context_locator_ref_count"]
    return sum(
        1
        for locator in row.get("hash_locator_records") or []
        if locator.get("artifact_stage") in CONTEXT_ONLY_STAGES
    )


def existing_source_locator_refs(row: dict[str, Any]) -> list[dict[str, Any]]:
    source_stage = row.get("source_stage")
    refs: list[dict[str, Any]] = []
    if source_stage in CONTEXT_ONLY_STAGES:
        return refs
    for locator in row.get("hash_locator_records") or []:
        if locator.get("artifact_stage") != source_stage:
            continue
        refs.append(
            {
                "locator_id_hash": locator.get("locator_id_hash"),
                "artifact_stage": source_stage,
                "artifact_locator_hash": locator.get("artifact_locator_hash"),
                "artifact_file_role_hash": locator.get("artifact_file_role_hash"),
                "artifact_content_hash": locator.get("artifact_content_hash"),
                "matched_lookup_key_names": sorted(locator.get("matched_lookup_key_names") or []),
                "matched_lookup_key_count": locator.get("matched_lookup_key_count", 0),
                "recovery_method": "preexisting_stage12504_source_stage_locator_ref",
                "public_safe_hash_locator_only": True,
            }
        )
    return refs


def recovered_source_locator_refs(root: Path, row: dict[str, Any]) -> list[dict[str, Any]]:
    source_stage = row.get("source_stage")
    if not isinstance(source_stage, str) or source_stage in CONTEXT_ONLY_STAGES:
        return []
    lookup_hashes = safe_lookup_hashes(row)
    source_lookup_hashes = {
        key: value for key, value in lookup_hashes.items() if key in SOURCE_PROOF_KEYS
    }
    refs: list[dict[str, Any]] = []
    for artifact in source_files_for_stage(root, source_stage):
        text = artifact.read_text(encoding="utf-8", errors="replace")
        matched_keys = sorted(
            key for key, value in source_lookup_hashes.items() if value in text
        )
        if not matched_keys:
            continue
        content_hash = file_hash(artifact)
        refs.append(
            {
                "record_type": "stage12506_source_stage_locator_recovery_candidate_ref_v1",
                "locator_id_hash": stable_hash(
                    {
                        "request": row.get("request_id_hash"),
                        "stage": source_stage,
                        "artifact_content_hash": content_hash,
                        "matches": matched_keys,
                    }
                ),
                "artifact_stage": source_stage,
                "artifact_locator_hash": stable_hash(
                    {
                        "stage": source_stage,
                        "artifact_role_hash": stable_hash({"stage": source_stage, "role": artifact.name}),
                        "content": content_hash,
                    }
                ),
                "artifact_file_role_hash": stable_hash({"stage": source_stage, "role": artifact.name}),
                "artifact_content_hash": content_hash,
                "matched_lookup_key_names": matched_keys,
                "matched_lookup_key_count": len(matched_keys),
                "source_stage_match_proven": True,
                "recovery_method": "source_stage_artifact_hash_overlap",
                "public_safe_hash_locator_only": True,
            }
        )
    deduped: dict[str, dict[str, Any]] = {}
    for ref in [*existing_source_locator_refs(row), *refs]:
        deduped.setdefault(ref["locator_id_hash"], ref)
    return list(deduped.values())


def common_fields(row: dict[str, Any], blocker: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "request_id_hash": row.get("request_id_hash"),
        "audit_item_id_hash": row.get("audit_item_id_hash"),
        "work_item_id_hash": row.get("work_item_id_hash"),
        "packet_id_hash": row.get("packet_id_hash"),
        "root_or_window_hash": row.get("root_or_window_hash"),
        "source_stage": row.get("source_stage"),
        "source_kind": row.get("source_kind"),
        "task_family": row.get("task_family"),
        "language_family": row.get("language_family"),
        "materialization_environment": "ai_env",
        "forbidden_materialization_environments": ["trellis"],
        "source_stage_locator_ref_count": 0,
        "context_locator_ref_count": context_locator_count(row, blocker),
        "raw_private_values_revealed": False,
        "raw_locator_values_emitted": False,
        "raw_source_output_included": False,
        "public_safe_hash_locator_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def build_recovery_record(
    root: Path,
    row: dict[str, Any],
    blocker: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    common = common_fields(row, blocker)
    source_stage = row.get("source_stage")
    refs, verification_flags, replay_blockers = recovered_source_locator_refs_by_identity_replay(root, row)
    if not refs:
        refs = recovered_source_locator_refs(root, row)
        verification_flags = {
            "unique_stage12385_match": False,
            "packet_id_hash_match": False,
            "row_id_hash_match": False,
            "source_row_id_hash_match": False,
            "root_or_window_hash_match": False,
            "source_ref_hash_match": False,
            "unique_source_stage_artifact_match": bool(refs),
            "hash_overlap_fallback_match": bool(refs),
        }
        if refs:
            replay_blockers = []
    blockers: list[str] = list(replay_blockers)

    if row.get("materialization_environment") != "ai_env":
        blockers.append("stage12504_materialization_environment_not_ai_env")
    if not isinstance(source_stage, str) or not source_stage:
        blockers.append("source_stage_missing")
    elif source_stage in CONTEXT_ONLY_STAGES:
        blockers.append("source_stage_is_context_only")
    if blocker is None:
        blockers.append("stage12505_blocker_missing")
    if not safe_lookup_hashes(row):
        blockers.append("safe_hash_lookup_keys_missing")
    if not any(key in SOURCE_PROOF_KEYS for key in safe_lookup_hashes(row)):
        blockers.append("source_identity_hash_lookup_keys_missing")
    if not source_files_for_stage(root, str(source_stage or "")):
        blockers.append("original_source_stage_artifacts_missing")
    if not refs:
        blockers.append("original_source_stage_locator_refs_unproven")

    common["source_stage_locator_ref_count"] = len(refs)
    if blockers:
        record = {
            "record_type": "stage12506_source_stage_locator_recovery_blocker_v1",
            "recovery_blocker_id_hash": stable_hash(
                {"request": row.get("request_id_hash"), "blockers": sorted(set(blockers))}
            ),
            "recovery_decision": "blocked_no_handoff_jobs_original_source_stage_locator_refs_unproven",
            "blocker_codes": sorted(set(blockers)),
            "source_stage_locator_refs": [],
            "source_stage_recovery_verification": verification_flags,
            "safe_next_action": "repair upstream hash-only source-stage locator evidence, then rerun Stage12506 and Stage12505",
            **common,
        }
        enforce_no_raw_leaks(record)
        return None, record

    record = {
        "record_type": "stage12506_source_stage_locator_recovery_candidate_v1",
        "recovery_candidate_id_hash": stable_hash(
            {"request": row.get("request_id_hash"), "source_refs": refs}
        ),
        "recovery_decision": "source_stage_locator_refs_recovered_no_handoff_jobs_emitted",
        "source_stage_locator_refs": refs,
        "source_stage_recovery_verification": verification_flags,
        "source_stage_locator_patch_ref": {
            "patch_target_stage": STAGE12504,
            "patch_intent": "add_hash_only_original_source_stage_locator_refs_before_rerunning_stage12505",
            "patch_payload_hash": stable_hash({"request": row.get("request_id_hash"), "refs": refs}),
            "raw_patch_emitted": False,
        },
        **common,
    }
    enforce_no_raw_leaks(record)
    return record, None


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / OUT_REL
    out.mkdir(parents=True, exist_ok=True)

    stage12504_summary = read_json(root / STAGE12504_SUMMARY_REL)
    stage12505_summary = read_json(root / STAGE12505_SUMMARY_REL)
    work_items = read_jsonl(root / STAGE12504_WORKLIST_REL)
    blockers = read_jsonl(root / STAGE12505_BLOCKERS_REL)

    work_by_request = {row.get("request_id_hash"): row for row in work_items}
    blocked_targets = blockers or [
        row
        for row in work_items
        if not existing_source_locator_refs(row)
    ]

    candidates: list[dict[str, Any]] = []
    recovery_blockers: list[dict[str, Any]] = []
    for blocker in blocked_targets:
        row = work_by_request.get(blocker.get("request_id_hash"), blocker)
        candidate, recovery_blocker = build_recovery_record(root, row, blocker if blockers else None)
        if candidate is not None:
            candidates.append(candidate)
        if recovery_blocker is not None:
            recovery_blockers.append(recovery_blocker)

    all_records = [*candidates, *recovery_blockers]
    language_counts = Counter(row.get("language_family") for row in all_records)
    task_counts = Counter(row.get("task_family") for row in all_records)
    source_stage_counts = Counter(row.get("source_stage") for row in all_records)
    blocker_counts = Counter()
    for row in recovery_blockers:
        blocker_counts.update(row.get("blocker_codes") or [])
    recovered_ref_count = sum(row["source_stage_locator_ref_count"] for row in candidates)
    blocked_ref_count = sum(row["source_stage_locator_ref_count"] for row in recovery_blockers)

    contract = {
        "record_type": "stage12506_source_stage_locator_recovery_preflight_contract_v1",
        "stage": STAGE,
        "input_stages": [STAGE12504, STAGE12505],
        "materialization_environment": "ai_env",
        "forbidden_materialization_environments": ["trellis"],
        "public_artifact_policy": "hashes_stage_ids_enums_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        "recovery_gate": "requires_stage12500_identity_replay_over_stage12385_or_declared_source_stage_and_unique_original_source_stage_row_join",
        "context_only_locator_policy": "never_promote_context_only_stage_locators_to_source_stage_locators",
        "handoff_policy": "no_handoff_jobs_emitted_by_stage12506",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }

    outputs = {
        "recovery_candidates": candidates,
        "recovery_blockers": recovery_blockers,
        "contract": contract,
    }
    leak_issues = scan_raw_leaks(outputs)
    guardrail = {
        "stage": STAGE,
        "scan_passed": not leak_issues,
        "raw_leak_count": len(leak_issues),
        "raw_leak_issue_hashes": leak_issues[:40],
        "scanned_outputs": [
            "source_stage_locator_recovery_candidates.jsonl",
            "source_stage_locator_recovery_blockers.jsonl",
            "source_stage_locator_recovery_contract.json",
        ],
    }
    if leak_issues:
        raise RawLeakError("stage12506 raw leak guard rejected public outputs")

    decision = (
        "source_stage_locator_recovery_candidates_ready_no_training_or_handoff"
        if candidates and not recovery_blockers
        else "partial_source_stage_locator_recovery_candidates_ready_remaining_blocked_no_training_or_handoff"
        if candidates
        else "blocked_original_source_stage_locator_refs_unproven_no_training_or_handoff"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12506_source_stage_locator_recovery_preflight_summary_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12506 recovers only hash/ref source-stage locator candidates for Stage12505 blockers. "
            "It does not execute extraction, does not emit handoff jobs, does not inspect raw source into "
            "public outputs, and does not admit or train on rows."
        ),
        "source_stage": STAGE12505,
        "stage12504_decision": stage12504_summary.get("decision"),
        "stage12505_decision": stage12505_summary.get("decision"),
        "input_work_item_count": len(work_items),
        "input_blocked_item_count": len(blocked_targets),
        "recovery_candidate_count": len(candidates),
        "recovery_blocker_count": len(recovery_blockers),
        "recovered_source_stage_locator_ref_count": recovered_ref_count,
        "blocked_source_stage_locator_ref_count": blocked_ref_count,
        "context_only_promoted_count": 0,
        "language_counts": dict(sorted(language_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "source_stage_counts": dict(sorted(source_stage_counts.items())),
        "blocker_code_counts": dict(sorted(blocker_counts.items())),
        "materialization_environment": "ai_env",
        "forbidden_materialization_environments": ["trellis"],
        "public_artifact_policy": contract["public_artifact_policy"],
        "guardrail_scan_passed": guardrail["scan_passed"],
        "raw_leak_count": guardrail["raw_leak_count"],
        "next_stage": (
            "patch_stage12504_with_hash_only_recovery_candidates_then_rerun_stage12505"
            if candidates
            else "repair_upstream_source_stage_locator_evidence_before_stage12505_handoff"
        ),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }

    write_jsonl(out / "source_stage_locator_recovery_candidates.jsonl", candidates)
    write_jsonl(out / "source_stage_locator_recovery_blockers.jsonl", recovery_blockers)
    write_json(out / "source_stage_locator_recovery_contract.json", contract)
    write_json(out / "guardrail_scan.json", guardrail)
    write_json(out / "summary.json", summary)
    write_json(root / SUMMARY_REL, summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()
