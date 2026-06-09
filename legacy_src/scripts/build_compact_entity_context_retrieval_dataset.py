#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any


_KEY_VALUE_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*?)=([^\s;]+)")


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def _key_values(text: str) -> dict[str, str]:
    return {str(key): str(value) for key, value in _KEY_VALUE_RE.findall(str(text or ""))}


def _load_negative_docs(raw: Any) -> list[str]:
    if raw is None:
        return []
    value = raw
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if isinstance(value, dict):
        value = value.get("docs") or value.get("negatives") or value.get("retrieval_negative_doc_texts") or []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item or "").strip()]


def _dump_negative_docs(value: Any, docs: list[str]) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return json.dumps(docs, ensure_ascii=True, separators=(",", ":"))
    return docs


def _is_entity_context(row: dict[str, Any], text: str) -> bool:
    operation = str(row.get("operation", "") or "").strip()
    return operation == "entity_context" or "op=entity_context" in text or "entity_context_card" in text


def _compact_entity_context_doc(text: str) -> str:
    keys = _key_values(text)
    domain = keys.get("domain", "")
    entity = keys.get("entity", "")
    if not domain or not entity:
        return text
    parts = [
        "<AK_OP_ENTITY_CONTEXT>",
        "entity_context_key",
        f"domain={domain}",
        f"entity={entity}",
    ]
    return " ".join(parts)


def _compact_row(row: dict[str, Any]) -> tuple[dict[str, Any], int]:
    out = dict(row)
    changed = 0
    doc = str(out.get("retrieval_doc_text", "") or "")
    if _is_entity_context(out, doc):
        compact = _compact_entity_context_doc(doc)
        if compact != doc:
            out["retrieval_doc_text"] = compact
            out["state_text"] = compact
            changed += 1
    negatives = _load_negative_docs(out.get("retrieval_negative_doc_texts"))
    if negatives:
        compact_negatives = [
            _compact_entity_context_doc(item) if "entity_context_card" in item or "op=entity_context" in item else item
            for item in negatives
        ]
        if compact_negatives != negatives:
            out["retrieval_negative_doc_texts"] = _dump_negative_docs(out.get("retrieval_negative_doc_texts"), compact_negatives)
            changed += 1
    return out, changed


def _copy_optional_tokenizer(src_manifest: dict[str, Any], output_dir: Path) -> str:
    tokenizer_dir = str(src_manifest.get("tokenizer_dir", "") or "")
    if not tokenizer_dir:
        return tokenizer_dir
    src = Path(tokenizer_dir)
    dst = output_dir / "tokenizer"
    if src.exists():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        return str(dst)
    return tokenizer_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    input_manifest_path = Path(args.input_manifest)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(input_manifest_path.read_text(encoding="utf-8"))

    train_rows = _iter_jsonl(Path(str(manifest["train_dataset_path"])))
    eval_rows = _iter_jsonl(Path(str(manifest["eval_dataset_path"])))

    train_out: list[dict[str, Any]] = []
    eval_out: list[dict[str, Any]] = []
    train_changed = 0
    eval_changed = 0
    for row in train_rows:
        compact, changed = _compact_row(row)
        train_out.append(compact)
        train_changed += changed
    for row in eval_rows:
        compact, changed = _compact_row(row)
        eval_out.append(compact)
        eval_changed += changed

    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    _write_jsonl(train_path, train_out)
    _write_jsonl(eval_path, eval_out)

    out_manifest = dict(manifest)
    out_manifest["objective"] = f"{manifest.get('objective', 'agentkernel')}_compact_entity_context_retrieval"
    out_manifest["train_dataset_path"] = str(train_path)
    out_manifest["eval_dataset_path"] = str(eval_path)
    out_manifest["source_manifest_path"] = str(input_manifest_path)
    out_manifest["compact_entity_context_retrieval"] = True
    out_manifest["compact_entity_context_train_changes"] = int(train_changed)
    out_manifest["compact_entity_context_eval_changes"] = int(eval_changed)
    out_manifest["train_rows"] = len(train_out)
    out_manifest["eval_rows"] = len(eval_out)
    tokenizer_dir = _copy_optional_tokenizer(manifest, output_dir)
    if tokenizer_dir:
        out_manifest["tokenizer_dir"] = tokenizer_dir

    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(out_manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"manifest_path": str(manifest_path), **{k: out_manifest[k] for k in out_manifest if k.startswith("compact_")}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
