#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10837
NAME = "stage10837_hf_local_repaired_support_readiness"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "hf_local_repaired_support_readiness.json"
OUT_JSONL = OUT_DIR / "hf_local_repaired_support_targets.jsonl"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

SUCCESSOR_REQUEST = ARTIFACTS / "stage10835_hf_local_multitest_successor_request" / "hf_local_multitest_successor_request.json"
REPAIRED_PACKET = ARTIFACTS / "stage10499_hf_local_multitest_packet_repair" / "hf_local_multitest_repaired_packet.json"
REPAIRED_ROWS = ARTIFACTS / "stage10499_hf_local_multitest_packet_repair" / "hf_local_multitest_repaired_preview_rows.jsonl"
REPAIR_AUDIT = ARTIFACTS / "stage10500_hf_local_multitest_repair_audit" / "hf_local_multitest_repair_audit.json"
PROMOTABILITY_QUEUE = ARTIFACTS / "stage10758_python_residual_packet_promotability_audit" / "python_residual_packet_promotability_queue.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


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
    repaired_packet = load_json(REPAIRED_PACKET)
    repaired_rows = load_jsonl(REPAIRED_ROWS)
    repair_audit = load_json(REPAIR_AUDIT)
    promotability_rows = load_jsonl(PROMOTABILITY_QUEUE)

    promotability = next(
        row for row in promotability_rows
        if row.get("repaired_packet_bundle_id") == repaired_packet["bundle"]["bundle_id"]
    )

    target_rows: list[dict[str, Any]] = []
    for row in repaired_rows:
        target_rows.append(
            {
                "bundle_id": row["bundle_id"],
                "task_type": row["task_type"],
                "preview_answer_kind": row["preview_answer_kind"],
                "preview_gold_value": row["preview_gold_value"],
                "candidate_option_count": len((row.get("prompt_contract") or {}).get("candidate_options", [])),
                "verifier_option_count": len((row.get("prompt_contract") or {}).get("verifier_options", [])),
                "status": "train_support_materialization_ready",
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "hf_local_repaired_packet_ready_for_train_support_materialization",
        "claim_scope": [
            "Promote the repaired hf_local multitest packet into the current residual-support lineage using current stage numbering and current anti-cheat boundaries.",
            "Keep the packet train-support only while making its readiness for bounded materialization explicit.",
        ],
        "current_lane_alignment": {
            "successor_request_stage": successor_request["stage"],
            "repaired_packet_bundle_id": repaired_packet["bundle"]["bundle_id"],
            "support_only_root_from_request": successor_request["lane_decision"]["support_only_root"],
            "rebuild_required_root_from_request": successor_request["lane_decision"]["rebuild_required_root"],
            "current_packet_role": "hf_local_rebuild_lane_train_support_candidate",
        },
        "readiness_checks": {
            "prompt_target_leak_false": repair_audit["anti_cheat_checks"]["prompt_target_leak_false"],
            "candidate_options_opaque": repair_audit["anti_cheat_checks"]["candidate_options_opaque"],
            "verifier_options_opaque": repair_audit["anti_cheat_checks"]["verifier_options_opaque"],
            "verifier_role_summaries_present": repair_audit["anti_cheat_checks"]["verifier_role_summaries_present"],
            "verifier_option_count": repaired_packet["bundle"]["selected_tests_count"],
            "preview_rows_count": repaired_packet["bundle"]["preview_rows_count"],
        },
        "promotion_boundary": {
            "train_support_only": True,
            "strict_eval_promotable": False,
            "reason": [
                "The repaired packet is clean enough for bounded execution materialization.",
                "It remains a rebuilt support packet, not a fresh strict heldout root.",
                "The V3 CLI sibling is still weaker than an ideal third verifier family.",
            ],
        },
        "promotability_queue_alignment": promotability,
        "next_best_steps": [
            "Compile these five repaired preview rows into the next multilingual train-support manifest.",
            "Keep the stage10236 context-pack rows as parallel Python support, but use this packet for the actual verifier-target competition geometry.",
            "Do not upgrade the Python headline until a fresh strict verifier root beyond MirrorMind is added and scores cleanly.",
        ],
        "sources": {
            "successor_request": rel(SUCCESSOR_REQUEST),
            "repaired_packet": rel(REPAIRED_PACKET),
            "repaired_preview_rows": rel(REPAIRED_ROWS),
            "repair_audit": rel(REPAIR_AUDIT),
            "promotability_queue": rel(PROMOTABILITY_QUEUE),
        },
    }

    write_json(OUT_JSON, payload)
    write_jsonl(OUT_JSONL, target_rows)
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
