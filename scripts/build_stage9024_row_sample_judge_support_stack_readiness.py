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
STAGE = 9024
NAME = "stage9024_row_sample_judge_support_stack_readiness"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9023_SUMMARY = ROOT / "runs/summaries/stage9023_row_sample_judge_diagnostics_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROW_SAMPLE_JUDGE_SUPPORT_STACK_READINESS_STAGE9024.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "row_sample_judge_support_stack_readiness.json"

SUPPORT_MODULES = {
    "objective_row_judge": {
        "script": "scripts/objective_row_judge.py",
        "test": "tests/test_judge_and_shortcuts.py",
        "diagnostics": ["criteria_scores", "reject_reason", "loss_mask_candidates"],
    },
    "dataset_junk_ood_ranker_v1": {
        "script": "scripts/dataset_junk_ood_ranker_v1.py",
        "test": "tests/test_dataset_junk_ood_ranker_v1.py",
        "diagnostics": ["quality_score", "risk_reasons", "route"],
    },
    "structured_dataset_junk_ranker": {
        "script": "scripts/structured_dataset_junk_ranker.py",
        "test": "tests/test_judge_and_shortcuts.py",
        "diagnostics": ["risk_reason_counts", "reject_reason_counts"],
    },
    "cross_encoder_reranker_calibration": {
        "script": "scripts/cross_encoder_reranker_calibration.py",
        "test": "tests/test_cross_encoder_reranker_calibration.py",
        "diagnostics": ["confidence", "criteria_scores"],
    },
    "dataset_cartography_active_learning": {
        "script": "scripts/dataset_cartography_active_learning.py",
        "test": "tests/test_dataset_cartography_active_learning.py",
        "diagnostics": ["confidence", "risk_reasons"],
    },
    "training_data_attribution_influence": {
        "script": "scripts/training_data_attribution_influence.py",
        "test": "tests/test_training_data_attribution_influence.py",
        "diagnostics": ["risk_reasons", "blocking_reasons"],
    },
    "adversarial_hard_negative_generator": {
        "script": "scripts/adversarial_hard_negative_generator.py",
        "test": "tests/test_adversarial_hard_negative_generator.py",
        "diagnostics": ["shortcut_proxy_absent", "near_duplicate_risk_below_threshold"],
    },
    "semantic_equivalence_metamorphic_verifier": {
        "script": "scripts/semantic_equivalence_metamorphic_verifier.py",
        "test": "tests/test_semantic_equivalence_metamorphic_verifier.py",
        "diagnostics": ["criteria_scores", "reject_reason"],
    },
    "confidence_ood_head_contract": {
        "script": "scripts/confidence_ood_head_contract.py",
        "test": "tests/test_confidence_ood_head_contract.py",
        "diagnostics": ["confidence", "quality_score"],
    },
    "gradient_activation_interpretability": {
        "script": "scripts/gradient_activation_interpretability.py",
        "test": "tests/test_gradient_activation_interpretability.py",
        "diagnostics": ["criteria_scores", "feature_presence"],
    },
    "training_telemetry_metrics": {
        "script": "scripts/training_telemetry_metrics.py",
        "test": "tests/test_training_telemetry_metrics.py",
        "diagnostics": ["score_distribution", "blocking_reasons"],
    },
    "rubric_judge_calibrator": {
        "script": "scripts/rubric_judge_calibrator.py",
        "test": "tests/test_rubric_judge_calibrator.py",
        "diagnostics": ["quality_score", "criteria_scores"],
    },
    "program_state_semantic_flow_extractors": {
        "script": "scripts/program_state_data_control_flow_extractor.py",
        "test": "tests/test_program_state_semantic_flow_extractors.py",
        "diagnostics": ["feature_presence", "gate_status"],
    },
}

