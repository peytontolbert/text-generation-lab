#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/local/tmp/stage644_semantic_ops_72_domain_seed461_base/agentkernel_lite_encdec_dataset_manifest.json"
OUT = ROOT / "runs/local/tmp/stage645_72domain_entity_field_selector_surface"
ARTIFACT = ROOT / "runs/local/artifacts/stage645_72domain_entity_field_selector_surface_dataset.json"
DOC = ROOT / "docs/stage645_72domain_entity_field_selector_surface.md"
FIELDS = ("capital", "currency", "continent", "owner", "status", "priority", "tool", "risk")
KEY_VALUE_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*?)=([^\s;]+)")
TEXT_FIELDS = {
    "decoder_text",
    "encoder_text",
    "json_decoder_text",
    "negative_decoder_text",
    "retrieval_doc_text",
    "retrieval_query_text",
    "state_text",
}
PARAMS = 16280


def stable_id(*parts: Any) -> str:
    return hashlib.sha256("\n".join(str(part) for part in parts).encode("utf-8")).hexdigest()


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


def key_values(text: str) -> dict[str, str]:
    return {str(key): str(value) for key, value in KEY_VALUE_RE.findall(str(text or ""))}


def inject_after_operation(text: str, op: str, marker: str) -> str:
    if not text or marker in text:
        return text
    op_token = f"<AK_OP_{op.upper()}>"
    op_match = re.search(rf"({re.escape(op_token)}|op={re.escape(op)})", text)
    if op_match:
        return text[: op_match.end()] + f" {marker}" + text[op_match.end() :]
    return f"{marker} {text}"


def marker_for(domain: str, field: str, entity: str) -> str:
    return f"{domain}|{field}|{entity}"


def rewrite_direct_fact(row: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query_keys = key_values(str(row.get("retrieval_query_text", "") or ""))
    doc_keys = key_values(str(row.get("retrieval_doc_text", "") or ""))
    keys = dict(doc_keys)
    keys.update(query_keys)
    domain = keys.get("domain", "")
    entity = keys.get("entity", "")
    field = keys.get("field", "")
    if not (domain and entity and field):
        return [dict(row)], {"changed": False}
    marker = marker_for(domain, field, entity)
    rewritten: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, str) and key in TEXT_FIELDS:
            rewritten[key] = inject_after_operation(value, "direct_fact", marker)
        else:
            rewritten[key] = value
    rewritten["stage645_field_lookup_selector_marker"] = marker
    rewritten["stage645_selector_template"] = "{domain}|{field}|{entity}"
    rewritten["source_type"] = f"{row.get('source_type', 'pocketpal_stage430_semantic_ops')}_stage645_field_selector"
    return [rewritten], {"changed": True, "marker": marker}


