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
STAGE = 8970
NAME = "stage8970_training_pipeline_module_gap_matrix"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINING_PIPELINE_MODULE_GAP_MATRIX_STAGE8970.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MATRIX = OUT_DIR / "training_pipeline_module_gap_matrix.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8969_github_backup_push_result.json"

COMPONENTS: dict[str, list[str]] = {
    "safety_and_path_control": [
        "scripts/safe_paths.py",
        "scripts/safe_cleanup.py",
        "tests/test_safe_cleanup.py",
    ],
    "manifest_validation_and_loss_masks": [
        "scripts/manifest_path_validator.py",
        "scripts/loss_mask_card.py",
        "scripts/software_maintenance_curriculum_cli.py",
        "tests/test_manifest_path_validator.py",
        "tests/test_software_maintenance_curriculum_cli.py",
    ],
    "dataset_judge_ranker_compiler": [
        "scripts/curriculum_compiler.py",
        "scripts/objective_row_judge.py",
        "scripts/structured_dataset_junk_ranker.py",
        "scripts/dataset_junk_ood_ranker_v1.py",
        "tests/test_curriculum_compiler.py",
        "tests/test_judge_and_shortcuts.py",
        "tests/test_dataset_junk_ood_ranker_v1.py",
    ],
    "counterfactual_and_hard_negative_support": [
        "scripts/adversarial_hard_negative_generator.py",
        "tests/test_adversarial_hard_negative_generator.py",
        "scripts/semantic_equivalence_metamorphic_verifier.py",
        "tests/test_semantic_equivalence_metamorphic_verifier.py",
    ],
    "program_state_multimodality": [
        "scripts/program_state_symbol_table_extractor.py",
        "scripts/program_state_call_graph_extractor.py",
        "scripts/repo_graph_encoder.py",
        "scripts/state_space_repo_state_compressor.py",
        "tests/test_repo_graph_encoder.py",
        "tests/test_state_space_repo_state_compressor.py",
    ],
    "maintenance_cognition_builders": [
        "scripts/source_backed_edit_localization_builder.py",
        "scripts/source_backed_patch_operator_builder.py",
        "scripts/source_backed_verifier_repair_builder.py",
        "scripts/verifier_guided_repair_target_materialization_builder.py",
        "tests/test_source_backed_edit_localization_builder.py",
        "tests/test_source_backed_patch_operator_builder.py",
        "tests/test_source_backed_verifier_repair_builder.py",
        "tests/test_verifier_guided_repair_target_materialization_builder.py",
    ],
    "repair_denoise_and_verifier_loop": [
        "scripts/denoise_diffusion_repair_contract.py",
        "scripts/output_repair_denoise_controls_builder.py",
        "scripts/runtime_verifier_loop_contract.py",
        "tests/test_denoise_diffusion_repair_contract.py",
        "tests/test_output_repair_denoise_controls_builder.py",
        "tests/test_runtime_verifier_loop_contract.py",
    ],
    "retrieval_ranking_confidence": [
        "scripts/cross_encoder_reranker_calibration.py",
        "scripts/rubric_judge_calibrator.py",
        "scripts/confidence_ood_head_contract.py",
        "tests/test_cross_encoder_reranker_calibration.py",
        "tests/test_rubric_judge_calibrator.py",
        "tests/test_confidence_ood_head_contract.py",
    ],
    "telemetry_interpretability_attribution": [
        "scripts/training_telemetry.py",
        "scripts/training_telemetry_metrics.py",
        "scripts/gradient_activation_interpretability.py",
        "scripts/model_output_packet_telemetry_contract_builder.py",
        "scripts/dataset_cartography_active_learning.py",
        "scripts/training_data_attribution_influence.py",
        "scripts/cross_modal_alignment_audit.py",
        "scripts/modality_dropout_ablation_audit.py",
        "tests/test_training_telemetry_metrics.py",
        "tests/test_gradient_activation_interpretability.py",
        "tests/test_model_output_packet_telemetry_contract_builder.py",
        "tests/test_dataset_cartography_active_learning.py",
        "tests/test_training_data_attribution_influence.py",
        "tests/test_cross_modal_alignment_and_dropout_audits.py",
    ],
    "trainer_runtime_contracts": [
        "legacy_src/scripts/train_agentkernel_lite_encdec.py",
        "scripts/training_runtime_contract.py",
        "scripts/mixed_precision_runtime_contract.py",
        "scripts/audit_training_runtime_contract.py",
        "tests/test_training_runtime_contract.py",
        "tests/test_mixed_precision_runtime_contract.py",
        "tests/test_recovered_trainer_contract.py",
    ],
    "verified_transition_records": [
        "scripts/build_stage8899_verified_transition_record_schema_contract.py",
        "scripts/build_stage8900_verified_transition_record_validation_contract.py",
        "scripts/build_stage8901_verified_transition_record_no_mining_compiler_adapter.py",
        "tests/test_verified_transition_record_schema_contract.py",
        "tests/test_verified_transition_record_validation_contract.py",
        "tests/test_verified_transition_record_no_mining_compiler_adapter.py",
    ],
}

