#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/local/tmp/pocketpal_stage607_entity_field_role_tokens_seed461"
OUT = ROOT / "runs/local/tmp/pocketpal_stage610_entity_selector_tokens_seed461"
ARTIFACT = ROOT / "runs/local/artifacts/stage610_entity_selector_tokens_dataset.json"
DOC = ROOT / "docs/stage610_entity_selector_tokens_dataset.md"
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


def selector_marker(domain: str, entity: str, field: str) -> str:
    return (
        "ENTITY_FIELD_SELECTOR"
        f" selector_domain={domain}"
        f" selector_entity={entity}"
        f" selector_field={field}"
        f" selector_pair={entity}|{field}"
    )


def inject_after_operation(text: str, marker: str) -> str:
    if not text or "ENTITY_FIELD_SELECTOR" in text:
        return text
    op_match = re.search(r"(<AK_OP_ENTITY_CONTEXT>|op=entity_context)", text)
    if op_match:
        return text[: op_match.end()] + f" {marker}" + text[op_match.end() :]
    return f"{marker} {text}"


def rewrite_row(row: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    if str(row.get("operation", "") or "") != "entity_context":
        return dict(row), False
    query_keys = key_values(str(row.get("retrieval_query_text", "") or ""))
    doc_keys = key_values(str(row.get("retrieval_doc_text", "") or ""))
    domain = query_keys.get("domain") or doc_keys.get("domain")
    entity = query_keys.get("entity") or doc_keys.get("entity")
    field = query_keys.get("field") or doc_keys.get("field")
    if not (domain and entity and field):
        return dict(row), False
    marker = selector_marker(domain, entity, field)
    rewritten: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, str) and key in TEXT_FIELDS:
            rewritten[key] = inject_after_operation(value, marker)
        else:
            rewritten[key] = value
    rewritten["entity_context_selector_tokens"] = True
    rewritten["entity_context_selector_domain"] = domain
    rewritten["entity_context_selector_entity"] = entity
    rewritten["entity_context_selector_field"] = field
    rewritten["source_type"] = f"{row.get('source_type', 'retrieval')}_entity_selector_tokens"
    return rewritten, True


def transform(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    out = []
    changed = 0
    for row in rows:
        new_row, did_change = rewrite_row(row)
        changed += int(did_change)
        out.append(new_row)
    return out, changed


def counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("operation", "") or "") for row in rows))


def selector_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(row.get(key, "") or "") for row in rows if row.get("entity_context_selector_tokens")))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_manifest = json.loads((SOURCE / "agentkernel_lite_encdec_dataset_manifest.json").read_text(encoding="utf-8"))
    split_outputs = {}
    changed_counts = {}
    op_counts = {}
    field_counts = {}
    for split in ("train", "eval"):
        rows = list(iter_jsonl(Path(source_manifest[f"{split}_dataset_path"])))
        converted, changed = transform(rows)
        output_path = OUT / f"agentkernel_lite_encdec_{split}.jsonl"
        write_jsonl(output_path, converted)
        split_outputs[split] = output_path
        changed_counts[split] = changed
        op_counts[split] = counts(converted)
        field_counts[split] = selector_counts(converted, "entity_context_selector_field")

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage610_entity_selector_tokens",
            "source_manifest_path": str(SOURCE / "agentkernel_lite_encdec_dataset_manifest.json"),
            "manifest_path": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(split_outputs["train"]),
            "eval_dataset_path": str(split_outputs["eval"]),
            "train_examples": sum(1 for _ in iter_jsonl(split_outputs["train"])),
            "eval_examples": sum(1 for _ in iter_jsonl(split_outputs["eval"])),
            "entity_context_field_level": True,
            "entity_context_field_role_tokens": True,
            "entity_context_selector_tokens": True,
            "stage610_selector_changed_train_examples": changed_counts["train"],
            "stage610_selector_changed_eval_examples": changed_counts["eval"],
            "collision_goal": "Strengthen entity+field candidate selection for entity_context without changing hard-filter keys.",
        }
    )
    (OUT / "agentkernel_lite_encdec_dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = {
        "artifact_kind": "stage610_entity_selector_tokens_dataset",
        "dataset_manifest": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
        "source_manifest": str(SOURCE / "agentkernel_lite_encdec_dataset_manifest.json"),
        "changed_counts": changed_counts,
        "operation_counts": op_counts,
        "selector_field_counts": field_counts,
        "decision": "entity_selector_token_dataset_ready",
        "finding": (
            "Stage610 keeps the Stage607 role-token schema and adds repeated entity+field selector markers to entity_context "
            "query/doc text. This tests whether the remaining role-token failures are selector weighting failures before changing the loss."
        ),
    }
    ARTIFACT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        f"""# Stage610 Entity Selector Tokens Dataset

Artifact: `runs/local/artifacts/stage610_entity_selector_tokens_dataset.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage610_entity_selector_tokens_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Changed train examples: `{changed_counts['train']}`
- Changed eval examples: `{changed_counts['eval']}`
- Eval selector field counts: `{field_counts['eval']}`

## Decision

`entity_selector_token_dataset_ready`

## Finding

{summary['finding']}
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
