#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8720
NAME = "stage8720_forgotten_vital_module_gap_audit"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FORGOTTEN_VITAL_MODULE_GAP_AUDIT_STAGE8720.md"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "training_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_body_authorized": False,
    "gemma_authorized": False,
    "promotion_ready": False,
}


MODULES = [
    {
        "module_id": "cross_encoder_reranker_calibration",
        "priority": 1,
        "why": "BM25/dense/hybrid retrieval exists, but evidence ordering still lacks calibrated task-evidence pair scoring.",
        "expected_files": [],
        "recovered_status": "missing_local_module",
        "needed_artifact": "deterministic reranker calibration card over task/evidence pairs with leakage and locked-eval gates",
    },
    {
        "module_id": "dataset_cartography_active_learning",
        "priority": 2,
        "why": "Scaling to 1M+ rows needs learnability signals: confidence, variability, forgetting, hard/easy/redundant rows.",
        "expected_files": [],
        "recovered_status": "missing_local_module",
        "needed_artifact": "cartography card and sampler contract; no training authority",
    },
    {
        "module_id": "training_data_attribution_influence",
        "priority": 3,
        "why": "Failure-to-data repair loop needs nearest/helpful/harmful example accounting rather than aggregate slice counts only.",
        "expected_files": [],
        "recovered_status": "missing_local_module",
        "needed_artifact": "deterministic attribution placeholder interface using row embeddings/loss metadata before heavy TRAK-style work",
    },
    {
        "module_id": "fusion_logits_forward_pass_contract",
        "priority": 4,
        "why": "Model-stack spine mentions fusion, but no local contract defines how structured heads, retrieval confidence, verifier signals, and decoder logits combine.",
        "expected_files": [],
        "recovered_status": "missing_local_module",
        "needed_artifact": "no-execution fusion policy contract with calibrated input requirements and authority gates",
    },
    {
        "module_id": "moe_lora_adapter_router_contract",
        "priority": 5,
        "why": "Specialist models/adapters are indexed, but no router contract prevents premature adapter routing before slice gates are reliable.",
        "expected_files": [],
        "recovered_status": "missing_local_module",
        "needed_artifact": "deterministic adapter routing card by language/task/repo slice with abstain fallback",
    },
    {
        "module_id": "denoise_diffusion_repair_contract",
        "priority": 6,
        "why": "Denoise rows exist, but no module defines masked-span repair loop, verifier-guided remasking, or when denoise CE can safely reopen.",
        "expected_files": [],
        "recovered_status": "manifest_only_no_repair_contract",
        "needed_artifact": "masked repair contract for bad_output -> repaired_output trajectories; training closed",
    },
    {
        "module_id": "adversarial_hard_negative_generator",
        "priority": 7,
        "why": "Shortcut/leakage audits catch current leaks, but scaling needs adversarial counterexample generation for proxy features.",
        "expected_files": [],
        "recovered_status": "missing_local_module",
        "needed_artifact": "no-authority hard-negative row generator for shortcut baselines and leakage probes",
    },
    {
        "module_id": "confidence_ood_head_contract",
        "priority": 8,
        "why": "Telemetry has entropy/confidence metrics and ranker has OOD score, but no head-level calibration contract exists.",
        "expected_files": [],
        "recovered_status": "metrics_exist_no_head_contract",
        "needed_artifact": "confidence/OOD head schema, thresholds, Brier/ECE card, high-confidence-wrong gate",
    },
    {
        "module_id": "structured_data_operation_curriculum",
        "priority": 9,
        "why": "Software maintenance spans JSON, tables, graphs, AST, logs, workflows, and memory, but there is no unified operation curriculum contract.",
        "expected_files": [],
        "recovered_status": "concept_only",
        "needed_artifact": "state + schema + addressing + operator + validator curriculum rows for non-code structures",
    },
    {
        "module_id": "semantic_equivalence_metamorphic_verifier",
        "priority": 10,
        "why": "Runtime verifier loop exists, but semantic equivalence/property/metamorphic checks are only operator names, not concrete verifier contracts.",
        "expected_files": [],
        "recovered_status": "operator_name_only",
        "needed_artifact": "deterministic verifier contract for equivalence, property tests, metamorphic tests, and API compatibility",
    },
]

