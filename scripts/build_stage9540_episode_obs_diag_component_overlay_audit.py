#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9540
NAME = "stage9540_episode_obs_diag_component_overlay_audit"
SOURCE = ROOT / "runs/local/artifacts/stage9539_episode_obs_diag_component_overlay_manifest/episode_obs_diag_component_overlay_manifest.jsonl"
SOURCE_CARD = ROOT / "runs/local/artifacts/stage9539_episode_obs_diag_component_overlay_manifest/episode_obs_diag_component_overlay_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_COMPONENT_OVERLAY_AUDIT_STAGE9540.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

ORDERED_REASONS = [
    "not_exact",
    "target_prefix_miss",
    "boundary_next_token_miss",
    "degenerate_repetition",
    "unterminated",
]
EXPECTED_LOSSES = {
    "episode_failure_type_ce": 58,
    "episode_repair_outcome_ce": 58,
    "episode_step_value_mse": 58,
}
FORBIDDEN_LOSSES = {
    "decoder_ce",
    "denoise_ce",
    "runtime_reward",
    "episode_boundary_match_ce",
    "episode_target_prefix_match_ce",
}


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
    rows = load_jsonl(SOURCE)
    card = load_json(SOURCE_CARD)
    failures: list[str] = []
    if card.get("passed") is not True:
        failures.append("stage9539_card_not_passed")
    if not rows:
        failures.append("missing_stage9539_rows")

    split_counts = Counter()
    loss_counts = Counter()
    failure_type_counts = Counter()
    mismatch_rows: list[dict] = []
    effective_leak_rows: list[str] = []
    missing_overlay_rows: list[str] = []
    non_telemetry_rows: list[str] = []
    forbidden_loss_rows: list[str] = []
    authority_rows: list[str] = []
    rejected_lineage_rows: list[str] = []
    opened_training_rows: list[str] = []

    for row in rows:
        row_id = str(row.get("row_id"))
        split_counts[row.get("split")] += 1
        effective = row.get("effective_verifier") if isinstance(row.get("effective_verifier"), dict) else {}
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        training_candidate = row.get("training_candidate") if isinstance(row.get("training_candidate"), dict) else {}
        composed = compose_failure_type(row)
        target = target_failure_type(row)
        failure_type_counts[composed] += 1
        if effective.get("effective_failure_type") != composed or composed != target:
            mismatch_rows.append(
                {
                    "row_id": row_id,
                    "effective_failure_type": effective.get("effective_failure_type"),
                    "composed_failure_type": composed,
                    "target_failure_type": target,
                    "residual_reasons": residual_reasons(row),
                }
            )
        if effective.get("effective_failure_type_source") != "deterministic_observation_component_overlay":
            missing_overlay_rows.append(row_id)
        if effective.get("learned_episode_failure_type_head_authority") != "telemetry_only":
            non_telemetry_rows.append(row_id)
        if any(key.startswith("effective_") for key in model_input):
            effective_leak_rows.append(row_id)
        for loss, enabled in loss_mask.items():
            if enabled:
                loss_counts[loss] += 1
        if any(loss_mask.get(loss) for loss in FORBIDDEN_LOSSES):
            forbidden_loss_rows.append(row_id)
        if any((row.get("authority") or {}).values()):
            authority_rows.append(row_id)
        lineage_blob = json.dumps(
            {
                "source_stage9525_row_id": row.get("source_stage9525_row_id"),
                "source_stage9521_row_id": row.get("source_stage9521_row_id"),
            },
            sort_keys=True,
        )
        if "stage9529" in lineage_blob or "stage9533" in lineage_blob:
            rejected_lineage_rows.append(row_id)
        if (
            training_candidate.get("model_execution_authorized_now")
            or not training_candidate.get("decoder_ce_closed")
            or not training_candidate.get("denoise_ce_closed")
            or not training_candidate.get("runtime_reward_closed")
        ):
            opened_training_rows.append(row_id)

    if len(rows) != 58:
        failures.append("unexpected_row_count")
    if split_counts != {"eval": 6, "strict_eval": 6, "train": 46}:
        failures.append("unexpected_split_counts")
    if dict(loss_counts) != EXPECTED_LOSSES:
        failures.append("unexpected_loss_counts")
    if mismatch_rows:
        failures.append("component_overlay_mismatch_rows")
    if effective_leak_rows:
        failures.append("effective_labels_in_model_input")
    if missing_overlay_rows:
        failures.append("missing_component_overlay_source")
    if non_telemetry_rows:
        failures.append("learned_failure_type_not_telemetry_only")
    if forbidden_loss_rows:
        failures.append("forbidden_loss_rows")
    if authority_rows:
        failures.append("authority_rows_present")
    if rejected_lineage_rows:
        failures.append("rejected_branch_lineage_rows")
    if opened_training_rows:
        failures.append("training_or_runtime_authority_opened")

    passed = not failures
    metrics = {
        "passed": passed,
        "failures": failures,
        "source_manifest": str(SOURCE.relative_to(ROOT)),
        "source_card": str(SOURCE_CARD.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "expected_loss_counts": EXPECTED_LOSSES,
        "failure_type_counts": dict(sorted(failure_type_counts.items())),
        "mismatch_rows": mismatch_rows,
        "effective_leak_rows": effective_leak_rows,
        "missing_overlay_rows": missing_overlay_rows,
        "non_telemetry_rows": non_telemetry_rows,
        "forbidden_loss_rows": forbidden_loss_rows,
        "authority_rows": authority_rows,
        "rejected_lineage_rows": rejected_lineage_rows,
        "opened_training_rows": opened_training_rows,
        "contract": {
            "effective_failure_type_source": "deterministic_observation_component_overlay",
            "learned_episode_failure_type_head": "telemetry_only",
            "model_input_has_no_effective_labels": not effective_leak_rows,
            "source_stage9525_only": not rejected_lineage_rows,
            "decoder_denoise_runtime_closed": not forbidden_loss_rows and not opened_training_rows,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "runtime_authorized_next": False,
        "promotion_ready": False,
    }
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": passed,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **metrics},
        "artifacts": {
            "source_manifest": str(SOURCE.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Audited Stage9539: the deterministic observation-component overlay is exact, external to model input, and keeps learned failure-type telemetry-only.",
        "next_best_step": "Use Stage9539 as the effective verifier-label base for the next closed-boundary rejoin or decoder-gating design; do not revive Stage9529 or Stage9533 branches.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9540 Episode Observation Diagnosis Component Overlay Audit",
                "",
                f"Passed: `{passed}`",
                f"Rows: `{len(rows)}`",
                f"Split counts: `{dict(split_counts)}`",
                f"Loss counts: `{dict(loss_counts)}`",
                f"Failure type counts: `{dict(failure_type_counts)}`",
                "",
                "The audit verifies that Stage9539 composes `effective_failure_type` from observation residual components and leaves learned failure-type prediction as telemetry only.",
                "",
                "No execution, decoder CE, denoise CE, runtime, harness, Gemma, controller merge, or promotion authority is opened.",
                "",
            ]
        )
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": passed, "rows": len(rows), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
