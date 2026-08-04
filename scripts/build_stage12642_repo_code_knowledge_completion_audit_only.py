#!/usr/bin/env python3
# Audit whether the repo/code knowledge capability stage can be marked complete.
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12642_repo_code_knowledge_completion_audit_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S8600 = ROOT / "runs/summaries/stage8600_reconstructed_arxiv_corpus_index_and_maintainer_registry.json"
S8601 = ROOT / "runs/summaries/stage8601_reconstructed_arxiv_repo_capability_and_graph_seed.json"
S8602 = ROOT / "runs/summaries/stage8602_reconstructed_arxiv_repo_capability_graph_seed_audit.json"
S8675 = ROOT / "runs/summaries/stage8675_source_backed_symbol_binding_candidate_manifest_audit.json"
S8715 = ROOT / "runs/summaries/stage8715_repo_graph_encoder_graph_attachment.json"
S12641 = ROOT / "runs/summaries/stage12641_canonical_curriculum_renderer_independent_review_only.json"

FALSE_FIELDS = (
    "repo_code_knowledge_stage_complete",
    "repo_code_ce_manifest_materialized",
    "repo_code_rows_admitted",
    "dataset_rows_admitted",
    "new_rows_admitted",
    "training_admission_allowed",
    "training_allowed",
    "training_run_allowed",
    "strict_eval_admitted",
    "sealed_eval_admitted",
    "replay_trustworthy",
    "level_3_materialized",
    "gpu_allocation_requested",
    "cuda2_training_allowed",
    "vm_runner_execution_allowed",
    "runtime_authorized",
    "model_execution_authorized_next",
    "source_emission_authorized",
    "body_emission_authorized",
    "decoder_ce_training_authorized_next",
    "transition_head_training_authorized_next",
    "promotion_ready",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "jsonl", "row_id", "raw_stream", "stdout.raw", "stderr.raw",
    "production_path", "patch_path", "repository_root", "slot_1.patch", "slot_2.patch",
)


class RepoCodeKnowledgeCompletionAuditError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RepoCodeKnowledgeCompletionAuditError("json_object_required:" + path.name)
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def no_claim_fields() -> dict[str, Any]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise RepoCodeKnowledgeCompletionAuditError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise RepoCodeKnowledgeCompletionAuditError(f"{label}_public_leak:{needle}")


def load_inputs() -> dict[str, dict[str, Any]]:
    inputs = {
        "stage8600": read_json(S8600),
        "stage8601": read_json(S8601),
        "stage8602": read_json(S8602),
        "stage8675": read_json(S8675),
        "stage8715": read_json(S8715),
        "stage12641": read_json(S12641),
    }
    return inputs


