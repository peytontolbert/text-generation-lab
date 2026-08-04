#!/usr/bin/env python3
# Split the combined adapter candidate into lane-specific trainer-binding candidates without authorizing training.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12668_combined_curriculum_loss_and_schedule_binding_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12667_SUMMARY = ROOT / "runs/summaries/stage12667_combined_curriculum_trainer_contract_adapter_preflight_only.json"
S12667_AUDIT = ROOT / "runs/local/artifacts/stage12667_combined_curriculum_trainer_contract_adapter_preflight_only/adapter_audit.json"
S12667_ADAPTER = ROOT / "runs/local/artifacts/stage12667_combined_curriculum_trainer_contract_adapter_preflight_only/private/combined_curriculum_canonical_adapter_candidate_manifest.jsonl"

EXPECTED_HASHES = {
    "stage12667_summary": "d0b28f591daf044406c21bb796c3d9bf1f504ef5db139b83248b4ba6c9e36f15",
    "stage12667_audit": "91676ecce07bbba0f4567801f276218d7462de5ea7bb5c38a8fe72c56171678c",
    "stage12667_adapter": "f4001f7a6a41d7791836fdaebc777d72e5991f4973de316d642ad13f597770b7",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12669_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field != "stage12669_allowed") + ("stage12668_allowed",)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "input_text", "target_text", "query_text", "model_input", "root_id", "state_id",
    "episode_id", "source_lineage", "source_row_id", "jsonl", "placeholder", "PLACEHOLDER", "TODO", "TBD",
)
PRIVATE_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "\x00", "Answer: placeholder", "PLACEHOLDER", "placeholder", "TODO", "TBD",
    "input_text", "target_text", "query_text", "model_input", "source_lineage", "source_row_id",
    "root_candidate_id", "training_candidate_id",
)

EXPECTED_LANE_SPLITS = {
    "repo_code_decoder_ce": {"eval": 40, "strict_eval": 39, "train": 121},
    "symbol_binding_probe": {"eval": 19, "strict_eval": 16, "train": 23},
    "structured_repo_state_extension": {"eval": 315, "strict_eval": 315, "train": 1557},
}
EXPECTED_TOTAL_SPLITS = {"eval": 374, "strict_eval": 370, "train": 1701}
CANONICAL_REQUIRED_FIELDS = {
    "row_id", "split", "language_family", "input_state", "target", "loss_mask",
    "authority", "source_provenance", "anti_cheat_contract",
}


class Stage12668BindingError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12668BindingError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12668BindingError(f"row_object_required:{line_number}")
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
            raise Stage12668BindingError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str, needles: tuple[str, ...]) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in needles:
        if needle in encoded:
            raise Stage12668BindingError(f"{label}_leak:{needle}")


def count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get(key)) for row in rows).items()))


def load_inputs() -> dict[str, Any]:
    for label, path in (
        ("stage12667_summary", S12667_SUMMARY),
        ("stage12667_audit", S12667_AUDIT),
        ("stage12667_adapter", S12667_ADAPTER),
    ):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12668BindingError("pin_drift:" + label)
    summary = read_json(S12667_SUMMARY)
    audit = read_json(S12667_AUDIT)
    check_false(summary, "stage12667_summary", UPSTREAM_FALSE_FIELDS)
    check_false(audit, "stage12667_audit", UPSTREAM_FALSE_FIELDS)
    if summary.get("next_required_action") != STAGE:
        raise Stage12668BindingError("stage12667_next_action_drift")
    return {"summary": summary, "audit": audit, "rows": read_jsonl(S12667_ADAPTER)}


def enabled_loss(row: Mapping[str, Any]) -> str:
    enabled = [str(key) for key, value in (row.get("loss_mask") or {}).items() if bool(value)]
    if len(enabled) != 1:
        raise Stage12668BindingError("expected_exactly_one_enabled_loss")
    return enabled[0]


def assert_canonical(row: Mapping[str, Any]) -> None:
    missing = CANONICAL_REQUIRED_FIELDS.difference(row)
    if missing:
        raise Stage12668BindingError("canonical_fields_missing:" + ",".join(sorted(missing)))


def all_false_authority(row: Mapping[str, Any]) -> bool:
    auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
    return bool(auth) and all(value is False for value in auth.values())


def clone_base(row: Mapping[str, Any]) -> dict[str, Any]:
    assert_canonical(row)
    if not all_false_authority(row):
        raise Stage12668BindingError("authority_gate_open")
    out = json.loads(json.dumps(row, sort_keys=True, ensure_ascii=True))
    out["adapter_status"] = "loss_schedule_binding_preflight_candidate"
    out["training_allowed"] = False
    out["training_run_allowed"] = False
    out["optimizer_step_authorized"] = False
    return out


