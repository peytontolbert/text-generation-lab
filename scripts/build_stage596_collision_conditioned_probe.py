#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/local/tmp/pocketpal_stage521_stage497_rule_replay_seed461"
OUT = ROOT / "runs/local/tmp/pocketpal_stage596_collision_conditioned_seed461"
ARTIFACT = ROOT / "runs/local/artifacts/stage596_collision_conditioned_probe.json"
DOC = ROOT / "docs/stage596_collision_conditioned_probe.md"

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
        return "bind_key", f"collision_entity_context|{domain}"
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
    # Put the primary key near the operation marker so key hashes see it early.
    op_match = re.search(r"(op=[^\s;]+)", text)
    if op_match:
        insert_at = op_match.end()
        return text[:insert_at] + f" {key}={value}" + text[insert_at:]
    token_match = re.search(r"(<AK_OP_[^>]+>)", text)
    if token_match:
        insert_at = token_match.end()
        return text[:insert_at] + f" {key}={value}" + text[insert_at:]
    return f"{key}={value} {text}"


def coarsen_old_unique_keys(text: str, op: str, value: str) -> str:
    if op.startswith("rule_case_intersection_"):
        text = re.sub(r"rule_case_intersection_key=[^\s;]+", f"rule_case_intersection_key={value}", text)
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
            text = coarsen_old_unique_keys(text, op, key_value)
            rewritten[field] = text
        else:
            rewritten[field] = value
    rewritten["source_type"] = f"{row.get('source_type', 'pocketpal_stage430_semantic_ops')}_collision_conditioned"
    rewritten["collision_conditioned"] = True
    rewritten["collision_key_name"] = key_name
    rewritten["collision_key_value"] = key_value
    return rewritten, True


def primary_key_for_query(query: str) -> tuple[str, str] | None:
    keys = key_values(query)
    for key in PRIMARY_FIELDS:
        if key in keys:
            return key, keys[key]
    if not keys:
        return None
    return "__all_fields__", "|".join(f"{key}={keys[key]}" for key in sorted(keys) if key != "op")