def audit_inputs(inputs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    s8600 = inputs["stage8600"]
    s8601 = inputs["stage8601"]
    s8602 = inputs["stage8602"]
    s8675 = inputs["stage8675"]
    s8715 = inputs["stage8715"]
    s12641 = inputs["stage12641"]

    inventory = s8600.get("repository_inventory") or {}
    dataset_inventory = s8600.get("dataset_inventory") or {}
    m8601 = s8601.get("metrics") or {}
    m8602 = s8602.get("metrics") or {}
    m8675 = s8675.get("metrics") or {}
    m8715 = s8715.get("metrics") or {}

    if s12641.get("training_allowed") is not False or s12641.get("dataset_rows_admitted") is not False:
        raise RepoCodeKnowledgeCompletionAuditError("stage12641_authority_drift")
    if s12641.get("next_required_action") != "stage12642_causal_transition_atom_preflight_only":
        raise RepoCodeKnowledgeCompletionAuditError("stage12641_next_action_drift")

    recovered_substrate = (
        s8600.get("passed") is True
        and (s8600.get("gates") or {}).get("arxiv_corpus_artifacts_present") is True
        and s8601.get("passed") is True
        and s8602.get("passed") is True
        and s8715.get("passed") is True
    )
    graph_seed_ready = m8602.get("graph_seed_rows") == 200 and m8602.get("endpoint_failures") == 0
    graph_attachment_ready = m8715.get("graph_nodes") == 1467 and m8715.get("graph_edges") == 2033
    symbol_binding_blocked = s8675.get("passed") is not True
    model_ready_rows = int(m8602.get("model_ready_training_rows") or 0)
    raw_training_blocked = (s8600.get("gates") or {}).get("raw_arxiv_training_blocked") is True

    completion_blockers = []
    if model_ready_rows == 0:
        completion_blockers.append("stage8602_model_ready_training_rows_zero")
    if raw_training_blocked:
        completion_blockers.append("raw_recovered_corpus_training_blocked_pending_schema_audit")
    if symbol_binding_blocked:
        completion_blockers.append("stage8675_symbol_binding_audit_failed_shortcut_feature_cells")
    completion_blockers.extend([
        "repo_code_ce_training_manifest_not_materialized",
        "repo_code_rows_not_admitted",
        "repo_code_stage_metrics_not_run",
        "heldout_retention_and_shortcut_baselines_not_materialized_for_repo_code_ce",
    ])

    return {
        "record_type": "stage12642_repo_code_knowledge_completion_audit_v1",
        "audit_scope": "repo_code_knowledge_completion_audit_only",
        "grounding_sources": {
            "training_structure_doc": "MAINTAINER_100M_TRAINING_STAGE_STRUCTURE",
            "central_research_spine": "recovered_v27_100m_spine",
            "current_authoritative_dataset_spine": "stage12638_to_stage12641",
        },
        "repo_code_knowledge_substrate_recovered": bool(recovered_substrate),
        "repo_code_knowledge_stage_complete": False,
        "completion_decision": "NOT_COMPLETE_RECOVERED_SUBSTRATE_ONLY_NO_TRAINING_ADMISSION",
        "repository_inventory_repos_indexed": int(inventory.get("repo_dirs_indexed") or 0),
        "repository_inventory_scan_truncations": int(inventory.get("truncated_repo_scans") or 0),
        "dataset_files_indexed": int(dataset_inventory.get("dataset_files_indexed") or 0),
        "graph_seed_rows": int(m8602.get("graph_seed_rows") or 0),
        "catalog_rows": int(m8602.get("catalog_rows") or 0),
        "model_ready_training_rows": model_ready_rows,
        "graph_seed_ready": bool(graph_seed_ready),
        "graph_attachment_ready": bool(graph_attachment_ready),
        "graph_nodes_attached": int(m8715.get("graph_nodes") or 0),
        "graph_edges_attached": int(m8715.get("graph_edges") or 0),
        "symbol_binding_audit_passed": bool(s8675.get("passed") is True),
        "symbol_binding_rows": int(m8675.get("rows") or 0),
        "symbol_binding_shortcut_feature_cells": int(m8675.get("shortcut_feature_cells") or 0),
        "repo_code_ce_manifest_materialized": False,
        "repo_code_rows_admitted": False,
        "required_repo_code_metrics": [
            "code_doc_test_perplexity",
            "symbol_reference_prediction",
            "test_file_association",
            "repository_metadata_classification",
            "old_language_retention",
            "shortcut_baselines",
            "heldout_retention",
        ],
        "completed_prerequisites": [
            "recovered_repository_inventory_present",
            "repo_capability_catalog_seed_present",
            "repo_state_graph_seed_present",
            "deterministic_repo_graph_attachment_present",
            "stage12640_12641_private_candidate_rows_cleaned_and_reviewed",
        ],
        "completion_blockers": completion_blockers,
        "safe_next_steps": [
            "repair_stage8675_symbol_binding_shortcut_failure_or_quarantine_manifest",
            "materialize_repo_code_ce_manifest_preflight_only_from_recovered_corpus",
            "define_repo_code_stage_metrics_and_heldout_retention_without_training",
            "run_independent_audit_before_any_repo_code_row_admission",
        ],
    }


def build_packet(inputs: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    audit = audit_inputs(inputs)
    true_fields = {
        "repo_code_knowledge_substrate_recovered": True,
        "repo_code_knowledge_completion_audit_only": True,
        "stage12642_repo_code_knowledge_completion_audit_performed": True,
        "vm_branch_remains_paused": True,
    }
    source_hashes = {name: stable_hash(value) for name, value in sorted(inputs.items())}
    private = {
        "record_type": "stage12642_private_repo_code_knowledge_completion_audit_only_v1",
        **no_claim_fields(),
        **true_fields,
        "source_hashes": source_hashes,
        "repo_code_knowledge_completion_audit": audit,
        "decision": "REPO_CODE_KNOWLEDGE_SUBSTRATE_RECOVERED_STAGE_NOT_COMPLETE_NO_TRAINING",
    }
    contract = {
        "record_type": "stage12642_public_repo_code_knowledge_completion_audit_only_contract_v1",
        **no_claim_fields(),
        **true_fields,
        "source_hashes": source_hashes,
        "repo_code_knowledge_completion_audit_sha256": stable_hash(audit),
        "private_repo_code_knowledge_completion_audit_sha256": stable_hash(private),
        "claim_boundary": {
            "repo_code_knowledge": "substrate_recovered_but_stage_not_complete",
            "repo_code_ce_manifest": "not_materialized",
            "row_admission": "not_performed",
            "training": "not_authorized",
            "eval": "not_authorized",
            "replay": "not_executed",
            "level3": "not_materialized",
            "gpu": "not_authorized",
        },
    }
    summary = {
        "record_type": "stage12642_public_repo_code_knowledge_completion_audit_only_summary_v1",
        **no_claim_fields(),
        **true_fields,
        "stage": STAGE,
        "decision": "REPO_CODE_KNOWLEDGE_SUBSTRATE_RECOVERED_STAGE_NOT_COMPLETE_NO_TRAINING",
        "repo_code_knowledge_completion_audit_sha256": stable_hash(audit),
        "private_repo_code_knowledge_completion_audit_sha256": stable_hash(private),
        "repo_code_knowledge_substrate_recovered": audit["repo_code_knowledge_substrate_recovered"],
        "repo_code_knowledge_stage_complete": False,
        "repository_inventory_repos_indexed": audit["repository_inventory_repos_indexed"],
        "dataset_files_indexed": audit["dataset_files_indexed"],
        "graph_seed_rows": audit["graph_seed_rows"],
        "catalog_rows": audit["catalog_rows"],
        "model_ready_training_rows": audit["model_ready_training_rows"],
        "symbol_binding_audit_passed": audit["symbol_binding_audit_passed"],
        "symbol_binding_shortcut_feature_cells": audit["symbol_binding_shortcut_feature_cells"],
        "repo_code_ce_manifest_materialized": False,
        "repo_code_rows_admitted": False,
        "completion_blocker_count": len(audit["completion_blockers"]),
        "completion_blockers": audit["completion_blockers"],
        "next_required_action": "stage12643_repo_code_ce_manifest_preflight_only_or_stage8675_shortcut_repair",
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12642_" + label)
        assert_public_sanitized(record, "stage12642_" + label)
    check_false(private, "stage12642_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    inputs = load_inputs()
    summary, contract, private = build_packet(inputs)
    pointer = {
        "record_type": "stage12642_public_private_repo_code_knowledge_completion_audit_pointer_v1",
        **no_claim_fields(),
        "contract_sha256": stable_hash(contract),
        "private_repo_code_knowledge_completion_audit_sha256": stable_hash(private),
        "repo_code_knowledge_completion_audit_sha256": stable_hash(private["repo_code_knowledge_completion_audit"]),
        "repo_code_knowledge_substrate_recovered": True,
        "repo_code_knowledge_completion_audit_only": True,
        "stage12642_repo_code_knowledge_completion_audit_performed": True,
        "vm_branch_remains_paused": True,
    }
    check_false(pointer, "stage12642_pointer")
    assert_public_sanitized(pointer, "stage12642_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/repo_code_knowledge_completion_audit_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
