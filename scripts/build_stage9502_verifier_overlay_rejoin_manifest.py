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
STAGE = 9502
NAME = "stage9502_verifier_overlay_rejoin_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9490_phase_aware_episode_verifier_manifest/phase_aware_episode_verifier_manifest.jsonl"
AUTHORITY_MAP = ROOT / "runs/local/artifacts/stage9501_verifier_label_authority_map/verifier_label_authority_map.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9502_verifier_overlay_rejoin_manifest"
MANIFEST = OUT_DIR / "verifier_overlay_rejoin_manifest.jsonl"
CARD = OUT_DIR / "verifier_overlay_rejoin_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "VERIFIER_OVERLAY_REJOIN_MANIFEST_STAGE9502.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

VERIFIER_LOSSES = {
    "episode_boundary_match_ce",
    "episode_failure_type_ce",
    "episode_repair_outcome_ce",
    "episode_step_value_mse",
    "episode_target_prefix_match_ce",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verifier_block(row: dict) -> dict[str, object]:
    transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    observation = transition.get("observation_t") if isinstance(transition.get("observation_t"), dict) else {}
    reward = transition.get("reward_or_verifier") if isinstance(transition.get("reward_or_verifier"), dict) else {}
    next_state = transition.get("state_t_plus_1") if isinstance(transition.get("state_t_plus_1"), dict) else {}
    return {
        "effective_boundary_match": observation.get("boundary_next_token_match"),
        "effective_target_prefix_match": observation.get("target_prefix_match"),
        "effective_failure_type": reward.get("failure_type"),
        "effective_repair_outcome": next_state.get("repair_outcome"),
        "effective_step_value": reward.get("reward"),
        "effective_step_passed": reward.get("step_passed"),
        "authority_source": "deterministic_verifier_observation_and_transition_record",
        "learned_verifier_heads_authority": "telemetry_only",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source_rows = load_jsonl(SOURCE)
    authority_map = load_json(AUTHORITY_MAP)
    failures: list[str] = []
    if not source_rows:
        failures.append("missing_source_rows")
    if authority_map.get("passed") is not True:
        failures.append("stage9501_authority_map_not_passed")

    output_rows: list[dict] = []
    split_counts = Counter()
    verifier_label_counts = Counter()
    enabled_loss_counts = Counter()
    missing_effective_rows: list[str] = []
    for idx, row in enumerate(source_rows):
        out = copy.deepcopy(row)
        out["row_id"] = f"stage9502_verifier_overlay_rejoin_{idx:04d}"
        out["source_stage9490_row_id"] = row.get("row_id")
        out["objective_family"] = "verifier_overlay_rejoin"
        out["route"] = "KEEP_VERIFIER_OVERLAY_REJOIN_METADATA_ONLY"
        out["effective_verifier"] = verifier_block(row)
        out["authority"] = dict(AUTHORITY_CLOSED)
        out["training_candidate"] = {
            **(out.get("training_candidate") or {}),
            "verifier_learning_closed": True,
            "learned_verifier_heads_authority": "telemetry_only",
            "model_execution_authorized_now": False,
            "decoder_ce_closed": True,
            "denoise_ce_closed": True,
            "runtime_reward_closed": True,
        }
        loss_mask = dict(out.get("loss_mask") or {})
        for key in VERIFIER_LOSSES:
            loss_mask[key] = False
        out["loss_mask"] = loss_mask
        for key, enabled in loss_mask.items():
            if enabled:
                enabled_loss_counts[key] += 1
        block = out["effective_verifier"]
        if any(block.get(key) is None for key in [
            "effective_boundary_match",
            "effective_target_prefix_match",
            "effective_failure_type",
            "effective_repair_outcome",
            "effective_step_value",
            "effective_step_passed",
        ]):
            missing_effective_rows.append(out["row_id"])
        split_counts[out.get("split")] += 1
        verifier_label_counts[f"boundary::{block.get('effective_boundary_match')}"] += 1
        verifier_label_counts[f"target_prefix::{block.get('effective_target_prefix_match')}"] += 1
        verifier_label_counts[f"failure::{block.get('effective_failure_type')}"] += 1
        verifier_label_counts[f"outcome::{block.get('effective_repair_outcome')}"] += 1
        verifier_label_counts[f"value::{block.get('effective_step_value')}"] += 1
        output_rows.append(out)

    if missing_effective_rows:
        failures.append("missing_effective_verifier_fields")
    if enabled_loss_counts:
        failures.append("unexpected_enabled_losses")
    if any(any((row.get("authority") or {}).values()) for row in output_rows):
        failures.append("authority_rows_present")

    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows))
    card = {
        "passed": not failures,
        "failures": failures,
        "source_manifest": str(SOURCE.relative_to(ROOT)),
        "authority_map": str(AUTHORITY_MAP.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(output_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "enabled_loss_counts": dict(sorted(enabled_loss_counts.items())),
        "verifier_label_counts": dict(sorted(verifier_label_counts.items())),
        "missing_effective_rows": missing_effective_rows,
        "contract": {
            "all_verifier_losses_closed": True,
            "effective_verifier_fields_outside_model_input": True,
            "learned_verifier_heads_authority": "telemetry_only",
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
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
        "decision": "Verifier overlay rejoin rows carry deterministic effective verifier metadata with verifier training losses closed. These rows are for control/evaluation rejoin, not learned verifier authority.",
        "next_best_step": "Audit Stage9502 manifest for loss closure, authority closure, effective verifier completeness, and absence of effective labels inside model_input.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    DOC.write_text("\n".join([
        "# Stage9502 Verifier Overlay Rejoin Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{len(output_rows)}`",
        f"Enabled loss counts: `{dict(enabled_loss_counts)}`",
        "",
        "This manifest rejoins verifier facts as deterministic control metadata. All verifier losses are closed, and learned verifier heads remain telemetry-only.",
        "",
        "The effective verifier block is outside `model_input`, so it can be used by audits/controllers without becoming a direct encoder shortcut.",
        "",
    ]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")

    print(json.dumps({"stage": STAGE, "passed": card["passed"], "rows": len(output_rows), "enabled_loss_counts": dict(enabled_loss_counts), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
