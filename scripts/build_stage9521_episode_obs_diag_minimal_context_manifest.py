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
STAGE = 9521
NAME = "stage9521_episode_obs_diag_minimal_context_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9513_episode_obs_diag_counterbalance_repair_manifest/episode_obs_diag_counterbalance_repair_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9520_episode_obs_diag_observation_dominant_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9521_episode_obs_diag_minimal_context_manifest"
MANIFEST = OUT_DIR / "episode_obs_diag_minimal_context_manifest.jsonl"
CARD = OUT_DIR / "episode_obs_diag_minimal_context_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_MINIMAL_CONTEXT_MANIFEST_STAGE9521.md"
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


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


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
        failures.append("stage9520_not_safe_failure_source")

    output_rows: list[dict] = []
    split_counts = Counter()
    loss_counts = Counter()
    language_counts = Counter()
    model_feature_counts = Counter()
    forbidden_loss_rows: list[str] = []
    authority_rows: list[str] = []
    effective_leak_rows: list[str] = []
    literal_prefix_rows: list[str] = []
    missing_context_rows: list[str] = []
    for idx, row in enumerate(rows):
        out = copy.deepcopy(row)
        out["row_id"] = f"stage9521_obs_diag_minctx_{idx:04d}"
        out["source_stage9513_row_id"] = row.get("row_id")
        out["objective_family"] = "episode_observation_diagnosis_minimal_context"
        out["route"] = "KEEP_EPISODE_OBS_DIAG_MINIMAL_CONTEXT"
        out["authority"] = dict(AUTHORITY_CLOSED)

        transition = out.get("episode_transition") if isinstance(out.get("episode_transition"), dict) else {}
        state = transition.get("state_t") if isinstance(transition.get("state_t"), dict) else {}
        action = transition.get("action_t") if isinstance(transition.get("action_t"), dict) else {}
        transition["state_t"] = {
            "active_generation_prefix_span": "redacted_literal_prefix_for_observation_diagnosis",
            "bridge_error_family": state.get("bridge_error_family"),
            "prefix_token_bucket": state.get("prefix_token_bucket"),
            "route": "USE_FOR_DENOISE_REPAIR_WITH_GATED_SUFFIX_CHOICE_PRIOR",
            "suffix_prior_available": state.get("suffix_prior_available"),
        }
        transition["action_t"] = {
            "action": action.get("action"),
            "emission_surface_family": action.get("emission_surface_family"),
        }
        out["episode_transition"] = transition

        model_input = dict(out.get("model_input") or {})
        model_input["obs_diag_minimal_context_phase"] = True
        model_input["literal_prefix_redacted"] = True
        model_input["context_kept_language_family"] = out.get("language_family")
        model_input["context_kept_bridge_error_family"] = transition["state_t"].get("bridge_error_family")
        model_input["context_kept_prefix_token_bucket"] = transition["state_t"].get("prefix_token_bucket")
        model_input["context_kept_suffix_prior_available"] = transition["state_t"].get("suffix_prior_available")
        model_input["context_kept_action_type"] = transition["action_t"].get("action")
        out["model_input"] = model_input

        out["training_candidate"] = {
            **(out.get("training_candidate") or {}),
            "minimal_context_phase": True,
            "literal_prefix_redacted": True,
            "controlled_context_available": True,
            "primitive_observation_evidence_visible": True,
            "model_execution_authorized_now": False,
            "decoder_ce_closed": True,
            "denoise_ce_closed": True,
            "runtime_reward_closed": True,
        }
        loss_mask = dict(out.get("loss_mask") or {})
        for loss in TRAINABLE_LOSSES:
            loss_mask[loss] = True
        for loss in FORBIDDEN_LOSSES:
            loss_mask[loss] = False
        out["loss_mask"] = loss_mask

        for loss, enabled in loss_mask.items():
            if enabled:
                loss_counts[loss] += 1
        if any(loss_mask.get(loss) for loss in FORBIDDEN_LOSSES):
            forbidden_loss_rows.append(out["row_id"])
        if any((out.get("authority") or {}).values()):
            authority_rows.append(out["row_id"])
        if any(key.startswith("effective_") for key in model_input):
            effective_leak_rows.append(out["row_id"])
        if transition["state_t"]["active_generation_prefix_span"] != "redacted_literal_prefix_for_observation_diagnosis":
            literal_prefix_rows.append(out["row_id"])
        required = [
            transition["state_t"].get("bridge_error_family"),
            transition["state_t"].get("prefix_token_bucket"),
            transition["state_t"].get("suffix_prior_available"),
            transition["action_t"].get("action"),
            model_input.get("obs_prefix_relation"),
            model_input.get("obs_boundary_relation"),
        ]
        if any(value is None for value in required):
            missing_context_rows.append(out["row_id"])
        split_counts[out.get("split")] += 1
        language_counts[out.get("language_family")] += 1
        for key in model_input:
            if key.startswith("obs_") or key.startswith("context_") or key in {"literal_prefix_redacted"}:
                model_feature_counts[key] += 1
        output_rows.append(out)

    expected_loss_counts = {loss: len(output_rows) for loss in sorted(TRAINABLE_LOSSES)}
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
    if literal_prefix_rows:
        failures.append("literal_prefix_not_redacted")
    if missing_context_rows:
        failures.append("missing_minimal_context_rows")

    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows))
    card = {
        "passed": not failures,
        "failures": failures,
        "source_manifest": str(SOURCE.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(output_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "expected_loss_counts": expected_loss_counts,
        "model_feature_counts": dict(sorted(model_feature_counts.items())),
        "forbidden_loss_rows": forbidden_loss_rows,
        "authority_rows": authority_rows,
        "effective_leak_rows": effective_leak_rows,
        "literal_prefix_rows": literal_prefix_rows,
        "missing_context_rows": missing_context_rows,
        "contract": {
            "literal_prefix_redacted": not literal_prefix_rows,
            "language_route_action_context_kept": not missing_context_rows,
            "primitive_observation_features_visible": True,
            "effective_labels_outside_model_input": not effective_leak_rows,
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
        "decision": "Built minimal-context diagnosis rows that keep controlled language/route/action context plus primitive observation facts while redacting literal prefix text.",
        "next_best_step": "Audit Stage9521, then run contract-only target-100M preflight if leakage and loss checks pass.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9521 Episode Observation Diagnosis Minimal-Context Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{len(output_rows)}`",
        f"Split counts: `{dict(split_counts)}`",
        f"Language counts: `{dict(language_counts)}`",
        f"Loss counts: `{dict(loss_counts)}`",
        "",
        "This manifest keeps controlled language/route/action context and primitive `obs_*` verifier features, while redacting literal generation prefix text.",
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
