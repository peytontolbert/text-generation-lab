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
STAGE = 8954
NAME = "stage8954_bounded_decoder_trainer_loss_mask_readiness_refresh"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDED_DECODER_TRAINER_LOSS_MASK_READINESS_STAGE8954.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "bounded_decoder_trainer_loss_mask_readiness_refresh.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"

SOURCE_SUMMARIES = {
    8592: "stage8592_reconstructed_bounded_decoder_ce_candidate_and_loss_mask_package",
    8593: "stage8593_reconstructed_bounded_decoder_ce_contract_probe_audit",
    8594: "stage8594_reconstructed_bounded_decoder_ce_final_pre_execution_audit",
    8953: "stage8953_training_readiness_matrix_refresh_after_converter_contracts",
}

REQUIRED_TRAINER_FLAGS = [
    "--repo-root",
    "--manifest",
    "--mode",
    "--max-train-rows",
    "--max-eval-rows",
    "--max-strict-rows",
    "--max-steps",
    "--decoder-ce-weight",
    "--structured-aux-weight",
    "--denoise-weight",
    "--require-loss-mask-enforcement-audit",
    "--require-counterfactual-obligation-audit",
    "--no-final-checkpoint-export",
    "--cleanup-checkpoints-after-probe",
    "--skip-final-model-save",
    "--execution-authorized-for-recovery-probe",
    "--output-dir",
    "--run-id",
    "--implementation",
    "--tokenizer-json",
    "--tokenizer-config",
]

REQUIRED_RUNTIME_GUARD_STRINGS = [
    "model execution is disabled unless --execution-authorized-for-recovery-probe is present",
    "bounded_decoder_ce_probe",
    "contract-only",
    "unsafe_loss_rows",
    "over_cap_rows",
    "final_checkpoint_export_disabled",
    "final_model_save_skipped",
    "cleanup_dry_run.json",
    "target_implementation_guard",
    "contract requires transformer",
]

EXPECTED_RECOVERED_CAPS = {
    "train": 32,
    "eval": 16,
    "strict_eval": 16,
    "max_steps": 16,
    "loss_mask_rows": 64,
}

