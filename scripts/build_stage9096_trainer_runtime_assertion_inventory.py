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
STAGE = 9096
NAME = "stage9096_trainer_runtime_assertion_inventory"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9095 = ROOT / "runs/summaries/stage9095_current_frontier_reconciliation_after_trainer_command_graph.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_RUNTIME_ASSERTION_INVENTORY_STAGE9096.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
INVENTORY = OUT_DIR / "trainer_runtime_assertion_inventory.json"

ASSERTION_FAMILIES = {
    "manifest_and_repo_path": [
        "manifest does not exist",
        "output_dir must be under repo_root",
        "_manifest_hash",
        "read_jsonl",
    ],
    "row_caps_and_splits": [
        "train rows",
        "eval rows",
        "strict rows",
        "unexpected split rows",
        "max_train_rows",
        "max_eval_rows",
        "max_strict_rows",
    ],
    "loss_mask_enforcement": [
        "normalize_loss_mask",
        "validate_loss_mask_row",
        "--require-loss-mask-enforcement-audit is required",
        "unsafe loss-mask rows present",
        "enabled_losses",
        "forbidden_losses",
    ],
    "authority_closure": [
        "AUTHORITY_FLAGS",
        "_row_authority",
        "authority rows present",
        "model_execution_authorized_next",
        "decoder_ce_training_authorized_next",
        "runtime_authorized",
    ],
    "decoder_budget_and_targets": [
        "_target_token_len",
        "target token over-cap rows present",
        "empty decoder target rows present",
        "max_decoder_tokens",
        "_decoder_target_text",
    ],
    "weight_mode_guards": [
        "bounded decoder CE probe requires --decoder-ce-weight > 0",
        "bounded decoder CE probe requires --structured-aux-weight 0",
        "bounded decoder CE probe requires --denoise-weight 0",
        "structured probes require --decoder-ce-weight 0",
        "denoise repair probe requires --denoise-weight > 0",
    ],
    "checkpoint_export_guards": [
        "--no-final-checkpoint-export is required",
        "--skip-final-model-save 1 is required",
        "checkpoint export must remain disabled",
        "final_checkpoint_export_disabled",
        "final_model_save_skipped",
    ],
    "execution_gates": [
        "contract_only",
        "execution_authorized_for_recovery_probe",
        "model execution is disabled unless --execution-authorized-for-recovery-probe is present",
        "cannot execute recovery probe because contract did not pass",
        "execution is not restored for mode",
    ],
    "cleanup_guards": [
        "safe_cleanup_checkpoints",
        "UnsafePathError",
        "safe cleanup dry-run refused",
        ".agentkernel_probe_output",
        "cleanup_dry_run.json",
        "cleanup_proof.json",
    ],
    "implementation_and_tokenizer_guards": [
        "evaluate_implementation_selection",
        "implementation_contract",
        "transformer_execution_requires_explicit_authorization",
        "tokenizer_contract",
        "target_100m_vocab_size",
        "byte_fallback_used_when_unset",
    ],
}

REQUIRED_TELEMETRY_ARTIFACTS = [
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_token_loss.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "feature_ablation_attribution.jsonl",
    "activation_patch_recovery.jsonl",
    "internal_token_logit_summary.json",
    "row_dynamics_history.jsonl",
    "eos_length_audit.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
    "sample_generation_audit.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def trainer_text() -> str:
    return TRAINER.read_text(encoding="utf-8") if TRAINER.exists() else ""


def build_inventory(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9095)
    text = trainer_text()
    missing_by_family = {
        family: [term for term in terms if term not in text]
        for family, terms in ASSERTION_FAMILIES.items()
    }
    missing_telemetry = [artifact for artifact in REQUIRED_TELEMETRY_ARTIFACTS if artifact not in text]
    checks = {
        "source_stage9095_passed": source.get("passed") is True,
        "trainer_exists": TRAINER.exists(),
        "assertion_families_complete": all(not missing for missing in missing_by_family.values()),
        "telemetry_artifacts_declared": missing_telemetry == [],
        "trainer_command_graph_frontier_closed": (source.get("metrics") or {}).get("trainer_executed_now") is False,
        "contract_only_frontier_closed": (source.get("metrics") or {}).get("contract_only_invoked_now") is False,
        "registry_frontier_stage9095": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9095,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TRAINER_RUNTIME_ASSERTION_INVENTORY_NO_INVOCATION",
        "trainer": str(TRAINER.relative_to(ROOT)),
        "assertion_families": ASSERTION_FAMILIES,
        "missing_by_family": missing_by_family,
        "required_telemetry_artifacts": REQUIRED_TELEMETRY_ARTIFACTS,
        "missing_telemetry_artifacts": missing_telemetry,
        "checks": checks,
        "metrics": {
            "assertion_families": len(ASSERTION_FAMILIES),
            "assertion_terms": sum(len(terms) for terms in ASSERTION_FAMILIES.values()),
            "families_with_missing_terms": sum(1 for missing in missing_by_family.values() if missing),
            "missing_assertion_terms": sum(len(missing) for missing in missing_by_family.values()),
            "required_telemetry_artifacts": len(REQUIRED_TELEMETRY_ARTIFACTS),
            "missing_telemetry_artifacts": len(missing_telemetry),
            "trainer_static_inspection_only": True,
            "trainer_executed_now": False,
            "contract_only_invoked_now": False,
            "runtime_assertions_executed_now": False,
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
        "decision": "Trainer runtime assertion inventory is complete by static inspection. This stage does not invoke the trainer, contract-only mode, runtime assertions, route-to-loss translation, model forward, row loading, /arxiv IO, or training.",
    }


def validate_inventory(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9095, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "trainer_executed_now",
        "contract_only_invoked_now",
        "runtime_assertions_executed_now",
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
    inventory = build_inventory(registry)
    failures = validate_inventory(inventory, registry)
    INVENTORY.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **inventory["metrics"]},
        "artifacts": {"inventory": str(INVENTORY.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": inventory["decision"] if not failures else "Trainer runtime assertion inventory failed.",
        "next_best_step": "Audit trainer runtime assertion inventory negative cases; do not execute trainer or load rows.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9096 Trainer Runtime Assertion Inventory",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Statically inventories recovered trainer runtime assertion families. The trainer is not invoked.",
        "",
        f"Assertion families: `{inventory['metrics']['assertion_families']}`",
        f"Missing assertion terms: `{inventory['metrics']['missing_assertion_terms']}`",
        f"Required telemetry artifacts: `{inventory['metrics']['required_telemetry_artifacts']}`",
        f"Missing telemetry artifacts: `{inventory['metrics']['missing_telemetry_artifacts']}`",
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
    marker = "## Stage9096 Trainer Runtime Assertion Inventory"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9096 statically inventories trainer runtime assertion families and telemetry artifact requirements. The trainer is not invoked; contract-only mode, route-to-loss translation, model forward, row loading, /arxiv IO, decoder CE, denoise CE, runtime, and training remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