KNOWN_REMAINING_BLOCKERS = [
    "native_training_execution_authority_closed",
    "real_arxiv_dataset_loading_closed_until_pipeline_preflight",
    "trainer_cli_runtime_assertions_must_be_reverified_against_recovered_contracts",
    "decoder_ce_probe_requires_fresh_explicit_authorization_ticket",
    "denoise_probe_requires_separate_no_execution_authorization_review_then_ticket",
    "github_pr_blocked_by_unrelated_backup_branch_history",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def component_status(files: list[str]) -> dict[str, Any]:
    present = [path for path in files if (ROOT / path).exists()]
    missing = [path for path in files if not (ROOT / path).exists()]
    return {
        "required_files": len(files),
        "present_files": len(present),
        "missing_files": missing,
        "complete": not missing,
    }


def build_matrix(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    components = {name: component_status(files) for name, files in COMPONENTS.items()}
    complete = [name for name, status in components.items() if status["complete"]]
    incomplete = {name: status["missing_files"] for name, status in components.items() if not status["complete"]}
    checks = {
        "source_stage8969_passed": source.get("passed") is True,
        "component_families_present": len(components) >= 10,
        "critical_safety_modules_present": components["safety_and_path_control"]["complete"],
        "compiler_modules_present": components["dataset_judge_ranker_compiler"]["complete"],
        "telemetry_modules_present": components["telemetry_interpretability_attribution"]["complete"],
        "trainer_contract_modules_present": components["trainer_runtime_contracts"]["complete"],
        "training_remains_closed": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8969_or_8970": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8969, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TRAINING_PIPELINE_MODULE_GAP_MATRIX",
        "components": components,
        "complete_components": complete,
        "incomplete_components": incomplete,
        "known_remaining_blockers": KNOWN_REMAINING_BLOCKERS,
        "checks": checks,
        "metrics": {
            "component_families": len(components),
            "complete_component_families": len(complete),
            "incomplete_component_families": len(incomplete),
            "missing_required_files": sum(len(paths) for paths in incomplete.values()),
            "known_remaining_blockers": len(KNOWN_REMAINING_BLOCKERS),
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_attempted": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Recovered module inventory indicates the critical compiler, judge, multimodal program-state, telemetry, attribution, verifier, denoise, and trainer-contract support modules are present. Training remains blocked until the recovered trainer contract is reverified against an explicit execution ticket and real-data preflight.",
    }


def validate_matrix(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8969, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "training_authorized",
        "data_mining_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "model_execution_attempted",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_matrix(registry)
    failures = validate_matrix(card, registry)
    MATRIX.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": failures,
            **card["metrics"],
        },
        "artifacts": {"matrix": str(MATRIX.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Run a no-execution trainer contract reconciliation against the recovered module matrix, then produce an explicit real-data preflight plan before any mining or training.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Stage8970 Training Pipeline Module Gap Matrix",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage inventories recovered training/compiler support modules without mining, training, runtime execution, checkpoint loading, or `/arxiv` access.",
        "",
        "## Component Families",
        "",
    ]
    for name, status in card["components"].items():
        lines.append(f"- `{name}`: present `{status['present_files']}/{status['required_files']}`, complete `{status['complete']}`")
    lines.extend([
        "",
        "## Known Remaining Blockers",
        "",
        *[f"- `{blocker}`" for blocker in KNOWN_REMAINING_BLOCKERS],
        "",
    ])
    DOC.write_text("\n".join(lines), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8970 Training Pipeline Module Gap Matrix"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8970 inventories recovered support modules for the 100M training pipeline. The module surface is mostly present, but training remains closed pending no-execution trainer contract reconciliation and real-data preflight.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
