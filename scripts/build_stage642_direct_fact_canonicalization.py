#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/local/tmp/recursive_kbpp_selector_stage626_rule_default_domain_selector/domain_entity_field_00fdde0fa6/agentkernel_lite_encdec_dataset_manifest.json"
OUT_ROOT = ROOT / "runs/local/tmp/stage642_direct_fact_canonicalization"
ARTIFACT = ROOT / "runs/local/artifacts/stage642_direct_fact_canonicalization_dataset.json"
TARGET_OP = "direct_fact"
TEXT_FIELDS = {
    "decoder_text",
    "encoder_text",
    "json_decoder_text",
    "negative_decoder_text",
    "retrieval_doc_text",
    "retrieval_query_text",
    "state_text",
}
KV_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*?)=([^\s;]+)")
VARIANTS = {
    "keep_new_remove_entity_field": {"remove_entity_field": True, "remove_domain_entity_field": False},
    "keep_new_remove_domain_entity_field": {"remove_entity_field": False, "remove_domain_entity_field": True},
    "keep_new_only": {"remove_entity_field": True, "remove_domain_entity_field": True},
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
    return {str(key): str(value) for key, value in KV_RE.findall(str(text or ""))}


def inject_after_operation(text: str, marker: str) -> str:
    if not text or marker in text:
        return text
    op_token = "<AK_OP_DIRECT_FACT>"
    op_match = re.search(rf"({re.escape(op_token)}|op=direct_fact)", text)
    if op_match:
        return text[: op_match.end()] + f" {marker}" + text[op_match.end() :]
    return f"{marker} {text}"


def remove_token(text: str, token: str) -> str:
    if not token:
        return text
    return re.sub(rf"(?<!\S){re.escape(token)}(?!\S)\s*", "", text).strip()


def rewrite_direct_fact_text(text: str, marker: str, entity_field: str, domain_entity_field: str, variant: dict[str, bool]) -> str:
    out = inject_after_operation(text, marker)
    if variant["remove_entity_field"]:
        out = remove_token(out, entity_field)
    if variant["remove_domain_entity_field"]:
        out = remove_token(out, domain_entity_field)
    return re.sub(r"\s+", " ", out).strip()


def rewrite_row(row: dict[str, Any], variant: dict[str, bool]) -> tuple[dict[str, Any], bool, str | None]:
    if str(row.get("operation", "") or "") != TARGET_OP:
        return dict(row), False, None
    query_keys = key_values(str(row.get("retrieval_query_text", "") or ""))
    doc_keys = key_values(str(row.get("retrieval_doc_text", "") or ""))
    keys = dict(doc_keys)
    keys.update(query_keys)
    domain = keys.get("domain", "")
    entity = keys.get("entity", "")
    field = keys.get("field", "")
    if not (domain and entity and field):
        return dict(row), False, None
    marker = f"{domain}|{field}|{entity}"
    entity_field = f"{entity}:{field}"
    domain_entity_field = f"{domain}:{entity}:{field}"
    rewritten: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, str) and key in TEXT_FIELDS:
            rewritten[key] = rewrite_direct_fact_text(value, marker, entity_field, domain_entity_field, variant)
        else:
            rewritten[key] = value
    rewritten["stage642_direct_fact_canonical_marker"] = marker
    rewritten["source_type"] = f"{row.get('source_type', 'retrieval')}_stage642_direct_fact_canonical"
    return rewritten, True, marker


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    artifact: dict[str, Any] = {
        "artifact_kind": "stage642_direct_fact_canonicalization_dataset",
        "source_manifest": str(SOURCE),
        "variants": {},
    }
    for name, variant in VARIANTS.items():
        out_dir = OUT_ROOT / name
        out_dir.mkdir(parents=True, exist_ok=True)
        split_paths = {}
        changed_counts = {}
        marker_counts = {}
        token_counts = {}
        op_counts = {}
        for split in ("train", "eval"):
            rows = list(iter_jsonl(Path(source[f"{split}_dataset_path"])))
            out_rows = []
            changed = 0
            markers: Counter[str] = Counter()
            direct_tokens = 0
            for row in rows:
                new_row, did_change, marker = rewrite_row(row, variant)
                changed += int(did_change)
                if marker:
                    markers[marker] += 1
                if str(new_row.get("operation", "") or "") == TARGET_OP:
                    direct_tokens += len(str(new_row.get("retrieval_query_text", "")).split())
                    direct_tokens += len(str(new_row.get("retrieval_doc_text", "")).split())
                out_rows.append(new_row)
            path = out_dir / f"agentkernel_lite_encdec_{split}.jsonl"
            write_jsonl(path, out_rows)
            split_paths[split] = path
            changed_counts[split] = changed
            marker_counts[split] = len(markers)
            token_counts[f"{split}_direct_fact_query_doc_tokens"] = direct_tokens
            op_counts[split] = dict(Counter(str(row.get("operation", "") or "") for row in out_rows))
        manifest = dict(source)
        manifest.update(
            {
                "artifact_kind": "agentkernel_lite_encdec_stage642_direct_fact_canonicalization",
                "source_manifest_path": str(SOURCE),
                "manifest_path": str(out_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
                "train_dataset_path": str(split_paths["train"]),
                "eval_dataset_path": str(split_paths["eval"]),
                "train_examples": sum(1 for _ in iter_jsonl(split_paths["train"])),
                "eval_examples": sum(1 for _ in iter_jsonl(split_paths["eval"])),
                "stage642_variant": name,
                "stage642_direct_fact_canonicalization": variant,
            }
        )
        manifest_path = out_dir / "agentkernel_lite_encdec_dataset_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        artifact["variants"][name] = {
            "manifest_path": str(manifest_path),
            "changed_counts": changed_counts,
            "distinct_marker_counts": marker_counts,
            "token_counts": token_counts,
            "operation_counts": op_counts,
            "variant": variant,
        }
    ARTIFACT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
