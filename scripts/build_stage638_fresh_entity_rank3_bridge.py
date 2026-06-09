#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/local/tmp/recursive_kbpp_selector_stage626_rule_default_domain_selector/domain_entity_field_00fdde0fa6/agentkernel_lite_encdec_dataset_manifest.json"
DETAILS = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage636_stage635_entity_rank3_bridge_lr5e7_steps120/retrieval_eval_stage626_train_full_corpus_operation_gated_details.jsonl"
OUT = ROOT / "runs/local/tmp/pocketpal_stage638_fresh_entity_rank3_bridge_seed461"
ARTIFACT = ROOT / "runs/local/artifacts/stage638_fresh_entity_rank3_bridge_dataset.json"
TARGET_OP = "entity_context"
MAX_RANK = 3


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    train_rows = list(iter_jsonl(Path(source["train_dataset_path"])))
    eval_rows = list(iter_jsonl(Path(source["eval_dataset_path"])))
    by_source_id = {str(row.get("source_id", "") or ""): row for row in train_rows}

    selected_ids: list[str] = []
    rank_hist: Counter[str] = Counter()
    residual_summary: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "exact_misses": 0,
            "answer_misses": 0,
            "answer_rank_2_3_misses": 0,
            "rank_histogram": Counter(),
        }
    )
    for detail in iter_jsonl(DETAILS):
        op = str(detail.get("operation", "") or "")
        row_summary = residual_summary[op]
        rank = int(detail.get("rank", 0) or 0)
        if not bool(detail.get("top1", False)):
            row_summary["exact_misses"] += 1
            row_summary["rank_histogram"][f"rank_{rank}"] += 1
        if not bool(detail.get("answer_top1", False)):
            row_summary["answer_misses"] += 1
            if 2 <= rank <= MAX_RANK:
                row_summary["answer_rank_2_3_misses"] += 1
        if op != TARGET_OP:
            continue
        if bool(detail.get("answer_top1", False)):
            continue
        if rank < 2 or rank > MAX_RANK:
            continue
        source_id = str(detail.get("source_id", "") or "")
        if source_id in by_source_id:
            selected_ids.append(source_id)
            rank_hist[f"rank_{rank}"] += 1

    replay_rows = []
    for source_id in selected_ids:
        row = dict(by_source_id[source_id])
        row["source_type"] = f"{row.get('source_type', 'retrieval')}_stage638_fresh_entity_rank3_bridge"
        row["stage638_fresh_entity_rank3_bridge"] = True
        replay_rows.append(row)

    train_out_rows = train_rows + replay_rows
    OUT.mkdir(parents=True, exist_ok=True)
    train_path = OUT / "agentkernel_lite_encdec_train.jsonl"
    eval_path = OUT / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_path, train_out_rows)
    write_jsonl(eval_path, eval_rows)

    manifest = dict(source)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage638_fresh_entity_rank3_bridge",
            "source_manifest_path": str(SOURCE),
            "train_miss_details_path": str(DETAILS),
            "manifest_path": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(train_out_rows),
            "eval_examples": len(eval_rows),
            "stage638_target_op": TARGET_OP,
            "stage638_max_rank": MAX_RANK,
            "stage638_replay_examples": len(replay_rows),
        }
    )
    manifest_path = OUT / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    cleaned_summary = {}
    for op, row in residual_summary.items():
        cleaned_summary[op] = dict(row)
        cleaned_summary[op]["rank_histogram"] = dict(row["rank_histogram"])

    artifact = {
        "artifact_kind": "stage638_fresh_entity_rank3_bridge_dataset",
        "source_manifest": str(SOURCE),
        "train_miss_details_path": str(DETAILS),
        "manifest_path": str(manifest_path),
        "target_op": TARGET_OP,
        "max_rank": MAX_RANK,
        "base_train_examples": len(train_rows),
        "replay_examples": len(replay_rows),
        "train_examples": len(train_out_rows),
        "eval_examples": len(eval_rows),
        "selected_rank_histogram": dict(rank_hist),
        "stage636_train_residual_summary": cleaned_summary,
        "train_operation_counts": dict(Counter(str(row.get("operation", "") or "") for row in train_out_rows)),
    }
    ARTIFACT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
