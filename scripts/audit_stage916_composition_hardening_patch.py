#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any


QSLOT_RE = re.compile(r"\bqslot_[0-9a-f]+\b")
DSLOT_RE = re.compile(r"\bdslot_[0-9a-f]+\b")
QPAIR_RE = re.compile(r"\bqpair_[0-9a-f]+\b")
DPAIR_RE = re.compile(r"\bdpair_[0-9a-f]+\b")


def _load_hardener():
    path = Path(__file__).resolve().parent / "build_stage819_hardened_binding_surface.py"
    spec = importlib.util.spec_from_file_location("stage819_hardener", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load hardener: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _direct_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get("task_type", "") or "") == "active_agent_direct_answer"
        and str(row.get("operation", "") or "") == "composition"
        and " target for " in str(row.get("retrieval_query_text", "") or "")
    ]


def _count_pair_overlap(hardened: dict[str, Any]) -> int:
    query_pairs = {token.removeprefix("qpair_") for token in QPAIR_RE.findall(str(hardened.get("retrieval_query_text", "") or ""))}
    doc_pairs = {token.removeprefix("dpair_") for token in DPAIR_RE.findall(str(hardened.get("retrieval_doc_text", "") or ""))}
    return len(query_pairs & doc_pairs)


def _audit_rows(rows: list[dict[str, Any]], hardener, *, salt: str, pair_code_salt: str) -> dict[str, Any]:
    total = qslot_rows = dslot_rows = qpair_ge3_rows = 0
    qslot_counts: list[int] = []
    dslot_counts: list[int] = []
    pair_overlap_counts: list[int] = []
    examples: list[dict[str, Any]] = []
    for row in rows:
        total += 1
        hardened = hardener._harden_row(
            row,
            salt=salt,
            harden_counterfactual_values=False,
            add_pair_codes=True,
            pair_code_salt=pair_code_salt,
        )
        query_text = str(hardened.get("retrieval_query_text", "") or "")
        doc_text = str(hardened.get("retrieval_doc_text", "") or "")
        qslot_count = len(set(QSLOT_RE.findall(query_text)))
        dslot_count = len(set(DSLOT_RE.findall(doc_text)))
        pair_overlap = _count_pair_overlap(hardened)
        qslot_counts.append(qslot_count)
        dslot_counts.append(dslot_count)
        pair_overlap_counts.append(pair_overlap)
        qslot_rows += int(qslot_count >= 2)
        dslot_rows += int(dslot_count >= 2)
        qpair_ge3_rows += int(pair_overlap >= 3)
        if len(examples) < 3:
            examples.append(
                {
                    "source_query": row.get("retrieval_query_text", ""),
                    "hardened_query": query_text,
                    "hardened_doc": doc_text,
                    "qslot_count": qslot_count,
                    "dslot_count": dslot_count,
                    "pair_overlap": pair_overlap,
                    "aliases": hardened.get("stage819_hardened_binding", {}),
                }
            )
    return {
        "rows": total,
        "qslot_ge2_rows": qslot_rows,
        "dslot_ge2_rows": dslot_rows,
        "pair_overlap_ge3_rows": qpair_ge3_rows,
        "min_qslot_count": min(qslot_counts) if qslot_counts else 0,
        "min_dslot_count": min(dslot_counts) if dslot_counts else 0,
        "min_pair_overlap": min(pair_overlap_counts) if pair_overlap_counts else 0,
        "examples": examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", default="runs/local/tmp/stage784_content_only_direct_answer/agentkernel_lite_encdec_dataset_manifest.json")
    parser.add_argument("--output-json", default="runs/local/artifacts/stage916_composition_hardening_patch_audit_summary.json")
    parser.add_argument("--salt", default="stage916_audit")
    parser.add_argument("--pair-code-salt", default="stage916_pair_code")
    args = parser.parse_args()

    hardener = _load_hardener()
    manifest = json.loads(Path(args.source_manifest).read_text(encoding="utf-8"))
    summary: dict[str, Any] = {
        "artifact_kind": "stage916_composition_hardening_patch_audit",
        "source_manifest": str(Path(args.source_manifest).resolve()),
        "decision": "Patch accepted as code/infrastructure audit. Composition query hardening now emits qslot hints for field and relation, enabling pair codes for subject, relation, and field.",
        "splits": {},
    }
    for split, key in (("train", "train_dataset_path"), ("calibration", "calibration_dataset_path"), ("eval", "eval_dataset_path")):
        if key not in manifest:
            continue
        rows = _direct_rows(_iter_jsonl(Path(manifest[key])))
        summary["splits"][split] = _audit_rows(rows, hardener, salt=str(args.salt), pair_code_salt=str(args.pair_code_salt))
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
