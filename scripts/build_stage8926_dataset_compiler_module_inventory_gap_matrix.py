#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8926
NAME = "stage8926_dataset_compiler_module_inventory_gap_matrix"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DATASET_COMPILER_MODULE_INVENTORY_GAP_MATRIX_STAGE8926.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MATRIX = OUT_DIR / "dataset_compiler_module_inventory_gap_matrix.json"

SOURCE_SUMMARY = ROOT / "runs/summaries/stage8925_tokenizer_hash_lock_bridge_decision.json"

MODULES = [
    {
        "area": "row_judge",
        "script": "scripts/objective_row_judge.py",
        "test": "tests/test_judge_and_shortcuts.py",
        "role": "row-level objective validation and shortcut checks",
    },
    {
        "area": "curriculum_compiler",
        "script": "scripts/curriculum_compiler.py",
        "test": "tests/test_curriculum_compiler.py",
        "role": "route judged rows into objective-specific manifests",
    },
    {
        "area": "unified_junk_ood_ranker",
        "script": "scripts/dataset_junk_ood_ranker_v1.py",
        "test": "tests/test_dataset_junk_ood_ranker_v1.py",
        "role": "objective-aware row risk/routing score",
    },
    {
        "area": "structured_junk_ranker",
        "script": "scripts/structured_dataset_junk_ranker.py",
        "test": None,
        "role": "structured row route/risk features for decoder-state curriculum",
    },
    {
        "area": "shortcut_baselines",
        "script": "scripts/shortcut_baseline_audit.py",
        "test": "tests/test_judge_and_shortcuts.py",
        "role": "single/combo feature shortcut detection before training",
    },
    {
        "area": "counterfactual_obligations",
        "script": "scripts/counterfactual_obligation_audit.py",
        "test": None,
        "role": "counterfactual row sufficiency and obligation checks",
    },
    {
        "area": "cluster_slice_duplicates",
        "script": "scripts/cluster_slice_near_duplicate_detector.py",
        "test": "tests/test_cluster_slice_near_duplicate_detector.py",
        "role": "cluster/slice duplicate and near-duplicate risk detection",
    },
    {
        "area": "dataset_cartography",
        "script": "scripts/dataset_cartography_active_learning.py",
        "test": "tests/test_dataset_cartography_active_learning.py",
        "role": "confidence/loss/forgetting based row routing",
    },
    {
        "area": "training_influence",
        "script": "scripts/training_data_attribution_influence.py",
        "test": "tests/test_training_data_attribution_influence.py",
        "role": "link eval failures to helpful/harmful/missing-neighborhood train rows",
    },
    {
        "area": "cross_encoder_reranker",
        "script": "scripts/cross_encoder_reranker_calibration.py",
        "test": "tests/test_cross_encoder_reranker_calibration.py",
        "role": "task/evidence pair calibration and high-confidence-wrong review",
    },
    {
        "area": "semantic_equivalence",
        "script": "scripts/semantic_equivalence_metamorphic_verifier.py",
        "test": "tests/test_semantic_equivalence_metamorphic_verifier.py",
        "role": "metamorphic equivalence verifier for candidate outputs/patches",
    },
    {
        "area": "repo_graph_encoder",
        "script": "scripts/repo_graph_encoder.py",
        "test": "tests/test_repo_graph_encoder.py",
        "role": "repo graph feature encoding for software-state inputs",
    },
    {
        "area": "program_state_extractors",
        "script": "scripts/program_state_symbol_table_extractor.py",
        "test": None,
        "role": "symbol-table extraction support",
    },
    {
        "area": "program_state_call_graph",
        "script": "scripts/program_state_call_graph_extractor.py",
        "test": None,
        "role": "call-graph extraction support",
    },
    {
        "area": "source_backed_edit_localization",
        "script": "scripts/source_backed_edit_localization_builder.py",
        "test": "tests/test_source_backed_edit_localization_builder.py",
        "role": "source-backed edit localization candidate builder",
    },
    {
        "area": "source_backed_patch_operator",
        "script": "scripts/source_backed_patch_operator_builder.py",
        "test": "tests/test_source_backed_patch_operator_builder.py",
        "role": "source-backed patch operator candidate builder",
    },
    {
        "area": "source_backed_verifier_repair",
        "script": "scripts/source_backed_verifier_repair_builder.py",
        "test": "tests/test_source_backed_verifier_repair_builder.py",
        "role": "source-backed verifier/failure-to-repair candidate builder",
    },
    {
        "area": "denoise_repair_contract",
        "script": "scripts/denoise_diffusion_repair_contract.py",
        "test": "tests/test_denoise_diffusion_repair_contract.py",
        "role": "denoise/diffusion repair objective contract",
    },
    {
        "area": "output_repair_controls",
        "script": "scripts/output_repair_denoise_controls_builder.py",
        "test": "tests/test_output_repair_denoise_controls_builder.py",
        "role": "output repair denoise controls and shortcut gates",
    },
    {
        "area": "structured_data_ops",
        "script": "scripts/structured_data_operation_curriculum.py",
        "test": "tests/test_structured_data_operation_curriculum.py",
        "role": "structured/table operation curriculum support",
    },
    {
        "area": "telemetry_metrics",
        "script": "scripts/training_telemetry_metrics.py",
        "test": "tests/test_training_telemetry_metrics.py",
        "role": "row/logit/loss/gradient telemetry metrics",
    },
    {
        "area": "packet_telemetry",
        "script": "scripts/model_output_packet_telemetry_contract_builder.py",
        "test": "tests/test_model_output_packet_telemetry_contract_builder.py",
        "role": "model output packet telemetry contract",
    },
    {
        "area": "confidence_ood",
        "script": "scripts/confidence_ood_head_contract.py",
        "test": "tests/test_confidence_ood_head_contract.py",
        "role": "confidence/OOD head contract",
    },
    {
        "area": "runtime_verifier_loop",
        "script": "scripts/runtime_verifier_loop_contract.py",
        "test": "tests/test_runtime_verifier_loop_contract.py",
        "role": "runtime verifier loop contract; still no runtime authority",
    },
    {
        "area": "verified_transition_record_adapter",
        "script": "scripts/build_stage8901_verified_transition_record_no_mining_compiler_adapter.py",
        "test": "tests/test_verified_transition_record_no_mining_compiler_adapter.py",
        "role": "no-mining verified transition record adapter",
    },
]

