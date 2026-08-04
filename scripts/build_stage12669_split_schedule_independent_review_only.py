#!/usr/bin/env python3
# Independently review the Stage12668 split schedule before trainer integration work.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12669_split_schedule_independent_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12668_SUMMARY = ROOT / "runs/summaries/stage12668_combined_curriculum_loss_and_schedule_binding_preflight_only.json"
S12668_AUDIT = ROOT / "runs/local/artifacts/stage12668_combined_curriculum_loss_and_schedule_binding_preflight_only/loss_schedule_binding_audit.json"
S12668_REPO = ROOT / "runs/local/artifacts/stage12668_combined_curriculum_loss_and_schedule_binding_preflight_only/private/repo_code_decoder_ce_candidate_manifest.jsonl"
S12668_SYMBOL = ROOT / "runs/local/artifacts/stage12668_combined_curriculum_loss_and_schedule_binding_preflight_only/private/symbol_binding_probe_candidate_manifest.jsonl"
S12668_STRUCTURED = ROOT / "runs/local/artifacts/stage12668_combined_curriculum_loss_and_schedule_binding_preflight_only/private/structured_repo_state_extension_candidate_manifest.jsonl"

EXPECTED_HASHES = {
    "stage12668_summary": "b7f779c663eeb2c614584db7c7eeea1a9c5d2b8f1970a499d0b4116d8df72d0f",
    "stage12668_audit": "50ae676a14ce8220ea6a8fc8c069c7135354bcecfbbaa298f0f166576e6f8d33",
    "repo_lane": "c6af15a0de623368a7a330fa2359d688ccc9cc5465a057fb18e437e3ffd664f2",
    "symbol_lane": "e2fdcb7354e9a6ba259eed5ab3c4e9256718db21c109808e25b4ee655a4d36f5",
    "structured_lane": "fce605c69b6fde29e800557c463d14139543f8bda3260ae106ce427d4a02af79",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12670_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field != "stage12670_allowed") + ("stage12669_allowed",)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "input_text", "target_text", "query_text", "model_input", "root_id", "state_id",
    "episode_id", "source_lineage", "source_row_id", "jsonl", "placeholder", "PLACEHOLDER", "TODO", "TBD",
)
PRIVATE_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "\x00", "Answer: placeholder", "PLACEHOLDER", "placeholder", "TODO", "TBD",
    "input_text", "target_text", "query_text", "model_input", "source_lineage", "source_row_id",
    "root_candidate_id", "training_candidate_id",
)

EXPECTED_SPLITS = {
    "repo_code_decoder_ce": {"eval": 40, "strict_eval": 39, "train": 121},
    "symbol_binding_probe": {"eval": 19, "strict_eval": 16, "train": 23},
    "structured_repo_state_extension": {"eval": 315, "strict_eval": 315, "train": 1557},
}
EXPECTED_LOSSES = {
    "repo_code_decoder_ce": {"decoder_ce": 200},
    "symbol_binding_probe": {"symbol_binding_ce": 58},
    "structured_repo_state_extension": {
        "structured_repo_state_evidence_role_ce": 729,
        "structured_repo_state_evidence_route_ce": 729,
        "structured_repo_state_hypothesis_status_ce": 729,
    },
}


class Stage12669ReviewError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12669ReviewError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12669ReviewError(f"row_object_required:{line_number}")
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
            raise Stage12669ReviewError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str, needles: tuple[str, ...]) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in needles:
        if needle in encoded:
            raise Stage12669ReviewError(f"{label}_leak:{needle}")


def count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get(key)) for row in rows).items()))


def enabled_loss(row: Mapping[str, Any]) -> str:
    enabled = [str(key) for key, value in (row.get("loss_mask") or {}).items() if bool(value)]
    if len(enabled) != 1:
        raise Stage12669ReviewError("expected_exactly_one_enabled_loss")
    return enabled[0]


def load_inputs() -> dict[str, Any]:
    for label, path in (
        ("stage12668_summary", S12668_SUMMARY),
        ("stage12668_audit", S12668_AUDIT),
        ("repo_lane", S12668_REPO),
        ("symbol_lane", S12668_SYMBOL),
        ("structured_lane", S12668_STRUCTURED),
    ):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12669ReviewError("pin_drift:" + label)
    summary = read_json(S12668_SUMMARY)
    audit = read_json(S12668_AUDIT)
    check_false(summary, "stage12668_summary", UPSTREAM_FALSE_FIELDS)
    check_false(audit, "stage12668_audit", UPSTREAM_FALSE_FIELDS)
    if summary.get("next_required_action") != STAGE:
        raise Stage12669ReviewError("stage12668_next_action_drift")
    return {
        "summary": summary,
        "audit": audit,
        "repo": read_jsonl(S12668_REPO),
        "symbol": read_jsonl(S12668_SYMBOL),
        "structured": read_jsonl(S12668_STRUCTURED),
    }


def lane_review(lane: str, rows: list[dict[str, Any]], *, expected_mode: str, runnable_candidate: bool) -> dict[str, Any]:
    assert_no_forbidden(rows, lane, PRIVATE_FORBIDDEN_SUBSTRINGS)
    if count(rows, "split") != EXPECTED_SPLITS[lane]:
        raise Stage12669ReviewError("split_count_drift:" + lane)
    loss_counts = dict(sorted(collections.Counter(enabled_loss(row) for row in rows).items()))
    if loss_counts != EXPECTED_LOSSES[lane]:
        raise Stage12669ReviewError("loss_count_drift:" + lane)
    if any(any((row.get("authority") or {}).values()) for row in rows):
        raise Stage12669ReviewError("authority_gate_open:" + lane)
    if any(row.get("training_allowed") is not False or row.get("training_run_allowed") is not False for row in rows):
        raise Stage12669ReviewError("training_gate_open:" + lane)
    if any(row.get("trainer_mode_candidate") != expected_mode for row in rows):
        raise Stage12669ReviewError("mode_candidate_drift:" + lane)
    return {
        "lane": lane,
        "rows_reviewed": len(rows),
        "split_counts": count(rows, "split"),
        "loss_counts": loss_counts,
        "trainer_mode_candidate": expected_mode,
        "runnable_with_current_trainer_contract_candidate": runnable_candidate,
        "authority_gates_closed": True,
        "training_gates_closed": True,
    }


