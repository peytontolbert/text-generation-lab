#!/usr/bin/env python3
# Inventory real knowledge sources for expansion without admitting training.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12673_real_knowledge_source_expansion_inventory_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12672_SUMMARY = ROOT / "runs/summaries/stage12672_knowledge_stage_status_rollup_preflight_only.json"
DOC_STAGE8616 = ROOT / "docs/RECOVERED_TRAINING_MINING_GAP_MATRIX_STAGE8616.md"
DOC_STAGE8655 = ROOT / "docs/SOURCE_BACKED_GRAPH_SYMBOL_BINDING_RECOVERY_PLAN_STAGE8655.md"
DOC_STAGE8796 = ROOT / "docs/CURRENT_GAP_AUDIT_AFTER_REGISTRY_RECONCILIATION_STAGE8796.md"

SOURCE_FILES = {
    "repo_capability_catalog_seed": ROOT / "runs/local/artifacts/stage8601_arxiv_repo_capability_and_graph_seed/repo_capability_catalog.jsonl",
    "repo_state_graph_seed": ROOT / "runs/local/artifacts/stage8601_arxiv_repo_capability_and_graph_seed/repo_state_graph_seed.jsonl",
    "symbol_binding_counterfactual_candidates": ROOT / "runs/local/artifacts/stage8618_symbol_binding_counterfactual_with_test_patch/combined_symbol_binding_candidates.jsonl",
    "source_backed_symbol_binding_shortcut_repair": ROOT / "runs/local/artifacts/stage8676_source_backed_symbol_binding_shortcut_repair_manifest/source_backed_symbol_binding_shortcut_repair_manifest.jsonl",
    "repo_span_retrieval_docs_sample": ROOT / "runs/local/artifacts/stage8666_repo_span_bm25_retrieval_baseline/retrieval_docs_sample.jsonl",
    "repo_state_cache_metadata_fixture": ROOT / "runs/local/artifacts/stage9257_repo_state_compiler_cache_metadata_fixture_audit/repo_state_cache_metadata_fixture_rows.jsonl",
    "repo_state_metadata_inventory_fixture": ROOT / "runs/local/artifacts/stage9259_repo_state_metadata_inventory_runner_synthetic_fixture/metadata_inventory_rows.jsonl",
}

EXPECTED_HASHES = {
    "stage12672_summary": "b93667122462956667108e14126ff42ceea5f6f5e449dc065d0123c1e6ba0ca8",
    "doc_stage8616": "d83ad97e9f2c64165c24ef0e32574a220bd29be9fd406444d7206da2841b3a1f",
    "doc_stage8655": "a58cc6729d506ef03db106df9c17fb92c8b45bbc9509468af2d8e4202182676c",
    "doc_stage8796": "ef2ed2a346b254e7846c6d4d0cdcbf0d3b77f4808d71cf5b8cf00ed984816c1c",
    "repo_capability_catalog_seed": "732dbe42bb7b2ce0ab0f208ff8caf7c1689317feb8477d5f8cb7814851e2d384",
    "repo_state_graph_seed": "0ff80beac8512ccd52012c948312c103a72358b42ceecbcd34fc8d3e0af3a935",
    "symbol_binding_counterfactual_candidates": "ac3a48aa9b7c9dc3a954ea875f4e8846c93fb869eaa185c1f50d0b12e272426d",
    "source_backed_symbol_binding_shortcut_repair": "dd3b100f834a904128d7063c9a85a8af73b6d062eb78bf71d0d4daef2a67141f",
    "repo_span_retrieval_docs_sample": "7aa39a2422b0b229903b1dd628b938d532cfb9d0f4b17b9232878a8e9b5fab75",
    "repo_state_cache_metadata_fixture": "fea865aa61645c971cfa257e92081c33e8982acfe7e429c8900548ac70747468",
    "repo_state_metadata_inventory_fixture": "1c59c1589a6c3adfa25140e93f32a26b1f328836431e7ff3dddd3c17b66f553b",
}

EXPECTED_ROWS = {
    "repo_capability_catalog_seed": 200,
    "repo_state_graph_seed": 200,
    "symbol_binding_counterfactual_candidates": 1068,
    "source_backed_symbol_binding_shortcut_repair": 80,
    "repo_span_retrieval_docs_sample": 80,
    "repo_state_cache_metadata_fixture": 10,
    "repo_state_metadata_inventory_fixture": 8,
}

