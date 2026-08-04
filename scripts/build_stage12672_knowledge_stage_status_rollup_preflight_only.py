#!/usr/bin/env python3
# Roll up the knowledge-stage dataset integration status without changing training authority.
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12672_knowledge_stage_status_rollup_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12671_SUMMARY = ROOT / "runs/summaries/stage12671_symbol_binding_lane_independent_review_only.json"
S12671_AUDIT = ROOT / "runs/local/artifacts/stage12671_symbol_binding_lane_independent_review_only/symbol_binding_lane_review_audit.json"
S12656_SUMMARY = ROOT / "runs/summaries/stage12656_repo_code_symbol_binding_shortcut_resilience_preflight_only.json"
S12665_SUMMARY = ROOT / "runs/summaries/stage12665_combined_curriculum_pack_independent_review_only.json"
S12668_SUMMARY = ROOT / "runs/summaries/stage12668_combined_curriculum_loss_and_schedule_binding_preflight_only.json"

EXPECTED_HASHES = {
    "stage12671_summary": "8218eb70d38f4b97115466fc0b65276611e5996a94cdda753e59bc87126ad415",
    "stage12671_audit": "89f4cf34faf742ca5e686a8b2d15f06cf396a44a18ca1e69665db1cc015dc737",
    "stage12656_summary": "d23629f1c35bc9ed82cbb808196b2d2518a1b4a0cfaeb981a4de8aa4857c3b1a",
    "stage12665_summary": "526db4073a6dcb26b9b807a888142998c7b69e4b22c4a74835069a8abd1de7a1",
    "stage12668_summary": "b7f779c663eeb2c614584db7c7eeea1a9c5d2b8f1970a499d0b4116d8df72d0f",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12673_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field != "stage12673_allowed") + ("stage12672_allowed",)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "input_text", "target_text", "query_text", "model_input", "root_id", "state_id",
    "episode_id", "source_lineage", "source_row_id", "jsonl", "placeholder", "PLACEHOLDER", "TODO", "TBD",
)


class Stage12672RollupError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12672RollupError("json_object_required:" + path.name)
    return value


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


def check_false(record: Mapping[str, Any], label: str, fields: tuple[str, ...]) -> None:
    for field in fields:
        if record.get(field) is not False:
            raise Stage12672RollupError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12672RollupError(f"{label}_leak:{needle}")


