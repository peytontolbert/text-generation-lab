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
STAGE = 9539
NAME = "stage9539_episode_obs_diag_component_overlay_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9525_episode_obs_diag_residual_gate_manifest/episode_obs_diag_residual_gate_manifest.jsonl"
SOURCE_CARD = ROOT / "runs/local/artifacts/stage9525_episode_obs_diag_residual_gate_manifest/episode_obs_diag_residual_gate_manifest_card.json"
CONTRACT = ROOT / "runs/local/artifacts/stage9538_episode_obs_diag_component_overlay_contract/episode_obs_diag_component_overlay_contract.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9539_episode_obs_diag_component_overlay_manifest"
MANIFEST = OUT_DIR / "episode_obs_diag_component_overlay_manifest.jsonl"
CARD = OUT_DIR / "episode_obs_diag_component_overlay_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_COMPONENT_OVERLAY_MANIFEST_STAGE9539.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

TRAINABLE_LOSSES = {
    "episode_failure_type_ce",
    "episode_repair_outcome_ce",
    "episode_step_value_mse",
}
FORBIDDEN_LOSSES = {
    "decoder_ce",
    "denoise_ce",
    "runtime_reward",
    "episode_boundary_match_ce",
    "episode_target_prefix_match_ce",
}
ORDERED_REASONS = [
    "not_exact",
    "target_prefix_miss",
    "boundary_next_token_miss",
    "degenerate_repetition",
    "unterminated",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def residual_reasons(row: dict) -> list[str]:
    transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    observation = transition.get("observation_t") if isinstance(transition.get("observation_t"), dict) else {}
    reasons = observation.get("residual_reasons")
    if not isinstance(reasons, list):
        return []
    return [str(reason) for reason in reasons]


def compose_failure_type(row: dict) -> str:
    reasons = set(residual_reasons(row))
    ordered = [reason for reason in ORDERED_REASONS if reason in reasons]
    return "none" if not ordered else "+".join(ordered)


def target_failure_type(row: dict) -> str:
    transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    verifier = transition.get("reward_or_verifier") if isinstance(transition.get("reward_or_verifier"), dict) else {}
    return str(verifier.get("failure_type") or "none")


def update_registry(summary: dict) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [
        row
        for row in registry.get("rows", [])
        if row.get("stage") != STAGE and row.get("stage_name") != NAME
    ]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(SOURCE)
    source_card = load_json(SOURCE_CARD)
    contract = load_json(CONTRACT)
    failures: list[str] = []
    if not rows:
        failures.append("missing_source_rows")
    if source_card.get("passed") is not True:
        failures.append("stage9525_card_not_passed")
    if contract.get("passed") is not True:
        failures.append("stage9538_contract_not_passed")

    output_rows: list[dict] = []
    split_counts = Counter()
    loss_counts = Counter()
    target_counts = Counter()
    composed_counts = Counter()
    source_stage_counts = Counter()
    mismatch_rows: list[dict] = []
    effective_leak_rows: list[str] = []
    forbidden_loss_rows: list[str] = []
    authority_rows: list[str] = []
    missing_overlay_rows: list[str] = []
    rejected_lineage_rows: list[str] = []

    for idx, row in enumerate(rows):
        out = copy.deepcopy(row)
        out["row_id"] = f"stage9539_obs_diag_component_overlay_{idx:04d}"
        out["source_stage9525_row_id"] = row.get("row_id")
        out["objective_family"] = "episode_observation_diagnosis_component_overlay"
        out["route"] = "KEEP_EPISODE_OBS_DIAG_COMPONENT_OVERLAY"
        out["authority"] = dict(AUTHORITY_CLOSED)

        composed = compose_failure_type(out)
        target = target_failure_type(out)
        previous_effective = out.get("effective_verifier") if isinstance(out.get("effective_verifier"), dict) else {}
        effective = dict(previous_effective)
        effective["effective_failure_type_previous"] = previous_effective.get("effective_failure_type")
        effective["effective_failure_type"] = composed
        effective["effective_failure_type_composed_from_observation"] = composed
        effective["effective_failure_type_source"] = "deterministic_observation_component_overlay"
        effective["effective_failure_type_component_order"] = list(ORDERED_REASONS)
        effective["effective_failure_type_component_source"] = "episode_transition.observation_t.residual_reasons"
        effective["learned_episode_failure_type_head_authority"] = "telemetry_only"
        effective["stage9538_component_overlay_contract_active"] = True
        out["effective_verifier"] = effective

        training_candidate = dict(out.get("training_candidate") or {})
        training_candidate.update(
            {
                "stage9538_component_overlay_contract_active": True,
                "component_overlay_source_stage": 9538,
                "effective_failure_type_authority": "deterministic_observation_component_overlay",
                "learned_episode_failure_type_head_authority": "telemetry_only",
                "stage9529_boundary_component_branch_rejected": True,
                "stage9533_python_boundary_upsample_branch_rejected": True,
                "model_execution_authorized_now": False,
                "decoder_ce_closed": True,
                "denoise_ce_closed": True,
                "runtime_reward_closed": True,
            }
        )
        out["training_candidate"] = training_candidate

        loss_mask = dict(out.get("loss_mask") or {})
        for loss in TRAINABLE_LOSSES:
            loss_mask[loss] = True
        for loss in FORBIDDEN_LOSSES:
            loss_mask[loss] = False
        out["loss_mask"] = loss_mask

        for loss, enabled in loss_mask.items():
            if enabled:
                loss_counts[loss] += 1
        if composed != target:
            mismatch_rows.append(
                {
                    "row_id": out["row_id"],
                    "source_stage9525_row_id": out["source_stage9525_row_id"],
                    "target_failure_type": target,
                    "composed_failure_type": composed,
                    "residual_reasons": residual_reasons(out),
                }
            )
        model_input = out.get("model_input") if isinstance(out.get("model_input"), dict) else {}
        if any(key.startswith("effective_") for key in model_input):
            effective_leak_rows.append(out["row_id"])
        if any(loss_mask.get(loss) for loss in FORBIDDEN_LOSSES):
            forbidden_loss_rows.append(out["row_id"])
        if any((out.get("authority") or {}).values()):
            authority_rows.append(out["row_id"])
        if effective.get("effective_failure_type_source") != "deterministic_observation_component_overlay":
            missing_overlay_rows.append(out["row_id"])
        source_id = str(out.get("source_stage9525_row_id") or "")
        source_stage_counts[source_id.split("_")[0] if source_id else "missing"] += 1
        lineage_blob = json.dumps(
            {
                "source_stage9525_row_id": out.get("source_stage9525_row_id"),
                "source_stage9521_row_id": out.get("source_stage9521_row_id"),
            },
            sort_keys=True,
        )
        if "stage9529" in lineage_blob or "stage9533" in lineage_blob:
            rejected_lineage_rows.append(out["row_id"])
        split_counts[out.get("split")] += 1
        target_counts[target] += 1
        composed_counts[composed] += 1
        output_rows.append(out)

    expected_loss_counts = {loss: len(output_rows) for loss in sorted(TRAINABLE_LOSSES)}
    if split_counts != {"eval": 6, "strict_eval": 6, "train": 46}:
        failures.append("unexpected_split_counts")
    if dict(loss_counts) != expected_loss_counts:
        failures.append("unexpected_loss_counts")
    if mismatch_rows:
        failures.append("component_overlay_mismatch_rows")
    if effective_leak_rows:
        failures.append("effective_verifier_leaked_into_model_input")
    if forbidden_loss_rows:
        failures.append("forbidden_loss_rows")
    if authority_rows:
        failures.append("authority_rows_present")
    if missing_overlay_rows:
        failures.append("missing_component_overlay_rows")
    if rejected_lineage_rows:
        failures.append("rejected_branch_lineage_rows")

    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows))
    card = {
        "passed": not failures,
        "failures": failures,
        "source_manifest": str(SOURCE.relative_to(ROOT)),
        "stage9538_contract": str(CONTRACT.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(output_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "expected_loss_counts": expected_loss_counts,
        "target_failure_type_counts": dict(sorted(target_counts.items())),
        "composed_failure_type_counts": dict(sorted(composed_counts.items())),
        "source_stage_prefix_counts": dict(sorted(source_stage_counts.items())),
        "mismatch_rows": mismatch_rows,
        "effective_leak_rows": effective_leak_rows,
        "forbidden_loss_rows": forbidden_loss_rows,
        "authority_rows": authority_rows,
        "missing_overlay_rows": missing_overlay_rows,
        "rejected_lineage_rows": rejected_lineage_rows,
        "contract": {
            "effective_failure_type_source": "deterministic_observation_component_overlay",
            "component_source": "episode_transition.observation_t.residual_reasons",
            "component_order": list(ORDERED_REASONS),
            "learned_episode_failure_type_head": "telemetry_only",
            "effective_labels_outside_model_input": not effective_leak_rows,
            "source_stage9525_only": not rejected_lineage_rows,
            "decoder_denoise_runtime_closed": not forbidden_loss_rows,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "runtime_authorized_next": False,
        "promotion_ready": False,
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": card["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **card},
        "artifacts": {
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "card": str(CARD.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Materialized the Stage9538 deterministic observation-component failure-type overlay on the Stage9525 residual-gate manifest while keeping learned failure-type telemetry-only.",
        "next_best_step": "Audit Stage9539 for component-overlay exactness, model-input non-leakage, rejected-branch exclusion, and closed execution/decode authority before any rejoin or decoder-gating probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9539 Episode Observation Diagnosis Component Overlay Manifest",
                "",
                f"Passed: `{card['passed']}`",
                f"Rows: `{len(output_rows)}`",
                f"Split counts: `{dict(split_counts)}`",
                f"Failure type counts: `{dict(target_counts)}`",
                "",
                "This stage applies the Stage9538 contract to the Stage9525 residual-gate manifest.",
                "`effective_verifier.effective_failure_type` is now composed deterministically from `episode_transition.observation_t.residual_reasons`.",
                "The learned `episode_failure_type` head remains telemetry-only and does not authorize verifier outcomes.",
                "",
                "Execution, decoder CE, denoise CE, runtime reward, harness, Gemma, controller merge, and promotion remain closed.",
                "",
            ]
        )
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": card["passed"], "rows": len(output_rows), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
