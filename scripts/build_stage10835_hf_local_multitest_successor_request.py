#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10835
NAME = "stage10835_hf_local_multitest_successor_request"
OUT_DIR = ARTIFACTS / NAME
REQUEST_JSON = OUT_DIR / "hf_local_multitest_successor_request.json"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

EXECUTION_PACKET = ARTIFACTS / "stage10834_residual_expansion_execution_packet" / "residual_expansion_execution_packet.json"
SUPPLY_MANIFEST = ARTIFACTS / "stage10822_residual_lane_fresh_root_supply_manifest" / "residual_lane_fresh_root_supply_manifest.json"
SUPPLY_TARGETS = ARTIFACTS / "stage10822_residual_lane_fresh_root_supply_manifest" / "residual_lane_fresh_root_targets.jsonl"
PREDECESSOR_REQUEST = ARTIFACTS / "stage10496_hf_local_verifier_geometry_rebuild_request" / "hf_local_verifier_geometry_rebuild_request.json"
PYTHON_PACKET = ARTIFACTS / "stage10493_python_verifier_fresh_review_packet_builder" / "python_verifier_fresh_review_packet_builder.json"
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
    python_packet = load_json(PYTHON_PACKET)
    scorer_audit = load_json(SCORER_AUDIT)

    python_targets = [
        row
        for row in supply_targets
        if row.get("lane") == "python_verifier_outcome"
    ]
    support_root = next(
        row for row in python_targets
        if row.get("usable_now_for_promotable_support")
    )
    rebuild_root = next(
        row for row in python_targets
        if not row.get("usable_now_for_promotable_support")
        and "hf_local" in str(row.get("candidate_root_id"))
    )
    current_miss = next(
        miss
        for miss in (execution_packet.get("current_frontier") or {}).get("strict_misses", [])
        if miss.get("language_family") == "python"
    )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "hf_local_multitest_successor_request_ready",
        "claim_scope": [
            "Convert the stage10834 residual packet into the concrete Python verifier rebuild request required for the next honest v2.7 advancement attempt.",
            "Keep stage10236 context-pack support available for training while forcing hf_local to become a real multitest verifier-disambiguation root before any promotion use.",
        ],
        "current_frontier_context": {
            "strict_exact": (execution_packet.get("current_frontier") or {}).get("strict_exact"),
            "python_strict_miss": current_miss,
            "strict_miss_set_unchanged": (execution_packet.get("current_frontier") or {}).get("strict_miss_set_unchanged"),
            "latest_probe_reason_not_fixed": "broad support and evidence-role probes preserved the canary without flipping the Python verifier row",
        },
        "lane_decision": {
            "support_only_root": support_root["candidate_root_id"],
            "support_only_root_selected_test_count": support_root["selected_test_count"],
            "support_only_root_executable_verifier_row_count": support_root["executable_verifier_row_count"],
            "rebuild_required_root": rebuild_root["candidate_root_id"],
            "rebuild_required_root_selected_test_count": rebuild_root["selected_test_count"],
            "rebuild_required_root_gaps": rebuild_root["gaps"],
            "packet_decision": (execution_packet.get("python_lane") or {}).get("packet_decision"),
        },
        "why_hf_local_is_still_the_right_rebuild": [
            "It is the only queued Python residual root explicitly aimed at verifier-target confusion rather than general support preservation.",
            "Its reviewed verifier geometry is still singleton and therefore incapable of teaching or honestly evaluating B-vs-C style selected-test disambiguation.",
            "The current canary miss remains a verifier_outcome failure even after clean evidence-role support, so geometry is the bottleneck rather than generic Python supply.",
        ],
        "rebuild_contract": {
            "minimum_visible_verifier_targets": predecessor["rebuild_requirements"]["minimum_visible_verifier_targets"],
            "must_include": predecessor["rebuild_requirements"]["must_include"],
            "must_reduce_shortcuts": predecessor["rebuild_requirements"]["must_reduce_shortcuts"],
            "acceptable_evidence_sources": predecessor["rebuild_requirements"]["acceptable_evidence_sources"],
            "anti_cheat_gates": (execution_packet.get("python_lane") or {}).get("anti_cheat_gates"),
            "additional_success_requirements": [
                "At least one wrong but plausible sibling test must share repo family and naming style with the gold test.",
                "The gold verifier target must be identifiable from evidence and transition semantics, not from literal path exposure.",
                "The rebuilt packet must remain root-disjoint from the current strict overlay and train-support rows.",
            ],
        },
        "support_boundary": {
            "immediately_qualified_reviewed_roots": supply_manifest["python_lane"]["immediately_qualified_reviewed_roots"],
            "qualified_support_row_count": python_packet["summary"]["qualified_support_row_count"],
            "train_support_only_guidance": [
                "Use stage10236 rows to preserve Python verifier signal in multilingual training packages.",
                "Do not describe stage10236 as a fix for the MirrorMind verifier miss.",
                "Do not treat hf_local as promotable until the multitest rebuild passes review, anti-cheat, and bounded executable-row materialization.",
            ],
        },
        "promotion_and_hygiene_gates": [
            "No same-root replay from the current strict overlay into train.",
            "No target path or gold test path may appear verbatim before the candidate set.",
            "Prompt-target leak audit must remain false.",
            "Candidate order balance must be verified after permutation generation.",
            "Any next multilingual probe must beat the 22/24 canary with zero regressions before promotion.",
        ],
        "recommended_next_stage": "stage10837_hf_local_multitest_verifier_packet_builder",
        "sources": {
            "execution_packet": display(EXECUTION_PACKET),
            "supply_manifest": display(SUPPLY_MANIFEST),
            "supply_targets": display(SUPPLY_TARGETS),
            "predecessor_request": display(PREDECESSOR_REQUEST),
            "python_packet_audit": display(PYTHON_PACKET),
            "latest_scorer_probe_audit": display(SCORER_AUDIT),
        },
    }

    write_json(REQUEST_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "request": display(REQUEST_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
