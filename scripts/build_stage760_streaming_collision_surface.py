#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
PARAMS = 16794
TARGET_KBPP = 512.0
ENTITY_RE = re.compile(r"\b(gdom_\d+_e\d+)\b")
TEXT_FIELDS = {
    "decoder_text",
    "encoder_text",
    "json_decoder_text",
    "negative_decoder_text",
    "retrieval_doc_text",
    "retrieval_query_text",
    "state_text",
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stage653 = load_module(ROOT / "scripts/build_stage653_generalized_8kbpp_surface.py", "stage653_stage760")
stage655 = load_module(ROOT / "scripts/build_stage655_generalized_bridge_curriculum.py", "stage655_stage760")
stage659 = load_module(ROOT / "scripts/build_stage659_balanced_generalized_8kbpp_surface.py", "stage659_stage760")
stage726 = load_module(ROOT / "scripts/build_stage726_selector_collision_factor_surface.py", "stage726_stage760")
stage734 = load_module(ROOT / "scripts/build_stage734_qidless_collision_audit.py", "stage734_stage760")


def chunked(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def qidless_collision_row(unit: dict[str, Any]) -> dict[str, Any]:
    return stage734.rewrite_row(stage726.rewrite_row(stage655.rewrite_row(stage653.retrieval_row(unit))))


def alias_for_entity(entity: str) -> str:
    digest = hashlib.sha256(entity.encode("utf-8")).hexdigest()
    return f"gdom_999_e{int(digest[:16], 16):020d}"


def alias_eval_row(row: dict[str, Any]) -> tuple[dict[str, Any], int, set[str]]:
    out = dict(row)
    row_replaced = 0
    row_entities: set[str] = set()
    for field in TEXT_FIELDS:
        if field not in out:
            continue

        def repl(match: re.Match[str]) -> str:
            nonlocal row_replaced
            entity = match.group(1)
            row_entities.add(entity)
            row_replaced += 1
            return alias_for_entity(entity)

        out[field] = ENTITY_RE.sub(repl, str(out.get(field, "") or ""))
    out["stage735_heldout_entity_alias_audit"] = True
    out["stage735_entity_alias_replacements"] = row_replaced
    out["stage760_deterministic_hash_entity_alias"] = True
    return out, row_replaced, row_entities


def write_jsonl_row(handle, row: dict[str, Any]) -> None:
    handle.write(json.dumps(row, sort_keys=True) + "\n")


def update_collision_counts(
    row: dict[str, Any],
    counts: Counter[str],
    by_operation: dict[str, Counter[str]],
) -> None:
    selector = str(row.get("stage726_collision_gsel", "") or "")
    if not selector:
        return
    counts[selector] += 1
    by_operation[str(row.get("operation", "") or "unknown")][selector] += 1


def summarize_collision_counts(
    *,
    rows: int,
    counts: Counter[str],
    by_operation: dict[str, Counter[str]],
) -> dict[str, Any]:
    return {
        "rows": rows,
        "distinct_collision_selectors": len(counts),
        "singleton_selectors": sum(1 for value in counts.values() if value == 1),
        "collision_selectors": sum(1 for value in counts.values() if value > 1),
        "rows_in_collision_selectors": sum(value for value in counts.values() if value > 1),
        "max_candidate_count": max(counts.values()) if counts else 0,
        "mean_candidate_count": (sum(counts.values()) / len(counts)) if counts else 0.0,
        "by_operation": {
            operation: {
                "rows": sum(counter.values()),
                "distinct_collision_selectors": len(counter),
                "singleton_selectors": sum(1 for value in counter.values() if value == 1),
                "collision_selectors": sum(1 for value in counter.values() if value > 1),
                "rows_in_collision_selectors": sum(value for value in counter.values() if value > 1),
                "max_candidate_count": max(counter.values()) if counter else 0,
                "mean_candidate_count": (sum(counter.values()) / len(counter)) if counter else 0.0,
            }
            for operation, counter in sorted(by_operation.items())
        },
    }


def update_breakdowns(row: dict[str, Any], bits: float, table: dict[str, dict[str, Any]]) -> None:
    for field in ("stage653_unit_family", "operation", "stage653_generalization_split"):
        key = str(row.get(field, "") or "unknown")
        slot = table.setdefault(key, {"rows": 0, "eval_bits": 0.0})
        slot["rows"] += 1
        slot["eval_bits"] += bits


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domains", type=int, default=2816)
    parser.add_argument("--chunk-size", type=int, default=96)
    parser.add_argument("--output-dir", default="runs/local/tmp/stage760_streaming_512kbpp_collision_surface_d2816")
    parser.add_argument("--artifact-json", default="runs/local/artifacts/stage760_streaming_512kbpp_collision_surface_d2816.json")
    parser.add_argument("--target-kbpp", type=float, default=TARGET_KBPP)
    args = parser.parse_args()

    domains = [f"gdom_{i:03d}" for i in range(int(args.domains))]
    out = (ROOT / args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    train_path = out / "agentkernel_lite_encdec_train.jsonl"
    eval_path = out / "agentkernel_lite_encdec_eval.jsonl"

    train_rows = 0
    eval_rows = 0
    eval_bits = 0.0
    alias_replacements = 0
    aliased_entities: set[str] = set()
    eval_collision_counts: Counter[str] = Counter()
    eval_collision_by_operation: dict[str, Counter[str]] = defaultdict(Counter)
    train_collision_counts: Counter[str] = Counter()
    train_collision_by_operation: dict[str, Counter[str]] = defaultdict(Counter)
    eval_breakdowns: dict[str, dict[str, Any]] = {}

    with train_path.open("w", encoding="utf-8") as train_handle, eval_path.open("w", encoding="utf-8") as eval_handle:
        for chunk_index, domain_chunk in enumerate(chunked(domains, max(1, int(args.chunk_size)))):
            stage653.DOMAINS = tuple(domain_chunk)
            for raw_unit in stage653.build_units():
                if raw_unit.get("domain") in {"math", "code"} and chunk_index > 0:
                    continue
                unit = stage659.rebalance_unit(raw_unit)
                row = qidless_collision_row(unit)
                if unit["train_visibility"] == "train_visible":
                    write_jsonl_row(train_handle, row)
                    train_rows += 1
                    update_collision_counts(row, train_collision_counts, train_collision_by_operation)
                    continue

                aliased, replacements, row_entities = alias_eval_row(row)
                write_jsonl_row(eval_handle, aliased)
                eval_rows += 1
                bits = float(aliased.get("stage653_verified_bits_if_correct", 0.0) or 0.0)
                eval_bits += bits
                alias_replacements += replacements
                aliased_entities.update(row_entities)
                update_collision_counts(aliased, eval_collision_counts, eval_collision_by_operation)
                update_breakdowns(aliased, bits, eval_breakdowns)

    manifest = {
        "artifact_kind": "agentkernel_lite_encdec_stage760_streaming_512kbpp_collision_surface",
        "timestamp": int(time.time()),
        "manifest_path": str(out / "agentkernel_lite_encdec_dataset_manifest.json"),
        "train_dataset_path": str(train_path),
        "eval_dataset_path": str(eval_path),
        "train_examples": train_rows,
        "eval_examples": eval_rows,
        "domains": int(args.domains),
        "chunk_size": int(args.chunk_size),
        "parameter_reference_count": PARAMS,
        "total_eval_verified_bits_available": eval_bits,
        "perfect_ceiling_kbpp_at_16794_params": eval_bits / PARAMS,
        "target_kbpp": float(args.target_kbpp),
        "target_verified_bits_at_16794_params": float(args.target_kbpp) * PARAMS,
        "target_margin_bits": eval_bits - float(args.target_kbpp) * PARAMS,
        "qidless": True,
        "heldout_entity_alias_eval": True,
        "deterministic_hash_entity_alias_eval": True,
        "eval_distinct_entities_aliased": len(aliased_entities),
        "eval_entity_alias_replacements": alias_replacements,
        "eval_collision_stats": summarize_collision_counts(
            rows=eval_rows,
            counts=eval_collision_counts,
            by_operation=eval_collision_by_operation,
        ),
        "train_collision_stats": summarize_collision_counts(
            rows=train_rows,
            counts=train_collision_counts,
            by_operation=train_collision_by_operation,
        ),
        "eval_breakdowns": dict(sorted(eval_breakdowns.items())),
        "acceptance_gates": {
            "trained_or_scored_no_filter_answer_kbpp": f">= {float(args.target_kbpp)}",
            "qidless_text": True,
            "heldout_entity_alias_eval": True,
            "allowed_factor_key_has_collisions": True,
            "full_selector_identity_counts": False,
            "streamed_generation_changes_scoring": False,
        },
    }
    manifest_path = out / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "artifact": str(artifact_path),
                "manifest": str(manifest_path),
                "train_examples": train_rows,
                "eval_examples": eval_rows,
                "perfect_ceiling_kbpp_at_16794_params": eval_bits / PARAMS,
                "target_margin_bits": manifest["target_margin_bits"],
                "eval_distinct_entities_aliased": len(aliased_entities),
                "eval_collision_selectors": manifest["eval_collision_stats"]["collision_selectors"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
