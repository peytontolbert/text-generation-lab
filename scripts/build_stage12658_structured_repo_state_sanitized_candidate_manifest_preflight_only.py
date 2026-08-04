#!/usr/bin/env python3
# Build a sanitized Structured Repo State candidate manifest without row admission or training.
from __future__ import annotations

import collections
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12658_structured_repo_state_sanitized_candidate_manifest_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12657 = ROOT / "runs/local/artifacts/stage12657_structured_repo_state_source_inventory_preflight_only"
S12657_SUMMARY = ROOT / "runs/summaries/stage12657_structured_repo_state_source_inventory_preflight_only.json"
S12657_AUDIT = S12657 / "private/candidate_source_audit.jsonl"
ROOTS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
TARGETS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_multitarget_rows.jsonl"
STATES = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_causal_states.jsonl"

EXPECTED_HASHES = {
    "stage12657_summary": "a44c2c3b3cce9f61df61a65d3217c329da6c403eeb676252c2d4df5bb700b70b",
    "stage12657_audit": "84fb693bceda060017767d314085458583c11974dbae06be12cc2b78834c8149",
    "stage10516_roots": "e7106ab3e14010a928e1af1fceecdeb15fb017ed2676fa5b8206658c1916b56d",
    "stage10516_targets": "279636642e2b3f992c3b82bcec13a4cbb74bc492081f4a365a14744c8771c817",
    "stage10516_states": "197f3ce57135abd7133a4054601a7dd637d1134fbad4d24b4bb553d6a0c4bb49",
}

FALSE_FIELDS = (
    "implementation_ready", "dataset_rows_admitted", "structured_repo_state_rows_admitted",
    "structured_repo_state_admission_ready", "stage12659_allowed", "training_admission_allowed",
    "training_allowed", "training_run_allowed", "training_admitted", "strict_eval_admitted",
    "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible", "gpu_allocation_requested",
    "cuda2_training_allowed", "vm_runner_execution_allowed", "runtime_authorized", "replay_trustworthy",
    "level_3_materialized", "model_execution_authorized_next", "optimizer_step_authorized",
    "source_emission_authorized", "body_emission_authorized",
)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "input_text", "target_text", "query_text", "root_id", "state_id",
    "episode_id", "source_lineage", "source_row_id", "jsonl",
)
PRIVATE_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "\x00", "Answer: placeholder", "input_text", "target_text",
    "query_text", "source_lineage", "source_row_id",
)

PATH_LINE_RE = re.compile(r"^(Changed files|Verification targets):\s*(.*)$", re.MULTILINE)
SYMBOL_LINE_RE = re.compile(r"^Key symbols:\s*(.*)$", re.MULTILINE)
TARGET_LINE_RE = re.compile(r"^(Execution route|Test selection route):\s*", re.MULTILINE)

EVIDENCE_TARGETS = {"decisive_evidence", "retrieve_answer_abstain"}
BLOCKERS = (
    "evidence_sufficiency_labels_missing_or_not_reviewed",
    "state_compression_targets_require_independent_review",
    "verifier_status_state_packets_not_independently_reviewed",
    "hidden_target_leakage_review_not_complete",
    "canonical_eval_and_strict_eval_split_not_materialized",
    "structured_repo_state_admission_manifest_missing",
)


class Stage12658ManifestError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12658ManifestError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12658ManifestError(f"object_required:{path.name}:{line_number}")
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
            raise Stage12658ManifestError(f"{label}_gate_drift:{field}")


def check_present_false(record: Mapping[str, Any], label: str, fields: tuple[str, ...]) -> None:
    for field in fields:
        if record.get(field) is not False:
            raise Stage12658ManifestError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str, needles: tuple[str, ...]) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in needles:
        if needle in encoded:
            raise Stage12658ManifestError(f"{label}_leak:{needle}")