def load_inputs() -> dict[str, Any]:
    for label, path in (
        ("stage12671_summary", S12671_SUMMARY),
        ("stage12671_audit", S12671_AUDIT),
        ("stage12656_summary", S12656_SUMMARY),
        ("stage12665_summary", S12665_SUMMARY),
        ("stage12668_summary", S12668_SUMMARY),
    ):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12672RollupError("pin_drift:" + label)
    summary71 = read_json(S12671_SUMMARY)
    audit71 = read_json(S12671_AUDIT)
    check_false(summary71, "stage12671_summary", UPSTREAM_FALSE_FIELDS)
    check_false(audit71, "stage12671_audit", UPSTREAM_FALSE_FIELDS)
    if summary71.get("next_required_action") != STAGE:
        raise Stage12672RollupError("stage12671_next_action_drift")
    return {
        "stage12671_summary": summary71,
        "stage12671_audit": audit71,
        "stage12656_summary": read_json(S12656_SUMMARY),
        "stage12665_summary": read_json(S12665_SUMMARY),
        "stage12668_summary": read_json(S12668_SUMMARY),
    }


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    inputs = load_inputs()
    s56 = inputs["stage12656_summary"]
    s65 = inputs["stage12665_summary"]
    s68 = inputs["stage12668_summary"]
    s71 = inputs["stage12671_summary"]

    if s71.get("symbol_binding_rows_reviewed") != 58:
        raise Stage12672RollupError("symbol_binding_review_count_drift")
    if s68.get("repo_code_decoder_target_audit_required_rows") != 200:
        raise Stage12672RollupError("repo_decoder_audit_count_drift")
    if s68.get("trainer_extension_required_rows") != 2187:
        raise Stage12672RollupError("structured_extension_count_drift")
    if s65.get("combined_trainer_rows_reviewed") != 2445:
        raise Stage12672RollupError("combined_review_count_drift")

    lanes = [
        {
            "lane": "repo_code_capability_profile",
            "status": "dataset_admitted_pack_reviewed",
            "rows": 200,
            "training_stage": "repo_and_code_knowledge",
            "remaining_blocker": "decoder_target_audit_before_decoder_ce_use",
        },
        {
            "lane": "source_backed_symbol_binding",
            "status": "knowledge_lane_reviewed_and_trainer_contract_validated",
            "rows": 58,
            "training_stage": "repo_graph_and_symbol_binding",
            "remaining_blocker": "separate_training_authorization",
        },
        {
            "lane": "structured_repo_state",
            "status": "dataset_admitted_but_trainer_extension_required",
            "rows": 2187,
            "training_stage": "structured_repo_state",
            "remaining_blocker": "structured_loss_head_and_validator_registration",
        },
    ]
    audit = {
        "record_type": "stage12672_knowledge_stage_status_rollup_audit_v1",
        "stage": STAGE,
        "rollup_decision": "KNOWLEDGE_STAGE_ROLLUP_COMPLETE_NO_TRAINING_RUN",
        "repo_code_knowledge_stage_complete": True,
        "symbol_binding_knowledge_lane_ready_for_training_admission_review": True,
        "repo_decoder_lane_requires_target_audit": True,
        "structured_repo_state_requires_trainer_extension": True,
        "combined_rows_reviewed": 2445,
        "knowledge_stage_rows_reviewed": 258,
        "symbol_binding_rows_contract_validated": 58,
        "repo_code_decoder_target_audit_required_rows": 200,
        "structured_repo_state_extension_required_rows": 2187,
        "lane_status": lanes,
        "next_required_action": "stage12673_symbol_binding_training_admission_review_only",
        **false_fields(),
    }
    checks = [
        {"check_id": "stage12671_pins", "status": "pass"},
        {"check_id": "repo_code_knowledge_rollup", "status": "pass"},
        {"check_id": "symbol_binding_contract_validation", "status": "pass"},
        {"check_id": "repo_decoder_target_audit", "status": "blocked"},
        {"check_id": "structured_repo_state_trainer_extension", "status": "blocked"},
        {"check_id": "training_execution_authority", "status": "blocked"},
    ]
    summary = {
        "record_type": "stage12672_public_knowledge_stage_status_rollup_summary_v1",
        "stage": STAGE,
        "decision": audit["rollup_decision"],
        "repo_code_knowledge_stage_complete": True,
        "knowledge_stage_rows_reviewed": 258,
        "symbol_binding_rows_contract_validated": 58,
        "symbol_binding_knowledge_lane_ready_for_training_admission_review": True,
        "repo_code_decoder_target_audit_required_rows": 200,
        "structured_repo_state_extension_required_rows": 2187,
        "dataset_rows_admitted": True,
        "combined_dataset_rows_admitted": True,
        "next_required_action": audit["next_required_action"],
        **false_fields(),
    }
    _ = s56
    for label, record in (("summary", summary), ("audit", audit)):
        assert_no_forbidden(record, label)
    return summary, audit, checks


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, checks = build_packet()
    private = {
        "record_type": "stage12672_private_knowledge_stage_status_rollup_packet_v1",
        "stage": STAGE,
        "stage12671_summary_sha256": EXPECTED_HASHES["stage12671_summary"],
        "stage12671_audit_sha256": EXPECTED_HASHES["stage12671_audit"],
        "stage12656_summary_sha256": EXPECTED_HASHES["stage12656_summary"],
        "stage12665_summary_sha256": EXPECTED_HASHES["stage12665_summary"],
        "stage12668_summary_sha256": EXPECTED_HASHES["stage12668_summary"],
        "rollup_audit_sha256": stable_hash(audit),
        "rollup_checks_sha256": stable_hash(checks),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12672_knowledge_stage_status_rollup_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "upstream_stage": "stage12671_symbol_binding_lane_independent_review_only",
        "recommended_next_stage": summary["next_required_action"],
        "knowledge_stage_rows_reviewed": summary["knowledge_stage_rows_reviewed"],
        "private_packet_sha256": stable_hash(private),
        "rollup_audit_sha256": stable_hash(audit),
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12672_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "rollup_audit_sha256": stable_hash(audit),
        **false_fields(),
    }
    for label, record in (("contract", contract), ("pointer", pointer), ("private", private)):
        assert_no_forbidden(record, label)
    write_json(out / "summary.json", summary)
    write_json(out / "knowledge_stage_status_rollup_audit.json", audit)
    write_jsonl(out / "private/knowledge_stage_status_rollup_checks.jsonl", checks)
    write_json(out / "private/knowledge_stage_status_rollup_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=True))
