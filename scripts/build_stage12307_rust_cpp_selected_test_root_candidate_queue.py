#!/usr/bin/env python3
"""Build Stage12307 Rust/C++ selected-test root-candidate queue.

This stage emits queue records only. It does not render examples, admit rows,
authorize training, or make strict/eval claims.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12307_rust_cpp_selected_test_root_candidate_queue"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

PATHS = {
    "stage12121_rust_summary": ROOT / "runs/summaries/stage12121_rust_verifier_ready_candidate_plan.json",
    "stage12121_rust_plan": ROOT
    / "runs/local/artifacts/stage12121_rust_verifier_ready_candidate_plan/rust_verifier_ready_candidate_plan.jsonl",
    "stage12121_cpp_summary": ROOT / "runs/summaries/stage12121_cpp_verifier_ready_candidate_plan.json",
    "stage12121_cpp_plan": ROOT
    / "runs/local/artifacts/stage12121_cpp_verifier_ready_candidate_plan/cpp_verifier_ready_candidate_plan.jsonl",
    "stage12130_summary": ROOT / "runs/summaries/stage12130_selected_test_train_support_package.json",
    "stage12130_rows": ROOT / "runs/local/artifacts/stage12130_selected_test_train_support_package/train_support_rows.jsonl",
    "stage12130_audit": ROOT
    / "runs/local/artifacts/stage12130_selected_test_train_support_package/train_support_package_audit.json",
    "stage12144_summary": ROOT / "runs/summaries/stage12144_rust_hydrated_selected_test_success_package.json",
    "stage12144_records": ROOT
    / "runs/local/artifacts/stage12144_rust_hydrated_selected_test_success_package/rust_hydrated_selected_test_successes.jsonl",
    "stage12146_summary": ROOT / "runs/summaries/stage12146_selected_test_supply_rollup.json",
    "stage12146_rollup": ROOT
    / "runs/local/artifacts/stage12146_selected_test_supply_rollup/selected_test_supply_rollup.jsonl",
    "stage12150_summary": ROOT / "runs/summaries/stage12150_corrected_selected_test_materialization_audit.json",
    "stage12150_audit": ROOT
    / "runs/local/artifacts/stage12150_corrected_selected_test_materialization_audit/row_materialization_blocker_audit.json",
    "stage12305_summary": ROOT / "runs/summaries/stage12305_canonical_root_candidate_materialization_queue.json",
}

REQUIRED_HASH_CLASSES = ("commit_sha", "verifier_command_or_log", "source_hash", "test_hash")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def stable_id(*parts: str, n: int = 16) -> str:
    return hashlib.sha256("::".join(parts).encode("utf-8")).hexdigest()[:n]


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            row["_source_line_no"] = line_no
            rows.append(row)
    return rows


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def by_repo(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        repo = row.get("repo_family")
        if repo:
            out[str(repo)] = row
    return out


def rows_by_repo(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        repo = row.get("repo_family")
        if repo:
            out[str(repo)].append(row)
    return dict(out)


def extract_stage12305_sets(stage12305: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    queues = stage12305.get("materialization_queue") if isinstance(stage12305, dict) else []
    selected: dict[str, dict[str, list[str]]] = {
        "rust": {"ready_or_seed_repos": [], "next_hydration_repos": []},
        "c_cpp": {"ready_or_seed_repos": [], "next_hydration_repos": []},
    }
    for queue in queues or []:
        qid = str(queue.get("queue_id") or "")
        if qid == "Q2_external_rust_selected_test_transition_roots":
            selected["rust"]["ready_or_seed_repos"] = list(queue.get("ready_or_seed_repos") or [])
            selected["rust"]["next_hydration_repos"] = list(queue.get("next_hydration_repos") or [])
        if qid == "Q3_external_cpp_selected_test_transition_roots":
            selected["c_cpp"]["ready_or_seed_repos"] = list(queue.get("ready_or_seed_repos") or [])
            selected["c_cpp"]["next_hydration_repos"] = list(queue.get("next_hydration_repos") or [])
    return selected


def evidence_refs_from_stage12130(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "commit_sha": None,
            "selected_test_ids": [],
            "verifier_refs": [],
            "source_hash_refs": [],
            "test_hash_refs": [],
            "semantic_task_count": 0,
            "semantic_option_counts": [],
        }
    first = rows[0]
    source = first.get("standalone_projection_source") or {}
    evidence_refs = list(source.get("evidence_refs") or [])
    source_hash_refs = list(source.get("source_hash_summary") or [])
    test_hash_refs = list(source.get("test_hash_summary") or [])
    verifier_refs = [
        item
        for item in evidence_refs
        if isinstance(item, str) and ("command_logs/" in item or "ctest" in item or "verifier" in item)
    ]
    selected = source.get("selected_test_summary") or {}
    selected_ids = list(selected.get("sample") or [])
    option_counts = []
    for row in rows:
        options = row.get("opaque_options")
        if isinstance(options, list):
            option_counts.append(len(options))
    return {
        "commit_sha": source.get("commit_sha") or first.get("commit_sha"),
        "selected_test_ids": selected_ids,
        "verifier_refs": verifier_refs,
        "source_hash_refs": source_hash_refs,
        "test_hash_refs": test_hash_refs,
        "semantic_task_count": len({str(row.get("task_type")) for row in rows if row.get("task_type")}),
        "semantic_option_counts": option_counts,
    }


def evidence_refs_from_rust_hydration(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {
            "commit_sha": None,
            "selected_test_ids": [],
            "verifier_refs": [],
            "source_hash_refs": [],
            "test_hash_refs": [],
            "semantic_task_count": 0,
            "semantic_option_counts": [],
        }
    return {
        "commit_sha": row.get("commit_sha"),
        "selected_test_ids": list(row.get("selected_test_ids") or []),
        "verifier_refs": [row.get("selected_test_command")] if row.get("selected_test_command") else [],
        "source_hash_refs": [],
        "test_hash_refs": [],
        "semantic_task_count": 0,
        "semantic_option_counts": [],
    }


def audit_info(repo: str, language: str, stage12150: dict[str, Any]) -> dict[str, Any]:
    if not stage12150:
        return {"present": False, "root_key": None, "semantic_diversity": None, "blockers": ["stage12150_audit_missing"]}
    if language == "rust":
        needle = repo.replace("/", "_").replace("-", "_")
        for key, info in (stage12150.get("per_root_semantic_diversity") or {}).items():
            if needle in key:
                return {
                    "present": True,
                    "root_key": key,
                    "semantic_diversity": info,
                    "blockers": [],
                }
    return {
        "present": True,
        "root_key": None,
        "semantic_diversity": None,
        "blockers": [],
    }


def missing_fields(evidence: dict[str, Any], needs_candidate_rewrite: bool, audit: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not evidence.get("commit_sha"):
        missing.append("commit_sha")
    if not evidence.get("verifier_refs"):
        missing.append("selected_verifier_command_or_log_ref")
    if not evidence.get("source_hash_refs"):
        missing.append("source_hash_refs")
    if not evidence.get("test_hash_refs"):
        missing.append("test_hash_refs")
    if not evidence.get("selected_test_ids"):
        missing.append("selected_test_ids")
    if needs_candidate_rewrite:
        missing.append("canonical_candidate_set_rewrite")
    if audit.get("blockers"):
        missing.append("stage12150_semantic_audit")
    return sorted(set(missing))


def candidate_blockers(
    language: str,
    status_bucket: str,
    evidence: dict[str, Any],
    audit: dict[str, Any],
    stage12130_backed: bool,
) -> list[str]:
    blockers: list[str] = []
    if status_bucket == "next_hydration":
        blockers.extend(
            [
                "not_hydrated",
                "missing_executed_selected_test_log",
                "missing_commit_sha",
                "missing_source_test_hashes",
                "candidate_set_not_materialized",
            ]
        )
    if language == "rust" and status_bucket == "ready_or_seed":
        if not audit.get("semantic_diversity"):
            blockers.append("stage12150_root_semantic_diversity_not_found")
        if not evidence.get("source_hash_refs") or not evidence.get("test_hash_refs"):
            blockers.append("hash_refs_not_present_in_stage12144_summary_require_capture_or_stage12150_input_audit_trace")
    if language == "c_cpp" and stage12130_backed:
        blockers.append("stage12130_train_support_rows_are_not_canonical_roots")
        blockers.append("canonical_task_specific_semantic_rewrite_required")
    if evidence.get("semantic_option_counts") and min(evidence["semantic_option_counts"]) < 2:
        blockers.append("singleton_candidate_set")
    blockers.extend(audit.get("blockers") or [])
    return sorted(set(blockers))


def build_record(
    *,
    repo: str,
    language: str,
    status_bucket: str,
    plan: dict[str, Any] | None,
    rollup: dict[str, Any] | None,
    rust_hydration: dict[str, Any] | None,
    stage12130_rows: list[dict[str, Any]],
    stage12150: dict[str, Any],
) -> dict[str, Any]:
    stage12130_backed = bool(stage12130_rows)
    evidence = (
        evidence_refs_from_stage12130(stage12130_rows)
        if stage12130_backed
        else evidence_refs_from_rust_hydration(rust_hydration)
    )
    audit = audit_info(repo, language, stage12150)
    needs_candidate_rewrite = language == "c_cpp" and stage12130_backed
    missing = missing_fields(evidence, needs_candidate_rewrite, audit)
    blockers = candidate_blockers(language, status_bucket, evidence, audit, stage12130_backed)
    canonical_root_id = f"{STAGE}::{language}::{repo.replace('/', '__').replace('-', '_')}"
    readiness = "next_hydration_required"
    if status_bucket == "ready_or_seed" and language == "rust" and rust_hydration:
        readiness = "ready_seed_selected_test_executed_semantic_audit_trace_present"
    if status_bucket == "ready_or_seed" and language == "c_cpp" and stage12130_backed:
        readiness = "seed_backed_by_stage12130_requires_canonical_rewrite"
    if status_bucket == "ready_or_seed" and not rust_hydration and not stage12130_backed:
        readiness = "seed_listed_but_required_artifacts_missing"

    source_refs = []
    if plan:
        source_refs.append(
            {
                "artifact": rel(PATHS["stage12121_rust_plan" if language == "rust" else "stage12121_cpp_plan"]),
                "record_selector": {"repo_family": repo, "queue_id": plan.get("queue_id")},
            }
        )
    if rollup:
        source_refs.append(
            {
                "artifact": rel(PATHS["stage12146_rollup"]),
                "record_selector": {"repo_family": repo, "root_id": rollup.get("root_id")},
            }
        )
    if rust_hydration:
        source_refs.append(
            {
                "artifact": rel(PATHS["stage12144_records"]),
                "record_selector": {"repo_family": repo, "queue_id": rust_hydration.get("queue_id")},
            }
        )
    if stage12130_backed:
        source_refs.append(
            {
                "artifact": rel(PATHS["stage12130_rows"]),
                "record_selector": {
                    "repo_family": repo,
                    "row_count": len(stage12130_rows),
                    "root_id": stage12130_rows[0].get("root_id"),
                },
            }
        )
    if stage12150:
        source_refs.append(
            {
                "artifact": rel(PATHS["stage12150_audit"]),
                "record_selector": {"root_key": audit.get("root_key")},
            }
        )

    return {
        "record_type": "canonical_root_candidate_queue_record",
        "canonical_root_candidate_id": canonical_root_id,
        "queue_record_id": f"stage12307::{stable_id(language, repo, status_bucket)}",
        "repo_family": repo,
        "language_family": language,
        "status_bucket": status_bucket,
        "readiness_status": readiness,
        "source_artifact_refs": source_refs,
        "stage12121_plan": {
            "queue_id": (plan or {}).get("queue_id"),
            "canonical_remote": (plan or {}).get("canonical_remote"),
            "expected_verifier_scope": (plan or {}).get("expected_verifier_scope"),
            "proposed_no_install_commands": (plan or {}).get("proposed_no_install_commands") or [],
            "dependency_risk": (plan or {}).get("dependency_risk"),
        },
        "stage12146_rollup": {
            "status": (rollup or {}).get("status"),
            "root_id": (rollup or {}).get("root_id"),
            "selected_test_anchor": bool((rollup or {}).get("selected_test_anchor")),
            "verifier_anchor": bool((rollup or {}).get("verifier_anchor")),
            "train_support_only": bool((rollup or {}).get("train_support_only")),
        },
        "required_hashes": {
            "required_classes": list(REQUIRED_HASH_CLASSES),
            "commit_sha": evidence.get("commit_sha"),
            "verifier_command_or_log_refs": evidence.get("verifier_refs") or [],
            "source_hash_refs": evidence.get("source_hash_refs") or [],
            "test_hash_refs": evidence.get("test_hash_refs") or [],
            "selected_test_ids": evidence.get("selected_test_ids") or [],
        },
        "candidate_set": {
            "semantic_task_count": evidence.get("semantic_task_count"),
            "semantic_option_counts": evidence.get("semantic_option_counts"),
            "stage12150_semantic_diversity": audit.get("semantic_diversity"),
            "non_singleton_required": True,
            "canonical_rewrite_required": needs_candidate_rewrite,
            "blockers": blockers,
        },
        "missing_fields": missing,
        "admission_fields": {
            "admission_level": "queue_only_no_admission",
            "canonical_countable": False,
            "row_admitted": False,
            "training_allowed": False,
            "strict_eval_eligible": False,
            "eval_claim_allowed": False,
            "source_heldout_admissible": False,
            "requires_separate_admission_stage": True,
        },
        "claim_boundary": "Queue record only: no training rows, no strict/eval claim, no external performance claim.",
    }


def main() -> None:
    stage12305 = read_json(PATHS["stage12305_summary"], {})
    selected_sets = extract_stage12305_sets(stage12305)
    rust_plan = by_repo(read_jsonl(PATHS["stage12121_rust_plan"]))
    cpp_plan = by_repo(read_jsonl(PATHS["stage12121_cpp_plan"]))
    rollup = by_repo(read_jsonl(PATHS["stage12146_rollup"]))
    rust_hydration = by_repo(read_jsonl(PATHS["stage12144_records"]))
    stage12130 = rows_by_repo(read_jsonl(PATHS["stage12130_rows"]))
    stage12150 = read_json(PATHS["stage12150_audit"], read_json(PATHS["stage12150_summary"], {}))

    records: list[dict[str, Any]] = []
    for language, plan_map in (("rust", rust_plan), ("c_cpp", cpp_plan)):
        for bucket in ("ready_or_seed_repos", "next_hydration_repos"):
            status_bucket = "ready_or_seed" if bucket == "ready_or_seed_repos" else "next_hydration"
            for repo in selected_sets[language][bucket]:
                records.append(
                    build_record(
                        repo=repo,
                        language=language,
                        status_bucket=status_bucket,
                        plan=plan_map.get(repo),
                        rollup=rollup.get(repo),
                        rust_hydration=rust_hydration.get(repo),
                        stage12130_rows=stage12130.get(repo, []),
                        stage12150=stage12150,
                    )
                )

    records.sort(key=lambda r: (r["language_family"], r["status_bucket"], r["repo_family"]))

    source_status = {
        name: {
            "path": rel(path),
            "exists": path.exists(),
            "jsonl_rows": len(read_jsonl(path)) if path.suffix == ".jsonl" and path.exists() else None,
        }
        for name, path in PATHS.items()
    }
    readiness_counts = Counter(record["readiness_status"] for record in records)
    blocker_counts = Counter(
        blocker for record in records for blocker in record["candidate_set"]["blockers"]
    )
    missing_counts = Counter(field for record in records for field in record["missing_fields"])

    summary = {
        "stage": STAGE,
        "created_at_utc": utc_now(),
        "decision": "rust_cpp_selected_test_root_candidate_queue_emitted_fail_closed",
        "claim_boundary": "Canonical root-candidate queue records only. No training rows are emitted or admitted.",
        "training_allowed": False,
        "strict_eval_eligible": False,
        "eval_claim_allowed": False,
        "source_heldout_admissible": False,
        "records_path": rel(OUT / "canonical_root_candidate_queue_records.jsonl"),
        "record_count": len(records),
        "counts_by_language": dict(Counter(record["language_family"] for record in records)),
        "counts_by_status_bucket": dict(Counter(record["status_bucket"] for record in records)),
        "counts_by_readiness_status": dict(readiness_counts),
        "candidate_set_blocker_counts": dict(blocker_counts),
        "missing_field_counts": dict(missing_counts),
        "source_status": source_status,
        "inputs": {
            "stage12121_rust_cpp_verifier_ready_plans": [
                rel(PATHS["stage12121_rust_plan"]),
                rel(PATHS["stage12121_cpp_plan"]),
            ],
            "stage12146_selected_test_rollup": rel(PATHS["stage12146_rollup"]),
            "stage12130_package_audit": [rel(PATHS["stage12130_rows"]), rel(PATHS["stage12130_audit"])],
            "stage12144_summary_if_present": rel(PATHS["stage12144_summary"]),
            "stage12150_audit_if_present": rel(PATHS["stage12150_audit"]),
            "stage12305_queue_source": rel(PATHS["stage12305_summary"]),
        },
        "records": records,
        "next_required_stage": "Hydrate blocked repos and rewrite ready/seed records into canonical_root_candidate records only after all required hashes and non-singleton candidate-set gates are explicit.",
    }

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "canonical_root_candidate_queue_records.jsonl", records)
    write_json(OUT / "canonical_root_candidate_queue.json", summary)
    (OUT / "STAGE12307_RUST_CPP_SELECTED_TEST_ROOT_CANDIDATE_QUEUE.md").write_text(
        "# Stage12307 Rust/C++ Selected-Test Root Candidate Queue\n\n"
        "Fail closed: this stage emits queue records only. It emits no training rows and makes no strict/eval claims.\n\n"
        f"- Records: {len(records)}\n"
        f"- Rust records: {sum(1 for r in records if r['language_family'] == 'rust')}\n"
        f"- C/C++ records: {sum(1 for r in records if r['language_family'] == 'c_cpp')}\n"
        f"- Ready/seed records: {sum(1 for r in records if r['status_bucket'] == 'ready_or_seed')}\n"
        f"- Next hydration records: {sum(1 for r in records if r['status_bucket'] == 'next_hydration')}\n",
        encoding="utf-8",
    )
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
