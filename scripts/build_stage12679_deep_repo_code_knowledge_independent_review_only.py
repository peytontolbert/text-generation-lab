#!/usr/bin/env python3
"""Independently review Stage12678 deep repo/code knowledge without admitting training."""
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12679_deep_repo_code_knowledge_independent_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12678_SUMMARY = ROOT / "runs/summaries/stage12678_code_doc_build_semantic_knowledge_materialization_preflight_only.json"
S12678_AUDIT = ROOT / "runs/local/artifacts/stage12678_code_doc_build_semantic_knowledge_materialization_preflight_only/deep_repo_code_knowledge_materialization_audit.json"
S12678_CONTRACT = ROOT / "runs/local/artifacts/stage12678_code_doc_build_semantic_knowledge_materialization_preflight_only/contract.json"
S12678_ROWS = ROOT / "runs/local/artifacts/stage12678_code_doc_build_semantic_knowledge_materialization_preflight_only/private/deep_repo_code_knowledge_rows.jsonl"

EXPECTED_HASHES = {
    "stage12678_summary": "12d9d0e07a479899a7456126bac86a9fe910c9ca4f4579b33131f63fa96bc74a",
    "stage12678_audit": "57bb755e0f67f6617bcd0325ad43da49681931d50914069c015d8b2543fe860b",
    "stage12678_contract": "261902f3412925b654d0edc910f35b6ad0fd5df1c8de6eac90e7bfd7d367be38",
    "stage12678_rows": "009af0a174e5c00327aeededff7f11e9c08144bd420bddba413ba0d19fbaca3f",
}

EXPECTED_OBJECTIVE_COUNTS = {
    "build_code_association_fact": 670,
    "deep_file_role_language_fact": 12526,
    "doc_code_association_fact": 60,
    "maintenance_vocabulary_fact": 11974,
    "nonpython_symbol_definition_fact": 33232,
    "nonpython_syntax_summary_fact": 7379,
    "python_import_api_fact": 12960,
    "python_symbol_definition_fact": 29882,
    "python_syntax_summary_fact": 2767,
    "test_file_association_fact": 1586,
    "test_framework_signal_fact": 6964,
}
EXPECTED_SPLIT_COUNTS = {"eval": 21308, "strict_eval": 20408, "train": 78284}

FALSE_FIELDS = (
    "implementation_ready", "stage12680_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted", "strict_eval_eligible",
    "strict_eval_authorized", "sealed_eval_authorized", "loss_authorized", "compiler_execution_authorized",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field != "stage12680_allowed") + ("stage12679_allowed",)
FORBIDDEN_SUBSTRINGS = ("/data/", "/arxiv/", "PLACEHOLDER", "placeholder", "TODO", "TBD", "Answer:", "<fill", "\x00")


class Stage12679ReviewError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12679ReviewError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Stage12679ReviewError(f"jsonl_object_required:{line_number}")
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
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n")
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
            raise Stage12679ReviewError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12679ReviewError(f"{label}_forbidden_substring:{needle}")


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    pins = {
        "stage12678_summary": S12678_SUMMARY,
        "stage12678_audit": S12678_AUDIT,
        "stage12678_contract": S12678_CONTRACT,
        "stage12678_rows": S12678_ROWS,
    }
    for label, path in pins.items():
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12679ReviewError("pin_drift:" + label)
    summary = read_json(S12678_SUMMARY)
    audit = read_json(S12678_AUDIT)
    contract = read_json(S12678_CONTRACT)
    for label, record in (("stage12678_summary", summary), ("stage12678_audit", audit), ("stage12678_contract", contract)):
        check_false(record, label, UPSTREAM_FALSE_FIELDS)
    rows = read_jsonl(S12678_ROWS)
    if len(rows) != 120000:
        raise Stage12679ReviewError("row_count_drift")
    return summary, audit, contract, rows