FALSE_FIELDS = (
    "implementation_ready", "stage12674_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted", "strict_eval_eligible",
    "strict_eval_authorized", "sealed_eval_authorized", "loss_authorized", "compiler_execution_authorized",
)

UPSTREAM_FALSE_FIELDS = (
    "implementation_ready", "stage12673_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted",
)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "input_text", "target_text", "query_text", "model_input", "graph_input",
    "source_ref", "source_lineage", "source_row_id", "jsonl", "placeholder", "PLACEHOLDER", "TODO", "TBD",
    "Answer:", "<fill", "\x00",
)

PLACEHOLDER_SUBSTRINGS = ("PLACEHOLDER", "placeholder", "TODO", "TBD", "Answer:", "<fill")


class Stage12673KnowledgeExpansionError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12673KnowledgeExpansionError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Stage12673KnowledgeExpansionError(f"jsonl_object_required:{path.name}:{line_number}")
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
            raise Stage12673KnowledgeExpansionError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12673KnowledgeExpansionError(f"{label}_leak:{needle}")


def objective_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counter = collections.Counter(str(row.get("objective_family") or row.get("objective") or row.get("task_family") or "unlabeled_source_material") for row in rows)
    return dict(sorted(counter.items()))


def split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counter = collections.Counter(str(row.get("split") or "unsplit") for row in rows)
    return dict(sorted(counter.items()))