REQUIRED_DIAGNOSTIC_COVERAGE = [
    "quality_score",
    "confidence",
    "risk_reasons",
    "reject_reason",
    "criteria_scores",
    "feature_presence",
    "gate_status",
    "loss_mask_candidates",
    "shortcut_proxy_absent",
    "near_duplicate_risk_below_threshold",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9023_SUMMARY)
    module_rows = []
    coverage: dict[str, list[str]] = {key: [] for key in REQUIRED_DIAGNOSTIC_COVERAGE}
    for name, spec in SUPPORT_MODULES.items():
        script = ROOT / str(spec["script"])
        test = ROOT / str(spec["test"])
        diagnostics = list(spec["diagnostics"])
        for diagnostic in diagnostics:
            if diagnostic in coverage:
                coverage[diagnostic].append(name)
        module_rows.append(
            {
                "module": name,
                "script": spec["script"],
                "test": spec["test"],
                "script_exists": script.exists(),
                "test_exists": test.exists(),
                "diagnostics": diagnostics,
            }
        )
    missing_scripts = [row["module"] for row in module_rows if not row["script_exists"]]
    missing_tests = [row["module"] for row in module_rows if not row["test_exists"]]
    missing_coverage = [key for key, modules in coverage.items() if not modules]
    checks = {
        "source_stage9023_present": SOURCE_9023_SUMMARY.exists(),
        "source_stage9023_passed": source.get("passed") is True,
        "support_modules_recorded": len(SUPPORT_MODULES) >= 13,
        "support_scripts_present": not missing_scripts,
        "support_tests_present": not missing_tests,
        "diagnostic_coverage_complete": not missing_coverage,
        "body_free_support_index": True,
        "authority_counts_zero": not any(
            ((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0)
            for key in AUTHORITY_CLOSED
        ),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ROW_SAMPLE_JUDGE_SUPPORT_STACK_READINESS_NO_EXECUTION",
        "support_modules": module_rows,
        "diagnostic_coverage": coverage,
        "missing_scripts": missing_scripts,
        "missing_tests": missing_tests,
        "missing_diagnostic_coverage": missing_coverage,
        "checks": checks,
        "metrics": {
            "support_modules": len(SUPPORT_MODULES),
            "support_scripts_present": len(SUPPORT_MODULES) - len(missing_scripts),
            "support_tests_present": len(SUPPORT_MODULES) - len(missing_tests),
            "required_diagnostic_coverage": len(REQUIRED_DIAGNOSTIC_COVERAGE),
            "missing_diagnostic_coverage": len(missing_coverage),
            "module_tests_executed_now": False,
            "dataset_files_opened": False,
            "dataset_rows_loaded": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
            "judge_executed_now": False,
            "judge_outputs_materialized_now": False,
            "manifest_compile_authorized_now": False,
            "manifest_materialized_now": False,
            "trainer_dry_run_execution_authorized_now": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "gemma_execution_attempted": False,
            "harness_scoring_attempted": False,
            "arxiv_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "The row-sample judge diagnostics support stack is indexed and file-present. This stage does not execute module tests, run a judge, materialize outputs, compile a manifest, train, mine, or read row bodies.",
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "module_tests_executed_now",
        "dataset_files_opened",
        "dataset_rows_loaded",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
        "judge_executed_now",
        "judge_outputs_materialized_now",
        "manifest_compile_authorized_now",
        "manifest_materialized_now",
        "trainer_dry_run_execution_authorized_now",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
        "gemma_execution_attempted",
        "harness_scoring_attempted",
        "arxiv_write_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"card": str(CARD.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Run the listed support-module tests in a separate no-data validation stage, then keep waiting for explicit row-sample judge execution authorization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9024 Row-Sample Judge Support Stack Readiness",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage indexes the recovered support modules backing future row-sample judge diagnostics. It does not run those modules, read data, materialize judge outputs, compile a manifest, train, mine, or write `/arxiv`.",
                "",
                f"Support modules: `{summary['metrics']['support_modules']}`",
                f"Missing diagnostic coverage: `{summary['metrics']['missing_diagnostic_coverage']}`",
                f"Module tests executed now: `{summary['metrics']['module_tests_executed_now']}`",
                f"Training authorized: `{summary['metrics']['training_authorized']}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
