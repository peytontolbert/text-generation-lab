#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED, apply_diagnostic_gate_fields, audit_diagnostic_ticket_fields
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED, apply_diagnostic_gate_fields, audit_diagnostic_ticket_fields  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9264
NAME = "stage9264_stabilized_bounded_decoder_execution_review"
SOURCE_PREFLIGHT = ROOT / "runs/summaries/stage9263_stabilized_bounded_decoder_contract_preflight.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STABILIZED_BOUNDED_DECODER_EXECUTION_REVIEW_STAGE9264.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TICKET = OUT_DIR / "stabilized_bounded_decoder_execution_review_inactive.json"
AUDIT = OUT_DIR / "stabilized_bounded_decoder_execution_review_audit.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

MANIFEST = "runs/local/artifacts/stage9249_semantic_bounded_decoder_target_repair_package/semantic_bounded_decoder_target_repair_manifest.jsonl"
OUTPUT_DIR = "runs/local/artifacts/stage9265_stabilized_target_100m_bounded_decoder_probe/bounded_decoder_probe"
RUN_ID = "stage9265_stabilized_target_100m_bounded_decoder_probe"
MANIFEST_SHA = "e9cf97f57f92b710e01b72350178c557a5ca7e05dbb44c7a29a8a7aedce8d06b"

REQUIRED_LIMITS = {
    "mode": "bounded_decoder_ce_probe",
    "probe_scale": "target_100m",
    "implementation": "transformer",
    "max_train_rows": 32,
    "max_eval_rows": 16,
    "max_strict_rows": 16,
    "max_steps": 16,
    "batch_size": 2,
    "max_encoder_tokens": 256,
    "max_decoder_tokens": 768,
    "learning_rate": 1e-5,
    "decoder_ce_weight": 1.0,
    "eos_loss_weight": 4.0,
    "structured_aux_weight": 0.0,
    "denoise_weight": 0.0,
    "generation_audit_enabled": True,
    "max_generation_rows": 16,
    "max_generation_tokens": 96,
    "runtime": False,
    "gemma": False,
    "harness": False,
    "scoring": False,
    "source_body_emission": False,
    "final_checkpoint_export": False,
    "cleanup_checkpoints_after_probe": True,
}

DENIED_NOW = [
    "run_trainer",
    "instantiate_model",
    "run_model_forward",
    "run_training_step",
    "run_backward",
    "write_checkpoint",
    "export_checkpoint",
    "open_runtime",
    "call_gemma",
    "run_harness",
    "score_output",
    "emit_source_body",
    "promote_model",
    "walk_arxiv",
    "mine_repositories",
    "cleanup_checkpoints",
]

