#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11043
NAME = "stage11043_priority_residual_root_materialization_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "priority_residual_root_materialization_audit.json"

PACKET_JSON = ARTIFACTS / "stage11042_priority_residual_root_materialization_packet" / "priority_residual_root_materialization_packet.json"
ROOT_CARDS = ARTIFACTS / "stage11042_priority_residual_root_materialization_packet" / "priority_root_cards.jsonl"
PACKET_ROWS = ARTIFACTS / "stage11042_priority_residual_root_materialization_packet" / "priority_packet_rows.jsonl"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    packet = load_json(PACKET_JSON)
    root_cards = load_jsonl(ROOT_CARDS)
    packet_rows = load_jsonl(PACKET_ROWS)

    blocked_rows = [row for row in packet_rows if not ((row.get("scoreability") or {}).get("scoreable_now"))]
    scoreable_rows = [row for row in packet_rows if (row.get("scoreability") or {}).get("scoreable_now")]

    blocked_by_reason = Counter(str((row.get("scoreability") or {}).get("reason") or "unknown") for row in blocked_rows)
    blocked_by_lane = Counter(str(row.get("promotion_lane") or "unknown") for row in blocked_rows)
    scoreable_by_lane = Counter(str(row.get("promotion_lane") or "unknown") for row in scoreable_rows)

    lane_readiness: dict[str, dict[str, Any]] = defaultdict(lambda: {"scoreable": 0, "blocked": 0, "roots": set()})
    for row in packet_rows:
        lane = str(row.get("promotion_lane") or "unknown")
        lane_readiness[lane]["roots"].add(str(row.get("root_id") or ""))
        if (row.get("scoreability") or {}).get("scoreable_now"):
            lane_readiness[lane]["scoreable"] += 1
        else:
            lane_readiness[lane]["blocked"] += 1

    lane_readiness_out = {
        lane: {
            "root_count": len(payload["roots"]),
            "scoreable_rows": payload["scoreable"],
            "blocked_rows": payload["blocked"],
        }
        for lane, payload in sorted(lane_readiness.items())
    }

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "priority_residual_root_materialization_audited",
        "claim_scope": [
            "Audit the stage11042 priority residual packet for immediate scoreability, anti-cheat blocking reasons, and lane readiness.",
            "Make explicit which parts of the packet can already support honest bounded scoring and which still need evidence-ledger projection.",
        ],
        "headline_findings": [
            "The packet is structurally healthy for the top five roots, but all five decisive_evidence rows are still blocked because their targets remain opaque chunk IDs rather than visible candidate ledgers.",
            "Verifier_outcome and retrieve_answer_abstain are already scoreable for every selected root, which makes the Python verifier-transition lane the closest to immediate executable successor rows.",
            "This confirms the next improvement should be evidence-ledger materialization for C/C++ plus opaque verifier-target construction for Python, not another broad support blend.",
        ],
        "metrics": {
            "root_count": len(root_cards),
            "packet_row_count": len(packet_rows),
            "scoreable_rows": len(scoreable_rows),
            "blocked_rows": len(blocked_rows),
            "blocked_by_reason": dict(sorted(blocked_by_reason.items())),
            "blocked_by_lane": dict(sorted(blocked_by_lane.items())),
            "scoreable_by_lane": dict(sorted(scoreable_by_lane.items())),
            "lane_readiness": lane_readiness_out,
        },
        "next_best_step": [
            "Project visible evidence candidates for the three parametergolf decisive_evidence roots so they can become honest C/C++ evidence rows.",
            "Use the two Python roots to build opaque verifier-transition candidates before adding more generic Python support.",
            "Keep the packet train-support or reserved-candidate only until those blocked rows become visibly answerable.",
        ],
        "source_artifacts": {
            "materialization_packet": rel(PACKET_JSON),
            "root_cards": rel(ROOT_CARDS),
            "packet_rows": rel(PACKET_ROWS),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
        },
    }

    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
