#!/usr/bin/env python3
"""Attach Stage8625 recoverable candidates to the central graph as an index.

The Stage8625 scrape has many dataset-source rows. This stage keeps the graph
usable by adding aggregate category/root nodes plus explicit high-value direct
and architecture nodes. It does not copy candidate files or authorize training.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_GRAPH = ROOT / "runs" / "local" / "artifacts" / "stage8624_arxiv_recovery_graph_attachment" / "central_research_graph_with_arxiv_sources.json"
CANDIDATES = ROOT / "runs" / "local" / "artifacts" / "stage8623_arxiv_recoverables_scrape" / "recoverable_candidates.jsonl"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8627_recoverables_graph_index"
SUMMARY_PATH = ROOT / "runs" / "summaries" / "stage8627_reconstructed_recoverables_graph_index.json"
DOC_PATH = ROOT / "docs" / "RECOVERABLES_GRAPH_INDEX_STAGE8627.md"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

HIGH_VALUE_KEYWORDS = {
    "agentkernel",
    "agentkernel_lite",
    "seq2seq",
    "100m",
    "repo_state_graph",
    "bounded_decoder",
    "model_stack",
    "model_family_stack",
    "symbol_binding",
    "edit_localization",
    "patch_operator",
    "verifier_repair",
    "codegraph",
    "repo_graph",
    "program_graph",
}

HIGH_VALUE_PATH_HINTS = [
    "agentkernel-seq2seq-text-lab",
    "agentkernel_lite",
    "bounded_decoder",
    "repo_state_graph",
    "code_graph.py",
    "repo_graph.py",
    "program_graph.py",
    "build_repo_tree_of_life.py",
    "build_repositories_spans.py",
    "build_joint_training_bundle",
    "tolbert_brain/data_builder.py",
    "OpenHands",
    "SWE-agent",
    "RepairThemAll",
    "Aider-AI",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def load_candidates() -> list[dict[str, Any]]:
    rows = []
    with CANDIDATES.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def node_id(kind: str, name: str) -> str:
    clean = str(name).replace("/", "_").replace(" ", "_").replace(":", "_")
    return f"{kind}:{clean}"


def add_node(nodes: dict[str, dict[str, Any]], kind: str, name: str, **attrs: Any) -> str:
    nid = node_id(kind, name)
    current = nodes.get(nid, {})
    nodes[nid] = {"id": nid, "kind": kind, "name": name, **current, **attrs}
    return nid


def add_edge(edges: list[dict[str, Any]], src: str, rel: str, dst: str, **attrs: Any) -> None:
    key = (src, rel, dst)
    if any((e["source"], e["relation"], e["target"]) == key for e in edges):
        return
    edges.append({"source": src, "relation": rel, "target": dst, **attrs})


def is_high_value(row: dict[str, Any]) -> bool:
    path = row["path"]
    path_l = path.lower()
    hits = set(row.get("keyword_hits", []))
    if row.get("category") == "likely_direct_recovery":
        return True
    if hits & HIGH_VALUE_KEYWORDS:
        return True
    return any(hint.lower() in path_l for hint in HIGH_VALUE_PATH_HINTS)


def priority(row: dict[str, Any]) -> tuple[int, int, str]:
    category_score = {
        "likely_direct_recovery": 0,
        "architecture_related": 1,
        "keyword_related": 2,
        "dataset_source": 3,
    }.get(row.get("category"), 9)
    keyword_score = -len(set(row.get("keyword_hits", [])) & HIGH_VALUE_KEYWORDS)
    return category_score, keyword_score, row["path"]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    category_counts = Counter(r["category"] for r in rows)
    root_counts = Counter(r["root"] for r in rows)
    keyword_counts: Counter[str] = Counter()
    for row in rows:
        keyword_counts.update(row.get("keyword_hits", []))
    high_value = sorted([r for r in rows if is_high_value(r)], key=priority)
    roots_by_category: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        roots_by_category[row["category"]][row["root"]] += 1
    return {
        "candidate_rows": len(rows),
        "category_counts": dict(sorted(category_counts.items())),
        "root_counts": dict(sorted(root_counts.items())),
        "keyword_counts": dict(sorted(keyword_counts.items())),
        "high_value_count": len(high_value),
        "high_value_candidates": high_value[:500],
        "roots_by_category": {k: dict(v.most_common()) for k, v in sorted(roots_by_category.items())},
    }


def attach_graph(index: dict[str, Any]) -> dict[str, Any]:
    graph = load_json(INPUT_GRAPH)
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = list(graph["edges"])

    stage = add_node(nodes, "stage", "8627", stage_name="stage8627_reconstructed_recoverables_graph_index", passed=True)
    index_node = add_node(
        nodes,
        "recovery_index",
        "stage8625_arxiv_recoverables",
        candidate_rows=index["candidate_rows"],
        high_value_count=index["high_value_count"],
        path="runs/local/artifacts/stage8623_arxiv_recoverables_scrape/recoverable_candidates.jsonl",
    )
    add_edge(edges, stage, "attaches_recovery_index", index_node, evidence_source="stage8627")

    for category, count in index["category_counts"].items():
        cat = add_node(nodes, "recoverable_category", category, candidate_rows=count)
        add_edge(edges, index_node, "has_category", cat, evidence_source="stage8627")

    for root, count in index["root_counts"].items():
        root_node = add_node(nodes, "recoverable_root", root, candidate_rows=count)
        add_edge(edges, index_node, "has_root", root_node, evidence_source="stage8627")

    for keyword, count in index["keyword_counts"].items():
        keyword_node = add_node(nodes, "recoverable_keyword", keyword, hits=count)
        add_edge(edges, index_node, "has_keyword", keyword_node, evidence_source="stage8627")

    for row in index["high_value_candidates"]:
        source = add_node(
            nodes,
            "high_value_recovery_source",
            row["path"],
            category=row["category"],
            root=row["root"],
            size_bytes=row.get("size_bytes"),
            keyword_hits=row.get("keyword_hits", []),
            sha256_prefix_probe=row.get("sha256_prefix_probe"),
        )
        add_edge(edges, index_node, "prioritizes_source", source, evidence_source="stage8627")
        if row["category"] == "likely_direct_recovery":
            add_edge(edges, source, "may_recover", add_node(nodes, "objective_family", "bounded_decoder_ce"), evidence_source="stage8627")
        if any(k in row.get("keyword_hits", []) for k in ["repo_graph", "program_graph", "codegraph"]):
            add_edge(edges, source, "may_recover", add_node(nodes, "objective_family", "repo_state_graph_v1"), evidence_source="stage8627")

    graph["nodes"] = sorted(nodes.values(), key=lambda n: n["id"])
    graph["edges"] = sorted(edges, key=lambda e: (e["source"], e["relation"], e["target"]))
    graph["version"] = "stage8627_reconstructed_central_graph_with_recoverables_index"
    return graph


def write_doc(index: dict[str, Any], metrics: dict[str, Any]) -> None:
    top_roots = sorted(index["root_counts"].items(), key=lambda kv: kv[1], reverse=True)[:20]
    high_value = index["high_value_candidates"][:80]
    DOC_PATH.write_text(
        "\n".join(
            [
                "# Stage8627 Recoverables Graph Index",
                "",
                "This stage attaches the Stage8625 `/arxiv` recoverable-candidate scrape to the central research graph. It keeps the graph compact by adding aggregate category/root/keyword nodes and explicit high-value recovery-source nodes.",
                "",
                "No files were copied from candidates, no checkpoints were loaded, no model execution occurred, and no training authority was opened.",
                "",
                "## Counts",
                "",
                "```json",
                json.dumps({k: index[k] for k in ["candidate_rows", "category_counts", "keyword_counts", "high_value_count"]}, indent=2, sort_keys=True),
                "```",
                "",
                "## Top Roots",
                "",
                *[f"- `{root}`: {count}" for root, count in top_roots],
                "",
                "## Prioritized High-Value Sources",
                "",
                *[f"- `{row['category']}` `{row['path']}` hits={row.get('keyword_hits', [])}" for row in high_value],
                "",
                "## Next Recovery Use",
                "",
                "Use this index to select exact source material for rebuilding missing objective builders. Priority should be direct AgentKernel artifacts first, then repo graph/codegraph assets, then agent repos and software datasets.",
                "",
                "## Metrics",
                "",
                "```json",
                json.dumps(metrics, indent=2, sort_keys=True),
                "```",
                "",
            ]
        )
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows = load_candidates()
    index = summarize(rows)
    write_json(OUT_DIR / "recoverables_graph_index.json", index)
    with (OUT_DIR / "high_value_recovery_sources.jsonl").open("w", encoding="utf-8") as f:
        for row in index["high_value_candidates"]:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    graph = attach_graph(index)
    write_json(OUT_DIR / "central_research_graph_with_recoverables_index.json", graph)
    with (OUT_DIR / "central_research_graph_with_recoverables_index_nodes.jsonl").open("w", encoding="utf-8") as f:
        for node in graph["nodes"]:
            f.write(json.dumps(node, sort_keys=True) + "\n")
    with (OUT_DIR / "central_research_graph_with_recoverables_index_edges.jsonl").open("w", encoding="utf-8") as f:
        for edge in graph["edges"]:
            f.write(json.dumps(edge, sort_keys=True) + "\n")

    metrics = {
        "candidate_rows": index["candidate_rows"],
        "high_value_count": index["high_value_count"],
        "high_value_graph_nodes_added": len(index["high_value_candidates"]),
        "attached_graph_nodes": len(graph["nodes"]),
        "attached_graph_edges": len(graph["edges"]),
        "category_counts": index["category_counts"],
        "keyword_counts": index["keyword_counts"],
    }
    write_doc(index, metrics)

    summary = {
        "stage": 8627,
        "stage_name": "stage8627_reconstructed_recoverables_graph_index",
        "passed": True,
        "reconstructed": True,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "gates": {
            "stage8625_candidates_attached": True,
            "high_value_sources_prioritized": index["high_value_count"] > 0,
            "no_candidate_files_copied": True,
            "no_checkpoint_loaded": True,
            "no_model_execution": True,
            "authority_closed": True,
        },
        "artifacts": {
            "index": str((OUT_DIR / "recoverables_graph_index.json").relative_to(ROOT)),
            "high_value_sources": str((OUT_DIR / "high_value_recovery_sources.jsonl").relative_to(ROOT)),
            "attached_graph": str((OUT_DIR / "central_research_graph_with_recoverables_index.json").relative_to(ROOT)),
            "doc": str(DOC_PATH.relative_to(ROOT)),
        },
        "next_best_step": "Select high-value direct/graph recovery sources to rebuild the missing objective builders, starting with intent-to-build and edit-localization.",
        "notes": "Stage8627 adds Stage8625 as a compact recovery-source index in the central graph.",
    }
    write_json(SUMMARY_PATH, summary)
    print(json.dumps({"passed": True, "metrics": metrics, "summary": str(SUMMARY_PATH)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
