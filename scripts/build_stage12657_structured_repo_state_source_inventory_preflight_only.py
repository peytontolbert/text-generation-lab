#!/usr/bin/env python3
# Inventory candidate sources for the Structured Repo State curriculum layer without admitting rows.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12657_structured_repo_state_source_inventory_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12656_SUMMARY = ROOT / "runs/summaries/stage12656_repo_code_symbol_binding_shortcut_resilience_preflight_only.json"
EXPECTED_STAGE12656_SUMMARY_SHA256 = "d23629f1c35bc9ed82cbb808196b2d2518a1b4a0cfaeb981a4de8aa4857c3b1a"

CANDIDATE_SOURCES = (
    {
        "source_id": "stage10516_root_state_compiler_roots",
        "path": ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl",
        "family": "long_context_root_state",
        "layer_role": "candidate_state_roots",
        "expected_rows": 784,
    },
    {
        "source_id": "stage10516_root_state_compiler_multitarget_rows",
        "path": ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_multitarget_rows.jsonl",
        "family": "long_context_root_state",
        "layer_role": "candidate_state_targets",
        "expected_rows": 2407,
    },
    {
        "source_id": "stage10516_root_state_compiler_causal_states",
        "path": ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_causal_states.jsonl",
        "family": "long_context_root_state",
        "layer_role": "candidate_visible_state_packets",
        "expected_rows": 784,
    },
    {
        "source_id": "stage9916_hardened_weighted_structured_state",
        "path": ROOT / "runs/local/artifacts/stage9916_v27_hardened_edit_localization_weighted_compiler_refresh/compiled/structured_state.jsonl",
        "family": "legacy_structured_execution",
        "layer_role": "mixed_later_layer_reference_only",
        "expected_rows": 396,
    },
    {
        "source_id": "stage12266_episode_graph_review_results",
        "path": ROOT / "runs/local/artifacts/stage12266_capped_episode_graph_review_result_ingest/materialized_review_results.jsonl",
        "family": "episode_graph_review",
        "layer_role": "review_reference_only",
        "expected_rows": 25,
    },
    {
        "source_id": "stage12213_strict_fail_current_state_records",
        "path": ROOT / "runs/local/artifacts/stage12213_strict_fail_current_state_level3_converter/strict_fail_current_state_level3_records.jsonl",
        "family": "level3_transition_reference",
        "layer_role": "later_transition_reference_only",
        "expected_rows": 2,
    },
)

FALSE_FIELDS = (
    "implementation_ready",
    "dataset_rows_admitted",
    "structured_repo_state_rows_admitted",
    "stage12658_allowed",
    "training_admission_allowed",
    "training_allowed",
    "training_run_allowed",
    "training_admitted",
    "strict_eval_admitted",
    "sealed_eval_admitted",
    "strict_eval_eligible",
    "sealed_eval_eligible",
    "gpu_allocation_requested",
    "cuda2_training_allowed",
    "vm_runner_execution_allowed",
    "runtime_authorized",
    "replay_trustworthy",
    "level_3_materialized",
    "model_execution_authorized_next",
    "optimizer_step_authorized",
    "source_emission_authorized",
    "body_emission_authorized",
)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/",
    "/arxiv/",
    "model_input",
    "target_text",
    "input_text",
    "state_before",
    "state_after",
    "source_log_path",
    "source_lineage",
    "source_row_id",
    "jsonl",
)

LEAK_MARKERS = ("/data/", "/arxiv/", "\x00", "Answer: placeholder")
STATE_PACKET_FIELDS = ("request", "query_text", "input_text", "input_state", "state_update", "graph_input", "visible_evidence_ids")
STATE_LABEL_FIELDS = ("evidence_sufficiency", "hypothesis_status", "verifier_status", "target", "target_text", "route", "stop_decision")
LATER_LAYER_MARKERS = (
    "edit_localization",
    "patch_operator_selection",
    "verifier_failure_repair_or_abstain",
    "bounded_decoder_ce",
    "level3",
    "transition",
)

BLOCKERS = (
    "state_packet_sanitizer_not_materialized",
    "canonical_split_mapping_not_materialized",
    "evidence_sufficiency_labels_missing_or_not_reviewed",
    "state_compression_targets_not_materialized",
    "verifier_status_state_packets_not_independently_reviewed",
    "hidden_target_leakage_audit_missing",
    "later_layer_rows_not_filtered_from_structured_state",
    "structured_repo_state_admission_manifest_missing",
)


