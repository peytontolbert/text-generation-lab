#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10838
NAME = "stage10838_linux_rust_support_readiness"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "linux_rust_support_readiness.json"
OUT_JSONL = OUT_DIR / "linux_rust_support_targets.jsonl"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

SUCCESSOR_REQUEST = ARTIFACTS / "stage10836_rust_anchor_materialization_request" / "rust_anchor_materialization_request.json"
ADJUDICATION = ARTIFACTS / "stage10680_linux_rust_ai_adjudication" / "linux_rust_ai_adjudication.json"
ADJ_PACKET = ARTIFACTS / "stage10680_linux_rust_ai_adjudication" / "review_packets" / "linux__rust" / "fresh_rust_bundle_preview.json"
ADJ_ANTI_CHEAT = ARTIFACTS / "stage10680_linux_rust_ai_adjudication" / "review_packets" / "linux__rust" / "anti_cheat_review_card.json"
ADJ_GOLD = ARTIFACTS / "stage10680_linux_rust_ai_adjudication" / "review_packets" / "linux__rust" / "perspective_gold_adjudication.json"


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


def main() -> None:
    successor_request = load_json(SUCCESSOR_REQUEST)
    adjudication = load_json(ADJUDICATION)
    packet = load_json(ADJ_PACKET)
    anti_cheat = load_json(ADJ_ANTI_CHEAT)
    gold = load_json(ADJ_GOLD)

    targets: list[dict[str, Any]] = []
    for row in packet.get("perspective_rows") or []:
        targets.append(
            {
                "bundle_id": packet["bundle_id"],
                "perspective": row["perspective"],
                "selected_tests_count": len((row.get("prompt_contract") or {}).get("selected_tests", [])),
                "candidate_paths_count": len((row.get("prompt_contract") or {}).get("candidate_paths", [])),
                "status": "train_support_ready_not_headline_promotable",
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "linux_rust_packet_ready_for_current_train_support_lineage",
        "claim_scope": [
            "Promote the adjudicated Linux Rust packet into the current residual-support lineage using current stage numbering and current Rust anchor priorities.",
            "Keep the packet train-support only while preserving the requirement for a second independent verifier-anchored Rust root.",
        ],
        "current_lane_alignment": {
            "successor_request_stage": successor_request["stage"],
            "requested_priority_targets": successor_request["lane_decision"]["selected_builder_targets"],
            "adjudicated_bundle_id": adjudication["bundle_id"],
            "selected_test": adjudication["selected_test"],
            "target_path": adjudication["target_path"],
            "current_packet_role": "fresh_rust_anchor_recovered_train_support_candidate",
        },
        "readiness_checks": {
            "ai_adjudication_complete": adjudication["passed"],
            "train_support_only": adjudication["train_support_only"],
            "verifier_anchor_present": not packet["claim_boundary"]["verifier_anchor_still_missing"],
            "selected_tests_count": len((packet.get("perspective_rows") or [])[0]["prompt_contract"]["selected_tests"]) if packet.get("perspective_rows") else 0,
            "anti_cheat_admissible_for_same_surface_comparison": anti_cheat["admissible_for_same_surface_comparison"],
            "gold_rows_filled": all(
                row.get("gold_answer_kind") != "TODO_AFTER_MATERIALIZATION"
                for row in gold.get("perspective_gold_answers", [])
            ),
        },
        "promotion_boundary": {
            "train_support_only": True,
            "strict_eval_promotable": False,
            "reason": adjudication["claim_boundary"],
        },
        "remaining_rust_gap": [
            "tokenizers::bindings/node remains the highest-priority unresolved promotable target",
            "candle::candle-transformers still lacks a recovered verifier/test anchor",
            "a second independent verifier-anchored Rust root is still needed for stronger multilingual claim support",
        ],
        "next_best_steps": [
            "Compile this Linux Rust packet into the next multilingual train-support manifest.",
            "Keep flash-attn as parallel Rust support, but do not treat either packet as the final promotable Rust residual fix.",
            "Continue anchor recovery for tokenizers::bindings/node and candle::candle-transformers.",
        ],
        "sources": {
            "successor_request": rel(SUCCESSOR_REQUEST),
            "adjudication": rel(ADJUDICATION),
            "preview_bundle": rel(ADJ_PACKET),
            "anti_cheat_review_card": rel(ADJ_ANTI_CHEAT),
            "perspective_gold_adjudication": rel(ADJ_GOLD),
        },
    }

    write_json(OUT_JSON, payload)
    write_jsonl(OUT_JSONL, targets)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "artifact": rel(OUT_JSON),
            "targets": rel(OUT_JSONL),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
