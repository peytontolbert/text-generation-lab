#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9379
NAME = "stage9379_bounded_decoder_ce_readiness_bridge"
SOURCE_DENOISE = ROOT / "runs/summaries/stage9378_full_rejoin_probe_audit.json"
SOURCE_DECODER_FAILURE = ROOT / "runs/summaries/stage9266_stage9265_stabilized_probe_diagnostic_audit.json"
SOURCE_DENOISE_SEED = ROOT / "runs/summaries/stage9267_repetition_to_denoise_repair_manifest.json"
SOURCE_DECODER_PACKAGE = ROOT / "runs/summaries/stage9249_semantic_bounded_decoder_target_repair_package.json"
SOURCE_TRAINER_READY = ROOT / "runs/summaries/stage8954_bounded_decoder_trainer_loss_mask_readiness_refresh.json"
SOURCE_PREFLIGHT = ROOT / "runs/summaries/stage9263_stabilized_bounded_decoder_contract_preflight.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BRIDGE = OUT_DIR / "bounded_decoder_ce_readiness_bridge.json"
AUDIT = OUT_DIR / "bounded_decoder_ce_readiness_bridge_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDED_DECODER_CE_READINESS_BRIDGE_STAGE9379.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def truthy_metric(summary: dict[str, Any], key: str) -> bool:
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    return bool(metrics.get(key))


