#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.native_probe_interpretability_artifact_contract import audit_artifact_dir
except ModuleNotFoundError:  # pragma: no cover
    from native_probe_interpretability_artifact_contract import audit_artifact_dir

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8902
NAME = "stage8902_diagnostic_promotion_gate"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DIAGNOSTIC_PROMOTION_GATE_STAGE8902.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCE_SUMMARIES = [
    ROOT / "runs/summaries/stage8862_native_probe_interpretability_artifact_contract.json",
    ROOT / "runs/summaries/stage8893_no_execution_telemetry_gate_matrix.json",
    ROOT / "runs/summaries/stage8901_verified_transition_record_no_mining_compiler_adapter.json",
]

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

REQUIRED_PROMOTION_ARTIFACTS = {
    "structured_aux_probe": [
        "loss_by_step.jsonl",
        "eval_loss_by_checkpoint.jsonl",
        "row_field_logits.jsonl",
        "row_field_losses.jsonl",
        "row_gradient_norms.jsonl",
        "activation_summary.jsonl",
        "feature_ablation_attribution.jsonl",
        "activation_patch_recovery.jsonl",
        "row_dynamics_history.jsonl",
        "module_delta_norms.json",
        "field_exact_by_cell.json",
        "field_label_vocabs.json",
        "structured_confusion_matrix.json",
        "failure_bucket_card.json",
        "cleanup_proof.json",
    ],
    "bounded_decoder_ce_probe": [
        "loss_by_step.jsonl",
        "eval_loss_by_checkpoint.jsonl",
        "row_token_loss.jsonl",
        "row_gradient_norms.jsonl",
        "activation_summary.jsonl",
        "row_dynamics_history.jsonl",
        "module_delta_norms.json",
        "internal_token_logit_summary.json",
        "eos_length_audit.json",
        "short_output_probe.json",
        "repetition_probe.json",
        "internal_leak_probe.json",
        "sample_generation_audit.json",
        "failure_bucket_card.json",
        "cleanup_proof.json",
    ],
}

PROMOTION_RULES = [
    "artifact_contract_passed",
    "all_required_artifacts_present",
    "all_jsonl_artifacts_nonempty",
    "row_field_logits_include_confidence_entropy_topk_for_structured",
    "row_token_loss_contains_per_position_loss_for_bounded_decoder",
    "row_gradient_norms_present",
    "activation_summary_present",
    "failure_bucket_card_present",
    "cleanup_proof_present",
    "structured_probe_decoder_delta_norm_zero",
    "authority_counts_zero",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def promotion_gate_for_artifact_dir(path: Path, *, mode: str) -> dict[str, Any]:
    audit = audit_artifact_dir(path, mode=mode)
    expected = set(REQUIRED_PROMOTION_ARTIFACTS[mode])
    observed = set(audit.get("artifacts", {}))
    missing = sorted(expected - observed)
    errors = list(audit.get("errors") or [])
    if missing:
        errors.append(f"promotion missing required artifacts: {missing}")
    if mode == "structured_aux_probe" and float(audit.get("decoder_delta_norm") or 0.0) > 1e-8:
        errors.append("promotion blocked: structured probe moved decoder parameters")
    return {
        "passed": audit.get("passed") is True and not missing and not errors,
        "mode": mode,
        "artifact_dir": str(path),
        "artifact_contract_passed": audit.get("passed") is True,
        "missing_required_artifacts": missing,
        "errors": errors,
        "nonempty_jsonl_artifacts": audit.get("nonempty_jsonl_artifacts", 0),
        "decoder_delta_norm": audit.get("decoder_delta_norm"),
        "promotion_ready": False,
    }


def build_gate_card(registry: dict[str, Any], source_cards: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    for source in source_cards:
        if source.get("passed") is not True:
            failures.append(f"source_failed:{source.get('stage_name')}")
        if any((source.get("authority") or {}).values()):
            failures.append(f"source_authority_open:{source.get('stage_name')}")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8901, STAGE, 8903, 8904}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            "promotion_rules": len(PROMOTION_RULES),
            "structured_required_artifacts": len(REQUIRED_PROMOTION_ARTIFACTS["structured_aux_probe"]),
            "bounded_required_artifacts": len(REQUIRED_PROMOTION_ARTIFACTS["bounded_decoder_ce_probe"]),
            "source_summaries_checked": len(SOURCE_SUMMARIES),
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "promotion_ready": False,
        },
        "required_promotion_artifacts": REQUIRED_PROMOTION_ARTIFACTS,
        "promotion_rules": PROMOTION_RULES,
        "decision": "Diagnostic promotion gate passed as no-execution policy. Future probe/run promotion is invalid unless required diagnostic artifacts pass mode-specific audit." if not failures else "Diagnostic promotion gate failed.",
        "next_best_step": "Wire this gate into any future live probe ticket as a post-run blocker; do not promote or interpret model metrics if diagnostics are incomplete.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main() -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    source_cards = [load_json(path) for path in SOURCE_SUMMARIES]
    card = build_gate_card(registry, source_cards)
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8902 Diagnostic Promotion Gate",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This no-execution gate says future probe/run promotion is invalid unless diagnostics are complete and mode-specific artifact audits pass.",
        "",
        "Structured probes must include row-field logits/losses, confidence/entropy/top-k, row gradient norms, activation summaries, feature ablation, activation patch recovery, row dynamics, field exact/confusion artifacts, failure buckets, cleanup proof, and zero decoder delta.",
        "",
        "Bounded decoder probes must include per-token loss positions, decoder/internal-token/EOS/short-output/repetition/leak probes, row gradient norms, activation summaries, row dynamics, failure buckets, cleanup proof, and module deltas.",
        "",
        "This opens no model execution, training, decoder CE, denoise CE, runtime, mining, source/body emission, Gemma, harness, scoring, controller merge, checkpoint export, or promotion.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8902 Diagnostic Promotion Gate"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8902 makes diagnostics a promotion blocker: future probe/run outputs are invalid unless mode-specific diagnostic artifacts exist, are non-empty, and pass `native_probe_interpretability_artifact_contract`.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
