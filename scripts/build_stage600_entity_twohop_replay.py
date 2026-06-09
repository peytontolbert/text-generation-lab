#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/local/tmp/pocketpal_stage596_collision_conditioned_seed461"
OUT = ROOT / "runs/local/tmp/pocketpal_stage600_entity_twohop_replay_seed461"
ARTIFACT = ROOT / "runs/local/artifacts/stage600_entity_twohop_replay_dataset.json"
DOC = ROOT / "docs/stage600_entity_twohop_replay_dataset.md"
TARGET_OPS = {"entity_context", "two_hop_owner_region"}
EXTRA_COPIES = 8


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
    added = 0
    for copy_index in range(EXTRA_COPIES):
        for row in train_rows:
            if str(row.get("operation", "") or "") not in TARGET_OPS:
                continue
            clone = dict(row)
            clone["source_id"] = f"{row.get('source_id', '')}__entity_twohop_replay_{copy_index}"
            clone["entity_twohop_replay"] = True
            replay_rows.append(clone)
            added += 1

    train_out = OUT / "agentkernel_lite_encdec_train.jsonl"
    eval_out = OUT / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_out, replay_rows)
    write_jsonl(eval_out, eval_rows)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage600_entity_twohop_replay",
            "source_manifest_path": str(SOURCE / "agentkernel_lite_encdec_dataset_manifest.json"),
            "manifest_path": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_out),
            "eval_dataset_path": str(eval_out),
            "train_examples": len(replay_rows),
            "eval_examples": len(eval_rows),
            "entity_twohop_replay": True,
            "entity_twohop_replay_ops": sorted(TARGET_OPS),
            "entity_twohop_replay_extra_copies": EXTRA_COPIES,
            "entity_twohop_replay_added_train_examples": added,
            "collision_goal": "Heavily oversample entity_context and two_hop_owner_region collision rows while leaving eval unchanged.",
        }
    )
    (OUT / "agentkernel_lite_encdec_dataset_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "artifact_kind": "stage600_entity_twohop_replay_dataset",
        "dataset_manifest": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
        "source_manifest": str(SOURCE / "agentkernel_lite_encdec_dataset_manifest.json"),
        "target_ops": sorted(TARGET_OPS),
        "extra_copies": EXTRA_COPIES,
        "added_train_examples": added,
        "train_examples_before": len(train_rows),
        "train_examples_after": len(replay_rows),
        "eval_examples": len(eval_rows),
        "train_operation_counts_before": counts(train_rows),
        "train_operation_counts_after": counts(replay_rows),
        "decision": "entity_twohop_replay_dataset_ready",
        "finding": (
            "Stage600 isolates the two collision families that did not improve under Stage599 weak-op replay: entity_context and "
            "two_hop_owner_region. It heavily oversamples them without changing the Stage596 eval surface."
        ),
    }
    ARTIFACT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        f"""# Stage600 Entity/Two-Hop Replay Dataset

Artifact: `runs/local/artifacts/stage600_entity_twohop_replay_dataset.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage600_entity_twohop_replay_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Target ops: `{', '.join(sorted(TARGET_OPS))}`
- Extra copies per target train row: `{EXTRA_COPIES}`
- Added train examples: `{added}`
- Train examples: `{len(train_rows)}` -> `{len(replay_rows)}`
- Eval examples unchanged: `{len(eval_rows)}`

## Decision

`entity_twohop_replay_dataset_ready`

## Finding

{summary['finding']}
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