class Stage12657SourceInventoryError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12657SourceInventoryError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12657SourceInventoryError(f"jsonl_object_required:{path.name}:{line_number}")
            rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def false_fields() -> dict[str, bool]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if record.get(field) is not False:
            raise Stage12657SourceInventoryError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12657SourceInventoryError(f"{label}_public_leak:{needle}")


def check_present_false(record: Mapping[str, Any], label: str, fields: tuple[str, ...]) -> None:
    for field in fields:
        if record.get(field) is not False:
            raise Stage12657SourceInventoryError(f"{label}_gate_drift:{field}")


def load_stage12656() -> dict[str, Any]:
    data = S12656_SUMMARY.read_bytes()
    if sha256_bytes(data) != EXPECTED_STAGE12656_SUMMARY_SHA256:
        raise Stage12657SourceInventoryError("stage12656_summary_pin_drift")
    summary = json.loads(data.decode("utf-8"))
    if summary.get("repo_code_curriculum_layer_complete") is not True:
        raise Stage12657SourceInventoryError("repo_code_layer_not_complete")
    if summary.get("shortcut_resilience_overlay_materialized") is not True:
        raise Stage12657SourceInventoryError("symbol_shortcut_resilience_missing")
    check_present_false(
        summary,
        "stage12656_summary",
        (
            "implementation_ready",
            "training_admission_allowed",
            "training_allowed",
            "training_run_allowed",
            "training_admitted",
            "strict_eval_admitted",
            "sealed_eval_admitted",
            "strict_eval_eligible",
            "sealed_eval_eligible",
            "gpu_allocation_requested",
            "cuda2_training_allowed",
            "vm_runner_execution_allowed",
            "runtime_authorized",
            "replay_trustworthy",
            "level_3_materialized",
            "model_execution_authorized_next",
            "optimizer_step_authorized",
            "source_emission_authorized",
            "body_emission_authorized",
        ),
    )
    return summary


def count_markers(text: str, markers: tuple[str, ...]) -> dict[str, int]:
    return {marker.replace("\x00", "NUL"): text.count(marker) for marker in markers if text.count(marker)}


def row_value_contains(row: Mapping[str, Any], needle: str) -> bool:
    return needle in json.dumps(row, sort_keys=True, ensure_ascii=True)


def classify_source(meta: Mapping[str, Any], rows: list[dict[str, Any]], text: str) -> str:
    if not rows:
        return "missing_or_empty"
    if any(marker in text for marker in LEAK_MARKERS):
        return "candidate_requires_sanitization"
    if meta["layer_role"].endswith("reference_only"):
        return "reference_only_not_admissible_for_structured_repo_state"
    if any(any(str(row.get("source_skill_area") or row.get("task_family") or row.get("record_type") or "").find(marker) >= 0 for marker in LATER_LAYER_MARKERS) for row in rows):
        return "mixed_later_layer_requires_filtering"
    return "candidate_requires_schema_review"


