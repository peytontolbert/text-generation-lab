#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9501
NAME = "stage9501_verifier_label_authority_map"
STAGE9490_MANIFEST = ROOT / "runs/local/artifacts/stage9490_phase_aware_episode_verifier_manifest/phase_aware_episode_verifier_manifest.jsonl"
STAGE9486 = ROOT / "runs/summaries/stage9486_target_prefix_observe_phase_probe_audit.json"
STAGE9492 = ROOT / "runs/summaries/stage9492_phase_aware_episode_verifier_probe_audit.json"
STAGE9500 = ROOT / "runs/summaries/stage9500_boundary_verifier_overlay_contract.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9501_verifier_label_authority_map"
AUTHORITY_MAP = OUT_DIR / "verifier_label_authority_map.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "VERIFIER_LABEL_AUTHORITY_MAP_STAGE9501.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def transition_parts(row: dict) -> tuple[dict, dict, dict]:
    transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    observation = transition.get("observation_t") if isinstance(transition.get("observation_t"), dict) else {}
    reward = transition.get("reward_or_verifier") if isinstance(transition.get("reward_or_verifier"), dict) else {}
    next_state = transition.get("state_t_plus_1") if isinstance(transition.get("state_t_plus_1"), dict) else {}
    return observation, reward, next_state


