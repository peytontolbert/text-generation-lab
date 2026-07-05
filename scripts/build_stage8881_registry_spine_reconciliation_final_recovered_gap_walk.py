#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8881
NAME = "stage8881_registry_spine_reconciliation_final_recovered_gap_walk"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_FINAL_RECOVERED_GAP_WALK_STAGE8881.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8879_closed_gate_status_reconciliation.json",
    ROOT / "runs/summaries/stage8880_final_recovered_gap_walk.json",
]
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> None:
    registry = load(REGISTRY) or {"rows": [], "metrics": {}}
    cards = [load(path) for path in SOURCES]
    failures = []
    for path, card_src in zip(SOURCES, cards):
        if not path.exists():
            failures.append(f"missing:{path}")
        elif card_src.get("passed") is not True:
            failures.append(f"failed:{card_src.get('stage_name')}")
    names = {NAME}
    names.update(card_src.get("stage_name") for card_src in cards if card_src)
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") not in names]
    for path, card_src in zip(SOURCES, cards):
        if card_src:
            rows.append({"stage": int(card_src["stage"]), "stage_name": card_src["stage_name"], "passed": card_src.get("passed") is True, "path": str(path), "authority": AUTHORITY_CLOSED, "next_best_step": card_src.get("next_best_step")})
    gap = cards[1].get("metrics", {}) if len(cards) > 1 else {}
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "source_failures": failures,
            "sources_indexed": len([c for c in cards if c]),
            "registry_rows_before": len(registry.get("rows", [])),
            "registry_rows_after": len(rows) + 1,
            "unresolved_missing_or_blocked_nodes": gap.get("unresolved_missing_or_blocked_nodes"),
            "optional_missing_nodes": gap.get("optional_missing_nodes"),
            "actionable_unresolved_nodes": gap.get("actionable_unresolved_nodes"),
            "closed_gate_recovered_nodes": gap.get("closed_gate_recovered_nodes"),
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
        },
        "decision": "Reconciled final recovered gap walk into registry/spine.",
        "next_best_step": "Recovery is caught up enough to choose a deliberate next branch: explicit tiny structured probe authorization review, optional metadata-only commit inventory preflight, or no-execution denoise authorization design. Do not run training directly.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = not failures
    registry["metrics"] = {
        **registry.get("metrics", {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": card["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "historical_failed_rows": sum(1 for row in rows if row.get("passed") is not True),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8881 Registry Spine Reconciliation Final Recovered Gap Walk",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Unresolved missing/blocking nodes: `{card['metrics']['unresolved_missing_or_blocked_nodes']}`",
        f"Optional missing nodes: `{card['metrics']['optional_missing_nodes']}`",
        f"Actionable unresolved nodes: `{card['metrics']['actionable_unresolved_nodes']}`",
        f"Closed-gate recovered nodes: `{card['metrics']['closed_gate_recovered_nodes']}`",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    marker = "## Stage8879-8881 Final Closed-Gate Recovery Walk"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Bounded decoder CE and denoise repair are now reconciled as recovered closed gates rather than missing prerequisite nodes.",
            "",
            "- Bounded decoder CE has target controls, heldout non-CE eval controls, closed package gate, and telemetry artifact gate recovered. It still requires explicit tiny execution authorization before any run.",
            "- Denoise repair has output-repair controls, verifier-guided repair targets, and denoise/diffusion contract recovered. Denoise CE and runtime verifier execution remain closed.",
            "- The only missing node left by the recovered graph is optional metadata-only commit inventory preflight, which must not run repository walking unless explicitly requested.",
            "",
            "This remains no-authority recovery: no model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, mining, controller merge, memory writes, or promotion is authorized.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