KNOWN_GAPS = [
    {
        "gap": "single_orchestrated_compiler_api",
        "status": "missing_or_undercentralized",
        "reason": "modules exist, but a single durable API that runs judge -> rank -> compile -> audit -> patch queue is not yet proven as one interface",
    },
    {
        "gap": "source_extractors_need_tests",
        "status": "partial",
        "reason": "symbol/call graph extractor scripts exist, but direct tests were not found in this inventory",
    },
    {
        "gap": "structured_junk_ranker_test_gap",
        "status": "partial",
        "reason": "structured_dataset_junk_ranker.py exists without a direct matching test filename",
    },
    {
        "gap": "counterfactual_obligation_test_gap",
        "status": "partial",
        "reason": "counterfactual_obligation_audit.py exists without a direct matching test filename",
    },
    {
        "gap": "runtime_loop_authority_closed",
        "status": "expected_blocked",
        "reason": "runtime verifier contract exists, but runtime remains unauthorized by design",
    },
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def module_status(row: dict[str, Any]) -> dict[str, Any]:
    script = ROOT / row["script"]
    test = ROOT / row["test"] if row.get("test") else None
    return {
        **row,
        "script_exists": script.exists(),
        "test_exists": test.exists() if test else None,
        "has_direct_test": bool(test and test.exists()),
    }


def build_matrix(registry: dict[str, Any]) -> dict[str, Any]:
    modules = [module_status(row) for row in MODULES]
    scripts_present = sum(1 for row in modules if row["script_exists"])
    tests_expected = sum(1 for row in modules if row.get("test"))
    tests_present = sum(1 for row in modules if row["test_exists"] is True)
    checks = {
        "source_stage8925_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "module_inventory_present": len(modules) >= 20,
        "all_required_scripts_present": scripts_present == len(modules),
        "most_direct_tests_present": tests_present >= 20,
        "known_gaps_recorded": len(KNOWN_GAPS) >= 5,
        "training_remains_blocked": True,
        "data_mining_remains_blocked": True,
        "runtime_remains_blocked": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "checks": checks,
        "metrics": {
            "module_count": len(modules),
            "scripts_present": scripts_present,
            "scripts_missing": len(modules) - scripts_present,
            "direct_tests_expected": tests_expected,
            "direct_tests_present": tests_present,
            "known_gap_count": len(KNOWN_GAPS),
            "training_authorized": False,
            "data_mining_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
        },
        "modules": modules,
        "known_gaps": KNOWN_GAPS,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": {
            "compiler_recovery_status": "substantial_modules_present_but_orchestration_gaps_remain",
            "training_status": "blocked",
            "next_required_artifact": "single compiler API contract or targeted tests for source extractors/structured ranker/counterfactual obligations",
        },
    }


def validate_matrix(matrix: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in matrix["checks"].items() if value is not True]
    if any((matrix.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8925, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    matrix = build_matrix(registry)
    failures = validate_matrix(matrix, registry)
    MATRIX.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            **matrix["metrics"],
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "artifacts": {"matrix": str(MATRIX.relative_to(ROOT))},
        "decision": "Dataset/compiler module inventory passed: substantial recovered modules exist, but orchestration and a few direct-test gaps remain. Training/mining stay blocked.",
        "next_best_step": "Build a single compiler API contract, or add targeted readiness tests for source extractors, structured junk ranker, and counterfactual obligation audit.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8926 Dataset Compiler Module Inventory Gap Matrix",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage records the recovered dataset/compiler support modules without running mining or training.",
        "",
        f"Modules inventoried: `{matrix['metrics']['module_count']}`",
        f"Scripts present: `{matrix['metrics']['scripts_present']}`",
        f"Direct tests present: `{matrix['metrics']['direct_tests_present']}/{matrix['metrics']['direct_tests_expected']}`",
        f"Known gaps: `{matrix['metrics']['known_gap_count']}`",
        "",
        "Training, mining, runtime, decoder CE, and model execution remain blocked.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8926 Dataset Compiler Module Inventory Gap Matrix"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8926 inventories recovered dataset/compiler modules: judges, junk/OOD rankers, curriculum compiler, shortcut/counterfactual audits, cartography, influence, reranking, repo graph, source-backed builders, denoise controls, semantic verifier, and telemetry. It records remaining orchestration and direct-test gaps while keeping mining/training closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