def expand_entity_context(row: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    doc_keys = key_values(str(row.get("retrieval_doc_text", "") or ""))
    domain = doc_keys.get("domain", "")
    entity = doc_keys.get("entity", "")
    if not (domain and entity):
        return [dict(row)], {"changed": False, "expanded": 1}

    expanded: list[dict[str, Any]] = []
    markers: list[str] = []
    for field in FIELDS:
        answer = doc_keys.get(field)
        if not answer:
            continue
        bind_key = f"collision_entity_context_field|{domain}|{field}"
        marker = marker_for(domain, field, entity)
        query = (
            f"<AK_OP_ENTITY_CONTEXT> {marker} op=entity_context bind_key={bind_key} "
            f"domain={domain} entity={entity} field={field}"
        )
        doc = (
            f"<AK_OP_ENTITY_CONTEXT> {marker} bind_key={bind_key} entity_context_field_card "
            f"domain={domain} entity={entity} field={field} answer={answer}"
        )
        decoder = (
            f"bind_key={bind_key} <AK_STRUCTURED> <AK_ACTION_RESPOND> <AK_TASK_TYPE> "
            f"{row.get('task_type', 'active_agent_json')} <AK_CONTENT> {answer} </AK_CONTENT> <AK_END>"
        )
        clone = dict(row)
        clone.update(
            {
                "collision_conditioned": True,
                "collision_key_name": "bind_key",
                "collision_key_value": bind_key,
                "decoder_text": decoder,
                "encoder_text": re.sub(
                    r"<AK_QUERY>.*?<AK_SUPPORT>",
                    f"<AK_QUERY> {query}\n<AK_SUPPORT>",
                    str(row.get("encoder_text", "") or ""),
                    flags=re.S,
                ),
                "entity_context_field_level": True,
                "entity_context_original_source_id": str(row.get("source_id", "") or ""),
                "entity_context_target_field": field,
                "example_id": stable_id("stage645_entity_field_selector", row.get("example_id"), field),
                "expected_content": answer,
                "json_decoder_text": f"bind_key={bind_key} {{\"action\":\"respond\",\"content\":\"{answer}\"}}",
                "negative_decoder_text": f"bind_key={bind_key} ",
                "retrieval_doc_text": doc,
                "retrieval_query_text": query,
                "source_id": f"{row.get('source_id', '')}__stage645_entity_field_{field}",
                "source_type": f"{row.get('source_type', 'pocketpal_stage430_semantic_ops')}_stage645_entity_field_selector",
                "stage645_field_lookup_selector_marker": marker,
                "stage645_selector_template": "{domain}|{field}|{entity}",
                "state_text": doc,
            }
        )
        expanded.append(clone)
        markers.append(marker)
    return expanded or [dict(row)], {"changed": bool(expanded), "expanded": len(expanded) or 1, "markers": markers}


def transform_row(row: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    op = str(row.get("operation", "") or "")
    if op == "direct_fact":
        return rewrite_direct_fact(row)
    if op == "entity_context":
        return expand_entity_context(row)
    return [dict(row)], {"changed": False}


def operation_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("operation", "") or "") for row in rows))


def selector_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("operation", "") or "") for row in rows if row.get("stage645_field_lookup_selector_marker")))


def entity_collision_analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, int] = defaultdict(int)
    for row in rows:
        if not row.get("entity_context_field_level"):
            continue
        bind_key = str(row.get("collision_key_value", "") or "")
        if bind_key:
            groups[bind_key] += 1
    sizes = list(groups.values())
    return {
        "field_level_rows": sum(sizes),
        "field_level_groups": len(sizes),
        "groups_with_collisions": sum(1 for size in sizes if size > 1),
        "collision_rows": sum(size for size in sizes if size > 1),
        "mean_candidate_count": (sum(sizes) / len(sizes)) if sizes else 0.0,
        "max_candidate_count": max(sizes) if sizes else 0,
    }


def row_token_stats(rows: list[dict[str, Any]]) -> dict[str, float]:
    if not rows:
        return {"avg_retrieval_tokens_per_pair": 0.0}
    total = 0
    for row in rows:
        total += len(str(row.get("retrieval_query_text", "") or "").split())
        total += len(str(row.get("retrieval_doc_text", "") or "").split())
    return {"avg_retrieval_tokens_per_pair": total / len(rows)}


