#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/local/tmp/pocketpal_stage596_collision_conditioned_seed461"
OUT = ROOT / "runs/local/tmp/pocketpal_stage601_entity_field_context_seed461"
ARTIFACT = ROOT / "runs/local/artifacts/stage601_entity_field_context_dataset.json"
DOC = ROOT / "docs/stage601_entity_field_context_dataset.md"
FIELDS = ("capital", "currency", "continent", "owner", "status", "priority", "tool", "risk")
KEY_VALUE_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*?)=([^\s;]+)")


def stable_id(*parts: Any) -> str:
    raw = "\n".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def key_values(text: str) -> dict[str, str]:
    return {str(key): str(value) for key, value in KEY_VALUE_RE.findall(str(text or ""))}


def entity_field_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    if str(row.get("operation", "") or "") != "entity_context":
        return [dict(row)]

    doc_keys = key_values(str(row.get("retrieval_doc_text", "") or ""))
    domain = doc_keys.get("domain")
    entity = doc_keys.get("entity")
    if not domain or not entity:
        return [dict(row)]

    expanded: list[dict[str, Any]] = []
    for field in FIELDS:
        answer = doc_keys.get(field)
        if not answer:
            continue
        bind_key = f"collision_entity_context_field|{domain}|{field}"
        query = (
            f"<AK_OP_ENTITY_CONTEXT> op=entity_context bind_key={bind_key} "
            f"domain={domain} entity={entity} field={field}"
        )
        doc = (
            f"<AK_OP_ENTITY_CONTEXT> bind_key={bind_key} entity_context_field_card "
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
                "example_id": stable_id("stage601_entity_field_context", row.get("example_id"), field),
                "expected_content": answer,
                "json_decoder_text": f"bind_key={bind_key} {{\"action\":\"respond\",\"content\":\"{answer}\"}}",
                "negative_decoder_text": f"bind_key={bind_key} ",
                "retrieval_doc_text": doc,
                "retrieval_query_text": query,
                "source_id": f"{row.get('source_id', '')}__entity_field_{field}",
                "source_type": f"{row.get('source_type', 'pocketpal_stage430_semantic_ops')}_entity_field_context",
                "state_text": doc,
            }
        )
        expanded.append(clone)
    return expanded or [dict(row)]


def transform(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    out: list[dict[str, Any]] = []
    source_entity_rows = 0
    expanded_entity_rows = 0
    for row in rows:
        converted = entity_field_rows(row)
        if str(row.get("operation", "") or "") == "entity_context":
            source_entity_rows += 1
            expanded_entity_rows += len(converted)
        out.extend(converted)
    return out, {
        "source_entity_context_rows": source_entity_rows,
        "expanded_entity_context_rows": expanded_entity_rows,
        "net_added_rows": len(out) - len(rows),
    }


def counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("operation", "") or "") for row in rows))


def collision_analysis(rows: list[dict[str, Any]], split: str) -> dict[str, Any]:
    groups: dict[str, int] = defaultdict(int)
    for row in rows:
        if not row.get("entity_context_field_level"):
            continue
        query_keys = key_values(str(row.get("retrieval_query_text", "") or ""))
        bind_key = query_keys.get("bind_key")
        if bind_key:
            groups[bind_key] += 1
    sizes = list(groups.values())
    return {
        "split": split,
        "field_level_rows": sum(sizes),
        "field_level_groups": len(sizes),
        "groups_with_collisions": sum(1 for size in sizes if size > 1),
        "collision_rows": sum(size for size in sizes if size > 1),
        "mean_candidate_count": (sum(sizes) / len(sizes)) if sizes else 0.0,
        "max_candidate_count": max(sizes) if sizes else 0,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_manifest = json.loads((SOURCE / "agentkernel_lite_encdec_dataset_manifest.json").read_text(encoding="utf-8"))
    split_outputs = {}
    transform_stats = {}
    analyses = {}
    operation_counts = {}
    for split in ("train", "eval"):
        source_path = Path(source_manifest[f"{split}_dataset_path"])
        source_rows = list(iter_jsonl(source_path))
        converted_rows, stats = transform(source_rows)
        output_path = OUT / f"agentkernel_lite_encdec_{split}.jsonl"
        write_jsonl(output_path, converted_rows)
        split_outputs[split] = output_path
        transform_stats[split] = stats
        analyses[split] = collision_analysis(converted_rows, split)
        operation_counts[split] = {
            "before": counts(source_rows),
            "after": counts(converted_rows),
        }

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage601_entity_field_context",
            "source_manifest_path": str(SOURCE / "agentkernel_lite_encdec_dataset_manifest.json"),
            "manifest_path": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(split_outputs["train"]),
            "eval_dataset_path": str(split_outputs["eval"]),
            "train_examples": sum(1 for _ in iter_jsonl(split_outputs["train"])),
            "eval_examples": sum(1 for _ in iter_jsonl(split_outputs["eval"])),
            "entity_context_field_level": True,
            "entity_context_field_level_fields": list(FIELDS),
            "collision_goal": (
                "Replace broad entity_context cards with field-level bindings while preserving non-singleton "
                "domain+field collision groups."
            ),
        }
    )
    (OUT / "agentkernel_lite_encdec_dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = {
        "artifact_kind": "stage601_entity_field_context_dataset",
        "dataset_manifest": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
        "source_manifest": str(SOURCE / "agentkernel_lite_encdec_dataset_manifest.json"),
        "fields": list(FIELDS),
        "transform_stats": transform_stats,
        "operation_counts": operation_counts,
        "analysis": analyses,
        "decision": "entity_field_context_probe_ready",
        "finding": (
            "Stage601 converts entity_context from whole-entity cards into compact field-level answer cards. "
            "The exact hard filter still sees multiple same-domain/same-field candidates, so the model must use "
            "the entity token to resolve the answer instead of relying on a singleton key."
        ),
    }
    ARTIFACT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        f"""# Stage601 Entity Field Context Dataset

Artifact: `runs/local/artifacts/stage601_entity_field_context_dataset.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage601_entity_field_context_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Fields: `{', '.join(FIELDS)}`
- Train entity rows: `{transform_stats['train']['source_entity_context_rows']}` -> `{transform_stats['train']['expanded_entity_context_rows']}`
- Eval entity rows: `{transform_stats['eval']['source_entity_context_rows']}` -> `{transform_stats['eval']['expanded_entity_context_rows']}`
- Eval field collision rows: `{analyses['eval']['collision_rows']}`
- Eval mean/max candidate count: `{analyses['eval']['mean_candidate_count']}` / `{analyses['eval']['max_candidate_count']}`

## Decision

`entity_field_context_probe_ready`

## Finding

{summary['finding']}
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
