#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/local/tmp/stage653_generalized_8kbpp_surface"
ARTIFACT = ROOT / "runs/local/artifacts/stage653_generalized_8kbpp_surface.json"
DOC = ROOT / "docs/stage653_generalized_8kbpp_surface.md"
PARAMS = 16280
TARGET_KBPP = 8.0
MIN_BITS = PARAMS * TARGET_KBPP

DOMAINS = tuple(f"gdom_{i:03d}" for i in range(72))
PROPERTIES = (
    "color",
    "phase",
    "risk",
    "tool",
    "region",
    "class",
    "signal",
    "unit",
)
VALUES = {
    prop: tuple(f"{prop}_v{i:02d}" for i in range(64)) for prop in PROPERTIES
}
RELATIONS = ("linked_to", "owned_by")
COUNTERFACTUAL_PROPS = ("risk", "tool", "region", "signal")


def stable_int(*parts: Any) -> int:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def stable_id(*parts: Any) -> str:
    digest = hashlib.sha256("\n".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:20]
    return f"stage653_{digest}"


def finite_space(values: tuple[str, ...] | list[str]) -> dict[str, Any]:
    size = max(2, len(values))
    return {"type": "finite", "values": list(values), "size": size, "bits": math.log2(size)}


def unit(
    *,
    unit_type: str,
    domain: str,
    statement: str,
    answer: str,
    candidate_space: dict[str, Any],
    train_visible: bool,
    split: str,
    family: str,
    evidence: list[str],
    source_units: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    unit_id = stable_id(unit_type, domain, statement, answer)
    return {
        "unit_id": unit_id,
        "unit_type": unit_type,
        "unit_family": family,
        "domain": domain,
        "canonical_statement": statement,
        "answer": answer,
        "candidate_space": candidate_space,
        "evidence": evidence,
        "train_visibility": "train_visible" if train_visible else "hidden_eval",
        "generalization_split": split,
        "source_units": source_units or [],
        "metadata": metadata or {},
        "queries": [
            statement,
            f"In {domain}, return only the answer for: {statement}",
        ],
    }


def fact_answer(domain: str, entity: str, prop: str) -> str:
    values = VALUES[prop]
    return values[stable_int("fact", domain, entity, prop) % len(values)]


def entities(domain: str) -> list[str]:
    return [f"{domain}_e{i:03d}" for i in range(96)]


def build_units() -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    fact_index: dict[tuple[str, str, str], dict[str, Any]] = {}
    rel_index: dict[tuple[str, str, str], dict[str, Any]] = {}

    for domain in DOMAINS:
        domain_entities = entities(domain)
        hidden_entities = set(domain_entities[-24:])
        for entity in domain_entities:
            for prop in PROPERTIES:
                answer = fact_answer(domain, entity, prop)
                hidden_prop = prop in ("risk", "tool")
                hidden_entity = entity in hidden_entities and prop in ("region", "class", "signal", "unit")
                train_visible = not (hidden_prop or hidden_entity)
                split = "held_out_field" if hidden_prop else ("held_out_entity_field" if hidden_entity else "seen_entity_field")
                item = unit(
                    unit_type="atomic_fact",
                    domain=domain,
                    statement=f"{entity} has {prop}",
                    answer=answer,
                    candidate_space=finite_space(VALUES[prop]),
                    train_visible=train_visible,
                    split=split,
                    family="atomic_facts",
                    evidence=[f"{entity}.{prop}={answer}"],
                    metadata={"entity": entity, "property": prop},
                )
                units.append(item)
                fact_index[(domain, entity, prop)] = item

        for i, entity in enumerate(domain_entities):
            for rel, offset in (("linked_to", 7), ("owned_by", 19)):
                target = domain_entities[(i + offset + stable_int(domain, rel) % 11) % len(domain_entities)]
                hidden_rel = target in hidden_entities or (i % 5 == 0 and rel == "owned_by")
                item = unit(
                    unit_type="relation",
                    domain=domain,
                    statement=f"{entity} {rel}",
                    answer=target,
                    candidate_space=finite_space(domain_entities),
                    train_visible=not hidden_rel,
                    split="held_out_relation_target" if hidden_rel else "seen_relation",
                    family="relations_and_sets",
                    evidence=[f"{entity} {rel} {target}"],
                    metadata={"subject": entity, "relation": rel, "object": target},
                )
                units.append(item)
                rel_index[(domain, entity, rel)] = item

        for entity in domain_entities[::2]:
            for rel, prop in (
                ("linked_to", "risk"),
                ("owned_by", "tool"),
                ("linked_to", "color"),
                ("owned_by", "phase"),
            ):
                rel_unit = rel_index[(domain, entity, rel)]
                target = str(rel_unit["answer"])
                fact = fact_index[(domain, target, prop)]
                hidden = (
                    rel_unit["train_visibility"] != "train_visible"
                    or fact["train_visibility"] != "train_visible"
                    or stable_int("composition", domain, entity, rel, prop) % 3 == 0
                )
                units.append(
                    unit(
                        unit_type="composition",
                        domain=domain,
                        statement=f"{prop} of {rel} target for {entity}",
                        answer=str(fact["answer"]),
                        candidate_space=finite_space(VALUES[prop]),
                        train_visible=not hidden,
                        split="held_out_two_hop_composition" if hidden else "seen_two_hop_composition",
                        family="multi_hop_compositions",
                        evidence=[f"{entity}->{rel}->{target}", f"{target}.{prop}={fact['answer']}"],
                        source_units=[str(rel_unit["unit_id"]), str(fact["unit_id"])],
                        metadata={"subject": entity, "relation": rel, "property": prop, "depth": 2},
                    )
                )

        for prop in ("risk", "tool", "region", "signal"):
            for value in VALUES[prop][::8]:
                matching = [e for e in domain_entities if fact_answer(domain, e, prop) == value]
                answer = str(len(matching))
                hidden = stable_int("count", domain, prop, value) % 2 == 0
                units.append(
                    unit(
                        unit_type="composition",
                        domain=domain,
                        statement=f"count entities where {prop} is {value}",
                        answer=answer,
                        candidate_space={"type": "integer_range", "size": 128, "bits": math.log2(128), "range": [0, 127]},
                        train_visible=not hidden,
                        split="held_out_set_count" if hidden else "seen_set_count",
                        family="relations_and_sets",
                        evidence=[f"count({domain}.{prop}={value})={answer}"],
                        metadata={"property": prop, "value": value, "operation": "set_count"},
                    )
                )

        for entity in domain_entities[:48]:
            for prop in COUNTERFACTUAL_PROPS:
                correct = fact_answer(domain, entity, prop)
                wrong = VALUES[prop][(VALUES[prop].index(correct) + 17) % len(VALUES[prop])]
                hidden = stable_int("counterfactual", domain, entity, prop) % 3 != 0
                fact = fact_index[(domain, entity, prop)]
                units.append(
                    unit(
                        unit_type="counterfactual_false_claim",
                        domain=domain,
                        statement=f"claim {entity} has {prop} {wrong}; correct {prop}",
                        answer=correct,
                        candidate_space=finite_space(VALUES[prop]),
                        train_visible=not hidden,
                        split="held_out_near_negative" if hidden else "seen_near_negative",
                        family="counterfactual_and_negative_knowledge",
                        evidence=[f"claimed={wrong}", f"correct={correct}"],
                        source_units=[str(fact["unit_id"])],
                        metadata={"entity": entity, "property": prop, "claimed": wrong},
                    )
                )

        for prop in ("risk", "tool"):
            default = VALUES[prop][stable_int("default", domain, prop) % len(VALUES[prop])]
            schema = unit(
                unit_type="schema",
                domain=domain,
                statement=f"default {prop} policy for {domain}",
                answer=default,
                candidate_space=finite_space(VALUES[prop]),
                train_visible=True,
                split="seen_schema_default",
                family="abstractions",
                evidence=[f"default({domain}.{prop})={default}"],
                metadata={"property": prop},
            )
            units.append(schema)
            for entity in domain_entities[-8:]:
                override = fact_answer(domain, entity, prop)
                units.append(
                    unit(
                        unit_type="exception",
                        domain=domain,
                        statement=f"{entity} overrides default {prop}",
                        answer=override,
                        candidate_space=finite_space(VALUES[prop]),
                        train_visible=False,
                        split="held_out_exception_override",
                        family="abstractions",
                        evidence=[f"default={default}", f"{entity}.{prop}={override}"],
                        source_units=[str(schema["unit_id"]), str(fact_index[(domain, entity, prop)]["unit_id"])],
                        metadata={"entity": entity, "property": prop},
                    )
                )

    for i in range(2048):
        a = i % 257
        b = (i * 17 + 13) % 251
        answer = str((a * b + 3 * a + b) % 4096)
        hidden = i % 4 == 0 or i % 11 == 0
        units.append(
            unit(
                unit_type="math_identity",
                domain="math",
                statement=f"compute h(a,b)=(a*b+3*a+b) mod 4096 for a={a} b={b}",
                answer=answer,
                candidate_space={"type": "integer_range", "size": 4096, "bits": math.log2(4096), "range": [0, 4095]},
                train_visible=not hidden,
                split="held_out_parameters" if hidden else "seen_formula",
                family="procedures",
                evidence=[f"({a}*{b}+3*{a}+{b}) mod 4096={answer}"],
                metadata={"a": a, "b": b, "formula": "h"},
            )
        )

    api_behaviors = tuple(f"api_behavior_{i:02d}" for i in range(64))
    for i in range(1024):
        api = f"api_{i:04d}"
        behavior = api_behaviors[stable_int("api", api) % len(api_behaviors)]
        hidden = i % 5 == 0
        units.append(
            unit(
                unit_type="code_api_semantics",
                domain="code",
                statement=f"behavior of {api}",
                answer=behavior,
                candidate_space=finite_space(api_behaviors),
                train_visible=not hidden,
                split="held_out_api_name" if hidden else "seen_api_name",
                family="procedures",
                evidence=[f"{api} -> {behavior}"],
                metadata={"api": api},
            )
        )

    return units


def retrieval_row(item: dict[str, Any]) -> dict[str, Any]:
    op = str(item["unit_type"])
    family = str(item["unit_family"])
    domain = str(item["domain"])
    statement = str(item["canonical_statement"])
    answer = str(item["answer"])
    unit_id = str(item["unit_id"])
    key = f"stage653|{family}|{domain}"
    query = f"<AK_OP_{op.upper()}> op={op} family={family} collision_key={key} domain={domain} qid={unit_id} query={statement}"
    doc = f"<AK_OP_{op.upper()}> op={op} family={family} collision_key={key} domain={domain} qid={unit_id} answer={answer} statement={statement}"
    return {
        "example_id": unit_id,
        "source_id": unit_id,
        "source_type": "stage653_generalized_8kbpp_surface",
        "operation": op,
        "task_type": "active_agent_json",
        "encoder_text": f"<AK_QUERY> {query}\n<AK_SUPPORT> {doc}",
        "decoder_text": f"collision_key={key} <AK_STRUCTURED> <AK_ACTION_RESPOND> <AK_TASK_TYPE> active_agent_json <AK_CONTENT> {answer} </AK_CONTENT> <AK_END>",
        "json_decoder_text": f"collision_key={key} {{\"action\":\"respond\",\"content\":\"{answer}\"}}",
        "negative_decoder_text": f"collision_key={key} ",
        "retrieval_query_text": query,
        "retrieval_doc_text": doc,
        "state_text": doc,
        "expected_content": answer,
        "stage653_unit_family": family,
        "stage653_generalization_split": item["generalization_split"],
        "stage653_verified_bits_if_correct": item["candidate_space"]["bits"],
        "collision_conditioned": True,
        "collision_key_name": "collision_key",
        "collision_key_value": key,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def summarize(units: list[dict[str, Any]]) -> dict[str, Any]:
    by_family: dict[str, dict[str, Any]] = {}
    by_type: dict[str, dict[str, Any]] = {}
    by_split: dict[str, dict[str, Any]] = {}
    collision_groups: dict[str, int] = defaultdict(int)
    eval_units = [u for u in units if u["train_visibility"] != "train_visible"]
    for item in units:
        bits = float(item["candidate_space"]["bits"]) if item["train_visibility"] != "train_visible" else 0.0
        for table, key in (
            (by_family, str(item["unit_family"])),
            (by_type, str(item["unit_type"])),
            (by_split, str(item["generalization_split"])),
        ):
            slot = table.setdefault(key, {"total": 0, "train": 0, "eval": 0, "eval_bits": 0.0})
            slot["total"] += 1
            if item["train_visibility"] == "train_visible":
                slot["train"] += 1
            else:
                slot["eval"] += 1
                slot["eval_bits"] += bits
        if item["train_visibility"] != "train_visible":
            collision_groups[f"{item['unit_family']}|{item['domain']}"] += 1
    sizes = list(collision_groups.values())
    total_eval_bits = sum(float(u["candidate_space"]["bits"]) for u in eval_units)
    return {
        "total_units": len(units),
        "train_units": len(units) - len(eval_units),
        "eval_units": len(eval_units),
        "total_eval_verified_bits_available": total_eval_bits,
        "perfect_ceiling_kbpp_at_16280_params": total_eval_bits / PARAMS,
        "target_kbpp": TARGET_KBPP,
        "target_verified_bits": MIN_BITS,
        "target_margin_bits": total_eval_bits - MIN_BITS,
        "target_margin_multiplier": total_eval_bits / MIN_BITS,
        "by_unit_family": dict(sorted(by_family.items())),
        "by_unit_type": dict(sorted(by_type.items())),
        "by_generalization_split": dict(sorted(by_split.items())),
        "collision_conditioning": {
            "eval_groups": len(sizes),
            "eval_rows_in_collision_groups": sum(size for size in sizes if size > 1),
            "groups_with_collisions": sum(1 for size in sizes if size > 1),
            "mean_candidate_count": sum(sizes) / len(sizes) if sizes else 0.0,
            "max_candidate_count": max(sizes) if sizes else 0,
        },
    }


def write_outputs(units: list[dict[str, Any]]) -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    train = [u for u in units if u["train_visibility"] == "train_visible"]
    eval_units = [u for u in units if u["train_visibility"] != "train_visible"]
    paths = {
        "all_units_path": OUT / "knowledge_units.jsonl",
        "train_units_path": OUT / "knowledge_units_train.jsonl",
        "eval_units_path": OUT / "knowledge_units_eval.jsonl",
        "eval_queries_path": OUT / "general_kbpp_eval_queries.jsonl",
        "train_dataset_path": OUT / "agentkernel_lite_encdec_train.jsonl",
        "eval_dataset_path": OUT / "agentkernel_lite_encdec_eval.jsonl",
    }
    write_jsonl(paths["all_units_path"], units)
    write_jsonl(paths["train_units_path"], train)
    write_jsonl(paths["eval_units_path"], eval_units)
    write_jsonl(paths["train_dataset_path"], [retrieval_row(u) for u in train])
    write_jsonl(paths["eval_dataset_path"], [retrieval_row(u) for u in eval_units])
    write_jsonl(
        paths["eval_queries_path"],
        [
            {
                "unit_id": u["unit_id"],
                "unit_type": u["unit_type"],
                "unit_family": u["unit_family"],
                "domain": u["domain"],
                "query": u["queries"][0],
                "answer": u["answer"],
                "candidate_space": u["candidate_space"],
                "verified_bits_if_correct": u["candidate_space"]["bits"],
                "source_units": u["source_units"],
                "generalization_split": u["generalization_split"],
            }
            for u in eval_units
        ],
    )
    stats = summarize(units)
    manifest = {
        "artifact_kind": "agentkernel_lite_encdec_stage653_generalized_8kbpp_surface",
        "timestamp": int(time.time()),
        "manifest_path": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
        **{key: str(path) for key, path in paths.items()},
        "train_examples": len(train),
        "eval_examples": len(eval_units),
        "parameter_reference_count": PARAMS,
        "stage653_goal": "First generalized rung with enough verified hidden entropy for an 8 no-filter KBPP ceiling at 16k.",
        "acceptance_gates": {
            "perfect_ceiling_kbpp_at_16280_params": ">= 8.0",
            "initialized_no_filter_answer_kbpp": ">= 8.0 before accepting the rung",
            "hard_filter_only_gain_counts": False,
            "required_hidden_families": [
                "atomic_facts",
                "relations_and_sets",
                "multi_hop_compositions",
                "procedures",
                "abstractions",
                "counterfactual_and_negative_knowledge",
            ],
        },
        **stats,
    }
    manifest_path = OUT / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ARTIFACT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def write_doc(manifest: dict[str, Any]) -> None:
    families = manifest["by_unit_family"]
    lines = [
        "# Stage653 Generalized 8 KBPP Surface",
        "",
        f"Artifact: `{ARTIFACT.relative_to(ROOT)}`",
        "",
        "## Result",
        "",
        f"- Eval units: `{manifest['eval_units']}`",
        f"- Train units: `{manifest['train_units']}`",
        f"- Verified hidden eval bits: `{manifest['total_eval_verified_bits_available']}`",
        f"- Perfect ceiling at 16,280 params: `{manifest['perfect_ceiling_kbpp_at_16280_params']}` KBPP",
        f"- 8 KBPP target bits: `{manifest['target_verified_bits']}`",
        f"- Target margin: `{manifest['target_margin_bits']}` bits (`{manifest['target_margin_multiplier']}`x)",
        "",
        "## Family Mix",
        "",
        "| family | train | eval | eval bits |",
        "|---|---:|---:|---:|",
    ]
    for family, stats in families.items():
        lines.append(f"| `{family}` | {stats['train']} | {stats['eval']} | {stats['eval_bits']} |")
    lines.extend(
        [
            "",
            "## Collision Conditioning",
            "",
            f"- Eval collision groups: `{manifest['collision_conditioning']['eval_groups']}`",
            f"- Groups with collisions: `{manifest['collision_conditioning']['groups_with_collisions']}`",
            f"- Rows in collision groups: `{manifest['collision_conditioning']['eval_rows_in_collision_groups']}`",
            f"- Mean candidate count: `{manifest['collision_conditioning']['mean_candidate_count']}`",
            f"- Max candidate count: `{manifest['collision_conditioning']['max_candidate_count']}`",
            "",
            "## Decision",
            "",
            "Stage653 establishes the next entropy rung. It is accepted as a surface only, not as a trained-model win. The next required step is a 16k initialized no-filter training probe on this manifest, scored by `scripts/score_general_kbpp_eval.py` and the retrieval evaluator. Hard-filter-only recovery remains excluded from neural KBPP.",
        ]
    )
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    units = build_units()
    manifest = write_outputs(units)
    write_doc(manifest)
    print(
        json.dumps(
            {
                "manifest": manifest["manifest_path"],
                "artifact": str(ARTIFACT),
                "doc": str(DOC),
                "eval_bits": manifest["total_eval_verified_bits_available"],
                "perfect_ceiling_kbpp": manifest["perfect_ceiling_kbpp_at_16280_params"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
