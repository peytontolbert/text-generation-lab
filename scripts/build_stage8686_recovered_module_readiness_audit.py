#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "runs/summaries/stage8686_recovered_module_readiness_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage8686_recovered_module_readiness_audit"
DOC = ROOT / "docs/RECOVERED_MODULE_READINESS_AUDIT_STAGE8686.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def exists_all(paths: list[str]) -> bool:
    return all((ROOT / path).exists() for path in paths)


def implementation_features(path: str) -> dict[str, bool]:
    p = ROOT / path
    text = p.read_text() if p.exists() else ""
    low = text.lower()
    return {
        "has_rotary": "rotary" in low or "rope" in low or "apply_rotary" in text,
        "has_agent_policy_heads": "agent_policy" in text or "policy_head" in text or "agent_policy_heads" in text,
        "has_retrieval_heads": "retrieval_query_head" in text and "retrieval_doc_head" in text,
        "has_scalar_invariant": "scalar_invariant" in text,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph_path = ROOT / "runs/local/artifacts/stage8685_shared_helpers_graph_attachment/central_research_graph_with_shared_helpers.json"
    graph = json.loads(graph_path.read_text()) if graph_path.exists() else {"nodes": [], "edges": []}
    scaffold_features = implementation_features("legacy_src/agentkernel_lite/modeling.py")
    transformer_features = implementation_features("legacy_src/agentkernel_lite/modeling_transformer.py")
    required_architecture_features = ["has_rotary", "has_agent_policy_heads", "has_retrieval_heads", "has_scalar_invariant"]
    transformer_missing_features = [key for key in required_architecture_features if not transformer_features.get(key)]
    scaffold_missing_features = [key for key in required_architecture_features if not scaffold_features.get(key)]

    modules = [
        {
            "name": "safe_storage_cleanup",
            "status": "ready" if exists_all(["scripts/safe_cleanup.py", "scripts/safe_paths.py", "scripts/artifact_paths.py"]) else "missing",
            "files": ["scripts/safe_cleanup.py", "scripts/safe_paths.py", "scripts/artifact_paths.py"],
            "gap": None,
            "next": "Keep as only cleanup path; never write training outputs to /arxiv.",
        },
        {
            "name": "stage_registry_authority_gate",
            "status": "ready" if exists_all(["scripts/authority_gate.py", "runs/local/artifacts/reconstructed_stage_registry.json"]) else "partial",
            "files": ["scripts/authority_gate.py", "runs/local/artifacts/reconstructed_stage_registry.json"],
            "gap": None,
            "next": "Keep all execution/training authority closed until explicit gate.",
        },
        {
            "name": "central_research_graph",
            "status": "ready_partial" if graph_path.exists() else "missing",
            "files": [str(graph_path.relative_to(ROOT))],
            "gap": "Graph is current through Stage8685, but no module-readiness graph validator exists yet.",
            "next": "Build graph validator after telemetry/context modules are recovered.",
        },

        {
            "name": "model_architecture_100m_recovered_transformer_features",
            "status": "ready_partial" if not transformer_missing_features else "missing",
            "files": ["configs/model/agentkernel_100m_seq2seq_recovered_target.json", "legacy_src/agentkernel_lite/modeling_transformer.py", "legacy_src/agentkernel_lite/modeling.py"],
            "gap": "Recovered transformer implementation contains required features, but legacy GRU scaffold is missing them and must never be selected for 100M training." if not transformer_missing_features else "Recovered transformer implementation is missing required target features: " + ",".join(transformer_missing_features),
            "next": "Require trainer/runtime audits to select modeling_transformer.py for target 100M runs and block legacy modeling.py for recovered-target training.",
            "feature_audit": {"required": required_architecture_features, "transformer": transformer_features, "scaffold": scaffold_features, "transformer_missing": transformer_missing_features, "scaffold_missing": scaffold_missing_features},
        },
        {
            "name": "source_inventory_lineage",
            "status": "ready",
            "files": ["configs/software_maintainer/source_inventory_lineage_registry_stage8663.json", "scripts/build_stage8663_source_inventory_lineage_registry.py"],
            "gap": None,
            "next": "Require source_id/lineage_hash in every source-backed builder.",
        },
        {
            "name": "shared_feature_normalizer",
            "status": "ready" if exists_all(["scripts/feature_normalizer.py", "runs/summaries/stage8684_shared_helper_readiness.json"]) else "partial",
            "files": ["scripts/feature_normalizer.py", "configs/software_maintainer/shared_feature_normalizer_stage8664.json", "runs/summaries/stage8684_shared_helper_readiness.json"],
            "gap": None,
            "next": "Make all future builders call scripts/feature_normalizer.py instead of local alias logic.",
        },
        {
            "name": "source_lineage_locked_eval_guard",
            "status": "ready" if exists_all(["scripts/source_lineage_guard.py", "runs/summaries/stage8684_shared_helper_readiness.json"]) else "partial",
            "files": ["scripts/source_lineage_guard.py", "configs/software_maintainer/source_inventory_lineage_registry_stage8663.json", "runs/summaries/stage8684_shared_helper_readiness.json"],
            "gap": None,
            "next": "Make all future source-backed builders call source_lineage_guard before writing train-eligible rows.",
        },
        {
            "name": "leakage_locked_eval_controls",
            "status": "ready",
            "files": ["configs/software_maintainer/leakage_retrieval_locked_eval_control_contract_stage8660.json", "scripts/audit_stage8669_patched_manifest_leakage_locked_eval_boundary.py"],
            "gap": "Controls and guard exist; future builders still need mandatory import/use enforcement.",
            "next": "Wire helper use into source-backed builder templates.",
        },
        {
            "name": "retrieval_baselines",
            "status": "ready_partial",
            "files": ["runs/summaries/stage8666_repo_span_bm25_retrieval_baseline.json", "runs/summaries/stage8671_dense_hybrid_retrieval_baseline.json"],
            "gap": "BM25/dense/hybrid exist; cross-encoder reranker and calibration remain missing.",
            "next": "Recover cross-encoder/reranker calibration card after context packer.",
        },
        {
            "name": "locked_benchmark_packs",
            "status": "ready_partial",
            "files": ["runs/summaries/stage8672_locked_benchmark_pack_manifest.json"],
            "gap": "Locked packs exist; helper exists; future builders need hard dependency on helper.",
            "next": "Enforce source_lineage_guard in every training-candidate builder.",
        },
        {
            "name": "shortcut_baseline_audits",
            "status": "ready",
            "files": ["scripts/shortcut_baseline_audit.py", "scripts/audit_stage8677_source_backed_symbol_binding_shortcut_repair.py"],
            "gap": None,
            "next": "Require per-objective shortcut cards before model probes.",
        },
        {
            "name": "unified_dataset_junk_ood_ranker_v1",
            "status": "ready" if exists_all(["scripts/dataset_junk_ood_ranker_v1.py", "runs/summaries/stage8681_unified_dataset_junk_ood_ranker_readiness.json"]) else "missing",
            "files": ["scripts/dataset_junk_ood_ranker_v1.py", "runs/summaries/stage8681_unified_dataset_junk_ood_ranker_readiness.json"],
            "gap": None,
            "next": "Use as the single row route/loss eligibility API for future manifests.",
        },
        {
            "name": "cluster_slice_near_duplicate_detector",
            "status": "ready" if exists_all(["scripts/cluster_slice_near_duplicate_detector.py", "runs/summaries/stage8682_cluster_slice_detector_readiness.json"]) else "missing",
            "files": ["scripts/cluster_slice_near_duplicate_detector.py", "runs/summaries/stage8682_cluster_slice_detector_readiness.json"],
            "gap": None,
            "next": "Use before source-backed expansion to prevent split overlap, semantic duplicates, and unmeasured slice gaps.",
        },
        {
            "name": "curriculum_compiler",
            "status": "partial",
            "files": ["scripts/curriculum_compiler.py", "scripts/audit_curriculum_compiler_outputs.py", "tests/test_curriculum_compiler.py"],
            "gap": "Compiler exists but still lacks mandatory calls to ranker, cluster detector, feature normalizer, and source lineage guard.",
            "next": "Patch compiler after telemetry/context recovery so all support modules are wired centrally.",
        },
        {
            "name": "loss_mask_cards",
            "status": "ready_partial",
            "files": ["scripts/loss_mask_card.py", "configs/schema/loss_mask.schema.json"],
            "gap": "Loss card helpers exist, but each future builder must emit a card by contract.",
            "next": "Require loss-card generation in source-backed builder template.",
        },
        {
            "name": "counterfactual_obligation_audit",
            "status": "ready_partial",
            "files": ["scripts/counterfactual_obligation_audit.py"],
            "gap": "Helper exists, but future source-backed rows still need sibling-obligation enforcement.",
            "next": "Wire after source-backed builders have enough row families.",
        },
        {
            "name": "source_backed_symbol_binding",
            "status": "candidate_ready_no_training",
            "files": ["runs/summaries/stage8677_source_backed_symbol_binding_shortcut_repair_audit.json", "runs/summaries/stage8678_symbol_binding_repair_graph_attachment.json"],
            "gap": "Validated seed exists, but test-query counterexamples are thin and row count should not increase yet.",
            "next": "Hold until recovery modules are complete; do not mine yet.",
        },
        {
            "name": "context_packer_lost_in_middle_memory_retrieval",
            "status": "missing",
            "files": [],
            "gap": "No executable context packer, lost-in-middle ranker, memory retrieval evaluator, or budgeted evidence-packet scorer.",
            "next": "Recover context_packer_v1 next before large repo context or source-backed expansion.",
        },
        {
            "name": "training_telemetry",
            "status": "partial",
            "files": ["scripts/build_stage8406_v27_standalone_decoder_repair_dependency_smoke_runner.py"] if (ROOT / "scripts/build_stage8406_v27_standalone_decoder_repair_dependency_smoke_runner.py").exists() else [],
            "gap": "Missing unified telemetry module for row losses, token losses, margins, entropy, gradient norms, module delta norms, and failure buckets.",
            "next": "Recover telemetry schema/module before any native probe or training execution.",
        },
        {
            "name": "gradient_activation_interpretability",
            "status": "missing",
            "files": [],
            "gap": "No current activation cache/probe/logit-lens/gradient-attribution module wired to recovered objectives.",
            "next": "Recover after telemetry schema is in place.",
        },
        {
            "name": "dataset_cartography_active_learning",
            "status": "missing",
            "files": [],
            "gap": "No confidence/variability/forgetting/difficulty sampler module.",
            "next": "Recover after telemetry exists; depends on per-epoch/per-row metrics.",
        },
        {
            "name": "confidence_calibration_ood_heads",
            "status": "partial",
            "files": ["scripts/dataset_junk_ood_ranker_v1.py"],
            "gap": "Ranker emits OOD score, but no calibration objective, threshold card, or learned OOD/confidence-head audit exists.",
            "next": "Recover calibration card after telemetry and native probes.",
        },
        {
            "name": "source_backed_edit_localization",
            "status": "missing",
            "files": [],
            "gap": "Neutral objective exists, but no source-backed builder with lineage/retrieval/leakage/shortcut/ranker/cluster controls.",
            "next": "Build only after context/telemetry recovery.",
        },
        {
            "name": "source_backed_patch_operator",
            "status": "missing",
            "files": [],
            "gap": "Neutral objective exists, but no source-backed builder with lineage/retrieval/leakage/shortcut/ranker/cluster controls.",
            "next": "Build after source-backed edit localization.",
        },
        {
            "name": "source_backed_verifier_repair",
            "status": "missing",
            "files": [],
            "gap": "Neutral objective exists, but no source-backed builder with lineage/retrieval/leakage/shortcut/ranker/cluster controls.",
            "next": "Build after source-backed patch operator.",
        },
        {
            "name": "bounded_decoder_ce_probe",
            "status": "closed_partial",
            "files": ["legacy_src/scripts/train_agentkernel_lite_encdec.py"],
            "gap": "Trainer path exists, but no execution allowed and telemetry remains incomplete.",
            "next": "Keep closed until support modules and source-backed state objectives are complete.",
        },
        {
            "name": "runtime_verifier_loop",
            "status": "missing_closed",
            "files": [],
            "gap": "Runtime/harness/verifier execution remains closed; no active tool loop is rebuilt.",
            "next": "Keep closed until post-decoder measured stage.",
        },
    ]

    status_counts = Counter(m["status"] for m in modules)
    blocking = [m for m in modules if m["status"] in {"missing", "missing_closed", "partial", "closed_partial"}]
    highest_priority_next_modules = [
        "context_packer_lost_in_middle_memory_retrieval",
        "training_telemetry",
        "gradient_activation_interpretability",
        "dataset_cartography_active_learning",
        "source_backed_edit_localization",
    ]
    card = {
        "stage": 8686,
        "stage_name": "stage8686_recovered_module_readiness_audit",
        "passed": False,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            "modules_reviewed": len(modules),
            "status_counts": dict(status_counts),
            "blocking_missing_or_partial_modules": [m["name"] for m in blocking],
            "highest_priority_next_modules": highest_priority_next_modules,
            "graph_nodes": len(graph.get("nodes", [])),
            "graph_edges": len(graph.get("edges", [])),
            "required_architecture_features": required_architecture_features,
            "transformer_implementation_features": transformer_features,
            "transformer_missing_recovered_features": transformer_missing_features,
            "legacy_scaffold_missing_recovered_features": scaffold_missing_features,
            "data_mining_allowed": False,
            "training_allowed": False,
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "runtime_authorized": False,
            "promotion_ready": False,
        },
        "modules": modules,
        "artifacts": {
            "doc": str(DOC.relative_to(ROOT)),
            "current_graph": str(graph_path.relative_to(ROOT)) if graph_path.exists() else None,
        },
        "decision": "Module recovery improved after Stages8681-8685, but recovery remains incomplete. Mining and training stay closed until context packing, telemetry, interpretability, and source-backed builders are recovered.",
        "next_best_step": "Recover context_packer_lost_in_middle_memory_retrieval, then recover training telemetry before native probes or source-backed expansion.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "recovered_module_readiness_audit_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")

    lines = [
        "# Stage8686 Recovered Module Readiness Audit",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Modules reviewed: `{len(modules)}`",
        f"Status counts: `{dict(status_counts)}`",
        "",
        "Mining: `closed`",
        "Training: `closed`",
        "",
        "## Blocking Modules",
        "",
    ]
    for m in blocking:
        lines.append(f"- `{m['name']}`: `{m['status']}` - {m['gap']} Next: {m['next']}")
    lines.extend(["", "## Ready Or Candidate-Ready Modules", ""])
    for m in modules:
        if m not in blocking:
            lines.append(f"- `{m['name']}`: `{m['status']}`. Next: {m['next']}")
    lines.extend(["", "## Next Required Sequence", "", "1. Recover `context_packer_lost_in_middle_memory_retrieval`.", "2. Recover `training_telemetry` schema/module.", "3. Recover `gradient_activation_interpretability` on top of telemetry.", "4. Recover `dataset_cartography_active_learning` after telemetry exists.", "5. Then resume source-backed edit/patch/verifier builders.", "", "All authority remains closed."])
    DOC.write_text("\n".join(lines) + "\n")

    old_rows = []
    if REGISTRY.exists():
        try:
            old_rows = list((json.loads(REGISTRY.read_text()).get("rows") or []))
        except Exception:
            old_rows = []
    rows = old_rows + [card]
    REGISTRY.write_text(json.dumps({"passed": True, "rows": rows, "metrics": {"min_stage": min([row.get("stage", 8686) for row in rows] + [8686]), "max_stage": 8686, "latest_stage": 8686, "latest_stage_name": card["stage_name"], "latest_stage_next_best_step": card["next_best_step"], "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}, indent=2, sort_keys=True) + "\n")
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