def analyze(rows: list[dict[str, Any]], split: str) -> dict[str, Any]:
    by_op: dict[str, Counter[str]] = defaultdict(Counter)
    target_rows = 0
    for row in rows:
        op = str(row.get("operation", "") or "")
        if op not in TARGET_OPS:
            continue
        target_rows += 1
        primary = primary_key_for_query(str(row.get("retrieval_query_text", "") or ""))
        if primary is None:
            continue
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
    OUT.mkdir(parents=True, exist_ok=True)
    source_manifest = json.loads((SOURCE / "agentkernel_lite_encdec_dataset_manifest.json").read_text(encoding="utf-8"))
    split_outputs = {}
    analyses = {}
    rewritten_counts = {}
    for split in ("train", "eval"):
        source_path = Path(source_manifest[f"{split}_dataset_path"])
        rows = []
        rewritten_count = 0
        for row in iter_jsonl(source_path):
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
            "artifact_kind": "agentkernel_lite_encdec_stage596_collision_conditioned",
            "source_manifest_path": str(SOURCE / "agentkernel_lite_encdec_dataset_manifest.json"),
            "manifest_path": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(split_outputs["train"]),
            "eval_dataset_path": str(split_outputs["eval"]),
            "collision_conditioned": True,
            "collision_conditioned_ops": sorted(TARGET_OPS),
            "collision_rewritten_train_examples": rewritten_counts["train"],
            "collision_rewritten_eval_examples": rewritten_counts["eval"],
            "collision_goal": "Make structured hard-filter candidate sets non-singleton so filtered retrieval still requires neural value/composition resolution.",
        }
    )
    (OUT / "agentkernel_lite_encdec_dataset_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "artifact_kind": "stage596_collision_conditioned_probe",
        "dataset_manifest": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
        "source_manifest": str(SOURCE / "agentkernel_lite_encdec_dataset_manifest.json"),
        "target_operations": sorted(TARGET_OPS),
        "rewritten_counts": rewritten_counts,
        "analysis": analyses,
        "decision": "collision_probe_ready_for_training",
        "finding": (
            "The Stage596 probe converts the Stage521/525 curriculum from unique exact-key lookup into collision-conditioned "
            "retrieval for the targeted operations. Hard filtering can still narrow by operation/domain-style keys, but the "
            "filtered candidate set now contains multiple rows, so value, entity, membership, and composition fields must carry "
            "the remaining KBPP."
        ),
    }
    probe_eval_path = (
        ROOT
        / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage525_stage502_rule_replay_lr1e4_steps300"
        / "retrieval_eval_stage596_collision_full_corpus_operation_gated_structured_hard_filter.json"
    )
    if probe_eval_path.exists():
        probe_eval = json.loads(probe_eval_path.read_text(encoding="utf-8"))
        summary["stage525_collision_hard_filter_eval"] = {
            "path": str(probe_eval_path),
            "exact_top1": probe_eval["top1_accuracy"],
            "answer_top1": probe_eval["answer_top1_accuracy"],
            "mrr": probe_eval["mean_reciprocal_rank"],
            "exact_bits_per_param": probe_eval["verified_density"]["exact_verified_bits"]
            / probe_eval["verified_density"]["parameter_count"],
            "answer_bits_per_param": probe_eval["verified_density"]["answer_verified_bits"]
            / probe_eval["verified_density"]["parameter_count"],
            "hard_filter_stats": probe_eval.get("structured_key_hard_filter_stats", {}),
        }
    no_filter_eval_path = (
        ROOT
        / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage525_stage502_rule_replay_lr1e4_steps300"
        / "retrieval_eval_stage596_collision_full_corpus_operation_gated.json"
    )
    if no_filter_eval_path.exists():
        no_filter_eval = json.loads(no_filter_eval_path.read_text(encoding="utf-8"))
        summary["stage525_collision_no_filter_eval"] = {
            "path": str(no_filter_eval_path),
            "exact_top1": no_filter_eval["top1_accuracy"],
            "answer_top1": no_filter_eval["answer_top1_accuracy"],
            "mrr": no_filter_eval["mean_reciprocal_rank"],
            "exact_bits_per_param": no_filter_eval["verified_density"]["exact_verified_bits"]
            / no_filter_eval["verified_density"]["parameter_count"],
            "answer_bits_per_param": no_filter_eval["verified_density"]["answer_verified_bits"]
            / no_filter_eval["verified_density"]["parameter_count"],
        }
    ARTIFACT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        f"""# Stage596 Collision-Conditioned Probe

Artifact: `runs/local/artifacts/stage596_collision_conditioned_probe.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage596_collision_conditioned_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

Rewrote primary retrieval keys for targeted operations so exact-key filtering no longer selects a unique row.

- Train rows rewritten: `{rewritten_counts['train']}`
- Eval rows rewritten: `{rewritten_counts['eval']}`
- Eval target rows: `{analyses['eval']['target_rows']}`
- Eval key groups: `{analyses['eval']['groups']}`
- Eval collision rows: `{analyses['eval']['collision_rows']}`
- Eval mean candidate count: `{analyses['eval']['mean_candidate_count']}`
- Eval max candidate count: `{analyses['eval']['max_candidate_count']}`

Stage525, without retraining, reaches `{summary.get('stage525_collision_no_filter_eval', {}).get('exact_top1', 'not_run')}` exact and `{summary.get('stage525_collision_no_filter_eval', {}).get('answer_top1', 'not_run')}` answer without hard filtering.

With strict full-corpus operation-gated hard filtering, Stage525 reaches `{summary.get('stage525_collision_hard_filter_eval', {}).get('exact_top1', 'not_run')}` exact and `{summary.get('stage525_collision_hard_filter_eval', {}).get('answer_top1', 'not_run')}` answer. This hard-filter run has `{summary.get('stage525_collision_hard_filter_eval', {}).get('hard_filter_stats', {}).get('queries_with_multiple_exact_key_candidates', 'not_run')}` multiple-candidate queries and max candidate count `{summary.get('stage525_collision_hard_filter_eval', {}).get('hard_filter_stats', {}).get('exact_key_candidate_max', 'not_run')}`.

## Decision

`collision_probe_ready_for_training`

## Finding

{summary['finding']}
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
