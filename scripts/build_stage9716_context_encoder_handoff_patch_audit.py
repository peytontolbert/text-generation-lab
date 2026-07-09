#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

import build_stage9715_software_maintenance_context_sufficiency_audit as stage9715

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9716
NAME = "stage9716_context_encoder_handoff_patch_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "context_encoder_handoff_patch_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CONTEXT_ENCODER_HANDOFF_PATCH_STAGE9716.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    trainer_default = stage9715.trainer_default_max_encoder_tokens()
    build_batch_default = stage9715.build_batch_default_max_encoder_tokens()
    serializes_context = stage9715.row_text_serializes_context_rows()

    resolved_contracts = {
        "row_text_serializes_context_rows": serializes_context is True,
        "trainer_default_max_encoder_tokens_not_toy": trainer_default is not None and trainer_default >= 2048,
        "build_batch_default_max_encoder_tokens_not_toy": build_batch_default is not None and build_batch_default >= 2048,
    }
    remaining_blockers = []
    long_context_cards = [stage9715.context_pack_card(stage9715.LONG_CONTEXT_ROWS), stage9715.context_pack_card(stage9715.EXTERNAL_COMMIT_PACK_ROWS)]
    manifest_cards = [stage9715.manifest_context_card(stage9715.SYMBOL_BINDING_MANIFEST), stage9715.manifest_context_card(stage9715.FIVE_WAY_SYMBOL_BINDING)]
    if any(not card.get("context_roles_preserved") for card in long_context_cards):
        remaining_blockers.append("long_context_pack_training_rows_drop_context_roles")
    if any(not card.get("first_context_local_evidence_first") for card in long_context_cards):
        remaining_blockers.append("long_context_pack_first_context_not_local_evidence")
    if any(card.get("context_rows_present") == 0 for card in manifest_cards):
        remaining_blockers.append("active_symbol_binding_manifests_have_no_context_rows")

    passed = all(resolved_contracts.values())
    next_step = "Patch the context compiler/materializer so maintenance manifests preserve role-bearing, local-first, task-closed context_rows; then rerun Stage9715 and rebuild symbol-binding rows with raw context evidence."
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": passed,
        "quality_passed": False,
        "promotion_ready": False,
        "resolved_contracts": resolved_contracts,
        "remaining_context_blockers": remaining_blockers,
        "trainer_default_max_encoder_tokens": trainer_default,
        "build_batch_default_max_encoder_tokens": build_batch_default,
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "name": NAME,
        "passed": passed,
        "quality_passed": False,
        "promotion_ready": False,
        "created_at_unix": int(time.time()),
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "metrics": {
            "resolved_contract_count": sum(1 for value in resolved_contracts.values() if value),
            "remaining_context_blocker_count": len(remaining_blockers),
            "trainer_default_max_encoder_tokens": trainer_default,
            "row_text_serializes_context_rows": serializes_context,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage9716 Context Encoder Handoff Patch",
            "",
            "Stage9716 records the trainer handoff fix from the Stage9715 context sufficiency audit.",
            "",
            "## Resolved",
            "",
            f"- `_row_text` serializes `context_rows`: `{serializes_context}`",
            f"- Trainer default max encoder tokens: `{trainer_default}`",
            f"- `build_batch` default max encoder tokens: `{build_batch_default}`",
            "",
            "## Remaining Blockers",
            "",
            *(f"- `{blocker}`" for blocker in remaining_blockers),
            "",
            "## Next",
            "",
            next_step,
            "",
            "No model execution, runtime, decoder CE training, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, or promotion was authorized.",
            "",
        ]),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
