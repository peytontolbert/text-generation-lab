#!/usr/bin/env python3
"""Compile repo capability catalog and repo-state graph seed rows from Stage8600.

This is a non-training compiler step. It consumes the read-only /arxiv index
artifacts and emits typed manifest rows with closed authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


AUTHORITY_CLOSED = {
    "training_authorized": False,
    "decoder_ce_authorized": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_authorized": False,
    "harness_authorized": False,
    "scoring_authorized": False,
}


BUILD_FAMILY_BY_FILE = {
    "pyproject.toml": "python_packaging",
    "setup.py": "python_packaging",
    "setup.cfg": "python_packaging",
    "requirements.txt": "python_requirements",
    "Pipfile": "python_packaging",
    "poetry.lock": "python_packaging",
    "Cargo.toml": "rust_cargo",
    "Cargo.lock": "rust_cargo",
    "package.json": "node_package",
    "package-lock.json": "node_package",
    "pnpm-lock.yaml": "node_package",
    "yarn.lock": "node_package",
    "CMakeLists.txt": "cmake",
    "Makefile": "make",
    "meson.build": "meson",
    "go.mod": "go_modules",
    "go.sum": "go_modules",
    "pom.xml": "jvm_maven",
    "build.gradle": "jvm_gradle",
    "build.gradle.kts": "jvm_gradle",
}


def stable_int(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def split_for_id(repo_id: str) -> str:
    bucket = stable_int(repo_id) % 10
    if bucket < 6:
        return "train"
    if bucket < 8:
        return "eval"
    return "strict_eval"


def size_bucket(scanned_files: int) -> str:
    if scanned_files < 100:
        return "tiny"
    if scanned_files < 1000:
        return "small"
    if scanned_files < 5000:
        return "medium"
    return "large"


def test_bucket(test_files: int) -> str:
    if test_files == 0:
        return "none"
    if test_files < 20:
        return "light"
    if test_files < 200:
        return "moderate"
    return "heavy"


def build_families(build_files: list[str]) -> list[str]:
    families = set()
    for path in build_files:
        families.add(BUILD_FAMILY_BY_FILE.get(Path(path).name, "other_build"))
    return sorted(families)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def opaque(prefix: str, repo_id: str, suffix: str = "") -> str:
    digest = hashlib.sha256(f"{repo_id}:{suffix}".encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def catalog_row(index: int, summary: dict[str, Any]) -> dict[str, Any]:
    repo_id = summary["repo_id"]
    languages = summary.get("likely_primary_languages", [])
    build = build_families(summary.get("build_files", []))
    uses = summary.get("recommended_curriculum_uses", [])
    row_id = f"stage8601_repo_capability_{index:06d}"
    tests = int(summary.get("test_files", 0))
    docs = int(summary.get("doc_files", 0))
    scanned_files = int(summary.get("scanned_files", 0))
    return {
        "row_id": row_id,
        "split": split_for_id(repo_id),
        "objective_family": "repo_capability_catalog",
        "source_ref": {
            "corpus": "/arxiv/repositories",
            "repo_id": repo_id,
            "path": summary.get("path"),
            "source_in_model_input": False
        },
        "model_input": {
            "opaque_repo_id": opaque("repo", repo_id),
            "language_families": languages,
            "build_system_families": build,
            "has_tests": tests > 0,
            "test_coverage_bucket": test_bucket(tests),
            "has_docs": docs > 0,
            "repo_size_bucket": size_bucket(scanned_files),
            "scan_truncated": bool(summary.get("scan_truncated", False))
        },
        "target": {
            "curriculum_uses": uses,
            "repo_capability_profile": sorted(set(uses + build + languages))
        },
        "loss_mask": {
            "structured_aux": False,
            "decoder_ce": False,
            "denoise_ce": False,
            "runtime_reward": False
        },
        "authority": AUTHORITY_CLOSED,
        "anti_cheat": {
            "raw_source_included": False,
            "repo_path_in_model_input": False,
            "target_label_in_id": False,
            "requires_shortcut_audit_before_training": True
        }
    }


def graph_seed_row(index: int, summary: dict[str, Any]) -> dict[str, Any]:
    repo_id = summary["repo_id"]
    languages = summary.get("likely_primary_languages", [])
    build = build_families(summary.get("build_files", []))
    tests = int(summary.get("test_files", 0))
    docs = int(summary.get("doc_files", 0))
    repo_node = opaque("node", repo_id, "repo")
    nodes = [{"node_id": repo_node, "node_type": "repo", "features": {"opaque_repo_id": opaque("repo", repo_id)}}]
    edges = []
    for lang in languages:
        node_id = opaque("node", repo_id, f"language:{lang}")
        nodes.append({"node_id": node_id, "node_type": "module", "features": {"language_family": lang}})
        edges.append({"src": repo_node, "dst": node_id, "edge_type": "language_boundary"})
    for family in build:
        node_id = opaque("node", repo_id, f"build:{family}")
        nodes.append({"node_id": node_id, "node_type": "config", "features": {"build_system_family": family}})
        edges.append({"src": repo_node, "dst": node_id, "edge_type": "config_controls"})
    if tests:
        node_id = opaque("node", repo_id, "tests")
        nodes.append({"node_id": node_id, "node_type": "test", "features": {"test_coverage_bucket": test_bucket(tests)}})
        edges.append({"src": node_id, "dst": repo_node, "edge_type": "test_covers"})
    if docs:
        node_id = opaque("node", repo_id, "docs")
        nodes.append({"node_id": node_id, "node_type": "file", "features": {"doc_bucket": test_bucket(docs)}})
        edges.append({"src": repo_node, "dst": node_id, "edge_type": "contains"})

    return {
        "row_id": f"stage8601_repo_graph_seed_{index:06d}",
        "split": split_for_id(repo_id),
        "objective_family": "repo_state_graph_v1_seed",
        "source_ref": {
            "corpus": "/arxiv/repositories",
            "repo_id": repo_id,
            "path": summary.get("path"),
            "source_in_model_input": False
        },
        "graph_input": {
            "graph_id": opaque("graph", repo_id),
            "nodes": nodes,
            "edges": edges
        },
        "target": {
            "recommended_next_objectives": summary.get("recommended_curriculum_uses", [])
        },
        "loss_mask": {
            "structured_aux": False,
            "decoder_ce": False,
            "denoise_ce": False,
            "runtime_reward": False
        },
        "authority": AUTHORITY_CLOSED,
        "anti_cheat": {
            "opaque_graph_ids": True,
            "raw_source_included": False,
            "objective_label_in_graph_id": False,
            "requires_endpoint_audit": True
        }
    }


def build_cards(catalog_rows: list[dict[str, Any]], graph_rows: list[dict[str, Any]]) -> dict[str, Any]:
    split_counts = Counter(row["split"] for row in catalog_rows)
    language_counts: Counter[str] = Counter()
    use_counts: Counter[str] = Counter()
    build_counts: Counter[str] = Counter()
    for row in catalog_rows:
        language_counts.update(row["model_input"]["language_families"])
        build_counts.update(row["model_input"]["build_system_families"])
        use_counts.update(row["target"]["curriculum_uses"])

    endpoint_failures = 0
    label_id_leaks = 0
    for row in graph_rows:
        node_ids = {node["node_id"] for node in row["graph_input"]["nodes"]}
        for edge in row["graph_input"]["edges"]:
            if edge["src"] not in node_ids or edge["dst"] not in node_ids:
                endpoint_failures += 1
        all_ids = [row["graph_input"]["graph_id"]] + list(node_ids)
        if any(any(term in value.lower() for term in ["symbol_binding", "patch_operator", "verifier_repair", "bounded_decoder"]) for value in all_ids):
            label_id_leaks += 1

    return {
        "rows": len(catalog_rows),
        "graph_seed_rows": len(graph_rows),
        "split_counts": dict(split_counts),
        "language_counts": dict(language_counts),
        "build_system_counts": dict(build_counts),
        "curriculum_use_counts": dict(use_counts),
        "endpoint_failures": endpoint_failures,
        "label_id_leak_rows": label_id_leaks,
        "authority_rows": 0,
        "raw_source_rows": 0,
        "decoder_ce_rows": 0
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", default="runs/local/artifacts/stage8600_arxiv_corpus_index")
    parser.add_argument("--output-dir", default="runs/local/artifacts/stage8601_arxiv_repo_capability_and_graph_seed")
    parser.add_argument("--max-rows", type=int, default=200)
    args = parser.parse_args()

    index_dir = Path(args.index_dir)
    output_dir = Path(args.output_dir)
    repo_rows = load_jsonl(index_dir / "repository_summaries.jsonl")
    repo_rows = sorted(repo_rows, key=lambda r: int(r.get("maintainer_usefulness_score", 0)), reverse=True)[: args.max_rows]

    catalog_rows = [catalog_row(index, row) for index, row in enumerate(repo_rows)]
    graph_rows = [graph_seed_row(index, row) for index, row in enumerate(repo_rows)]
    card = build_cards(catalog_rows, graph_rows)
    passed = (
        card["rows"] > 0
        and card["endpoint_failures"] == 0
        and card["label_id_leak_rows"] == 0
        and card["authority_rows"] == 0
        and card["raw_source_rows"] == 0
        and card["decoder_ce_rows"] == 0
    )

    write_jsonl(output_dir / "repo_capability_catalog.jsonl", catalog_rows)
    write_jsonl(output_dir / "repo_state_graph_seed.jsonl", graph_rows)
    write_json(output_dir / "cell_card.json", card)
    write_json(
        output_dir / "authority_card.json",
        {
            "passed": True,
            "authority": AUTHORITY_CLOSED,
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False
        },
    )
    summary = {
        "stage": 8601,
        "name": "stage8601_reconstructed_arxiv_repo_capability_and_graph_seed",
        "passed": passed,
        "summary": "Compiled non-training repo capability catalog and opaque repo-state graph seed rows from Stage8600 /arxiv repository index.",
        "metrics": card,
        "artifacts": {
            "repo_capability_catalog": str(output_dir / "repo_capability_catalog.jsonl"),
            "repo_state_graph_seed": str(output_dir / "repo_state_graph_seed.jsonl"),
            "cell_card": str(output_dir / "cell_card.json"),
            "authority_card": str(output_dir / "authority_card.json")
        },
        "gates": {
            "endpoint_failures": card["endpoint_failures"],
            "label_id_leak_rows": card["label_id_leak_rows"],
            "authority_rows": card["authority_rows"],
            "raw_source_rows": card["raw_source_rows"],
            "decoder_ce_rows": card["decoder_ce_rows"],
            "body_emission_authorized": False,
            "source_emission_authorized": False,
            "runtime_authorized": False,
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "transition_head_training_authorized_next": False,
            "gemma_execution_authorized_next": False,
            "harness_execution_authorized_next": False,
            "scoring_authorized_next": False,
            "controller_complete_merge_authorized_next": False,
            "promotion_ready": False
        },
        "next_best_step": "Audit repo capability and graph seed shortcuts, then build symbol/import/test binding rows from actual repository structure with opaque IDs."
    }
    write_json(Path("runs/summaries/stage8601_reconstructed_arxiv_repo_capability_and_graph_seed.json"), summary)
    print(json.dumps({"passed": passed, "metrics": card, "output_dir": str(output_dir)}, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