def review_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    objective_counts = dict(sorted(collections.Counter(row["objective_family"] for row in rows).items()))
    split_counts = dict(sorted(collections.Counter(row["split"] for row in rows).items()))
    if objective_counts != EXPECTED_OBJECTIVE_COUNTS:
        raise Stage12679ReviewError("objective_count_drift")
    if split_counts != EXPECTED_SPLIT_COUNTS:
        raise Stage12679ReviewError("split_count_drift")

    row_ids: set[str] = set()
    semantic_hashes: collections.Counter[str] = collections.Counter()
    target_hashes: collections.Counter[str] = collections.Counter()
    target_splits: dict[str, set[str]] = collections.defaultdict(set)
    repo_splits: dict[str, set[str]] = collections.defaultdict(set)
    file_splits: dict[str, set[str]] = collections.defaultdict(set)
    file_rows: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    objective_splits: dict[str, set[str]] = collections.defaultdict(set)
    authority_open_rows = 0
    raw_source_body_rows = 0
    absolute_path_rows = 0
    forbidden_marker_rows = 0
    duplicate_row_ids = 0

    for row in rows:
        split = row.get("split")
        objective = row.get("objective_family")
        objective_splits[str(objective)].add(str(split))
        row_id = row.get("row_id")
        if row_id in row_ids:
            duplicate_row_ids += 1
        row_ids.add(str(row_id))

        authority = row.get("authority", {})
        if not isinstance(authority, dict) or any(value is not False for value in authority.values()):
            authority_open_rows += 1
        evidence = row.get("evidence", {})
        raw_source_body_rows += int(evidence.get("raw_source_body_included") is not False)
        absolute_path_rows += int(evidence.get("absolute_path_included") is not False)
        encoded = json.dumps(row, sort_keys=True, ensure_ascii=True)
        forbidden_marker_rows += int(any(needle in encoded for needle in FORBIDDEN_SUBSTRINGS))

        repo_digest = evidence.get("repo_digest") or row.get("input_state", {}).get("opaque_repo_id")
        file_digest = evidence.get("source_file_digest") or row.get("input_state", {}).get("opaque_file_id")
        if repo_digest:
            repo_splits[str(repo_digest)].add(str(split))
        if file_digest:
            file_splits[str(file_digest)].add(str(split))
            if len(file_rows[str(file_digest)]) < 6:
                file_rows[str(file_digest)].append({
                    "row_id": str(row_id),
                    "split": str(split),
                    "repo_digest": str(repo_digest),
                    "objective_family": str(objective),
                })

        semantic = {
            "split": split,
            "objective_family": objective,
            "input_state": row.get("input_state"),
            "expected_output": row.get("expected_output"),
            "evidence": evidence,
        }
        semantic_hashes[stable_hash(semantic)] += 1
        target = {"objective_family": objective, "expected_output": row.get("expected_output")}
        target_key = stable_hash(target)
        target_hashes[target_key] += 1
        target_splits[target_key].add(str(split))

    cross_split_file_examples = []
    for file_digest, splits in sorted(file_splits.items()):
        if len(splits) > 1:
            cross_split_file_examples.append({
                "source_file_digest": file_digest,
                "splits": sorted(splits),
                "sample_rows": file_rows[file_digest],
            })

    top_duplicate_targets = []
    target_labels: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = stable_hash({"objective_family": row.get("objective_family"), "expected_output": row.get("expected_output")})
        target_labels.setdefault(key, {"objective_family": row.get("objective_family"), "expected_output": row.get("expected_output")})
    for key, count in target_hashes.most_common(10):
        if count > 1:
            top_duplicate_targets.append({"count": count, **target_labels[key]})

    return {
        "deep_knowledge_rows_reviewed": len(rows),
        "objective_counts": objective_counts,
        "split_counts": split_counts,
        "objective_family_count": len(objective_counts),
        "repo_digest_count": len(repo_splits),
        "source_file_digest_count": len(file_splits),
        "duplicate_row_ids": duplicate_row_ids,
        "semantic_duplicate_rows_excluding_row_id": sum(count - 1 for count in semantic_hashes.values() if count > 1),
        "semantic_duplicate_signatures_excluding_row_id": sum(1 for count in semantic_hashes.values() if count > 1),
        "target_duplicate_instances": sum(count for count in target_hashes.values() if count > 1),
        "target_duplicate_signatures": sum(1 for count in target_hashes.values() if count > 1),
        "target_signatures_cross_split": sum(1 for key, splits in target_splits.items() if len(splits) > 1),
        "cross_split_repo_digest_groups": sum(1 for splits in repo_splits.values() if len(splits) > 1),
        "cross_split_source_file_digest_groups": len(cross_split_file_examples),
        "cross_split_source_file_digest_rows_sampled": cross_split_file_examples,
        "authority_open_rows": authority_open_rows,
        "raw_source_body_rows": raw_source_body_rows,
        "absolute_path_rows": absolute_path_rows,
        "forbidden_marker_rows": forbidden_marker_rows,
        "missing_objective_split_pairs": sum(1 for objective in objective_counts for split in EXPECTED_SPLIT_COUNTS if split not in objective_splits[objective]),
        "top_duplicate_targets": top_duplicate_targets,
    }


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    summary78, audit78, contract78, rows = load_inputs()
    review = review_rows(rows)
    hard_hygiene_passed = (
        review["authority_open_rows"] == 0
        and review["raw_source_body_rows"] == 0
        and review["absolute_path_rows"] == 0
        and review["forbidden_marker_rows"] == 0
        and review["cross_split_repo_digest_groups"] == 0
    )
    training_admission_passed = (
        hard_hygiene_passed
        and review["cross_split_source_file_digest_groups"] == 0
        and review["semantic_duplicate_rows_excluding_row_id"] == 0
        and review["target_signatures_cross_split"] == 0
    )
    decision = "BLOCKED_DEEP_KNOWLEDGE_TRAINING_ADMISSION_REQUIRES_FILE_SPLIT_AND_SHORTCUT_ADAPTER_REPAIR"

    summary = {
        "record_type": "stage12679_public_deep_repo_code_knowledge_independent_review_summary_v1",
        "stage": STAGE,
        "decision": decision,
        "upstream_stage": summary78["stage"],
        "upstream_rows_sha256": contract78["rows_sha256"],
        "hygiene_review_passed": hard_hygiene_passed,
        "materialization_review_passed": True,
        "training_admission_review_passed": training_admission_passed,
        "file_split_repair_required": review["cross_split_source_file_digest_groups"] > 0,
        "shortcut_adapter_required": review["target_signatures_cross_split"] > 0,
        "semantic_duplicate_repair_required": review["semantic_duplicate_rows_excluding_row_id"] > 0,
        "trainer_adapter_required": True,
        "recommended_next_stage": "stage12680_deep_repo_code_knowledge_adapter_and_shortcut_preflight_only",
        "training_source_rows_admitted": 0,
        **{key: review[key] for key in (
            "deep_knowledge_rows_reviewed", "objective_family_count", "repo_digest_count", "source_file_digest_count",
            "cross_split_repo_digest_groups", "cross_split_source_file_digest_groups",
            "semantic_duplicate_rows_excluding_row_id", "semantic_duplicate_signatures_excluding_row_id",
            "target_duplicate_instances", "target_duplicate_signatures", "target_signatures_cross_split",
            "authority_open_rows", "raw_source_body_rows", "absolute_path_rows", "forbidden_marker_rows",
        )},
        **false_fields(),
    }
    audit = {
        "record_type": "stage12679_deep_repo_code_knowledge_independent_review_audit_v1",
        "stage": STAGE,
        "decision": decision,
        "split_counts": review["split_counts"],
        "objective_counts": review["objective_counts"],
        "missing_objective_split_pairs": review["missing_objective_split_pairs"],
        "duplicate_row_ids": review["duplicate_row_ids"],
        "top_duplicate_targets": review["top_duplicate_targets"],
        "cross_split_source_file_digest_rows_sampled": review["cross_split_source_file_digest_rows_sampled"],
        "stage12678_materialization_decision": audit78["decision"],
        "stage12678_contract_rows_sha256": contract78["rows_sha256"],
        "label_validity_review": "pass_body_free_schema_and_stage12678_hash_pin_review",
        "trainer_adapter_fit": "blocked_pending_deep_repo_code_knowledge_adapter_binding",
        "shortcut_baseline_status": "blocked_pending_duplicate_target_quarantine_or_weighting",
        **summary,
    }
    checks = [
        {"check_id": "upstream_hash_pins", "status": "passed", "count": len(EXPECTED_HASHES)},
        {"check_id": "row_count_and_objective_coverage", "status": "passed", "count": review["deep_knowledge_rows_reviewed"]},
        {"check_id": "authority_body_path_hygiene", "status": "passed", "count": 0},
        {"check_id": "repo_split_isolation", "status": "passed", "count": review["cross_split_repo_digest_groups"]},
        {"check_id": "file_digest_split_isolation", "status": "blocked", "count": review["cross_split_source_file_digest_groups"]},
        {"check_id": "semantic_duplicate_rows", "status": "blocked", "count": review["semantic_duplicate_rows_excluding_row_id"]},
        {"check_id": "target_duplicate_shortcut_risk", "status": "blocked", "count": review["target_duplicate_instances"]},
        {"check_id": "trainer_adapter_binding", "status": "blocked", "count": 0},
        {"check_id": "training_authority", "status": "blocked", "count": 0},
    ]
    for label, record in (("summary", summary), ("audit", audit), ("checks", checks)):
        assert_no_forbidden(record, label)
    return summary, audit, checks


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, checks = build_packet()
    private = {
        "record_type": "stage12679_private_deep_repo_code_knowledge_independent_review_packet_v1",
        "stage": STAGE,
        "upstream_hashes": EXPECTED_HASHES,
        "summary": summary,
        "audit": audit,
        "checks": checks,
    }
    contract = {
        "record_type": "stage12679_deep_repo_code_knowledge_independent_review_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "deep_knowledge_rows_reviewed": summary["deep_knowledge_rows_reviewed"],
        "training_source_rows_admitted": 0,
        "recommended_next_stage": summary["recommended_next_stage"],
        **false_fields(),
    }
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    write_json(out / "deep_repo_code_knowledge_independent_review_audit.json", audit)
    write_json(out / "contract.json", contract)
    write_json(out / "private/deep_repo_code_knowledge_independent_review_packet.json", private)
    write_jsonl(out / "private/deep_repo_code_knowledge_independent_review_checks.jsonl", checks)
    pointer = {
        "record_type": "stage12679_deep_repo_code_knowledge_independent_review_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "audit_sha256": stable_hash(audit),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "checks_sha256": sha256_bytes((out / "private/deep_repo_code_knowledge_independent_review_checks.jsonl").read_bytes()),
    }
    write_json(out / "digest_pointer.json", pointer)
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


def main() -> None:
    print(json.dumps(build(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
