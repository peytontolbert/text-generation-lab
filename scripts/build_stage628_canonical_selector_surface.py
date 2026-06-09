#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "runs/local/tmp/pocketpal_stage602_entity_field_balanced_replay_seed461/agentkernel_lite_encdec_dataset_manifest.json"
DEFAULT_OUTPUT = ROOT / "runs/local/tmp/pocketpal_stage628_canonical_selector_surface_seed461"
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
FINAL_ANSWER_KEYS = {"actual", "answer", "member", "count", "owner_region"}
ALLOWED_DOC_ONLY_KEYS = {
    "two_hop_owner_region": {"owner"},
}
SELECTOR_TEMPLATES = {
    "direct_fact": "{domain}:{entity}:{field}",
    "entity_context": "{domain}:{entity}:{field}",
    "reverse_lookup_set": "{domain}:{field}:{answer}",
    "rule_case_intersection_count": "{domain}:{rule_field}:{case}:{filter_field}:{filter_answer}",
    "rule_case_intersection_member": "{domain}:{rule_field}:{case}:{entity}",
    "rule_default": "{domain}:{entity}:{field}",
    "two_hop_owner_region": "{domain}:{entity}:{owner}",
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


def template_fields(template: str) -> list[str]:
    return re.findall(r"\{([A-Za-z][A-Za-z0-9_]*)\}", template)


def marker_for_row(op: str, row: dict[str, Any], template: str) -> tuple[str | None, list[str]]:
    query_keys = key_values(str(row.get("retrieval_query_text", "") or ""))
    doc_keys = key_values(str(row.get("retrieval_doc_text", "") or ""))
    allowed_doc_only = ALLOWED_DOC_ONLY_KEYS.get(op, set())
    keys = dict(query_keys)
    doc_only_used: list[str] = []
    for key in template_fields(template):
        if key in keys:
            continue
        if key in doc_keys and key in allowed_doc_only:
            keys[key] = doc_keys[key]
            doc_only_used.append(key)
            continue
        return None, doc_only_used
    if any(key in FINAL_ANSWER_KEYS and key not in query_keys for key in template_fields(template)):
        return None, doc_only_used
    marker = template.format_map(keys).strip()
    return marker or None, doc_only_used


def inject_after_operation(text: str, op: str, marker: str) -> str:
    if not text or marker in text:
        return text
    op_token = f"<AK_OP_{op.upper()}>"
    op_match = re.search(rf"({re.escape(op_token)}|op={re.escape(op)})", text)
    if op_match:
        return text[: op_match.end()] + f" {marker}" + text[op_match.end() :]
    return f"{marker} {text}"


def rewrite_row(row: dict[str, Any]) -> tuple[dict[str, Any], bool, str | None, list[str]]:
    op = str(row.get("operation", "") or "")
    template = SELECTOR_TEMPLATES.get(op)
    if not template:
        return dict(row), False, None, []
    marker, doc_only_used = marker_for_row(op, row, template)
    if marker is None:
        return dict(row), False, None, doc_only_used
    rewritten: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, str) and key in TEXT_FIELDS:
            rewritten[key] = inject_after_operation(value, op, marker)
        else:
            rewritten[key] = value
    rewritten["stage628_canonical_selector_marker"] = marker
    rewritten["stage628_canonical_selector_template"] = template
    rewritten["source_type"] = f"{row.get('source_type', 'retrieval')}_stage628_canonical_selector"
    return rewritten, True, marker, doc_only_used


def build(source_manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    split_paths: dict[str, Path] = {}
    changed_counts: dict[str, int] = {}
    marker_counts: dict[str, int] = {}
    operation_counts: dict[str, dict[str, int]] = {}
    changed_by_operation: dict[str, dict[str, int]] = {}
    doc_only_key_counts: dict[str, dict[str, int]] = {}

    for split in ("train", "eval"):
        rows = list(iter_jsonl(Path(source_manifest[f"{split}_dataset_path"])))
        rewritten_rows = []
        markers: Counter[str] = Counter()
        changed_ops: Counter[str] = Counter()
        doc_only_keys: Counter[str] = Counter()
        for row in rows:
            rewritten, changed, marker, doc_only_used = rewrite_row(row)
            if changed:
                op = str(row.get("operation", "") or "")
                changed_ops[op] += 1
                if marker:
                    markers[marker] += 1
                for key in doc_only_used:
                    doc_only_keys[f"{op}:{key}"] += 1
            rewritten_rows.append(rewritten)
        split_path = output_dir / f"agentkernel_lite_encdec_{split}.jsonl"
        write_jsonl(split_path, rewritten_rows)
        split_paths[split] = split_path
        changed_counts[split] = sum(changed_ops.values())
        marker_counts[split] = len(markers)
        operation_counts[split] = dict(Counter(str(row.get("operation", "") or "") for row in rewritten_rows))
        changed_by_operation[split] = dict(changed_ops)
        doc_only_key_counts[split] = dict(doc_only_keys)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage628_canonical_selector_surface",
            "source_manifest_path": str(source_manifest_path),
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(split_paths["train"]),
            "eval_dataset_path": str(split_paths["eval"]),
            "train_examples": sum(1 for _ in iter_jsonl(split_paths["train"])),
            "eval_examples": sum(1 for _ in iter_jsonl(split_paths["eval"])),
            "stage628_selector_templates": SELECTOR_TEMPLATES,
            "stage628_changed_train_examples": changed_counts["train"],
            "stage628_changed_eval_examples": changed_counts["eval"],
        }
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "artifact_kind": "stage628_canonical_selector_surface_dataset",
        "source_manifest": str(source_manifest_path),
        "manifest_path": str(manifest_path),
        "selector_templates": SELECTOR_TEMPLATES,
        "changed_counts": changed_counts,
        "changed_by_operation": changed_by_operation,
        "distinct_marker_counts": marker_counts,
        "operation_counts": operation_counts,
        "doc_only_key_counts": doc_only_key_counts,
        "dataset_hash": hashlib.sha1(manifest_path.read_bytes()).hexdigest(),
    }
    (ROOT / "runs/local/artifacts/stage628_canonical_selector_surface_dataset.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Stage628 canonical per-operation selector surface from clean Stage602 rows.")
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary = build(args.source_manifest, args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
