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
STAGE = 9542
NAME = "stage9542_episode_obs_diag_closed_boundary_rejoin_gate_audit"
SOURCE = ROOT / "runs/local/artifacts/stage9541_episode_obs_diag_closed_boundary_rejoin_gate_manifest/episode_obs_diag_closed_boundary_rejoin_gate_manifest.jsonl"
SOURCE_CARD = ROOT / "runs/local/artifacts/stage9541_episode_obs_diag_closed_boundary_rejoin_gate_manifest/episode_obs_diag_closed_boundary_rejoin_gate_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_CLOSED_BOUNDARY_REJOIN_GATE_AUDIT_STAGE9542.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def update_registry(summary: dict) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
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
        failures.append("stage9541_card_not_passed")
    if not rows:
        failures.append("missing_stage9541_rows")

    split_counts = Counter()
    enabled_losses = Counter()
    gate_counts = Counter()
    authority_rows: list[str] = []
    leakage_rows: list[str] = []
    missing_gate_rows: list[str] = []
    actual_authority_rows: list[str] = []
    non_stage9539_source_rows: list[str] = []

    for row in rows:
        row_id = str(row.get("row_id"))
        split_counts[row.get("split")] += 1
        for loss, enabled in (row.get("loss_mask") or {}).items():
            if enabled:
                enabled_losses[loss] += 1
        if any((row.get("authority") or {}).values()):
            authority_rows.append(row_id)
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        if any(key.startswith("effective_") or key.startswith("rejoin_") for key in model_input):
            leakage_rows.append(row_id)
        gate = row.get("rejoin_gate") if isinstance(row.get("rejoin_gate"), dict) else {}
        if gate.get("gate_source") != "stage9539_effective_verifier_component_overlay":
            missing_gate_rows.append(row_id)
        if gate.get("actual_decoder_authority_opened") or gate.get("actual_model_execution_authorized"):
            actual_authority_rows.append(row_id)
        gate_counts[f"terminal_candidate::{gate.get('would_allow_terminal_decode_rejoin_candidate')}"] += 1
        gate_counts[f"residual_candidate::{gate.get('would_route_to_residual_repair_candidate')}"] += 1
        if not str(row.get("source_stage9539_row_id") or "").startswith("stage9539_"):
            non_stage9539_source_rows.append(row_id)

    if len(rows) != 58:
        failures.append("unexpected_row_count")
    if split_counts != {"eval": 6, "strict_eval": 6, "train": 46}:
        failures.append("unexpected_split_counts")
    if enabled_losses:
        failures.append("enabled_losses_present")
    if authority_rows:
        failures.append("authority_rows_present")
    if leakage_rows:
        failures.append("effective_or_rejoin_labels_in_model_input")
    if missing_gate_rows:
        failures.append("missing_gate_rows")
    if actual_authority_rows:
        failures.append("actual_decoder_or_execution_authority_rows")
    if non_stage9539_source_rows:
        failures.append("non_stage9539_source_rows")
    if gate_counts.get("terminal_candidate::True") != 29 or gate_counts.get("residual_candidate::True") != 29:
        failures.append("unexpected_gate_counts")

    passed = not failures
    metrics = {
        "passed": passed,
        "failures": failures,
        "source_manifest": str(SOURCE.relative_to(ROOT)),
        "source_card": str(SOURCE_CARD.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "enabled_losses": dict(sorted(enabled_losses.items())),
        "gate_counts": dict(sorted(gate_counts.items())),
        "authority_rows": authority_rows,
        "leakage_rows": leakage_rows,
        "missing_gate_rows": missing_gate_rows,
        "actual_authority_rows": actual_authority_rows,
        "non_stage9539_source_rows": non_stage9539_source_rows,
        "contract": {
            "metadata_only": True,
            "all_losses_closed": not enabled_losses,
            "effective_and_rejoin_labels_outside_model_input": not leakage_rows,
            "terminal_candidate_is_not_authorization": True,
            "source_stage9539_only": not non_stage9539_source_rows,
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
        "artifacts": {"source_manifest": str(SOURCE.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Audited the Stage9541 closed-boundary rejoin gate as metadata-only. Terminal-pass rows are candidates only; no losses, decoder authority, runtime, or model execution opened.",
        "next_best_step": "Design a contract-only preflight for a future tiny terminal-pass rejoin probe using Stage9541 gates, or route residual rows back to repair data without reopening decoder CE.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9542 Episode Observation Diagnosis Closed-Boundary Rejoin Gate Audit",
        "",
        f"Passed: `{passed}`",
        f"Rows: `{len(rows)}`",
        f"Gate counts: `{dict(gate_counts)}`",
        f"Enabled losses: `{dict(enabled_losses)}`",
        "",
        "The rejoin gate is metadata-only. It is safe to use for a later contract-only preflight design, not for direct execution or decoder CE.",
        "",
    ]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": passed, "rows": len(rows), "gate_counts": dict(gate_counts), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
