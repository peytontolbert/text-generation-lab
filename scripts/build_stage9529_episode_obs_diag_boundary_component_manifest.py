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
STAGE = 9529
NAME = "stage9529_episode_obs_diag_boundary_component_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9525_episode_obs_diag_residual_gate_manifest/episode_obs_diag_residual_gate_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9528_episode_obs_diag_residual_gate_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9529_episode_obs_diag_boundary_component_manifest"
MANIFEST = OUT_DIR / "episode_obs_diag_boundary_component_manifest.jsonl"
CARD = OUT_DIR / "episode_obs_diag_boundary_component_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_BOUNDARY_COMPONENT_MANIFEST_STAGE9529.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def boundary_features(model_input: dict) -> dict[str, object]:
    not_exact = bool(model_input.get("obs_has_not_exact_reason"))
    prefix = bool(model_input.get("obs_has_target_prefix_miss_reason"))
    boundary = bool(model_input.get("obs_has_boundary_next_token_miss_reason")) or model_input.get("obs_boundary_relation") == "boundary_miss"
    components = int(not_exact) + int(prefix) + int(boundary)
    if boundary and prefix:
        family = "prefix_and_boundary_components"
    elif prefix:
        family = "prefix_only_components"
    elif boundary:
        family = "boundary_only_components"
    else:
        family = "no_failure_components"
    return {
        "obs_diag_boundary_component_patch_phase": True,
        "obs_component_not_exact": not_exact,
        "obs_component_target_prefix_miss": prefix,
        "obs_component_boundary_next_token_miss": boundary,
        "obs_boundary_component_required": boundary,
        "obs_failure_component_count": components,
        "obs_failure_component_family": family,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(SOURCE)
    source_summary = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    if not rows:
        failures.append("missing_source_rows")
    if source_summary.get("metrics", {}).get("safety_passed") is not True:
        failures.append("stage9528_not_safe")
    wrong = source_summary.get("metrics", {}).get("wrong_rows", [])
    if len(wrong) != 1:
        failures.append("unexpected_stage9528_wrong_row_count")

    output_rows: list[dict] = []
    split_counts = Counter()
    language_counts = Counter()
    component_family_counts = Counter()
    loss_counts = Counter()
    forbidden_loss_rows: list[str] = []
    authority_rows: list[str] = []
    effective_leak_rows: list[str] = []
    missing_component_rows: list[str] = []
    for idx, row in enumerate(rows):
        out = copy.deepcopy(row)
        out["row_id"] = f"stage9529_obs_diag_boundary_{idx:04d}"
        out["source_stage9525_row_id"] = row.get("row_id")
        out["objective_family"] = "episode_observation_diagnosis_boundary_component"
        out["route"] = "KEEP_EPISODE_OBS_DIAG_BOUNDARY_COMPONENT"
        out["authority"] = dict(AUTHORITY_CLOSED)
        model_input = dict(out.get("model_input") or {})
        model_input.update(boundary_features(model_input))
        out["model_input"] = model_input
        out["training_candidate"] = {
            **(out.get("training_candidate") or {}),
            "boundary_component_patch_phase": True,
            "failure_type_only_focus": True,
            "model_execution_authorized_now": False,
            "decoder_ce_closed": True,
            "denoise_ce_closed": True,
            "runtime_reward_closed": True,
        }
        loss_mask = dict(out.get("loss_mask") or {})
        loss_mask["episode_failure_type_ce"] = True
        loss_mask["episode_repair_outcome_ce"] = False
        loss_mask["episode_step_value_mse"] = False
        for loss in ["decoder_ce", "denoise_ce", "runtime_reward", "episode_boundary_match_ce", "episode_target_prefix_match_ce"]:
            loss_mask[loss] = False
        out["loss_mask"] = loss_mask

        for loss, enabled in loss_mask.items():
            if enabled:
                loss_counts[loss] += 1
        if any(loss_mask.get(loss) for loss in ["decoder_ce", "denoise_ce", "runtime_reward", "episode_boundary_match_ce", "episode_target_prefix_match_ce"]):
            forbidden_loss_rows.append(out["row_id"])
        if any((out.get("authority") or {}).values()):
            authority_rows.append(out["row_id"])
        if any(key.startswith("effective_") for key in model_input):
            effective_leak_rows.append(out["row_id"])
        if model_input.get("obs_failure_component_family") is None:
            missing_component_rows.append(out["row_id"])
        split_counts[out.get("split")] += 1
        language_counts[out.get("language_family")] += 1
        component_family_counts[model_input.get("obs_failure_component_family")] += 1
        output_rows.append(out)

    expected_loss_counts = {"episode_failure_type_ce": len(output_rows)}
    if dict(loss_counts) != expected_loss_counts:
        failures.append("unexpected_loss_counts")
    if split_counts != {"eval": 6, "strict_eval": 6, "train": 46}:
        failures.append("unexpected_split_counts")
    if forbidden_loss_rows:
        failures.append("forbidden_loss_rows")
    if authority_rows:
        failures.append("authority_rows_present")
    if effective_leak_rows:
        failures.append("effective_verifier_leaked_into_model_input")
    if missing_component_rows:
        failures.append("missing_boundary_component_rows")
    if component_family_counts.get("prefix_and_boundary_components", 0) <= 0:
        failures.append("missing_prefix_and_boundary_components")

    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows))
    card = {
        "passed": not failures,
        "failures": failures,
        "source_manifest": str(SOURCE.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(output_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "component_family_counts": dict(sorted(component_family_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "expected_loss_counts": expected_loss_counts,
        "forbidden_loss_rows": forbidden_loss_rows,
        "authority_rows": authority_rows,
        "effective_leak_rows": effective_leak_rows,
        "missing_component_rows": missing_component_rows,
        "contract": {
            "failure_type_only_focus": True,
            "effective_labels_outside_model_input": not effective_leak_rows,
            "boundary_component_features_derived_from_observation": True,
            "decoder_denoise_runtime_closed": not forbidden_loss_rows,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": card["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **card},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built boundary-component diagnosis rows focused only on episode_failure_type_ce.",
        "next_best_step": "Audit Stage9529 for leakage, failure-type-only loss focus, boundary-component coverage, and preflight readiness.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9529 Episode Observation Diagnosis Boundary-Component Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{len(output_rows)}`",
        f"Split counts: `{dict(split_counts)}`",
        f"Component family counts: `{dict(component_family_counts)}`",
        f"Loss counts: `{dict(loss_counts)}`",
        "",
        "This patch targets the remaining Stage9528 eval failure-type miss by exposing observation-derived boundary-component salience while training only the failure-type head.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": card["passed"], "rows": len(output_rows), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
