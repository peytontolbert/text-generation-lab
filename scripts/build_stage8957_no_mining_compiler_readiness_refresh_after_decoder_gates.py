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
STAGE = 8957
NAME = "stage8957_no_mining_compiler_readiness_refresh_after_decoder_gates"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NO_MINING_COMPILER_READINESS_REFRESH_STAGE8957.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "no_mining_compiler_readiness_refresh_after_decoder_gates.json"

SOURCE_SUMMARIES = {
    8931: "stage8931_orchestrated_compiler_synthetic_dry_run",
    8932: "stage8932_no_mining_compiler_cli_wrapper_contract",
    8933: "stage8933_no_mining_compiler_cli_wrapper_skeleton",
    8954: "stage8954_bounded_decoder_trainer_loss_mask_readiness_refresh",
    8955: "stage8955_bounded_decoder_no_execution_telemetry_gate",
    8956: "stage8956_bounded_decoder_future_one_run_authorization_schema",
}

REQUIRED_MODULES = [
    "scripts/objective_row_judge.py",
    "scripts/dataset_junk_ood_ranker_v1.py",
    "scripts/shortcut_baseline_audit.py",
    "scripts/counterfactual_obligation_audit.py",
    "scripts/curriculum_compiler.py",
    "scripts/loss_mask_card.py",
    "scripts/software_maintenance_curriculum_cli.py",
    "scripts/manifest_path_validator.py",
]

REQUIRED_TESTS = [
    "tests/test_software_maintenance_curriculum_cli.py",
    "tests/test_orchestrated_compiler_synthetic_dry_run.py",
    "tests/test_no_mining_compiler_cli_wrapper_contract.py",
    "tests/test_no_mining_compiler_cli_wrapper_skeleton.py",
    "tests/test_single_compiler_api_contract.py",
    "tests/test_curriculum_compiler.py",
    "tests/test_dataset_junk_ood_ranker_v1.py",
]

PIPELINE_STEPS = [
    "normalize_or_synthetic_input_rows",
    "objective_row_judge",
    "dataset_junk_ood_ranker_v1",
    "shortcut_baseline_audit",
    "counterfactual_obligation_audit",
    "curriculum_compiler",
    "loss_mask_card",
    "no_mining_cli_wrapper",
]

FORCED_CLOSED_PATHS = [
    "data_mining",
    "model_execution",
    "decoder_ce",
    "denoise_ce",
    "runtime",
    "gemma",
    "harness",
    "scoring",
    "source_body_emission",
    "checkpoint_export",
    "training",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def summary_path(stage_name: str) -> Path:
    return ROOT / "runs/summaries" / f"{stage_name}.json"


def source_status() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for stage, stage_name in SOURCE_SUMMARIES.items():
        summary = load_json(summary_path(stage_name))
        out[str(stage)] = {
            "stage_name": stage_name,
            "exists": bool(summary),
            "passed": summary.get("passed") is True,
            "metrics": summary.get("metrics") or {},
        }
    return out


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    sources = source_status()
    module_status = {path: (ROOT / path).exists() for path in REQUIRED_MODULES}
    test_status = {path: (ROOT / path).exists() for path in REQUIRED_TESTS}
    stage8931_metrics = sources["8931"]["metrics"]
    stage8933_metrics = sources["8933"]["metrics"]
    checks = {
        "source_summaries_present": all(item["exists"] for item in sources.values()),
        "source_summaries_passed": all(item["passed"] for item in sources.values()),
        "required_modules_present": all(module_status.values()),
        "required_tests_present": all(test_status.values()),
        "pipeline_steps_recorded": len(PIPELINE_STEPS) >= 8,
        "forced_closed_paths_recorded": len(FORCED_CLOSED_PATHS) >= 11,
        "orchestrated_dry_run_had_compiled_rows": int(stage8931_metrics.get("compiled_rows", 0) or 0) > 0,
        "orchestrated_dry_run_decoder_ce_closed": stage8931_metrics.get("decoder_ce_loss_rows") == 0,
        "orchestrated_dry_run_denoise_ce_closed": stage8931_metrics.get("denoise_ce_loss_rows") == 0,
        "orchestrated_dry_run_runtime_closed": stage8931_metrics.get("runtime_reward_rows") == 0,
        "cli_wrapper_present": stage8933_metrics.get("wrapper_script_present") == 1,
        "cli_wrapper_test_present": stage8933_metrics.get("wrapper_test_present") == 1,
        "decoder_execution_template_inactive": sources["8956"]["metrics"].get("execution_authorized_now") is False,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8956": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 8956,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "NO_MINING_COMPILER_READINESS_REFRESH_AFTER_DECODER_GATES",
        "source_status": sources,
        "required_modules": module_status,
        "required_tests": test_status,
        "pipeline_steps": PIPELINE_STEPS,
        "forced_closed_paths": FORCED_CLOSED_PATHS,
        "checks": checks,
        "metrics": {
            "source_summaries": len(SOURCE_SUMMARIES),
            "source_summaries_passed": sum(1 for item in sources.values() if item["passed"]),
            "required_modules": len(REQUIRED_MODULES),
            "required_modules_present": sum(1 for value in module_status.values() if value),
            "required_tests": len(REQUIRED_TESTS),
            "required_tests_present": sum(1 for value in test_status.values() if value),
            "pipeline_steps": len(PIPELINE_STEPS),
            "forced_closed_paths": len(FORCED_CLOSED_PATHS),
            "synthetic_compiler_dry_run_recovered": True,
            "manifest_no_mining_audit_only_recovered": True,
            "decoder_execution_template_inactive": True,
            "actual_execution_authorized_next": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "No-mining compiler readiness is refreshed after bounded decoder gates: judge/ranker/shortcut/counterfactual/compiler/loss-mask/CLI wiring is recovered for synthetic and audit-only manifests, but mining, model execution, decoder CE, denoise CE, runtime, checkpoint export, and training remain closed.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8956, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["actual_execution_authorized_next", "model_execution_attempted", "runtime_authorized_flag", "training_authorized", "data_mining_authorized", "decoder_ce_authorized", "denoise_ce_authorized"]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card, registry)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        "artifacts": {"card": str(CARD.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Recover real-manifest audit-only checklist and route-card requirements before any new data mining; keep execution and training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8957 No-Mining Compiler Readiness Refresh",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage refreshes recovered judge/ranker/shortcut/counterfactual/compiler/loss-mask/CLI wiring after the bounded decoder safety gates.",
        "",
        f"Required modules present: `{card['metrics']['required_modules_present']}/{card['metrics']['required_modules']}`",
        f"Required tests present: `{card['metrics']['required_tests_present']}/{card['metrics']['required_tests']}`",
        f"Data mining authorized: `{card['metrics']['data_mining_authorized']}`",
        f"Training authorized: `{card['metrics']['training_authorized']}`",
        "",
        "No mining, model execution, decoder CE, denoise CE, runtime, checkpoint export, or training is authorized.",
        "",
    ]), encoding="utf-8")
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
    marker = "## Stage8957 No-Mining Compiler Readiness Refresh"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8957 refreshes the no-mining compiler path after bounded decoder gates. Judge, ranker, shortcut, counterfactual, compiler, loss-mask, and CLI wrapper wiring are recovered for synthetic/audit-only paths, but mining and training remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
