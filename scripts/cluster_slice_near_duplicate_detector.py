from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
from typing import Any


def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def row_hash(row: dict[str, Any]) -> str:
    return hashlib.sha256(stable_json(row).encode("utf-8")).hexdigest()


def semantic_key(row: dict[str, Any]) -> str:
    for key in ["semantic_key", "row_semantic_key", "objective_key"]:
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    objective = row.get("objective_family") or row.get("objective") or ""
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    graph = row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}
    query = row.get("query") if isinstance(row.get("query"), dict) else {}
    action = clean.get("binding_action") or clean.get("action") or row.get("target")
    return stable_json({"objective": objective, "action": action, "query_kind": graph.get("query_kind"), "query_node": query.get("query_node_id")})


def source_cluster_key(row: dict[str, Any]) -> str:
    source_lineage = row.get("source_lineage") if isinstance(row.get("source_lineage"), dict) else {}
    return stable_json(
        {
            "nodes": source_lineage.get("graph_nodes_source_id"),
            "spans": source_lineage.get("graph_spans_source_id"),
            "old": source_lineage.get("old_source_ref_path"),
        }
    )


def slice_key(row: dict[str, Any]) -> str:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    graph = row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}
    return stable_json(
        {
            "objective": row.get("objective_family") or row.get("objective"),
            "action": clean.get("binding_action") or clean.get("action"),
            "query_kind": graph.get("query_kind"),
        }
    )


def near_duplicate_text(row: dict[str, Any]) -> str:
    pieces: list[str] = []
    for key in ["encoder_text", "decoder_text", "target_text", "input_text", "graph_input", "query", "clean_state"]:
        value = row.get(key)
        if isinstance(value, str):
            pieces.append(value)
        elif isinstance(value, (dict, list)):
            pieces.append(stable_json(value))
    return "\n".join(pieces)


def shingles(text: str, n: int = 5) -> set[str]:
    compact = " ".join(text.lower().split())
    if len(compact) <= n:
        return {compact} if compact else set()
    return {compact[i : i + n] for i in range(len(compact) - n + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def detect_clusters(rows: list[dict[str, Any]], *, near_duplicate_threshold: float = 0.92, max_pair_checks: int = 25000) -> dict[str, Any]:
    row_records: list[dict[str, Any]] = []
    exact_clusters: dict[str, list[str]] = collections.defaultdict(list)
    semantic_clusters: dict[str, list[str]] = collections.defaultdict(list)
    source_clusters: dict[str, list[str]] = collections.defaultdict(list)
    slice_clusters: dict[str, list[str]] = collections.defaultdict(list)
    split_by_semantic: dict[str, set[str]] = collections.defaultdict(set)
    split_by_hash: dict[str, set[str]] = collections.defaultdict(set)
    shingle_cache: list[tuple[str, set[str]]] = []

    for idx, row in enumerate(rows):
        row_id = str(row.get("row_id") or row.get("candidate_id") or row.get("id") or f"row_{idx}")
        h = row_hash(row)
        sk = semantic_key(row)
        src = source_cluster_key(row)
        sl = slice_key(row)
        split = str(row.get("split") or "unknown")
        exact_clusters[h].append(row_id)
        semantic_clusters[sk].append(row_id)
        source_clusters[src].append(row_id)
        slice_clusters[sl].append(row_id)
        split_by_semantic[sk].add(split)
        split_by_hash[h].add(split)
        shingle_cache.append((row_id, shingles(near_duplicate_text(row))))
        row_records.append({"row_id": row_id, "row_hash": h, "semantic_key": sk, "source_cluster_key": src, "slice_key": sl, "split": split})

    near_pairs: list[dict[str, Any]] = []
    checked = 0
    for i in range(len(shingle_cache)):
        if checked >= max_pair_checks:
            break
        left_id, left = shingle_cache[i]
        for j in range(i + 1, len(shingle_cache)):
            checked += 1
            if checked > max_pair_checks:
                break
            right_id, right = shingle_cache[j]
            score = jaccard(left, right)
            if score >= near_duplicate_threshold:
                near_pairs.append({"left": left_id, "right": right_id, "jaccard": round(score, 4)})

    exact_duplicate_clusters = {k: v for k, v in exact_clusters.items() if len(v) > 1}
    semantic_duplicate_clusters = {k: v for k, v in semantic_clusters.items() if len(v) > 1}
    exact_split_overlaps = {k: sorted(v) for k, v in split_by_hash.items() if len(v) > 1}
    semantic_split_overlaps = {k: sorted(v) for k, v in split_by_semantic.items() if len(v) > 1}
    undercovered_slices = {k: v for k, v in slice_clusters.items() if len(v) < 3}

    return {
        "rows": len(rows),
        "row_records": row_records,
        "metrics": {
            "exact_duplicate_clusters": len(exact_duplicate_clusters),
            "semantic_duplicate_clusters": len(semantic_duplicate_clusters),
            "near_duplicate_pairs": len(near_pairs),
            "exact_split_overlap_clusters": len(exact_split_overlaps),
            "semantic_split_overlap_clusters": len(semantic_split_overlaps),
            "source_clusters": len(source_clusters),
            "slice_clusters": len(slice_clusters),
            "undercovered_slices": len(undercovered_slices),
            "near_duplicate_pair_checks": checked,
        },
        "clusters": {
            "exact_duplicate_clusters": exact_duplicate_clusters,
            "semantic_duplicate_clusters": semantic_duplicate_clusters,
            "exact_split_overlaps": exact_split_overlaps,
            "semantic_split_overlaps": semantic_split_overlaps,
            "undercovered_slices": undercovered_slices,
            "near_duplicate_pairs": near_pairs[:200],
        },
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect exact, semantic, source, slice, split-overlap, and near-duplicate clusters.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--near-duplicate-threshold", type=float, default=0.92)
    args = parser.parse_args()
    card = detect_clusters(read_jsonl(args.manifest), near_duplicate_threshold=args.near_duplicate_threshold)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
