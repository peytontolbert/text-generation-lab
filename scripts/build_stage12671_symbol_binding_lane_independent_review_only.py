#!/usr/bin/env python3
# Independently review the validated symbol-binding knowledge-source lane without training admission.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12671_symbol_binding_lane_independent_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12670_SUMMARY = ROOT / "runs/summaries/stage12670_symbol_binding_trainer_contract_validation_preflight_only.json"
S12670_AUDIT = ROOT / "runs/local/artifacts/stage12670_symbol_binding_trainer_contract_validation_preflight_only/symbol_binding_contract_validation_audit.json"
S12670_MANIFEST = ROOT / "runs/local/artifacts/stage12670_symbol_binding_trainer_contract_validation_preflight_only/private/identity_bound_symbol_binding_probe_candidate_manifest.jsonl"
STRUCTURE_DOC = ROOT / "docs/MAINTAINER_100M_TRAINING_STAGE_STRUCTURE.md"
STAGE_THEORY_DOC = ROOT / "training_stages.md"

EXPECTED_HASHES = {
    "stage12670_summary": "d9a314db75bd027a315e12f99908001fceafbe09f8e3202bbb575a41f03662de",
    "stage12670_audit": "e4f257f7c786990308daf46dfa9ea5c5507c75cd2189ef05cf25447c35256b42",
    "stage12670_manifest": "9845602efc04cbf31d548a3971c4dfc60c96b582265af8aa090f4bd633de230d",
    "maintainer_stage_structure_doc": "cf6204f501f5226c96d9fe892334ac19822f6473b98d4cbcf2dfcb05fd0551af",
    "stage_theory_doc": "13131a6ab8f4a7bf4fb4344c4b331ec89d3c2ea1b76c7a9f8849d78f6f9b174f",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12672_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field != "stage12672_allowed") + ("stage12671_allowed",)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "input_text", "target_text", "query_text", "model_input", "root_id", "state_id",
    "episode_id", "source_lineage", "source_row_id", "jsonl", "placeholder", "PLACEHOLDER", "TODO", "TBD",
)
PRIVATE_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "\x00", "Answer: placeholder", "PLACEHOLDER", "placeholder", "TODO", "TBD",
    "input_text", "target_text", "query_text", "model_input", "source_lineage", "source_row_id",
    "root_candidate_id", "training_candidate_id",
)

EXPECTED_SPLITS = {"eval": 19, "strict_eval": 16, "train": 23}
EXPECTED_ACTIONS = {
    "ABSTAIN_UNBOUND": 13,
    "BIND_CALL_TO_SYMBOL": 16,
    "BIND_IMPORT_TO_MODULE": 13,
    "BIND_TEST_TO_SYMBOL": 9,
    "RETRIEVE_MORE": 7,
}


class Stage12671ReviewError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12671ReviewError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12671ReviewError(f"row_object_required:{line_number}")
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


def check_false(record: Mapping[str, Any], label: str, fields: tuple[str, ...]) -> None:
    for field in fields:
        if record.get(field) is not False:
            raise Stage12671ReviewError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str, needles: tuple[str, ...]) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in needles:
        if needle in encoded:
            raise Stage12671ReviewError(f"{label}_leak:{needle}")


def count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get(key)) for row in rows).items()))


def enabled_loss(row: Mapping[str, Any]) -> str:
    enabled = [str(key) for key, value in (row.get("loss_mask") or {}).items() if bool(value)]
    if len(enabled) != 1:
        raise Stage12671ReviewError("expected_exactly_one_enabled_loss")
    return enabled[0]


def load_inputs() -> dict[str, Any]:
    for label, path in (
        ("stage12670_summary", S12670_SUMMARY),
        ("stage12670_audit", S12670_AUDIT),
        ("stage12670_manifest", S12670_MANIFEST),
        ("maintainer_stage_structure_doc", STRUCTURE_DOC),
        ("stage_theory_doc", STAGE_THEORY_DOC),
    ):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12671ReviewError("pin_drift:" + label)
    summary = read_json(S12670_SUMMARY)
    audit = read_json(S12670_AUDIT)
    check_false(summary, "stage12670_summary", UPSTREAM_FALSE_FIELDS)
    check_false(audit, "stage12670_audit", UPSTREAM_FALSE_FIELDS)
    if summary.get("next_required_action") != STAGE:
        raise Stage12671ReviewError("stage12670_next_action_drift")
    return {"summary": summary, "audit": audit, "rows": read_jsonl(S12670_MANIFEST)}


