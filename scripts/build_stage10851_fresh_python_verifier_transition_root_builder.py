#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10851
NAME = "stage10851_fresh_python_verifier_transition_root_builder"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "fresh_python_verifier_transition_root_builder.json"
ROOTS_JSONL = OUT_DIR / "fresh_python_verifier_transition_roots.jsonl"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

QUEUE_JSON = ARTIFACTS / "stage10850_residual_frontier_root_build_queue" / "residual_frontier_root_build_queue.json"
CONTRAST_SUMMARY = ARTIFACTS / "stage10715_fresh_python_verifier_contrast_builder" / "fresh_python_verifier_contrast_builder.json"
GEOMETRY_SUMMARY = ARTIFACTS / "stage10756_python_verifier_geometry_upgrade_scaffolds" / "python_verifier_geometry_upgrade_scaffolds.json"
QUEUE_ALIGNED_PACKET = ARTIFACTS / "stage10813_python_queue_aligned_admission" / "review_packets" / "stage10236__localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662__python"
GEOMETRY_PACKET_DIR = ARTIFACTS / "stage10756_python_verifier_geometry_upgrade_scaffolds" / "review_packets"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def packet_record(packet_dir: Path, lane: str, readiness: str, missing: list[str], source_stage: int) -> dict[str, Any]:
    bundle = load_json(packet_dir / "fresh_python_bundle_preview.json")
    anti = load_json(packet_dir / "anti_cheat_review_card.json")
    gold = load_json(packet_dir / "perspective_gold_adjudication.json")
    perspective_rows = bundle.get("perspective_rows") or []
    return {
        "bundle_id": str(bundle.get("bundle_id") or bundle.get("root_id") or packet_dir.name),
        "packet_dir": rel(packet_dir),
        "lane": lane,
        "readiness": readiness,
        "source_stage": source_stage,
        "repo_id": str(bundle.get("repo_id") or packet_dir.name.split("__", 1)[0]),
        "language_family": "python",
        "selected_test_count": len(bundle.get("selected_tests") or []),
        "perspective_row_count": len(perspective_rows),
        "maintainer_visible_evidence_keys": sorted((bundle.get("maintainer_visible_evidence") or {}).keys()),
        "anti_cheat_status": anti.get("status"),
        "gold_status": gold.get("status"),
        "missing_fields": missing,
        "required_next_action": "materialize richer verifier-transition evidence and re-adjudicate",
    }


def main() -> None:
    queue = load_json(QUEUE_JSON)
    contrast = load_json(CONTRAST_SUMMARY)
    geometry = load_json(GEOMETRY_SUMMARY)

    records = [
        packet_record(
            QUEUE_ALIGNED_PACKET,
            lane="queue_aligned_context_pack",
            readiness="train_support_packetized_but_not_transition_complete",
            missing=[
                "B/C/G-style transition supervision at scale",
                "fresh heldout root assignment for verifier transitions",
                "multi-option transition labels beyond file-choice semantics",
            ],
            source_stage=10813,
        )
    ]

    for packet_dir in sorted(GEOMETRY_PACKET_DIR.iterdir()):
        if not packet_dir.is_dir():
            continue
        records.append(
            packet_record(
                packet_dir,
                lane="geometry_upgrade_scaffold",
                readiness="scaffold_only",
                missing=[
                    "real prompt-visible verifier/test evidence for 3+ plausible selected tests",
                    "no gold test path leakage before options",
                    "refreshed perspective gold adjudication after geometry upgrade",
                ],
                source_stage=10756,
            )
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "fresh_python_verifier_transition_root_manifest_ready",
        "headline_findings": [
            "There are still zero promotable singleton Python verifier roots from the older contrast miner.",
            "Python does have packetized richer-geometry candidates in queue-aligned and geometry-upgrade form.",
            "The next honest Python move is to complete verifier-transition materialization on these packetized roots, not to rerun another residual probe.",
        ],
        "authoritative_inputs": {
            "root_build_queue": rel(QUEUE_JSON),
            "contrast_summary": rel(CONTRAST_SUMMARY),
            "geometry_summary": rel(GEOMETRY_SUMMARY),
        },
        "source_gap_readout": {
            "promotable_singleton_root_count": contrast["promotable_singleton_root_count"],
            "diagnostic_multi_target_root_count": contrast["diagnostic_multi_target_root_count"],
            "geometry_scaffold_targets": geometry["scaffold_targets"],
        },
        "records": records,
        "next_best_step": "Use these packetized roots to build stage10853 residual-root admission with explicit transition labels and leak-clean verifier competition.",
    }

    write_jsonl(ROOTS_JSONL, records)
    write_json(OUT_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "root_count": len(records),
            "artifact": rel(OUT_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
