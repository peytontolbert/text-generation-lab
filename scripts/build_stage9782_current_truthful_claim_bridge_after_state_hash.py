#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9782
NAME = "stage9782_current_truthful_claim_bridge_after_state_hash"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
LEDGER = OUT_DIR / "current_truthful_claim_bridge_after_state_hash.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_TRUTHFUL_CLAIM_BRIDGE_AFTER_STATE_HASH_STAGE9782.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SOURCE_BRIDGE = ROOT / "runs/local/artifacts/stage9779_current_truthful_standalone_claim_bridge/current_truthful_standalone_claim_bridge.json"
HASH_CARD = ROOT / "runs/local/artifacts/stage9781_winning_edit_localization_state_hash/winning_edit_localization_state_hash.json"
PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def update_registry(summary: dict[str, Any]) -> None:
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
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_bridge() -> dict[str, Any]:
    source = load_json(SOURCE_BRIDGE)
    hash_card = load_json(HASH_CARD)
    packet_index = {str(packet.get("cell_key") or ""): packet for packet in load_jsonl(PACKETS)}
    records = source.get("records") if isinstance(source.get("records"), list) else []
    refreshed: list[dict[str, Any]] = []
    refreshed_cells = 0
    failures: list[str] = []

    if source.get("passed") is not True:
        failures.append("stage9779_not_passed")
    if hash_card.get("passed") is not True:
        failures.append("stage9781_not_passed")

    for row in records:
        updated = copy.deepcopy(row)
        cell_key = str(updated.get("cell_key") or "")
        if cell_key in {f"standalone_100m_weights::{lang}::edit_localization" for lang in LANGS}:
            packet = packet_index.get(cell_key)
            checkpoint_rel = ((packet.get("review_packet_paths") or {}).get("frozen_export_or_checkpoint_hash")) if isinstance(packet, dict) else None
            if not checkpoint_rel:
                failures.append(f"missing_checkpoint_path:{cell_key}")
            else:
                updated["attached_evidence"] = list(updated.get("attached_evidence") or []) + [
                    {
                        "kind": "frozen_state_hash_support",
                        "stage": 9781,
                        "path": str(Path(checkpoint_rel)),
                        "supports": ["frozen_export_or_checkpoint_hash"],
                        "quality_passed": True,
                        "claim_sufficient": False,
                        "details": {
                            "state_sha256": hash_card.get("state_sha256"),
                            "manifest_sha256": hash_card.get("manifest_sha256"),
                            "selected_step": hash_card.get("selected_step"),
                            "best_state_restored": hash_card.get("best_state_restored"),
                            "strict_exact": hash_card.get("strict_exact"),
                        },
                        "why_not_claim_sufficient": [
                            "no_expert_maintainer_rubric_scores",
                            "no_cell_specific_anti_cheat_cards",
                        ],
                    }
                ]
                updated["missing_required_evidence"] = [
                    item for item in list(updated.get("missing_required_evidence") or [])
                    if item != "frozen_export_or_checkpoint_hash"
                ]
                updated["blockers"] = [
                    blocker for blocker in list(updated.get("blockers") or [])
                    if blocker != "missing_required_evidence:frozen_export_or_checkpoint_hash"
                ]
                refreshed_cells += 1
        refreshed.append(updated)

    winning_rows = [
        row for row in refreshed
        if row.get("cell_key") in {f"standalone_100m_weights::{lang}::edit_localization" for lang in LANGS}
    ]
    if refreshed_cells != 4:
        failures.append("refreshed_cells_not_4")
    if any(row.get("missing_required_evidence") != ["expert_maintainer_rubric_scores", "anti_cheat_cards"] for row in winning_rows):
        failures.append("winning_rows_missing_evidence_not_reduced_to_review_only")

    return {
        "passed": not failures,
        "failures": failures,
        "records": refreshed,
        "metrics": {
            "records": len(refreshed),
            "refreshed_cells": refreshed_cells,
            "winning_cells_with_hash_evidence": len(winning_rows),
            "winning_cells_missing_review_only": sum(
                1 for row in winning_rows
                if row.get("missing_required_evidence") == ["expert_maintainer_rubric_scores", "anti_cheat_cards"]
            ),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_bridge()
    LEDGER.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use the refreshed bridge to focus human expert-maintainer rubric and anti-cheat review on the four winning edit-localization cells, "
        "because checkpoint/hash evidence is now attached and only review judgments remain missing there."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "ledger": str(LEDGER.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Refreshed the current truthful claim bridge after Stage9781 so the four winning edit-localization cells no longer treat checkpoint/hash evidence as missing.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9782 Current Truthful Claim Bridge After State Hash",
                "",
                f"Passed: `{summary['passed']}`",
                f"Refreshed cells: `{built['metrics']['refreshed_cells']}`",
                f"Winning cells with hash evidence: `{built['metrics']['winning_cells_with_hash_evidence']}`",
                f"Winning cells missing review only: `{built['metrics']['winning_cells_missing_review_only']}`",
                "",
                "This stage updates the current standalone claim view after the Stage9781 frozen-state hash run.",
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if not built["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