KNOWN_RECOVERED = {
    "dataset_junk_ood_ranker_v1": ["scripts/dataset_junk_ood_ranker_v1.py", "tests/test_dataset_junk_ood_ranker_v1.py"],
    "cluster_slice_near_duplicate_detector": ["scripts/cluster_slice_near_duplicate_detector.py", "tests/test_cluster_slice_near_duplicate_detector.py"],
    "context_packer_lost_in_middle_memory": ["scripts/context_packer_v1.py", "tests/test_context_packer_v1.py"],
    "training_telemetry_metrics": ["scripts/training_telemetry_metrics.py", "tests/test_training_telemetry_metrics.py"],
    "program_state_extractors": [
        "scripts/program_state_ast_cst_extractor.py",
        "scripts/program_state_symbol_table_extractor.py",
        "scripts/program_state_import_dependency_extractor.py",
        "scripts/program_state_call_graph_extractor.py",
        "scripts/program_state_data_control_flow_extractor.py",
        "scripts/program_state_type_signature_extractor.py",
    ],
    "semantic_flow_extractors": ["scripts/program_state_data_control_flow_extractor.py"],
    "alignment_dropout_audit": ["scripts/cross_modal_alignment_audit.py", "scripts/modality_dropout_ablation_audit.py"],
    "state_space_repo_state_compressor": ["scripts/state_space_repo_state_compressor.py", "tests/test_state_space_repo_state_compressor.py"],
    "gradient_activation_interpretability": ["scripts/gradient_activation_interpretability.py", "tests/test_gradient_activation_interpretability.py"],
    "mixed_precision_runtime_contract": ["scripts/mixed_precision_runtime_contract.py", "tests/test_mixed_precision_runtime_contract.py"],
    "repo_graph_encoder": ["scripts/repo_graph_encoder.py", "tests/test_repo_graph_encoder.py"],
    "rubric_judge_calibrator": ["scripts/rubric_judge_calibrator.py", "tests/test_rubric_judge_calibrator.py"],
    "operator_codelength_interface": ["scripts/operator_codelength_interface.py", "tests/test_operator_codelength_interface.py"],
}


def exists(path: str) -> bool:
    return (ROOT / path).exists()


def recovered_presence() -> dict[str, dict[str, object]]:
    out = {}
    for module_id, files in KNOWN_RECOVERED.items():
        present = [p for p in files if exists(p)]
        missing = [p for p in files if not exists(p)]
        out[module_id] = {
            "expected_files": files,
            "present_files": present,
            "missing_files": missing,
            "ready_partial": not missing,
        }
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    recovered = recovered_presence()
    forgotten_queue = sorted(MODULES, key=lambda row: row["priority"])
    queue_path = OUT_DIR / "forgotten_vital_module_queue.json"
    recovered_path = OUT_DIR / "known_recovered_module_presence.json"
    queue_path.write_text(json.dumps(forgotten_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    recovered_path.write_text(json.dumps(recovered, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "stage": STAGE,
        "name": NAME,
        "stage_name": NAME,
        "passed": True,
        "authority": AUTHORITY_CLOSED,
        "artifacts": {
            "forgotten_queue": str(queue_path.relative_to(ROOT)),
            "known_recovered_presence": str(recovered_path.relative_to(ROOT)),
        },
        "metrics": {
            **AUTHORITY_CLOSED,
            "forgotten_vital_modules": len(forgotten_queue),
            "known_recovered_modules": len(recovered),
            "known_recovered_ready_partial": sum(1 for card in recovered.values() if card["ready_partial"]),
            "highest_priority_missing": forgotten_queue[0]["module_id"],
        },
        "decision": "Recovered high-level scan shows more vital modules remain concept-only or contract-missing; do not resume mining/training until the priority queue is addressed.",
        "next_best_step": "Recover cross_encoder_reranker_calibration, then dataset_cartography_active_learning and training_data_attribution_influence.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Stage8720 Forgotten Vital Module Gap Audit",
        "",
        "This audit separates modules already recovered from high-value modules still only conceptually indexed.",
        "",
        "## Already Covered",
        "",
    ]
    for module_id, card in sorted(recovered.items()):
        status = "ready_partial" if card["ready_partial"] else "incomplete"
        lines.append(f"- `{module_id}`: `{status}`")
    lines.extend(["", "## Forgotten / Not Yet Recovered", ""])
    for row in forgotten_queue:
        lines.append(f"{row['priority']}. `{row['module_id']}` - {row['why']}")
        lines.append(f"   - needed: {row['needed_artifact']}")
    lines.extend([
        "",
        "## Boundary",
        "",
        "This is a recovery audit only. It does not authorize model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, or promotion.",
        "",
    ])
    DOC.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