def review_schedule(inputs: Mapping[str, Any]) -> dict[str, Any]:
    repo = inputs["repo"]
    symbol = inputs["symbol"]
    structured = inputs["structured"]
    symbol_actions = sorted({str((row.get("target") or {}).get("binding_action") or "") for row in symbol})
    if not symbol_actions or any(not action for action in symbol_actions):
        raise Stage12669ReviewError("symbol_binding_action_missing")
    structured_fields = sorted({str(row.get("structured_repo_state_field") or "") for row in structured})
    if structured_fields != ["evidence_role", "evidence_route", "hypothesis_status"]:
        raise Stage12669ReviewError("structured_field_drift")
    duplicate_weighted = sum(1 for row in structured if row.get("loss_weight") == 0.25)
    if duplicate_weighted != 1686:
        raise Stage12669ReviewError("structured_downweight_drift")
    lanes = [
        lane_review("repo_code_decoder_ce", repo, expected_mode="bounded_decoder_ce_probe", runnable_candidate=False),
        lane_review("symbol_binding_probe", symbol, expected_mode="symbol_binding_probe", runnable_candidate=True),
        lane_review("structured_repo_state_extension", structured, expected_mode="structured_repo_state_probe", runnable_candidate=False),
    ]
    return {
        "record_type": "stage12669_split_schedule_review_audit_v1",
        "stage": STAGE,
        "review_decision": "PASS_SPLIT_SCHEDULE_REVIEW_NO_TRAINING_RUN",
        "combined_rows_reviewed": len(repo) + len(symbol) + len(structured),
        "current_trainer_candidate_rows": len(symbol),
        "repo_code_decoder_target_audit_required_rows": len(repo),
        "trainer_extension_required_rows": len(structured),
        "structured_duplicate_downweighted_rows_preserved": duplicate_weighted,
        "symbol_binding_action_vocab": symbol_actions,
        "structured_repo_state_fields": structured_fields,
        "lane_reviews": lanes,
        "repo_code_decoder_ce_not_admitted_for_training": True,
        "symbol_binding_candidate_reviewed": True,
        "structured_repo_state_extension_reviewed_as_blocked": True,
        "next_required_action": "stage12670_symbol_binding_trainer_contract_validation_preflight_only",
        **false_fields(),
    }


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    inputs = load_inputs()
    audit = review_schedule(inputs)
    checks = [
        {"check_id": "stage12668_pins", "status": "pass"},
        {"check_id": "repo_code_decoder_lane", "status": "blocked", "detail": "decoder target audit required before use"},
        {"check_id": "symbol_binding_lane", "status": "pass", "detail": "parsed target fields are present"},
        {"check_id": "structured_repo_state_lane", "status": "blocked", "detail": "trainer loss/head extension required"},
        {"check_id": "training_execution_authority", "status": "blocked", "detail": "separate authorization still required"},
    ]
    summary = {
        "record_type": "stage12669_public_split_schedule_review_summary_v1",
        "stage": STAGE,
        "decision": audit["review_decision"],
        "combined_rows_reviewed": audit["combined_rows_reviewed"],
        "current_trainer_candidate_rows": audit["current_trainer_candidate_rows"],
        "repo_code_decoder_target_audit_required_rows": audit["repo_code_decoder_target_audit_required_rows"],
        "trainer_extension_required_rows": audit["trainer_extension_required_rows"],
        "structured_duplicate_downweighted_rows_preserved": audit["structured_duplicate_downweighted_rows_preserved"],
        "symbol_binding_candidate_reviewed": True,
        "repo_code_decoder_ce_not_admitted_for_training": True,
        "structured_repo_state_extension_reviewed_as_blocked": True,
        "split_schedule_review_passed": True,
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
        "record_type": "stage12669_private_split_schedule_review_packet_v1",
        "stage": STAGE,
        "stage12668_summary_sha256": EXPECTED_HASHES["stage12668_summary"],
        "stage12668_audit_sha256": EXPECTED_HASHES["stage12668_audit"],
        "repo_lane_sha256": EXPECTED_HASHES["repo_lane"],
        "symbol_lane_sha256": EXPECTED_HASHES["symbol_lane"],
        "structured_lane_sha256": EXPECTED_HASHES["structured_lane"],
        "review_audit_sha256": stable_hash(audit),
        "review_checks_sha256": stable_hash(checks),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12669_split_schedule_review_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "upstream_stage": "stage12668_combined_curriculum_loss_and_schedule_binding_preflight_only",
        "recommended_next_stage": summary["next_required_action"],
        "current_trainer_candidate_rows": summary["current_trainer_candidate_rows"],
        "repo_code_decoder_target_audit_required_rows": summary["repo_code_decoder_target_audit_required_rows"],
        "trainer_extension_required_rows": summary["trainer_extension_required_rows"],
        "private_packet_sha256": stable_hash(private),
        "review_audit_sha256": stable_hash(audit),
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12669_digest_pointer_v1",
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
    write_json(out / "split_schedule_review_audit.json", audit)
    write_jsonl(out / "private/split_schedule_review_checks.jsonl", checks)
    write_json(out / "private/split_schedule_review_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=True))
