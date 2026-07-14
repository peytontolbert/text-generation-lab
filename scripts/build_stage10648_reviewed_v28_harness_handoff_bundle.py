#!/usr/bin/env python3
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
PACKAGE_DIR = ARTIFACTS / "stage10645_reviewed_v28_candidate_manifest_package"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_hash(payload: Any) -> str:
    return sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def main() -> None:
    headline = load_jsonl(PACKAGE_DIR / "headline_strict_eval.jsonl")
    rust_replacement = load_jsonl(PACKAGE_DIR / "rust_replacement_experiment_eval.jsonl")

    rows_by_lang: dict[str, list[dict[str, Any]]] = {}
    for row in headline:
        rows_by_lang.setdefault(str(row.get("language_family") or ""), []).append(row)
    for row in rust_replacement:
        rows_by_lang.setdefault(str(row.get("language_family") or ""), []).append(row)

    handoff_cells = []
    for language_family, rows in sorted(rows_by_lang.items()):
        rows = sorted(rows, key=lambda item: str(item.get("row_id") or ""))
        row_ids = [str(row.get("row_id") or "") for row in rows]
        lineage_hash = stable_hash(
            {
                "language_family": language_family,
                "row_ids": row_ids,
                "target_texts": [row.get("target_text") for row in rows],
                "source_bundle_ids": [row.get("source_bundle_id") for row in rows],
            }
        )
        source_id = f"reviewed_v28_harness_source::{language_family}::{lineage_hash[:20]}"
        task_pack_id = f"stage10648_reviewed_v28_locked_{lineage_hash[:20]}"
        cell_key = f"reviewed_full_product_harness::{language_family}::maintainer_choice"
        packet_dir = (
            ARTIFACTS
            / "stage10648_reviewed_v28_harness_handoff_bundle"
            / "review_packets"
            / cell_key.replace("::", "__")
        )
        rel_packet_dir = str(packet_dir.relative_to(ROOT))
        handoff_cells.append(
            {
                "cell_key": cell_key,
                "language_family": language_family,
                "skill_area": "maintainer_choice",
                "task_pack_id": task_pack_id,
                "source_id": source_id,
                "lineage_hash": lineage_hash,
                "row_count": len(rows),
                "slice_tags": sorted({str(row.get("slice_name") or "") for row in rows} | {language_family, "maintainer_choice"}),
                "artifact_paths": {
                    "packet_dir": rel_packet_dir,
                    "harness_run_id": f"{rel_packet_dir}/harness_run_id.txt",
                    "same_task_pack_as_gemma12b": f"{rel_packet_dir}/same_task_pack_as_gemma12b.json",
                    "tool_trace_spans": f"{rel_packet_dir}/tool_trace_spans.jsonl",
                    "verifier_results": f"{rel_packet_dir}/verifier_results.json",
                    "patch_minimality_or_abstain_scores": f"{rel_packet_dir}/patch_minimality_or_abstain_scores.json",
                    "anti_cheat_cards": f"{rel_packet_dir}/anti_cheat_cards.json",
                    "expert_maintainer_rubric_scores": f"{rel_packet_dir}/expert_maintainer_rubric_scores.json",
                },
            }
        )

    payload = {
        "stage": 10648,
        "stage_name": "stage10648_reviewed_v28_harness_handoff_bundle",
        "passed": True,
        "failures": [],
        "authority": {
            "model_execution_authorized_next": False,
            "gemma_execution_authorized_next": False,
            "harness_execution_authorized_next": True,
            "promotion_ready": False,
        },
        "metrics": {
            "handoff_cells": len(handoff_cells),
            "languages": sorted(rows_by_lang.keys()),
            "total_rows": sum(len(rows) for rows in rows_by_lang.values()),
        },
        "claim_boundary": [
            "This handoff bundle is for the reviewed v2.8 candidate maintainer-choice surface, not the old stage10081 locked edit-localization pack.",
            "Rows preserve the reviewed same-manifest benchmark boundary plus the explicit Rust replacement experiment slice.",
            "Any harness claim built from this handoff must stay separate from the legacy stage10081 canonical edit-localization claim path.",
        ],
        "handoff_cells": handoff_cells,
    }

    out_dir = ARTIFACTS / "stage10648_reviewed_v28_harness_handoff_bundle"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "reviewed_v28_harness_handoff_bundle.json", payload)
    print(out_dir / "reviewed_v28_harness_handoff_bundle.json")


if __name__ == "__main__":
    main()
