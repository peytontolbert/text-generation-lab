#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


_KV_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*?)=([^\s;|]+)")


def _kv(text: str) -> dict[str, str]:
    return {key: value for key, value in _KV_RE.findall(str(text or ""))}


def _entity_bind_key(text: str) -> str:
    values = _kv(text)
    domain = values.get("domain", "")
    entity = values.get("entity", "")
    if not domain or not entity:
        return ""
    return f"bind_key=entity_context|{domain}|{entity}"


def _prefix_entity_context_text(text: str) -> str:
    text = str(text or "")
    if "bind_key=entity_context|" in text:
        return text
    if "entity_context" not in text:
        return text
    bind_key = _entity_bind_key(text)
    if not bind_key:
        return text
    op_token = "<AK_OP_ENTITY_CONTEXT>"
    if text.startswith(op_token):
        return f"{op_token} {bind_key} {text[len(op_token):].strip()}"
    return f"{bind_key} {text}"


def _load_negative_docs(raw: Any) -> list[str]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item)]
    if isinstance(raw, dict):
        value = raw.get("docs") or raw.get("negatives") or raw.get("retrieval_negative_doc_texts") or []
        return [str(item) for item in value if str(item)]
    try:
        value = json.loads(str(raw))
    except json.JSONDecodeError:
        return [str(raw)]
    return _load_negative_docs(value)


def _transform_row(row: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    if str(row.get("operation", "") or "") != "entity_context":
        return row, False
    out = dict(row)
    changed = False
    for key in ("retrieval_query_text", "retrieval_doc_text", "state_text"):
        old = str(out.get(key, "") or "")
        new = _prefix_entity_context_text(old)
        if new != old:
            out[key] = new
            changed = True
    negatives = _load_negative_docs(out.get("retrieval_negative_doc_texts"))
    if negatives:
        new_negatives = [_prefix_entity_context_text(item) for item in negatives]
        if new_negatives != negatives:
            out["retrieval_negative_doc_texts"] = json.dumps(new_negatives, ensure_ascii=True, separators=(",", ":"))
            changed = True
    return out, changed


def _transform_jsonl(input_path: Path, output_path: Path) -> dict[str, int]:
    total = 0
    changed = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open("r", encoding="utf-8") as src, output_path.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            row, did_change = _transform_row(json.loads(line))
            total += 1
            changed += int(did_change)
            dst.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
    return {"total": total, "changed": changed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    base_manifest_path = Path(args.base_manifest).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    base = json.loads(base_manifest_path.read_text(encoding="utf-8"))
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    train_stats = _transform_jsonl(Path(str(base["train_dataset_path"])), train_path)
    eval_stats = _transform_jsonl(Path(str(base["eval_dataset_path"])), eval_path)
    manifest = dict(base)
    manifest.update(
        {
            "base_manifest": str(base_manifest_path),
            "stage": "stage552_entity_context_bind_key_prefix",
            "entity_context_bind_key_prefix": True,
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": int(train_stats["total"]),
            "eval_examples": int(eval_stats["total"]),
            "entity_context_bind_key_rows_train": int(train_stats["changed"]),
            "entity_context_bind_key_rows_eval": int(eval_stats["changed"]),
        }
    )
    Path(str(manifest["manifest_path"])).write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
