#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
KBPP_ROUTE = ROOT / "runs/local/artifacts/100m_general_kbpp_route_map.json"
OP_REPORT = ROOT / "runs/local/artifacts/operation_bits_per_param_report.json"
TINY_MAP = ROOT / "runs/local/artifacts/tiny_intelligence_mapping.json"
JSON_OUT = ROOT / "runs/local/artifacts/model_intelligence_density_framework.json"
DOC_OUT = ROOT / "docs/model_intelligence_density_framework.md"


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build() -> dict[str, Any]:
    route = _load(KBPP_ROUTE)
    op = _load(OP_REPORT)
    tiny = _load(TINY_MAP)
    bridge = route["bridge_to_100m_vs_7b"]
    composability = op["composability_by_band"]

    framework = {
        "artifact_kind": "model_intelligence_density_framework",
        "scope": "understanding model intelligence as useful knowledge and composition per parameter and per compute",
        "source_artifacts": {
            "100m_route": str(KBPP_ROUTE.relative_to(ROOT)),
            "operation_bits": str(OP_REPORT.relative_to(ROOT)),
            "tiny_intelligence_map": str(TINY_MAP.relative_to(ROOT)),
        },
        "core_claim": (
            "A smaller model can be more intelligent than a larger model only if it has higher effective intelligence density: "
            "more recoverable, composable, generalizable knowledge per parameter and per unit inference compute."
        ),
        "intelligence_axes": [
            {
                "name": "recoverable_knowledge_bits_per_param",
                "question": "How many distinct facts, relations, procedures, schemas, and rules can be recovered per parameter?",
                "current_metric": "verified answer bits per parameter",
                "current_status": "implemented for structured semantic curricula",
                "next_metric": "general KBPP over atomic, relational, procedural, and compositional natural knowledge units",
            },
            {
                "name": "binding_reliability",
                "question": "Are the right pieces of knowledge retrieved/generated together in one checkpoint, not just somewhere in the run family?",
                "current_metric": "exact/answer top1 plus operation-oracle vs best-single-run composability gap",
                "current_status": "16k oracle gap is small, but 16k still misses residual answer bits; 26k clears reliability",
                "next_metric": "joint reliability over broad knowledge categories and paraphrase forms",
            },
            {
                "name": "composition_depth_per_param",
                "question": "Can stored knowledge be recombined into unseen multi-hop answers?",
                "current_metric": "derived set intersections, rule-case intersections, two-hop owner-region operations",
                "current_status": "measured in controlled curricula; composite membership remains the 16k bottleneck",
                "next_metric": "held-out composition graphs with depth, branching factor, and distractor controls",
            },
            {
                "name": "generalization_bits_per_param",
                "question": "How many useful bits transfer to unseen formulations rather than memorized rows?",
                "current_metric": "not fully separated from retrieval-card recovery",
                "current_status": "open gap",
                "next_metric": "train/test split by entity, schema, relation template, paraphrase, and composition graph",
            },
            {
                "name": "compute_efficiency",
                "question": "How many verified useful bits are available per inference and training compute unit?",
                "current_metric": "verified bits per training token and params*steps proxies",
                "current_status": "implemented as proxy in tiny_intelligence_mapping",
                "next_metric": "verified bits per measured FLOP and latency at fixed answer quality",
            },
            {
                "name": "abstraction_reuse",
                "question": "Does one learned parameter pattern serve many facts/tasks, or only one memorized card?",
                "current_metric": "indirectly visible through density shifts from target factorization",
                "current_status": "target design moved reliable density by about 20x in controlled setting",
                "next_metric": "reuse factor: verified held-out bits gained per explicitly trained bit",
            },
        ],
        "working_equation": {
            "name": "effective_intelligence_density",
            "definition": (
                "EID = sum_i(verified_bits_i * reliability_i * generalization_i * composition_depth_weight_i) "
                "/ (parameters * inference_compute_i)"
            ),
            "notes": [
                "KBPP is the storage term, not the whole intelligence term.",
                "A model with high KBPP but low binding reliability is dense but not reliably intelligent.",
                "A model with high memorized KBPP but low generalization has knowledge storage, not broad intelligence.",
                "A 100M model beats a 7B generally only when its EID advantage exceeds the 70x parameter deficit at comparable task breadth.",
            ],
        },
        "current_quantitative_anchors": {
            "required_100m_vs_7b_kbpp_multiplier_if_7b_fully_utilized": bridge[
                "required_useful_kbpp_multiplier_if_7b_fully_utilized"
            ],
            "observed_reliable_kbpp_bridge": bridge["observed_reliable_26k_vs_reliable_523k_bpp_ratio"],
            "observed_raw_kbpp_bridge": bridge["observed_raw_16k_vs_reliable_523k_bpp_ratio"],
            "remaining_multiplier_after_reliable_bridge": bridge[
                "remaining_multiplier_after_observed_reliable_bridge"
            ],
            "remaining_multiplier_after_raw_bridge": bridge["remaining_multiplier_after_observed_raw_bridge"],
            "10k_20k_operation_oracle_gap_fraction": composability["10k-20k"][
                "noncomposable_oracle_gap_fraction"
            ],
            "tiny_map_record_count": tiny.get("record_count"),
        },
        "research_implications": [
            "The route to powerful smaller models is not only better memorization; it is higher recoverable knowledge density plus reliable binding and reusable abstractions.",
            "Current evidence says target representation can move density by tens of times, but broad general intelligence needs a general KBPP benchmark and generalization-bit accounting.",
            "The next decisive map is not another narrow replay run; it is a general knowledge-unit benchmark with scale ladders and 7B useful-KBPP baselines.",
            "Once the broad ladder predicts a 100M EID advantage over the measured 7B baseline with margin, the route becomes engineering rather than exploration.",
        ],
        "next_artifacts": [
            "general_kbpp_benchmark_spec",
            "knowledge_unit_schema",
            "generalization_bits_per_param_ladder",
            "7b_useful_kbpp_baseline",
            "100m_eid_go_no_go_gate",
        ],
    }
    return framework


