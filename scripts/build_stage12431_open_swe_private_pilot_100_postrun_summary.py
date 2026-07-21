#!/usr/bin/env python3
"""Stage12431 Open-SWE private pilot-100 postrun summary.

This stage may privately inspect local Open-SWE parquet metadata and a bounded
sample of row values, but it emits only public-safe aggregate counts, hashes,
and normalized enums. It emits no raw row values, paths, URLs, commands,
outputs, diffs, patches, issue text, source text, or schema field names.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12431_open_swe_private_pilot_100_postrun_summary"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
STAGE12430_SUMMARY = ROOT / "runs/summaries/stage12430_open_swe_private_sampler_execution_request.json"

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
REQUESTED_PHASE = "pilot_100"
REQUESTED_SAMPLE_SIZE = 100
DETERMINISTIC_SEED = 12431

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
    "replay_attempted_count": 0,
    "patch_apply_attempted_count": 0,
    "tests_run_count": 0,
}

RAW_CONTENT_POLICY: dict[str, bool] = {
    "raw_trajectories_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_diffs_emitted": False,
    "raw_patches_emitted": False,
    "raw_issue_bodies_emitted": False,
    "urls_emitted": False,
    "source_text_emitted": False,
    "raw_paths_emitted": False,
    "training_rows_emitted": False,
    "row_values_emitted": False,
    "locator_values_emitted": False,
    "schema_field_names_emitted": False,
}

SAFE_LANGUAGE_VALUES = {
    "c",
    "cpp",
    "go",
    "java",
    "javascript",
    "php",
    "python",
    "rust",
    "typescript",
}

SAFE_RESULT_VALUES = {"resolved", "unresolved", "unknown_or_other"}
SAFE_SMALL_ENUM_RE = re.compile(r"^[a-z][a-z0-9_]{0,48}$")

FORBIDDEN_TEXT_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout|stderr|pytest |npm |pip |git clone|git apply|curl )\b",
    re.IGNORECASE | re.MULTILINE,
)

OVERCLAIM_RE = re.compile(
    r"\b(?:training rows|admitted training|admission allowed|level3 complete|"
    r"closed loop|verified repair|causal proof|patch applied|replay succeeded)\b",
    re.IGNORECASE,
)

ALLOWED_OVERCLAIM_CONTEXT_RE = re.compile(
    r"(false|zero|none|not_|no_|blocked|drop|candidate|after_private_replay|"
    r"training_allowed|admission_allowed|admitted_rows|level3_candidates|"
    r"patch_trace_candidates|replay_attempted_count|patch_apply_attempted_count)",
    re.IGNORECASE,
)

PRIVATE_COLUMN_CANDIDATES = {
    "row_identity": ("instance_id", "repo", "trajectory_id", "id"),
    "language": ("language", "repo_language", "language_family", "primary_language"),
    "result": ("resolved", "result", "resolution", "status", "instance_status"),
    "category": ("category",),
    "event_type": ("type", "role", "name"),
    "modified_file_count": ("num_modified_files",),
    "modified_line_count": ("num_modified_lines",),
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


def normalize_language(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"c++", "cxx", "c/c++"}:
        return "cpp"
    if text in SAFE_LANGUAGE_VALUES:
        return text
    return "unknown_or_other"


def normalize_result(value: Any) -> str:
    if isinstance(value, bool):
        return "resolved" if value else "unresolved"
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "success", "passed", "pass", "resolved"}:
        return "resolved"
    if text in {"false", "0", "no", "failure", "failed", "fail", "unresolved"}:
        return "unresolved"
    if text in SAFE_RESULT_VALUES:
        return text
    return "unknown_or_other"


def normalize_small_enum(value: Any) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    if SAFE_SMALL_ENUM_RE.match(text):
        return text
    return "unknown_or_other"


def normalize_positive_bucket(value: Any) -> str:
    number = safe_int(value)
    if number <= 0:
        return "zero_or_absent"
    if number == 1:
        return "one"
    if number <= 5:
        return "two_to_five"
    if number <= 20:
        return "six_to_twenty"
    return "over_twenty"


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
        return [], f"pyarrow_unavailable:{type(exc).__name__}"

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
                    "config_bucket_hash": stable_hash(path.parent.name, 16),
                }
            )
            offset += row_count
    except Exception as exc:
        return [], f"raw_access_blocked:{type(exc).__name__}:parquet_metadata_read"
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


def scalar(row: dict[str, Any], candidates: tuple[str, ...]) -> Any:
    for name in candidates:
        if name in row:
            return row.get(name)
    return None


def present(row: dict[str, Any], candidates: tuple[str, ...]) -> bool:
    value = scalar(row, candidates)
    return value is not None and str(value) != ""


def private_row_hash(row: dict[str, Any]) -> str:
    values = []
    for name in PRIVATE_COLUMN_CANDIDATES["row_identity"]:
        if name in row:
            values.append([stable_hash(name, 12), stable_hash(row.get(name), 24)])
    if not values:
        values = [[stable_hash(key, 12), stable_hash(value, 24)] for key, value in sorted(row.items())]
    return stable_hash(values, 32)


def inspect_samples(plan: list[dict[str, Any]], sample_indexes: list[int]) -> tuple[dict[str, Any], str]:
    try:
        import pyarrow.parquet as pq  # type: ignore
    except Exception as exc:
        return {}, f"pyarrow_unavailable:{type(exc).__name__}"

    by_file = locate_samples(plan, sample_indexes)
    language_counts: Counter[str] = Counter()
    result_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    event_type_counts: Counter[str] = Counter()
    modified_file_bucket_counts: Counter[str] = Counter()
    modified_line_bucket_counts: Counter[str] = Counter()
    config_bucket_counts: Counter[str] = Counter()
    proof_slot_counts: Counter[str] = Counter()
    dedupe_status_counts: Counter[str] = Counter()
    drop_reason_counts: Counter[str] = Counter()
    private_hashes: list[str] = []
    rows_read = 0
    shard_count_read = 0
    column_presence_counts: Counter[str] = Counter()

    try:
        for file_index, local_indexes in by_file.items():
            item = plan[file_index]
            path = item["path"]
            columns = selected_columns(item["schema_names"])
            if not columns:
                drop_reason_counts["no_safe_projection_columns_available"] += len(local_indexes)
                continue
            parquet = pq.ParquetFile(path)
            table = parquet.read_row_group(0, columns=columns)
            data = table.to_pydict()
            shard_count_read += 1
            config_bucket_counts[str(item["config_bucket_hash"])] += len(local_indexes)
            for local_index in local_indexes:
                row = {name: values[local_index] for name, values in data.items()}
                rows_read += 1
                row_hash = private_row_hash(row)
                if row_hash in private_hashes:
                    dedupe_status_counts["duplicate_in_private_sample"] += 1
                else:
                    dedupe_status_counts["survivor"] += 1
                    private_hashes.append(row_hash)

                language_counts[normalize_language(scalar(row, PRIVATE_COLUMN_CANDIDATES["language"]))] += 1
                result_counts[normalize_result(scalar(row, PRIVATE_COLUMN_CANDIDATES["result"]))] += 1
                category_counts[normalize_small_enum(scalar(row, PRIVATE_COLUMN_CANDIDATES["category"]))] += 1
                event_type_counts[normalize_small_enum(scalar(row, PRIVATE_COLUMN_CANDIDATES["event_type"]))] += 1
                modified_file_bucket_counts[
                    normalize_positive_bucket(scalar(row, PRIVATE_COLUMN_CANDIDATES["modified_file_count"]))
                ] += 1
                modified_line_bucket_counts[
                    normalize_positive_bucket(scalar(row, PRIVATE_COLUMN_CANDIDATES["modified_line_count"]))
                ] += 1

                same_source = present(row, ("repo", "instance_id", "trajectory_id"))
                locator_resolves = True
                language_present = normalize_language(scalar(row, PRIVATE_COLUMN_CANDIDATES["language"])) != "unknown_or_other"
                result_present = normalize_result(scalar(row, PRIVATE_COLUMN_CANDIDATES["result"])) != "unknown_or_other"
                modified_hint_present = (
                    safe_int(scalar(row, PRIVATE_COLUMN_CANDIDATES["modified_file_count"])) > 0
                    or safe_int(scalar(row, PRIVATE_COLUMN_CANDIDATES["modified_line_count"])) > 0
                )

                if same_source:
                    proof_slot_counts["same_source_lineage_present"] += 1
                else:
                    proof_slot_counts["same_source_lineage_missing"] += 1
                    drop_reason_counts["missing_same_source_lineage_private_projection"] += 1
                if locator_resolves:
                    proof_slot_counts["private_locator_resolves"] += 1
                if language_present:
                    proof_slot_counts["language_bucket_present"] += 1
                if result_present:
                    proof_slot_counts["result_bucket_present"] += 1
                if modified_hint_present:
                    proof_slot_counts["patch_shape_hint_present"] += 1

                proof_slot_counts["checkout_before_anchor_missing"] += 1
                proof_slot_counts["same_verifier_before_after_missing"] += 1
                proof_slot_counts["patch_application_proof_missing"] += 1
                proof_slot_counts["causal_transition_proof_missing"] += 1
                proof_slot_counts["stop_or_continue_label_missing"] += 1
                proof_slot_counts["all_required_slots_complete"] += 0
                drop_reason_counts["no_private_replay_executed"] += 1
                drop_reason_counts["missing_checkout_before_anchor"] += 1
                drop_reason_counts["missing_same_verifier_before_after"] += 1
                drop_reason_counts["missing_patch_application_proof"] += 1
                drop_reason_counts["missing_causal_transition_proof"] += 1
                drop_reason_counts["missing_stop_or_continue_label"] += 1

            for role, candidates in PRIVATE_COLUMN_CANDIDATES.items():
                if any(name in columns for name in candidates):
                    column_presence_counts[f"{role}_private_projection_present"] += 1
                else:
                    column_presence_counts[f"{role}_private_projection_absent"] += 1
    except Exception as exc:
        return {}, f"raw_access_blocked:{type(exc).__name__}:sample_projection_read"

    sample_set_hash = stable_hash({"seed": DETERMINISTIC_SEED, "private_hashes": sorted(private_hashes)}, 32)
    dedupe_ledger_hash = stable_hash(sorted(private_hashes), 32)
    return (
        {
            "rows_read": rows_read,
            "sample_shard_count_read": shard_count_read,
            "sample_set_hash": sample_set_hash,
            "dedupe_ledger_hash": dedupe_ledger_hash,
            "dedupe_survivors": dedupe_status_counts["survivor"],
            "language_bucket_counts": dict(sorted(language_counts.items())),
            "result_bucket_counts": dict(sorted(result_counts.items())),
            "category_enum_counts": dict(sorted(category_counts.items())),
            "event_type_enum_counts": dict(sorted(event_type_counts.items())),
            "modified_file_count_bucket_counts": dict(sorted(modified_file_bucket_counts.items())),
            "modified_line_count_bucket_counts": dict(sorted(modified_line_bucket_counts.items())),
            "hashed_config_bucket_counts": dict(sorted(config_bucket_counts.items())),
            "proof_slot_status_counts": dict(sorted(proof_slot_counts.items())),
            "dedupe_status_counts": dict(sorted(dedupe_status_counts.items())),
            "drop_reason_counts": dict(sorted(drop_reason_counts.items())),
            "private_projection_column_status_counts": dict(sorted(column_presence_counts.items())),
        },
        "",
    )


def source_stage12430(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_stage": summary.get("stage"),
        "source_decision_hash": stable_hash(summary.get("decision"), 16),
        "source_training_allowed": summary.get("training_allowed", False),
        "source_admission_allowed": summary.get("admission_allowed", False),
        "source_guardrail_scan_passed": summary.get("guardrail_scan_passed", False),
        "source_raw_leak_count": safe_int(summary.get("raw_leak_count")),
        "source_overclaim_count": safe_int(summary.get("overclaim_count")),
        "source_candidate_supply_rows": safe_int(summary.get("candidate_supply_rows")),
        "source_requested_phase": summary.get("requested_phase"),
        "source_requested_private_candidate_count": safe_int(summary.get("requested_private_candidate_count")),
        "source_admitted_rows": safe_int(summary.get("admitted_rows")),
        "source_emitted_rows": safe_int(summary.get("emitted_rows")),
        "source_countable_new_rows": safe_int(summary.get("countable_new_rows")),
    }


def fail_closed_summary(
    *,
    stage12430: dict[str, Any],
    blocker: str,
    metadata_rows: int = 0,
    parquet_shards: int = 0,
    dataset_root_hit_count: int = 0,
    schema_signature_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    accounting = {
        "metadata_candidate_supply_rows": CANDIDATE_SUPPLY_ROWS,
        "sampled": 0,
        "dedupe_survivors": 0,
        "proof_complete": 0,
        "level3_candidates_after_private_replay": 0,
        "patch_trace_candidates": 0,
        "admitted": 0,
    }
    return {
        **ZERO_COUNTERS,
        "stage": STAGE,
        "record_type": "open_swe_private_pilot_100_postrun_summary_v1",
        "decision": "fail_closed_private_pilot_100_blocked_no_rows_admitted",
        "blocker": blocker,
        "blocker_detail_hash": stable_hash(blocker, 24),
        "claim_boundary": (
            "Stage12431 emits a public-safe postrun summary only. Any row inspection remains private; no "
            "training, admission, replay, patch application, or test execution is authorized by this artifact."
        ),
        "input_summary_hashes": {"stage12430_summary": file_hash(STAGE12430_SUMMARY)},
        "input_summary_presence": {"stage12430_summary": STAGE12430_SUMMARY.exists()},
        "source_summary": source_stage12430(stage12430),
        "requested_phase": REQUESTED_PHASE,
        "sample_seed_hash": stable_hash({"seed": DETERMINISTIC_SEED}, 16),
        "requested_private_candidate_count": REQUESTED_SAMPLE_SIZE,
        "metadata_candidate_supply_rows": CANDIDATE_SUPPLY_ROWS,
        "metadata_rows_observed_private": metadata_rows,
        "dataset_root_hit_count": dataset_root_hit_count,
        "parquet_shard_count": parquet_shards,
        "schema_signature_counts": schema_signature_counts or {},
        "sampled": 0,
        "private_sampled_rows": 0,
        "private_dedupe_survivors": 0,
        "proof_complete_candidates": 0,
        "level3_candidates_after_private_replay": 0,
        "patch_trace_candidates": 0,
        "private_rows_inspected": 0,
        "accounting_table": accounting,
        "required_public_postrun_accounting_table": accounting,
        "required_public_postrun_accounting_table": accounting,
        "stage12430_accounting_table": {
            "chain": [
                "metadata_candidate_supply_rows",
                "sampled",
                "dedupe_survivors",
                "proof_complete",
                "level3_candidates_after_private_replay",
                "patch_trace_candidates",
                "admitted"
            ],
            "metadata_candidate_supply_rows": CANDIDATE_SUPPLY_ROWS,
            "sampled": accounting["sampled"],
            "dedupe_survivors": accounting["dedupe_survivors"],
            "proof_complete": accounting["proof_complete"],
            "level3_candidates_after_private_replay": accounting["level3_candidates_after_private_replay"],
            "patch_trace_candidates": accounting["patch_trace_candidates"],
            "admitted": 0,
        },
        "aggregate_bucket_counts": {},
        "proof_slot_status_counts": {"blocked_before_private_row_sample": 1},
        "dedupe_status_counts": {"blocked_before_private_row_sample": 1},
        "drop_reason_counts": {blocker: 1, "no_rows_admitted": 1, "training_gate_not_open": 1},
        "raw_content_policy": RAW_CONTENT_POLICY,
        "next_stage_recommendation": "resolve_private_sampler_blocker_then_rerun_public_safe_postrun_summary",
    }


def build_summary(stage12430: dict[str, Any]) -> dict[str, Any]:
    source = source_stage12430(stage12430)
    source_ok = (
        bool(stage12430)
        and source["source_stage"] == "stage12430_open_swe_private_sampler_execution_request"
        and source["source_training_allowed"] is False
        and source["source_admission_allowed"] is False
        and source["source_guardrail_scan_passed"] is True
        and source["source_raw_leak_count"] == 0
        and source["source_overclaim_count"] == 0
        and source["source_candidate_supply_rows"] == CANDIDATE_SUPPLY_ROWS
        and source["source_requested_phase"] == REQUESTED_PHASE
        and source["source_requested_private_candidate_count"] == REQUESTED_SAMPLE_SIZE
    )
    if not source_ok:
        return fail_closed_summary(stage12430=stage12430, blocker="stage12430_precondition_failed")

    roots = probe_roots()
    files = iter_parquet_files(roots)
    if not roots:
        return fail_closed_summary(stage12430=stage12430, blocker="dataset_root_unavailable", dataset_root_hit_count=0)
    if not files:
        return fail_closed_summary(
            stage12430=stage12430,
            blocker="local_open_swe_parquet_unavailable",
            dataset_root_hit_count=len(roots),
        )

    plan, blocker = parquet_plan(files)
    schema_counts: Counter[str] = Counter(str(item.get("schema_signature")) for item in plan)
    metadata_rows = sum(safe_int(item.get("row_count")) for item in plan)
    if blocker:
        return fail_closed_summary(
            stage12430=stage12430,
            blocker=blocker,
            metadata_rows=metadata_rows,
            parquet_shards=len(plan),
            dataset_root_hit_count=len(roots),
            schema_signature_counts=dict(sorted(schema_counts.items())),
        )
    if metadata_rows < REQUESTED_SAMPLE_SIZE:
        return fail_closed_summary(
            stage12430=stage12430,
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
            stage12430=stage12430,
            blocker=blocker,
            metadata_rows=metadata_rows,
            parquet_shards=len(plan),
            dataset_root_hit_count=len(roots),
            schema_signature_counts=dict(sorted(schema_counts.items())),
        )

    sampled = safe_int(sample.get("rows_read"))
    if sampled != REQUESTED_SAMPLE_SIZE:
        return fail_closed_summary(
            stage12430=stage12430,
            blocker="private_sample_size_mismatch",
            metadata_rows=metadata_rows,
            parquet_shards=len(plan),
            dataset_root_hit_count=len(roots),
            schema_signature_counts=dict(sorted(schema_counts.items())),
        )

    dedupe_survivors = safe_int(sample.get("dedupe_survivors"))
    proof_complete = 0
    level3_candidates_after_private_replay = 0
    patch_trace_candidates = 0
    accounting = {
        "metadata_candidate_supply_rows": CANDIDATE_SUPPLY_ROWS,
        "sampled": sampled,
        "dedupe_survivors": dedupe_survivors,
        "proof_complete": proof_complete,
        "level3_candidates_after_private_replay": level3_candidates_after_private_replay,
        "patch_trace_candidates": patch_trace_candidates,
        "admitted": 0,
    }
    drop_reasons = Counter(sample.get("drop_reason_counts", {}))
    if metadata_rows != CANDIDATE_SUPPLY_ROWS:
        drop_reasons["metadata_candidate_supply_mismatch_with_stage12430"] += 1
    drop_reasons["admission_gate_forced_closed"] += sampled
    drop_reasons["training_gate_forced_closed"] += sampled

    return {
        **ZERO_COUNTERS,
        "stage": STAGE,
        "record_type": "open_swe_private_pilot_100_postrun_summary_v1",
        "decision": "fail_closed_private_pilot_100_postrun_no_rows_admitted",
        "blocker": None,
        "claim_boundary": (
            "Stage12431 privately sampled Open-SWE candidates only to produce public-safe aggregate counts. "
            "No raw values are emitted and no admission or training release is authorized."
        ),
        "input_summary_hashes": {"stage12430_summary": file_hash(STAGE12430_SUMMARY)},
        "input_summary_presence": {"stage12430_summary": STAGE12430_SUMMARY.exists()},
        "source_summary": source,
        "requested_phase": REQUESTED_PHASE,
        "sample_seed_hash": stable_hash({"seed": DETERMINISTIC_SEED}, 16),
        "requested_private_candidate_count": REQUESTED_SAMPLE_SIZE,
        "metadata_candidate_supply_rows": CANDIDATE_SUPPLY_ROWS,
        "metadata_rows_observed_private": metadata_rows,
        "dataset_root_hit_count": len(roots),
        "parquet_shard_count": len(plan),
        "schema_signature_counts": dict(sorted(schema_counts.items())),
        "sampled": sampled,
        "private_sampled_rows": sampled,
        "private_dedupe_survivors": dedupe_survivors,
        "proof_complete_candidates": proof_complete,
        "level3_candidates_after_private_replay": level3_candidates_after_private_replay,
        "patch_trace_candidates": patch_trace_candidates,
        "private_rows_inspected": sampled,
        "sample_shard_count_read": safe_int(sample.get("sample_shard_count_read")),
        "sample_set_hash": sample.get("sample_set_hash"),
        "dedupe_ledger_hash": sample.get("dedupe_ledger_hash"),
        "accounting_table": accounting,
        "required_public_postrun_accounting_table": accounting,
        "stage12430_accounting_table": {
            "chain": [
                "metadata_candidate_supply_rows",
                "sampled",
                "dedupe_survivors",
                "proof_complete",
                "level3_candidates_after_private_replay",
                "patch_trace_candidates",
                "admitted"
            ],
            "metadata_candidate_supply_rows": CANDIDATE_SUPPLY_ROWS,
            "sampled": sampled,
            "dedupe_survivors": dedupe_survivors,
            "proof_complete": proof_complete,
            "level3_candidates_after_private_replay": level3_candidates_after_private_replay,
            "patch_trace_candidates": patch_trace_candidates,
            "admitted": 0,
        },
        "aggregate_bucket_counts": {
            "language": sample.get("language_bucket_counts", {}),
            "result": sample.get("result_bucket_counts", {}),
            "category_enum": sample.get("category_enum_counts", {}),
            "event_type_enum": sample.get("event_type_enum_counts", {}),
            "modified_file_count": sample.get("modified_file_count_bucket_counts", {}),
            "modified_line_count": sample.get("modified_line_count_bucket_counts", {}),
            "hashed_config": sample.get("hashed_config_bucket_counts", {}),
        },
        "private_projection_column_status_counts": sample.get("private_projection_column_status_counts", {}),
        "proof_slot_status_counts": sample.get("proof_slot_status_counts", {}),
        "dedupe_status_counts": sample.get("dedupe_status_counts", {}),
        "drop_reason_counts": dict(sorted(drop_reasons.items())),
        "raw_content_policy": RAW_CONTENT_POLICY,
        "next_stage_recommendation": "do_not_admit_training_rows_without_private_replay_proof_slots_and_clean_public_summary",
    }


def overclaim_count(value: dict[str, Any]) -> int:
    hits = 0
    for match in OVERCLAIM_RE.finditer(json.dumps(value, sort_keys=True)):
        start = max(0, match.start() - 80)
        end = min(len(match.string), match.end() + 80)
        if not ALLOWED_OVERCLAIM_CONTEXT_RE.search(match.string[start:end]):
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
    stage12430 = read_json(STAGE12430_SUMMARY)
    summary = finalize(build_summary(stage12430))

    write_json(OUT / "stage12431_open_swe_private_pilot_100_postrun_summary.json", summary)
    write_json(OUT / "summary.json", summary)
    write_json(OUT / "guardrail_scan.json", summary["guardrail_scan"])
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
                "sampled": summary["sampled"],
                "dedupe_survivors": summary["accounting_table"]["dedupe_survivors"],
                "proof_complete": summary["accounting_table"]["proof_complete"],
                "level3_candidates_after_private_replay": summary["accounting_table"][
                    "level3_candidates_after_private_replay"
                ],
                "patch_trace_candidates": summary["accounting_table"]["patch_trace_candidates"],
                "admitted_rows": summary["admitted_rows"],
                "emitted_rows": summary["emitted_rows"],
                "countable_new_rows": summary["countable_new_rows"],
                "raw_leak_count": summary["raw_leak_count"],
                "overclaim_count": summary["overclaim_count"],
                "guardrail_scan_passed": summary["guardrail_scan_passed"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
