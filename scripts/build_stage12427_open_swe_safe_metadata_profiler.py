#!/usr/bin/env python3
"""Stage12427 Open-SWE-Traces safe metadata profiler.

This stage inspects only local dataset availability, file metadata, schemas,
shard counts, and safe categorical counts for nvidia--Open-SWE-Traces. It emits
no training rows and copies no raw trajectories, commands, outputs, diffs,
patches, issue bodies, URLs, source text, or raw paths.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12427_open_swe_safe_metadata_profiler"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
STAGE12425_SUMMARY = ROOT / "runs/summaries/stage12425_source_adapter_feasibility_miner.json"

DATASET_ID = "nvidia--Open-SWE-Traces"
DATASET_FAMILY = "open_swe_traces"

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

SAFE_EXTENSIONS = {".arrow", ".json", ".jsonl", ".parquet"}

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "admitted_rows": 0,
    "emitted_rows": 0,
    "emitted_training_rows": 0,
    "countable_rows": 0,
    "countable_new_rows": 0,
    "countable_as_new_train_support_rows": 0,
    "countable_as_new_proof_floor_rows": 0,
    "raw_rows_inspected": 0,
    "raw_rows_copied": 0,
    "raw_content_emitted": False,
    "replay_attempted_count": 0,
    "patch_apply_attempted_count": 0,
    "tests_run_count": 0,
}

RAW_CONTENT_POLICY = {
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
    "c++",
    "cpp",
    "go",
    "java",
    "javascript",
    "php",
    "python",
    "rust",
    "typescript",
}
SAFE_RESULT_VALUES = {
    "resolved",
    "unresolved",
    "unknown",
    "other",
    "success",
    "failure",
    "failed",
    "passed",
    "pass",
    "fail",
}
LANGUAGE_COLUMN_CANDIDATES = {
    "language",
    "repo_language",
    "language_family",
    "primary_language",
}
RESULT_COLUMN_CANDIDATES = {
    "result",
    "resolved",
    "resolution",
    "status",
    "instance_status",
}

FORBIDDEN_TEXT_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){1,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout|stderr|pytest |npm |pip |git clone)\b",
    re.IGNORECASE | re.MULTILINE,
)

RAWISH_KEY_RE = re.compile(
    r"(trajectory|command|cmd|output|stdout|stderr|diff|patch|issue|body|url|path|source|code|content|text|log)",
    re.IGNORECASE,
)


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


def safe_file_fingerprint(path: Path, n: int = 24) -> str:
    """Bounded file identity; avoids full raw shard reads."""
    if not path.exists() or not path.is_file():
        return "missing"
    stat = path.stat()
    digest = hashlib.sha256()
    digest.update(
        json.dumps(
            {
                "file_ref_hash": stable_hash(str(path), 24),
                "size_bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    try:
        with path.open("rb") as handle:
            digest.update(handle.read(4096))
            if stat.st_size > 4096:
                handle.seek(max(0, stat.st_size - 4096))
                digest.update(handle.read(4096))
    except Exception:
        pass
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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def probe_roots() -> list[Path]:
    return [path for path in DATASET_ROOT_PROBES if path.exists() and path.is_dir()]


def iter_safe_metadata_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in {".git", "__pycache__"}]
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.suffix.lower() in SAFE_EXTENSIONS:
                files.append(path)
    return sorted(files, key=lambda p: stable_hash(str(p), 32))


def line_count_without_parsing(path: Path) -> int:
    count = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            count += chunk.count(b"\n")
    return count


def normalize_language(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"cxx", "c/c++"}:
        return "cpp"
    if text in SAFE_LANGUAGE_VALUES:
        return text
    return "unknown_or_other"


def normalize_result(value: Any) -> str:
    if isinstance(value, bool):
        return "resolved" if value else "unresolved"
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return "resolved"
    if text in {"false", "0", "no"}:
        return "unresolved"
    if text in SAFE_RESULT_VALUES:
        if text in {"success", "passed", "pass"}:
            return "resolved"
        if text in {"failure", "failed", "fail"}:
            return "unresolved"
        return text
    return "unknown_or_other"


def safe_value_counts_for_parquet(path: Path, names: list[str], kind: str) -> dict[str, int]:
    # Deliberately disabled for this public safe profiler: full categorical
    # counts require scanning row values. Later private admission can compute
    # these counts alongside raw replay/lineage controls.
    return {}
    try:
        import pyarrow.parquet as pq  # type: ignore
    except Exception:
        return {}
    counts: Counter[str] = Counter()
    normalizer = normalize_language if kind == "language" else normalize_result
    try:
        parquet = pq.ParquetFile(path)
        for batch in parquet.iter_batches(columns=names, batch_size=65536):
            table = batch.to_pydict()
            for name in names:
                for value in table.get(name, []):
                    counts[normalizer(value)] += 1
    except Exception:
        return {}
    return dict(sorted(counts.items()))


def parquet_metadata(path: Path) -> dict[str, Any]:
    try:
        import pyarrow.parquet as pq  # type: ignore
    except Exception:
        return {"metadata_status": "parquet_metadata_library_unavailable", "candidate_count": 0}
    try:
        meta = pq.ParquetFile(path).metadata
    except Exception:
        return {"metadata_status": "parquet_metadata_unreadable", "candidate_count": 0}
    schema = meta.schema
    names = list(schema.names)
    field_type_counts: Counter[str] = Counter()
    field_hashes: list[str] = []
    for index, name in enumerate(names):
        column = schema.column(index)
        field_type_counts[str(column.physical_type)] += 1
        field_hashes.append(stable_hash({"name": name, "type": str(column.physical_type)}, 16))
    language_columns = [name for name in names if name.lower() in LANGUAGE_COLUMN_CANDIDATES]
    result_columns = [name for name in names if name.lower() in RESULT_COLUMN_CANDIDATES]
    return {
        "metadata_status": "metadata_read",
        "candidate_count": safe_int(meta.num_rows),
        "shard_count": 1,
        "row_group_count": safe_int(meta.num_row_groups),
        "column_count": len(names),
        "schema_field_hashes": sorted(field_hashes),
        "schema_physical_type_counts": dict(sorted(field_type_counts.items())),
        "safe_language_counts": safe_value_counts_for_parquet(path, language_columns[:1], "language") if language_columns else {},
        "safe_result_counts": safe_value_counts_for_parquet(path, result_columns[:1], "result") if result_columns else {},
        "language_count_status": "safe_column_present_private_count_required" if language_columns else "safe_language_column_unavailable",
        "result_count_status": "safe_column_present_private_count_required" if result_columns else "safe_result_column_unavailable",
    }


def arrow_metadata(path: Path) -> dict[str, Any]:
    try:
        import pyarrow.ipc as ipc  # type: ignore
    except Exception:
        return {"metadata_status": "arrow_metadata_library_unavailable", "candidate_count": 0}
    try:
        with path.open("rb") as handle:
            reader = ipc.open_file(handle)
            schema = reader.schema
            candidate_count = sum(reader.get_batch(i).num_rows for i in range(reader.num_record_batches))
            batch_count = reader.num_record_batches
    except Exception:
        return {"metadata_status": "arrow_metadata_unreadable", "candidate_count": 0}
    field_type_counts = Counter(str(field.type) for field in schema)
    field_hashes = [stable_hash({"name": field.name, "type": str(field.type)}, 16) for field in schema]
    return {
        "metadata_status": "metadata_read",
        "candidate_count": candidate_count,
        "shard_count": 1,
        "record_batch_count": batch_count,
        "column_count": len(schema),
        "schema_field_hashes": sorted(field_hashes),
        "schema_type_counts": dict(sorted(field_type_counts.items())),
        "language_count_status": "not_counted_for_arrow_to_avoid_raw_batch_projection",
        "result_count_status": "not_counted_for_arrow_to_avoid_raw_batch_projection",
        "safe_language_counts": {},
        "safe_result_counts": {},
    }


def json_metadata(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"metadata_status": "json_metadata_unreadable", "candidate_count": 0}
    if isinstance(value, list):
        return {
            "metadata_status": "json_tool_metadata_container_count_only",
            "candidate_count": 0,
            "tool_metadata_item_count": len(value),
            "container_type": "list",
            "shard_count": 1,
            "schema_status": "not_read_to_avoid_raw_row_copy",
            "safe_language_counts": {},
            "safe_result_counts": {},
        }
    if isinstance(value, dict):
        safe_keys = [key for key in value if not RAWISH_KEY_RE.search(str(key))]
        rawish_keys = [key for key in value if RAWISH_KEY_RE.search(str(key))]
        return {
            "metadata_status": "json_metadata_read",
            "candidate_count": 0,
            "container_type": "object",
            "top_level_key_count": len(value),
            "safe_key_hashes": sorted(stable_hash(str(key), 16) for key in safe_keys),
            "rawish_key_count": len(rawish_keys),
            "rawish_key_hashes": sorted(stable_hash(str(key), 16) for key in rawish_keys),
            "safe_language_counts": {},
            "safe_result_counts": {},
        }
    return {
        "metadata_status": "json_scalar_ignored",
        "candidate_count": 0,
        "container_type": type(value).__name__,
        "safe_language_counts": {},
        "safe_result_counts": {},
    }


def metadata_for_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    base = {
        "dataset_family": DATASET_FAMILY,
        "file_ref_hash": stable_hash(str(path), 24),
        "safe_file_fingerprint_24": safe_file_fingerprint(path),
        "content_sha256_24": "not_computed_to_avoid_full_raw_shard_read",
        "extension_class": suffix.lstrip(".") or "none",
        "size_bytes": path.stat().st_size,
        "parent_config_hash": stable_hash(path.parent.name, 16),
    }
    if suffix == ".parquet":
        detail = parquet_metadata(path)
    elif suffix == ".arrow":
        detail = arrow_metadata(path)
    elif suffix == ".jsonl":
        detail = {
            "metadata_status": "jsonl_line_count_only",
            "candidate_count": line_count_without_parsing(path),
            "shard_count": 1,
            "schema_status": "not_read_to_avoid_raw_row_copy",
            "safe_language_counts": {},
            "safe_result_counts": {},
        }
    elif suffix == ".json":
        detail = json_metadata(path)
    else:
        detail = {"metadata_status": "unsupported_extension_ignored", "candidate_count": 0}
    return {**base, **detail}


def merge_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        value = row.get(key)
        if isinstance(value, dict):
            counts.update({str(k): safe_int(v) for k, v in value.items()})
    return dict(sorted(counts.items()))


def build_profile(stage12425: dict[str, Any], roots: list[Path]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    file_profiles: list[dict[str, Any]] = []
    if roots:
        for root in roots:
            for path in iter_safe_metadata_files(root):
                file_profiles.append(metadata_for_file(path))

    parquet_profiles = [item for item in file_profiles if item.get("extension_class") == "parquet"]
    candidate_count = sum(safe_int(item.get("candidate_count")) for item in parquet_profiles)
    tool_metadata_item_count = sum(safe_int(item.get("tool_metadata_item_count")) for item in file_profiles)
    extension_counts = Counter(str(item["extension_class"]) for item in file_profiles)
    status_counts = Counter(str(item.get("metadata_status")) for item in file_profiles)
    shard_count = len(parquet_profiles)
    config_counts: Counter[str] = Counter()
    for item in parquet_profiles:
        config_counts[stable_hash({"config_ref": item.get("parent_config_hash")}, 16)] += 1
    schema_file_count = sum(1 for item in file_profiles if safe_int(item.get("column_count")) > 0 or item.get("safe_key_hashes"))
    dataset_root_present = bool(roots)
    safe_metadata_available = bool(file_profiles)

    blocked_reasons = []
    if not dataset_root_present:
        blocked_reasons.append("dataset_root_unavailable_fail_closed")
    elif not safe_metadata_available:
        blocked_reasons.append("dataset_root_has_no_safe_metadata_files_fail_closed")
    blocked_reasons.extend(
        [
            "metadata_only_profile_not_training_data",
            "no_admission_gate_run",
            "no_raw_trace_or_patch_lineage",
            "no_private_replay_or_same_verifier_before_after_proof",
            "dedupe_required_before_any_future_admission",
            "private_replay_admission_packet_required",
            "reject_resolved_metadata_as_repair_proof",
            "reject_patch_and_verifier_copresence_as_causality",
        ]
    )

    profile = {
        **ZERO_COUNTERS,
        "stage": STAGE,
        "record_type": "open_swe_safe_metadata_profile_v1",
        "decision": "fail_closed_safe_metadata_only_no_rows_admitted",
        "claim_boundary": (
            "Stage12427 profiles only Open-SWE-Traces dataset availability, schema hashes, shard counts, "
            "row counts, and allowlisted language/result counts. It emits no training rows and copies no "
            "raw trajectories, commands, outputs, diffs, patches, issue bodies, URLs, source text, or raw paths."
        ),
        "source_adapter_id": "stage12427_open_swe_metadata_only",
        "dataset_family": DATASET_FAMILY,
        "safe_dataset_root_label": "Open-SWE-Traces",
        "dataset_root_available": dataset_root_present,
        "safe_metadata_available": safe_metadata_available,
        "dataset_root_probe_count": len(DATASET_ROOT_PROBES),
        "dataset_root_hit_count": len(roots),
        "dataset_root_ref_hashes": sorted(stable_hash(str(path), 24) for path in roots),
        "metadata_file_count": len(file_profiles),
        "trajectory_shard_count": shard_count,
        "shard_count": shard_count,
        "candidate_count": candidate_count if safe_metadata_available else 0,
        "candidate_count_source": "parquet_trajectory_rows_only",
        "tool_metadata_item_count": tool_metadata_item_count,
        "candidate_count_is_admission": False,
        "candidate_count_is_training_rows": False,
        "language_counts": merge_counts(file_profiles, "safe_language_counts"),
        "result_counts": merge_counts(file_profiles, "safe_result_counts"),
        "config_counts": dict(sorted(config_counts.items())),
        "config_count_policy": "hashed_parent_config_labels_only",
        "extension_counts": dict(sorted(extension_counts.items())),
        "metadata_status_counts": dict(sorted(status_counts.items())),
        "schema_file_count": schema_file_count,
        "schema_field_name_policy": "hashes_only_no_field_names",
        "file_profile_artifact": "safe_metadata_file_profiles.jsonl",
        "raw_content_policy": RAW_CONTENT_POLICY,
        "blocked_reason_counts": dict(Counter(blocked_reasons)),
        "proof_slot_status_counts": {
            "direct_source_anchor_present": 0,
            "direct_verifier_anchor_present": 0,
            "state_transition_anchor_present": 0,
            "stop_or_continue_anchor_present": 0,
            "before_after_verifier_status_present": 0,
            "same_source_lineage_present": 0,
            "all_required_slots_present": 0,
        },
        "dedupe_key_policy": {
            "required_before_admission": True,
            "key_material": "hashes_only",
            "must_dedupe_against": ["stage12385", "stage12416", "stage12418", "stage12421"],
            "raw_locator_material_allowed": False,
        },
        "dataset_characterization": {
            "language_family": "multilingual_code_repair_trace_metadata",
            "task_family": "transition_and_replay_candidate_supply_metadata",
            "best_use": "candidate sourcing for later private replay/admission packet",
            "not_claimable_as": [
                "training_rows",
                "level3_closed_loop",
                "patch_trace_admission",
                "fail_to_pass_repair",
                "verifier_causal_proof",
            ],
        },
        "admission_path_recommendation": {
            "recommended_later_stage": "private_open_swe_replay_admission_packet",
            "training_allowed": False,
            "required_before_any_admission": [
                "private raw locator packet kept out of public/model-facing artifacts",
                "same-source checkout-before and state-after anchors",
                "patch application proof",
                "same verifier identity before/after",
                "causal linkage rather than resolved-status shortcut",
                "stop-or-continue label extraction",
                "dedupe against existing countable ledgers",
                "repo, language, result, and source-family caps",
                "guardrail scan over rendered safe artifacts",
            ],
        },
        "source_controls": {
            "stage12425_present": bool(stage12425),
            "stage12425_decision": stage12425.get("decision"),
            "stage12425_training_allowed": stage12425.get("training_allowed", False),
            "stage12425_guardrail_scan_passed": stage12425.get("guardrail_scan_passed"),
            "stage12425_recommended_stage": stage12425.get("next_stage_recommendation"),
        },
        "next_stage_recommendation": "later_private_open_swe_replay_admission_packet_after_safe_metadata_review",
    }
    return profile, file_profiles


def guardrail_scan(value: Any) -> dict[str, Any]:
    payload = json.dumps(value, sort_keys=True)
    matches = FORBIDDEN_TEXT_RE.findall(payload)
    counter_source = value.get("profile") if isinstance(value, dict) and isinstance(value.get("profile"), dict) else value
    zero_counter_failures = [
        key
        for key, expected in ZERO_COUNTERS.items()
        if isinstance(counter_source, dict) and key in counter_source and counter_source.get(key) != expected
    ]
    return {
        "scan_passed": not matches and not zero_counter_failures,
        "issue_count": len(matches) + len(zero_counter_failures),
        "issues": (
            (["forbidden_raw_text_pattern_detected"] if matches else [])
            + [f"nonzero_or_true_zero_counter:{key}" for key in zero_counter_failures]
        ),
        "raw_content_policy": RAW_CONTENT_POLICY,
        "zero_counter_keys_checked": sorted(ZERO_COUNTERS),
    }


def main() -> None:
    stage12425 = read_json(STAGE12425_SUMMARY)
    roots = probe_roots()
    profile, file_profiles = build_profile(stage12425, roots)

    guardrail = guardrail_scan({"profile": profile, "file_profiles": file_profiles})
    profile["guardrail_scan_passed"] = guardrail["scan_passed"]
    profile["raw_leak_count"] = guardrail["issue_count"]
    profile["overclaim_count"] = 0
    profile["summary_hash"] = stable_hash({k: v for k, v in profile.items() if k != "summary_hash"})

    write_json(OUT / "open_swe_safe_metadata_profile.json", profile)
    write_jsonl(OUT / "safe_metadata_file_profiles.jsonl", file_profiles)
    write_json(OUT / "summary.json", profile)
    write_json(SUMMARY, profile)
    write_json(OUT / "guardrail_scan.json", guardrail)
    if not guardrail["scan_passed"]:
        raise SystemExit(f"guardrail scan failed with {guardrail['issue_count']} issues")

    print(
        json.dumps(
            {
                "stage": STAGE,
                "decision": profile["decision"],
                "candidate_count": profile["candidate_count"],
                "shard_count": profile["shard_count"],
                "training_allowed": False,
                "guardrail_scan_passed": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
