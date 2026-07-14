#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10836
NAME = "stage10836_rust_anchor_materialization_request"
OUT_DIR = ARTIFACTS / NAME
REQUEST_JSON = OUT_DIR / "rust_anchor_materialization_request.json"
TARGETS_JSONL = OUT_DIR / "rust_anchor_materialization_targets.jsonl"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

EXECUTION_PACKET = ARTIFACTS / "stage10834_residual_expansion_execution_packet" / "residual_expansion_execution_packet.json"
SUPPLY_MANIFEST = ARTIFACTS / "stage10822_residual_lane_fresh_root_supply_manifest" / "residual_lane_fresh_root_supply_manifest.json"
SUPPLY_TARGETS = ARTIFACTS / "stage10822_residual_lane_fresh_root_supply_manifest" / "residual_lane_fresh_root_targets.jsonl"
PREDECESSOR_REQUEST = ARTIFACTS / "stage10441_rust_evidence_citation_fresh_builder_request" / "rust_evidence_citation_fresh_builder_request.json"
INVENTORY_REFRESH = ARTIFACTS / "stage10664_rust_materialization_inventory_refresh" / "rust_materialization_inventory_refresh.json"
SCORER_AUDIT = ARTIFACTS / "stage10830_evidence_role_probe_audit" / "evidence_role_probe_audit.json"


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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    execution_packet = load_json(EXECUTION_PACKET)
    supply_manifest = load_json(SUPPLY_MANIFEST)
    supply_targets = load_jsonl(SUPPLY_TARGETS)
    predecessor = load_json(PREDECESSOR_REQUEST)
    inventory_refresh = load_json(INVENTORY_REFRESH)
    scorer_audit = load_json(SCORER_AUDIT)

    rust_miss = next(
        miss
        for miss in (execution_packet.get("current_frontier") or {}).get("strict_misses", [])
        if miss.get("language_family") == "rust"
    )
    selected_targets = []
    for target_id in (execution_packet.get("rust_lane") or {}).get("selected_builder_targets", []):
        row = next(
            candidate for candidate in supply_targets
            if candidate.get("lane") == "rust_evidence_citation"
            and candidate.get("candidate_root_id") == target_id
        )
        selected_targets.append(row)

    request_targets: list[dict[str, Any]] = []
    for priority, row in enumerate(selected_targets, start=1):
        request_targets.append(
            {
                "priority_order": priority,
                "candidate_root_id": row["candidate_root_id"],
                "repo_id": row.get("repo_id"),
                "status": row.get("status"),
                "competition_geometries": row.get("competition_geometries", []),
                "required_builder_delta": row.get("required_builder_delta", []),
                "selected_test_or_verifier_anchor_required": True,
                "diagnostic_only_until_reviewed": True,
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "rust_anchor_materialization_request_ready",
        "claim_scope": [
            "Convert the stage10834 residual packet into a concrete Rust anchor-materialization request for the remaining evidence-citation blocker.",
            "Prioritize fresh rooted evidence-citation contrast over scorer patching, while keeping flash-attn available only as support material.",
        ],
        "current_frontier_context": {
            "strict_exact": (execution_packet.get("current_frontier") or {}).get("strict_exact"),
            "rust_strict_miss": rust_miss,
            "strict_miss_set_unchanged": (execution_packet.get("current_frontier") or {}).get("strict_miss_set_unchanged"),
            "headline_reason": "the full-vocab model already surfaces E, but the bounded evidence-citation decision remains wrong on the strict tokenizers row",
        },
        "lane_decision": {
            "support_only_root": (execution_packet.get("rust_lane") or {}).get("support_only_root"),
            "selected_builder_targets": (execution_packet.get("rust_lane") or {}).get("selected_builder_targets"),
            "packet_decision": (execution_packet.get("rust_lane") or {}).get("packet_decision"),
            "builder_success_condition": (execution_packet.get("rust_lane") or {}).get("builder_success_condition"),
        },
        "why_anchor_materialization_is_next": [
            "Scorer-side remaps and conditioned retrieval failed, so the next honest fix path is richer fresh-root evidence geometry.",
            "Flash-attn increases reviewed Rust support supply but is abstention-heavy and not the precise E-vs-F promotable contrast.",
            "The selected targets already expose implementation/build/symbol competition, but still need concrete verifier or selected-test anchors to become scoreable maintainer-grade rows.",
        ],
        "builder_contract": {
            "baseline_requirements": predecessor["builder_requirements"],
            "inventory_refresh_claim_boundary": inventory_refresh["claim_boundary"],
            "additional_requirements": [
                "At least one materialized root must be disjoint from tokenizers strict eval lineage.",
                "candidate_change_surface must remain a tempting visible negative rather than being removed from the option set",
                "the gold support fact must stay semantically distinct from verifier_and_test_constraint and from candidate surface labels",
                "rows must be reviewed, anti-cheat cleared, and gold adjudicated before any scoring use",
            ],
        },
        "priority_targets": request_targets,
        "promotion_and_hygiene_gates": [
            "No same-root replay from the current strict overlay into train.",
            "No target support fact may appear verbatim before options.",
            "Selected-test or verifier anchors are preferred; missing anchors keep the root diagnostic-only.",
            "Any next multilingual probe must beat the 22/24 canary with zero regressions before promotion.",
        ],
        "recommended_next_stage": "stage10838_rust_evidence_anchor_bundle_builder",
        "sources": {
            "execution_packet": display(EXECUTION_PACKET),
            "supply_manifest": display(SUPPLY_MANIFEST),
            "supply_targets": display(SUPPLY_TARGETS),
            "predecessor_request": display(PREDECESSOR_REQUEST),
            "inventory_refresh": display(INVENTORY_REFRESH),
            "latest_scorer_probe_audit": display(SCORER_AUDIT),
        },
    }

    write_json(REQUEST_JSON, payload)
    write_jsonl(TARGETS_JSONL, request_targets)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "request": display(REQUEST_JSON),
            "targets": display(TARGETS_JSONL),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
