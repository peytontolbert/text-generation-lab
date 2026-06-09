#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


DOMAINS = ("astro", "bio", "geo", "code", "math", "materials", "systems", "language")
PROPERTIES = ("color", "phase", "risk", "tool", "region", "class", "signal", "unit")
VALUES = {
    "color": ("red", "blue", "green", "amber", "white", "black"),
    "phase": ("solid", "liquid", "gas", "plasma"),
    "risk": ("low", "medium", "high", "critical"),
    "tool": ("indexer", "parser", "solver", "router", "encoder", "verifier"),
    "region": ("north", "south", "east", "west", "central"),
    "class": ("alpha", "beta", "gamma", "delta", "epsilon"),
    "signal": ("weak", "stable", "noisy", "strong"),
    "unit": ("meter", "second", "kelvin", "byte", "token"),
}


def _hash_id(*parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"gkbpp_{digest}"


def _candidate(values: tuple[str, ...] | list[str]) -> dict[str, Any]:
    size = max(2, len(values))
    return {
        "type": "finite",
        "values": list(values),
        "size": size,
        "bits": math.log2(size),
    }


def _unit(
    *,
    unit_type: str,
    domain: str,
    canonical_statement: str,
    answer: str,
    candidate_space: dict[str, Any],
    evidence: list[str],
    train_visibility: str,
    generalization_split: str,
    source_units: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    unit_id = _hash_id(unit_type, domain, canonical_statement, answer)
    return {
        "unit_id": unit_id,
        "unit_type": unit_type,
        "domain": domain,
        "canonical_statement": canonical_statement,
        "answer": answer,
        "candidate_space": candidate_space,
        "evidence": evidence,
        "train_visibility": train_visibility,
        "generalization_split": generalization_split,
        "source_units": source_units or [],
        "metadata": metadata or {},
        "queries": [
            canonical_statement,
            f"In domain {domain}, answer: {canonical_statement}",
        ],
    }


def build_units(seed: int, entities_per_domain: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    units: list[dict[str, Any]] = []
    fact_index: dict[tuple[str, str, str], dict[str, Any]] = {}
    relation_index: dict[tuple[str, str, str], dict[str, Any]] = {}

    for domain in DOMAINS:
        entities = [f"{domain}_entity_{i:03d}" for i in range(entities_per_domain)]
        hidden_entities = set(entities[-max(2, entities_per_domain // 5) :])
        for entity in entities:
            for prop in PROPERTIES:
                values = VALUES[prop]
                answer = values[(hash((seed, domain, entity, prop)) % len(values))]
                split = "held_out_entity" if entity in hidden_entities else "seen_entity"
                visibility = "hidden_eval" if entity in hidden_entities and prop in ("risk", "tool", "region") else "train_visible"
                statement = f"{entity} has {prop}"
                unit = _unit(
                    unit_type="atomic_fact",
                    domain=domain,
                    canonical_statement=statement,
                    answer=answer,
                    candidate_space=_candidate(values),
                    evidence=[f"{entity}.{prop}={answer}"],
                    train_visibility=visibility,
                    generalization_split=split,
                    metadata={"entity": entity, "property": prop},
                )
                units.append(unit)
                fact_index[(domain, entity, prop)] = unit

        for i, entity in enumerate(entities):
            target = entities[(i + 3) % len(entities)]
            rel = "linked_to"
            split = "held_out_relation_target" if target in hidden_entities else "seen_relation"
            visibility = "hidden_eval" if target in hidden_entities and i % 2 == 0 else "train_visible"
            statement = f"{entity} {rel}"
            unit = _unit(
                unit_type="relation",
                domain=domain,
                canonical_statement=statement,
                answer=target,
                candidate_space=_candidate(entities),
                evidence=[f"{entity} {rel} {target}"],
                train_visibility=visibility,
                generalization_split=split,
                metadata={"subject": entity, "relation": rel, "object": target},
            )
            units.append(unit)
            relation_index[(domain, entity, rel)] = unit

        for prop in ("risk", "tool"):
            default = VALUES[prop][0]
            statement = f"default {prop} for {domain}"
            units.append(
                _unit(
                    unit_type="schema",
                    domain=domain,
                    canonical_statement=statement,
                    answer=default,
                    candidate_space=_candidate(VALUES[prop]),
                    evidence=[f"schema {domain}.{prop}.default={default}"],
                    train_visibility="train_visible",
                    generalization_split="schema_default",
                    metadata={"property": prop},
                )
            )
            exception_entity = entities[1]
            exception_value = VALUES[prop][-1]
            units.append(
                _unit(
                    unit_type="exception",
                    domain=domain,
                    canonical_statement=f"{exception_entity} overrides default {prop}",
                    answer=exception_value,
                    candidate_space=_candidate(VALUES[prop]),
                    evidence=[f"exception {exception_entity}.{prop}={exception_value}"],
                    train_visibility="hidden_eval" if prop == "risk" else "train_visible",
                    generalization_split="exception_override",
                    metadata={"entity": exception_entity, "property": prop},
                )
            )

        for entity in entities[: entities_per_domain // 2]:
            entity_index = int(entity.rsplit("_", 1)[1])
            rel_unit = relation_index[(domain, entity, "linked_to")]
            target = rel_unit["answer"]
            prop = "risk"
            fact = fact_index[(domain, target, prop)]
            statement = f"risk of linked target for {entity}"
            units.append(
                _unit(
                    unit_type="composition",
                    domain=domain,
                    canonical_statement=statement,
                    answer=fact["answer"],
                    candidate_space=_candidate(VALUES[prop]),
                    evidence=[f"{entity}->linked_to->{target}", f"{target}.{prop}={fact['answer']}"],
                    train_visibility="hidden_eval"
                    if entity in hidden_entities or target in hidden_entities or entity_index % 5 == 0
                    else "train_visible",
                    generalization_split="two_hop_relation_property",
                    source_units=[rel_unit["unit_id"], fact["unit_id"]],
                    metadata={"depth": 2, "subject": entity, "relation": "linked_to", "property": prop},
                )
            )

    procedure_ops = {
        "strip_then_lower": ("strip", "lowercase", "hello"),
        "sort_then_join": ("sort", "join", "a|b|c"),
        "dedupe_then_count": ("dedupe", "count", "3"),
        "filter_then_sum": ("filter_positive", "sum", "9"),
        "tokenize_then_count": ("tokenize_space", "count", "4"),
    }
    for index, (name, (step_a, step_b, answer)) in enumerate(procedure_ops.items()):
        units.append(
            _unit(
                unit_type="procedure",
                domain="systems",
                canonical_statement=f"output of procedure {name}",
                answer=answer,
                candidate_space=_candidate(tuple(v[2] for v in procedure_ops.values())),
                evidence=[f"{name}: {step_a} -> {step_b} -> {answer}"],
                train_visibility="hidden_eval" if index in (2, 4) else "train_visible",
                generalization_split="held_out_procedure" if index in (2, 4) else "seen_procedure",
                metadata={"procedure": name, "steps": [step_a, step_b]},
            )
        )

    for i in range(32):
        domain = "math"
        a = i + 2
        b = (i * 3) % 11 + 1
        answer = str(a * b + a)
        units.append(
            _unit(
                unit_type="math_identity",
                domain=domain,
                canonical_statement=f"compute f(a,b)=a*b+a for a={a} b={b}",
                answer=answer,
                candidate_space={"type": "integer_range", "size": 512, "bits": math.log2(512), "range": [0, 511]},
                evidence=[f"{a}*{b}+{a}={answer}"],
                train_visibility="hidden_eval" if i % 5 == 0 else "train_visible",
                generalization_split="held_out_parameters" if i % 5 == 0 else "seen_formula",
                metadata={"a": a, "b": b, "formula": "a*b+a"},
            )
        )

    api_behaviors = {
        "normalize_key": "lowercase_and_strip",
        "merge_counts": "sum_by_key",
        "route_query": "select_operation_namespace",
        "verify_choice": "check_candidate_membership",
    }
    for name, behavior in api_behaviors.items():
        units.append(
            _unit(
                unit_type="code_api_semantics",
                domain="code",
                canonical_statement=f"behavior of api {name}",
                answer=behavior,
                candidate_space=_candidate(tuple(api_behaviors.values())),
                evidence=[f"def {name}(...): {behavior}"],
                train_visibility="hidden_eval" if name == "verify_choice" else "train_visible",
                generalization_split="held_out_api_name" if name == "verify_choice" else "seen_api",
                metadata={"api": name},
            )
        )

    for i, effect in enumerate(("increase", "decrease", "stabilize", "invert")):
        units.append(
            _unit(
                unit_type="causal_rule",
                domain="systems",
                canonical_statement=f"effect of intervention_{i} on signal",
                answer=effect,
                candidate_space=_candidate(("increase", "decrease", "stabilize", "invert")),
                evidence=[f"do(intervention_{i}) -> signal={effect}"],
                train_visibility="hidden_eval" if i == 3 else "train_visible",
                generalization_split="held_out_intervention" if i == 3 else "seen_intervention",
                metadata={"intervention": i},
            )
        )

    visible_facts = [unit for unit in units if unit["unit_type"] == "atomic_fact" and unit["train_visibility"] == "train_visible"]
    for unit in visible_facts[:64]:
        wrong_values = [v for v in unit["candidate_space"]["values"] if v != unit["answer"]]
        if not wrong_values:
            continue
        claimed = rng.choice(wrong_values)
        units.append(
            _unit(
                unit_type="counterfactual_false_claim",
                domain=unit["domain"],
                canonical_statement=f"claim {unit['canonical_statement']} is {claimed}; correct it",
                answer=unit["answer"],
                candidate_space=unit["candidate_space"],
                evidence=[f"claimed={claimed}", f"correct={unit['answer']}"],
                train_visibility="hidden_eval" if len(units) % 3 == 0 else "train_visible",
                generalization_split="near_miss_claim",
                source_units=[unit["unit_id"]],
                metadata={"claimed": claimed, "source_statement": unit["canonical_statement"]},
            )
        )

    return units


def write_outputs(units: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    all_path = output_dir / "knowledge_units.jsonl"
    train_path = output_dir / "knowledge_units_train.jsonl"
    eval_path = output_dir / "knowledge_units_eval.jsonl"
    query_path = output_dir / "general_kbpp_eval_queries.jsonl"

    train = [u for u in units if u["train_visibility"] == "train_visible"]
    eval_units = [u for u in units if u["train_visibility"] != "train_visible"]

    for path, rows in ((all_path, units), (train_path, train), (eval_path, eval_units)):
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")

    with query_path.open("w", encoding="utf-8") as handle:
        for unit in eval_units:
            handle.write(
                json.dumps(
                    {
                        "unit_id": unit["unit_id"],
                        "unit_type": unit["unit_type"],
                        "domain": unit["domain"],
                        "query": unit["queries"][0],
                        "answer": unit["answer"],
                        "candidate_space": unit["candidate_space"],
                        "verified_bits_if_correct": unit["candidate_space"]["bits"],
                        "source_units": unit["source_units"],
                        "generalization_split": unit["generalization_split"],
                    },
                    sort_keys=True,
                )
                + "\n"
            )

    total_eval_bits = sum(float(u["candidate_space"]["bits"]) for u in eval_units)
    by_type: dict[str, dict[str, Any]] = {}
    for unit in units:
        item = by_type.setdefault(unit["unit_type"], {"total": 0, "train": 0, "eval": 0, "eval_bits": 0.0})
        item["total"] += 1
        if unit["train_visibility"] == "train_visible":
            item["train"] += 1
        else:
            item["eval"] += 1
            item["eval_bits"] += float(unit["candidate_space"]["bits"])

    manifest = {
        "artifact_kind": "general_kbpp_pilot_dataset",
        "unit_schema": "runs/local/artifacts/knowledge_unit_schema.json",
        "all_units_path": str(all_path.relative_to(ROOT)),
        "train_units_path": str(train_path.relative_to(ROOT)),
        "eval_units_path": str(eval_path.relative_to(ROOT)),
        "eval_queries_path": str(query_path.relative_to(ROOT)),
        "total_units": len(units),
        "train_units": len(train),
        "eval_units": len(eval_units),
        "total_eval_verified_bits_available": total_eval_bits,
        "by_unit_type": by_type,
    }
    manifest_path = output_dir / "general_kbpp_pilot_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="runs/local/tmp/general_kbpp_pilot_v1")
    parser.add_argument("--seed", type=int, default=587)
    parser.add_argument("--entities-per-domain", type=int, default=16)
    args = parser.parse_args()

    units = build_units(seed=int(args.seed), entities_per_domain=int(args.entities_per_domain))
    manifest = write_outputs(units, ROOT / args.output_dir)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
