#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JSON_OUT = ROOT / "runs/local/artifacts/general_kbpp_benchmark_spec.json"
DOC_OUT = ROOT / "docs/general_kbpp_benchmark_spec.md"
SCHEMA_OUT = ROOT / "runs/local/artifacts/knowledge_unit_schema.json"


def build() -> dict:
    unit_schema = {
        "schema_name": "knowledge_unit_v1",
        "required_fields": [
            "unit_id",
            "unit_type",
            "domain",
            "canonical_statement",
            "answer",
            "candidate_space",
            "evidence",
            "train_visibility",
            "generalization_split",
        ],
        "unit_types": {
            "atomic_fact": "Single recoverable proposition, e.g. entity-property-value.",
            "relation": "Typed relation between two or more entities.",
            "schema": "Reusable field/type/default structure.",
            "exception": "Override to a schema/default rule.",
            "procedure": "Ordered transformation or algorithmic step sequence.",
            "causal_rule": "If/then or intervention-style relation with directionality.",
            "math_identity": "Symbolic or numerical identity with variable substitution.",
            "code_api_semantics": "Function/class/API behavior and constraints.",
            "composition": "Multi-unit query requiring joins, chains, intersections, or rule application.",
            "counterfactual_false_claim": "Incorrect claim with recoverable correction.",
        },
        "candidate_space": {
            "type": "finite_or_estimated",
            "bits": "log2(number_of_valid_candidates) or calibrated entropy for open answers",
        },
    }

    spec = {
        "artifact_kind": "general_kbpp_benchmark_spec",
        "purpose": "Measure broad recoverable, composable, generalizable knowledge bits per parameter for general models.",
        "non_goals": [
            "Do not measure agent/tool use.",
            "Do not reward verbose explanation unless it recovers additional verified knowledge bits.",
            "Do not count benchmark leakage or exact memorization as generalization.",
        ],
        "knowledge_unit_schema": unit_schema,
        "benchmark_families": [
            {
                "name": "atomic_recovery",
                "unit_types": ["atomic_fact", "relation", "schema", "exception"],
                "measures": ["recoverable_knowledge_bits_per_param", "binding_reliability"],
                "split_controls": ["held_out_entities", "held_out_domains", "paraphrased_queries"],
            },
            {
                "name": "composition_recovery",
                "unit_types": ["composition", "relation", "schema", "exception"],
                "measures": ["composition_depth_per_param", "binding_reliability"],
                "split_controls": ["held_out_composition_graphs", "depth", "branching_factor", "distractors"],
            },
            {
                "name": "procedural_knowledge",
                "unit_types": ["procedure", "code_api_semantics", "math_identity"],
                "measures": ["generalization_bits_per_param", "compute_efficiency"],
                "split_controls": ["held_out_parameters", "held_out_surface_forms", "held_out_api_names"],
            },
            {
                "name": "false_claim_correction",
                "unit_types": ["counterfactual_false_claim", "exception", "causal_rule"],
                "measures": ["negative_knowledge_bits_per_param", "binding_reliability"],
                "split_controls": ["near_miss_claims", "field_swaps", "entity_swaps"],
            },
            {
                "name": "abstraction_reuse",
                "unit_types": ["schema", "procedure", "causal_rule", "math_identity"],
                "measures": ["reuse_factor", "generalization_bits_per_param"],
                "split_controls": ["new_entities_under_seen_schema", "new_schema_combinations", "new_variable_bindings"],
            },
        ],
        "bit_accounting": {
            "verified_bits": "sum(correct_unit_i * log2(candidate_space_i))",
            "kbpp": "verified_bits / parameter_count",
            "generalization_kbpp": "verified_bits_on_hidden_unit_splits / parameter_count",
            "composition_kbpp": "verified_bits_on_multi_unit_queries / parameter_count",
            "eid": "sum(verified_bits_i * reliability_i * generalization_i * composition_depth_weight_i) / (parameters * inference_compute_i)",
            "reliability_gate": "Report raw density separately from thresholds; promotion requires exact/answer reliability across all required families.",
        },
        "required_model_ladder": [
            "10M",
            "30M",
            "100M",
            "300M",
            "7B_baseline",
        ],
        "go_no_go_for_100m_vs_7b": {
            "primary": "100M generalization KBPP and EID exceed measured 7B baseline by margin on hidden units.",
            "minimum_margin": ">=1.25x on EID and >=1.10x on generalization KBPP before claiming route is engineering-ready.",
            "failure_condition": "If 100M only wins memorized KBPP but loses generalization or composition, route is not sufficient.",
        },
        "dataset_construction_rules": [
            "Every unit must have a finite or calibrated candidate space.",
            "Every answer must be verifier-checkable.",
            "Natural-language paraphrases must map back to the same canonical unit.",
            "Composition examples must reference source unit ids and graph depth.",
            "Training-visible and hidden units must be explicitly marked.",
            "Generated synthetic units and natural mined units must be tracked separately.",
            "Candidate distractors must include near misses, field swaps, relation swaps, and entity swaps.",
        ],
        "next_build_steps": [
            "Create a JSONL knowledge-unit dataset with this schema.",
            "Build a verifier that scores exact, answer-equivalent, and compositional answers.",
            "Measure a 7B baseline useful-KBPP on the same hidden-unit splits.",
            "Train 10M/30M/100M ladder models with factorized knowledge supervision.",
            "Fit KBPP/EID scaling curves and only then decide whether the 100M route is non-experimental.",
        ],
    }
    return spec


def write_doc(spec: dict) -> None:
    lines = [
        "# General KBPP Benchmark Spec",
        "",
        spec["purpose"],
        "",
        "## Non-Goals",
        "",
    ]
    for item in spec["non_goals"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Knowledge Unit Types", ""])
    for name, desc in spec["knowledge_unit_schema"]["unit_types"].items():
        lines.append(f"- `{name}`: {desc}")
    lines.extend(["", "## Benchmark Families", ""])
    for family in spec["benchmark_families"]:
        lines.append(f"### {family['name']}")
        lines.append(f"- Unit types: `{', '.join(family['unit_types'])}`")
        lines.append(f"- Measures: `{', '.join(family['measures'])}`")
        lines.append(f"- Split controls: `{', '.join(family['split_controls'])}`")
        lines.append("")
    lines.extend(["## Bit Accounting", ""])
    for key, value in spec["bit_accounting"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## 100M vs 7B Go/No-Go", ""])
    for key, value in spec["go_no_go_for_100m_vs_7b"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Dataset Construction Rules", ""])
    for item in spec["dataset_construction_rules"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Next Build Steps", ""])
    for item in spec["next_build_steps"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Source",
            "",
            f"- Spec JSON: `{JSON_OUT.relative_to(ROOT)}`",
            f"- Unit schema JSON: `{SCHEMA_OUT.relative_to(ROOT)}`",
        ]
    )
    DOC_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    spec = build()
    JSON_OUT.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SCHEMA_OUT.write_text(json.dumps(spec["knowledge_unit_schema"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(spec)
    print(json.dumps({"spec": str(JSON_OUT), "schema": str(SCHEMA_OUT), "doc": str(DOC_OUT)}, indent=2))


if __name__ == "__main__":
    main()