def derived_labels(row: dict) -> dict[str, object]:
    observation, reward, next_state = transition_parts(row)
    return {
        "episode_boundary_match": observation.get("boundary_next_token_match"),
        "episode_target_prefix_match": observation.get("target_prefix_match"),
        "episode_failure_type": reward.get("failure_type"),
        "episode_repair_outcome": next_state.get("repair_outcome"),
        "episode_step_value": reward.get("reward"),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(STAGE9490_MANIFEST)
    stage9486 = load_json(STAGE9486)
    stage9492 = load_json(STAGE9492)
    stage9500 = load_json(STAGE9500)
    failures: list[str] = []
    if not rows:
        failures.append("missing_stage9490_rows")
    if stage9500.get("passed") is not True:
        failures.append("stage9500_boundary_overlay_not_passed")

    field_counts: dict[str, Counter] = defaultdict(Counter)
    split_field_counts: dict[str, Counter] = defaultdict(Counter)
    missing_by_field: dict[str, list[str]] = defaultdict(list)
    authority_rows: list[str] = []
    for row in rows:
        row_id = row.get("row_id")
        if any((row.get("authority") or {}).values()):
            authority_rows.append(row_id)
        for field, value in derived_labels(row).items():
            if value is None:
                missing_by_field[field].append(row_id)
            field_counts[field][str(value)] += 1
            split_field_counts[field][f"{row.get('split')}::{value}"] += 1
    if authority_rows:
        failures.append("authority_rows_present")
    if any(missing_by_field.values()):
        failures.append("missing_derived_label_values")

    loss_counts = Counter()
    for row in rows:
        for loss_name, enabled in (row.get("loss_mask") or {}).items():
            if enabled:
                loss_counts[loss_name] += 1
    expected_loss_counts = {
        "episode_boundary_match_ce": len(rows),
        "episode_failure_type_ce": len(rows),
        "episode_repair_outcome_ce": len(rows),
        "episode_step_value_mse": len(rows),
        "episode_target_prefix_match_ce": len(rows),
    }
    if dict(loss_counts) != expected_loss_counts:
        failures.append("unexpected_stage9490_loss_counts")

    stage9486_metrics = stage9486.get("metrics", {}) if isinstance(stage9486.get("metrics"), dict) else {}
    stage9492_metrics = stage9492.get("metrics", {}) if isinstance(stage9492.get("metrics"), dict) else {}
    stage9500_metrics = stage9500.get("metrics", {}) if isinstance(stage9500.get("metrics"), dict) else {}
    verifier_fields = {
        "episode_boundary_match": {
            "loss": "episode_boundary_match_ce",
            "effective_authority": "deterministic_overlay",
            "effective_rule": "observation_t.boundary_next_token_match",
            "learned_head_role": "telemetry_only",
            "evidence": "Stage9500 effective exact 1.0 and zero false boundary accepts; Stage9496/9499 learned head did not quality-pass.",
            "may_authorize_acceptance": False,
        },
        "episode_target_prefix_match": {
            "loss": "episode_target_prefix_match_ce",
            "effective_authority": "deterministic_overlay",
            "effective_rule": "observation_t.target_prefix_match",
            "learned_head_role": "telemetry_and_representation_probe",
            "evidence": "Stage9486 isolated target-prefix probe passed, but effective verifier acceptance must still use the deterministic observation.",
            "may_authorize_acceptance": False,
        },
        "episode_failure_type": {
            "loss": "episode_failure_type_ce",
            "effective_authority": "deterministic_normalizer",
            "effective_rule": "reward_or_verifier.failure_type derived from residual verifier reasons",
            "learned_head_role": "telemetry_only_until_isolated_probe_passes",
            "evidence": "Stage9492 multi-head verifier probe collapsed on default/majority labels; no isolated failure-type pass exists yet.",
            "may_authorize_acceptance": False,
        },
        "episode_repair_outcome": {
            "loss": "episode_repair_outcome_ce",
            "effective_authority": "transition_record",
            "effective_rule": "state_t_plus_1.repair_outcome",
            "learned_head_role": "telemetry_only_until_isolated_probe_passes",
            "evidence": "Outcome is post-step transition state. It is useful for diagnosis and curricula but should not be model authority.",
            "may_authorize_acceptance": False,
        },
        "episode_step_value": {
            "loss": "episode_step_value_mse",
            "effective_authority": "deterministic_reward",
            "effective_rule": "reward_or_verifier.reward / reward_or_verifier.step_passed",
            "learned_head_role": "value_estimate_only",
            "evidence": "Value is verifier-backed reward. Learned value can rank actions later, but acceptance is verifier-driven.",
            "may_authorize_acceptance": False,
        },
    }

    authority_map = {
        "passed": not failures,
        "failures": failures,
        "source_manifest": str(STAGE9490_MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "field_counts": {field: dict(sorted(counts.items())) for field, counts in sorted(field_counts.items())},
        "split_field_counts": {field: dict(sorted(counts.items())) for field, counts in sorted(split_field_counts.items())},
        "loss_counts": dict(sorted(loss_counts.items())),
        "expected_loss_counts": expected_loss_counts,
        "missing_by_field": {field: ids for field, ids in sorted(missing_by_field.items()) if ids},
        "authority_rows": authority_rows,
        "verifier_fields": verifier_fields,
        "probe_evidence": {
            "stage9486_target_prefix": {
                "passed": stage9486.get("passed"),
                "final_eval_joint_proxy_exact": stage9486_metrics.get("final_eval_joint_proxy_exact"),
                "final_strict_joint_proxy_exact": stage9486_metrics.get("final_strict_joint_proxy_exact"),
            },
            "stage9492_all_verifier": {
                "passed": stage9492.get("passed"),
                "final_eval_joint_proxy_exact": stage9492_metrics.get("final_eval_joint_proxy_exact"),
                "final_strict_joint_proxy_exact": stage9492_metrics.get("final_strict_joint_proxy_exact"),
            },
            "stage9500_boundary_overlay": {
                "passed": stage9500.get("passed"),
                "effective_boundary_exact": stage9500_metrics.get("effective_boundary_exact"),
                "effective_false_boundary_accept_rows": len(stage9500_metrics.get("effective_false_boundary_accept_rows") or []),
            },
        },
        "decision": "Verifier-derived labels may be trained as telemetry/representation heads, but no verifier head may authorize acceptance, decoder promotion, scoring, runtime, or harness execution. Effective authority stays with deterministic verifier observations and transition records.",
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "promotion_ready": False,
    }
    AUTHORITY_MAP.write_text(json.dumps(authority_map, indent=2, sort_keys=True) + "\n")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": authority_map["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **authority_map},
        "artifacts": {"authority_map": str(AUTHORITY_MAP.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": authority_map["decision"],
        "next_best_step": "Build a verifier overlay rejoin manifest that uses deterministic effective verifier fields and keeps learned verifier heads telemetry-only, then audit it before any model execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    DOC.write_text("\n".join([
        "# Stage9501 Verifier Label Authority Map",
        "",
        f"Passed: `{authority_map['passed']}`",
        f"Rows: `{len(rows)}`",
        "",
        "## Decision",
        "",
        authority_map["decision"],
        "",
        "## Field Authority",
        "",
        "| Field | Effective authority | Learned role | May authorize acceptance |",
        "| --- | --- | --- | --- |",
        *[
            f"| `{field}` | `{spec['effective_authority']}` | `{spec['learned_head_role']}` | `{spec['may_authorize_acceptance']}` |"
            for field, spec in verifier_fields.items()
        ],
        "",
        "## Probe Evidence",
        "",
        f"- Stage9486 target-prefix isolated probe passed: `{stage9486.get('passed')}`",
        f"- Stage9492 all-verifier observe probe passed: `{stage9492.get('passed')}`",
        f"- Stage9500 boundary deterministic overlay passed: `{stage9500.get('passed')}`",
        "",
        "The next verifier rejoin must use deterministic effective verifier fields for authority and treat learned verifier outputs as calibration/diagnostic telemetry.",
        "",
    ]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")

    print(json.dumps({"stage": STAGE, "passed": authority_map["passed"], "rows": len(rows), "fields": sorted(verifier_fields), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
