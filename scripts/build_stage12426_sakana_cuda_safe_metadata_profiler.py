#!/usr/bin/env python3
"""Stage12426 Sakana CUDA safe metadata profiler.

This stage inspects only local dataset availability, file metadata, schemas,
and counts for SakanaAI--AI-CUDA-Engineer-Archive. It emits no training rows
and does not copy raw code, commands, outputs, profiler text, diagnostics,
locators, URLs, diffs, or source text into artifacts.
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
STAGE = "stage12426_sakana_cuda_safe_metadata_profiler"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
STAGE12425_SUMMARY = ROOT / "runs/summaries/stage12425_source_adapter_feasibility_miner.json"

DATASET_ID = "SakanaAI--AI-CUDA-Engineer-Archive"
DATASET_FAMILY = "sakana_cuda_engineer_archive"

DATASET_ROOT_PROBES = [
    Path("/arxiv/datasets/SakanaAI--AI-CUDA-Engineer-Archive"),
    Path("/data/.cache/huggingface/hub/datasets--SakanaAI--AI-CUDA-Engineer-Archive"),
    Path("/data/datasets/SakanaAI--AI-CUDA-Engineer-Archive"),
    Path("/data/datasets/sakana_ai_cuda_engineer_archive"),
    ROOT / "datasets/SakanaAI--AI-CUDA-Engineer-Archive",
    ROOT / "data/SakanaAI--AI-CUDA-Engineer-Archive",
]

SAFE_EXTENSIONS = {
    ".arrow",
    ".json",
    ".jsonl",
    ".parquet",
}

ZERO_COUNTERS = {
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
    "raw_code_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_profiler_text_emitted": False,
    "raw_error_text_emitted": False,
    "raw_paths_emitted": False,
    "urls_emitted": False,
    "diffs_emitted": False,
    "source_text_emitted": False,
    "training_rows_emitted": False,
    "row_values_emitted": False,
    "locator_values_emitted": False,
    "schema_field_names_emitted": False,
}

FORBIDDEN_TEXT_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){1,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|nvprof |nsys |ncu |cuda-gdb |ptxas fatal)\b",
    re.IGNORECASE | re.MULTILINE,
)

RAWISH_KEY_RE = re.compile(
    r"(command|cmd|output|stdout|stderr|profiler|profile_text|error|traceback|path|url|diff|patch|source|code|content)",
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
    field_type_counts: Counter[str] = Counter()
    field_hashes: list[str] = []
    column_count = len(schema.names)
    for index in range(column_count):
        column = schema.column(index)
        field_type_counts[str(column.physical_type)] += 1
        field_hashes.append(stable_hash({"name": column.name, "type": str(column.physical_type)}, 16))
    return {
        "metadata_status": "metadata_read",
        "candidate_count": safe_int(meta.num_rows),
        "row_group_count": safe_int(meta.num_row_groups),
        "column_count": safe_int(column_count),
        "schema_field_hashes": sorted(field_hashes),
        "schema_physical_type_counts": dict(sorted(field_type_counts.items())),
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
        "record_batch_count": batch_count,
        "column_count": len(schema),
        "schema_field_hashes": sorted(field_hashes),
        "schema_type_counts": dict(sorted(field_type_counts.items())),
    }


def json_metadata(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"metadata_status": "json_metadata_unreadable", "candidate_count": 0}
    if isinstance(value, list):
        return {
            "metadata_status": "json_container_count_only",
            "candidate_count": len(value),
            "container_type": "list",
            "schema_status": "not_read_to_avoid_raw_row_copy",
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
        }
    return {
        "metadata_status": "json_scalar_ignored",
        "candidate_count": 0,
        "container_type": type(value).__name__,
    }


def metadata_for_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    base = {
        "dataset_family": DATASET_FAMILY,
        "file_ref_hash": stable_hash(str(path), 24),
        "content_sha256_24": file_hash(path),
        "extension_class": suffix.lstrip(".") or "none",
        "size_bytes": path.stat().st_size,
    }
    if suffix == ".parquet":
        detail = parquet_metadata(path)
    elif suffix == ".arrow":
        detail = arrow_metadata(path)
    elif suffix == ".jsonl":
        detail = {
            "metadata_status": "jsonl_line_count_only",
            "candidate_count": line_count_without_parsing(path),
            "schema_status": "not_read_to_avoid_raw_row_copy",
        }
    elif suffix == ".json":
        detail = json_metadata(path)
    else:
        detail = {"metadata_status": "unsupported_extension_ignored", "candidate_count": 0}
    return {**base, **detail}


def build_fail_closed_profile(stage12425: dict[str, Any], roots: list[Path]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    file_profiles: list[dict[str, Any]] = []
    if roots:
        for root in roots:
            for path in iter_safe_metadata_files(root):
                file_profiles.append(metadata_for_file(path))

    candidate_count = sum(safe_int(item.get("candidate_count")) for item in file_profiles)
    extension_counts = Counter(str(item["extension_class"]) for item in file_profiles)
    status_counts = Counter(str(item.get("metadata_status")) for item in file_profiles)
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
            "no_raw_verifier_output_or_patch_lineage",
            "dedupe_required_before_any_future_admission",
            "local_rerun_required_before_any_future_training_support",
            "reject_performance_score_shortcut_without_verifier_interpretation",
            "reject_kernel_variant_overcount_without_root_task_collapse",
            "reject_broad_maintainer_claim_from_cuda_only_source",
        ]
    )

    profile = {
        **ZERO_COUNTERS,
        "stage": STAGE,
        "record_type": "sakana_cuda_safe_metadata_profile_v1",
        "decision": "fail_closed_safe_metadata_only_no_rows_admitted",
        "claim_boundary": (
            "Stage12426 profiles only dataset availability, metadata, schemas, and counts. "
            "It emits no training rows and copies no raw code, commands, outputs, diagnostics, "
            "locators, URLs, diffs, or source text."
        ),
        "source_adapter_id": "stage12426_sakana_cuda_metadata_only",
        "dataset_family": DATASET_FAMILY,
        "safe_dataset_root_label": DATASET_ID,
        "dataset_root_available": dataset_root_present,
        "safe_metadata_available": safe_metadata_available,
        "dataset_root_probe_count": len(DATASET_ROOT_PROBES),
        "dataset_root_hit_count": len(roots),
        "dataset_root_ref_hashes": sorted(stable_hash(str(path), 24) for path in roots),
        "metadata_file_count": len(file_profiles),
        "candidate_count": candidate_count if safe_metadata_available else 0,
        "candidate_count_is_admission": False,
        "candidate_count_is_training_rows": False,
        "extension_counts": dict(sorted(extension_counts.items())),
        "metadata_status_counts": dict(sorted(status_counts.items())),
        "schema_file_count": schema_file_count,
        "dataset_characterization": {
            "language_family": "cuda_c_cpp",
            "task_family": "verifier_performance_observation_metadata",
            "best_use": "auxiliary C++/CUDA verifier-observation support after private admission",
            "not_claimable_as": ["patch_trace", "level3_closed_loop", "level4_episode", "fail_to_pass_repair", "broad_multilingual_maintainer_progress"],
        },
        "language_task_characterization": {
            "language_family": "CUDA C/C++",
            "task_family": "verifier/performance observation metadata",
            "best_use": "support rows only after private admission, verifier anchoring, rerun or authoritative status extraction, and dedupe",
            "not_claimable_as": ["patch_trace", "level3_closed_loop", "fail_to_pass_repair"],
        },
        "candidate_safe_semantic_labels": [
            "cuda_c_cpp_verifier_performance_observation_support",
            "positive_verifier_observation_candidate",
            "negative_or_error_verifier_observation_candidate",
            "metadata_only_candidate",
        ],
        "exact_admission_caveats_for_verifier_observation_rows": [
            "metadata-only profile is not training data",
            "no admission gate was run",
            "local rerun or authoritative verifier status classes are required before any future training-support claim",
            "same-source lineage hashes are required",
            "dedupe against existing countable ledgers is required",
            "repo, task, variant, and source-family caps are required",
            "guardrail scan over rendered safe artifacts is required",
            "raw verifier output, raw code, and patch lineage were not emitted",
            "missing proof slots include local_rerun, patch_lineage, before_after_causal_repair_transition, and stop_continue",
            "candidate counts are not admitted rows and are not training rows",
        ],
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
        "source_controls": {
            "stage12425_present": bool(stage12425),
            "stage12425_decision": stage12425.get("decision"),
            "stage12425_training_allowed": stage12425.get("training_allowed", False),
            "stage12425_highest_priority_adapter": stage12425.get("highest_priority_adapter"),
            "stage12425_guardrail_scan_passed": stage12425.get("guardrail_scan_passed"),
        },
        "admission_path": {
            "stage12427": {
                "recommended_action": "open_swe_safe_metadata_profiler",
                "admission_allowed": False,
                "purpose": "parallel safe metadata profile for transition/replay candidate supply",
            },
            "stage12428": {
                "recommended_action": "raw_private_admission_packet_materialization_after_hydration",
                "admission_allowed": False,
                "required_before_admission": [
                    "private raw reviewer packet only",
                    "local rerun or authoritative verifier status classes",
                    "same-source lineage hashes",
                    "dedupe against existing countable ledgers",
                    "repo and source-family caps",
                    "guardrail scan over rendered safe artifacts",
                ],
            },
        },
        "next_stage_recommendation": "stage12427_open_swe_safe_metadata_profiler_then_stage12428_sakana_cuda_private_admission_packet_path",
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
    profile, file_profiles = build_fail_closed_profile(stage12425, roots)

    guardrail = guardrail_scan({"profile": profile, "file_profiles": file_profiles})
    profile["guardrail_scan_passed"] = guardrail["scan_passed"]
    profile["raw_leak_count"] = guardrail["issue_count"]
    profile["overclaim_count"] = 0
    profile["summary_hash"] = stable_hash({k: v for k, v in profile.items() if k != "summary_hash"})

    profile_path = OUT / "sakana_cuda_safe_metadata_profile.json"
    file_profiles_path = OUT / "safe_metadata_file_profiles.jsonl"
    guardrail_path = OUT / "guardrail_scan.json"
    local_summary_path = OUT / "summary.json"

    write_json(profile_path, profile)
    write_jsonl(file_profiles_path, file_profiles)
    write_json(local_summary_path, profile)
    write_json(SUMMARY, profile)

    write_json(guardrail_path, guardrail)
    if not guardrail["scan_passed"]:
        raise SystemExit(f"guardrail scan failed with {guardrail['issue_count']} issues")

    print(
        json.dumps(
            {
                "stage": STAGE,
                "decision": profile["decision"],
                "candidate_count": profile["candidate_count"],
                "training_allowed": False,
                "guardrail_scan_passed": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