def parse_binding_action(target: Mapping[str, Any]) -> str:
    text = str(target.get("decoder_text") or target.get("semantic_value") or "")
    for part in text.split(";"):
        key, sep, value = part.strip().partition("=")
        if sep and key == "binding_action" and value.strip():
            return value.strip()
    raise Stage12668BindingError("binding_action_missing")


def repo_decoder_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if enabled_loss(row) != "repo_code_ce":
            continue
        item = clone_base(row)
        target = item.get("target") if isinstance(item.get("target"), dict) else {}
        if not str(target.get("decoder_text") or "").strip():
            raise Stage12668BindingError("repo_decoder_target_missing")
        item["loss_mask"] = {"decoder_ce": True}
        item["lane"] = "repo_code_decoder_ce"
        item["trainer_mode_candidate"] = "bounded_decoder_ce_probe"
        item["binding_decision"] = "blocked_requires_decoder_target_audit_before_bounded_decoder_ce_use"
        out.append(item)
    return out


def symbol_binding_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if enabled_loss(row) != "symbol_binding_ce":
            continue
        item = clone_base(row)
        action = parse_binding_action(item["target"])
        item["target"]["binding_action"] = action
        item["target"]["symbol_binding"] = action
        item["clean_state"] = {"binding_action": action, "symbol_binding": action}
        item["loss_mask"] = {"symbol_binding_ce": True}
        item["lane"] = "symbol_binding_probe"
        item["trainer_mode_candidate"] = "symbol_binding_probe"
        item["binding_decision"] = "candidate_supported_by_existing_symbol_binding_contract_review_required"
        out.append(item)
    return out


def structured_extension_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if enabled_loss(row) != "structured_repo_state_ce":
            continue
        item = clone_base(row)
        objective = str(item["input_state"].get("training_objective") or "")
        if not objective:
            objective = {
                "teacher_supported": "structured_repo_state.hypothesis_status",
                "decisive_evidence": "structured_repo_state.evidence_role",
                "retrieve_answer_abstain": "structured_repo_state.evidence_route",
            }.get(str(item["target"].get("bounded_choice_target_label") or ""), "")
        objective = objective or "structured_repo_state.unknown"
        field = objective.rsplit(".", 1)[-1]
        label = str(item["target"].get("bounded_choice_target_label") or "")
        if not label:
            raise Stage12668BindingError("structured_label_missing")
        item["clean_state"] = {field: label}
        item["target"][field] = label
        item["structured_repo_state_field"] = field
        item["loss_mask"] = {f"structured_repo_state_{field}_ce": True}
        item["lane"] = "structured_repo_state_extension"
        item["trainer_mode_candidate"] = "structured_repo_state_probe"
        item["binding_decision"] = "blocked_requires_new_structured_head_loss_and_validator_registration"
        out.append(item)
    return out


def lane_audit(lane: str, rows: list[dict[str, Any]], *, runnable_candidate: bool) -> dict[str, Any]:
    split_counts = count(rows, "split")
    if split_counts != EXPECTED_LANE_SPLITS[lane]:
        raise Stage12668BindingError("lane_split_count_drift:" + lane)
    loss_counts: collections.Counter[str] = collections.Counter()
    weight_counts: collections.Counter[str] = collections.Counter()
    for row in rows:
        loss_counts.update([enabled_loss(row)])
        weight_counts.update([str(row.get("loss_weight"))])
    return {
        "lane": lane,
        "rows": len(rows),
        "split_counts": split_counts,
        "enabled_loss_counts": dict(sorted(loss_counts.items())),
        "loss_weight_counts": dict(sorted(weight_counts.items())),
        "trainer_mode_candidate": rows[0]["trainer_mode_candidate"] if rows else None,
        "runnable_with_current_trainer_contract_candidate": runnable_candidate,
        "training_allowed": False,
        "training_run_allowed": False,
    }


