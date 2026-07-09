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
STAGE = 9523
NAME = "stage9523_episode_obs_diag_minimal_context_preflight_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9522_episode_obs_diag_minimal_context_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9523_episode_obs_diag_minimal_context_target_100m_contract_preflight"
CONTRACT = RUN_DIR / "probe_contract_audit.json"
AUDIT = RUN_DIR / "stage9523_preflight_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_MINIMAL_CONTEXT_PREFLIGHT_STAGE9523.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(CONTRACT)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9522_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_preflight_not_passed")
    if contract.get("model_execution_attempted") is not False:
        failures.append("model_execution_attempted_during_preflight")
    if contract.get("probe_scale") != "target_100m":
        failures.append("not_target_100m_contract")
    if contract.get("implementation") != "transformer":
        failures.append("not_transformer_contract")
    if contract.get("rows") != 58:
        failures.append("unexpected_rows")
    if contract.get("split_counts") != {"eval": 6, "other": 0, "strict_eval": 6, "train": 46}:
        failures.append("unexpected_split_counts")
    losses = contract.get("loss_counts") if isinstance(contract.get("loss_counts"), dict) else {}
    for key in ["episode_failure_type_ce", "episode_repair_outcome_ce", "episode_step_value_mse"]:
        if losses.get(key) != 58:
            failures.append(f"{key}_count_mismatch")
    for key in ["decoder_ce", "denoise_ce", "runtime_reward", "episode_boundary_match_ce", "episode_target_prefix_match_ce"]:
        if losses.get(key) != 0:
            failures.append(f"{key}_not_closed")
    if contract.get("unsafe_loss_rows") != 0 or contract.get("authority_rows") != 0:
        failures.append("unsafe_or_authority_rows_present")
    if contract.get("final_checkpoint_export_disabled") is not True or contract.get("final_model_save_skipped") is not True:
        failures.append("checkpoint_export_or_model_save_not_closed")
    if contract.get("cleanup_requested") is not True:
        failures.append("cleanup_not_requested")

    authority = dict(AUTHORITY_CLOSED)
    authority["model_execution_authorized_next"] = not failures
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9522_episode_obs_diag_minimal_context_audit",
        "contract": str(CONTRACT.relative_to(ROOT)),
        "rows": contract.get("rows"),
        "split_counts": contract.get("split_counts"),
        "loss_counts": losses,
        "manifest_sha256": contract.get("manifest_sha256"),
        "probe_scale": contract.get("probe_scale"),
        "implementation": contract.get("implementation"),
        "model_execution_attempted": contract.get("model_execution_attempted"),
        "execution_authorized_for_next_stage": not failures,
        "authority": authority,
        "model_execution_authorized_next": not failures,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "gemma_execution_authorized_next": False,
        "harness_execution_authorized_next": False,
        "scoring_authorized_next": False,
        "promotion_ready": False,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": authority,
        "metrics": {**authority, **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "contract": str(CONTRACT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Contract-only target-100M preflight passed for the minimal-context diagnosis manifest.",
        "next_best_step": "Run Stage9524 target-100M minimal-context diagnosis probe under trellis, then audit whether eval exactness recovers without high-confidence wrong rows.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9523 Episode Observation Diagnosis Minimal-Context Preflight",
        "",
        f"Passed: `{audit['passed']}`",
        f"Execution authorized for next stage: `{audit['execution_authorized_for_next_stage']}`",
        f"Split counts: `{audit['split_counts']}`",
        "",
        "Only the next structured probe is authorized. Decoder CE, denoise CE, runtime, harness, Gemma, scoring, checkpoint export, and promotion remain closed.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": authority, "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "execution_authorized_for_next_stage": audit["execution_authorized_for_next_stage"], "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
