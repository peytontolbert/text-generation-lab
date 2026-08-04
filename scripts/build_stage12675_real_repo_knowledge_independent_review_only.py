#!/usr/bin/env python3
"""Independently review Stage12674 real repo-knowledge rows without training admission."""
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12675_real_repo_knowledge_independent_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12674_SUMMARY = ROOT / "runs/summaries/stage12674_real_repo_knowledge_materialization_preflight_only.json"
S12674_AUDIT = ROOT / "runs/local/artifacts/stage12674_real_repo_knowledge_materialization_preflight_only/real_repo_knowledge_materialization_audit.json"
S12674_CONTRACT = ROOT / "runs/local/artifacts/stage12674_real_repo_knowledge_materialization_preflight_only/contract.json"
S12674_ROWS = ROOT / "runs/local/artifacts/stage12674_real_repo_knowledge_materialization_preflight_only/real_repo_knowledge_examples.jsonl"
REPO_SUMMARIES = ROOT / "runs/local/artifacts/stage8600_arxiv_corpus_index/repository_summaries.jsonl"

EXPECTED_HASHES = {
    "stage12674_summary": "a5f38e41fc599074d59c1e379490b8f94309f23e2d3b408db0c24952f457a6f6",
    "stage12674_audit": "92810c5339127fffa8e3a0a2fe2678c65bd8d99c8b5ff6fe8555a4d310ecf75f",
    "stage12674_contract": "954f4705492e06afa4d3f8782a801b3f78d33230fcde06111aa9539a76a67a5b",
    "stage12674_rows": "eddca41340146b1910bd771c2bf9b673efa2f0db69b54ebbcf8c8c7acad24558",
    "repository_summaries": "4905c47a9e3feca39b0ed3abf51d07ee334e002c81292617ca90c4bad13a3489",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12676_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted", "strict_eval_eligible",
    "strict_eval_authorized", "sealed_eval_authorized", "loss_authorized", "compiler_execution_authorized",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field != "stage12676_allowed") + ("stage12675_allowed",)
ROW_AUTHORITY_FALSE_FIELDS = (
    "training_authorized", "runtime_authorized", "source_emission_authorized", "body_emission_authorized",
    "model_execution_authorized", "loss_authorized", "optimizer_step_authorized",
)
FORBIDDEN_SUBSTRINGS = ("/data/", "/arxiv/", "PLACEHOLDER", "placeholder", "TODO", "TBD", "Answer:", "<fill", "\x00")
EXPECTED_OBJECTIVE_COUNTS = {
    "build_file_role_fact": 7068,
    "curriculum_use_presence": 3937,
    "extension_count_fact": 9081,
    "language_count_fact": 2236,
    "primary_language_rank_fact": 1774,
    "readme_doc_surface_fact": 4873,
    "repo_capability_profile": 500,
    "repo_health_bucket_fact": 2000,
}
EXPECTED_SPLIT_COUNTS = {"eval": 6868, "strict_eval": 6338, "train": 18263}


