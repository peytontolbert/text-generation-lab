#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/local/tmp/stage645_72domain_entity_field_selector_surface/agentkernel_lite_encdec_dataset_manifest.json"
OUT = ROOT / "runs/local/tmp/stage646_72domain_collision_conditioned_selector"
ARTIFACT = ROOT / "runs/local/artifacts/stage646_72domain_collision_conditioned_selector_dataset.json"
DOC = ROOT / "docs/stage646_72domain_collision_conditioned_selector.md"
KEY_VALUE_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*?)=([^\s;]+)")
PRIMARY_FIELDS = ("bind_key", "lookup_key", "fact_key", "rule_key", "composition_key")
TARGET_OPS = {
    "direct_fact",
    "entity_context",
    "rule_case_intersection_count",
    "rule_case_intersection_member",
    "set_intersection_member",
    "two_hop_owner_region",
}
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def key_values(text: str) -> dict[str, str]:
    return {str(key): str(value) for key, value in KEY_VALUE_RE.findall(str(text or ""))}


def collision_key(row: dict[str, Any]) -> tuple[str, str] | None:
    op = str(row.get("operation", "") or "")
    query_keys = key_values(str(row.get("retrieval_query_text", "") or ""))
    domain = query_keys.get("domain", "domain_unknown")
    if op == "direct_fact":
        return "fact_key", f"collision_direct_fact|{domain}|{query_keys.get('field', 'field_unknown')}"
    if op == "entity_context":
        return "bind_key", f"collision_entity_context_field|{domain}|{query_keys.get('field', 'field_unknown')}"
    if op == "rule_case_intersection_count":
        return (
            "lookup_key",
            "collision_rule_case_intersection_count|"
            f"{domain}|{query_keys.get('rule_field', 'rule_unknown')}|{query_keys.get('case', 'case_unknown')}|"
            f"{query_keys.get('filter_field', 'filter_unknown')}",
        )
    if op == "rule_case_intersection_member":
        return (
            "lookup_key",
            "collision_rule_case_intersection_member|"
            f"{domain}|{query_keys.get('rule_field', 'rule_unknown')}|{query_keys.get('case', 'case_unknown')}|"
            f"{query_keys.get('filter_field', 'filter_unknown')}|{query_keys.get('filter_answer', 'answer_unknown')}",
        )
    if op == "set_intersection_member":
        return (
            "lookup_key",
            "collision_set_intersection_member|"
            f"{domain}|{query_keys.get('field_a', 'field_a_unknown')}|{query_keys.get('answer_a', 'answer_a_unknown')}|"
            f"{query_keys.get('field_b', 'field_b_unknown')}|{query_keys.get('answer_b', 'answer_b_unknown')}",
        )
    if op == "two_hop_owner_region":
        return "composition_key", f"collision_two_hop_owner_region|{domain}"
    return None


def replace_or_insert_key(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"{re.escape(key)}=[^\s;]+")
    if pattern.search(text):
        return pattern.sub(f"{key}={value}", text)
    op_match = re.search(r"(op=[^\s;]+)", text)
    if op_match:
        return text[: op_match.end()] + f" {key}={value}" + text[op_match.end() :]
    token_match = re.search(r"(<AK_OP_[^>]+>)", text)
    if token_match:
        return text[: token_match.end()] + f" {key}={value}" + text[token_match.end() :]
    return f"{key}={value} {text}"


def coarsen_auxiliary_keys(text: str, op: str, value: str) -> str:
    if op.startswith("rule_case_intersection_"):
        text = re.sub(r"rule_case_intersection_key=[^\s;]+", f"rule_case_intersection_key={value}", text)
    if op == "set_intersection_member":
        text = re.sub(r"lookup_key=[^\s;]+", f"lookup_key={value}", text)
    return text


