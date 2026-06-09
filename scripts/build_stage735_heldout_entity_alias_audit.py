#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENTITY_RE = re.compile(r"\b(gdom_\d+_e\d+)\b")
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


def alias_entities(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str], int]:
    entities = sorted({entity for row in rows for field in TEXT_FIELDS for entity in ENTITY_RE.findall(str(row.get(field, "") or ""))})
    mapping = {entity: f"gdom_999_e{index:05d}" for index, entity in enumerate(entities)}
    replaced = 0
    rewritten_rows: list[dict[str, Any]] = []
    for row in rows:
        out = dict(row)
        row_replaced = 0
        for field in TEXT_FIELDS:
            if field not in out:
                continue

            def repl(match: re.Match[str]) -> str:
                nonlocal row_replaced
                row_replaced += 1
                return mapping[match.group(1)]

            out[field] = ENTITY_RE.sub(repl, str(out.get(field, "") or ""))
        out["stage735_heldout_entity_alias_audit"] = True
        out["stage735_entity_alias_replacements"] = row_replaced
        replaced += row_replaced
        rewritten_rows.append(out)
    return rewritten_rows, mapping, replaced


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-manifest",
        default="runs/local/tmp/stage734_qidless_collision_audit/agentkernel_lite_encdec_dataset_manifest.json",
    )
    parser.add_argument("--output-dir", default="runs/local/tmp/stage735_heldout_entity_alias_audit")
    parser.add_argument("--artifact-json", default="runs/local/artifacts/stage735_heldout_entity_alias_audit.json")
    args = parser.parse_args()

    source_manifest_path = (ROOT / args.source_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    train_rows = [row for row in iter_jsonl(Path(str(source_manifest["train_dataset_path"])))]
    eval_rows = [row for row in iter_jsonl(Path(str(source_manifest["eval_dataset_path"])))]
    aliased_eval_rows, mapping, replacements = alias_entities(eval_rows)

    output_dir = (ROOT / args.output_dir).resolve()
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_path, train_rows)
    write_jsonl(eval_path, aliased_eval_rows)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage735_heldout_entity_alias_audit",
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(train_rows),
            "eval_examples": len(aliased_eval_rows),
            "stage735_source_manifest": str(source_manifest_path),
            "stage735_heldout_entity_alias_audit": True,
            "stage735_eval_distinct_entities_aliased": len(mapping),
            "stage735_eval_entity_alias_replacements": replacements,
            "stage735_goal": "Audit whether text_domain_field_entity works with unseen eval entity anchors, not memorized original entity strings.",
            "timestamp": int(time.time()),
        }
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = {
        "artifact_kind": "stage735_heldout_entity_alias_audit",
        "source_manifest": str(source_manifest_path),
        "dataset_manifest": str(manifest_path),
        "train_rows": len(train_rows),
        "eval_rows": len(aliased_eval_rows),
        "eval_distinct_entities_aliased": len(mapping),
        "eval_entity_alias_replacements": replacements,
        "alias_prefix": "gdom_999_e",
        "decision_rule": "Stage733 should retain >=8 answer KBPP if the factor is reusable and not dependent on memorized original entity strings.",
        "timestamp": int(time.time()),
    }
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