FUTURE_ARGV = [
    "conda", "run", "-n", "trellis", "python", "legacy_src/scripts/train_agentkernel_lite_encdec.py",
    "--repo-root", str(ROOT),
    "--manifest", MANIFEST,
    "--mode", "bounded_decoder_ce_probe",
    "--max-train-rows", "32",
    "--max-eval-rows", "16",
    "--max-strict-rows", "16",
    "--max-steps", "16",
    "--max-decoder-tokens", "768",
    "--decoder-ce-weight", "1.0",
    "--eos-loss-weight", "4.0",
    "--structured-aux-weight", "0.0",
    "--denoise-weight", "0.0",
    "--require-loss-mask-enforcement-audit",
    "--no-final-checkpoint-export",
    "--cleanup-checkpoints-after-probe",
    "--skip-final-model-save", "1",
    "--output-dir", OUTPUT_DIR,
    "--run-id", RUN_ID,
    "--batch-size", "2",
    "--max-encoder-tokens", "256",
    "--learning-rate", "1e-5",
    "--implementation", "transformer",
    "--probe-scale", "target_100m",
    "--model-config", "configs/model/agentkernel_100m_seq2seq_recovered_target.json",
    "--tokenizer-json", "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json",
    "--tokenizer-config", "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json",
    "--tokenizer-hashlock", "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json",
    "--enable-generation-audit",
    "--max-generation-rows", "16",
    "--max-generation-tokens", "96",
    "--execution-authorized-for-recovery-probe",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_ticket(source_preflight: dict[str, Any]) -> dict[str, Any]:
    ticket = {
        "ticket_id": "stage9264_stabilized_bounded_decoder_execution_review__inactive",
        "ticket_status": "DESIGN_ONLY_INACTIVE",
        "requested_stage": 9265,
        "requested_stage_name": RUN_ID,
        "requested_capability": "stabilized_target_100m_bounded_decoder_ce_probe",
        "source_stage": 9263,
        "source_manifest_path": MANIFEST,
        "source_manifest_sha256": (source_preflight.get("metrics") or {}).get("manifest_sha256"),
        "future_output_dir": OUTPUT_DIR,
        "future_argv": list(FUTURE_ARGV),
        "command_materialized_for_review_only": True,
        "command_executable_now": False,
        "requires_explicit_user_authorization": True,
        "explicit_user_authorization_observed": True,
        "requires_fresh_pre_execution_audit": False,
        "execution_authorized_now": False,
        "model_execution_authorized_now": False,
        "decoder_ce_training_authorized_now": False,
        "allowed_operations_now": [],
        "denied_operations_now": list(DENIED_NOW),
        "required_limits": dict(REQUIRED_LIMITS),
        "authority": dict(AUTHORITY_CLOSED),
    }
    return apply_diagnostic_gate_fields(ticket)


def audit_ticket(ticket: dict[str, Any], source_preflight: dict[str, Any]) -> dict[str, Any]:
    failures = audit_diagnostic_ticket_fields(ticket)
    metrics = source_preflight.get("metrics") or {}
    if source_preflight.get("passed") is not True:
        failures.append("source_stage9263_not_passed")
    if metrics.get("manifest_sha256") != MANIFEST_SHA:
        failures.append("manifest_hash_mismatch")
    if metrics.get("eos_loss_weight") != 4.0:
        failures.append("source_eos_weight_not_4")
    if metrics.get("model_execution_attempted") is not False:
        failures.append("source_preflight_attempted_execution")
    for key, expected in REQUIRED_LIMITS.items():
        if (ticket.get("required_limits") or {}).get(key) != expected:
            failures.append(f"limit_mismatch:{key}")
    if ticket.get("execution_authorized_now") is not False:
        failures.append("execution_authorized_now_not_false")
    if ticket.get("allowed_operations_now") != []:
        failures.append("allowed_operations_now_not_empty")
    if any((ticket.get("authority") or {}).values()):
        failures.append("authority_open")
    if not str(ticket.get("future_output_dir", "")).startswith("runs/local/artifacts/"):
        failures.append("future_output_dir_not_artifact_local")
    if "/arxiv" in str(ticket.get("future_output_dir", "")):
        failures.append("future_output_dir_mentions_arxiv")
    return {"passed": not failures, "failures": failures, "diagnostic_contract_failures": audit_diagnostic_ticket_fields(ticket)}


def negative_cases(ticket: dict[str, Any], source_preflight: dict[str, Any]) -> list[dict[str, Any]]:
    cases = []
    for name, mutator in [
        ("execution_opened", lambda t: t.update({"execution_authorized_now": True})),
        ("allowed_ops_opened", lambda t: t.update({"allowed_operations_now": ["run_trainer"]})),
        ("eos_weight_changed", lambda t: t["required_limits"].update({"eos_loss_weight": 1.0})),
        ("lr_widened", lambda t: t["required_limits"].update({"learning_rate": 5e-5})),
        ("runtime_opened", lambda t: t["required_limits"].update({"runtime": True})),
        ("authority_opened", lambda t: t["authority"].update({"model_execution_authorized_next": True})),
    ]:
        mutated = copy.deepcopy(ticket)
        mutator(mutated)
        audit = audit_ticket(mutated, source_preflight)
        cases.append({"case": name, "rejected": audit["passed"] is False, "failures": audit["failures"]})
    return cases


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_PREFLIGHT)
    ticket = build_ticket(source)
    audit = audit_ticket(ticket, source)
    negatives = negative_cases(ticket, source)
    if not all(case["rejected"] for case in negatives):
        audit["passed"] = False
        audit["failures"].append("negative_cases_not_rejected")
    TICKET.write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AUDIT.write_text(json.dumps({**audit, "negative_cases": negatives}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "negative_cases": len(negatives), "negative_cases_rejected": sum(1 for case in negatives if case["rejected"]), "execution_authorized_now": False, "explicit_user_authorization_observed": True, "eos_loss_weight": 4.0, "learning_rate": 1e-5},
        "artifacts": {"ticket": str(TICKET.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built an inactive execution review for one stabilized target-100M bounded decoder rerun. The ticket records the authorized future command but opens no current authority.",
        "next_best_step": "Run the reviewed Stage9265 stabilized target-100M bounded decoder probe once, then audit generation quality against Stage9261 gates.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("# Stage9264 Stabilized Bounded Decoder Execution Review\n\nInactive review ticket for one stabilized target-100M rerun. Current authority remains closed; future command uses EOS loss weight 4.0 and LR 1e-5.\n", encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
