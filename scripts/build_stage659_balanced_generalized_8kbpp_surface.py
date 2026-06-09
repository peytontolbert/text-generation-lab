#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_UNITS = ROOT / "runs/local/tmp/stage653_generalized_8kbpp_surface/knowledge_units.jsonl"
OUT = ROOT / "runs/local/tmp/stage659_balanced_generalized_8kbpp_surface"
ARTIFACT = ROOT / "runs/local/artifacts/stage659_balanced_generalized_8kbpp_surface.json"
DOC = ROOT / "docs/stage659_balanced_generalized_8kbpp_surface.md"
PARAMS = 16280
TARGET_KBPP = 8.0
MIN_BITS = PARAMS * TARGET_KBPP


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stage653 = load_module(ROOT / "scripts/build_stage653_generalized_8kbpp_surface.py", "stage653_builder")
stage655 = load_module(ROOT / "scripts/build_stage655_generalized_bridge_curriculum.py", "stage655_builder")


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def entity_index(entity: str) -> int:
    try:
        return int(str(entity).rsplit("_e", 1)[1])
    except Exception:
        return 0


def rebalance_unit(unit: dict[str, Any]) -> dict[str, Any]:
    out = dict(unit)
    unit_type = str(unit.get("unit_type", "") or "")
    family = str(unit.get("unit_family", "") or "")
    domain = str(unit.get("domain", "") or "")
    metadata = dict(unit.get("metadata", {}) or {})
    statement = str(unit.get("canonical_statement", "") or "")
    answer = str(unit.get("answer", "") or "")
    hidden = False
    split = "seen_balanced"

    if unit_type == "atomic_fact":
        entity = str(metadata.get("entity", ""))
        prop = str(metadata.get("property", ""))
        idx = entity_index(entity)
        hidden = idx >= 72 or stage653.stable_int("stage659_atomic", domain, entity, prop) % 8 == 0
        split = "held_out_entity_binding" if idx >= 72 else ("held_out_seen_entity_binding" if hidden else "seen_entity_field")
    elif unit_type == "relation":
        subject = str(metadata.get("subject", ""))
        obj = str(metadata.get("object", ""))
        hidden = entity_index(obj) >= 72 or stage653.stable_int("stage659_relation", domain, subject, obj) % 7 == 0
        split = "held_out_relation_binding" if hidden else "seen_relation"
    elif unit_type == "composition":
        if metadata.get("operation") == "set_count":
            prop = str(metadata.get("property", ""))
            value = str(metadata.get("value", ""))
            hidden = stage653.stable_int("stage659_set_count", domain, prop, value) % 3 == 0
            split = "held_out_set_count_binding" if hidden else "seen_set_count"
        else:
            subject = str(metadata.get("subject", ""))
            relation = str(metadata.get("relation", ""))
            prop = str(metadata.get("property", ""))
            hidden = entity_index(subject) >= 72 or stage653.stable_int("stage659_comp", domain, subject, relation, prop) % 4 == 0
            split = "held_out_two_hop_binding" if hidden else "seen_two_hop_composition"
    elif unit_type == "counterfactual_false_claim":
        entity = str(metadata.get("entity", ""))
        prop = str(metadata.get("property", ""))
        hidden = entity_index(entity) >= 36 or stage653.stable_int("stage659_negative", domain, entity, prop, answer) % 5 == 0
        split = "held_out_near_negative_binding" if hidden else "seen_near_negative"
    elif unit_type == "exception":
        entity = str(metadata.get("entity", ""))
        prop = str(metadata.get("property", ""))
        hidden = entity_index(entity) % 2 == 0
        split = "held_out_exception_binding" if hidden else "seen_exception_override"
    elif unit_type == "math_identity":
        hidden = stage653.stable_int("stage659_math", statement, answer) % 5 == 0
        split = "held_out_parameters" if hidden else "seen_formula"
    elif unit_type == "code_api_semantics":
        api = str(metadata.get("api", ""))
        hidden = stage653.stable_int("stage659_api", api) % 5 == 0
        split = "held_out_api_name" if hidden else "seen_api_name"
    else:
        hidden = stage653.stable_int("stage659_misc", family, domain, statement, answer) % 5 == 0
        split = "held_out_balanced_misc" if hidden else "seen_balanced_misc"

    out["train_visibility"] = "hidden_eval" if hidden else "train_visible"
    out["generalization_split"] = split
    out["stage659_balanced_split"] = True
    return out


