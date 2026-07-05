#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8885
NAME = "stage8885_registry_spine_reconciliation_after_authorization_reviews"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_AUTHORIZATION_REVIEWS_STAGE8885.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8882_tiny_structured_probe_execution_authorization_review.json",
    ROOT / "runs/summaries/stage8883_metadata_only_commit_inventory_preflight_design.json",
    ROOT / "runs/summaries/stage8884_no_execution_denoise_authorization_review.json",
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
    probe = cards[0].get("metrics", {}) if cards else {}
    inventory = cards[1].get("metrics", {}) if len(cards) > 1 else {}
    denoise = cards[2].get("metrics", {}) if len(cards) > 2 else {}
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
            "tiny_probe_review_passed": not bool(probe.get("review_failures")),
            "commit_inventory_repository_walks_now": inventory.get("repository_walks_now"),
            "commit_inventory_commit_reads_now": inventory.get("commit_reads_now"),
            "denoise_review_failures": denoise.get("review_failures"),
            "training_authorized": False,
            "model_execution_authorized_now": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
        },
        "decision": "Reconciled three requested authorization/design cards into registry/spine. All remain no-execution/no-training.",
        "next_best_step": "Choose one explicit branch next: issue a one-run Stage8890 execution ticket, keep inventory at design-only, or prepare a denoise one-run ticket. Do not run directly from these cards.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = not failures
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "historical_failed_rows": sum(1 for row in rows if row.get("passed") is not True), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8885 Registry Spine Reconciliation After Authorization Reviews",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Indexed:",
        "",
        "- Stage8882 tiny structured probe execution authorization review card",
        "- Stage8883 metadata-only commit inventory preflight design",
        "- Stage8884 no-execution denoise authorization review",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    marker = "## Stage8882-8885 Authorization Review Cards"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Three requested next-step review/design artifacts are recovered and indexed.",
            "",
            "- Stage8882 reviews the future Stage8890 tiny structured-policy probe plan. It passes but does not run or authorize execution by itself.",
            "- Stage8883 designs optional metadata-only commit inventory preflight with zero repository walks, zero commit reads, zero diff body reads, and zero training rows.",
            "- Stage8884 reviews denoise authorization prerequisites as no-execution/no-CE only. Denoise CE and runtime verifier execution remain closed.",
            "- Stage8885 reconciles these into registry/spine.",
            "",
            "No model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, controller merge, mining, memory writes, or promotion is authorized.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
