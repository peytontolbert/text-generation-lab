#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/local/tmp/stage653_generalized_8kbpp_surface/agentkernel_lite_encdec_dataset_manifest.json"
OUT = ROOT / "runs/local/tmp/stage655_generalized_bridge_curriculum"
ARTIFACT = ROOT / "runs/local/artifacts/stage655_generalized_bridge_curriculum.json"
DOC = ROOT / "docs/stage655_generalized_bridge_curriculum.md"
TEXT_FIELDS = {
    "decoder_text",
    "encoder_text",
    "json_decoder_text",
    "negative_decoder_text",
    "retrieval_doc_text",
    "retrieval_query_text",
    "state_text",
}
KEY_VALUE_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*?)=([^\s;]+)")


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


def qid_parts(row: dict[str, Any]) -> dict[str, str]:
    text = str(row.get("retrieval_query_text", "") or "")
    keys = key_values(text)
    qid = keys.get("qid", str(row.get("source_id", "") or ""))
    return {"qid": qid, **keys}


def selector_for(row: dict[str, Any]) -> str:
    op = str(row.get("operation", "") or "")
    family = str(row.get("stage653_unit_family", "") or "")
    domain = str(row.get("retrieval_query_text", "") or "").split(" domain=", 1)[-1].split(" ", 1)[0]
    query = str(row.get("retrieval_query_text", "") or "")
    statement = query.split(" query=", 1)[-1] if " query=" in query else query
    tokens = statement.split()
    qid = qid_parts(row).get("qid", "")
    if op == "atomic_fact" and len(tokens) >= 3 and tokens[1] == "has":
        entity, prop = tokens[0], tokens[2]
        return f"fact|{domain}|{prop}|{entity}"
    if op == "relation" and len(tokens) >= 2:
        entity, relation = tokens[0], tokens[1]
        return f"rel|{domain}|{relation}|{entity}"
    if op == "composition":
        if statement.startswith("count entities where "):
            parts = statement.replace("count entities where ", "").split()
            prop = parts[0] if parts else "field"
            value = parts[-1] if parts else "value"
            return f"setcount|{domain}|{prop}|{value}"
        if " target for " in statement:
            left, entity = statement.rsplit(" target for ", 1)
            prop, _, rel = left.partition(" of ")
            return f"compose2|{domain}|{rel}|{prop}|{entity}"
        return f"compose|{domain}|{qid}"
    if op == "counterfactual_false_claim" and len(tokens) >= 6:
        entity = tokens[1]
        prop = tokens[3]
        claimed = tokens[4].rstrip(";")
        return f"neg|{domain}|{prop}|{entity}|{claimed}"
    if op == "exception" and len(tokens) >= 4:
        entity = tokens[0]
        prop = tokens[-1]
        return f"exception|{domain}|{prop}|{entity}"
    if op == "math_identity":
        return f"math|h|{qid}"
    if op == "code_api_semantics":
        api = tokens[-1] if tokens else qid
        return f"api|{api}"
    return f"{family}|{domain}|{qid}"


def insert_selector(text: str, selector: str) -> str:
    if "gsel=" in text:
        return re.sub(r"gsel=[^\s]+", f"gsel={selector}", text)
    op_match = re.search(r"(<AK_OP_[^>]+>|op=[^\s]+)", text)
    if op_match:
        return text[: op_match.end()] + f" gsel={selector}" + text[op_match.end() :]
    return f"gsel={selector} {text}"


def rewrite_row(row: dict[str, Any]) -> dict[str, Any]:
    selector = selector_for(row)
    out: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, str) and key in TEXT_FIELDS:
            out[key] = insert_selector(value, selector)
        else:
            out[key] = value
    out["stage655_generalized_selector"] = selector
    out["stage655_bridge_curriculum"] = True
    out["source_type"] = f"{row.get('source_type', 'stage653_generalized_8kbpp_surface')}_stage655_selector_bridge"
    return out


