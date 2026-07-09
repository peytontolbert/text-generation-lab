#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9541
NAME = "stage9541_episode_obs_diag_closed_boundary_rejoin_gate_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9539_episode_obs_diag_component_overlay_manifest/episode_obs_diag_component_overlay_manifest.jsonl"
SOURCE_CARD = ROOT / "runs/local/artifacts/stage9539_episode_obs_diag_component_overlay_manifest/episode_obs_diag_component_overlay_manifest_card.json"
SOURCE_AUDIT = ROOT / "runs/summaries/stage9540_episode_obs_diag_component_overlay_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9541_episode_obs_diag_closed_boundary_rejoin_gate_manifest"
MANIFEST = OUT_DIR / "episode_obs_diag_closed_boundary_rejoin_gate_manifest.jsonl"
CARD = OUT_DIR / "episode_obs_diag_closed_boundary_rejoin_gate_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_CLOSED_BOUNDARY_REJOIN_GATE_MANIFEST_STAGE9541.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

ALL_KNOWN_LOSSES = {
    "action_sequence_ce",
    "allowed_import_policy_ce",
    "blocked_import_policy_ce",
    "build_mode_ce",
    "decoder_ce",
    "denoise_ce",
    "edit_localization_ce",
    "episode_boundary_match_ce",
    "episode_failure_type_ce",
    "episode_repair_outcome_ce",
    "episode_step_value_mse",
    "episode_target_prefix_match_ce",
    "file_plan_ce",
    "patch_operator_ce",
    "repair_surface_ce",
    "repo_dependency_policy_ce",
    "runtime_reward",
    "suffix_choice_ce",
    "surface_role_ce",
    "symbol_binding_ce",
    "verifier_repair_ce",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def update_registry(summary: dict) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")


def gate_block(row: dict) -> dict[str, object]:
    effective = row.get("effective_verifier") if isinstance(row.get("effective_verifier"), dict) else {}
    boundary = effective.get("effective_boundary_match") is True
    prefix = effective.get("effective_target_prefix_match") is True
    passed = effective.get("effective_step_passed") is True
    failure_none = effective.get("effective_failure_type") == "none"
    terminal_success = effective.get("effective_repair_outcome") == "successful_suffix_repair_step"
    terminal_candidate = boundary and prefix and passed and failure_none and terminal_success
    residual_candidate = not terminal_candidate
    return {
        "gate_source": "stage9539_effective_verifier_component_overlay",
        "gate_stage": 9541,
        "effective_failure_type_authority": effective.get("effective_failure_type_source"),
        "learned_failure_type_head_authority": "telemetry_only",
        "boundary_gate_passed": boundary,
        "target_prefix_gate_passed": prefix,
        "failure_type_gate_passed": failure_none,
        "repair_outcome_gate_passed": terminal_success,
        "step_value_gate_passed": passed,
        "would_allow_terminal_decode_rejoin_candidate": terminal_candidate,
        "would_route_to_residual_repair_candidate": residual_candidate,
        "actual_decoder_authority_opened": False,
        "actual_model_execution_authorized": False,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(SOURCE)
    card = load_json(SOURCE_CARD)
    audit = load_json(SOURCE_AUDIT)
    failures: list[str] = []
    if card.get("passed") is not True:
        failures.append("stage9539_card_not_passed")
    if audit.get("passed") is not True:
        failures.append("stage9540_audit_not_passed")
    if not rows:
        failures.append("missing_source_rows")

    output_rows: list[dict] = []
    split_counts = Counter()
    gate_counts = Counter()
    enabled_loss_counts = Counter()
    authority_rows: list[str] = []
    effective_leak_rows: list[str] = []
    missing_gate_rows: list[str] = []
    actual_decoder_authority_rows: list[str] = []

    for idx, row in enumerate(rows):
        out = copy.deepcopy(row)
        out["row_id"] = f"stage9541_obs_diag_rejoin_gate_{idx:04d}"
        out["source_stage9539_row_id"] = row.get("row_id")
        out["objective_family"] = "episode_observation_diagnosis_closed_boundary_rejoin_gate"
        out["route"] = "KEEP_EPISODE_OBS_DIAG_REJOIN_GATE_METADATA_ONLY"
        out["authority"] = dict(AUTHORITY_CLOSED)
        out["rejoin_gate"] = gate_block(out)
        training_candidate = dict(out.get("training_candidate") or {})
        training_candidate.update(
            {
                "stage9541_closed_boundary_rejoin_gate": True,
                "losses_closed_for_rejoin_gate": True,
                "effective_verifier_authority_remains_external": True,
                "learned_failure_type_head_authority": "telemetry_only",
                "model_execution_authorized_now": False,
                "decoder_ce_closed": True,
                "denoise_ce_closed": True,
                "runtime_reward_closed": True,
            }
        )
        out["training_candidate"] = training_candidate
        loss_mask = dict(out.get("loss_mask") or {})
        for loss in ALL_KNOWN_LOSSES:
            loss_mask[loss] = False
        out["loss_mask"] = loss_mask

        for loss, enabled in loss_mask.items():
            if enabled:
                enabled_loss_counts[loss] += 1
        if any((out.get("authority") or {}).values()):
            authority_rows.append(out["row_id"])
        model_input = out.get("model_input") if isinstance(out.get("model_input"), dict) else {}
        if any(key.startswith("effective_") or key.startswith("rejoin_") for key in model_input):
            effective_leak_rows.append(out["row_id"])
        gate = out.get("rejoin_gate") if isinstance(out.get("rejoin_gate"), dict) else {}
        if gate.get("gate_source") != "stage9539_effective_verifier_component_overlay":
            missing_gate_rows.append(out["row_id"])
        if gate.get("actual_decoder_authority_opened") or gate.get("actual_model_execution_authorized"):
            actual_decoder_authority_rows.append(out["row_id"])
        split_counts[out.get("split")] += 1
        gate_counts[f"terminal_candidate::{gate.get('would_allow_terminal_decode_rejoin_candidate')}"] += 1
        gate_counts[f"residual_candidate::{gate.get('would_route_to_residual_repair_candidate')}"] += 1
        output_rows.append(out)

    if len(output_rows) != 58:
        failures.append("unexpected_row_count")
    if split_counts != {"eval": 6, "strict_eval": 6, "train": 46}:
        failures.append("unexpected_split_counts")
    if enabled_loss_counts:
        failures.append("enabled_losses_present")
    if authority_rows:
        failures.append("authority_rows_present")
    if effective_leak_rows:
        failures.append("gate_or_effective_labels_in_model_input")
    if missing_gate_rows:
        failures.append("missing_rejoin_gate_rows")
    if actual_decoder_authority_rows:
        failures.append("actual_decoder_or_execution_authority_rows")
    if gate_counts.get("terminal_candidate::True") != 29 or gate_counts.get("residual_candidate::True") != 29:
        failures.append("unexpected_terminal_residual_gate_counts")

    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows))
    result = {
        "passed": not failures,
        "failures": failures,
        "source_manifest": str(SOURCE.relative_to(ROOT)),
        "source_card": str(SOURCE_CARD.relative_to(ROOT)),
        "source_audit": str(SOURCE_AUDIT.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(output_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "gate_counts": dict(sorted(gate_counts.items())),
        "enabled_loss_counts": dict(sorted(enabled_loss_counts.items())),
        "authority_rows": authority_rows,
        "effective_leak_rows": effective_leak_rows,
        "missing_gate_rows": missing_gate_rows,
        "actual_decoder_authority_rows": actual_decoder_authority_rows,
        "contract": {
            "metadata_only_rejoin_gate": True,
            "all_losses_closed": not enabled_loss_counts,
            "effective_verifier_outside_model_input": not effective_leak_rows,
            "terminal_candidate_is_not_authorization": True,
            "learned_failure_type_head": "telemetry_only",
            "source_stage9539_only": True,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "runtime_authorized_next": False,
        "promotion_ready": False,
    }
    CARD.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": result["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **result},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built a metadata-only closed-boundary rejoin gate from Stage9539 effective verifier labels. Terminal-pass rows are marked as candidates only; no decoder or execution authority is opened.",
        "next_best_step": "Audit Stage9541 for loss closure, model-input non-leakage, terminal/residual gate counts, and closed authority before any preflight or execution design.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9541 Episode Observation Diagnosis Closed-Boundary Rejoin Gate Manifest",
        "",
        f"Passed: `{result['passed']}`",
        f"Rows: `{len(output_rows)}`",
        f"Gate counts: `{dict(gate_counts)}`",
        "",
        "This is a metadata-only rejoin/gating manifest. It closes every known loss key and keeps the deterministic effective verifier block outside `model_input`.",
        "",
        "Terminal-pass rows are candidates for a later design review, not authorization to decode or execute.",
        "",
    ]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": result["passed"], "rows": len(output_rows), "gate_counts": dict(gate_counts), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
