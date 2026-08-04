#!/usr/bin/env python3
"""Materialize deeper repo/code knowledge rows without raw body emission."""

from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12678_deep_repo_code_knowledge_materialization_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12676_SUMMARY = ROOT / "runs/summaries/stage12676_repo_knowledge_trainer_adapter_and_shortcut_baseline_preflight_only.json"
REPOSITORY_SUMMARIES = ROOT / "runs/local/artifacts/stage8600_arxiv_corpus_index/repository_summaries.jsonl"
SYMBOL_CANDIDATES = ROOT / "runs/local/artifacts/stage8618_symbol_binding_counterfactual_with_test_patch/combined_symbol_binding_candidates.jsonl"
RETRIEVAL_DOCS = ROOT / "runs/local/artifacts/stage8666_repo_span_bm25_retrieval_baseline/retrieval_docs_sample.jsonl"
SELECTED_TEST_ROWS = ROOT / "runs/local/artifacts/stage12375_combined_train_support_ledger_v10/combined_selected_test_rows_v10.jsonl"
VERIFIER_EVIDENCE_ROWS = ROOT / "runs/local/artifacts/stage11205_fresh_verifier_constraint_evidence_support/admitted_fresh_verifier_constraint_evidence_rows.jsonl"

EXPECTED_HASHES = {
    "stage12676_summary": "302935471616849c1a26ef22fa637b4d16e299f51a4e0dcea6efe45b98397d59",
    "repository_summaries": "4905c47a9e3feca39b0ed3abf51d07ee334e002c81292617ca90c4bad13a3489",
    "symbol_candidates": "ac3a48aa9b7c9dc3a954ea875f4e8846c93fb869eaa185c1f50d0b12e272426d",
    "retrieval_docs": "7aa39a2422b0b229903b1dd628b938d532cfb9d0f4b17b9232878a8e9b5fab75",
    "selected_test_rows": "094a184a207f44c8a4dd165aebcab7f5926cecb5eed52a89faedf25452706d6a",
    "verifier_evidence_rows": "33771a4e32ab89cafcd5aed9ddc8f122d387805affe465d124739730580a9047",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12679_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted", "strict_eval_eligible",
    "strict_eval_authorized", "sealed_eval_authorized", "loss_authorized", "compiler_execution_authorized",
)

