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
STAGE = 9092
NAME = "stage9092_trainer_command_surface_static_refresh"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9091 = ROOT / "runs/summaries/stage9091_current_frontier_reconciliation_after_route_to_loss_graph.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_COMMAND_SURFACE_STATIC_REFRESH_STAGE9092.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "trainer_command_surface_static_refresh.json"

REQUIRED_FLAGS = [
    "--repo-root",
    "--manifest",
    "--mode",
    "--max-train-rows",
    "--max-eval-rows",
    "--max-strict-rows",
    "--max-steps",
    "--max-decoder-tokens",
    "--decoder-ce-weight",
    "--structured-aux-weight",
    "--denoise-weight",
    "--require-loss-mask-enforcement-audit",
    "--require-counterfactual-obligation-audit",
    "--no-final-checkpoint-export",
    "--cleanup-checkpoints-after-probe",
    "--skip-final-model-save",
    "--output-dir",
    "--run-id",
    "--implementation",
    "--execution-authorized-for-recovery-probe",
    "--contract-only",
]

REQUIRED_MODES = [
    "structured_policy_probe",
    "repo_graph_probe",
    "symbol_binding_probe",
    "edit_localization_probe",
    "patch_operator_probe",
    "verifier_repair_probe",
    "bounded_decoder_ce_probe",
    "denoise_repair_probe",
]

REQUIRED_GUARD_TERMS = [
    "ProbeContractError",
    "validate_loss_mask_row",
    "safe_cleanup_checkpoints",
    "execution-authorized-for-recovery-probe",
    "contract-only",
    "no-final-checkpoint-export",
    "cleanup-checkpoints-after-probe",
    "decoder_ce_weight",
    "structured_aux_weight",
    "denoise_weight",
    "model_execution_authorized_next",
    "decoder_ce_training_authorized_next",
    "runtime_authorized",
    "source_emission_authorized",
    "body_emission_authorized",
    "gemma_execution_authorized_next",
    "harness_execution_authorized_next",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def trainer_text() -> str:
    return TRAINER.read_text(encoding="utf-8") if TRAINER.exists() else ""


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9091)
    text = trainer_text()
    missing_flags = [flag for flag in REQUIRED_FLAGS if flag not in text]
    missing_modes = [mode for mode in REQUIRED_MODES if mode not in text]
    missing_guards = [term for term in REQUIRED_GUARD_TERMS if term not in text]
    checks = {
        "source_stage9091_passed": source.get("passed") is True,
        "trainer_exists": TRAINER.exists(),
        "required_flags_present": missing_flags == [],
        "required_modes_present": missing_modes == [],
        "required_guard_terms_present": missing_guards == [],
        "route_to_loss_frontier_closed": (source.get("metrics") or {}).get("route_to_loss_translation_ready_now") is False,
        "model_input_rows_zero": (source.get("metrics") or {}).get("model_input_rows_now") == 0,
        "registry_frontier_stage9091": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9091,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TRAINER_COMMAND_SURFACE_STATIC_REFRESH_NO_EXECUTION",
        "trainer": str(TRAINER.relative_to(ROOT)),
        "required_flags": REQUIRED_FLAGS,
        "required_modes": REQUIRED_MODES,
        "required_guard_terms": REQUIRED_GUARD_TERMS,
        "missing_flags": missing_flags,
        "missing_modes": missing_modes,
        "missing_guard_terms": missing_guards,
        "checks": checks,
        "metrics": {
            "required_flags": len(REQUIRED_FLAGS),
            "required_modes": len(REQUIRED_MODES),
            "required_guard_terms": len(REQUIRED_GUARD_TERMS),
            "missing_flags": len(missing_flags),
            "missing_modes": len(missing_modes),
            "missing_guard_terms": len(missing_guards),
            "trainer_static_inspection_only": True,
            "trainer_executed_now": False,
            "trainer_dry_run_ready_now": False,
            "contract_only_invoked_now": False,
            "route_to_loss_translation_ready_now": False,
            "model_input_rows_now": 0,
            "candidate_rows_materialized": 0,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Trainer command surface statically contains recovered flags, modes, and guard terms required for future contract checks. This stage does not invoke the trainer, contract-only mode, route-to-loss translation, model forward, row loading, /arxiv IO, or training.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9091, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "trainer_executed_now",
        "trainer_dry_run_ready_now",
        "contract_only_invoked_now",
        "route_to_loss_translation_ready_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    for key in ["model_input_rows_now", "candidate_rows_materialized"]:
        if card["metrics"].get(key) != 0:
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
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **card["metrics"]},
        "artifacts": {"card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": card["decision"] if not failures else "Trainer command surface static refresh failed.",
        "next_best_step": "Audit trainer command surface static refresh negative cases; do not execute trainer or load rows.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9092 Trainer Command Surface Static Refresh",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Statically refreshes the recovered trainer command surface against the route-to-loss graph controls. The trainer is not invoked.",
        "",
        f"Required flags: `{card['metrics']['required_flags']}`",
        f"Missing flags: `{card['metrics']['missing_flags']}`",
        f"Required modes: `{card['metrics']['required_modes']}`",
        f"Missing modes: `{card['metrics']['missing_modes']}`",
        f"Required guard terms: `{card['metrics']['required_guard_terms']}`",
        f"Missing guard terms: `{card['metrics']['missing_guard_terms']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage9092 Trainer Command Surface Static Refresh"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9092 statically refreshes the recovered trainer command surface after route-to-loss controls. The trainer is not invoked; contract-only mode, route-to-loss translation, model forward, row loading, /arxiv IO, decoder CE, denoise CE, runtime, and training remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