def load_pinned_inputs() -> dict[str, Any]:
    for label, path in (
        ("stage12657_summary", S12657_SUMMARY), ("stage12657_audit", S12657_AUDIT),
        ("stage10516_roots", ROOTS), ("stage10516_targets", TARGETS), ("stage10516_states", STATES),
    ):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12658ManifestError("pin_drift:" + label)
    summary = read_json(S12657_SUMMARY)
    check_present_false(summary, "stage12657_summary", ("implementation_ready", "dataset_rows_admitted", "structured_repo_state_rows_admitted", "training_admission_allowed", "training_allowed", "training_run_allowed", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed", "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next", "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized"))
    if summary.get("next_required_action") != STAGE:
        raise Stage12658ManifestError("stage12657_next_action_drift")
    return {
        "stage12657_summary": summary,
        "stage12657_audit": read_jsonl(S12657_AUDIT),
        "roots": read_jsonl(ROOTS),
        "targets": read_jsonl(TARGETS),
        "states": read_jsonl(STATES),
    }


def opaque_id(prefix: str, raw: str) -> str:
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def bucket_count(count: int) -> str:
    if count == 0:
        return "0"
    if count <= 2:
        return "1_2"
    if count <= 5:
        return "3_5"
    if count <= 10:
        return "6_10"
    if count <= 25:
        return "11_25"
    return "gt_25"


def item_count_from_line(text: str, label: str) -> int:
    for match in PATH_LINE_RE.finditer(text):
        if match.group(1) == label:
            return len([item.strip() for item in match.group(2).split(",") if item.strip()])
    return 0


def symbol_count_from_line(text: str) -> int:
    match = SYMBOL_LINE_RE.search(text)
    if not match:
        return 0
    return len([item.strip() for item in match.group(1).split(",") if item.strip()])


def query_features(text: str) -> dict[str, str | bool]:
    return {
        "changed_file_count_bucket": bucket_count(item_count_from_line(text, "Changed files")),
        "verification_target_count_bucket": bucket_count(item_count_from_line(text, "Verification targets")),
        "key_symbol_count_bucket": bucket_count(symbol_count_from_line(text)),
        "target_route_lines_removed": bool(TARGET_LINE_RE.search(text)),
    }


def count_list(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def canonical_split(split_component: str) -> str:
    if split_component in {"audited_train", "train_bootstrap_long_context"}:
        return "train_candidate"
    return "unknown_candidate"


def target_visible(row: Mapping[str, Any]) -> bool:
    target = str(row.get("target_text") or "").strip()
    source = str(row.get("input_text") or "")
    return bool(target and target in source)


def root_row(row: Mapping[str, Any]) -> dict[str, Any]:
    task = str(row.get("task_family") or "unknown")
    quarantine = [] if task == "retrieval_supervision" else ["terminal_or_query_supervision_root"]
    return {
        "candidate_id": opaque_id("srs_root", str(row["root_id"])),
        "root_candidate_id": opaque_id("root", str(row["root_id"])),
        "source_row_family": "compiled_root_records",
        "canonical_split": canonical_split(str(row.get("split_component") or "")),
        "repo_family_bucket": str(row.get("repo_family") or "unknown"),
        "language_family": str(row.get("language_family") or "unknown"),
        "state_signal_type": task,
        "state_label_type": "root_metadata_only",
        "sanitized_structural_features": {"verifier_family": str(row.get("verifier_id") or "unknown")},
        "source_target_visible": False,
        "candidate_status": "candidate_for_independent_review" if not quarantine else "quarantined_terminal_or_action_policy_state",
        "eligible_for_stage12659_review": not quarantine,
        "trainer_consumable": False,
        "row_admitted": False,
        "loss_weight": 0.0,
        "quarantine_reasons": quarantine,
    }


def state_row(row: Mapping[str, Any]) -> dict[str, Any]:
    state_kind = str(row.get("state_kind") or "unknown")
    final_state = row.get("final_state") if isinstance(row.get("final_state"), dict) else {}
    quarantine = [] if state_kind == "retrieval_teacher_state" else ["terminal_or_action_policy_state"]
    return {
        "candidate_id": opaque_id("srs_state", str(row["state_id"])),
        "root_candidate_id": opaque_id("root", str(row["root_id"])),
        "source_row_family": "compiled_causal_states",
        "canonical_split": "train_candidate",
        "repo_family_bucket": "unknown",
        "language_family": "unknown",
        "state_signal_type": state_kind,
        "state_label_type": str(row.get("hypothesis_status") or "unknown"),
        "sanitized_structural_features": {
            **query_features(str(row.get("query_text") or "")),
            "final_changed_file_count_bucket": bucket_count(count_list(final_state.get("expected_changed_files"))),
            "final_verification_target_count_bucket": bucket_count(count_list(final_state.get("verification_targets"))),
            "final_key_symbol_count_bucket": bucket_count(count_list(final_state.get("key_symbols"))),
            "visible_evidence_count_bucket": bucket_count(count_list(row.get("visible_evidence_ids"))),
            "candidate_set_count_bucket": bucket_count(count_list(row.get("candidate_set_ids"))),
        },
        "source_target_visible": False,
        "candidate_status": "candidate_for_independent_review" if not quarantine else "quarantined_terminal_or_action_policy_state",
        "eligible_for_stage12659_review": not quarantine,
        "trainer_consumable": False,
        "row_admitted": False,
        "loss_weight": 0.0,
        "quarantine_reasons": quarantine,
    }


def target_row(row: Mapping[str, Any]) -> dict[str, Any]:
    subtype = str(row.get("target_subtype") or "unknown")
    visible = target_visible(row)
    quarantine: list[str] = []
    if subtype not in EVIDENCE_TARGETS:
        quarantine.append("non_state_evidence_target_subtype")
    if visible:
        quarantine.append("target_visible_in_source_prompt")
    features = query_features(str(row.get("input_text") or ""))
    return {
        "candidate_id": opaque_id("srs_target", str(row["row_id"])),
        "root_candidate_id": opaque_id("root", str(row["root_id"])),
        "source_row_family": "compiled_multitarget_rows",
        "canonical_split": canonical_split(str(row.get("split_component") or "")),
        "repo_family_bucket": "unknown",
        "language_family": "unknown",
        "state_signal_type": str(row.get("target_family") or "unknown"),
        "state_label_type": subtype,
        "sanitized_structural_features": features,
        "source_target_visible": visible,
        "candidate_status": "candidate_for_independent_review" if not quarantine else "quarantined_target_leak_or_later_layer",
        "eligible_for_stage12659_review": not quarantine,
        "trainer_consumable": False,
        "row_admitted": False,
        "loss_weight": 0.0,
        "quarantine_reasons": sorted(set(quarantine)),
    }


def build_manifest_rows(inputs: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    rows.extend(root_row(row) for row in inputs["roots"])
    rows.extend(state_row(row) for row in inputs["states"])
    rows.extend(target_row(row) for row in inputs["targets"])
    for row in rows:
        assert_no_forbidden(row, "sanitized_manifest_row", PRIVATE_FORBIDDEN_SUBSTRINGS)
    excluded = []
    for audit in inputs["stage12657_audit"]:
        if str(audit["source_id"]).startswith("stage10516_"):
            continue
        excluded.append({
            "source_id": audit["source_id"],
            "family": audit["family"],
            "layer_role": audit["layer_role"],
            "row_count": audit["row_count"],
            "exclusion_reason": "reference_or_later_layer_not_structured_repo_state_candidate",
        })
    return rows, excluded


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    inputs = load_pinned_inputs()
    manifest, excluded = build_manifest_rows(inputs)
    status_counts = dict(sorted(collections.Counter(row["candidate_status"] for row in manifest).items()))
    family_counts = dict(sorted(collections.Counter(row["source_row_family"] for row in manifest).items()))
    split_counts = dict(sorted(collections.Counter(row["canonical_split"] for row in manifest).items()))
    label_counts = dict(sorted(collections.Counter(row["state_label_type"] for row in manifest).items()))
    eligible = sum(1 for row in manifest if row["eligible_for_stage12659_review"])
    matrix = {
        "record_type": "stage12658_structured_repo_state_sanitized_candidate_matrix_v1",
        "stage": STAGE,
        "sanitized_candidate_rows": len(manifest),
        "eligible_for_stage12659_review": eligible,
        "quarantined_candidate_rows": len(manifest) - eligible,
        "excluded_reference_source_rows": sum(int(row["row_count"]) for row in excluded),
        "candidate_status_counts": status_counts,
        "source_row_family_counts": family_counts,
        "canonical_split_counts": split_counts,
        "state_label_type_counts": label_counts,
        "blockers": list(BLOCKERS),
        "recommended_next_stage": "stage12659_structured_repo_state_manifest_independent_review_only",
        **false_fields(),
    }
    summary = {
        "record_type": "stage12658_public_structured_repo_state_sanitized_candidate_manifest_summary_v1",
        "stage": STAGE,
        "decision": "STRUCTURED_REPO_STATE_SANITIZED_CANDIDATE_MANIFEST_MATERIALIZED_NO_ROW_ADMISSION",
        "structured_repo_state_sanitized_candidate_manifest_materialized": True,
        "sanitized_candidate_rows": len(manifest),
        "eligible_for_stage12659_review": eligible,
        "quarantined_candidate_rows": len(manifest) - eligible,
        "excluded_reference_source_rows": matrix["excluded_reference_source_rows"],
        "candidate_status_counts": status_counts,
        "source_row_family_counts": family_counts,
        "canonical_split_counts": split_counts,
        "blocking_issue_count": len(BLOCKERS),
        "next_required_action": "stage12659_structured_repo_state_manifest_independent_review_only",
        **false_fields(),
    }
    assert_no_forbidden(summary, "summary", PUBLIC_FORBIDDEN_SUBSTRINGS)
    assert_no_forbidden(matrix, "matrix", PUBLIC_FORBIDDEN_SUBSTRINGS)
    return summary, matrix, manifest, excluded


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, matrix, manifest, excluded = build_packet()
    private = {
        "record_type": "stage12658_private_structured_repo_state_sanitized_manifest_packet_v1",
        "stage": STAGE,
        "stage12657_summary_sha256": EXPECTED_HASHES["stage12657_summary"],
        "sanitized_candidate_manifest_sha256": stable_hash(manifest),
        "excluded_reference_sources_sha256": stable_hash(excluded),
        "matrix_sha256": stable_hash(matrix),
        "blockers": list(BLOCKERS),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12658_structured_repo_state_sanitized_manifest_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "upstream_stage": "stage12657_structured_repo_state_source_inventory_preflight_only",
        "recommended_next_stage": summary["next_required_action"],
        "matrix_sha256": stable_hash(matrix),
        "private_packet_sha256": stable_hash(private),
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12658_structured_repo_state_sanitized_manifest_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "matrix_sha256": stable_hash(matrix),
        "private_packet_sha256": stable_hash(private),
        "sanitized_candidate_manifest_sha256": stable_hash(manifest),
        "excluded_reference_sources_sha256": stable_hash(excluded),
        **false_fields(),
    }
    for label, record in (("summary", summary), ("matrix", matrix), ("contract", contract), ("pointer", pointer)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    assert_no_forbidden(manifest, "private_manifest", PRIVATE_FORBIDDEN_SUBSTRINGS)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "summary.json", summary)
    write_json(out / "sanitized_candidate_matrix.json", matrix)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/structured_repo_state_sanitized_manifest_packet.json", private)
    write_jsonl(out / "private/sanitized_structured_repo_state_candidate_manifest.jsonl", manifest)
    write_jsonl(out / "private/excluded_reference_sources.jsonl", excluded)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(out / "private")
    fsync_dir(summary_path.parent)
    return summary


def main() -> None:
    print(json.dumps(build(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