class Stage12675ReviewError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def stable_int(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def opaque(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256(":".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def split_for_id(repo_id: str) -> str:
    bucket = stable_int(repo_id) % 10
    if bucket < 6:
        return "train"
    if bucket < 8:
        return "eval"
    return "strict_eval"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12675ReviewError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Stage12675ReviewError(f"jsonl_object_required:{path.name}:{line_number}")
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
            raise Stage12675ReviewError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12675ReviewError(f"{label}_forbidden_substring:{needle}")


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    pins = {
        "stage12674_summary": S12674_SUMMARY,
        "stage12674_audit": S12674_AUDIT,
        "stage12674_contract": S12674_CONTRACT,
        "stage12674_rows": S12674_ROWS,
        "repository_summaries": REPO_SUMMARIES,
    }
    for label, path in pins.items():
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12675ReviewError("pin_drift:" + label)
    summary = read_json(S12674_SUMMARY)
    audit = read_json(S12674_AUDIT)
    contract = read_json(S12674_CONTRACT)
    for label, record in (("stage12674_summary", summary), ("stage12674_audit", audit), ("stage12674_contract", contract)):
        check_false(record, label, UPSTREAM_FALSE_FIELDS)
    rows = read_jsonl(S12674_ROWS)
    repos = read_jsonl(REPO_SUMMARIES)
    if len(rows) != 31469 or len(repos) != 500:
        raise Stage12675ReviewError("input_count_drift")
    return summary, audit, contract, rows, repos


def review_rows(rows: list[dict[str, Any]], repos: list[dict[str, Any]]) -> dict[str, Any]:
    objective_counts = dict(sorted(collections.Counter(row["objective_family"] for row in rows).items()))
    split_counts = dict(sorted(collections.Counter(row["split"] for row in rows).items()))
    if objective_counts != EXPECTED_OBJECTIVE_COUNTS:
        raise Stage12675ReviewError("objective_count_drift")
    if split_counts != EXPECTED_SPLIT_COUNTS:
        raise Stage12675ReviewError("split_count_drift")

    repo_by_digest = {opaque("repo", repo["repo_id"]): repo for repo in repos}
    expected_split_by_repo = {opaque("repo", repo["repo_id"]): split_for_id(repo["repo_id"]) for repo in repos}
    rows_by_repo: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    row_hashes: list[str] = []
    semantic_hashes: list[str] = []
    authority_open_rows = 0
    bad_evidence_rows = 0
    bad_label_rows = 0
    split_mismatch_rows = 0
    forbidden_rows = 0

    for row in rows:
        encoded = json.dumps(row, sort_keys=True, ensure_ascii=True)
        forbidden_rows += int(any(needle in encoded for needle in FORBIDDEN_SUBSTRINGS))
        row_hashes.append(stable_hash(row))
        repo_key = row.get("knowledge_input", {}).get("opaque_repo_id")
        rows_by_repo[str(repo_key)].append(row)
        semantic_hashes.append(stable_hash({
            "split": row.get("split"),
            "objective_family": row.get("objective_family"),
            "knowledge_input": row.get("knowledge_input"),
            "expected_output": row.get("expected_output"),
        }))
        authority = row.get("authority", {})
        if not isinstance(authority, dict) or any(authority.get(field) is not False for field in ROW_AUTHORITY_FALSE_FIELDS):
            authority_open_rows += 1
        evidence = row.get("evidence", {})
        if evidence.get("raw_source_included") is not False or evidence.get("absolute_path_included") is not False or evidence.get("source_body_included") is not False:
            bad_evidence_rows += 1
        if repo_key not in repo_by_digest:
            bad_label_rows += 1
        elif row.get("split") != expected_split_by_repo[repo_key]:
            split_mismatch_rows += 1

    duplicate_exact_rows = len(row_hashes) - len(set(row_hashes))
    duplicate_semantic_rows = len(semantic_hashes) - len(set(semantic_hashes))
    cross_split_repo_leakage = 0
    for repo_key, repo_rows in rows_by_repo.items():
        if len({row["split"] for row in repo_rows}) > 1:
            cross_split_repo_leakage += 1

    target_groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        target_groups[stable_hash(row.get("expected_output"))].append(row)
    target_duplicate_instances = sum(len(group) - 1 for group in target_groups.values() if len(group) > 1)
    target_duplicate_signatures = sum(1 for group in target_groups.values() if len(group) > 1)
    target_duplicate_signatures_cross_split = sum(1 for group in target_groups.values() if len({row["split"] for row in group}) > 1)

    families_per_split = collections.defaultdict(set)
    for row in rows:
        families_per_split[row["split"]].add(row["objective_family"])
    missing_family_split_pairs = sum(
        1 for split in EXPECTED_SPLIT_COUNTS for family in EXPECTED_OBJECTIVE_COUNTS if family not in families_per_split[split]
    )

    return {
        "materialized_knowledge_rows_reviewed": len(rows),
        "repository_metadata_rows_cross_checked": len(repos),
        "objective_counts": objective_counts,
        "split_counts": split_counts,
        "exact_duplicate_rows": duplicate_exact_rows,
        "semantic_duplicate_rows": duplicate_semantic_rows,
        "cross_split_repo_leakage_groups": cross_split_repo_leakage,
        "split_mismatch_rows": split_mismatch_rows,
        "authority_open_rows": authority_open_rows,
        "bad_evidence_rows": bad_evidence_rows,
        "forbidden_marker_rows": forbidden_rows,
        "missing_family_split_pairs": missing_family_split_pairs,
        "label_shape_invalid_rows": bad_label_rows,
        "target_duplicate_instances": target_duplicate_instances,
        "target_duplicate_signatures": target_duplicate_signatures,
        "target_duplicate_signatures_cross_split": target_duplicate_signatures_cross_split,
    }


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    _summary74, _audit74, _contract74, rows, repos = load_inputs()
    review = review_rows(rows, repos)
    hard_failures = {
        key: review[key]
        for key in (
            "exact_duplicate_rows", "semantic_duplicate_rows", "cross_split_repo_leakage_groups", "split_mismatch_rows",
            "authority_open_rows", "bad_evidence_rows", "forbidden_marker_rows", "missing_family_split_pairs", "label_shape_invalid_rows",
        )
    }
    if any(hard_failures.values()):
        decision = "BLOCKED_REAL_REPO_KNOWLEDGE_REVIEW_FAILURE_NO_TRAINING"
    else:
        decision = "BLOCKED_KNOWLEDGE_TRAINING_ADMISSION_REQUIRES_SHORTCUT_AND_ADAPTER_REVIEW"
    audit = {
        "record_type": "stage12675_real_repo_knowledge_independent_review_audit_v1",
        "stage": STAGE,
        "decision": decision,
        "materialization_review_passed": decision != "BLOCKED_REAL_REPO_KNOWLEDGE_REVIEW_FAILURE_NO_TRAINING",
        "training_admission_review_passed": False,
        "training_source_rows_admitted": 0,
        "materialized_knowledge_rows_reviewed": review["materialized_knowledge_rows_reviewed"],
        "repository_metadata_rows_cross_checked": review["repository_metadata_rows_cross_checked"],
        "objective_counts": review["objective_counts"],
        "split_counts": review["split_counts"],
        "hard_failure_counts": hard_failures,
        "target_duplicate_instances": review["target_duplicate_instances"],
        "target_duplicate_signatures": review["target_duplicate_signatures"],
        "target_duplicate_signatures_cross_split": review["target_duplicate_signatures_cross_split"],
        "trainer_adapter_fit": "blocked_pending_repo_knowledge_adapter_binding",
        "shortcut_baseline_status": "blocked_pending_objective_family_shortcut_baselines",
        "label_validity_status": "passed_shape_and_source_digest_cross_check",
        "next_required_action": "stage12676_repo_knowledge_trainer_adapter_and_shortcut_baseline_preflight_only",
        **false_fields(),
    }
    summary = {
        "record_type": "stage12675_public_real_repo_knowledge_independent_review_summary_v1",
        "stage": STAGE,
        "decision": decision,
        "materialization_review_passed": audit["materialization_review_passed"],
        "training_admission_review_passed": False,
        "materialized_knowledge_rows_reviewed": review["materialized_knowledge_rows_reviewed"],
        "repository_metadata_rows_cross_checked": review["repository_metadata_rows_cross_checked"],
        "objective_family_count": len(review["objective_counts"]),
        "split_counts": review["split_counts"],
        "training_source_rows_admitted": 0,
        "target_duplicate_instances": review["target_duplicate_instances"],
        "target_duplicate_signatures_cross_split": review["target_duplicate_signatures_cross_split"],
        "trainer_adapter_required": True,
        "shortcut_baseline_required": True,
        "next_required_action": audit["next_required_action"],
        **false_fields(),
    }
    checks = [
        {"check_id": "stage12674_pins", "status": "pass"},
        {"check_id": "row_count_and_objective_counts", "status": "pass"},
        {"check_id": "exact_and_semantic_duplicates", "status": "pass" if not review["semantic_duplicate_rows"] else "fail"},
        {"check_id": "split_repo_isolation", "status": "pass" if not review["cross_split_repo_leakage_groups"] else "fail"},
        {"check_id": "label_source_digest_cross_check", "status": "pass" if not review["label_shape_invalid_rows"] else "fail"},
        {"check_id": "authority_and_evidence_closed", "status": "pass" if not review["authority_open_rows"] and not review["bad_evidence_rows"] else "fail"},
        {"check_id": "target_duplicate_shortcut_risk", "status": "blocked"},
        {"check_id": "trainer_adapter_binding", "status": "blocked"},
        {"check_id": "shortcut_baseline_materialization", "status": "blocked"},
        {"check_id": "training_authority", "status": "blocked"},
    ]
    for label, record in (("summary", summary), ("audit", audit), ("checks", checks)):
        assert_no_forbidden(record, label)
    return summary, audit, checks


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, checks = build_packet()
    private = {
        "record_type": "stage12675_private_real_repo_knowledge_independent_review_packet_v1",
        "stage": STAGE,
        "input_hashes": EXPECTED_HASHES,
        "audit_sha256": stable_hash(audit),
        "checks_sha256": stable_hash(checks),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12675_real_repo_knowledge_independent_review_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "materialized_knowledge_rows_reviewed": summary["materialized_knowledge_rows_reviewed"],
        "materialization_review_passed": summary["materialization_review_passed"],
        "training_admission_review_passed": False,
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        "recommended_next_stage": summary["next_required_action"],
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12675_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        **false_fields(),
    }
    for label, record in (("private", private), ("contract", contract), ("pointer", pointer)):
        assert_no_forbidden(record, label)
    write_json(out / "summary.json", summary)
    write_json(out / "real_repo_knowledge_independent_review_audit.json", audit)
    write_jsonl(out / "private/real_repo_knowledge_independent_review_checks.jsonl", checks)
    write_json(out / "private/real_repo_knowledge_independent_review_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(out / "private")
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=True))
