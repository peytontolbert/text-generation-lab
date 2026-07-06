#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9025
NAME = "stage9025_row_sample_judge_support_stack_no_data_test_validation"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9024_SUMMARY = ROOT / "runs/summaries/stage9024_row_sample_judge_support_stack_readiness.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROW_SAMPLE_JUDGE_SUPPORT_STACK_NO_DATA_TEST_VALIDATION_STAGE9025.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "row_sample_judge_support_stack_no_data_test_validation.json"

SUPPORT_TESTS = [
    "tests/test_judge_and_shortcuts.py",
    "tests/test_dataset_junk_ood_ranker_v1.py",
    "tests/test_cross_encoder_reranker_calibration.py",
    "tests/test_dataset_cartography_active_learning.py",
    "tests/test_training_data_attribution_influence.py",
    "tests/test_adversarial_hard_negative_generator.py",
    "tests/test_semantic_equivalence_metamorphic_verifier.py",
    "tests/test_confidence_ood_head_contract.py",
    "tests/test_gradient_activation_interpretability.py",
    "tests/test_training_telemetry_metrics.py",
    "tests/test_rubric_judge_calibrator.py",
    "tests/test_program_state_semantic_flow_extractors.py",
    "tests/test_row_sample_judge_support_stack_readiness_stage9024.py",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def run_tests() -> dict[str, Any]:
    command = [sys.executable, "-m", "pytest", "-q", *SUPPORT_TESTS]
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    output = (proc.stdout + "\n" + proc.stderr).strip()
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout.splitlines()[-40:],
        "stderr_tail": proc.stderr.splitlines()[-40:],
        "output_tail": output.splitlines()[-80:],
    }


def build_card(registry: dict[str, Any], test_result: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9024_SUMMARY)
    tests_exist = {test: (ROOT / test).exists() for test in SUPPORT_TESTS}
    checks = {
        "source_stage9024_present": SOURCE_9024_SUMMARY.exists(),
        "source_stage9024_passed": source.get("passed") is True,
        "support_tests_recorded": len(SUPPORT_TESTS) == 13,
        "support_tests_exist": all(tests_exist.values()),
        "pytest_passed": test_result["returncode"] == 0,
        "no_dataset_or_model_execution_authority": True,
        "authority_counts_zero": not any(
            ((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0)
            for key in AUTHORITY_CLOSED
        ),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ROW_SAMPLE_JUDGE_SUPPORT_STACK_NO_DATA_TEST_VALIDATION",
        "support_tests": SUPPORT_TESTS,
        "tests_exist": tests_exist,
        "test_result": test_result,
        "checks": checks,
        "metrics": {
            "support_tests": len(SUPPORT_TESTS),
            "support_tests_present": sum(1 for ok in tests_exist.values() if ok),
            "module_tests_executed_now": True,
            "pytest_returncode": test_result["returncode"],
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
        "decision": "The row-sample judge support-stack unit tests were executed as no-data validation. This does not run a judge, materialize outputs, compile a manifest, train, mine, execute models, or read row bodies.",
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
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
    test_result = run_tests()
    card = build_card(registry, test_result)
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
        "next_best_step": "Keep judge/materialization/manifest/training closed until an explicit row-sample judge execution ticket is authorized.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9025 Row-Sample Judge Support Stack No-Data Test Validation",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage runs the recovered support-stack unit tests only. It does not run a row-sample judge, read row/source bodies, materialize outputs, compile a manifest, train, mine, execute models, or write `/arxiv`.",
                "",
                f"Support tests: `{summary['metrics']['support_tests']}`",
                f"Pytest return code: `{summary['metrics']['pytest_returncode']}`",
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
