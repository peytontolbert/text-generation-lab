#!/usr/bin/env python3
"""Stage12433 Open-SWE pilot-100 private proof-slot runner postrun.

This stage may privately inspect a bounded deterministic Open-SWE parquet row
sample to classify proof-slot recoverability from row structure. It emits only
public-safe aggregate counts, hashes, and normalized enums. It never emits raw
row values, paths, URLs, commands, command outputs, diffs, patches, issue text,
source text, or schema field names.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12433_open_swe_pilot_100_private_proof_slot_runner_postrun"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
STAGE12431_SUMMARY = ROOT / "runs/summaries/stage12431_open_swe_private_pilot_100_postrun_summary.json"
STAGE12432_SUMMARY = ROOT / "runs/summaries/stage12432_open_swe_pilot_100_proof_slot_reconstruction_request.json"

DATASET_ROOT_PROBES = [
    Path("/arxiv/datasets/nvidia--Open-SWE-Traces"),
    Path("/arxiv/datasets/Open-SWE-Traces"),
    Path("/data/.cache/huggingface/hub/datasets--nvidia--Open-SWE-Traces"),
    Path("/data/datasets/nvidia--Open-SWE-Traces"),
    Path("/data/datasets/Open-SWE-Traces"),
    ROOT / "datasets/nvidia--Open-SWE-Traces",
    ROOT / "datasets/Open-SWE-Traces",
    ROOT / "data/nvidia--Open-SWE-Traces",
    ROOT / "data/Open-SWE-Traces",
]

CANDIDATE_SUPPLY_ROWS = 207489
REQUESTED_SAMPLE_SIZE = 100
DETERMINISTIC_SEED = 12431

PROOF_SLOTS = [
    "checkout_before_anchor",
    "patch_application_proof",
    "same_verifier_before_after",
    "causal_transition",
    "state_after",
    "stop_continue",
]

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "admitted_rows": 0,
    "emitted_rows": 0,
    "emitted_training_rows": 0,
    "countable_rows": 0,
    "countable_new_rows": 0,
    "countable_as_new_train_support_rows": 0,
    "countable_as_new_proof_floor_rows": 0,
    "raw_rows_copied": 0,
    "raw_content_emitted": False,
    "checkout_execution_attempted_count": 0,
    "patch_apply_attempted_count": 0,
    "verifier_execution_attempted_count": 0,
    "replay_attempted_count": 0,
    "tests_run_count": 0,
}

RAW_CONTENT_POLICY: dict[str, bool] = {
    "raw_trajectories_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_diffs_emitted": False,
    "raw_patches_emitted": False,
    "raw_issue_bodies_emitted": False,
    "raw_paths_emitted": False,
    "raw_urls_emitted": False,
    "source_text_emitted": False,
    "row_values_emitted": False,
    "locator_values_emitted": False,
    "schema_field_names_emitted": False,
    "private_slot_values_emitted": False,
    "training_rows_emitted": False,
}

FORBIDDEN_TEXT_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout|stderr|pytest |npm |pip |git clone|git apply|curl )\b",
    re.IGNORECASE | re.MULTILINE,
)

OVERCLAIM_RE = re.compile(
    r"\b(?:training rows|admitted training|admission allowed|level3 complete|"
    r"closed loop|verified repair|causal proof|patch applied|replay succeeded|tests passed)\b",
    re.IGNORECASE,
)

ALLOWED_OVERCLAIM_CONTEXT_RE = re.compile(
    r"(false|zero|none|not_|no_|blocked|drop|candidate|after_private_replay|"
    r"training_allowed|admission_allowed|admitted_rows|level3_candidates|"
    r"patch_trace_candidates|replay_attempted_count|patch_apply_attempted_count|"
    r"not_executed|execution_attempted_count)",
    re.IGNORECASE,
)

PRIVATE_COLUMN_CANDIDATES = {
    "row_identity": ("instance_id", "repo", "trajectory_id", "id"),
    "result": ("resolved", "result", "resolution", "status", "instance_status"),
    "checkout_locator": (
        "repo",
        "repository",
        "repo_name",
        "instance_id",
        "trajectory_id",
    ),
    "before_anchor": (
        "base_commit",
        "before_commit",
        "commit",
        "commit_sha",
        "parent_commit",
        "environment_setup_commit",
        "checkout_commit",
    ),
    "after_anchor": (
        "after_commit",
        "final_commit",
        "head_commit",
        "commit_sha",
        "patch_commit",
        "environment_setup_commit",
    ),
    "patch_payload": (
        "patch",
        "diff",
        "model_patch",
        "gold_patch",
        "test_patch",
        "candidate_patch",
    ),
    "trace_payload": (
        "trajectory",
        "messages",
        "events",
        "history",
        "turns",
        "steps",
        "actions",
    ),
    "verifier_identity": (
        "test_patch",
        "fail_to_pass",
        "pass_to_pass",
        "tests",
        "test_cmd",
        "verifier",
    ),
    "before_observation": (
        "fail_to_pass",
        "before_result",
        "pre_result",
        "initial_result",
        "before_observation",
    ),
    "after_observation": (
        "resolved",
        "after_result",
        "post_result",
        "final_result",
        "after_observation",
    ),
    "stop_continue": (
        "resolved",
        "status",
        "result",
        "termination",
        "stop_reason",
        "done",
        "finished",
    ),
}


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def scalar(row: dict[str, Any], candidates: Iterable[str]) -> Any:
    for name in candidates:
        if name in row:
            return row.get(name)
    return None


def value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return str(value).strip() != ""


def present(row: dict[str, Any], role: str) -> bool:
    return value_present(scalar(row, PRIVATE_COLUMN_CANDIDATES[role]))


def normalize_result(value: Any) -> str:
    if isinstance(value, bool):
        return "resolved" if value else "unresolved"
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "success", "passed", "pass", "resolved"}:
        return "resolved"
    if text in {"false", "0", "no", "failure", "failed", "fail", "unresolved"}:
        return "unresolved"
    return "unknown_or_other"


def probe_roots() -> list[Path]:
    return [path for path in DATASET_ROOT_PROBES if path.exists() and path.is_dir()]


def iter_parquet_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in {".git", "__pycache__"}]
            for filename in filenames:
                path = Path(dirpath) / filename
                if path.suffix.lower() != ".parquet":
                    continue
                try:
                    key = str(path.resolve(strict=True))
                except Exception:
                    key = str(path)
                if key in seen:
                    continue
                seen.add(key)
                files.append(path)
    return sorted(files, key=lambda p: stable_hash(str(p), 32))


def parquet_plan(files: list[Path]) -> tuple[list[dict[str, Any]], str]:
    try:
        import pyarrow.parquet as pq  # type: ignore
    except Exception as exc:
        return [], f"pyarrow_unavailable_{type(exc).__name__}"

    plan: list[dict[str, Any]] = []
    offset = 0
    try:
        for path in files:
            parquet = pq.ParquetFile(path)
            meta = parquet.metadata
            row_count = safe_int(meta.num_rows)
            schema = meta.schema
            field_hashes = [
                stable_hash({"name": schema.column(index).name, "type": str(schema.column(index).physical_type)}, 16)
                for index in range(len(schema.names))
            ]
            row_group_bounds = []
            group_offset = 0
            for group_index in range(safe_int(meta.num_row_groups)):
                group_rows = safe_int(meta.row_group(group_index).num_rows)
                row_group_bounds.append((group_index, group_offset, group_offset + group_rows))
                group_offset += group_rows
            plan.append(
                {
                    "path": path,
                    "start": offset,
                    "end": offset + row_count,
                    "row_count": row_count,
                    "row_group_count": safe_int(meta.num_row_groups),
                    "column_count": len(schema.names),
                    "schema_signature": stable_hash(sorted(field_hashes), 24),
                    "schema_names": tuple(schema.names),
                    "row_group_bounds": row_group_bounds,
                    "config_bucket_hash": stable_hash(path.parent.name, 16),
                }
            )
            offset += row_count
    except Exception as exc:
        return [], f"parquet_metadata_read_blocked_{type(exc).__name__}"
    return plan, ""


def selected_columns(schema_names: tuple[str, ...]) -> list[str]:
    names = set(schema_names)
    selected: set[str] = set()
    for candidates in PRIVATE_COLUMN_CANDIDATES.values():
        for name in candidates:
            if name in names:
                selected.add(name)
    return sorted(selected)


def locate_samples(plan: list[dict[str, Any]], global_indexes: list[int]) -> dict[int, list[int]]:
    by_file: dict[int, list[int]] = defaultdict(list)
    file_index = 0
    for global_index in sorted(global_indexes):
        while file_index < len(plan) and global_index >= safe_int(plan[file_index]["end"]):
            file_index += 1
        if file_index >= len(plan):
            continue
        by_file[file_index].append(global_index - safe_int(plan[file_index]["start"]))
    return by_file


def locate_row_groups(item: dict[str, Any], local_indexes: list[int]) -> dict[int, list[int]]:
    by_group: dict[int, list[int]] = defaultdict(list)
    bounds = item.get("row_group_bounds", [])
    group_index = 0
    for local_index in sorted(local_indexes):
        while group_index < len(bounds) and local_index >= bounds[group_index][2]:
            group_index += 1
        if group_index >= len(bounds):
            continue
        row_group, start, _end = bounds[group_index]
        by_group[row_group].append(local_index - start)
    return by_group


def private_row_hash(row: dict[str, Any]) -> str:
    values = []
    for name in PRIVATE_COLUMN_CANDIDATES["row_identity"]:
        if name in row:
            values.append([stable_hash(name, 12), stable_hash(row.get(name), 24)])
    if not values:
        values = [[stable_hash(key, 12), stable_hash(value, 24)] for key, value in sorted(row.items())]
    return stable_hash(values, 32)


def classify_slots(row: dict[str, Any]) -> tuple[dict[str, bool], dict[str, bool]]:
    checkout_recoverable = present(row, "checkout_locator") and present(row, "before_anchor")
    patch_recoverable = present(row, "patch_payload") or present(row, "trace_payload")
    verifier_recoverable = present(row, "verifier_identity")
    before_after_recoverable = (
        verifier_recoverable and present(row, "before_observation") and present(row, "after_observation")
    )
    state_after_recoverable = (
        present(row, "after_anchor")
        or normalize_result(scalar(row, PRIVATE_COLUMN_CANDIDATES["result"])) != "unknown_or_other"
    )
    stop_continue_present = present(row, "stop_continue")
    recoverable = {
        "checkout_before_anchor": checkout_recoverable,
        "patch_application_proof": patch_recoverable,
        "same_verifier_before_after": before_after_recoverable,
        "causal_transition": patch_recoverable and before_after_recoverable,
        "state_after": state_after_recoverable,
        "stop_continue": stop_continue_present,
    }
    proof_present = {
        "checkout_before_anchor": False,
        "patch_application_proof": False,
        "same_verifier_before_after": False,
        "causal_transition": False,
        "state_after": False,
        "stop_continue": stop_continue_present,
    }
    return recoverable, proof_present


def inspect_samples(plan: list[dict[str, Any]], sample_indexes: list[int]) -> tuple[dict[str, Any], str]:
    try:
        import pyarrow.parquet as pq  # type: ignore
    except Exception as exc:
        return {}, f"pyarrow_unavailable_{type(exc).__name__}"

    by_file = locate_samples(plan, sample_indexes)
    proof_slot_structural_inspection_counts: Counter[str] = Counter()
    proof_slot_present_counts: Counter[str] = Counter()
    proof_slot_recoverable_counts: Counter[str] = Counter()
    proof_slot_missing_counts: Counter[str] = Counter()
    transition_status_counts: Counter[str] = Counter()
    drop_reason_counts: Counter[str] = Counter()
    dedupe_status_counts: Counter[str] = Counter()
    schema_signature_counts: Counter[str] = Counter()
    config_bucket_counts: Counter[str] = Counter()
    private_hashes: list[str] = []
    rows_read = 0
    shard_count_read = 0

    try:
        for file_index, local_indexes in by_file.items():
            item = plan[file_index]
            columns = selected_columns(item["schema_names"])
            schema_signature_counts[str(item["schema_signature"])] += len(local_indexes)
            config_bucket_counts[str(item["config_bucket_hash"])] += len(local_indexes)
            if not columns:
                for slot in PROOF_SLOTS:
                    proof_slot_structural_inspection_counts[slot] += len(local_indexes)
                    proof_slot_missing_counts[slot] += len(local_indexes)
                    drop_reason_counts[f"{slot}_structure_unavailable"] += len(local_indexes)
                transition_status_counts["blocked_no_safe_structure_columns"] += len(local_indexes)
                continue

            parquet = pq.ParquetFile(item["path"])
            by_group = locate_row_groups(item, local_indexes)
            for row_group, row_indexes in by_group.items():
                table = parquet.read_row_group(row_group, columns=columns)
                data = table.to_pydict()
                shard_count_read += 1
                for row_index in row_indexes:
                    row = {name: values[row_index] for name, values in data.items()}
                    rows_read += 1
                    row_hash = private_row_hash(row)
                    if row_hash in private_hashes:
                        dedupe_status_counts["duplicate_in_private_sample"] += 1
                    else:
                        dedupe_status_counts["survivor"] += 1
                        private_hashes.append(row_hash)

                    slot_recoverable, slot_present = classify_slots(row)
                    all_structural_slots = all(slot_recoverable.values())
                    result_status = normalize_result(scalar(row, PRIVATE_COLUMN_CANDIDATES["result"]))
                    transition_status_counts[f"source_result_{result_status}"] += 1
                    transition_status_counts[
                        "all_structural_slots_recoverable" if all_structural_slots else "structural_slots_incomplete"
                    ] += 1
                    transition_status_counts["execution_not_attempted_safety_boundary"] += 1

                    for slot in PROOF_SLOTS:
                        proof_slot_structural_inspection_counts[slot] += 1
                        if slot_present[slot]:
                            proof_slot_present_counts[slot] += 1
                        else:
                            proof_slot_missing_counts[slot] += 1
                        if slot_recoverable[slot]:
                            proof_slot_recoverable_counts[slot] += 1
                        else:
                            drop_reason_counts[f"{slot}_structure_missing"] += 1

                    drop_reason_counts["checkout_execution_not_attempted"] += 1
                    drop_reason_counts["patch_application_execution_not_attempted"] += 1
                    drop_reason_counts["verifier_execution_not_attempted"] += 1
                    drop_reason_counts["causal_transition_not_execution_verified"] += 1
                    drop_reason_counts["level3_blocked_without_same_verifier_replay"] += 1
                    drop_reason_counts["patch_trace_blocked_without_patch_apply_log"] += 1
                    drop_reason_counts["training_gate_forced_closed"] += 1
                    drop_reason_counts["admission_gate_forced_closed"] += 1
    except Exception as exc:
        return {}, f"private_structure_read_blocked_{type(exc).__name__}"

    return (
        {
            "rows_read": rows_read,
            "sample_shard_count_read": shard_count_read,
            "sample_set_hash": stable_hash({"seed": DETERMINISTIC_SEED, "private_hashes": sorted(private_hashes)}, 32),
            "dedupe_ledger_hash": stable_hash(sorted(private_hashes), 32),
            "dedupe_survivors": dedupe_status_counts["survivor"],
            "proof_slot_structural_inspection_counts": complete_slot_counts(proof_slot_structural_inspection_counts),
            "proof_slot_present_counts": complete_slot_counts(proof_slot_present_counts),
            "proof_slot_recoverable_counts": complete_slot_counts(proof_slot_recoverable_counts),
            "proof_slot_missing_counts": complete_slot_counts(proof_slot_missing_counts),
            "transition_status_counts": dict(sorted(transition_status_counts.items())),
            "drop_reason_counts": dict(sorted(drop_reason_counts.items())),
            "dedupe_status_counts": dict(sorted(dedupe_status_counts.items())),
            "sample_schema_signature_counts": dict(sorted(schema_signature_counts.items())),
            "hashed_config_bucket_counts": dict(sorted(config_bucket_counts.items())),
        },
        "",
    )


def source_summary(stage12431: dict[str, Any], stage12432: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage12431": {
            "source_stage_hash": stable_hash(stage12431.get("stage"), 16),
            "source_record_type_hash": stable_hash(stage12431.get("record_type"), 16),
            "source_decision_hash": stable_hash(stage12431.get("decision"), 16),
            "guardrail_scan_passed": stage12431.get("guardrail_scan_passed", False),
            "training_allowed": stage12431.get("training_allowed", False),
            "admission_allowed": stage12431.get("admission_allowed", False),
            "admitted_rows": safe_int(stage12431.get("admitted_rows")),
            "emitted_rows": safe_int(stage12431.get("emitted_rows")),
            "countable_new_rows": safe_int(stage12431.get("countable_new_rows")),
            "raw_leak_count": safe_int(stage12431.get("raw_leak_count")),
            "overclaim_count": safe_int(stage12431.get("overclaim_count")),
            "metadata_candidate_supply_rows": safe_int(stage12431.get("metadata_candidate_supply_rows")),
            "private_sampled_rows": safe_int(stage12431.get("private_sampled_rows")),
            "private_dedupe_survivors": safe_int(stage12431.get("private_dedupe_survivors")),
            "sample_set_hash": stage12431.get("sample_set_hash", "missing"),
        },
        "stage12432": {
            "source_stage_hash": stable_hash(stage12432.get("stage"), 16),
            "source_record_type_hash": stable_hash(stage12432.get("record_type"), 16),
            "source_decision_hash": stable_hash(stage12432.get("decision"), 16),
            "guardrail_scan_passed": stage12432.get("guardrail_scan_passed", False),
            "training_allowed": stage12432.get("training_allowed", False),
            "admission_allowed": stage12432.get("admission_allowed", False),
            "admitted_rows": safe_int(stage12432.get("admitted_rows")),
            "emitted_rows": safe_int(stage12432.get("emitted_rows")),
            "countable_new_rows": safe_int(stage12432.get("countable_new_rows")),
            "raw_leak_count": safe_int(stage12432.get("raw_leak_count")),
            "overclaim_count": safe_int(stage12432.get("overclaim_count")),
            "metadata_candidate_supply_rows": safe_int(stage12432.get("metadata_candidate_supply_rows")),
            "private_sampled_rows": safe_int(stage12432.get("private_sampled_rows")),
            "private_dedupe_survivors": safe_int(stage12432.get("private_dedupe_survivors")),
        },
    }


def source_preconditions(stage12431: dict[str, Any], stage12432: dict[str, Any]) -> dict[str, bool]:
    return {
        "stage12431_summary_present": bool(stage12431),
        "stage12432_summary_present": bool(stage12432),
        "stage12431_guardrail_clean": stage12431.get("guardrail_scan_passed") is True
        and safe_int(stage12431.get("raw_leak_count")) == 0
        and safe_int(stage12431.get("overclaim_count")) == 0,
        "stage12432_guardrail_clean": stage12432.get("guardrail_scan_passed") is True
        and safe_int(stage12432.get("raw_leak_count")) == 0
        and safe_int(stage12432.get("overclaim_count")) == 0,
        "stage12431_closed_gates": stage12431.get("training_allowed") is False
        and stage12431.get("admission_allowed") is False
        and safe_int(stage12431.get("admitted_rows")) == 0
        and safe_int(stage12431.get("emitted_rows")) == 0
        and safe_int(stage12431.get("countable_new_rows")) == 0,
        "stage12432_closed_gates": stage12432.get("training_allowed") is False
        and stage12432.get("admission_allowed") is False
        and safe_int(stage12432.get("admitted_rows")) == 0
        and safe_int(stage12432.get("emitted_rows")) == 0
        and safe_int(stage12432.get("countable_new_rows")) == 0,
        "stage12431_expected_sample": safe_int(stage12431.get("private_sampled_rows")) == REQUESTED_SAMPLE_SIZE
        and safe_int(stage12431.get("private_dedupe_survivors")) == REQUESTED_SAMPLE_SIZE,
        "stage12432_expected_scope": safe_int(stage12432.get("private_sampled_rows")) == REQUESTED_SAMPLE_SIZE
        and safe_int(stage12432.get("private_dedupe_survivors")) == REQUESTED_SAMPLE_SIZE,
        "stage12432_required_slots_present": stage12432.get("required_private_reconstruction_tasks") == PROOF_SLOTS,
    }


def zero_slot_counts(count: int = 0) -> dict[str, int]:
    return {slot: count for slot in PROOF_SLOTS}


def complete_slot_counts(counter: Counter[str]) -> dict[str, int]:
    return {slot: safe_int(counter.get(slot)) for slot in PROOF_SLOTS}


def fail_closed_summary(
    *,
    stage12431: dict[str, Any],
    stage12432: dict[str, Any],
    blocker: str,
    metadata_rows: int = 0,
    parquet_shards: int = 0,
    dataset_root_hit_count: int = 0,
    schema_signature_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    accounting = {
        "metadata_candidate_supply_rows": CANDIDATE_SUPPLY_ROWS,
        "private_sampled_rows": 0,
        "private_dedupe_survivors": 0,
        "proof_complete_candidates": 0,
        "level3_candidates_after_private_replay": 0,
        "patch_trace_candidates": 0,
        "admitted_rows": 0,
    }
    return {
        **ZERO_COUNTERS,
        "stage": STAGE,
        "record_type": "open_swe_pilot_100_private_proof_slot_runner_postrun_v1",
        "decision": "fail_closed_private_proof_slot_runner_blocked_no_rows_admitted",
        "blocker": blocker,
        "blocker_detail_hash": stable_hash(blocker, 24),
        "claim_boundary": "aggregate_only_private_structure_no_execution_no_admission",
        "input_summary_hashes": {
            "stage12431_summary": file_hash(STAGE12431_SUMMARY),
            "stage12432_summary": file_hash(STAGE12432_SUMMARY),
        },
        "input_summary_presence": {
            "stage12431_summary": STAGE12431_SUMMARY.exists(),
            "stage12432_summary": STAGE12432_SUMMARY.exists(),
        },
        "source_summary": source_summary(stage12431, stage12432),
        "source_preconditions": source_preconditions(stage12431, stage12432),
        "metadata_candidate_supply_rows": CANDIDATE_SUPPLY_ROWS,
        "metadata_rows_observed_private": metadata_rows,
        "private_sampled_rows": 0,
        "private_dedupe_survivors": 0,
        "dataset_root_hit_count": dataset_root_hit_count,
        "parquet_shard_count": parquet_shards,
        "schema_signature_counts": schema_signature_counts or {},
        "sample_seed_hash": stable_hash({"seed": DETERMINISTIC_SEED}, 16),
        "sample_set_hash": "missing",
        "stage12431_sample_set_hash_match": False,
        "private_rows_inspected": 0,
        "sample_shard_count_read": 0,
        "actual_execution_attempt_counts": zero_slot_counts(),
        "proof_slot_structural_inspection_counts": zero_slot_counts(),
        "proof_slot_present_counts": zero_slot_counts(),
        "proof_slot_recoverable_counts": zero_slot_counts(),
        "proof_slot_missing_counts": zero_slot_counts(),
        "proof_complete_candidates": 0,
        "level3_candidates_after_private_replay": 0,
        "patch_trace_candidates": 0,
        "transition_status_counts": {f"blocked_{blocker}": 1},
        "drop_reason_counts": {
            blocker: 1,
            "no_rows_admitted": 1,
            "training_gate_forced_closed": 1,
            "admission_gate_forced_closed": 1,
        },
        "dedupe_status_counts": {"blocked_before_private_sample": 1},
        "accounting_table": accounting,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "next_stage_recommendation": "resolve_private_runner_blocker_then_rerun_aggregate_only_postrun",
    }


def build_summary(stage12431: dict[str, Any], stage12432: dict[str, Any]) -> dict[str, Any]:
    preconditions = source_preconditions(stage12431, stage12432)
    if not all(preconditions.values()):
        return fail_closed_summary(
            stage12431=stage12431,
            stage12432=stage12432,
            blocker="prior_stage_precondition_failed",
        )

    roots = probe_roots()
    files = iter_parquet_files(roots)
    if not roots:
        return fail_closed_summary(
            stage12431=stage12431,
            stage12432=stage12432,
            blocker="dataset_root_unavailable",
        )
    if not files:
        return fail_closed_summary(
            stage12431=stage12431,
            stage12432=stage12432,
            blocker="local_open_swe_parquet_unavailable",
            dataset_root_hit_count=len(roots),
        )

    plan, blocker = parquet_plan(files)
    schema_counts: Counter[str] = Counter(str(item.get("schema_signature")) for item in plan)
    metadata_rows = sum(safe_int(item.get("row_count")) for item in plan)
    if blocker:
        return fail_closed_summary(
            stage12431=stage12431,
            stage12432=stage12432,
            blocker=blocker,
            metadata_rows=metadata_rows,
            parquet_shards=len(plan),
            dataset_root_hit_count=len(roots),
            schema_signature_counts=dict(sorted(schema_counts.items())),
        )
    if metadata_rows < REQUESTED_SAMPLE_SIZE:
        return fail_closed_summary(
            stage12431=stage12431,
            stage12432=stage12432,
            blocker="requested_sample_count_unavailable",
            metadata_rows=metadata_rows,
            parquet_shards=len(plan),
            dataset_root_hit_count=len(roots),
            schema_signature_counts=dict(sorted(schema_counts.items())),
        )

    sample_indexes = sorted(random.Random(DETERMINISTIC_SEED).sample(range(metadata_rows), REQUESTED_SAMPLE_SIZE))
    sample, blocker = inspect_samples(plan, sample_indexes)
    if blocker:
        return fail_closed_summary(
            stage12431=stage12431,
            stage12432=stage12432,
            blocker=blocker,
            metadata_rows=metadata_rows,
            parquet_shards=len(plan),
            dataset_root_hit_count=len(roots),
            schema_signature_counts=dict(sorted(schema_counts.items())),
        )

    sampled = safe_int(sample.get("rows_read"))
    dedupe_survivors = safe_int(sample.get("dedupe_survivors"))
    if sampled != REQUESTED_SAMPLE_SIZE:
        return fail_closed_summary(
            stage12431=stage12431,
            stage12432=stage12432,
            blocker="private_sample_size_mismatch",
            metadata_rows=metadata_rows,
            parquet_shards=len(plan),
            dataset_root_hit_count=len(roots),
            schema_signature_counts=dict(sorted(schema_counts.items())),
        )

    proof_complete = 0
    level3_candidates_after_private_replay = 0
    patch_trace_candidates = 0
    drop_reasons = Counter(sample.get("drop_reason_counts", {}))
    if metadata_rows != CANDIDATE_SUPPLY_ROWS:
        drop_reasons["metadata_candidate_supply_mismatch_with_prior_stage"] += 1

    accounting = {
        "metadata_candidate_supply_rows": CANDIDATE_SUPPLY_ROWS,
        "private_sampled_rows": sampled,
        "private_dedupe_survivors": dedupe_survivors,
        "proof_complete_candidates": proof_complete,
        "level3_candidates_after_private_replay": level3_candidates_after_private_replay,
        "patch_trace_candidates": patch_trace_candidates,
        "admitted_rows": 0,
    }
    return {
        **ZERO_COUNTERS,
        "stage": STAGE,
        "record_type": "open_swe_pilot_100_private_proof_slot_runner_postrun_v1",
        "decision": "fail_closed_private_structure_only_proof_slot_postrun_no_rows_admitted",
        "blocker": "actual_checkout_patch_verifier_execution_not_attempted_safety_boundary",
        "claim_boundary": "aggregate_only_private_structure_no_execution_no_admission",
        "input_summary_hashes": {
            "stage12431_summary": file_hash(STAGE12431_SUMMARY),
            "stage12432_summary": file_hash(STAGE12432_SUMMARY),
        },
        "input_summary_presence": {
            "stage12431_summary": STAGE12431_SUMMARY.exists(),
            "stage12432_summary": STAGE12432_SUMMARY.exists(),
        },
        "source_summary": source_summary(stage12431, stage12432),
        "source_preconditions": source_preconditions(stage12431, stage12432),
        "metadata_candidate_supply_rows": CANDIDATE_SUPPLY_ROWS,
        "metadata_rows_observed_private": metadata_rows,
        "private_sampled_rows": sampled,
        "private_dedupe_survivors": dedupe_survivors,
        "dataset_root_hit_count": len(roots),
        "parquet_shard_count": len(plan),
        "schema_signature_counts": dict(sorted(schema_counts.items())),
        "sample_seed_hash": stable_hash({"seed": DETERMINISTIC_SEED}, 16),
        "sample_set_hash": sample.get("sample_set_hash"),
        "stage12431_sample_set_hash_match": sample.get("sample_set_hash") == stage12431.get("sample_set_hash"),
        "dedupe_ledger_hash": sample.get("dedupe_ledger_hash"),
        "private_rows_inspected": sampled,
        "sample_shard_count_read": safe_int(sample.get("sample_shard_count_read")),
        "proof_slot_inspection_mode": "private_structure_classification_only_no_execution",
        "actual_execution_attempt_counts": {
            "checkout_before_anchor": 0,
            "patch_application_proof": 0,
            "same_verifier_before_after": 0,
            "causal_transition": 0,
            "state_after": 0,
            "stop_continue": 0
        },
        "proof_slot_attempted_counts": sample.get("proof_slot_structural_inspection_counts", zero_slot_counts()),
        "proof_slot_structural_inspection_counts": sample.get("proof_slot_structural_inspection_counts", zero_slot_counts()),
        "proof_slot_present_counts": sample.get("proof_slot_present_counts", zero_slot_counts()),
        "proof_slot_recoverable_counts": sample.get("proof_slot_recoverable_counts", zero_slot_counts()),
        "proof_slot_missing_counts": sample.get("proof_slot_missing_counts", zero_slot_counts()),
        "proof_complete_candidates": proof_complete,
        "level3_candidates_after_private_replay": level3_candidates_after_private_replay,
        "patch_trace_candidates": patch_trace_candidates,
        "transition_status_counts": sample.get("transition_status_counts", {}),
        "drop_reason_counts": dict(sorted(drop_reasons.items())),
        "dedupe_status_counts": sample.get("dedupe_status_counts", {}),
        "sample_schema_signature_counts": sample.get("sample_schema_signature_counts", {}),
        "hashed_config_bucket_counts": sample.get("hashed_config_bucket_counts", {}),
        "accounting_table": accounting,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "next_stage_recommendation": (
            "keep_admission_closed_until_a_safe_private_replay_runner_records_same_verifier_before_after_and_patch_apply_proof"
        ),
    }


def overclaim_count(value: dict[str, Any]) -> int:
    hits = 0
    payload = json.dumps(value, sort_keys=True)
    for match in OVERCLAIM_RE.finditer(payload):
        start = max(0, match.start() - 96)
        end = min(len(payload), match.end() + 96)
        if not ALLOWED_OVERCLAIM_CONTEXT_RE.search(payload[start:end]):
            hits += 1
    return hits


def guardrail_scan(value: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(value, sort_keys=True)
    raw_matches = FORBIDDEN_TEXT_RE.findall(payload)
    zero_counter_failures = [
        key for key, expected in ZERO_COUNTERS.items() if value.get(key) != expected
    ]
    raw_policy_failures = [
        key
        for key, expected in RAW_CONTENT_POLICY.items()
        if value.get("raw_content_policy", {}).get(key) != expected
    ]
    claims = overclaim_count(value)
    issues = (
        (["forbidden_raw_text_pattern_detected"] if raw_matches else [])
        + [f"nonzero_or_true_zero_counter:{key}" for key in zero_counter_failures]
        + [f"raw_content_policy_failure:{key}" for key in raw_policy_failures]
        + (["unsupported_positive_claim_detected"] if claims else [])
    )
    return {
        "scan_passed": not issues,
        "raw_leak_count": len(raw_matches),
        "overclaim_count": claims,
        "issue_count": len(issues),
        "issues": issues,
        "zero_counter_keys_checked": sorted(ZERO_COUNTERS),
        "raw_content_policy_keys_checked": sorted(RAW_CONTENT_POLICY),
        "scan_scope": "public_summary_payload_after_private_value_suppression",
    }


def finalize(summary: dict[str, Any]) -> dict[str, Any]:
    pre_scan = guardrail_scan(summary)
    summary["guardrail_scan"] = pre_scan
    summary["guardrail_scan_passed"] = pre_scan["scan_passed"]
    summary["raw_leak_count"] = pre_scan["raw_leak_count"]
    summary["overclaim_count"] = pre_scan["overclaim_count"]
    summary["summary_hash"] = stable_hash({k: v for k, v in summary.items() if k != "summary_hash"})
    post_scan = guardrail_scan(summary)
    summary["guardrail_scan"] = post_scan
    summary["guardrail_scan_passed"] = post_scan["scan_passed"]
    summary["raw_leak_count"] = post_scan["raw_leak_count"]
    summary["overclaim_count"] = post_scan["overclaim_count"]
    summary["summary_hash"] = stable_hash({k: v for k, v in summary.items() if k != "summary_hash"})
    return summary


def main() -> None:
    stage12431 = read_json(STAGE12431_SUMMARY)
    stage12432 = read_json(STAGE12432_SUMMARY)
    summary = finalize(build_summary(stage12431, stage12432))

    write_json(OUT / f"{STAGE}.json", summary)
    write_json(OUT / "summary.json", summary)
    write_json(OUT / "guardrail_scan.json", summary["guardrail_scan"])
    write_json(OUT / "proof_slot_aggregate_counts.json", {
        "proof_slot_inspection_mode": summary["proof_slot_inspection_mode"]
        if "proof_slot_inspection_mode" in summary
        else "blocked_before_private_structure_classification",
        "proof_slot_structural_inspection_counts": summary["proof_slot_structural_inspection_counts"],
        "proof_slot_present_counts": summary["proof_slot_present_counts"],
        "proof_slot_recoverable_counts": summary["proof_slot_recoverable_counts"],
        "proof_slot_missing_counts": summary["proof_slot_missing_counts"],
        "proof_complete_candidates": summary["proof_complete_candidates"],
        "level3_candidates_after_private_replay": summary["level3_candidates_after_private_replay"],
        "patch_trace_candidates": summary["patch_trace_candidates"],
    })
    write_json(SUMMARY, summary)

    if not summary["guardrail_scan_passed"]:
        raise SystemExit(f"guardrail scan failed with {summary['guardrail_scan']['issue_count']} issues")

    print(
        json.dumps(
            {
                "stage": STAGE,
                "decision": summary["decision"],
                "training_allowed": summary["training_allowed"],
                "admission_allowed": summary["admission_allowed"],
                "metadata_candidate_supply_rows": summary["metadata_candidate_supply_rows"],
                "private_sampled_rows": summary["private_sampled_rows"],
                "private_dedupe_survivors": summary["private_dedupe_survivors"],
                "proof_complete_candidates": summary["proof_complete_candidates"],
                "level3_candidates_after_private_replay": summary["level3_candidates_after_private_replay"],
                "patch_trace_candidates": summary["patch_trace_candidates"],
                "admitted_rows": summary["admitted_rows"],
                "emitted_rows": summary["emitted_rows"],
                "countable_new_rows": summary["countable_new_rows"],
                "guardrail_scan_passed": summary["guardrail_scan_passed"],
                "raw_leak_count": summary["raw_leak_count"],
                "overclaim_count": summary["overclaim_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
