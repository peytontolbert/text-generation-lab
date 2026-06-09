#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE626 = ROOT / "runs/local/tmp/recursive_kbpp_selector_stage626_rule_default_domain_selector/domain_entity_field_00fdde0fa6/agentkernel_lite_encdec_dataset_manifest.json"
STAGE628 = ROOT / "runs/local/tmp/pocketpal_stage628_canonical_selector_surface_seed461/agentkernel_lite_encdec_dataset_manifest.json"
OUT = ROOT / "runs/local/tmp/pocketpal_stage633_selector_bridge_mix_seed461"
ARTIFACT = ROOT / "runs/local/artifacts/stage633_selector_bridge_mix_dataset.json"


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def tagged(row: dict[str, Any], bridge_source: str) -> dict[str, Any]:
    out = dict(row)
    out["stage633_bridge_source"] = bridge_source
    out["source_type"] = f"{row.get('source_type', 'retrieval')}_stage633_{bridge_source}"
    return out


def interleave(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(max(len(left), len(right))):
        if index < len(left):
            rows.append(tagged(left[index], "stage626_accumulated"))
        if index < len(right):
            rows.append(tagged(right[index], "stage628_canonical"))
    return rows


def counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "examples": len(rows),
        "operation_counts": dict(Counter(str(row.get("operation", "") or "") for row in rows)),
        "bridge_source_counts": dict(Counter(str(row.get("stage633_bridge_source", "") or "") for row in rows)),
    }


def main() -> None:
    stage626 = json.loads(STAGE626.read_text(encoding="utf-8"))
    stage628 = json.loads(STAGE628.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)

    train626 = list(iter_jsonl(Path(stage626["train_dataset_path"])))
    train628 = list(iter_jsonl(Path(stage628["train_dataset_path"])))
    eval626 = list(iter_jsonl(Path(stage626["eval_dataset_path"])))
    eval628 = list(iter_jsonl(Path(stage628["eval_dataset_path"])))
    train_rows = interleave(train626, train628)
    eval_rows = interleave(eval626, eval628)

    train_path = OUT / "agentkernel_lite_encdec_train.jsonl"
    eval_path = OUT / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_path, train_rows)
    write_jsonl(eval_path, eval_rows)

    manifest = dict(stage626)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage633_selector_bridge_mix",
            "source_stage626_manifest": str(STAGE626),
            "source_stage628_manifest": str(STAGE628),
            "manifest_path": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(train_rows),
            "eval_examples": len(eval_rows),
            "stage633_bridge_mix": "interleaved_stage626_accumulated_and_stage628_canonical",
        }
    )
    manifest_path = OUT / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = {
        "artifact_kind": "stage633_selector_bridge_mix_dataset",
        "manifest_path": str(manifest_path),
        "source_stage626_manifest": str(STAGE626),
        "source_stage628_manifest": str(STAGE628),
        "train": counts(train_rows),
        "eval": counts(eval_rows),
    }
    ARTIFACT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