def summarize(units: list[dict[str, Any]]) -> dict[str, Any]:
    tables: dict[str, dict[str, dict[str, Any]]] = {
        "by_unit_family": {},
        "by_unit_type": {},
        "by_generalization_split": {},
    }
    train_schema: dict[str, Counter[str]] = defaultdict(Counter)
    eval_schema: dict[str, Counter[str]] = defaultdict(Counter)
    eval_bits = 0.0
    eval_units = 0
    for unit in units:
        is_eval = unit["train_visibility"] != "train_visible"
        bits = float(unit["candidate_space"]["bits"]) if is_eval else 0.0
        eval_bits += bits
        eval_units += int(is_eval)
        for table_name, key in (
            ("by_unit_family", str(unit.get("unit_family", ""))),
            ("by_unit_type", str(unit.get("unit_type", ""))),
            ("by_generalization_split", str(unit.get("generalization_split", ""))),
        ):
            slot = tables[table_name].setdefault(key, {"total": 0, "train": 0, "eval": 0, "eval_bits": 0.0})
            slot["total"] += 1
            if is_eval:
                slot["eval"] += 1
                slot["eval_bits"] += bits
            else:
                slot["train"] += 1
        metadata = dict(unit.get("metadata", {}) or {})
        prop = str(metadata.get("property", metadata.get("relation", unit.get("unit_type", ""))))
        target = eval_schema if is_eval else train_schema
        target[str(unit.get("unit_family", ""))][prop] += 1
    schema_coverage = {
        family: {
            "train_schema_keys": sorted(train_schema.get(family, {}).keys()),
            "eval_schema_keys": sorted(eval_schema.get(family, {}).keys()),
        }
        for family in sorted(set(train_schema) | set(eval_schema))
    }
    return {
        "total_units": len(units),
        "train_units": len(units) - eval_units,
        "eval_units": eval_units,
        "total_eval_verified_bits_available": eval_bits,
        "perfect_ceiling_kbpp_at_16280_params": eval_bits / PARAMS,
        "target_kbpp": TARGET_KBPP,
        "target_verified_bits": MIN_BITS,
        "target_margin_bits": eval_bits - MIN_BITS,
        "target_margin_multiplier": eval_bits / MIN_BITS,
        **{name: dict(sorted(table.items())) for name, table in tables.items()},
        "schema_coverage": schema_coverage,
    }


def main() -> None:
    units = [rebalance_unit(unit) for unit in iter_jsonl(SOURCE_UNITS)]
    OUT.mkdir(parents=True, exist_ok=True)
    train = [unit for unit in units if unit["train_visibility"] == "train_visible"]
    eval_units = [unit for unit in units if unit["train_visibility"] != "train_visible"]

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
    write_jsonl(
        paths["eval_queries_path"],
        [
            {
                "unit_id": unit["unit_id"],
                "unit_type": unit["unit_type"],
                "unit_family": unit["unit_family"],
                "domain": unit["domain"],
                "query": unit["queries"][0],
                "answer": unit["answer"],
                "candidate_space": unit["candidate_space"],
                "verified_bits_if_correct": unit["candidate_space"]["bits"],
                "source_units": unit["source_units"],
                "generalization_split": unit["generalization_split"],
            }
            for unit in eval_units
        ],
    )

    train_rows = [stage655.rewrite_row(stage653.retrieval_row(unit)) for unit in train]
    eval_rows = [stage655.rewrite_row(stage653.retrieval_row(unit)) for unit in eval_units]
    write_jsonl(paths["train_dataset_path"], train_rows)
    write_jsonl(paths["eval_dataset_path"], eval_rows)

    stats = summarize(units)
    manifest = {
        "artifact_kind": "agentkernel_lite_encdec_stage659_balanced_generalized_8kbpp_surface",
        "timestamp": int(time.time()),
        "source_units_path": str(SOURCE_UNITS),
        "manifest_path": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
        **{key: str(path) for key, path in paths.items()},
        "train_examples": len(train),
        "eval_examples": len(eval_units),
        "stage659_balanced_split": True,
        "stage659_goal": "Balance generalized KBPP so every schema family appears in train while eval holds out bindings/entities/compositions.",
        "acceptance_gates": {
            "perfect_ceiling_kbpp_at_16280_params": ">= 8.0",
            "trained_no_filter_answer_kbpp": ">= 8.0",
            "hard_filter_only_gain_counts": False,
        },
        **stats,
    }
    manifest_path = OUT / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ARTIFACT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        f"""# Stage659 Balanced Generalized 8 KBPP Surface

Artifact: `{ARTIFACT.relative_to(ROOT)}`

Manifest: `{manifest_path.relative_to(ROOT)}`

## Result

- Train units: `{manifest['train_units']}`
- Eval units: `{manifest['eval_units']}`
- Hidden eval bits: `{manifest['total_eval_verified_bits_available']}`
- Perfect ceiling: `{manifest['perfect_ceiling_kbpp_at_16280_params']}` KBPP
- Target margin: `{manifest['target_margin_bits']}` bits (`{manifest['target_margin_multiplier']}`x)

## Change

Stage659 corrects the Stage653/655 split. It no longer holds out whole field families such as `risk` or `tool`. Every schema family appears in train; eval holds out bindings, entities, relations, set counts, compositions, parameters, and API names.

The retrieval rows keep Stage655-style compact `gsel=` selectors. Acceptance still requires no-filter generalized answer KBPP `>= 8.0`.
""",
        encoding="utf-8",
    )
    print(json.dumps({"artifact": str(ARTIFACT), "manifest": str(manifest_path), "doc": str(DOC), "eval_bits": stats["total_eval_verified_bits_available"], "kbpp": stats["perfect_ceiling_kbpp_at_16280_params"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