def split_lanes(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    assert_no_forbidden(rows, "stage12667_adapter_rows", PRIVATE_FORBIDDEN_SUBSTRINGS)
    if len(rows) != 2445 or count(rows, "split") != EXPECTED_TOTAL_SPLITS:
        raise Stage12668BindingError("adapter_count_drift")
    repo = repo_decoder_rows(rows)
    symbol = symbol_binding_rows(rows)
    structured = structured_extension_rows(rows)
    if len(repo) + len(symbol) + len(structured) != len(rows):
        raise Stage12668BindingError("lane_partition_incomplete")
    for label, lane_rows in (("repo", repo), ("symbol", symbol), ("structured", structured)):
        assert_no_forbidden(lane_rows, label + "_lane_rows", PRIVATE_FORBIDDEN_SUBSTRINGS)
    matrix = {
        "record_type": "stage12668_loss_schedule_binding_matrix_v1",
        "stage": STAGE,
        "lane_audits": [
            lane_audit("repo_code_decoder_ce", repo, runnable_candidate=False),
            lane_audit("symbol_binding_probe", symbol, runnable_candidate=True),
            lane_audit("structured_repo_state_extension", structured, runnable_candidate=False),
        ],
        "combined_rows_partitioned": len(rows),
        "current_trainer_candidate_rows": len(symbol),
        "decoder_target_audit_required_rows": len(repo),
        "trainer_extension_required_rows": len(structured),
        "structured_duplicate_downweighted_rows_preserved": sum(1 for row in structured if row.get("loss_weight") == 0.25),
        "schedule_binding_preflight_passed": True,
        "adapter_manifest_trainer_runnable_as_single_mixed_invocation": False,
        "training_allowed": False,
        "training_run_allowed": False,
        "next_required_action": "stage12669_split_schedule_independent_review_only",
        **false_fields(),
    }
    return repo, symbol, structured, matrix


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    loaded = load_inputs()
    repo, symbol, structured, matrix = split_lanes(loaded["rows"])
    blockers = [
        "repo_code_decoder_target_audit_required_before_decoder_ce_use",
        "structured_repo_state_loss_heads_and_validator_registration_required",
        "separate_training_run_authorization_required_after_independent_review",
    ]
    summary = {
        "record_type": "stage12668_public_loss_schedule_binding_preflight_summary_v1",
        "stage": STAGE,
        "decision": "SPLIT_SCHEDULE_MATERIALIZED_REPO_DECODER_AUDIT_AND_STRUCTURED_EXTENSION_REQUIRED",
        "combined_rows_partitioned": matrix["combined_rows_partitioned"],
        "repo_code_decoder_candidate_rows": len(repo),
        "repo_code_decoder_target_audit_required_rows": len(repo),
        "symbol_binding_candidate_rows": len(symbol),
        "structured_repo_state_extension_rows": len(structured),
        "current_trainer_candidate_rows": matrix["current_trainer_candidate_rows"],
        "decoder_target_audit_required_rows": matrix["decoder_target_audit_required_rows"],
        "trainer_extension_required_rows": matrix["trainer_extension_required_rows"],
        "structured_duplicate_downweighted_rows_preserved": matrix["structured_duplicate_downweighted_rows_preserved"],
        "adapter_manifest_trainer_runnable_as_single_mixed_invocation": False,
        "schedule_binding_preflight_passed": True,
        "dataset_rows_admitted": True,
        "combined_dataset_rows_admitted": True,
        "authorization_blockers": blockers,
        "next_required_action": matrix["next_required_action"],
        **false_fields(),
    }
    audit = {
        "record_type": "stage12668_loss_schedule_binding_audit_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "lane_audits": matrix["lane_audits"],
        "authorization_blockers": blockers,
        "next_required_action": summary["next_required_action"],
        **false_fields(),
    }
    for label, record in (("summary", summary), ("audit", audit), ("matrix", matrix)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    return summary, audit, repo, symbol, structured


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, repo, symbol, structured = build_packet()
    private = {
        "record_type": "stage12668_private_loss_schedule_binding_packet_v1",
        "stage": STAGE,
        "stage12667_summary_sha256": EXPECTED_HASHES["stage12667_summary"],
        "stage12667_audit_sha256": EXPECTED_HASHES["stage12667_audit"],
        "stage12667_adapter_sha256": EXPECTED_HASHES["stage12667_adapter"],
        "repo_code_decoder_manifest_sha256": stable_hash(repo),
        "symbol_binding_manifest_sha256": stable_hash(symbol),
        "structured_extension_manifest_sha256": stable_hash(structured),
        "audit_sha256": stable_hash(audit),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12668_loss_schedule_binding_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "upstream_stage": "stage12667_combined_curriculum_trainer_contract_adapter_preflight_only",
        "recommended_next_stage": summary["next_required_action"],
        "current_trainer_candidate_rows": summary["current_trainer_candidate_rows"],
        "trainer_extension_required_rows": summary["trainer_extension_required_rows"],
        "adapter_manifest_trainer_runnable_as_single_mixed_invocation": False,
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12668_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        **false_fields(),
    }
    for label, record in (("contract", contract), ("pointer", pointer), ("private", private)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    write_json(out / "summary.json", summary)
    write_json(out / "loss_schedule_binding_audit.json", audit)
    write_jsonl(out / "private/repo_code_decoder_ce_candidate_manifest.jsonl", repo)
    write_jsonl(out / "private/symbol_binding_probe_candidate_manifest.jsonl", symbol)
    write_jsonl(out / "private/structured_repo_state_extension_candidate_manifest.jsonl", structured)
    write_json(out / "private/loss_schedule_binding_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=True))