def source_audit(meta: Mapping[str, Any]) -> dict[str, Any]:
    path = meta["path"]
    if not path.exists():
        return {
            "source_id": meta["source_id"],
            "family": meta["family"],
            "layer_role": meta["layer_role"],
            "exists": False,
            "row_count": 0,
            "readiness": "missing_or_empty",
            "row_count_matches_expected": False,
        }
    data = path.read_bytes()
    rows = read_jsonl(path)
    text = data.decode("utf-8", errors="replace")
    key_counts = collections.Counter(key for row in rows for key in row)
    split_counts = collections.Counter(str(row.get("split") or row.get("split_component") or "<missing>") for row in rows)
    lane_counts = collections.Counter(str(row.get("source_skill_area") or row.get("target_family") or row.get("record_type") or "<missing>") for row in rows)
    state_field_rows = sum(1 for row in rows if any(field in row for field in STATE_PACKET_FIELDS))
    label_field_rows = sum(1 for row in rows if any(field in row for field in STATE_LABEL_FIELDS))
    target_visible_rows = sum(
        1
        for row in rows
        if isinstance(row.get("target_text"), str)
        and isinstance(row.get("input_text"), str)
        and str(row["target_text"]).strip()
        and str(row["target_text"]).strip() in str(row["input_text"])
    )
    path_marker_rows = sum(1 for row in rows if row_value_contains(row, "/data/") or row_value_contains(row, "/arxiv/"))
    return {
        "source_id": meta["source_id"],
        "family": meta["family"],
        "layer_role": meta["layer_role"],
        "exists": True,
        "row_count": len(rows),
        "row_count_matches_expected": len(rows) == meta["expected_rows"],
        "sha256": sha256_bytes(data),
        "readiness": classify_source(meta, rows, text),
        "top_level_key_counts": dict(sorted(key_counts.items())),
        "split_or_component_counts": dict(sorted(split_counts.items())),
        "lane_counts": dict(sorted(lane_counts.items())),
        "state_packet_field_rows": state_field_rows,
        "state_label_field_rows": label_field_rows,
        "target_visible_rows": target_visible_rows,
        "private_path_marker_rows": path_marker_rows,
        "leak_marker_counts": count_markers(text, LEAK_MARKERS),
    }


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    upstream = load_stage12656()
    audits = [source_audit(meta) for meta in CANDIDATE_SOURCES]
    readiness_counts = dict(sorted(collections.Counter(row["readiness"] for row in audits).items()))
    family_counts = dict(sorted(collections.Counter(row["family"] for row in audits).items()))
    total_rows = sum(int(row["row_count"]) for row in audits)
    candidate_rows = sum(
        int(row["row_count"])
        for row in audits
        if row["readiness"] in {"candidate_requires_sanitization", "candidate_requires_schema_review", "mixed_later_layer_requires_filtering"}
    )
    public_matrix = {
        "record_type": "stage12657_structured_repo_state_source_inventory_matrix_v1",
        "stage": STAGE,
        "candidate_source_count": len(audits),
        "total_inventory_rows": total_rows,
        "candidate_rows_before_sanitization": candidate_rows,
        "readiness_counts": readiness_counts,
        "family_counts": family_counts,
        "blockers": list(BLOCKERS),
        "structured_repo_state_layer_admission_ready": False,
        "recommended_next_stage": "stage12658_structured_repo_state_sanitized_candidate_manifest_preflight_only",
        **false_fields(),
    }
    summary = {
        "record_type": "stage12657_public_structured_repo_state_source_inventory_summary_v1",
        "stage": STAGE,
        "decision": "STRUCTURED_REPO_STATE_SOURCE_INVENTORY_RECORDED_NO_ROW_ADMISSION",
        "repo_code_curriculum_layer_complete": upstream["repo_code_curriculum_layer_complete"],
        "symbol_binding_shortcut_resilience_materialized": upstream["shortcut_resilience_overlay_materialized"],
        "structured_repo_state_source_inventory_materialized": True,
        "candidate_source_count": len(audits),
        "total_inventory_rows": total_rows,
        "candidate_rows_before_sanitization": candidate_rows,
        "readiness_counts": readiness_counts,
        "blocking_issue_count": len(BLOCKERS),
        "structured_repo_state_layer_admission_ready": False,
        "next_required_action": "stage12658_structured_repo_state_sanitized_candidate_manifest_preflight_only",
        **false_fields(),
    }
    private = {
        "record_type": "stage12657_private_structured_repo_state_source_inventory_packet_v1",
        "stage": STAGE,
        "stage12656_summary_sha256": EXPECTED_STAGE12656_SUMMARY_SHA256,
        "candidate_source_audit_count": len(audits),
        "candidate_source_audits_sha256": stable_hash(audits),
        "source_inventory_matrix_sha256": stable_hash(public_matrix),
        "blockers": list(BLOCKERS),
        **false_fields(),
    }
    assert_public_sanitized(summary, "summary")
    assert_public_sanitized(public_matrix, "matrix")
    return summary, public_matrix, audits


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, matrix, audits = build_packet()
    private = {
        "record_type": "stage12657_private_structured_repo_state_source_inventory_packet_v1",
        "stage": STAGE,
        "source_inventory_matrix_sha256": stable_hash(matrix),
        "candidate_source_audits_sha256": stable_hash(audits),
        "stage12656_summary_sha256": EXPECTED_STAGE12656_SUMMARY_SHA256,
        "blockers": list(BLOCKERS),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12657_structured_repo_state_source_inventory_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "upstream_stage": "stage12656_repo_code_symbol_binding_shortcut_resilience_preflight_only",
        "recommended_next_stage": summary["next_required_action"],
        "source_inventory_matrix_sha256": stable_hash(matrix),
        "private_packet_sha256": stable_hash(private),
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12657_structured_repo_state_source_inventory_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "source_inventory_matrix_sha256": stable_hash(matrix),
        "private_packet_sha256": stable_hash(private),
        **false_fields(),
    }
    for label, record in (("summary", summary), ("matrix", matrix), ("contract", contract), ("pointer", pointer)):
        assert_public_sanitized(record, label)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "summary.json", summary)
    write_json(out / "source_inventory_matrix.json", matrix)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/structured_repo_state_source_inventory_packet.json", private)
    write_jsonl(out / "private/candidate_source_audit.jsonl", audits)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(out / "private")
    fsync_dir(summary_path.parent)
    return summary


def main() -> None:
    print(json.dumps(build(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