def main() -> None:
    source_manifest = json.loads(SOURCE.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    split_paths: dict[str, Path] = {}
    split_stats: dict[str, Any] = {}
    op_counts: dict[str, Any] = {}
    selector_op_counts: dict[str, Any] = {}
    token_stats: dict[str, Any] = {}
    for split in ("train", "eval"):
        source_rows = list(iter_jsonl(Path(source_manifest[f"{split}_dataset_path"])))
        transformed: list[dict[str, Any]] = []
        changed = 0
        source_entity_rows = 0
        expanded_entity_rows = 0
        direct_fact_changed = 0
        markers: Counter[str] = Counter()
        for row in source_rows:
            op = str(row.get("operation", "") or "")
            converted, stats = transform_row(row)
            transformed.extend(converted)
            changed += int(bool(stats.get("changed")))
            if op == "entity_context":
                source_entity_rows += 1
                expanded_entity_rows += len(converted)
            if op == "direct_fact" and stats.get("changed"):
                direct_fact_changed += 1
            if stats.get("marker"):
                markers[str(stats["marker"])] += 1
            for marker in stats.get("markers", []) or []:
                markers[str(marker)] += 1

        output_path = OUT / f"agentkernel_lite_encdec_{split}.jsonl"
        write_jsonl(output_path, transformed)
        split_paths[split] = output_path
        split_stats[split] = {
            "source_rows": len(source_rows),
            "output_rows": len(transformed),
            "changed_source_rows": changed,
            "source_entity_context_rows": source_entity_rows,
            "expanded_entity_context_rows": expanded_entity_rows,
            "direct_fact_changed_rows": direct_fact_changed,
            "distinct_selector_markers": len(markers),
        }
        op_counts[split] = {"before": operation_counts(source_rows), "after": operation_counts(transformed)}
        selector_op_counts[split] = selector_counts(transformed)
        token_stats[split] = row_token_stats(transformed)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage645_72domain_entity_field_selector_surface",
            "source_manifest_path": str(SOURCE),
            "manifest_path": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(split_paths["train"]),
            "eval_dataset_path": str(split_paths["eval"]),
            "train_examples": sum(1 for _ in iter_jsonl(split_paths["train"])),
            "eval_examples": sum(1 for _ in iter_jsonl(split_paths["eval"])),
            "stage645_selector_template": "{domain}|{field}|{entity}",
            "stage645_target_ops": ["direct_fact", "entity_context"],
            "entity_context_field_level": True,
            "entity_context_field_level_fields": list(FIELDS),
        }
    )
    manifest_path = OUT / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    eval_rows = int(manifest["eval_examples"])
    bits_per_eval_card_choice = math.log2(eval_rows)
    perfect_bits = eval_rows * bits_per_eval_card_choice
    summary = {
        "artifact_kind": "stage645_72domain_entity_field_selector_surface_dataset",
        "timestamp": int(time.time()),
        "source_manifest": str(SOURCE),
        "dataset_manifest": str(manifest_path),
        "split_stats": split_stats,
        "operation_counts": op_counts,
        "selector_operation_counts": selector_op_counts,
        "entity_context_collision_analysis": {
            "train": entity_collision_analysis(list(iter_jsonl(split_paths["train"]))),
            "eval": entity_collision_analysis(list(iter_jsonl(split_paths["eval"]))),
        },
        "token_stats": token_stats,
        "perfect_answer_surface": {
            "eval_rows": eval_rows,
            "bits_per_eval_card_choice": bits_per_eval_card_choice,
            "perfect_answer_bits": perfect_bits,
            "perfect_answer_bits_per_param_at_16280": perfect_bits / PARAMS,
        },
        "decision": "stage645_selector_surface_ready_for_collision_eval",
        "finding": (
            "Stage644's whole-entity entity_context rows cannot use the Stage643 domain|field|entity selector directly. "
            "Stage645 first factors entity_context into field-level answer rows, then applies the same compact selector to "
            "direct_fact and entity_context on the 72-domain entropy-expanded surface."
        ),
    }
    ARTIFACT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        f"""# Stage645 72-Domain Entity Field Selector Surface

Artifact: `runs/local/artifacts/stage645_72domain_entity_field_selector_surface_dataset.json`

Dataset manifest: `runs/local/tmp/stage645_72domain_entity_field_selector_surface/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Train rows: `{split_stats['train']['source_rows']}` -> `{split_stats['train']['output_rows']}`
- Eval rows: `{split_stats['eval']['source_rows']}` -> `{split_stats['eval']['output_rows']}`
- Direct-fact selector rows: train `{split_stats['train']['direct_fact_changed_rows']}`, eval `{split_stats['eval']['direct_fact_changed_rows']}`
- Entity-context rows: train `{split_stats['train']['source_entity_context_rows']}` -> `{split_stats['train']['expanded_entity_context_rows']}`, eval `{split_stats['eval']['source_entity_context_rows']}` -> `{split_stats['eval']['expanded_entity_context_rows']}`
- Eval entity field collision rows: `{summary['entity_context_collision_analysis']['eval']['collision_rows']}`
- Eval entity field mean/max candidate count: `{summary['entity_context_collision_analysis']['eval']['mean_candidate_count']}` / `{summary['entity_context_collision_analysis']['eval']['max_candidate_count']}`
- Perfect answer ceiling: `{perfect_bits / PARAMS}` bits/param at `16280` params

## Decision

`stage645_selector_surface_ready_for_collision_eval`

## Finding

{summary['finding']}
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