REQUIRED_FOCUSED_TESTS = [
    "tests/test_recovered_trainer_contract.py",
    "tests/test_training_readiness_matrix_refresh_after_converter_contracts_stage8953.py",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def summary_path(stage_name: str) -> Path:
    return ROOT / "runs/summaries" / f"{stage_name}.json"


def source_status() -> dict[str, dict[str, Any]]:
    status: dict[str, dict[str, Any]] = {}
    for stage, stage_name in SOURCE_SUMMARIES.items():
        summary = load_json(summary_path(stage_name))
        status[str(stage)] = {
            "stage_name": stage_name,
            "exists": bool(summary),
            "passed": summary.get("passed") is True,
            "metrics": summary.get("metrics") or {},
        }
    return status


def trainer_static_contract() -> dict[str, Any]:
    text = TRAINER.read_text(encoding="utf-8") if TRAINER.exists() else ""
    missing_flags = [flag for flag in REQUIRED_TRAINER_FLAGS if flag not in text]
    missing_guards = [guard for guard in REQUIRED_RUNTIME_GUARD_STRINGS if guard not in text]
    return {
        "trainer_path": str(TRAINER.relative_to(ROOT)),
        "trainer_exists": TRAINER.exists(),
        "required_flags": REQUIRED_TRAINER_FLAGS,
        "missing_required_flags": missing_flags,
        "required_runtime_guard_strings": REQUIRED_RUNTIME_GUARD_STRINGS,
        "missing_runtime_guard_strings": missing_guards,
    }


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    sources = source_status()
    trainer = trainer_static_contract()
    stage8592_metrics = sources["8592"]["metrics"]
    stage8593_metrics = sources["8593"]["metrics"]
    stage8594_metrics = sources["8594"]["metrics"]
    checks = {
        "source_summaries_present": all(item["exists"] for item in sources.values()),
        "source_summaries_passed": all(item["passed"] for item in sources.values()),
        "trainer_exists": trainer["trainer_exists"],
        "trainer_required_flags_present": trainer["missing_required_flags"] == [],
        "trainer_runtime_guard_strings_present": trainer["missing_runtime_guard_strings"] == [],
        "loss_mask_package_rows_recovered": stage8592_metrics.get("loss_mask_rows") == EXPECTED_RECOVERED_CAPS["loss_mask_rows"],
        "loss_mask_package_caps_recovered": stage8592_metrics.get("loss_mask_split_counts") == {"eval": 16, "other": 0, "strict_eval": 16, "train": 32},
        "loss_mask_package_unsafe_rows_zero": stage8592_metrics.get("unsafe_loss_rows") == 0,
        "contract_probe_no_model_execution": stage8593_metrics.get("model_execution_attempted") is False,
        "final_pre_execution_audit_passed": stage8594_metrics.get("final_pre_execution_audit_passed") is True,
        "final_pre_execution_still_not_authorized": stage8594_metrics.get("actual_execution_authorized_next") is False,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8953": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 8953,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "BOUNDED_DECODER_TRAINER_LOSS_MASK_READINESS_CONTRACT_ONLY",
        "source_status": sources,
        "trainer_static_contract": trainer,
        "expected_recovered_caps": EXPECTED_RECOVERED_CAPS,
        "required_focused_tests": REQUIRED_FOCUSED_TESTS,
        "checks": checks,
        "metrics": {
            "source_summaries": len(SOURCE_SUMMARIES),
            "source_summaries_passed": sum(1 for item in sources.values() if item["passed"]),
            "trainer_missing_required_flags": len(trainer["missing_required_flags"]),
            "trainer_missing_runtime_guard_strings": len(trainer["missing_runtime_guard_strings"]),
            "loss_mask_rows": int(stage8592_metrics.get("loss_mask_rows", 0) or 0),
            "unsafe_loss_rows": int(stage8592_metrics.get("unsafe_loss_rows", 0) or 0),
            "over_cap_rows": int(stage8594_metrics.get("over_cap_rows", 0) or 0),
            "trainer_help_missing_flags": int(stage8594_metrics.get("trainer_help_missing_flags", -1) or 0),
            "actual_execution_authorized_next": False,
            "contract_only_probe_available": True,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "The bounded decoder trainer command/loss-mask contract is recovered enough for no-execution contract checks: required flags and runtime guard strings are present, recovered loss-mask rows are capped and safe, and the final pre-execution audit remains non-authorizing. This does not permit model execution, converter execution, mining, decoder CE, denoise CE, runtime, checkpoint export, or training.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8953, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["actual_execution_authorized_next", "model_execution_attempted", "runtime_authorized_flag", "training_authorized", "data_mining_authorized", "decoder_ce_authorized", "denoise_ce_authorized"]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    if card["metrics"].get("trainer_missing_required_flags") != 0:
        failures.append("trainer_missing_required_flags")
    if card["metrics"].get("trainer_missing_runtime_guard_strings") != 0:
        failures.append("trainer_missing_runtime_guard_strings")
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
        "next_best_step": "Recover the bounded decoder CE no-execution telemetry gate against the current artifact contract before any execution ticket is considered.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8954 Bounded Decoder Trainer/Loss-Mask Readiness",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage refreshes the recovered bounded decoder trainer command and loss-mask contract. It statically confirms required flags, runtime guard strings, capped reconstructed loss-mask rows, and the prior non-authorizing final pre-execution audit.",
        "",
        f"Loss-mask rows: `{card['metrics']['loss_mask_rows']}`",
        f"Unsafe loss rows: `{card['metrics']['unsafe_loss_rows']}`",
        f"Actual execution authorized next: `{card['metrics']['actual_execution_authorized_next']}`",
        "",
        "No model execution, runtime, mining, decoder CE, denoise CE, checkpoint export, or training is authorized.",
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
    marker = "## Stage8954 Bounded Decoder Trainer/Loss-Mask Readiness"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8954 refreshes the recovered trainer command/loss-mask contract for bounded decoder CE. The no-execution contract is recovered, but model execution, mining, decoder CE, denoise CE, runtime, checkpoint export, and training remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
