#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9665
NAME = "stage9665_observe_repair_control_promotion_contract"
S9664 = ROOT / "runs/summaries/stage9664_five_head_visible_episode_rejoin_tiny_probe.json"
S9561 = ROOT / "runs/summaries/stage9561_residual_denoise_loss_mask_reopen_design_audit.json"
S9366 = ROOT / "runs/summaries/stage9366_full_interference_rejoin_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "observe_repair_control_promotion_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OBSERVE_REPAIR_CONTROL_PROMOTION_CONTRACT_STAGE9665.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    s9664 = load_json(S9664)
    s9561 = load_json(S9561)
    s9366 = load_json(S9366)
    m9664 = s9664.get("metrics") if isinstance(s9664.get("metrics"), dict) else {}
    m9561 = s9561.get("metrics") if isinstance(s9561.get("metrics"), dict) else {}
    m9366 = s9366.get("metrics") if isinstance(s9366.get("metrics"), dict) else {}
    failures: list[str] = []
    if s9664.get("passed") is not True or m9664.get("safety_passed") is not True or m9664.get("quality_passed") is not True:
        failures.append("stage9664_not_passed")
    if float(m9664.get("decoder_delta_norm") or 0.0) != 0.0:
        failures.append("stage9664_decoder_delta_nonzero")
    for flag in ["runtime_executed", "gemma_executed", "harness_executed", "final_checkpoint_exported"]:
        if m9664.get(flag):
            failures.append(f"stage9664_forbidden_{flag}")
    expected_fields = {"episode_boundary_match", "episode_target_prefix_match", "episode_failure_type", "episode_repair_outcome", "episode_step_value"}
    if set((m9664.get("strict_field_exact") or {}).keys()) != expected_fields:
        failures.append("stage9664_missing_expected_fields")
    if min((m9664.get("strict_field_exact") or {}).values() or [0.0]) < 1.0:
        failures.append("stage9664_strict_not_exact")
    if s9561.get("passed") is not True or int(m9561.get("future_denoise_ce_candidate_rows") or 0) != 41:
        failures.append("stage9561_residual_denoise_candidates_not_ready")
    if m9561.get("denoise_ce_training_authorized_next") is not False or m9561.get("execution_authorized_for_next_stage") is not False:
        failures.append("stage9561_authority_unexpectedly_open")
    if int(m9366.get("generated_rows") or 0) != 209 or int(m9366.get("generated_internal_token_rows") or 0) != 0:
        failures.append("stage9366_reference_metrics_missing")
    if (m9366.get("error_counts") or {}).get("dependency_patch_ins_duplicate") != 41:
        failures.append("stage9366_route0_duplicate_residual_not_confirmed")
    contract = {
        "passed": not failures,
        "failures": failures,
        "promotion": {
            "promoted_contract": "five_head_visible_episode_observe_repair_control_v1",
            "source_stage": 9664,
            "fields": sorted(expected_fields),
            "eval_joint_proxy_exact": m9664.get("eval_joint_proxy_exact"),
            "strict_joint_proxy_exact": m9664.get("strict_joint_proxy_exact"),
            "strict_field_exact": m9664.get("strict_field_exact"),
            "decoder_delta_norm": m9664.get("decoder_delta_norm"),
            "authority_level": "training_contract_and_telemetry_gate_only",
            "deterministic_verifier_overlay_remains_authority": True,
        },
        "reconnect_target": {
            "next_objective_family": "residual_denoise_route0_duplicate_repair",
            "source_stage9366_residual": "dependency_patch_ins_duplicate",
            "stage9366_exact_rows": m9366.get("exact_match_rows"),
            "stage9366_generated_rows": m9366.get("generated_rows"),
            "stage9561_future_denoise_ce_candidate_rows": m9561.get("future_denoise_ce_candidate_rows"),
            "candidate_manifest": "runs/local/artifacts/stage9560_residual_denoise_loss_mask_reopen_design/residual_denoise_loss_mask_reopen_candidate_manifest.jsonl",
            "current_denoise_ce_rows": 0,
            "current_decoder_ce_rows": 0,
        },
        "required_next_stage_contract": {
            "build_stage9666": "sidecar_gated_residual_denoise_preexecution_design",
            "denoise_ce_currently_closed": True,
            "decoder_ce_must_remain_closed": True,
            "runtime_must_remain_closed": True,
            "gemma_harness_scoring_must_remain_closed": True,
            "final_checkpoint_export_must_remain_closed": True,
            "must_require_stage9664_control_contract": True,
            "must_require_stage9561_candidate_rows": 41,
            "must_emit_raw_vs_effective_gate_telemetry": True,
            "must_fail_if_observe_repair_control_artifacts_missing": True,
            "must_route_only_residual_repair_candidates": True,
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    CARD.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build Stage9666 sidecar-gated residual-denoise preexecution design using the 41 Stage9561 candidates and Stage9664 observe/repair control as telemetry gate; keep decoder/runtime/Gemma/harness closed."
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": contract["passed"], "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **contract}, "artifacts": {"card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))}, "decision": "Promoted Stage9664 as the five-head visible observe/repair control contract and selected the Stage9561 41-row residual denoise candidate set as the next reconnect target." if contract["passed"] else "Promotion/reconnect contract failed; do not build denoise preexecution.", "next_best_step": next_step, "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9665 Observe/Repair Control Promotion Contract", "", f"Passed: `{contract['passed']}`", "", "Promoted contract: `five_head_visible_episode_observe_repair_control_v1`", "", f"Stage9664 eval/strict joint: `{m9664.get('eval_joint_proxy_exact')}` / `{m9664.get('strict_joint_proxy_exact')}`", f"Stage9664 strict field exact: `{m9664.get('strict_field_exact')}`", f"Stage9664 decoder delta norm: `{m9664.get('decoder_delta_norm')}`", "", "Reconnect target: Stage9561 41-row residual denoise candidate set for the Stage9366 `dependency_patch_ins_duplicate` residual.", "", "Authority remains closed. The learned five-head controller is promoted as a training contract and telemetry gate only; deterministic verifier overlays remain authority for effective routing.", "", f"Next: {next_step}", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": contract["passed"], "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
