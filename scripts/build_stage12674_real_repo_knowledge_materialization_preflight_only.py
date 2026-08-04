#!/usr/bin/env python3
"""Materialize tens-of-thousands of source-backed repo knowledge rows.

This is a preflight-only compiler. It uses Stage8600 repository metadata and
Stage12673 inventory pins to build structured knowledge examples without raw
source bodies, absolute source paths, runtime authority, or training authority.
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12674_real_repo_knowledge_materialization_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12673_SUMMARY = ROOT / "runs/summaries/stage12673_real_knowledge_source_expansion_inventory_preflight_only.json"
STAGE8600_SUMMARY = ROOT / "runs/summaries/stage8600_reconstructed_arxiv_corpus_index_and_maintainer_registry.json"
STAGE8601_SUMMARY = ROOT / "runs/summaries/stage8601_reconstructed_arxiv_repo_capability_and_graph_seed.json"
STAGE8671_SUMMARY = ROOT / "runs/summaries/stage8671_dense_hybrid_retrieval_baseline.json"
STAGE8715_SUMMARY = ROOT / "runs/summaries/stage8715_repo_graph_encoder_graph_attachment.json"
REPOSITORY_SUMMARIES = ROOT / "runs/local/artifacts/stage8600_arxiv_corpus_index/repository_summaries.jsonl"
CANDIDATE_TRAINING_SOURCES = ROOT / "runs/local/artifacts/stage8600_arxiv_corpus_index/candidate_training_sources.json"

EXPECTED_HASHES = {
    "stage12673_summary": "2987b41c16e6c6cfe9b5d778686ef3747dd09a339093f3a92d2ebabea6adfafd",
    "stage8600_summary": "a6d9431aee934170c58b61d3597eb5d497a42a5e4bce5f96b7f10a56ce9dc44d",
    "stage8601_summary": "454e83ca2c7b750ef18b25df325b9beff5f600ba4ec5225a7e0bbe28631f8654",
    "stage8671_summary": "2f21e4b99e9bf848d7d49791c4e2d605e9833f2462426180ee6abf29b9230c89",
    "stage8715_summary": "792368aeae2ab93c99934c61f55a6c64c46fdc878de8876d7293cbdb80fe5bb8",
    "repository_summaries": "4905c47a9e3feca39b0ed3abf51d07ee334e002c81292617ca90c4bad13a3489",
    "candidate_training_sources": "959549cb024a8c26db18b1b4a040027b9b471395f6fd7f8ee5cfb00e960ff6ad",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12675_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted", "strict_eval_eligible",
    "strict_eval_authorized", "sealed_eval_authorized", "loss_authorized", "compiler_execution_authorized",
)

UPSTREAM_FALSE_FIELDS = (
    "implementation_ready", "stage12674_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
)

AUTHORITY_CLOSED = {
    "training_authorized": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "model_execution_authorized": False,
    "loss_authorized": False,
    "optimizer_step_authorized": False,
}

FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "PLACEHOLDER", "placeholder", "TODO", "TBD", "Answer:", "<fill", "\x00",
)

BUILD_FAMILY_BY_FILE = {
    "pyproject.toml": "python_packaging",
    "setup.py": "python_packaging",
    "setup.cfg": "python_packaging",
    "requirements.txt": "python_requirements",
    "Pipfile": "python_packaging",
    "poetry.lock": "python_packaging",
    "Cargo.toml": "rust_cargo",
    "Cargo.lock": "rust_cargo",
    "package.json": "node_package",
    "package-lock.json": "node_package",
    "pnpm-lock.yaml": "node_package",
    "yarn.lock": "node_package",
    "CMakeLists.txt": "cmake",
    "Makefile": "make",
    "meson.build": "meson",
    "go.mod": "go_modules",
    "go.sum": "go_modules",
    "pom.xml": "jvm_maven",
    "build.gradle": "jvm_gradle",
    "build.gradle.kts": "jvm_gradle",
}


class Stage12674KnowledgeMaterializationError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12674KnowledgeMaterializationError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Stage12674KnowledgeMaterializationError(f"jsonl_object_required:{path.name}:{line_number}")
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
            raise Stage12674KnowledgeMaterializationError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12674KnowledgeMaterializationError(f"{label}_forbidden_substring:{needle}")


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


def size_bucket(scanned_files: int) -> str:
    if scanned_files < 100:
        return "tiny"
    if scanned_files < 1000:
        return "small"
    if scanned_files < 5000:
        return "medium"
    return "large"


def count_bucket(count: int) -> str:
    if count == 0:
        return "none"
    if count < 10:
        return "tiny"
    if count < 100:
        return "small"
    if count < 1000:
        return "medium"
    return "large"


def depth_bucket(path_text: str) -> str:
    depth = len([part for part in path_text.split("/") if part])
    if depth <= 1:
        return "root"
    if depth <= 3:
        return "shallow"
    return "deep"


def directory_role(path_text: str) -> str:
    parts = [part.lower() for part in path_text.split("/")[:-1]]
    joined = "/".join(parts)
    if not parts:
        return "repo_root"
    if any(token in joined for token in ("test", "spec")):
        return "test_area"
    if any(token in joined for token in ("doc", "guide", "tutorial", "lesson", "example")):
        return "documentation_or_example_area"
    if any(token in joined for token in ("config", ".github", ".devcontainer", "ci")):
        return "configuration_area"
    return "nested_project_area"


def suffix_of(path_text: str) -> str:
    suffix = Path(path_text).suffix
    return suffix if suffix else "<none>"


def build_family(path_text: str) -> str:
    return BUILD_FAMILY_BY_FILE.get(Path(path_text).name, "other_build")


def base_input(repo: Mapping[str, Any], objective: str, slot: str, ordinal: int) -> dict[str, Any]:
    repo_id = str(repo["repo_id"])
    return {
        "opaque_repo_id": opaque("repo", repo_id),
        "objective_family": objective,
        "fact_slot": slot,
        "fact_ordinal": ordinal,
        "repo_size_bucket": size_bucket(int(repo.get("scanned_files", 0))),
        "maintainer_score_bucket": count_bucket(int(repo.get("maintainer_usefulness_score", 0))),
        "scan_truncated": bool(repo.get("scan_truncated", False)),
    }


def row(row_index: int, repo: Mapping[str, Any], objective: str, slot: str, ordinal: int, target: Mapping[str, Any], extra_input: Mapping[str, Any] | None = None) -> dict[str, Any]:
    repo_id = str(repo["repo_id"])
    knowledge_input = base_input(repo, objective, slot, ordinal)
    if extra_input:
        knowledge_input.update(extra_input)
    record = {
        "row_id": f"stage12674_real_repo_knowledge_{row_index:06d}",
        "split": split_for_id(repo_id),
        "objective_family": objective,
        "knowledge_input": knowledge_input,
        "expected_output": dict(target),
        "evidence": {
            "source_stage": "stage8600_repository_metadata",
            "repo_digest": opaque("source_repo", repo_id),
            "raw_source_included": False,
            "absolute_path_included": False,
            "source_body_included": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "quality": {
            "label_source": "deterministic_metadata_compiler",
            "requires_independent_review_before_training": True,
            "template_marker_free": True,
        },
    }
    assert_no_forbidden(record, "knowledge_row")
    return record


def load_inputs() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    pins = {
        "stage12673_summary": STAGE12673_SUMMARY,
        "stage8600_summary": STAGE8600_SUMMARY,
        "stage8601_summary": STAGE8601_SUMMARY,
        "stage8671_summary": STAGE8671_SUMMARY,
        "stage8715_summary": STAGE8715_SUMMARY,
        "repository_summaries": REPOSITORY_SUMMARIES,
        "candidate_training_sources": CANDIDATE_TRAINING_SOURCES,
    }
    for label, path in pins.items():
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12674KnowledgeMaterializationError("pin_drift:" + label)

    upstream = read_json(STAGE12673_SUMMARY)
    check_false(upstream, "stage12673_summary", UPSTREAM_FALSE_FIELDS)
    if int(upstream.get("current_knowledge_seed_rows", -1)) != 258:
        raise Stage12674KnowledgeMaterializationError("seed_count_drift")
    if int(upstream.get("candidate_source_rows_inventory_total", -1)) != 1646:
        raise Stage12674KnowledgeMaterializationError("inventory_count_drift")

    repo_rows = read_jsonl(REPOSITORY_SUMMARIES)
    if len(repo_rows) != 500:
        raise Stage12674KnowledgeMaterializationError("repo_count_drift")
    candidate_sources = read_json(CANDIDATE_TRAINING_SOURCES)
    check_false(candidate_sources["authority"], "candidate_training_sources", (
        "body_emission_authorized", "source_emission_authorized", "runtime_authorized", "model_execution_authorized_next",
        "decoder_ce_training_authorized_next", "gemma_execution_authorized_next", "harness_execution_authorized_next",
        "scoring_authorized_next", "controller_complete_merge_authorized_next", "promotion_ready",
    ))
    return upstream, sorted(repo_rows, key=lambda item: (-int(item.get("maintainer_usefulness_score", 0)), str(item["repo_id"])))


def materialize_rows(repo_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(repo: Mapping[str, Any], objective: str, slot: str, ordinal: int, target: Mapping[str, Any], extra_input: Mapping[str, Any] | None = None) -> None:
        rows.append(row(len(rows), repo, objective, slot, ordinal, target, extra_input))

    for repo in repo_rows:
        languages = sorted((repo.get("language_file_counts") or {}).items())
        primary_languages = list(repo.get("likely_primary_languages") or [])
        build_files = list(repo.get("build_files") or [])
        readme_files = list(repo.get("readme_files") or [])
        extensions = sorted((repo.get("extension_counts") or {}).items())
        uses = list(repo.get("recommended_curriculum_uses") or [])

        add(repo, "repo_capability_profile", "capability_profile", 0, {
            "language_family_count": len(languages),
            "primary_language_count": len(primary_languages),
            "build_file_count": len(build_files),
            "readme_file_count": len(readme_files),
            "recommended_curriculum_use_count": len(uses),
            "has_tests": int(repo.get("test_files", 0)) > 0,
            "has_docs": int(repo.get("doc_files", 0)) > 0,
        })
        for ordinal, use in enumerate(uses):
            add(repo, "curriculum_use_presence", "recommended_curriculum_use", ordinal, {
                "curriculum_use": use,
                "present": True,
            })
        for ordinal, (language, count) in enumerate(languages):
            add(repo, "language_count_fact", "language_family", ordinal, {
                "language_family": language,
                "file_count_bucket": count_bucket(int(count)),
                "present": int(count) > 0,
            })
        for ordinal, language in enumerate(primary_languages):
            add(repo, "primary_language_rank_fact", "primary_language_rank", ordinal, {
                "language_family": language,
                "rank": ordinal,
            })
        for ordinal, path_text in enumerate(build_files):
            add(repo, "build_file_role_fact", "build_file", ordinal, {
                "build_system_family": build_family(path_text),
                "file_suffix": suffix_of(path_text),
                "depth_bucket": depth_bucket(path_text),
                "directory_role": directory_role(path_text),
            }, {"opaque_file_id": opaque("file", repo["repo_id"], "build", ordinal, path_text)})
        for ordinal, path_text in enumerate(readme_files):
            add(repo, "readme_doc_surface_fact", "readme_doc_file", ordinal, {
                "file_suffix": suffix_of(path_text),
                "depth_bucket": depth_bucket(path_text),
                "directory_role": directory_role(path_text),
            }, {"opaque_file_id": opaque("file", repo["repo_id"], "readme", ordinal, path_text)})
        for ordinal, (extension, count) in enumerate(extensions):
            add(repo, "extension_count_fact", "extension", ordinal, {
                "extension": extension,
                "file_count_bucket": count_bucket(int(count)),
                "present": int(count) > 0,
            })
        health_facts = (
            ("repo_size_bucket", size_bucket(int(repo.get("scanned_files", 0)))),
            ("test_file_count_bucket", count_bucket(int(repo.get("test_files", 0)))),
            ("doc_file_count_bucket", count_bucket(int(repo.get("doc_files", 0)))),
            ("scan_truncated", bool(repo.get("scan_truncated", False))),
        )
        for ordinal, (name, value) in enumerate(health_facts):
            add(repo, "repo_health_bucket_fact", name, ordinal, {"health_fact": name, "value": value})

    if len(rows) < 30000:
        raise Stage12674KnowledgeMaterializationError("materialized_rows_below_tens_of_thousands")
    if any(record["expected_output"] == {} for record in rows):
        raise Stage12674KnowledgeMaterializationError("empty_target")
    return rows


def summarize(rows: list[dict[str, Any]], upstream: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    split_counts = dict(sorted(collections.Counter(row["split"] for row in rows).items()))
    objective_counts = dict(sorted(collections.Counter(row["objective_family"] for row in rows).items()))
    row_hashes = [stable_hash(row) for row in rows]
    duplicate_rows = len(row_hashes) - len(set(row_hashes))
    authority_open_rows = sum(1 for record in rows if any(record["authority"].values()))
    placeholder_hits = sum(1 for record in rows if any(needle in json.dumps(record, sort_keys=True, ensure_ascii=True) for needle in FORBIDDEN_SUBSTRINGS))
    source_body_rows = sum(1 for record in rows if record["evidence"]["source_body_included"] or record["evidence"]["absolute_path_included"])
    if duplicate_rows or authority_open_rows or placeholder_hits or source_body_rows:
        raise Stage12674KnowledgeMaterializationError("row_quality_gate_failed")

    audit = {
        "record_type": "stage12674_real_repo_knowledge_materialization_audit_v1",
        "stage": STAGE,
        "decision": "REAL_REPO_KNOWLEDGE_ROWS_MATERIALIZED_PRETRAINING_REVIEW_REQUIRED",
        "upstream_inventory_rows": int(upstream["candidate_source_rows_inventory_total"]),
        "current_reviewed_seed_rows": int(upstream["current_knowledge_seed_rows"]),
        "repository_metadata_rows_consumed": 500,
        "materialized_knowledge_rows": len(rows),
        "objective_counts": objective_counts,
        "split_counts": split_counts,
        "duplicate_row_hashes": duplicate_rows,
        "authority_open_rows": authority_open_rows,
        "template_marker_or_forbidden_hits": placeholder_hits,
        "raw_source_body_rows": source_body_rows,
        "absolute_path_rows": source_body_rows,
        "training_source_rows_admitted": 0,
        "recommended_next_stage": "stage12675_real_repo_knowledge_independent_review_only",
        "blockers_to_training_admission": [
            "independent_review_of_stage12674_rows",
            "split_endpoint_dedup_and_shortcut_audits",
            "label_validity_review_against_stage8600_metadata",
            "trainer_adapter_binding_after_review",
        ],
        **false_fields(),
    }
    summary = {
        "record_type": "stage12674_public_real_repo_knowledge_materialization_summary_v1",
        "stage": STAGE,
        "decision": audit["decision"],
        "current_reviewed_seed_rows": audit["current_reviewed_seed_rows"],
        "upstream_inventory_rows": audit["upstream_inventory_rows"],
        "repository_metadata_rows_consumed": 500,
        "materialized_knowledge_rows": len(rows),
        "objective_family_count": len(objective_counts),
        "objective_counts": objective_counts,
        "split_counts": split_counts,
        "training_source_rows_admitted": 0,
        "recommended_next_stage": audit["recommended_next_stage"],
        **false_fields(),
    }
    checks = [
        {"check_id": "stage12673_pin", "status": "pass"},
        {"check_id": "repository_metadata_pin", "status": "pass"},
        {"check_id": "tens_of_thousands_materialized", "status": "pass", "row_count": len(rows)},
        {"check_id": "no_duplicate_exact_rows", "status": "pass"},
        {"check_id": "no_raw_source_or_absolute_paths", "status": "pass"},
        {"check_id": "no_template_markers", "status": "pass"},
        {"check_id": "authority_closed", "status": "pass"},
        {"check_id": "independent_training_admission", "status": "blocked"},
    ]
    for label, record in (("summary", summary), ("audit", audit), ("checks", checks)):
        assert_no_forbidden(record, label)
    return summary, audit, checks


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    upstream, repo_rows = load_inputs()
    rows = materialize_rows(repo_rows)
    summary, audit, checks = summarize(rows, upstream)
    private = {
        "record_type": "stage12674_private_real_repo_knowledge_materialization_packet_v1",
        "stage": STAGE,
        "input_hashes": EXPECTED_HASHES,
        "knowledge_rows_sha256": stable_hash(rows),
        "audit_sha256": stable_hash(audit),
        "checks_sha256": stable_hash(checks),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12674_real_repo_knowledge_materialization_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "materialized_knowledge_rows": summary["materialized_knowledge_rows"],
        "knowledge_rows_sha256": stable_hash(rows),
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        "recommended_next_stage": summary["recommended_next_stage"],
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12674_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        "knowledge_rows_sha256": stable_hash(rows),
        **false_fields(),
    }
    for label, record in (("private", private), ("contract", contract), ("pointer", pointer)):
        assert_no_forbidden(record, label)

    write_jsonl(out / "real_repo_knowledge_examples.jsonl", rows)
    write_json(out / "summary.json", summary)
    write_json(out / "real_repo_knowledge_materialization_audit.json", audit)
    write_jsonl(out / "private/real_repo_knowledge_materialization_checks.jsonl", checks)
    write_json(out / "private/real_repo_knowledge_materialization_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=True))
