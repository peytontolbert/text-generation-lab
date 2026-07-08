#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9256
NAME = "stage9256_repo_state_compiler_cache_manifest_design"
SOURCE_STAGE = ROOT / "runs/summaries/stage9255_precomputed_repo_state_transformation_spine.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "repo_state_compiler_cache_manifest_design.json"
AUDIT = OUT_DIR / "repo_state_compiler_cache_manifest_design_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_STATE_COMPILER_CACHE_MANIFEST_DESIGN_STAGE9256.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

CACHE_LAYERS = [
    {
        "layer_id": "psi_ast_cst_structure",
        "modality": "cst_ast",
        "extractor_module": "scripts/program_state_ast_cst_extractor.py",
        "future_artifact": "repo_ast_cst_packets.jsonl",
        "cache_key_fields": ["repo_id", "commit_hash", "path", "source_sha256", "extractor_version"],
        "consumers": ["symbol_binding", "edit_localization", "patch_operator", "bounded_decoder_arguments"],
    },
    {
        "layer_id": "psi_symbol_table",
        "modality": "symbol_table",
        "extractor_module": "scripts/program_state_symbol_table_extractor.py",
        "future_artifact": "repo_symbol_table_packets.jsonl",
        "cache_key_fields": ["repo_id", "commit_hash", "path", "source_sha256", "extractor_version"],
        "consumers": ["symbol_binding", "edit_localization", "task_observable"],
    },
    {
        "layer_id": "psi_import_dependency_graph",
        "modality": "import_export_graph",
        "extractor_module": "scripts/program_state_import_dependency_extractor.py",
        "future_artifact": "repo_import_dependency_packets.jsonl",
        "cache_key_fields": ["repo_id", "commit_hash", "path", "source_sha256", "dependency_lock_hash", "extractor_version"],
        "consumers": ["intent_to_build_strategy", "allowed_import_policy", "dependency_capability_cards"],
    },
    {
        "layer_id": "psi_type_signature_map",
        "modality": "type_signature_schema_map",
        "extractor_module": "scripts/program_state_type_signature_extractor.py",
        "future_artifact": "repo_type_signature_packets.jsonl",
        "cache_key_fields": ["repo_id", "commit_hash", "path", "source_sha256", "extractor_version"],
        "consumers": ["patch_operator", "verifier_repair", "bounded_decoder_arguments"],
    },
    {
        "layer_id": "psi_call_graph",
        "modality": "call_graph",
        "extractor_module": "scripts/program_state_call_graph_extractor.py",
        "future_artifact": "repo_call_graph_packets.jsonl",
        "cache_key_fields": ["repo_id", "commit_hash", "path", "source_sha256", "extractor_version"],
        "consumers": ["symbol_binding", "edit_localization", "blast_radius_map"],
    },
    {
        "layer_id": "psi_data_control_flow",
        "modality": "data_flow_graph+control_flow_graph",
        "extractor_module": "scripts/program_state_data_control_flow_extractor.py",
        "future_artifact": "repo_data_control_flow_packets.jsonl",
        "cache_key_fields": ["repo_id", "commit_hash", "path", "source_sha256", "extractor_version"],
        "consumers": ["patch_operator", "verifier_repair", "semantic_equivalence_verifier"],
    },
    {
        "layer_id": "psi_repo_state_compressed_stream",
        "modality": "state_space_compressed_repo_memory",
        "extractor_module": "scripts/state_space_repo_state_compressor.py",
        "future_artifact": "repo_state_compressed_stream.jsonl",
        "cache_key_fields": ["repo_id", "commit_hash", "event_stream_hash", "compressor_version", "token_budget"],
        "consumers": ["active_subgraph_contraction_packet", "task_conditioned_context_packer", "100m_policy_state"],
    },
    {
        "layer_id": "psi_test_coverage_graph",
        "modality": "tests_fixtures_ci",
        "extractor_module": "future:no_runtime_static_test_indexer",
        "future_artifact": "repo_test_coverage_static_packets.jsonl",
        "cache_key_fields": ["repo_id", "commit_hash", "test_index_hash", "extractor_version"],
        "consumers": ["verifier_plan", "edit_localization", "failure_to_repair_loop"],
    },
    {
        "layer_id": "psi_patch_affordance_index",
        "modality": "patch_affordance_index",
        "extractor_module": "future:no_execution_affordance_compiler",
        "future_artifact": "repo_patch_affordance_packets.jsonl",
        "cache_key_fields": ["repo_id", "commit_hash", "symbol_table_hash", "call_graph_hash", "extractor_version"],
        "consumers": ["patch_operator", "bounded_decoder_arguments", "repair_denoise"],
    },
    {
        "layer_id": "psi_module_boundary_cache",
        "modality": "module_boundary_cache",
        "extractor_module": "future:module_boundary_static_compiler",
        "future_artifact": "repo_module_boundary_packets.jsonl",
        "cache_key_fields": ["repo_id", "commit_hash", "import_graph_hash", "path_cluster_hash", "extractor_version"],
        "consumers": ["active_subgraph_contraction_packet", "blast_radius_map", "context_packer"],
    },
]

