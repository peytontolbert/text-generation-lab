#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path: str) -> dict[str, Any]:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def best_for_threshold(report: dict[str, Any], threshold: str) -> dict[str, Any] | None:
    rows = report.get("threshold_leaders", {}).get(threshold, [])
    return rows[0] if rows else None


def build_report() -> dict[str, Any]:
    kbpp = load_json("runs/local/artifacts/knowledge_bits_per_param_report.json")
    ops = load_json("runs/local/artifacts/operation_bits_per_param_report.json")
    scale = load_json("runs/local/artifacts/scale_sweep_intelligence_density.json")
    readiness = load_json("runs/local/artifacts/general_kbpp_sweep_readiness.json")

    raw_leader = kbpp["top_verified_bits_per_param"][0]
    reliable_leader = best_for_threshold(kbpp, "exact>=0.999_and_answer>=0.999")
    answer_999 = best_for_threshold(kbpp, "answer>=0.999")
    exact_999 = best_for_threshold(kbpp, "exact>=0.999")
    op_10k = ops["composability_by_band"]["10k-20k"]

    target_designs = []
    for name, item in kbpp["target_design_summary"].items():
        best = item["best"]
        target_designs.append(
            {
                "design": name,
                "best_label": best["label"],
                "params": best["params"],
                "verified_bits_per_param": best["verified_bits_per_param"],
                "exact_top1": best.get("exact_top1"),
                "answer_top1": best.get("answer_top1"),
                "records": item["records"],
            }
        )
    target_designs.sort(key=lambda row: row["verified_bits_per_param"], reverse=True)

    raw_to_reliable_density_tax = None
    raw_to_answer999_density_tax = None
    if reliable_leader:
        raw_to_reliable_density_tax = 1.0 - (reliable_leader["verified_bits_per_param"] / raw_leader["verified_bits_per_param"])
    if answer_999:
        raw_to_answer999_density_tax = 1.0 - (answer_999["verified_bits_per_param"] / raw_leader["verified_bits_per_param"])

    report = {
        "artifact_kind": "kbpp_maximization_map",
        "sources": {
            "knowledge_bits_per_param": "runs/local/artifacts/knowledge_bits_per_param_report.json",
            "operation_bits_per_param": "runs/local/artifacts/operation_bits_per_param_report.json",
            "scale_sweep": "runs/local/artifacts/scale_sweep_intelligence_density.json",
            "general_sweep_readiness": "runs/local/artifacts/general_kbpp_sweep_readiness.json",
        },
        "current_frontiers": {
            "raw_density_leader": raw_leader,
            "answer_999_leader": answer_999,
            "exact_999_leader": exact_999,
            "exact_and_answer_999_leader": reliable_leader,
            "raw_to_answer999_density_tax_fraction": raw_to_answer999_density_tax,
            "raw_to_reliable_density_tax_fraction": raw_to_reliable_density_tax,
        },
        "design_levers_ranked": target_designs,
        "operation_geometry": {
            "ten_to_twenty_k_operation_oracle_answer_bits_per_param": op_10k["operation_oracle_answer_bits_per_param"],
            "ten_to_twenty_k_best_single_run_answer_bits_per_param": op_10k["best_single_run_answer_bits_per_param"],
            "ten_to_twenty_k_noncomposable_gap_fraction": op_10k["noncomposable_oracle_gap_fraction"],
            "oracle_operation_sources": op_10k["oracle_operation_sources"],
        },
        "anti_levers": [
            {
                "name": "learned_key_hash_or_auxiliary_anchor_inside_tiny_embedding_path",
                "evidence": "Stage572/575 share 123 misses with 0.9389 Jaccard; key pressure collapses membership proof geometry.",
                "rule": "Do not spend neural parameters learning deterministic keys; keep filters outside the neural path or encode keys as stable explicit fields.",
            },
            {
                "name": "overcompressed_membership_cards",
                "evidence": "Stage579 compact membership cards fell to 0.9540 exact / 0.9703 answer batch-local and 0.8563 / 0.9306 strict op-gated.",
                "rule": "Remove repeated boilerplate, but preserve entity, member, relation, count, and constraint anchors.",
            },
            {
                "name": "larger_model_on_saturated_curriculum",
                "evidence": "100M-v429 scored only 1.3919e-05 verified bits/param on the narrow map; overcapacity hides density.",
                "rule": "Only scale parameters after hidden entropy and composition depth scale with them.",
            },
        ],
        "maximization_principles": [
            {
                "principle": "Maximize target entropy per token before maximizing model size.",
                "reason": "The 16k band wins raw KBPP because the curriculum is compact and high-entropy; 100M is meaningless on a saturated target.",
            },
            {
                "principle": "Preserve discriminative binding anchors.",
                "reason": "The negative results are not from too many words; they are from removing anchors needed to separate near neighbors.",
            },
            {
                "principle": "Spend parameters on shared transforms, not deterministic lookup structure.",
                "reason": "Learned hashes and anchor sidepaths use capacity on structure a verifier/filter can provide exactly.",
            },
            {
                "principle": "Track reliability as a separate multiplier on KBPP.",
                "reason": "Stage525 has the raw density peak, but Stage508/548 is the reliable frontier.",
            },
            {
                "principle": "Use tiny rungs as geometry microscopes and large rungs only after entropy expansion.",
                "reason": f"The current general pilot needs {readiness['next_dataset_target']['required_growth_from_pilot']}x more hidden bits for a 100M screen.",
            },
        ],
        "next_ablation_stack": [
            {
                "name": "anchored_compact_membership_v2",
                "goal": "Recover Stage525 raw density while removing only redundant wording.",
                "target_change": "Use compact cards that always include op, domain, set/rule id, subject entity, candidate member, constraint fields, and answer.",
                "success_gate": "At 16k: answer >= 0.9985 without lowering strict op-gated membership recovery; at 21k: answer >= 0.9995.",
            },
            {
                "name": "entropy_balanced_general_pilot_v2",
                "goal": "Grow hidden bits while balancing facts, relations, procedures, math, counterfactuals, and compositions.",
                "target_change": "Increase candidate spaces and hidden units by type; avoid trivial schema saturation.",
                "success_gate": "At least 100k hidden bits for sub-1M screens; path to 10M hidden bits for 100M screens.",
            },
            {
                "name": "deterministic_key_outside_neural_path",
                "goal": "Measure neural KBPP with exact namespace/key filtering but no learned key pressure.",
                "target_change": "Evaluator supplies stable operation/domain candidate set; neural model resolves values and compositions.",
                "success_gate": "Hard-filter corrections must fall without reducing pure neural answer access.",
            },
            {
                "name": "composition_depth_curriculum",
                "goal": "Raise intelligence density, not just storage density.",
                "target_change": "Add controlled depth-2/depth-3 units where source facts are train-visible and compositions are hidden.",
                "success_gate": "Composition KBPP improves independently of atomic KBPP.",
            },
        ],
        "route_to_max_kbpp": {
            "near_term": "Push 16k/21k anchored compact targets until raw KBPP and answer reliability converge.",
            "mid_term": "Expand general hidden entropy to 100k+ bits and rerun 1k-1M to find real density knees.",
            "hundred_m_gate": "Do not use 100M as evidence until hidden verified bits reach the multi-million range and a 7B baseline is measured on the same scorer.",
        },
    }
    return report


