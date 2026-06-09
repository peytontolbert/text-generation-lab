#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/local/tmp/pocketpal_stage602_entity_field_balanced_replay_seed461"
OUT = ROOT / "runs/local/tmp/pocketpal_stage603_rule_intersection_repair_seed461"
ARTIFACT = ROOT / "runs/local/artifacts/stage603_rule_intersection_repair_dataset.json"
DOC = ROOT / "docs/stage603_rule_intersection_repair_dataset.md"
TARGET_REPLAY_OPS = {"rule_case_intersection_count", "rule_case_intersection_member"}
EXTRA_COPIES = 1


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

    replay_rows = list(train_rows)
    added_by_op: Counter[str] = Counter()
    for copy_index in range(EXTRA_COPIES):
        for row in train_rows:
            op = str(row.get("operation", "") or "")
            if op not in TARGET_REPLAY_OPS:
                continue
            clone = dict(row)
            clone["source_id"] = f"{row.get('source_id', '')}__stage603_rule_intersection_repair_{copy_index}"
            clone["stage603_rule_intersection_repair"] = True
            replay_rows.append(clone)
            added_by_op[op] += 1

    train_out = OUT / "agentkernel_lite_encdec_train.jsonl"
    eval_out = OUT / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_out, replay_rows)
    write_jsonl(eval_out, eval_rows)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage603_rule_intersection_repair",
            "source_manifest_path": str(SOURCE / "agentkernel_lite_encdec_dataset_manifest.json"),
            "manifest_path": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_out),
            "eval_dataset_path": str(eval_out),
            "train_examples": len(replay_rows),
            "eval_examples": len(eval_rows),
            "entity_context_field_level": True,
            "stage603_rule_intersection_repair": True,
            "stage603_rule_intersection_repair_ops": sorted(TARGET_REPLAY_OPS),
            "stage603_rule_intersection_repair_extra_copies": EXTRA_COPIES,
            "stage603_rule_intersection_repair_added_train_examples": sum(added_by_op.values()),
            "collision_goal": (
                "Keep Stage602 entity/direct/set gains while replaying the rule-intersection rows that showed small residual damage."
            ),
        }
    )
    (OUT / "agentkernel_lite_encdec_dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = {
        "artifact_kind": "stage603_rule_intersection_repair_dataset",
        "dataset_manifest": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
        "source_manifest": str(SOURCE / "agentkernel_lite_encdec_dataset_manifest.json"),
        "target_replay_ops": sorted(TARGET_REPLAY_OPS),
        "extra_copies": EXTRA_COPIES,
        "added_train_examples": sum(added_by_op.values()),
        "added_train_examples_by_op": dict(sorted(added_by_op.items())),
        "train_examples_before": len(train_rows),
        "train_examples_after": len(replay_rows),
        "eval_examples": len(eval_rows),
        "train_operation_counts_before": counts(train_rows),
        "train_operation_counts_after": counts(replay_rows),
        "decision": "rule_intersection_repair_dataset_ready",
        "finding": (
            "Stage603 keeps the Stage602 balanced field-context mix and adds one replay copy of rule_case_intersection_count "
            "and rule_case_intersection_member to target the remaining small rule-intersection damage."
        ),
    }
    ARTIFACT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        f"""# Stage603 Rule Intersection Repair Dataset

Artifact: `runs/local/artifacts/stage603_rule_intersection_repair_dataset.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage603_rule_intersection_repair_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Target replay ops: `{', '.join(sorted(TARGET_REPLAY_OPS))}`
- Extra copies per target train row: `{EXTRA_COPIES}`
- Added train examples: `{sum(added_by_op.values())}`
- Train examples: `{len(train_rows)}` -> `{len(replay_rows)}`
- Eval examples unchanged: `{len(eval_rows)}`

## Decision

`rule_intersection_repair_dataset_ready`

## Finding

{summary['finding']}
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
