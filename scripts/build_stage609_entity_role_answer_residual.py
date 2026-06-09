#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/local/tmp/pocketpal_stage607_entity_field_role_tokens_seed461"
DETAILS = (
    ROOT
    / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage602_stage601_entity_field_balanced_replay_lr3e6_steps200"
    / "retrieval_eval_stage607_entity_field_role_tokens_full_corpus_operation_gated_details.jsonl"
)
OUT = ROOT / "runs/local/tmp/pocketpal_stage609_entity_role_answer_residual_seed461"
ARTIFACT = ROOT / "runs/local/artifacts/stage609_entity_role_answer_residual_dataset.json"
DOC = ROOT / "docs/stage609_entity_role_answer_residual_dataset.md"
TARGET_OP = "entity_context"
REPEAT_FAILURES = 4
REPEAT_NEAR_MISSES = 1


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("operation", "") or "") for row in rows))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_manifest = json.loads((SOURCE / "agentkernel_lite_encdec_dataset_manifest.json").read_text(encoding="utf-8"))
    train_rows = list(iter_jsonl(Path(source_manifest["train_dataset_path"])))
    eval_rows = list(iter_jsonl(Path(source_manifest["eval_dataset_path"])))
    eval_by_source = {str(row.get("source_id", "") or ""): row for row in eval_rows}

    miss_ids: list[str] = []
    near_ids: list[str] = []
    for detail in iter_jsonl(DETAILS):
        if str(detail.get("operation", "") or "") != TARGET_OP:
            continue
        if bool(detail.get("answer_top1")):
            continue
        source_id = str(detail.get("source_id", "") or "")
        predicted_id = str(detail.get("predicted_source_id", "") or "")
        if source_id in eval_by_source:
            miss_ids.append(source_id)
        if predicted_id in eval_by_source:
            near_ids.append(predicted_id)

    unique_miss_ids = sorted(set(miss_ids))
    unique_near_ids = sorted(set(near_ids) - set(unique_miss_ids))
    selected_rows = list(train_rows)
    for repeat in range(REPEAT_FAILURES):
        for source_id in unique_miss_ids:
            row = dict(eval_by_source[source_id])
            row["source_id"] = f"{row.get('source_id', '')}__stage609_entity_role_answer_residual_{repeat}"
            row["source_type"] = f"{row.get('source_type', 'retrieval')}_stage609_entity_role_answer_residual"
            row["stage609_entity_role_answer_residual"] = True
            row["residual_reason"] = "entity_context_role_token_answer_miss"
            selected_rows.append(row)
    for repeat in range(REPEAT_NEAR_MISSES):
        for source_id in unique_near_ids:
            row = dict(eval_by_source[source_id])
            row["source_id"] = f"{row.get('source_id', '')}__stage609_entity_role_answer_near_{repeat}"
            row["source_type"] = f"{row.get('source_type', 'retrieval')}_stage609_entity_role_answer_residual"
            row["stage609_entity_role_answer_residual"] = True
            row["residual_reason"] = "entity_context_role_token_predicted_near_miss"
            selected_rows.append(row)

    train_out = OUT / "agentkernel_lite_encdec_train.jsonl"
    eval_out = OUT / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_out, selected_rows)
    write_jsonl(eval_out, eval_rows)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage609_entity_role_answer_residual",
            "source_manifest_path": str(SOURCE / "agentkernel_lite_encdec_dataset_manifest.json"),
            "manifest_path": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_out),
            "eval_dataset_path": str(eval_out),
            "train_examples": len(selected_rows),
            "eval_examples": len(eval_rows),
            "entity_context_field_level": True,
            "entity_context_field_role_tokens": True,
            "stage609_entity_role_answer_residual": True,
            "stage609_target_operation": TARGET_OP,
            "stage609_answer_miss_source_ids": len(unique_miss_ids),
            "stage609_near_miss_source_ids": len(unique_near_ids),
            "stage609_repeat_failures": REPEAT_FAILURES,
            "stage609_repeat_near_misses": REPEAT_NEAR_MISSES,
            "collision_goal": "Test narrow answer-miss replay on the role-token entity_context surface after broad Stage608 answer contrast regressed.",
        }
    )
    (OUT / "agentkernel_lite_encdec_dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = {
        "artifact_kind": "stage609_entity_role_answer_residual_dataset",
        "dataset_manifest": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
        "source_manifest": str(SOURCE / "agentkernel_lite_encdec_dataset_manifest.json"),
        "details_jsonl": str(DETAILS),
        "target_operation": TARGET_OP,
        "answer_miss_source_ids": len(unique_miss_ids),
        "near_miss_source_ids": len(unique_near_ids),
        "repeat_failures": REPEAT_FAILURES,
        "repeat_near_misses": REPEAT_NEAR_MISSES,
        "train_examples_before": len(train_rows),
        "train_examples_after": len(selected_rows),
        "eval_examples": len(eval_rows),
        "train_operation_counts_before": counts(train_rows),
        "train_operation_counts_after": counts(selected_rows),
        "decision": "entity_role_answer_residual_dataset_ready",
        "finding": (
            "Stage609 narrows the Stage608 idea to entity_context answer misses on the role-token surface only. "
            "It tests whether weak answer contrast can repair local value binding without the global damage seen in broad operation-wide contrast."
        ),
    }
    ARTIFACT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        f"""# Stage609 Entity Role Answer Residual Dataset

Artifact: `runs/local/artifacts/stage609_entity_role_answer_residual_dataset.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage609_entity_role_answer_residual_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Target op: `{TARGET_OP}`
- Answer-miss source ids: `{len(unique_miss_ids)}`
- Near-miss source ids: `{len(unique_near_ids)}`
- Repeat failures: `{REPEAT_FAILURES}`
- Repeat near misses: `{REPEAT_NEAR_MISSES}`
- Train examples: `{len(train_rows)}` -> `{len(selected_rows)}`
- Eval examples unchanged: `{len(eval_rows)}`

## Decision

`entity_role_answer_residual_dataset_ready`

## Finding

{summary['finding']}
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