REQUIRED_CONTROLS = {
    "design_only_no_extraction": True,
    "read_arxiv_now": False,
    "write_arxiv_now": False,
    "read_repository_bodies_now": False,
    "runtime_authorized_now": False,
    "training_authorized_now": False,
    "model_execution_authorized_now": False,
    "source_body_emission_authorized_now": False,
    "future_cache_root_under_repo_only": True,
    "opaque_ids_required": True,
    "raw_target_text_forbidden": True,
    "decoder_text_forbidden": True,
    "hidden_or_locked_eval_forbidden": True,
    "cache_invalidation_required": True,
    "manifest_hash_required_before_use": True,
}

TASK_TIME_PRODUCTS = [
    "task_observable_schema",
    "active_subgraph_contraction_packet",
    "maintenance_state_packet",
    "edit_affordance_tensor_rows",
    "verifier_feedback_state_update_rows",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_manifest() -> dict[str, Any]:
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "manifest_status": "DESIGN_ONLY_NO_EXTRACTION_NO_EXECUTION",
        "source_stage": 9255,
        "equation": "S_t = Contract(Psi_R, O_q, h_t)",
        "cache_root_future": "runs/local/artifacts/repo_state_cache/<repo_id>/<commit_hash>/",
        "cache_layers": CACHE_LAYERS,
        "task_time_products": TASK_TIME_PRODUCTS,
        "controls": dict(REQUIRED_CONTROLS),
        "authority": dict(AUTHORITY_CLOSED),
    }


def audit_manifest(manifest: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    layers = manifest.get("cache_layers") or []
    layer_ids = [layer.get("layer_id") for layer in layers]
    artifacts = [layer.get("future_artifact") for layer in layers]
    controls = manifest.get("controls") or {}
    if source.get("passed") is not True:
        failures.append("source_stage9255_not_passed")
    if any((source.get("authority") or {}).values()):
        failures.append("source_stage9255_authority_open")
    if manifest.get("manifest_status") != "DESIGN_ONLY_NO_EXTRACTION_NO_EXECUTION":
        failures.append("manifest_status_not_design_only")
    if len(layers) < 10:
        failures.append("cache_layers_lt_10")
    if len(set(layer_ids)) != len(layer_ids):
        failures.append("duplicate_layer_ids")
    if len(set(artifacts)) != len(artifacts):
        failures.append("duplicate_future_artifacts")
    for layer in layers:
        for key in ["layer_id", "modality", "extractor_module", "future_artifact", "cache_key_fields", "consumers"]:
            if not layer.get(key):
                failures.append(f"missing_layer_field:{layer.get('layer_id')}:{key}")
        if "commit_hash" not in layer.get("cache_key_fields", []):
            failures.append(f"missing_commit_hash_cache_key:{layer.get('layer_id')}")
        if "extractor_version" not in layer.get("cache_key_fields", []) and "compressor_version" not in layer.get("cache_key_fields", []):
            failures.append(f"missing_version_cache_key:{layer.get('layer_id')}")
    for key, expected in REQUIRED_CONTROLS.items():
        if controls.get(key) != expected:
            failures.append(f"control_mismatch:{key}")
    if any((manifest.get("authority") or {}).values()):
        failures.append("manifest_authority_open")
    content_for_scan = {key: value for key, value in manifest.items() if key not in {"controls"}}
    forbidden = json.dumps(content_for_scan, sort_keys=True).lower()
    for token in ["target_body", "expected_answer", "hidden_eval", "locked_eval"]:
        if token in forbidden:
            failures.append(f"forbidden_token_present:{token}")
    if not all(product in manifest.get("task_time_products", []) for product in TASK_TIME_PRODUCTS):
        failures.append("missing_task_time_products")
    return {
        "passed": not failures,
        "failures": failures,
        "cache_layers": len(layers),
        "task_time_products": len(manifest.get("task_time_products") or []),
        "controls_checked": len(REQUIRED_CONTROLS),
        "future_artifacts": len(set(artifacts)),
        "extractor_modules": sorted({str(layer.get("extractor_module")) for layer in layers}),
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_STAGE)
    manifest = build_manifest()
    audit = audit_manifest(manifest, source)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit, "authority_rows": 0},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Designed the repo-state compiler cache manifest for Psi_R layers without extraction, /arxiv access, runtime, or training." if audit["passed"] else "Repo-state compiler cache manifest design failed audit.",
        "next_best_step": "Build a no-source-body metadata fixture audit for repo_state_compiler_cache_manifest before any real repo body extraction.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9256 Repo-State Compiler Cache Manifest Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage turns the precomputed repo-state spine into an auditable cache manifest design for `Psi_R`. It is design-only: it does not read repository bodies, read or write `/arxiv`, run runtime/tools, execute a model, train, mine data, or authorize cleanup.",
        "",
        f"Cache layers: `{audit['cache_layers']}`",
        f"Task-time products: `{audit['task_time_products']}`",
        f"Controls checked: `{audit['controls_checked']}`",
        "",
        "Core future flow: offline cache layers -> task observable -> active subgraph contraction packet -> 100M policy state.",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
    marker = "## Stage9256 Repo-State Compiler Cache Manifest Design"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + marker + "\n\n" + "Stage9256 defines the design-only `repo_state_compiler_cache_manifest`: cache layers for AST/CST, symbols, imports, types, calls, data/control flow, compressed repo stream, test coverage, patch affordances, and module boundaries. It keeps extraction, runtime, training, mining, and /arxiv access closed.\n", encoding="utf-8")
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