def write_doc(framework: dict[str, Any]) -> None:
    lines = [
        "# Model Intelligence Density Framework",
        "",
        framework["core_claim"],
        "",
        "## Working Equation",
        "",
        f"`{framework['working_equation']['definition']}`",
        "",
    ]
    for note in framework["working_equation"]["notes"]:
        lines.append(f"- {note}")
    lines.extend(["", "## Intelligence Axes", ""])
    for axis in framework["intelligence_axes"]:
        lines.append(f"### {axis['name']}")
        lines.append(f"- Question: {axis['question']}")
        lines.append(f"- Current metric: {axis['current_metric']}")
        lines.append(f"- Current status: {axis['current_status']}")
        lines.append(f"- Next metric: {axis['next_metric']}")
        lines.append("")
    lines.extend(["## Quantitative Anchors", ""])
    for key, value in framework["current_quantitative_anchors"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Research Implications", ""])
    for item in framework["research_implications"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Next Artifacts", ""])
    for item in framework["next_artifacts"]:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "## Source",
            "",
            f"- JSON: `{JSON_OUT.relative_to(ROOT)}`",
            f"- 100M KBPP route: `{framework['source_artifacts']['100m_route']}`",
            f"- Operation bits report: `{framework['source_artifacts']['operation_bits']}`",
            f"- Tiny intelligence map: `{framework['source_artifacts']['tiny_intelligence_map']}`",
        ]
    )
    DOC_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    framework = build()
    JSON_OUT.write_text(json.dumps(framework, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(framework)
    print(json.dumps({"json": str(JSON_OUT), "doc": str(DOC_OUT)}, indent=2))


if __name__ == "__main__":
    main()
