#!/usr/bin/env python3
"""Build Stage12257 inventory snapshot drift audit.

Documents that Stage12255 mixed a stale parent inventory with a live filesystem
scan. This invalidates Stage12255 as an attachment base and defines the rebuild
sequence for a coherent snapshot.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12257_inventory_snapshot_drift_audit"


def load_json(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    if not path.exists():
        return {"_missing": rel}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def main() -> int:
    stage12255 = load_json("runs/summaries/stage12255_physical_session_path_hash_rehydrator.json")
    stage12256 = load_json("runs/summaries/stage12256_live_physical_session_inventory_refresh.json")
    old_counts = load_json("runs/local/artifacts/session_like_source_inventory_real/session_inventory_counts_by_root.json")
    drift = stage12256.get("drift_vs_previous_inventory") or {}
    live_root_card = stage12256.get("root_card") or {}

    audit = {
        "stage": STAGE,
        "artifact_type": "inventory_snapshot_drift_audit",
        "decision": "stage12255_invalid_for_attachment_due_to_mixed_stale_inventory_and_live_scan",
        "training_allowed": False,
        "claim_boundary": (
            "Audit/control artifact only. It invalidates a parent-index artifact for attachment use, "
            "admits no roots, and authorizes no training."
        ),
        "finding": {
            "live_codex_session_count": ((stage12256.get("counts_by_root") or {}).get("codex_sessions") or {}).get("file_count"),
            "old_codex_session_count": (old_counts.get("codex_sessions") or {}).get("file_count"),
            "live_total_files": live_root_card.get("total_files"),
            "old_total_files": 1739,
            "drift_vs_previous_inventory": drift,
            "stage12255_decision": stage12255.get("decision"),
            "stage12255_coverage_pass": (stage12255.get("coverage") or {}).get("coverage_pass"),
        },
        "root_cause": [
            "The old no-content inventory was internally consistent at 1,739 files, including 758 Codex session JSONLs.",
            "The live filesystem now has 1,301 files, including 279 Codex session JSONLs and 1,019 Cursor project files.",
            "Stage12255 mixed old Stage12253 parent records with a fresh live scan, then minted physical_source_ids for live files missing from the stale parent index.",
            "That artifact is useful as a drift detector, but not valid as the derivative attachment base.",
        ],
        "valid_interpretation": (
            "We currently have 279 live Codex session files under /home/peyton/.codex/sessions. "
            "We also have older derived artifacts from a previous 758-file snapshot. Those are not the same inventory state."
        ),
        "required_fix": [
            "Do not use Stage12255 for derivative attachment.",
            "Regenerate physical parent inventory from the live filesystem snapshot.",
            "Rerun physical source indexer from the refreshed inventory, not the stale one.",
            "Rerun path-hash rehydrator against that same refreshed parent index immediately.",
            "Modify future rehydrators to report live_uninventoried and inventory_missing_from_live instead of minting synthetic IDs into the parent namespace.",
            "If attaching derivatives from the old July 8 inventory, restore the exact old physical snapshot or treat old derivatives as historical/unattached views.",
        ],
        "next_stage_sequence": [
            {
                "stage": "stage12258_live_inventory_snapshot_indexer",
                "purpose": "Use Stage12256 live inventory records as the canonical parent snapshot and rebuild physical_source_records from it.",
                "training_allowed": False,
            },
            {
                "stage": "stage12259_live_snapshot_derivative_attacher",
                "purpose": "Attach current derivative pools to the live parent snapshot; report old-snapshot derivatives separately as historical/unattached.",
                "training_allowed": False,
            },
            {
                "stage": "stage12260_historical_derivative_salvage_plan",
                "purpose": "Decide whether older 758-file-snapshot derivatives can be salvaged from artifact contents or must remain train-only/historical.",
                "training_allowed": False,
            },
        ],
        "quality_rule": (
            "Parent inventory, path-hash attachment, derivative attachment, and root admission must all use the same snapshot_id."
        ),
    }

    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", audit)
    write_json(out_dir / "inventory_snapshot_drift_audit.json", audit)
    md = f"""# Stage12257 Inventory Snapshot Drift Audit

## Decision

`{audit["decision"]}`

No training is allowed.

## Answer

The live filesystem currently has `{audit["finding"]["live_codex_session_count"]}` Codex session JSONLs. The older inventory had `{audit["finding"]["old_codex_session_count"]}`. Those are different snapshots.

Stage12255 is invalid for derivative attachment because it mixed the old parent index with a live scan.

## Rule Going Forward

`snapshot_id` must match across:

- parent inventory,
- path-hash index,
- derivative attachment,
- root projection,
- admission.

If it does not match, fail closed.
"""
    write_text(out_dir / "INVENTORY_SNAPSHOT_DRIFT_AUDIT_STAGE12257.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "INVENTORY_SNAPSHOT_DRIFT_AUDIT_STAGE12257.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