def write_doc(report: dict[str, Any]) -> None:
    raw = report["current_frontiers"]["raw_density_leader"]
    reliable = report["current_frontiers"]["exact_and_answer_999_leader"]
    designs = "\n".join(
        f"- `{row['design']}`: `{row['verified_bits_per_param']}` bits/param via `{row['best_label']}`"
        for row in report["design_levers_ranked"]
    )
    principles = "\n".join(f"- {row['principle']} {row['reason']}" for row in report["maximization_principles"])
    ablations = "\n".join(
        f"- `{row['name']}`: {row['goal']} Success: {row['success_gate']}" for row in report["next_ablation_stack"]
    )
    anti = "\n".join(f"- `{row['name']}`: {row['rule']}" for row in report["anti_levers"])
    doc = f"""# KBPP Maximization Map

Artifact: `runs/local/artifacts/kbpp_maximization_map.json`

## Current Frontier

- Raw density leader: `{raw['label']}` at `{raw['params']}` params, `{raw['verified_bits_per_param']}` verified bits/param.
- Reliable exact+answer leader: `{reliable['label']}` at `{reliable['params']}` params, `{reliable['verified_bits_per_param']}` verified bits/param.
- Density tax from raw leader to reliable leader: `{report['current_frontiers']['raw_to_reliable_density_tax_fraction']}`.
- 16k operation-oracle gap: `{report['operation_geometry']['ten_to_twenty_k_noncomposable_gap_fraction']}`.

## Best Levers So Far

{designs}

## Anti-Levers

{anti}

## Maximization Rules

{principles}

## Next Ablations

{ablations}

## Route

- Near term: {report['route_to_max_kbpp']['near_term']}
- Mid term: {report['route_to_max_kbpp']['mid_term']}
- 100M gate: {report['route_to_max_kbpp']['hundred_m_gate']}
"""
    (ROOT / "docs/kbpp_maximization_map.md").write_text(doc, encoding="utf-8")


def main() -> None:
    report = build_report()
    output = ROOT / "runs/local/artifacts/kbpp_maximization_map.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(report)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
