#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8971
NAME = "stage8971_trainer_contract_reconciliation_no_execution"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_CONTRACT_RECONCILIATION_NO_EXECUTION_STAGE8971.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "trainer_contract_reconciliation_no_execution.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8970_training_pipeline_module_gap_matrix.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"

REQUIRED_FLAGS = [
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
    "--no-final-checkpoint-export",
    "--cleanup-checkpoints-after-probe",
    "--skip-final-model-save",
    "--output-dir",
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

REQUIRED_TELEMETRY_TERMS = [
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_token_loss.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "feature_ablation_attribution.jsonl",
    "activation_patch_recovery.jsonl",
    "row_dynamics_history.jsonl",
    "module_delta_norms.json",
    "cleanup_proof.json",
]

REQUIRED_SAFETY_TERMS = [
    "validate_loss_mask_row",
    "safe_cleanup_checkpoints",
    "evaluate_implementation_selection",
    "checkpoint export must remain disabled",
    "output_dir must be under repo_root",
    "contract_only=true",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def help_text() -> str:
    return subprocess.check_output(["python", str(TRAINER), "--help"], cwd=ROOT, text=True)


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    help_out = help_text()
    trainer_text = TRAINER.read_text(encoding="utf-8")
    missing_flags = [flag for flag in REQUIRED_FLAGS if flag not in help_out]
    missing_modes = [mode for mode in REQUIRED_MODES if mode not in help_out]
    missing_telemetry = [term for term in REQUIRED_TELEMETRY_TERMS if term not in trainer_text]
    missing_safety = [term for term in REQUIRED_SAFETY_TERMS if term not in trainer_text]
    checks = {
        "source_stage8970_passed": source.get("passed") is True,
        "trainer_exists": TRAINER.exists(),
        "required_flags_present": not missing_flags,
        "required_modes_present": not missing_modes,
        "required_telemetry_terms_present": not missing_telemetry,
        "required_safety_terms_present": not missing_safety,
        "contract_only_available": "--contract-only" in help_out,
        "execution_requires_explicit_flag": "--execution-authorized-for-recovery-probe" in help_out,
        "no_execution_performed_by_stage": True,
        "training_remains_closed": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8970_or_8971": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8970, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TRAINER_CONTRACT_RECONCILIATION_NO_EXECUTION",
        "missing_flags": missing_flags,
        "missing_modes": missing_modes,
        "missing_telemetry_terms": missing_telemetry,
        "missing_safety_terms": missing_safety,
        "checks": checks,
        "metrics": {
            "required_flags": len(REQUIRED_FLAGS),
            "missing_flags": len(missing_flags),
            "required_modes": len(REQUIRED_MODES),
            "missing_modes": len(missing_modes),
            "required_telemetry_terms": len(REQUIRED_TELEMETRY_TERMS),
            "missing_telemetry_terms": len(missing_telemetry),
            "required_safety_terms": len(REQUIRED_SAFETY_TERMS),
            "missing_safety_terms": len(missing_safety),
            "trainer_help_invoked": True,
            "trainer_contract_only_invoked": False,
            "model_execution_attempted": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Trainer command surface now exposes the recovered probe modes, safety flags, loss-mask controls, telemetry terms, and explicit execution gate. This stage did not run contract-only output generation or model training; execution remains closed pending a fresh ticket.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8970, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "trainer_contract_only_invoked",
        "model_execution_attempted",
        "training_authorized",
        "data_mining_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
    ]:
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
        "artifacts": {"contract_reconciliation": str(CARD.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Design a real-data preflight plan that checks /arxiv dataset and repository availability without loading training data, then require an explicit ticket before any contract-only trainer dry run or training execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8971 Trainer Contract Reconciliation No-Execution",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage invokes trainer `--help` only. It does not run contract-only artifact generation, model execution, training, mining, runtime, or `/arxiv` access.",
        "",
        f"Missing flags: `{card['missing_flags']}`",
        f"Missing modes: `{card['missing_modes']}`",
        f"Missing telemetry terms: `{card['missing_telemetry_terms']}`",
        f"Missing safety terms: `{card['missing_safety_terms']}`",
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
    marker = "## Stage8971 Trainer Contract Reconciliation No-Execution"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8971 statically reconciles the recovered trainer CLI and telemetry contract. The interface is present, but contract-only generation and training remain closed pending explicit tickets.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