def build_bridge() -> dict[str, Any]:
    denoise = load_json(SOURCE_DENOISE)
    decoder_failure = load_json(SOURCE_DECODER_FAILURE)
    denoise_seed = load_json(SOURCE_DENOISE_SEED)
    decoder_package = load_json(SOURCE_DECODER_PACKAGE)
    trainer_ready = load_json(SOURCE_TRAINER_READY)
    preflight = load_json(SOURCE_PREFLIGHT)
    dm = denoise.get("metrics") if isinstance(denoise.get("metrics"), dict) else {}
    fm = decoder_failure.get("metrics") if isinstance(decoder_failure.get("metrics"), dict) else {}
    sm = denoise_seed.get("metrics") if isinstance(denoise_seed.get("metrics"), dict) else {}
    pm = decoder_package.get("metrics") if isinstance(decoder_package.get("metrics"), dict) else {}
    tm = trainer_ready.get("metrics") if isinstance(trainer_ready.get("metrics"), dict) else {}
    cm = preflight.get("metrics") if isinstance(preflight.get("metrics"), dict) else {}
    return {
        "stage": STAGE,
        "name": NAME,
        "purpose": "Bridge the passed denoise repair loop back to bounded decoder CE readiness without opening decoder CE execution.",
        "source_evidence": {
            "denoise_rejoin": {
                "summary": str(SOURCE_DENOISE.relative_to(ROOT)),
                "passed": denoise.get("passed"),
                "generated_rows": dm.get("generated_rows"),
                "exact_match_rows": dm.get("exact_match_rows"),
                "boundary_next_token_match_rows": dm.get("boundary_next_token_match_rows"),
                "contentful_rows": dm.get("contentful_rows"),
                "short_or_junk_rows": dm.get("short_or_junk_rows"),
                "degenerate_repetition_rows": dm.get("degenerate_repetition_rows"),
                "generated_internal_token_rows": dm.get("generated_internal_token_rows"),
            },
            "bounded_decoder_failure_source": {
                "summary": str(SOURCE_DECODER_FAILURE.relative_to(ROOT)),
                "passed_safety": decoder_failure.get("passed"),
                "quality_gate_passed": fm.get("quality_gate_passed"),
                "target_prefix_match_rate": fm.get("target_prefix_match_rate"),
                "contentful_generation_rate": fm.get("contentful_generation_rate"),
                "degenerate_repetition_rate": fm.get("degenerate_repetition_rate"),
                "unterminated_generation_rate": fm.get("unterminated_generation_rate"),
                "failure_buckets": fm.get("failure_buckets"),
            },
            "denoise_seed": {
                "summary": str(SOURCE_DENOISE_SEED.relative_to(ROOT)),
                "passed": denoise_seed.get("passed"),
                "repair_rows": sm.get("repair_rows"),
                "eos_calibration_rows": sm.get("eos_calibration_rows"),
            },
            "bounded_decoder_package": {
                "summary": str(SOURCE_DECODER_PACKAGE.relative_to(ROOT)),
                "passed": decoder_package.get("passed"),
                "rows": pm.get("rows"),
                "split_counts": pm.get("split_counts"),
                "language_counts": pm.get("language_counts"),
                "loss_counts": pm.get("loss_counts"),
                "over_cap_rows": pm.get("over_cap_rows"),
                "unsafe_loss_rows": pm.get("unsafe_loss_rows"),
                "authority_rows": pm.get("authority_rows"),
                "first_token_dominance_rate": pm.get("first_token_dominance_rate"),
            },
            "trainer_loss_mask_readiness": {
                "summary": str(SOURCE_TRAINER_READY.relative_to(ROOT)),
                "passed": trainer_ready.get("passed"),
                "trainer_missing_required_flags": tm.get("trainer_missing_required_flags"),
                "trainer_missing_runtime_guard_strings": tm.get("trainer_missing_runtime_guard_strings"),
                "unsafe_loss_rows": tm.get("unsafe_loss_rows"),
                "over_cap_rows": tm.get("over_cap_rows"),
            },
            "prior_contract_preflight": {
                "summary": str(SOURCE_PREFLIGHT.relative_to(ROOT)),
                "passed": preflight.get("passed"),
                "rows": cm.get("rows"),
                "decoder_ce_rows": cm.get("decoder_ce_rows"),
                "manifest_sha256": cm.get("manifest_sha256"),
                "model_execution_attempted": cm.get("model_execution_attempted"),
                "eos_loss_weight": cm.get("eos_loss_weight"),
                "decoder_ce_weight": cm.get("decoder_ce_weight"),
            },
        },
        "readiness_claim": {
            "denoise_failure_loop_resolved": True,
            "bounded_decoder_candidate_package_available": True,
            "trainer_contract_available": True,
            "fresh_preexecution_required": True,
            "execution_authorized_now": False,
            "decoder_ce_training_authorized_now": False,
            "model_execution_authorized_now": False,
        },
        "next_probe_contract": {
            "stage": 9380,
            "mode": "bounded_decoder_ce_probe",
            "probe_scale": "target_100m",
            "implementation": "transformer",
            "manifest": "runs/local/artifacts/stage9249_semantic_bounded_decoder_target_repair_package/semantic_bounded_decoder_target_repair_manifest.jsonl",
            "max_train_rows": 32,
            "max_eval_rows": 16,
            "max_strict_rows": 16,
            "max_steps": 16,
            "batch_size": 2,
            "learning_rate": 1e-5,
            "max_encoder_tokens": 256,
            "max_decoder_tokens": 768,
            "decoder_ce_weight": 1.0,
            "structured_aux_weight": 0.0,
            "denoise_weight": 0.0,
            "eos_loss_weight": 4.0,
            "max_generation_rows": 16,
            "max_generation_tokens": 96,
            "required_telemetry": [
                "probe_contract_audit.json",
                "loss_by_step.jsonl",
                "eval_loss_by_checkpoint.jsonl",
                "row_token_loss.jsonl",
                "row_gradient_norms.jsonl",
                "boundary_next_token_logits.jsonl",
                "sample_generation_audit.json",
                "short_output_probe.json",
                "repetition_probe.json",
                "internal_leak_probe.json",
                "module_delta_norms.json",
                "cleanup_proof.json",
            ],
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def audit_bridge(bridge: dict[str, Any]) -> dict[str, Any]:
    e = bridge["source_evidence"]
    failures: list[str] = []
    denoise = e["denoise_rejoin"]
    if denoise.get("passed") is not True:
        failures.append("stage9378_not_passed")
    if not (denoise.get("generated_rows") == denoise.get("exact_match_rows") == denoise.get("boundary_next_token_match_rows") == denoise.get("contentful_rows") == 276):
        failures.append("stage9378_not_full_exact")
    if denoise.get("short_or_junk_rows") != 0 or denoise.get("degenerate_repetition_rows") != 0 or denoise.get("generated_internal_token_rows") != 0:
        failures.append("stage9378_generation_safety_not_clean")
    failure = e["bounded_decoder_failure_source"]
    if failure.get("passed_safety") is not True or failure.get("quality_gate_passed") is not False:
        failures.append("stage9266_not_safe_failed_decoder_quality")
    seed = e["denoise_seed"]
    if seed.get("passed") is not True or seed.get("repair_rows") != 6 or seed.get("eos_calibration_rows") != 15:
        failures.append("stage9267_seed_not_expected")
    package = e["bounded_decoder_package"]
    if package.get("passed") is not True or package.get("rows") != 64:
        failures.append("bounded_decoder_package_not_ready")
    if package.get("split_counts") != {"eval": 16, "strict_eval": 16, "train": 32}:
        failures.append("bounded_decoder_package_split_mismatch")
    if package.get("language_counts") != {"cpp": 16, "python": 16, "rust": 16, "web_js_ts_html": 16}:
        failures.append("bounded_decoder_language_balance_mismatch")
    if package.get("loss_counts") != {"decoder_ce": 64}:
        failures.append("bounded_decoder_loss_counts_mismatch")
    if package.get("over_cap_rows") != 0 or package.get("unsafe_loss_rows") != 0 or package.get("authority_rows") != 0:
        failures.append("bounded_decoder_package_safety_violation")
    trainer = e["trainer_loss_mask_readiness"]
    if trainer.get("passed") is not True or trainer.get("trainer_missing_required_flags") != 0 or trainer.get("trainer_missing_runtime_guard_strings") != 0:
        failures.append("trainer_readiness_not_clean")
    preflight = e["prior_contract_preflight"]
    if preflight.get("passed") is not True or preflight.get("model_execution_attempted") is not False:
        failures.append("prior_contract_preflight_not_clean")
    contract = bridge["next_probe_contract"]
    if contract.get("mode") != "bounded_decoder_ce_probe" or contract.get("decoder_ce_weight") != 1.0:
        failures.append("next_contract_not_decoder_ce")
    if contract.get("denoise_weight") != 0.0 or contract.get("structured_aux_weight") != 0.0:
        failures.append("next_contract_non_decoder_weights_enabled")
    if contract.get("max_steps") != 16 or contract.get("max_generation_rows") != 16:
        failures.append("next_contract_not_tiny")
    readiness = bridge["readiness_claim"]
    if readiness.get("execution_authorized_now") is not False or readiness.get("decoder_ce_training_authorized_now") is not False:
        failures.append("bridge_opened_execution_authority")
    if any(bool(v) for v in (bridge.get("authority") or {}).values()):
        failures.append("authority_open")
    return {
        "passed": not failures,
        "failures": failures,
        "denoise_rejoin_exact_rows": denoise.get("exact_match_rows"),
        "bounded_decoder_rows": package.get("rows"),
        "languages": package.get("language_counts"),
        "next_probe_contract_ready": not failures,
        "execution_authorized_now": False,
        "decoder_ce_training_authorized_now": False,
        "fresh_preexecution_required": True,
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    bridge = build_bridge()
    audit = audit_bridge(bridge)
    BRIDGE.write_text(json.dumps(bridge, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"bridge": str(BRIDGE.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "The denoise repair loop has resolved the bounded decoder failure residuals enough to design a fresh bounded decoder CE preexecution card. No execution or decoder CE authority is opened by this bridge.",
        "next_best_step": "Build Stage9380 bounded decoder CE preexecution using the Stage9249 semantic target-repaired package and Stage9378 denoise evidence; keep execution closed until that preexecution passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9379 Bounded Decoder CE Readiness Bridge",
                "",
                f"Passed: `{audit['passed']}`",
                f"Denoise rejoin exact rows: `{audit['denoise_rejoin_exact_rows']}`",
                f"Bounded decoder candidate rows: `{audit['bounded_decoder_rows']}`",
                f"Languages: `{audit['languages']}`",
                f"Execution authorized now: `{audit['execution_authorized_now']}`",
                f"Decoder CE authorized now: `{audit['decoder_ce_training_authorized_now']}`",
                "",
                "This bridge reconnects the passed Stage9378 denoise repair evidence to the Stage9249 bounded decoder CE package. It does not execute a model and does not open decoder CE authority.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["denoise_rejoin_exact_rows", "bounded_decoder_rows", "next_probe_contract_ready", "execution_authorized_now", "decoder_ce_training_authorized_now"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
