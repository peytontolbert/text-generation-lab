#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9445
NAME = "stage9445_episode_step_suffix_transition_contract"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9444_gated_prior_rejoin_residual_diagnosis.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "episode_step_suffix_transition_contract.json"
SCHEMA = OUT_DIR / "episode_step_suffix_transition_schema.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_SUFFIX_TRANSITION_CONTRACT_STAGE9445.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9444_not_passed")

    schema = {
        "schema_name": "episode_step_suffix_transition_v1",
        "purpose": "Represent decoder/denoise repair as ordered maintainer episode steps instead of flat mixed repair rows.",
        "required_fields": {
            "episode_id": "Opaque id for a full maintenance attempt or synthetic repair trajectory.",
            "step_id": "Opaque row-local step id within the episode.",
            "step_index": "Integer transition index in the episode.",
            "split": "train|eval|strict_eval.",
            "language_family": "python|rust|c_family|web_js_ts_html or other audited family.",
            "phase": "observe|orient|act|decode|verify|repair|terminate.",
            "state_t": "Structured state before the step; no target labels or hidden authority.",
            "action_t": "Typed action taken or proposed at the step.",
            "observation_t": "Tool/verifier/model observation used by the repair step.",
            "reward_or_verifier": "Verifier-derived signal: pass/fail/failure type/confidence, not hidden scoring.",
            "state_t_plus_1": "Clean next state or repaired state target.",
            "target_suffix_choice": "Route-local continuation class for suffix/token repair.",
            "active_generation_prefix_span": "Bounded prefix shown to the decoder/denoiser.",
            "decoder_target": "Bounded target text for authorized denoise or future gated decode.",
            "loss_mask": "Per-loss authorization card. Decoder CE remains false until separately authorized.",
            "authority": "Closed authority flags for body/source/runtime/Gemma/harness/scoring/promotion.",
        },
        "forbidden_input_fields": [
            "target_suffix_choice visible as a label token in state_t",
            "decoder_target copied into model input",
            "stage/objective labels in opaque ids",
            "hidden scoring references",
            "runtime/body/source authority fields set true",
        ],
        "step_transition_equation": "state_t + action_t + observation_t -> state_t_plus_1",
        "episode_equation": "episode = ordered sequence of step_transition rows",
    }
    contract = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9444_gated_prior_rejoin_residual_diagnosis",
        "problem_reframed": {
            "previous_flat_surface": "mixed prefix-primed denoise rows with route-local suffix interference",
            "new_transition_surface": "episode-step repair transitions with phase/action/verifier fields",
            "current_residual_target": "suffix-token misses and a small repetition/unterminated repair pocket",
        },
        "curriculum_mapping": {
            "episode": "one complete software-maintenance attempt, from task observation through verified finish or abstain",
            "step": "one observe/action/reward-or-verifier/next-state transition inside the episode",
            "suffix_choice_row": "one repair step, usually phase=repair or decode, where the next continuation is conditioned on route-local state",
        },
        "required_compiler_changes_next": [
            "assign episode_id and step_index to denoise/decoder repair rows",
            "separate phase labels from target labels",
            "carry verifier_failure_type and reward_or_verifier into repair rows",
            "include route-local suffix choice as target, not visible input shortcut",
            "emit per-step loss masks so denoise rows do not authorize decoder CE",
            "audit that query/step ids alone do not solve target suffix or repair route",
        ],
        "probe_gate_next": {
            "target_prefix_match_rate": 1.0,
            "boundary_next_token_match_rate": 1.0,
            "contentful_rate": 1.0,
            "degenerate_repetition_rows": 0,
            "unterminated_rows": 0,
            "internal_leak_rows": 0,
            "decoder_ce_rows": 0,
        },
        "schema_path": str(SCHEMA.relative_to(ROOT)),
        "authority": dict(AUTHORITY_CLOSED),
    }
    SCHEMA.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": contract["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **contract},
        "artifacts": {
            "contract": str(CONTRACT.relative_to(ROOT)),
            "schema": str(SCHEMA.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Defined the episode-step transition contract for route-local suffix repair without opening decoder CE or execution.",
        "next_best_step": "Build Stage9446 episode-step suffix repair manifest from Stage9444 residuals and prior successful rows; keep it no-execution until shortcut and contract audits pass.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9445 Episode-Step Suffix Transition Contract",
                "",
                f"Passed: `{contract['passed']}`",
                "",
                "This stage folds the RL episode/step framing into the 100M maintainer curriculum.",
                "",
                "- Episode: a complete maintenance attempt.",
                "- Step: one `state_t, action_t, verifier/reward, state_t_plus_1` transition.",
                "- Current suffix-choice denoise rows: step-level repair transitions, not a standalone decoder capability.",
                "",
                "The next compiler patch should emit episode ids, step indices, phase labels, verifier failure fields, "
                "route-local suffix targets, and strict per-step loss masks.",
                "",
                "Decoder CE, runtime, Gemma, harness, hidden scoring, body/source emission, and promotion remain closed.",
                "",
            ]
        )
    )

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
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
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "next": summary["next_best_step"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