def token_stats(rows: list[dict[str, Any]]) -> dict[str, float]:
    if not rows:
        return {"avg_query_doc_whitespace_tokens": 0.0}
    total = 0
    for row in rows:
        total += len(str(row.get("retrieval_query_text", "") or "").split())
        total += len(str(row.get("retrieval_doc_text", "") or "").split())
    return {"avg_query_doc_whitespace_tokens": total / len(rows)}


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    split_paths: dict[str, Path] = {}
    split_stats: dict[str, Any] = {}
    stage_paths: dict[str, str] = {}
    for split in ("train", "eval"):
        rows = [rewrite_row(row) for row in iter_jsonl(Path(source[f"{split}_dataset_path"]))]
        path = OUT / f"agentkernel_lite_encdec_{split}.jsonl"
        write_jsonl(path, rows)
        split_paths[split] = path
        families = Counter(str(row.get("stage653_unit_family", "") or "") for row in rows)
        selectors = Counter(str(row.get("stage655_generalized_selector", "") or "") for row in rows)
        split_stats[split] = {
            "rows": len(rows),
            "families": dict(sorted(families.items())),
            "distinct_selectors": len(selectors),
            "selector_collisions": sum(count for count in selectors.values() if count > 1),
            "max_selector_group": max(selectors.values()) if selectors else 0,
            **token_stats(rows),
        }
        if split == "train":
            curriculum = {
                "stage1_bindings": {"atomic_facts", "relations_and_sets"},
                "stage2_compositions": {"atomic_facts", "relations_and_sets", "multi_hop_compositions"},
                "stage3_full": set(families),
            }
            for name, allowed in curriculum.items():
                stage_rows = [row for row in rows if str(row.get("stage653_unit_family", "") or "") in allowed]
                stage_path = OUT / f"agentkernel_lite_encdec_train_{name}.jsonl"
                write_jsonl(stage_path, stage_rows)
                stage_paths[name] = str(stage_path)

    manifest = dict(source)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage655_generalized_bridge_curriculum",
            "source_manifest_path": str(SOURCE),
            "manifest_path": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(split_paths["train"]),
            "eval_dataset_path": str(split_paths["eval"]),
            "train_examples": split_stats["train"]["rows"],
            "eval_examples": split_stats["eval"]["rows"],
            "stage655_bridge_curriculum": True,
            "stage655_selector_field": "gsel",
            "stage655_curriculum_stage_paths": stage_paths,
            "stage655_goal": "Add compact family-specific selectors to make the Stage653 8-KBPP entropy surface learnable without changing verified units or bit accounting.",
            "stage655_stats": split_stats,
        }
    )
    manifest_path = OUT / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ARTIFACT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        f"""# Stage655 Generalized Bridge Curriculum

Artifact: `{ARTIFACT.relative_to(ROOT)}`

Manifest: `{manifest_path.relative_to(ROOT)}`

## Purpose

Stage654 showed that Stage653 has enough entropy but is not learnable by direct continuation. Stage655 keeps the same verified unit set and bit accounting, then adds compact `gsel=` selectors by family:

- facts: `fact|domain|field|entity`
- relations: `rel|domain|relation|entity`
- two-hop: `compose2|domain|relation|field|entity`
- set counts: `setcount|domain|field|value`
- counterfactuals: `neg|domain|field|entity|claimed`
- exceptions: `exception|domain|field|entity`

## Stats

- Train rows: `{split_stats['train']['rows']}`
- Eval rows: `{split_stats['eval']['rows']}`
- Train distinct selectors: `{split_stats['train']['distinct_selectors']}`
- Eval distinct selectors: `{split_stats['eval']['distinct_selectors']}`
- Train avg query+doc whitespace tokens: `{split_stats['train']['avg_query_doc_whitespace_tokens']}`
- Eval avg query+doc whitespace tokens: `{split_stats['eval']['avg_query_doc_whitespace_tokens']}`

## Next Gate

Run staged training or a full selectorized initialized probe. Acceptance is unchanged: no-filter generalized answer KBPP must clear `8.0`; hard-filter-only gains do not count.
""",
        encoding="utf-8",
    )
    print(json.dumps({"artifact": str(ARTIFACT), "manifest": str(manifest_path), "doc": str(DOC)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
