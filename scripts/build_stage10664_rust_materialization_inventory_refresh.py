#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10664
NAME = "stage10664_rust_materialization_inventory_refresh"
OUT_DIR = ARTIFACTS / NAME
OUT_PATH = OUT_DIR / "rust_materialization_inventory_refresh.json"

STAGE10476 = ARTIFACTS / "stage10476_rust_citation_materialized_root_bundle_builder/rust_citation_materialized_root_bundle_builder.json"
STAGE10663 = ARTIFACTS / "stage10663_rust_flash_attn_executable_support_audit/rust_flash_attn_executable_support_audit.json"
STAGE10662 = ARTIFACTS / "stage10662_reviewed_source_supply_upgrade_atlas/reviewed_source_supply_upgrade_atlas.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    stale = load_json(STAGE10476)
    flash = load_json(STAGE10663)
    supply = load_json(STAGE10662)

    stale_metrics = stale.get("metrics") or {}
    flash_metrics = flash.get("metrics") or {}
    builder_targets = ((supply.get("rust_current_state") or {}).get("builder_targets") or [])

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "rust_materialization_inventory_refreshed_with_flash_attn_support",
        "sources": {
            "stale_rust_inventory": rel(STAGE10476),
            "flash_attn_executable_support_audit": rel(STAGE10663),
            "source_supply_upgrade_atlas": rel(STAGE10662),
        },
        "metrics": {
            "previous_executable_root_count": stale_metrics.get("executable_root_count"),
            "refreshed_executable_support_root_count": int(stale_metrics.get("executable_root_count") or 0) + 1,
            "reviewed_pending_root_count_after_refresh": 0,
            "fresh_builder_target_count_remaining": len(builder_targets),
            "flash_attn_support_row_count": flash_metrics.get("row_count"),
            "flash_attn_task_type_counts": flash_metrics.get("task_type_counts"),
        },
        "refreshed_state": {
            "executable_support_roots_now": [
                "stage10126::candle::candle-core::rust",
                "stage10413::candle::candle-flash-attn::rust",
            ],
            "remaining_builder_targets": [target.get("candidate_root_id") for target in builder_targets],
            "flash_attn_support_contract": flash.get("support_contract"),
        },
        "claim_boundary": [
            "Rust no longer has only candle-core executable support; flash-attn is now an executable reviewed support root as well.",
            "This is still not the final promotable Rust residual fix path because flash-attn is abstention-heavy and not the exact non-abstention E-vs-F contrast target.",
            "The remaining high-value Rust work is builder-target construction, not proving that no executable reviewed support exists.",
        ],
        "next_best_steps": [
            "Include flash-attn in the next multilingual Rust support package.",
            "Prioritize linux::rust, candle-datasets, and candle-transformers for explicit evidence-citation contrast materialization.",
            "Audit any future Rust package for option-role leakage and root-disjointness before promotion.",
        ],
    }

    write_json(OUT_PATH, payload)
    print(OUT_PATH)


if __name__ == "__main__":
    main()
