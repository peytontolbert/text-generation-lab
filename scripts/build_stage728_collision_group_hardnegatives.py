#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOKEN_RE = re.compile(r"[a-z0-9_]+")


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


def _answer_key(row: dict[str, Any]) -> str:
    return str(row.get("expected_content", row.get("decoder_text", "")) or "")


def _doc_text(row: dict[str, Any]) -> str:
    return str(row.get("retrieval_doc_text", "") or "")


def _tokens(text: str) -> set[str]:
    return set(TOKEN_RE.findall(str(text or "").lower()))


def select_same_collision_negatives(
    rows: list[dict[str, Any]],
    index: int,
    group_indices: list[int],
    *,
    max_negatives: int,
    selection: str,
) -> list[str]:
    row = rows[index]
    answer = _answer_key(row)
    original_gsel = str(row.get("stage726_original_gsel", "") or "")
    candidates: list[int] = []
    fallback: list[int] = []
    for candidate_index in group_indices:
        if candidate_index == index:
            continue
        candidate = rows[candidate_index]
        if _answer_key(candidate) == answer:
            continue
        if not _doc_text(candidate):
            continue
        fallback.append(candidate_index)
        if str(candidate.get("stage726_original_gsel", "") or "") != original_gsel:
            candidates.append(candidate_index)
    ordered = candidates or fallback
    if not ordered:
        return []

    if str(selection) == "lexical":
        query_tokens = _tokens(str(row.get("retrieval_query_text", "") or ""))

        def lexical_score(candidate_index: int) -> tuple[int, int, str]:
            candidate_tokens = _tokens(_doc_text(rows[candidate_index]))
            overlap = len(query_tokens & candidate_tokens)
            return (-overlap, abs(candidate_index - index), _doc_text(rows[candidate_index]))

        rotated = sorted(ordered, key=lexical_score)
    else:
        start = index % len(ordered)
        rotated = ordered[start:] + ordered[:start]
    negatives: list[str] = []
    seen: set[str] = set()
    for candidate_index in rotated:
        text = _doc_text(rows[candidate_index])
        if text in seen:
            continue
        seen.add(text)
        negatives.append(text)
        if len(negatives) >= max(0, int(max_negatives)):
            break
    return negatives


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-manifest",
        default="runs/local/tmp/stage726_selector_collision_factor_surface/agentkernel_lite_encdec_dataset_manifest.json",
    )
    parser.add_argument(
        "--output-dir",
        default="runs/local/tmp/stage728_collision_group_hardnegatives",
    )
    parser.add_argument(
        "--artifact-json",
        default="runs/local/artifacts/stage728_collision_group_hardnegatives.json",
    )
    parser.add_argument("--max-negatives", type=int, default=3)
    parser.add_argument("--loss-weight", type=float, default=1.0)
    parser.add_argument("--selection", choices=("rotate", "lexical"), default="rotate")
    args = parser.parse_args()

    source_manifest_path = (ROOT / args.source_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    train_rows = [row for row in iter_jsonl(Path(str(source_manifest["train_dataset_path"])))]
    eval_rows = [row for row in iter_jsonl(Path(str(source_manifest["eval_dataset_path"])))]

    groups: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(train_rows):
        selector = str(row.get("stage726_collision_gsel", "") or "")
        if selector:
            groups[selector].append(index)

    rewritten: list[dict[str, Any]] = []
    negative_counts: Counter[int] = Counter()
    rows_with_collision_group = 0
    for index, row in enumerate(train_rows):
        out = dict(row)
        selector = str(row.get("stage726_collision_gsel", "") or "")
        group_indices = groups.get(selector, [])
        if len(group_indices) > 1:
            rows_with_collision_group += 1
        negatives = select_same_collision_negatives(
            train_rows,
            index,
            group_indices,
            max_negatives=int(args.max_negatives),
            selection=str(args.selection),
        )
        out["retrieval_negative_doc_texts"] = negatives
        out["retrieval_loss_weight"] = float(out.get("retrieval_loss_weight", args.loss_weight) or args.loss_weight)
        out["stage728_collision_group_negative_count"] = len(negatives)
        out["stage728_collision_group_hardnegatives"] = True
        out["stage728_goal"] = (
            "Train value/entity discrimination inside shared Stage726 selector-collision groups, "
            "without restoring full selector identity as an allowed factor key."
        )
        negative_counts[len(negatives)] += 1
        rewritten.append(out)

    output_dir = (ROOT / args.output_dir).resolve()
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_path, rewritten)
    write_jsonl(eval_path, eval_rows)

    rows_with_negatives = sum(1 for row in rewritten if row["stage728_collision_group_negative_count"] > 0)
    total_negatives = sum(int(row["stage728_collision_group_negative_count"]) for row in rewritten)
    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage728_collision_group_hardnegatives",
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(rewritten),
            "eval_examples": len(eval_rows),
            "stage728_source_manifest": str(source_manifest_path),
            "stage728_collision_group_hardnegatives": True,
            "stage728_max_negatives_per_row": int(args.max_negatives),
            "stage728_negative_selection": str(args.selection),
            "stage728_rows_with_collision_group": rows_with_collision_group,
            "stage728_rows_with_negatives": rows_with_negatives,
            "stage728_total_negatives": total_negatives,
            "stage728_mean_negatives_per_train_row": total_negatives / max(len(rewritten), 1),
            "stage728_goal": (
                "Use same-coarse-selector wrong docs as hard negatives so the neural path must resolve "
                "entity/value evidence inside Stage726 collisions."
            ),
            "stage728_acceptance": (
                "Improve Stage727 no-filter answer KBPP on the Stage726 collision surface without using "
                "unique full-selector factor keys."
            ),
            "timestamp": int(time.time()),
        }
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = {
        "artifact_kind": "stage728_collision_group_hardnegatives",
        "source_manifest": str(source_manifest_path),
        "dataset_manifest": str(manifest_path),
        "rows": len(rewritten),
        "rows_with_collision_group": rows_with_collision_group,
        "rows_with_negatives": rows_with_negatives,
        "max_negatives_per_row": int(args.max_negatives),
        "negative_selection": str(args.selection),
        "mean_negatives_per_train_row": total_negatives / max(len(rewritten), 1),
        "negative_count_histogram": {str(key): value for key, value in sorted(negative_counts.items())},
        "decision_rule": (
            "If Stage728 moves materially above Stage727, collision-local value/entity discrimination is the "
            "next recursive factor. If it stays flat, the trainer needs factorized hard-negative logits or an "
            "explicit within-group ranker."
        ),
        "timestamp": int(time.time()),
    }
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
