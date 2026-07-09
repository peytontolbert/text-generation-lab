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
STAGE = 9538
NAME = "stage9538_episode_obs_diag_component_overlay_contract"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9537_episode_obs_diag_component_overlay_analysis.json"
SOURCE_ROWS = ROOT / "runs/local/artifacts/stage9537_episode_obs_diag_component_overlay_analysis/episode_obs_diag_component_overlay_rows.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts/stage9538_episode_obs_diag_component_overlay_contract"
CONTRACT = OUT_DIR / "episode_obs_diag_component_overlay_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_COMPONENT_OVERLAY_CONTRACT_STAGE9538.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


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
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(SOURCE_ROWS)
    failures: list[str] = []
    overlay_rates = source.get("metrics", {}).get("overlay_exact_rates") if isinstance(source.get("metrics"), dict) else {}
    if source.get("passed") is not True:
        failures.append("stage9537_not_passed")
    if overlay_rates != {"eval": 1.0, "strict_eval": 1.0, "train": 1.0}:
        failures.append("overlay_not_exact_all_splits")
    if len(rows) != 58:
        failures.append("unexpected_overlay_row_count")
    mismatch_rows = [row.get("row_id") for row in rows if row.get("exact") is not True]
    if mismatch_rows:
        failures.append("overlay_mismatch_rows")

    contract = {
        "passed": not failures,
        "failures": failures,
        "contract_name": "episode_obs_diag_component_overlay_v1",
        "source_analysis": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_rows": str(SOURCE_ROWS.relative_to(ROOT)),
        "rows": len(rows),
        "overlay_exact_rates": overlay_rates,
        "mismatch_rows": mismatch_rows,
        "effective_authority_rule": {
            "effective_failure_type_source": "deterministic_observation_component_overlay",
            "ordered_components": [
                "not_exact",
                "target_prefix_miss",
                "boundary_next_token_miss",
                "degenerate_repetition",
                "unterminated",
            ],
            "none_when_no_components": True,
            "component_source": "episode_transition.observation_t.residual_reasons",
            "learned_episode_failure_type_head": "telemetry_only",
        },
        "training_policy": {
            "do_not_promote_stage9529_boundary_component_branch": True,
            "do_not_promote_stage9533_python_boundary_upsample_branch": True,
            "best_training_base_remains": "stage9525_episode_obs_diag_residual_gate_manifest",
            "best_probe_evidence_remains": "stage9528_episode_obs_diag_residual_gate_probe_audit",
            "next_training_probe_required": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "promotion_ready": False,
    }
    CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": contract["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **contract},
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Established deterministic observation-component overlay as effective failure_type authority and demoted learned composite failure_type to telemetry.",
        "next_best_step": "Update the verifier/episode diagnosis compiler to emit the Stage9538 effective_failure_type overlay contract before any future rejoin or decoder-gating probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9538 Episode Observation Diagnosis Component Overlay Contract",
        "",
        f"Passed: `{contract['passed']}`",
        f"Overlay exact rates: `{overlay_rates}`",
        "",
        "Effective `failure_type` authority is now deterministic composition of observation residual components.",
        "The learned composite `episode_failure_type` head remains useful telemetry but must not authorize verifier outcome decisions.",
        "",
        "Rejected branches:",
        "- Stage9529 boundary-component feature branch",
        "- Stage9533/9536 Python boundary upsample branch",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": contract["passed"], "overlay_exact_rates": overlay_rates, "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
