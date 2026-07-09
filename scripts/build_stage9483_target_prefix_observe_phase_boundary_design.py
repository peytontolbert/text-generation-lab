#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from collections import Counter, defaultdict

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9483
NAME = "stage9483_target_prefix_observe_phase_boundary_design"
SOURCE_QUEUE_SUMMARY = ROOT / "runs/summaries/stage9482_target_prefix_positive_repair_queue.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9479_episode_target_prefix_balance_manifest/episode_target_prefix_balance_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts/stage9483_target_prefix_observe_phase_boundary_design"
DESIGN = OUT_DIR / "target_prefix_observe_phase_boundary_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TARGET_PREFIX_OBSERVE_PHASE_BOUNDARY_DESIGN_STAGE9483.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def append_structured(parts: list[str], prefix: str, payload: dict) -> None:
    for key in sorted(payload):
        if key.endswith("_id") or key in {"row_id", "target", "decoder_text", "source_ref", "path"}:
            continue
        value = payload[key]
        if isinstance(value, (str, int, float, bool)):
            parts.append(f"{prefix}.{key}={value}")
        elif isinstance(value, list):
            scalar = [item for item in value if isinstance(item, (str, int, float, bool))]
            if scalar:
                parts.append(f"{prefix}.{key}.count={len(scalar)}")
                for item in scalar[:12]:
                    parts.append(f"{prefix}.{key}.item={item}")


def current_encoder_text(row: dict) -> str:
    parts: list[str] = []
    if row.get("language_family"):
        parts.append(f"language={row.get('language_family')}")
    if row.get("route"):
        parts.append(f"route={row.get('route')}")
    if row.get("objective_family"):
        parts.append(f"objective={row.get('objective_family')}")
    transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    state = transition.get("state_t") if isinstance(transition.get("state_t"), dict) else {}
    action = transition.get("action_t") if isinstance(transition.get("action_t"), dict) else {}
    append_structured(parts, "episode.state", state)
    append_structured(parts, "episode.action", action)
    model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
    append_structured(parts, "model", model_input)
    return " | ".join(parts)


def label(row: dict) -> bool:
    return bool(row["episode_transition"]["observation_t"].get("target_prefix_match"))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    queue_summary = load_json(SOURCE_QUEUE_SUMMARY)
    rows = read_jsonl(SOURCE_MANIFEST)
    visible_text = [current_encoder_text(row).lower() for row in rows]
    observation_visible_rows = sum(1 for text in visible_text if "generated_text" in text or "target_prefix_match" in text or "failure_type" in text)
    by_lang_label = Counter((row.get("language_family"), label(row)) for row in rows)
    high_conf_wrong = queue_summary.get("metrics", {}).get("stage9481_high_confidence_wrong_rows", [])
    duplicate_inputs: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        duplicate_inputs[current_encoder_text(row)].append(row)
    contradictory_current_inputs = []
    for text, group in duplicate_inputs.items():
        labels = {label(row) for row in group}
        if len(labels) > 1:
            contradictory_current_inputs.append({"encoder_text": text, "row_ids": [row["row_id"] for row in group], "labels": sorted(labels)})

    failures: list[str] = []
    if queue_summary.get("passed") is not True:
        failures.append("source_stage9482_not_passed")
    if observation_visible_rows != 0:
        failures.append("current_encoder_unexpectedly_exposes_observation")
    if not high_conf_wrong:
        failures.append("source_high_conf_wrong_missing")

    design = {
        "passed": not failures,
        "failures": failures,
        "source_queue_summary": str(SOURCE_QUEUE_SUMMARY.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "current_encoder_observation_visible_rows": observation_visible_rows,
        "current_contradictory_encoder_inputs": contradictory_current_inputs,
        "current_target_prefix_counts_by_language_label": {f"{lang}::{target}": count for (lang, target), count in sorted(by_lang_label.items(), key=lambda kv: str(kv[0]))},
        "stage9481_high_confidence_wrong_rows": high_conf_wrong,
        "boundary_decision": "Do not continue treating episode_target_prefix_match as a pure pre-action policy target. It is a verifier/observation-phase target and should either be computed deterministically by the verifier or trained with an observe-phase input packet that exposes generated output evidence without exposing the label string.",
        "stage9484_manifest_requirements": {
            "phase": "verify_or_observe",
            "loss_mask_only_episode_target_prefix_match_ce": True,
            "include_model_input_generated_output_preview": True,
            "include_model_input_active_generation_prefix_span": True,
            "include_model_input_reference_prefix_or_expected_prefix_basis": "only if used as verifier-training, not policy-gating authority",
            "forbid_model_input_target_prefix_match_label": True,
            "forbid_model_input_failure_type_label_when_predicting_failure_type": True,
            "authority_closed": True,
            "decoder_ce_closed": True,
            "denoise_ce_closed": True,
            "runtime_reward_closed": True,
            "requires_shortcut_audit": [
                "single_feature_generated_contains_prefix_baseline",
                "language_only_baseline",
                "prefix_family_only_baseline",
                "generated_length_only_baseline",
            ],
        },
        "relationship_to_stage9482_queue": "Stage9482 positive rows remain useful, but they must be materialized as observe/verify-phase examples with generated-output evidence or as deterministic verifier fixtures, not as hidden-observation pre-action rows.",
        "authority": dict(AUTHORITY_CLOSED),
    }
    DESIGN.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n")
    authority = dict(AUTHORITY_CLOSED)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": design["passed"],
        "authority": authority,
        "metrics": {**authority, **design},
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Target-prefix repair should move to an observe/verify-phase input surface or deterministic verifier fixture before more target-prefix training.",
        "next_best_step": "Build Stage9484 observe-phase target-prefix manifest from Stage9482 queue with generated-output evidence visible, target-prefix label hidden, and shortcut baselines audited before execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9483 Target-Prefix Observe-Phase Boundary Design",
        "",
        f"Passed: `{design['passed']}`",
        f"Current encoder observation-visible rows: `{observation_visible_rows}`",
        f"Current contradictory encoder inputs: `{len(contradictory_current_inputs)}`",
        "",
        design["boundary_decision"],
        "",
        "Stage9482 positive rows remain useful, but they must be materialized as observe/verify-phase examples with generated-output evidence or as deterministic verifier fixtures, not as hidden-observation pre-action rows.",
        "",
        "Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": authority, "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = bool(reg_rows)
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows)}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures, "next_best_step": summary["next_best_step"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
