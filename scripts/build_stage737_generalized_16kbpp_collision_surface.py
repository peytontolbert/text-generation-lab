#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PARAMS = 16794
TARGET_KBPP = 16.0


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stage653 = load_module(ROOT / "scripts/build_stage653_generalized_8kbpp_surface.py", "stage653_stage737")
stage655 = load_module(ROOT / "scripts/build_stage655_generalized_bridge_curriculum.py", "stage655_stage737")
stage659 = load_module(ROOT / "scripts/build_stage659_balanced_generalized_8kbpp_surface.py", "stage659_stage737")
stage726 = load_module(ROOT / "scripts/build_stage726_selector_collision_factor_surface.py", "stage726_stage737")
stage734 = load_module(ROOT / "scripts/build_stage734_qidless_collision_audit.py", "stage734_stage737")
stage735 = load_module(ROOT / "scripts/build_stage735_heldout_entity_alias_audit.py", "stage735_stage737")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def qidless_row(row: dict[str, Any]) -> dict[str, Any]:
    return stage734.rewrite_row(row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domains", type=int, default=120)
    parser.add_argument("--output-dir", default="runs/local/tmp/stage737_generalized_16kbpp_collision_surface")
    parser.add_argument("--artifact-json", default="runs/local/artifacts/stage737_generalized_16kbpp_collision_surface.json")
    args = parser.parse_args()

    stage653.DOMAINS = tuple(f"gdom_{i:03d}" for i in range(int(args.domains)))
    units = [stage659.rebalance_unit(unit) for unit in stage653.build_units()]
    train_units = [unit for unit in units if unit["train_visibility"] == "train_visible"]
    eval_units = [unit for unit in units if unit["train_visibility"] != "train_visible"]

    train_rows = [
        qidless_row(stage726.rewrite_row(stage655.rewrite_row(stage653.retrieval_row(unit))))
        for unit in train_units
    ]
    eval_rows = [
        qidless_row(stage726.rewrite_row(stage655.rewrite_row(stage653.retrieval_row(unit))))
        for unit in eval_units
    ]
    aliased_eval_rows, entity_aliases, alias_replacements = stage735.alias_entities(eval_rows)

    out = (ROOT / args.output_dir).resolve()
    train_path = out / "agentkernel_lite_encdec_train.jsonl"
    eval_path = out / "agentkernel_lite_encdec_eval.jsonl"
    units_path = out / "knowledge_units.jsonl"
    train_units_path = out / "knowledge_units_train.jsonl"
    eval_units_path = out / "knowledge_units_eval.jsonl"
    write_jsonl(units_path, units)
    write_jsonl(train_units_path, train_units)
    write_jsonl(eval_units_path, eval_units)
    write_jsonl(train_path, train_rows)
    write_jsonl(eval_path, aliased_eval_rows)

    eval_bits = sum(float(row.get("stage653_verified_bits_if_correct", 0.0) or 0.0) for row in aliased_eval_rows)
    collision_stats = stage726.collision_stats(aliased_eval_rows)
    manifest = {
        "artifact_kind": "agentkernel_lite_encdec_stage737_generalized_16kbpp_collision_surface",
        "timestamp": int(time.time()),
        "manifest_path": str(out / "agentkernel_lite_encdec_dataset_manifest.json"),
        "all_units_path": str(units_path),
        "train_units_path": str(train_units_path),
        "eval_units_path": str(eval_units_path),
        "train_dataset_path": str(train_path),
        "eval_dataset_path": str(eval_path),
        "train_examples": len(train_rows),
        "eval_examples": len(aliased_eval_rows),
        "domains": int(args.domains),
        "total_eval_verified_bits_available": eval_bits,
        "perfect_ceiling_kbpp_at_16794_params": eval_bits / PARAMS,
        "target_kbpp": TARGET_KBPP,
        "target_verified_bits_at_16794_params": TARGET_KBPP * PARAMS,
        "target_margin_bits": eval_bits - TARGET_KBPP * PARAMS,
        "qidless": True,
        "heldout_entity_alias_eval": True,
        "eval_distinct_entities_aliased": len(entity_aliases),
        "eval_entity_alias_replacements": alias_replacements,
        "eval_collision_stats": collision_stats,
        "acceptance_gates": {
            "trained_or_scored_no_filter_answer_kbpp": ">= 16.0",
            "qidless_text": True,
            "heldout_entity_alias_eval": True,
            "allowed_factor_key_has_collisions": True,
            "full_selector_identity_counts": False
        },
    }
    manifest_path = out / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "artifact": str(artifact_path),
        "manifest": str(manifest_path),
        "train_examples": len(train_rows),
        "eval_examples": len(aliased_eval_rows),
        "perfect_ceiling_kbpp_at_16794_params": eval_bits / PARAMS,
        "eval_distinct_entities_aliased": len(entity_aliases),
        "eval_collision_selectors": collision_stats["collision_selectors"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