def source_backing_label(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "empty"
    if any(any(key in row for key in ("source_ref", "source_refs", "source_lineage", "provenance", "source_stage")) for row in rows):
        return "source_backed_candidate"
    if any(any(key in row for key in ("corpus", "doc_id", "source_id", "cache_key", "input_packet")) for row in rows):
        return "source_material_needs_label_builder"
    return "unknown_requires_review"


def blocker_label(name: str) -> str:
    if name in {"repo_capability_catalog_seed", "repo_state_graph_seed"}:
        return "needs_scale_builder_split_dedup_endpoint_and_shortcut_audits"
    if name == "symbol_binding_counterfactual_candidates":
        return "needs_stage8676_style_shortcut_repair_reselection_compiler_gate_and_label_contract"
    if name == "source_backed_symbol_binding_shortcut_repair":
        return "needs_expansion_balance_compiler_gate_and_separate_admission_review"
    if name == "repo_span_retrieval_docs_sample":
        return "needs_query_document_label_builder_hard_negative_contract_and_split_dedup"
    return "fixture_or_metadata_only_needs_real_source_materializer_before_admission"


def load_inputs() -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    pins = {
        "stage12672_summary": S12672_SUMMARY,
        "doc_stage8616": DOC_STAGE8616,
        "doc_stage8655": DOC_STAGE8655,
        "doc_stage8796": DOC_STAGE8796,
        **SOURCE_FILES,
    }
    for label, path in pins.items():
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12673KnowledgeExpansionError("pin_drift:" + label)
    upstream = read_json(S12672_SUMMARY)
    check_false(upstream, "stage12672_summary", UPSTREAM_FALSE_FIELDS)
    if int(upstream.get("knowledge_stage_rows_reviewed", -1)) != 258:
        raise Stage12673KnowledgeExpansionError("current_seed_count_drift")
    rows_by_source = {name: read_jsonl(path) for name, path in SOURCE_FILES.items()}
    for name, rows in rows_by_source.items():
        if len(rows) != EXPECTED_ROWS[name]:
            raise Stage12673KnowledgeExpansionError("row_count_drift:" + name)
        text = SOURCE_FILES[name].read_text(encoding="utf-8")
        if any(needle in text for needle in PLACEHOLDER_SUBSTRINGS):
            raise Stage12673KnowledgeExpansionError("placeholder_source_material:" + name)
    return upstream, rows_by_source


def source_inventory(rows_by_source: Mapping[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for name in sorted(rows_by_source):
        rows = rows_by_source[name]
        inventory.append({
            "source_family": name,
            "row_count": len(rows),
            "objective_counts": objective_counts(rows),
            "split_counts": split_counts(rows),
            "source_backing": source_backing_label(rows),
            "template_marker_hits": 0,
            "admission_status": "not_admitted_for_training",
            "blocker": blocker_label(name),
        })
    return inventory


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    upstream, rows_by_source = load_inputs()
    inventory = source_inventory(rows_by_source)
    candidate_rows = sum(row["row_count"] for row in inventory)
    source_backed_rows = sum(row["row_count"] for row in inventory if row["source_backing"] == "source_backed_candidate")
    source_material_rows = sum(row["row_count"] for row in inventory if row["source_backing"] == "source_material_needs_label_builder")

    if candidate_rows <= int(upstream["knowledge_stage_rows_reviewed"]):
        raise Stage12673KnowledgeExpansionError("expansion_inventory_not_larger_than_seed")
    if source_backed_rows < 1000:
        raise Stage12673KnowledgeExpansionError("source_backed_inventory_too_small")

    audit = {
        "record_type": "stage12673_real_knowledge_source_expansion_audit_v1",
        "stage": STAGE,
        "decision": "REAL_KNOWLEDGE_SOURCE_EXPANSION_INVENTORY_MATERIALIZED_NO_TRAINING",
        "current_knowledge_seed_rows": 258,
        "target_real_knowledge_dataset_required": True,
        "candidate_source_rows_inventory_total": candidate_rows,
        "source_backed_candidate_rows_inventory_total": source_backed_rows,
        "source_material_rows_needing_label_builder": source_material_rows,
        "knowledge_seed_insufficient_for_frontier_100m": True,
        "source_inventory": inventory,
        "blockers_to_training_admission": [
            "materialize_expanded_source_backed_rows_from_inventory",
            "compile_verified_labels_and_targets",
            "run_split_dedup_endpoint_shortcut_and_label_audits",
            "separate_independent_admission_review_before_training",
        ],
        "recommended_next_stage": "stage12674_real_knowledge_candidate_materialization_preflight_only",
        **false_fields(),
    }
    summary = {
        "record_type": "stage12673_public_real_knowledge_source_expansion_summary_v1",
        "stage": STAGE,
        "decision": audit["decision"],
        "current_knowledge_seed_rows": 258,
        "target_real_knowledge_dataset_required": True,
        "knowledge_seed_insufficient_for_frontier_100m": True,
        "candidate_source_rows_inventory_total": candidate_rows,
        "source_backed_candidate_rows_inventory_total": source_backed_rows,
        "source_material_rows_needing_label_builder": source_material_rows,
        "source_family_count": len(inventory),
        "training_source_rows_admitted": 0,
        "recommended_next_stage": audit["recommended_next_stage"],
        **false_fields(),
    }
    checks = [
        {"check_id": "stage12672_pin", "status": "pass"},
        {"check_id": "real_knowledge_seed_is_insufficient", "status": "pass"},
        {"check_id": "source_inventory_larger_than_seed", "status": "pass"},
        {"check_id": "template_marker_scan", "status": "pass"},
        {"check_id": "training_authority", "status": "blocked"},
        {"check_id": "expanded_label_materialization", "status": "blocked"},
    ]
    for label, record in (("summary", summary), ("audit", audit)):
        assert_no_forbidden(record, label)
    return summary, audit, checks


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, checks = build_packet()
    private = {
        "record_type": "stage12673_private_real_knowledge_source_expansion_packet_v1",
        "stage": STAGE,
        "input_hashes": EXPECTED_HASHES,
        "source_file_count": len(SOURCE_FILES),
        "audit_sha256": stable_hash(audit),
        "checks_sha256": stable_hash(checks),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12673_real_knowledge_source_expansion_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "current_knowledge_seed_rows": summary["current_knowledge_seed_rows"],
        "candidate_source_rows_inventory_total": summary["candidate_source_rows_inventory_total"],
        "recommended_next_stage": summary["recommended_next_stage"],
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12673_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        **false_fields(),
    }
    for label, record in (("contract", contract), ("pointer", pointer), ("private", private)):
        assert_no_forbidden(record, label)
    write_json(out / "summary.json", summary)
    write_json(out / "real_knowledge_source_expansion_audit.json", audit)
    write_jsonl(out / "private/real_knowledge_source_expansion_checks.jsonl", checks)
    write_json(out / "private/real_knowledge_source_expansion_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=True))