def review_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    assert_no_forbidden(rows, "symbol_binding_rows", PRIVATE_FORBIDDEN_SUBSTRINGS)
    if len(rows) != 58:
        raise Stage12671ReviewError("row_count_drift")
    if count(rows, "split") != EXPECTED_SPLITS:
        raise Stage12671ReviewError("split_count_drift")
    if dict(sorted(collections.Counter(str((row.get("target") or {}).get("binding_action") or "") for row in rows).items())) != EXPECTED_ACTIONS:
        raise Stage12671ReviewError("binding_action_count_drift")
    if any(enabled_loss(row) != "symbol_binding_ce" for row in rows):
        raise Stage12671ReviewError("loss_mask_drift")
    if any(row.get("contract_validation_identity_bound") is not True for row in rows):
        raise Stage12671ReviewError("identity_binding_missing")
    if any(any((row.get("authority") or {}).values()) for row in rows):
        raise Stage12671ReviewError("authority_gate_open")
    if any(row.get("training_allowed") is not False or row.get("training_run_allowed") is not False for row in rows):
        raise Stage12671ReviewError("training_gate_open")
    if any((row.get("target") or {}).get("binding_action") != (row.get("clean_state") or {}).get("binding_action") for row in rows):
        raise Stage12671ReviewError("target_clean_state_binding_drift")
    return {
        "rows_reviewed": len(rows),
        "split_counts": count(rows, "split"),
        "binding_action_counts": dict(sorted(collections.Counter(str((row.get("target") or {}).get("binding_action") or "") for row in rows).items())),
        "enabled_loss_counts": dict(sorted(collections.Counter(enabled_loss(row) for row in rows).items())),
        "identity_binding_present": True,
        "trainer_contract_validation_preserved": True,
        "authority_gates_closed": True,
        "training_gates_closed": True,
    }


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    inputs = load_inputs()
    row_audit = review_rows(inputs["rows"])
    trainer_card = inputs["audit"].get("trainer_contract_card") if isinstance(inputs["audit"].get("trainer_contract_card"), dict) else {}
    if trainer_card.get("passed") is not True or trainer_card.get("model_execution_attempted") is not False:
        raise Stage12671ReviewError("trainer_contract_card_drift")
    checks = [
        {"check_id": "stage12670_pins", "status": "pass"},
        {"check_id": "stage_structure_alignment", "status": "pass"},
        {"check_id": "symbol_binding_identity_bound_rows", "status": "pass"},
        {"check_id": "trainer_contract_validation", "status": "pass"},
        {"check_id": "training_execution_authority", "status": "blocked", "detail": "review does not authorize training execution"},
    ]
    audit = {
        "record_type": "stage12671_symbol_binding_lane_review_audit_v1",
        "stage": STAGE,
        "review_decision": "PASS_SYMBOL_BINDING_KNOWLEDGE_LANE_REVIEW_NO_TRAINING_RUN",
        "knowledge_stage_alignment": "repo_graph_and_symbol_binding",
        "stage_structure_docs_pinned": True,
        "repo_code_knowledge_stage_continues": True,
        "structured_repo_state_stage_already_separate": True,
        "symbol_binding_lane_training_contract_validated": True,
        "rows_reviewed": row_audit["rows_reviewed"],
        "split_counts": row_audit["split_counts"],
        "binding_action_counts": row_audit["binding_action_counts"],
        "enabled_loss_counts": row_audit["enabled_loss_counts"],
        "next_required_action": "stage12672_knowledge_stage_status_rollup_preflight_only",
        **false_fields(),
    }
    summary = {
        "record_type": "stage12671_public_symbol_binding_lane_review_summary_v1",
        "stage": STAGE,
        "decision": audit["review_decision"],
        "knowledge_stage_alignment": audit["knowledge_stage_alignment"],
        "symbol_binding_rows_reviewed": row_audit["rows_reviewed"],
        "split_counts": row_audit["split_counts"],
        "symbol_binding_lane_review_passed": True,
        "symbol_binding_lane_training_contract_validated": True,
        "dataset_rows_admitted": True,
        "combined_dataset_rows_admitted": True,
        "next_required_action": audit["next_required_action"],
        **false_fields(),
    }
    for label, record in (("summary", summary), ("audit", audit)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    return summary, audit, checks


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, checks = build_packet()
    private = {
        "record_type": "stage12671_private_symbol_binding_lane_review_packet_v1",
        "stage": STAGE,
        "stage12670_summary_sha256": EXPECTED_HASHES["stage12670_summary"],
        "stage12670_audit_sha256": EXPECTED_HASHES["stage12670_audit"],
        "identity_bound_symbol_manifest_sha256": EXPECTED_HASHES["stage12670_manifest"],
        "maintainer_stage_structure_doc_sha256": EXPECTED_HASHES["maintainer_stage_structure_doc"],
        "stage_theory_doc_sha256": EXPECTED_HASHES["stage_theory_doc"],
        "review_audit_sha256": stable_hash(audit),
        "review_checks_sha256": stable_hash(checks),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12671_symbol_binding_lane_review_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "upstream_stage": "stage12670_symbol_binding_trainer_contract_validation_preflight_only",
        "recommended_next_stage": summary["next_required_action"],
        "symbol_binding_rows_reviewed": summary["symbol_binding_rows_reviewed"],
        "private_packet_sha256": stable_hash(private),
        "review_audit_sha256": stable_hash(audit),
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12671_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "review_audit_sha256": stable_hash(audit),
        **false_fields(),
    }
    for label, record in (("contract", contract), ("pointer", pointer), ("private", private)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    write_json(out / "summary.json", summary)
    write_json(out / "symbol_binding_lane_review_audit.json", audit)
    write_jsonl(out / "private/symbol_binding_lane_review_checks.jsonl", checks)
    write_json(out / "private/symbol_binding_lane_review_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=True))
