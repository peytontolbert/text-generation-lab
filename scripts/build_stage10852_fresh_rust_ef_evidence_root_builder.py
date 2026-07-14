#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10852
NAME = "stage10852_fresh_rust_ef_evidence_root_builder"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "fresh_rust_ef_evidence_root_builder.json"
ROOTS_JSONL = OUT_DIR / "fresh_rust_ef_evidence_roots.jsonl"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

QUEUE_JSON = ARTIFACTS / "stage10850_residual_frontier_root_build_queue" / "residual_frontier_root_build_queue.json"
SCAFFOLD_SUMMARY = ARTIFACTS / "stage10674_rust_fresh_review_packet_scaffolds" / "rust_fresh_review_packet_scaffolds.json"
LINUX_ADJUDICATION = ARTIFACTS / "stage10680_linux_rust_ai_adjudication" / "linux_rust_ai_adjudication.json"
CANDLE_DATASETS = ARTIFACTS / "stage10686_candle_datasets_ai_adjudication" / "candle_datasets_ai_adjudication.json"
CANDLE_TRANSFORMERS_BLOCKER = ARTIFACTS / "stage10817_candle_transformers_verifier_anchor_blocker" / "candle_transformers_verifier_anchor_blocker.json"
PACKETS_DIR = ARTIFACTS / "stage10674_rust_fresh_review_packet_scaffolds" / "review_packets"
ADJUDICATED_PACKETS_DIR = ARTIFACTS / "stage10686_candle_datasets_ai_adjudication" / "review_packets"


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


def packet_record(packet_dir: Path, readiness: str, missing: list[str], note: str) -> dict[str, Any]:
    bundle = load_json(packet_dir / "fresh_rust_bundle_preview.json")
    anti = load_json(packet_dir / "anti_cheat_review_card.json")
    gold = load_json(packet_dir / "perspective_gold_adjudication.json")
    return {
        "bundle_id": str(bundle.get("bundle_id") or bundle.get("root_id") or packet_dir.name),
        "packet_dir": rel(packet_dir),
        "repo_id": str(bundle.get("repo_id") or packet_dir.name),
        "language_family": "rust",
        "readiness": readiness,
        "selected_test_count": len(bundle.get("selected_tests") or []),
        "maintainer_visible_evidence_keys": sorted((bundle.get("maintainer_visible_evidence") or {}).keys()),
        "anti_cheat_status": anti.get("status"),
        "gold_status": gold.get("status"),
        "missing_fields": missing,
        "note": note,
    }


def main() -> None:
    queue = load_json(QUEUE_JSON)
    scaffold = load_json(SCAFFOLD_SUMMARY)
    linux = load_json(LINUX_ADJUDICATION)
    datasets = load_json(CANDLE_DATASETS)
    transformers = load_json(CANDLE_TRANSFORMERS_BLOCKER)

    records = [
        packet_record(
            PACKETS_DIR / "linux__rust",
            readiness="train_support_admitted",
            missing=[
                "fresh heldout E/F evidence-root counterpart",
                "explicit E/F role coverage beyond current train-support framing",
            ],
            note=linux["decision"],
        ),
        packet_record(
            ADJUDICATED_PACKETS_DIR / "candle__candle-datasets",
            readiness="train_support_admitted",
            missing=[
                "explicit E/F evidence-role compilation into bounded rows",
                "fresh heldout E/F evidence-root counterpart",
            ],
            note=datasets["decision"],
        ),
        packet_record(
            PACKETS_DIR / "candle__candle-transformers",
            readiness="blocked_on_verifier_anchor",
            missing=transformers["blocking_evidence"]["required_recovered_fields"],
            note=transformers["decision"],
        ),
    ]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "fresh_rust_ef_evidence_root_manifest_ready",
        "headline_findings": [
            "Linux Rust is admitted for train-support only but is not enough by itself for the fresh Rust residual lane.",
            "Candle-datasets is already AI-adjudicated for train-support use and is the strongest current non-tokenizers Rust support root.",
            "Candle-transformers remains blocked on verifier-anchor recovery and should not be treated as ready for scoring or support admission.",
        ],
        "authoritative_inputs": {
            "root_build_queue": rel(QUEUE_JSON),
            "scaffold_summary": rel(SCAFFOLD_SUMMARY),
            "linux_adjudication": rel(LINUX_ADJUDICATION),
            "candle_datasets_packet": rel(CANDLE_DATASETS),
            "candle_transformers_blocker": rel(CANDLE_TRANSFORMERS_BLOCKER),
        },
        "scaffold_targets": scaffold["scaffold_targets"],
        "records": records,
        "next_best_step": "Use Linux and candle-datasets as train-support Rust roots, and recover a second non-tokenizers anchored Rust heldout root before the next multilingual residual package.",
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