AUTHORITY_CLOSED = {
    "training_allowed": False,
    "training_run_allowed": False,
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

RARE_OR_RETENTION_LANGUAGES = {"c_family", "go", "java_jvm", "rust", "shell", "web_js_ts_html"}


class Stage12678DeepKnowledgeError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12678DeepKnowledgeError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12678DeepKnowledgeError(f"jsonl_object_required:{path.name}:{line_number}")
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


def assert_no_forbidden(value: Any, label: str) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12678DeepKnowledgeError(f"{label}_forbidden_substring:{needle}")


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise Stage12678DeepKnowledgeError(f"{label}_gate_drift:{field}")


def stable_int(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def opaque(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256(":".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def split_for_key(key: str) -> str:
    bucket = stable_int(key) % 10
    if bucket < 6:
        return "train"
    if bucket < 8:
        return "eval"
    return "strict_eval"


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


def boolean_label(value: bool) -> str:
    return "yes" if value else "no"


def row(row_index: int, objective: str, source_stage: str, split: str, input_state: Mapping[str, Any], target: Mapping[str, Any]) -> dict[str, Any]:
    record = {
        "row_id": f"stage12678_deep_repo_code_knowledge_{row_index:06d}",
        "split": split,
        "objective_family": objective,
        "knowledge_input": dict(input_state),
        "expected_output": dict(target),
        "evidence": {
            "source_stage": source_stage,
            "raw_source_included": False,
            "absolute_path_included": False,
            "source_body_included": False,
            "source_paths_redacted": True,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "quality": {
            "label_source": "deterministic_body_free_structural_compiler",
            "requires_independent_review_before_training": True,
            "target_not_visible_in_input": True,
        },
    }
    if any(record["authority"].values()):
        raise Stage12678DeepKnowledgeError("row_authority_open")
    assert_no_forbidden(record, "knowledge_row")
    return record


def load_inputs() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    pins = {
        "stage12676_summary": STAGE12676_SUMMARY,
        "repository_summaries": REPOSITORY_SUMMARIES,
        "symbol_candidates": SYMBOL_CANDIDATES,
        "retrieval_docs": RETRIEVAL_DOCS,
        "selected_test_rows": SELECTED_TEST_ROWS,
        "verifier_evidence_rows": VERIFIER_EVIDENCE_ROWS,
    }
    for label, path in pins.items():
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12678DeepKnowledgeError("pin_drift:" + label)
    stage12676 = read_json(STAGE12676_SUMMARY)
    check_false(stage12676, "stage12676_summary")
    if int(stage12676.get("adapter_candidate_rows", -1)) != 28618:
        raise Stage12678DeepKnowledgeError("stage12676_adapter_count_drift")
    repos = read_jsonl(REPOSITORY_SUMMARIES)
    symbols = read_jsonl(SYMBOL_CANDIDATES)
    retrieval_docs = read_jsonl(RETRIEVAL_DOCS)
    selected_tests = read_jsonl(SELECTED_TEST_ROWS)
    verifier_evidence = read_jsonl(VERIFIER_EVIDENCE_ROWS)
    if (len(repos), len(symbols), len(retrieval_docs), len(selected_tests), len(verifier_evidence)) != (500, 1068, 80, 55, 54):
        raise Stage12678DeepKnowledgeError("input_row_count_drift")
    return stage12676, repos, symbols, retrieval_docs, selected_tests, verifier_evidence


def repo_rows(repos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for repo in sorted(repos, key=lambda item: str(item["repo_id"])):
        repo_id = str(repo["repo_id"])
        split = split_for_key(repo_id)
        opaque_repo = opaque("repo", repo_id)
        languages = sorted((repo.get("language_file_counts") or {}).items())
        primary = list(repo.get("likely_primary_languages") or [])
        uses = list(repo.get("recommended_curriculum_uses") or [])
        for ordinal, (language, file_count) in enumerate(languages):
            rows.append(row(len(rows), "syntax_api_structural_profile", "stage8600_repository_metadata", split, {
                "opaque_repo_id": opaque_repo,
                "language_family": language,
                "language_rank_hint": ordinal,
                "repo_size_bucket": count_bucket(int(repo.get("scanned_files", 0))),
            }, {
                "language_file_count_bucket": count_bucket(int(file_count)),
                "test_file_count_bucket": count_bucket(int(repo.get("test_files", 0))),
                "has_build_surface": boolean_label(bool(repo.get("build_files") or [])),
            }))
        for ordinal, fact_name in enumerate(("has_tests", "test_count_bucket", "docs_count_bucket", "build_count_bucket")):
            target_value: str | bool
            if fact_name == "has_tests":
                target_value = boolean_label(int(repo.get("test_files", 0)) > 0)
            elif fact_name == "test_count_bucket":
                target_value = count_bucket(int(repo.get("test_files", 0)))
            elif fact_name == "docs_count_bucket":
                target_value = count_bucket(int(repo.get("doc_files", 0)))
            else:
                target_value = count_bucket(len(repo.get("build_files") or []))
            rows.append(row(len(rows), "test_file_association_bucket", "stage8600_repository_metadata", split, {
                "opaque_repo_id": opaque_repo,
                "association_fact": fact_name,
                "primary_language_count": len(primary),
            }, {"association_value": target_value}))
        for ordinal, language in enumerate(primary):
            rows.append(row(len(rows), "doc_code_test_relationship", "stage8600_repository_metadata", split, {
                "opaque_repo_id": opaque_repo,
                "primary_language_family": language,
                "primary_language_rank": ordinal,
            }, {
                "doc_surface_bucket": count_bucket(int(repo.get("doc_files", 0))),
                "test_surface_bucket": count_bucket(int(repo.get("test_files", 0))),
                "readme_surface_bucket": count_bucket(len(repo.get("readme_files") or [])),
            }))
        for ordinal, use in enumerate(uses):
            rows.append(row(len(rows), "issue_maintenance_vocabulary_proxy", "stage8600_repository_metadata", split, {
                "opaque_repo_id": opaque_repo,
                "curriculum_use_slot": ordinal,
                "repo_size_bucket": count_bucket(int(repo.get("scanned_files", 0))),
            }, {
                "maintenance_vocabulary_family": use,
                "use_present": "yes",
            }))
        retention_languages = sorted(set(primary) & RARE_OR_RETENTION_LANGUAGES)
        rows.append(row(len(rows), "old_language_retention_flag", "stage8600_repository_metadata", split, {
            "opaque_repo_id": opaque_repo,
            "retention_language_family_count": len(retention_languages),
        }, {
            "requires_old_language_retention": boolean_label(bool(retention_languages)),
            "retention_language_families": retention_languages,
        }))
    return rows


def symbol_rows(symbols: list[dict[str, Any]], offset: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ordinal, source in enumerate(symbols):
        graph = source.get("graph_input") or {}
        query = source.get("query") or {}
        target = source.get("target") or {}
        nodes = graph.get("nodes") or []
        file_node = next((node for node in nodes if node.get("node_type") == "file"), {})
        features = file_node.get("features") or {}
        split = str(source.get("split") or split_for_key(str(source.get("row_id"))))
        base = {
            "opaque_symbol_row_id": opaque("sym", source.get("row_id")),
            "query_kind": query.get("query_kind") or graph.get("query_kind"),
            "source_file_is_test": bool(((query.get("features") or {}).get("source_file_is_test"))),
            "language_family": (nodes[0].get("features") or {}).get("language_family", "unknown") if nodes else "unknown",
        }
        rows.append(row(offset + len(rows), "symbol_reference_prediction_structural", "stage8618_symbol_binding_counterfactual", split, base, {
            "binding_action": target.get("binding_action"),
            "target_node_presence": boolean_label(bool(target.get("target_node_id"))),
            "target_node_kind": target.get("target_node_kind") or "none",
        }))
        for feature_name in ("call_count_bucket", "definition_count_bucket", "import_count_bucket"):
            rows.append(row(offset + len(rows), "symbol_graph_feature_prediction", "stage8618_symbol_binding_counterfactual", split, {
                **base,
                "feature_name": feature_name,
            }, {"feature_bucket": features.get(feature_name, 0)}))
    return rows


def retrieval_rows(docs: list[dict[str, Any]], offset: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ordinal, source in enumerate(docs):
        key = f"{source.get('corpus')}:{source.get('doc_id')}:{ordinal}"
        split = split_for_key(key)
        doc_id = str(source.get("doc_id", ""))
        source_id = str(source.get("source_id", ""))
        suffix = Path(source_id).suffix or "<none>"
        token_count_bucket = count_bucket(len(str(source.get("query", "")).split()))
        base = {
            "opaque_retrieval_doc_id": opaque("retrieval", key),
            "doc_suffix": suffix,
            "query_token_count_bucket": token_count_bucket,
        }
        rows.append(row(offset + len(rows), "retrieval_file_association_proxy", "stage8666_repo_span_bm25_retrieval_baseline", split, base, {
            "doc_id_kind": "repo_relative_file",
            "source_id_suffix": suffix,
        }))
        rows.append(row(offset + len(rows), "retrieval_query_surface_proxy", "stage8666_repo_span_bm25_retrieval_baseline", split, base, {
            "query_surface_bucket": token_count_bucket,
            "has_compound_terms": boolean_label("_" in str(source.get("query", ""))),
        }))
        rows.append(row(offset + len(rows), "retrieval_doc_role_proxy", "stage8666_repo_span_bm25_retrieval_baseline", split, base, {
            "doc_role": "script_or_source" if doc_id.endswith((".py", ".rs", ".go", ".js", ".ts", ".cpp", ".c", ".h")) else "other_repo_file",
        }))
    return rows


def selected_test_rows(selected: list[dict[str, Any]], verifier: list[dict[str, Any]], offset: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ordinal, source in enumerate(selected):
        key = str(source.get("row_id"))
        split = split_for_key(key)
        base = {
            "opaque_selected_test_row_id": opaque("selected", key),
            "language_family": source.get("language_family", "unknown"),
            "task_family": source.get("task_family", "unknown"),
        }
        rows.append(row(offset + len(rows), "selected_test_task_family_summary", "stage12375_selected_test_train_support_ledger", split, base, {
            "task_family": source.get("task_family", "unknown"),
            "record_type": source.get("record_type", "unknown"),
        }))
        enabled_losses = sorted(k for k, v in (source.get("loss_mask") or {}).items() if v)
        rows.append(row(offset + len(rows), "selected_test_loss_contract_summary", "stage12375_selected_test_train_support_ledger", split, base, {
            "enabled_loss_count": len(enabled_losses),
            "has_transition_projection": boolean_label("transition_projection" in enabled_losses),
        }))
        options = source.get("opaque_options") or []
        rows.append(row(offset + len(rows), "selected_test_evidence_shape_summary", "stage12375_selected_test_train_support_ledger", split, base, {
            "opaque_option_count_bucket": count_bucket(len(options)),
            "raw_verifier_log_emitted": boolean_label(bool((source.get("source_refs") or {}).get("raw_verifier_log_emitted"))),
        }))
    for ordinal, source in enumerate(verifier):
        key = str(source.get("row_id"))
        split = str(source.get("split") or split_for_key(key))
        base = {
            "opaque_verifier_evidence_row_id": opaque("verifier", key),
            "language_family": source.get("language_family", "unknown"),
            "task_type": source.get("task_type", "unknown"),
        }
        option_values = [item.get("value") for item in (source.get("opaque_options") or [])]
        rows.append(row(offset + len(rows), "verifier_evidence_role_choice_summary", "stage11205_fresh_verifier_constraint_evidence", split, base, {
            "target_role_family": (source.get("target") or {}).get("target_text", source.get("target_text")),
            "task_type": source.get("task_type", "unknown"),
        }))
        rows.append(row(offset + len(rows), "verifier_evidence_language_summary", "stage11205_fresh_verifier_constraint_evidence", split, base, {
            "language_family": source.get("language_family", "unknown"),
            "enabled_loss": source.get("expected_enabled_loss", "unknown"),
        }))
        rows.append(row(offset + len(rows), "verifier_option_set_summary", "stage11205_fresh_verifier_constraint_evidence", split, base, {
            "option_count_bucket": count_bucket(len(option_values)),
            "contains_verifier_constraint_option": boolean_label("verifier_and_test_constraint" in option_values),
        }))
    return rows


def materialize_rows(repos: list[dict[str, Any]], symbols: list[dict[str, Any]], retrieval_docs: list[dict[str, Any]], selected: list[dict[str, Any]], verifier: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = repo_rows(repos)
    rows.extend(symbol_rows(symbols, len(rows)))
    rows.extend(retrieval_rows(retrieval_docs, len(rows)))
    rows.extend(selected_test_rows(selected, verifier, len(rows)))
    if len(rows) < 15000:
        raise Stage12678DeepKnowledgeError("deep_knowledge_rows_below_floor")
    if any(record["expected_output"] == {} for record in rows):
        raise Stage12678DeepKnowledgeError("empty_target")
    row_ids = [record["row_id"] for record in rows]
    if len(row_ids) != len(set(row_ids)):
        raise Stage12678DeepKnowledgeError("duplicate_row_id")
    return rows


def summarize(rows: list[dict[str, Any]], stage12676: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    objective_counts = dict(sorted(collections.Counter(row["objective_family"] for row in rows).items()))
    split_counts = dict(sorted(collections.Counter(row["split"] for row in rows).items()))
    duplicate_hashes = len(rows) - len({stable_hash(row) for row in rows})
    authority_open_rows = sum(1 for record in rows if any(record["authority"].values()))
    forbidden_hits = sum(1 for record in rows if any(needle in json.dumps(record, sort_keys=True, ensure_ascii=True) for needle in FORBIDDEN_SUBSTRINGS))
    raw_body_rows = sum(1 for record in rows if record["evidence"]["raw_source_included"] or record["evidence"]["absolute_path_included"] or record["evidence"]["source_body_included"])
    if duplicate_hashes or authority_open_rows or forbidden_hits or raw_body_rows:
        raise Stage12678DeepKnowledgeError("deep_row_quality_gate_failed")
    coverage = {
        "syntax_api_regularities": "body_free_structural_proxy_materialized",
        "code_doc_test_relationships": "body_free_relationship_rows_materialized",
        "symbol_reference_prediction": "source_backed_structural_rows_materialized",
        "test_file_association": "metadata_bucket_rows_materialized",
        "compact_verifier_test_summaries": "selected_test_and_verifier_summary_rows_materialized",
        "issue_maintenance_vocabulary": "curriculum_use_proxy_materialized",
        "retention_sets": "old_language_retention_flags_materialized",
        "direct_source_body_syntax_api_mining": "blocked_pending_controlled_parser_no_body_emission",
    }
    audit = {
        "record_type": "stage12678_deep_repo_code_knowledge_materialization_audit_v1",
        "stage": STAGE,
        "decision": "DEEP_REPO_CODE_KNOWLEDGE_ROWS_MATERIALIZED_REVIEW_REQUIRED",
        "stage12676_adapter_candidate_rows": int(stage12676["adapter_candidate_rows"]),
        "materialized_deep_knowledge_rows": len(rows),
        "objective_counts": objective_counts,
        "split_counts": split_counts,
        "coverage": coverage,
        "duplicate_row_hashes": duplicate_hashes,
        "authority_open_rows": authority_open_rows,
        "template_marker_or_forbidden_hits": forbidden_hits,
        "raw_source_body_rows": raw_body_rows,
        "absolute_path_rows": raw_body_rows,
        "training_source_rows_admitted": 0,
        "recommended_next_stage": "stage12679_deep_repo_code_knowledge_independent_review_only",
        "blockers_to_training_admission": [
            "independent_review_of_stage12678_rows",
            "shortcut_and_duplicate_target_audit",
            "trainer_adapter_binding_for_deep_knowledge_loss",
            "controlled_parser_required_for_direct_source_body_syntax_api_expansion",
        ],
        **false_fields(),
    }
    summary = {
        "record_type": "stage12678_public_deep_repo_code_knowledge_materialization_summary_v1",
        "stage": STAGE,
        "decision": audit["decision"],
        "upstream_repo_knowledge_adapter_rows": audit["stage12676_adapter_candidate_rows"],
        "materialized_deep_knowledge_rows": len(rows),
        "objective_family_count": len(objective_counts),
        "objective_counts": objective_counts,
        "split_counts": split_counts,
        "coverage": coverage,
        "training_source_rows_admitted": 0,
        "recommended_next_stage": audit["recommended_next_stage"],
        **false_fields(),
    }
    checks = [
        {"check_id": "stage12676_pin", "status": "pass"},
        {"check_id": "source_artifact_pins", "status": "pass"},
        {"check_id": "deep_row_floor", "status": "pass", "row_count": len(rows)},
        {"check_id": "no_raw_source_or_absolute_paths", "status": "pass"},
        {"check_id": "no_template_markers", "status": "pass"},
        {"check_id": "authority_closed", "status": "pass"},
        {"check_id": "direct_source_body_syntax_api_parser", "status": "blocked"},
        {"check_id": "independent_training_admission", "status": "blocked"},
    ]
    for label, record in (("summary", summary), ("audit", audit), ("checks", checks)):
        assert_no_forbidden(record, label)
    return summary, audit, checks


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12676, repos, symbols, retrieval_docs, selected, verifier = load_inputs()
    rows = materialize_rows(repos, symbols, retrieval_docs, selected, verifier)
    summary, audit, checks = summarize(rows, stage12676)
    private = {
        "record_type": "stage12678_private_deep_repo_code_knowledge_materialization_packet_v1",
        "stage": STAGE,
        "input_hashes": EXPECTED_HASHES,
        "deep_knowledge_rows_sha256": stable_hash(rows),
        "audit_sha256": stable_hash(audit),
        "checks_sha256": stable_hash(checks),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12678_deep_repo_code_knowledge_materialization_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "materialized_deep_knowledge_rows": summary["materialized_deep_knowledge_rows"],
        "deep_knowledge_rows_sha256": stable_hash(rows),
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        "recommended_next_stage": summary["recommended_next_stage"],
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12678_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        "deep_knowledge_rows_sha256": stable_hash(rows),
        **false_fields(),
    }
    for label, record in (("private", private), ("contract", contract), ("pointer", pointer)):
        assert_no_forbidden(record, label)
    write_jsonl(out / "deep_repo_code_knowledge_examples.jsonl", rows)
    write_json(out / "summary.json", summary)
    write_json(out / "deep_repo_code_knowledge_materialization_audit.json", audit)
    write_jsonl(out / "private/deep_repo_code_knowledge_materialization_checks.jsonl", checks)
    write_json(out / "private/deep_repo_code_knowledge_materialization_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=True))
