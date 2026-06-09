#!/usr/bin/env python3
"""Build the 100M-vs-7B KBPP bridge contract."""

from __future__ import annotations

import json
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def maybe_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> None:
    stage968 = maybe_json(ROOT / "runs/local/artifacts/stage968_loadable_pair_router_summary.json")
    stage969 = maybe_json(ROOT / "runs/local/artifacts/stage969_100m_stage968_integration_plan.json")
    route = maybe_json(ROOT / "runs/local/artifacts/100m_general_kbpp_route_map.json")
    baseline_candidates = [
        ROOT / "runs/local/artifacts/stage970_7b_stage968_baseline_summary.json",
        ROOT / "runs/local/artifacts/modern_7b_stage968_baseline_summary.json",
        ROOT / "runs/local/artifacts/7b_kbpp_stage968_baseline.json",
    ]
    found_baselines = [str(path.relative_to(ROOT)) for path in baseline_candidates if path.exists()]
    stage969_status = str(stage969.get("status", "missing_stage969"))
    has_100m_base = any(bool(base.get("checkpoint_exists")) for base in stage969.get("candidate_100m_bases", []))
    has_7b_baseline = bool(found_baselines)

    target_answer_exact = [
        int(stage968.get("split_scores", {}).get("eval", {}).get("answer", 0)),
        int(stage968.get("split_scores", {}).get("eval", {}).get("exact", 0)),
    ]
    implied_full = list(stage968.get("implied_full_answer_exact", [0, 0]))
    status = "ready_for_bridge_trial"
    blockers = []
    if not has_100m_base:
        blockers.append("missing_100m_base_checkpoint")
    if not has_7b_baseline:
        blockers.append("missing_7b_stage968_baseline")
    if blockers:
        status = "blocked_" + "_and_".join(blockers)

    if blockers:
        decision = (
            "Focus remains 100M beating 7B, but the evidence gate is not satisfied yet: "
            + ", ".join(blockers)
            + "."
        )
    else:
        decision = (
            "The 100M base and same-scorer 7B baseline artifacts are present. The next step is "
            "to run the bridge trial and compare useful KBPP under identical scorer and budget accounting."
        )

    if has_100m_base:
        first_step = "Run the Stage969 20-step frozen-decoder 100M smoke from the selected available base."
    else:
        first_step = "Restore the v430 or v424 100M checkpoint, or train a fresh 100M checkpoint from the same architecture if restoration is impossible."

    summary = {
        "artifact_kind": "stage970_100m_vs_7b_bridge_contract",
        "status": status,
        "timestamp": int(time.time()),
        "research_claim_scope": {
            "claim": "Binding-first semantic compression can give tiny/100M models higher verified semantic decision density than scale-first training on controlled KBPP tasks.",
            "not_yet_claimed": [
                "100M generally beats a modern 7B model.",
                "Bridge-free model-owned internalization of the Stage968 shared-anchor overlap primitive.",
                "Free-form generation parity with a modern 7B model.",
            ],
            "current_positive_result": "Stage968 loadable counted-interface scorer reaches 328/640 answer and 311/640 exact on hardened target rows, implied full 558/540, using a fixed shared-anchor overlap/count primitive plus a 97-parameter router.",
        },
        "stage968_gate": {
            "target_answer_exact": target_answer_exact,
            "implied_full_answer_exact": implied_full,
            "router_parameter_count": int(stage968.get("router_parameter_count", 0)),
            "scorer": "runs/local/artifacts/stage968_loadable_pair_router_summary.json",
        },
        "required_evidence_for_100m_beats_7b": [
            "Restore or train a 100M checkpoint with the Stage968 interface available.",
            "Evaluate the 100M on the same hidden KBPP scorer and preserve existing app/NLL gates.",
            "Evaluate at least one modern 7B baseline on the same hidden scorer with identical candidate sets and no extra labels.",
            "Claim only if 100M verified semantic decision density exceeds the 7B baseline after counting all interface/router parameters and fixed primitive budget.",
            "For strict model-owned claims, replace the fixed shared-anchor set-intersection circuit with a learned/equivalent internal equality-count circuit and rerun the same gates.",
        ],
        "blockers": blockers,
        "available_7b_baselines": found_baselines,
        "stage969_status": stage969_status,
        "candidate_100m_bases": stage969.get("candidate_100m_bases", []),
        "density_bridge_context": {
            "required_100m_vs_7b_multiplier_if_7b_fully_utilized": route.get("bridge_to_100m_vs_7b", {}).get("required_useful_kbpp_multiplier_if_7b_fully_utilized"),
            "params_ratio_7b_to_100m": route.get("bridge_to_100m_vs_7b", {}).get("params_ratio_7b_to_100m"),
            "route_artifact": "runs/local/artifacts/100m_general_kbpp_route_map.json",
        },
        "next_best_steps": [
            first_step,
            "Create a Stage970 7B baseline artifact by running a modern 7B on the Stage960/Stage968 KBPP scorer.",
            "Require Stage968 >= 328/311 and preserve app/NLL gates before any longer 100M run.",
            "Only then expand to longer 100M training and broader hidden KBPP surfaces.",
        ],
        "decision": decision,
    }
    output = ROOT / "runs/local/artifacts/stage970_100m_vs_7b_bridge_contract.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
