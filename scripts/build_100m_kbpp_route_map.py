#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BITS_REPORT = ROOT / "runs/local/artifacts/knowledge_bits_per_param_report.json"
OP_REPORT = ROOT / "runs/local/artifacts/operation_bits_per_param_report.json"
JSON_OUT = ROOT / "runs/local/artifacts/100m_general_kbpp_route_map.json"
DOC_OUT = ROOT / "docs/100m_general_kbpp_route.md"


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _find(records: list[dict[str, Any]], label: str) -> dict[str, Any] | None:
    for record in records:
        if record.get("label") == label:
            return record
    return None


def _leader(report: dict[str, Any], section: str, label: str) -> dict[str, Any] | None:
    for record in report.get(section, []):
        if record.get("label") == label:
            return record
    return None


def _all_records(report: dict[str, Any]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for key in ("top_verified_bits_per_param", "top_verified_bits_per_training_token"):
        for row in report.get(key, []):
            if row.get("label"):
                seen[str(row["label"])] = row
    for rows in (report.get("threshold_leaders") or {}).values():
        for row in rows:
            if row.get("label"):
                seen[str(row["label"])] = row
    for summary in (report.get("band_summary") or {}).values():
        best = summary.get("best")
        if isinstance(best, dict) and best.get("label"):
            seen[str(best["label"])] = best
    return list(seen.values())


def build() -> dict[str, Any]:
    bits = _load(BITS_REPORT)
    op = _load(OP_REPORT)
    records = _all_records(bits)

    raw_16k = _leader(bits, "top_verified_bits_per_param", "stage525_16k_rule_replay_from_stage502_2400step")
    reliable_26k = None
    for row in (bits.get("threshold_leaders") or {}).get("exact>=0.999_and_answer>=0.999", []):
        if row.get("label") == "stage508_26k_intermediate_d12_900step":
            reliable_26k = row
            break
    reliable_60k = _find(records, "stage491_60k_direct_fact_key_600step")
    reliable_523k = _find(records, "stage470_523k_compact_reverse_comp_key")
    reliable_13m = _find(records, "stage473_13m_compact_reverse_comp_key")

    def bpp(row: dict[str, Any] | None) -> float:
        return float((row or {}).get("verified_bits_per_param") or 0.0)

    def ratio(a: dict[str, Any] | None, b: dict[str, Any] | None) -> float | None:
        denom = bpp(b)
        return bpp(a) / denom if denom else None

    bridge = {
        "params_ratio_7b_to_100m": 70.0,
        "required_useful_kbpp_multiplier_if_7b_fully_utilized": 70.0,
        "observed_reliable_26k_vs_reliable_523k_bpp_ratio": ratio(reliable_26k, reliable_523k),
        "observed_raw_16k_vs_reliable_523k_bpp_ratio": ratio(raw_16k, reliable_523k),
        "observed_reliable_26k_vs_reliable_60k_bpp_ratio": ratio(reliable_26k, reliable_60k),
        "observed_raw_16k_vs_reliable_26k_bpp_ratio": ratio(raw_16k, reliable_26k),
        "observed_raw_16k_vs_13m_bpp_ratio": ratio(raw_16k, reliable_13m),
    }
    reliable_bridge = float(bridge["observed_reliable_26k_vs_reliable_523k_bpp_ratio"] or 0.0)
    raw_bridge = float(bridge["observed_raw_16k_vs_reliable_523k_bpp_ratio"] or 0.0)
    bridge["remaining_multiplier_after_observed_reliable_bridge"] = 70.0 / reliable_bridge if reliable_bridge else None
    bridge["remaining_multiplier_after_observed_raw_bridge"] = 70.0 / raw_bridge if raw_bridge else None
    bridge["max_7b_effective_useful_fraction_for_reliable_bridge_to_suffice"] = reliable_bridge / 70.0 if reliable_bridge else None
    bridge["max_7b_effective_useful_fraction_for_raw_bridge_to_suffice"] = raw_bridge / 70.0 if raw_bridge else None

    route = {
        "artifact_kind": "100m_general_kbpp_route_map",
        "scope": "general knowledge bits per parameter, not agentic/tool-use specialization",
        "source_reports": {
            "knowledge_bits_per_param_report": str(BITS_REPORT.relative_to(ROOT)),
            "operation_bits_per_param_report": str(OP_REPORT.relative_to(ROOT)),
        },
        "current_anchor_points": {
            "raw_density_16k": raw_16k,
            "reliable_26k": reliable_26k,
            "reliable_60k": reliable_60k,
            "reliable_523k": reliable_523k,
            "reliable_13m": reliable_13m,
        },
        "bridge_to_100m_vs_7b": bridge,
        "current_read": [
            "The required 100M-vs-7B bridge is about 70x useful knowledge density if every 7B parameter is equally useful.",
            "The controlled semantic curriculum already shows roughly 20x reliable density improvement from target design at the 26k-vs-523k anchor, and over 32x raw density at the 16k-vs-523k anchor.",
            "After the observed reliable bridge, the remaining multiplier to a fully utilized 7B is about 3.46x; after the observed raw bridge, it is about 2.18x.",
            "Equivalently, the observed reliable bridge would be enough if the measured 7B baseline uses no more than about 28.9% of its parameters for recoverable target knowledge; the raw bridge threshold is about 45.8%.",
            "The remaining bridge must come from broad general-knowledge factorization, tokenizer/vocabulary overhead reduction, better reusable abstractions, and exploiting redundancy in ordinary 7B token-prediction training.",
            "The route is not proven, but it is now a concrete density-bridge problem rather than a vague small-model hope.",
        ],
        "non_experimental_route_requirements": [
            {
                "name": "Define general knowledge bits",
                "gate": "A benchmark that counts recoverable atomic, relational, procedural, and compositional knowledge bits independent of agent/tool behavior.",
            },
            {
                "name": "Show broad KBPP scaling",
                "gate": "A 10M/30M/100M/300M ladder where answer-equivalent general KBPP rises predictably and the 100M rung exceeds the measured 7B useful-KBPP baseline.",
            },
            {
                "name": "Factorize the corpus",
                "gate": "Training data represented as reusable knowledge units: entities, relations, schemas, exceptions, procedures, causal rules, and compositions, with natural-language paraphrase tied back to those units.",
            },
            {
                "name": "Use dense semantic supervision",
                "gate": "Every token budget must carry measured knowledge bits; avoid long low-entropy prose when a factorized card or schema carries the same recoverable knowledge.",
            },
            {
                "name": "Preserve anchors while compressing",
                "gate": "Targets must remove irrelevant fields but keep discriminative anchors. Stage579 shows minimal key/member/count cards are too compressed.",
            },
            {
                "name": "Train a general model, not a sidecar",
                "gate": "Auxiliary KBPP heads are allowed during training, but the final 100M model must answer through its general model path.",
            },
            {
                "name": "Establish a non-experimental go/no-go threshold",
                "gate": "Before the final 100M run, the extrapolated KBPP curve must exceed the 7B measured baseline by a margin, not just tie it.",
            },
        ],
        "candidate_training_route": [
            "Build a broad factorized knowledge corpus from natural data: facts, relations, definitions, procedures, causal rules, code/API semantics, math identities, and multi-hop compositions.",
            "Train with mixed objectives: next-token language modeling, masked/fill knowledge reconstruction, relation completion, contradiction/false-claim correction, and composition queries.",
            "Use compact target design from the successful stages: direct keys, compact false claims, rule/exception keys, composition keys, selected anchors for membership-like structures.",
            "Avoid failed mechanisms: broad replay without target redesign, learned key hashes mixed into tiny embeddings, and over-compressed membership cards.",
            "Track KBPP continuously: total verified bits/param, operation/procedure-level bits/param, oracle-vs-single-run composability gap, and reliability thresholds.",
            "Only scale to the final 100M general run after the smaller ladder predicts the 100M KBPP bridge over the 7B baseline.",
        ],
    }
    return route


def write_doc(route: dict[str, Any]) -> None:
    b = route["bridge_to_100m_vs_7b"]
    lines = [
        "# 100M General KBPP Route",
        "",
        "Scope: general knowledge bits per parameter, not agentic/tool-use specialization.",
        "",
        "## Current Answer",
        "",
        "We do not yet have a non-experimental route that guarantees a 100M general model beats a modern 7B general model.",
        "We do have a concrete density-bridge map: a 100M model must overcome a `70x` parameter deficit, and our controlled curricula already show large but incomplete KBPP multipliers.",
        "",
        "## Density Bridge",
        "",
        f"- Required multiplier if 7B parameters are fully useful: `{b['required_useful_kbpp_multiplier_if_7b_fully_utilized']}`",
        f"- Observed reliable 26k vs reliable 523k KBPP ratio: `{b['observed_reliable_26k_vs_reliable_523k_bpp_ratio']}`",
        f"- Observed raw 16k vs reliable 523k KBPP ratio: `{b['observed_raw_16k_vs_reliable_523k_bpp_ratio']}`",
        f"- Observed reliable 26k vs reliable 60k KBPP ratio: `{b['observed_reliable_26k_vs_reliable_60k_bpp_ratio']}`",
        f"- Observed raw 16k vs reliable 26k KBPP ratio: `{b['observed_raw_16k_vs_reliable_26k_bpp_ratio']}`",
        f"- Remaining multiplier after observed reliable bridge: `{b['remaining_multiplier_after_observed_reliable_bridge']}`",
        f"- Remaining multiplier after observed raw bridge: `{b['remaining_multiplier_after_observed_raw_bridge']}`",
        f"- 7B effective-useful-fraction threshold for reliable bridge to suffice: `{b['max_7b_effective_useful_fraction_for_reliable_bridge_to_suffice']}`",
        f"- 7B effective-useful-fraction threshold for raw bridge to suffice: `{b['max_7b_effective_useful_fraction_for_raw_bridge_to_suffice']}`",
        "",
        "Interpretation: target design has already produced roughly `20x` reliable density movement in the controlled curriculum and `32x` raw density movement at the 16k anchor. If a 7B baseline's recoverable target knowledge uses less than about `29%` of its parameter budget, the reliable bridge could already be enough in principle; if it uses less than about `46%`, the raw bridge could be enough. Otherwise the remaining multiplier must come from broad factorization, tokenizer overhead reduction, reusable abstractions, and measured redundancy in ordinary 7B training.",
        "",
        "## Non-Experimental Route Requirements",
        "",
    ]
    for item in route["non_experimental_route_requirements"]:
        lines.append(f"- `{item['name']}`: {item['gate']}")
    lines.extend(["", "## Candidate Training Route", ""])
    for step in route["candidate_training_route"]:
        lines.append(f"- {step}")
    lines.extend(["", "## Current Read", ""])
    for finding in route["current_read"]:
        lines.append(f"- {finding}")
    lines.extend(
        [
            "",
            "## Source",
            "",
            f"- JSON: `{JSON_OUT.relative_to(ROOT)}`",
            f"- KBPP report: `{route['source_reports']['knowledge_bits_per_param_report']}`",
            f"- Operation report: `{route['source_reports']['operation_bits_per_param_report']}`",
        ]
    )
    DOC_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    route = build()
    JSON_OUT.write_text(json.dumps(route, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(route)
    print(json.dumps({"json": str(JSON_OUT), "doc": str(DOC_OUT)}, indent=2))


if __name__ == "__main__":
    main()
