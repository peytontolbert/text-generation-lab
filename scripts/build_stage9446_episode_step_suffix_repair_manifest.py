#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9446
NAME = "stage9446_episode_step_suffix_repair_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9445_episode_step_suffix_transition_contract.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9441_gated_prior_fusion_rejoin_manifest/gated_prior_fusion_rejoin_manifest.jsonl"
SAMPLES = ROOT / "runs/local/artifacts/stage9443_gated_prior_fusion_rejoin_probe/sample_generation_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "episode_step_suffix_repair_manifest.jsonl"
CARD = OUT_DIR / "episode_step_suffix_repair_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_SUFFIX_REPAIR_MANIFEST_STAGE9446.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def digest(value: str, n: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:n]


def residual_reasons(sample: dict) -> list[str]:
    reasons: list[str] = []
    if not sample.get("exact_match"):
        reasons.append("not_exact")
    if not sample.get("target_prefix_match"):
        reasons.append("target_prefix_miss")
    if not (sample.get("boundary_next_token") or {}).get("match"):
        reasons.append("boundary_next_token_miss")
    if sample.get("short_or_junk") or sample.get("empty_output"):
        reasons.append("not_contentful")
    if sample.get("degenerate_repetition"):
        reasons.append("degenerate_repetition")
    if not sample.get("stopped_on_eos"):
        reasons.append("unterminated")
    return reasons


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    source_rows = load_jsonl(SOURCE_MANIFEST)
    samples_card = load_json(SAMPLES)
    samples = samples_card.get("samples") if isinstance(samples_card.get("samples"), list) else []
    samples_by_id = {str(sample.get("row_id")): sample for sample in samples}

    rows: list[dict] = []
    split_counts = Counter()
    outcome_counts = Counter()
    phase_counts = Counter()
    authority_rows = 0
    decoder_ce_rows = 0
    denoise_ce_rows = 0
    copied_target_input_rows = 0

    for idx, source_row in enumerate(source_rows):
        row_id = str(source_row.get("row_id"))
        sample = samples_by_id.get(row_id, {})
        reasons = residual_reasons(sample)
        outcome = "successful_suffix_repair_step" if not reasons else "residual_suffix_repair_step"
        episode_seed = str(source_row.get("source_stage9388_row_id") or source_row.get("source_row_id") or row_id)
        episode_id = f"ep_step_suffix_{digest(episode_seed)}"
        step_id = f"step_suffix_{digest(row_id)}"
        model_input = source_row.get("model_input") if isinstance(source_row.get("model_input"), dict) else {}
        input_state = source_row.get("input_state") if isinstance(source_row.get("input_state"), dict) else {}
        prior = source_row.get("suffix_choice_prior") if isinstance(source_row.get("suffix_choice_prior"), dict) else {}
        boundary = sample.get("boundary_next_token") if isinstance(sample.get("boundary_next_token"), dict) else {}

        row = {
            "row_id": f"stage9446_episode_step_suffix_{idx:04d}",
            "source_stage9441_row_id": row_id,
            "source_stage9443_generation_row_id": row_id,
            "episode_id": episode_id,
            "step_id": step_id,
            "step_index": 0,
            "split": source_row.get("split"),
            "language_family": source_row.get("language_family"),
            "phase": "repair",
            "transition_schema": "episode_step_suffix_transition_v1",
            "episode_transition": {
                "state_t": {
                    "target_visible": False,
                    "clean_target_hidden_from_model_input": True,
                    "active_generation_prefix_span": model_input.get("active_generation_prefix_span"),
                    "bridge_error_family": model_input.get("bridge_error_family"),
                    "route": source_row.get("route"),
                    "failure_type": input_state.get("failure_type"),
                    "suffix_choice_prior_confidence": prior.get("confidence"),
                    "suffix_choice_prior_source": source_row.get("suffix_choice_prior_source"),
                },
                "action_t": {
                    "action": "REPAIR_SUFFIX_CONTINUATION",
                    "target_surface": model_input.get("target_surface"),
                },
                "observation_t": {
                    "generated_text": sample.get("generated_text"),
                    "target_prefix_match": bool(sample.get("target_prefix_match")),
                    "boundary_next_token_match": bool(boundary.get("match")),
                    "boundary_expected_rank": boundary.get("expected_rank"),
                    "degenerate_repetition": bool(sample.get("degenerate_repetition")),
                    "short_or_junk": bool(sample.get("short_or_junk")),
                    "stopped_on_eos": bool(sample.get("stopped_on_eos")),
                    "residual_reasons": reasons,
                },
                "reward_or_verifier": {
                    "verifier_source": "stage9443_generation_audit",
                    "step_passed": not reasons,
                    "reward": 1.0 if not reasons else 0.0,
                    "failure_type": "none" if not reasons else "+".join(reasons),
                },
                "state_t_plus_1": {
                    "decoder_text": source_row.get("decoder_text") or source_row.get("clean_target"),
                    "target_suffix_choice": prior.get("target") or prior.get("label"),
                    "repair_outcome": outcome,
                },
            },
            "loss_mask": {
                "decoder_ce": False,
                "denoise_ce": False,
                "runtime_reward": False,
                "episode_step_ce": False,
            },
            "authority": dict(AUTHORITY_CLOSED),
            "anti_cheat": {
                "decoder_target_copied_to_model_input": False,
                "target_suffix_choice_visible_as_input_label": False,
                "stage_label_in_opaque_ids": False,
                "decoder_ce_closed": True,
                "runtime_closed": True,
            },
        }
        rows.append(row)
        split_counts[str(row["split"])] += 1
        outcome_counts[outcome] += 1
        phase_counts[str(row["phase"])] += 1
        authority_rows += int(any(bool(v) for v in row["authority"].values()))
        decoder_ce_rows += int(bool(row["loss_mask"].get("decoder_ce")))
        denoise_ce_rows += int(bool(row["loss_mask"].get("denoise_ce")))
        copied_target_input_rows += int(str(row["episode_transition"]["state_t"].get("active_generation_prefix_span") or "") == str(row["episode_transition"]["state_t_plus_1"].get("decoder_text") or ""))

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9445_not_passed")
    if len(source_rows) != 50 or len(samples) != 50 or len(rows) != 50:
        failures.append("unexpected_row_count")
    if authority_rows:
        failures.append("authority_rows_present")
    if decoder_ce_rows or denoise_ce_rows:
        failures.append("loss_authority_opened")
    if copied_target_input_rows:
        failures.append("target_copied_to_prefix_rows")

    card = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9445_episode_step_suffix_transition_contract",
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "phase_counts": dict(sorted(phase_counts.items())),
        "authority_rows": authority_rows,
        "decoder_ce_rows": decoder_ce_rows,
        "denoise_ce_rows": denoise_ce_rows,
        "copied_target_input_rows": copied_target_input_rows,
        "schema": "episode_step_suffix_transition_v1",
        "authority": dict(AUTHORITY_CLOSED),
    }
    write_jsonl(MANIFEST, rows)
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
        "decision": "Built a no-execution episode-step suffix repair manifest; all model/loss/runtime authority remains closed.",
        "next_best_step": "Audit Stage9446 for episode-step contract compliance, shortcut leakage, and target-copy leakage before considering any training wrapper.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9446 Episode-Step Suffix Repair Manifest",
                "",
                f"Passed: `{card['passed']}`",
                f"Rows: `{len(rows)}`",
                f"Splits: `{dict(sorted(split_counts.items()))}`",
                f"Outcomes: `{dict(sorted(outcome_counts.items()))}`",
                "",
                "This manifest recasts the gated suffix repair probe as episode-step transitions. It is not trainable yet: "
                "all decoder CE, denoise CE, runtime reward, model execution, and promotion authority remain closed.",
                "",
            ]
        )
    )

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows_reg = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows_reg.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    rows_reg = sorted(rows_reg, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows_reg
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows_reg),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "rows": len(rows), "outcomes": card["outcome_counts"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