def rewrite_row(row: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    op = str(row.get("operation", "") or "")
    key = collision_key(row)
    if op not in TARGET_OPS or key is None:
        return dict(row), False
    key_name, key_value = key
    rewritten: dict[str, Any] = {}
    for field, value in row.items():
        if isinstance(value, str) and field in TEXT_FIELDS:
            text = replace_or_insert_key(value, key_name, key_value)
            text = coarsen_auxiliary_keys(text, op, key_value)
            rewritten[field] = text
        else:
            rewritten[field] = value
    rewritten["source_type"] = f"{row.get('source_type', 'pocketpal_stage430_semantic_ops')}_stage646_collision_conditioned"
    rewritten["collision_conditioned"] = True
    rewritten["collision_key_name"] = key_name
    rewritten["collision_key_value"] = key_value
    return rewritten, True


def primary_key_for_query(query: str) -> tuple[str, str] | None:
    keys = key_values(query)
    for key in PRIMARY_FIELDS:
        if key in keys:
            return key, keys[key]
    return None


def analyze(rows: list[dict[str, Any]], split: str) -> dict[str, Any]:
    by_op: dict[str, Counter[str]] = defaultdict(Counter)
    target_rows = 0
    for row in rows:
        op = str(row.get("operation", "") or "")
        if op not in TARGET_OPS:
            continue
        target_rows += 1
        primary = primary_key_for_query(str(row.get("retrieval_query_text", "") or ""))
        if primary is not None:
            by_op[op][f"{primary[0]}={primary[1]}"] += 1
    op_stats = {}
    total_collision_rows = 0
    total_groups = 0
    max_group = 0
    for op, counts in sorted(by_op.items()):
        sizes = list(counts.values())
        collision_rows = sum(size for size in sizes if size > 1)
        total_collision_rows += collision_rows
        total_groups += len(sizes)
        max_group = max(max_group, max(sizes) if sizes else 0)
        op_stats[op] = {
            "rows": sum(sizes),
            "groups": len(sizes),
            "groups_with_collisions": sum(1 for size in sizes if size > 1),
            "collision_rows": collision_rows,
            "mean_candidate_count": (sum(sizes) / len(sizes)) if sizes else 0.0,
            "max_candidate_count": max(sizes) if sizes else 0,
        }
    return {
        "split": split,
        "target_rows": target_rows,
        "groups": total_groups,
        "collision_rows": total_collision_rows,
        "mean_candidate_count": (target_rows / total_groups) if total_groups else 0.0,
        "max_candidate_count": max_group,
        "by_operation": op_stats,
    }


def main() -> None:
    source_manifest = json.loads(SOURCE.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    split_outputs: dict[str, Path] = {}
    rewritten_counts: dict[str, int] = {}
    analyses: dict[str, Any] = {}
    for split in ("train", "eval"):
        rows = []
        rewritten_count = 0
        for row in iter_jsonl(Path(source_manifest[f"{split}_dataset_path"])):
            rewritten, changed = rewrite_row(row)
            rewritten_count += int(changed)
            rows.append(rewritten)
        output_path = OUT / f"agentkernel_lite_encdec_{split}.jsonl"
        write_jsonl(output_path, rows)
        split_outputs[split] = output_path
        rewritten_counts[split] = rewritten_count
        analyses[split] = analyze(rows, split)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage646_72domain_collision_conditioned_selector",
            "source_manifest_path": str(SOURCE),
            "manifest_path": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(split_outputs["train"]),
            "eval_dataset_path": str(split_outputs["eval"]),
            "collision_conditioned": True,
            "collision_conditioned_ops": sorted(TARGET_OPS),
            "collision_rewritten_train_examples": rewritten_counts["train"],
            "collision_rewritten_eval_examples": rewritten_counts["eval"],
            "collision_goal": "Keep compact selectors visible while coarsening exact structured keys so hard filtering cannot solve targeted rows alone.",
        }
    )
    manifest_path = OUT / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "artifact_kind": "stage646_72domain_collision_conditioned_selector_dataset",
        "timestamp": int(time.time()),
        "source_manifest": str(SOURCE),
        "dataset_manifest": str(manifest_path),
        "rewritten_counts": rewritten_counts,
        "analysis": analyses,
        "decision": "stage646_collision_conditioned_selector_ready_for_16k_probe",
        "finding": (
            "Stage646 coarsens exact structured keys on the Stage645 entropy-expanded selector surface. "
            "This preserves domain|field|entity as neural binding evidence while making hard-filter candidate sets non-singleton."
        ),
    }
    ARTIFACT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        f"""# Stage646 72-Domain Collision-Conditioned Selector

Artifact: `runs/local/artifacts/stage646_72domain_collision_conditioned_selector_dataset.json`

Dataset manifest: `runs/local/tmp/stage646_72domain_collision_conditioned_selector/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Rewritten rows: train `{rewritten_counts['train']}`, eval `{rewritten_counts['eval']}`
- Eval target rows: `{analyses['eval']['target_rows']}`
- Eval collision rows: `{analyses['eval']['collision_rows']}`
- Eval mean/max candidate count: `{analyses['eval']['mean_candidate_count']}` / `{analyses['eval']['max_candidate_count']}`

## Eval By Operation

```json
{json.dumps(analyses['eval']['by_operation'], indent=2, sort_keys=True)}
```

## Decision

`stage646_collision_conditioned_selector_ready_for_16k_probe`

## Finding

{summary['finding']}
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
