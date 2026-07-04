#!/usr/bin/env python3
"""Extract no-authority symbol/import/test binding candidates from /arxiv repos.

The extractor may inspect local source files to identify definitions/imports,
but emitted rows intentionally do not include raw source or raw code bodies.
All graph/node IDs are opaque and row-local.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
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

QUERY_KINDS = ("callsite", "import", "test")
TARGET_ACTIONS = ("BIND_CALL_TO_SYMBOL", "BIND_IMPORT_TO_MODULE", "BIND_TEST_TO_SYMBOL", "RETRIEVE_MORE", "ABSTAIN_UNBOUND")
FORBIDDEN_ID_TERMS = {"bind", "symbol", "import", "test", "call", "target", "answer"}


@dataclass
class PyFileFacts:
    path: Path
    rel_path: str
    module_name: str
    is_test: bool
    definitions: list[str]
    imports: list[str]
    calls: list[str]
    test_functions: list[str]


def stable_hash(*parts: str, n: int = 16) -> str:
    return hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()[:n]


def opaque(prefix: str, *parts: str) -> str:
    return f"{prefix}_{stable_hash(*parts)}"


def split_for(text: str) -> str:
    bucket = int(stable_hash(text, n=8), 16) % 10
    if bucket < 6:
        return "train"
    if bucket < 8:
        return "eval"
    return "strict_eval"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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


def module_name_for(repo_root: Path, path: Path) -> str:
    rel = path.relative_to(repo_root).with_suffix("")
    parts = [part for part in rel.parts if part not in {"src", "lib"}]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def is_test_path(rel_path: str) -> bool:
    lowered = rel_path.lower()
    return (
        "/test" in lowered
        or "tests/" in lowered
        or lowered.startswith("test_")
        or "/test_" in lowered
        or lowered.endswith("_test.py")
    )


def parse_python_file(repo_root: Path, path: Path) -> PyFileFacts | None:
    rel = str(path.relative_to(repo_root))
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(text)
    except Exception:
        return None
    definitions: list[str] = []
    imports: list[str] = []
    calls: list[str] = []
    test_functions: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions.append(node.name)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                test_functions.append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.append(func.id)
            elif isinstance(func, ast.Attribute):
                calls.append(func.attr)
    return PyFileFacts(
        path=path,
        rel_path=rel,
        module_name=module_name_for(repo_root, path),
        is_test=is_test_path(rel),
        definitions=sorted(set(definitions))[:200],
        imports=sorted(set(imports))[:200],
        calls=sorted(set(calls))[:300],
        test_functions=sorted(set(test_functions))[:100],
    )


def scan_python_repo(repo_root: Path, max_py_files: int) -> list[PyFileFacts]:
    facts: list[PyFileFacts] = []
    for root, dirs, files in os.walk(repo_root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".venv", "venv", "node_modules", "target", "dist", "build"}]
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            if len(facts) >= max_py_files:
                return facts
            fact = parse_python_file(repo_root, Path(root) / name)
            if fact:
                facts.append(fact)
    return facts


def sanitize_name_features(name: str) -> dict[str, Any]:
    # The raw symbol/import string is not emitted. These coarse features are
    # intentionally not enough to solve the target ID by memorization.
    return {
        "name_len_bucket": "short" if len(name) < 6 else "medium" if len(name) < 14 else "long",
        "starts_with_test": name.startswith("test_"),
        "contains_underscore": "_" in name,
        "has_dunder_shape": name.startswith("__") and name.endswith("__"),
    }


def build_repo_index(facts: list[PyFileFacts]) -> dict[str, Any]:
    module_to_fact = {fact.module_name: fact for fact in facts}
    def_to_fact: dict[str, list[PyFileFacts]] = defaultdict(list)
    for fact in facts:
        for name in fact.definitions:
            def_to_fact[name].append(fact)
    return {"module_to_fact": module_to_fact, "def_to_fact": def_to_fact}


def graph_for_row(repo_id: str, row_key: str, query_kind: str, facts: list[PyFileFacts], candidates: list[PyFileFacts]) -> dict[str, Any]:
    repo_node = opaque("n", repo_id, row_key, "repo")
    nodes = [{"node_id": repo_node, "node_type": "repo", "features": {"language_family": "python"}}]
    edges = []
    seen = {repo_node}
    for idx, fact in enumerate(candidates[:8]):
        file_node = opaque("n", repo_id, row_key, "file", str(idx))
        seen.add(file_node)
        nodes.append(
            {
                "node_id": file_node,
                "node_type": "file",
                "features": {
                    "is_test": fact.is_test,
                    "definition_count_bucket": min(5, len(fact.definitions)),
                    "import_count_bucket": min(5, len(fact.imports)),
                    "call_count_bucket": min(5, len(fact.calls)),
                    "path_depth_bucket": min(6, len(Path(fact.rel_path).parts)),
                },
            }
        )
        edges.append({"src": repo_node, "dst": file_node, "edge_type": "contains"})
    return {
        "graph_id": opaque("g", repo_id, row_key),
        "query_kind": query_kind,
        "nodes": nodes,
        "edges": edges,
    }


def make_row(
    row_index: int,
    repo_id: str,
    repo_path: str,
    query_kind: str,
    binding_action: str,
    query_features: dict[str, Any],
    target_node_kind: str | None,
    facts: list[PyFileFacts],
    candidates: list[PyFileFacts],
) -> dict[str, Any]:
    row_key = f"{repo_id}:{row_index}:{query_kind}"
    target_node_id = opaque("n", repo_id, row_key, "target") if target_node_kind else None
    row = {
        "row_id": f"stage8604_row_{row_index:06d}",
        "split": split_for(row_key),
        "objective_family": "symbol_binding",
        "source_ref": {
            "corpus": "/arxiv/repositories",
            "repo_id": repo_id,
            "path": repo_path,
            "source_in_model_input": False
        },
        "query": {
            "query_kind": query_kind,
            "query_node_id": opaque("q", repo_id, row_key),
            "features": query_features
        },
        "graph_input": graph_for_row(repo_id, row_key, query_kind, facts, candidates),
        "target": {
            "binding_action": binding_action,
            "target_node_id": target_node_id,
            "target_node_kind": target_node_kind
        },
        "loss_mask": {
            "symbol_binding_ce": False,
            "decoder_ce": False,
            "denoise_ce": False,
            "runtime_reward": False
        },
        "authority": AUTHORITY_CLOSED,
        "anti_cheat": {
            "raw_source_included": False,
            "raw_symbol_names_in_model_input": False,
            "target_label_in_id": False,
            "requires_shortcut_audit_before_training": True
        }
    }
    return row


def binding_rows_for_repo(repo_summary: dict[str, Any], max_rows_per_repo: int, max_py_files: int) -> list[dict[str, Any]]:
    repo_id = repo_summary["repo_id"]
    repo_path = Path(repo_summary["path"])
    facts = scan_python_repo(repo_path, max_py_files=max_py_files)
    if not facts:
        return []
    index = build_repo_index(facts)
    rows: list[dict[str, Any]] = []
    row_index_base = int(stable_hash(repo_id, n=8), 16) % 10_000_000

    for fact in facts:
        if len(rows) >= max_rows_per_repo:
            break
        local_defs = set(fact.definitions)
        for call_name in fact.calls:
            if len(rows) >= max_rows_per_repo:
                break
            if call_name in local_defs:
                candidates = [fact]
                action = "BIND_CALL_TO_SYMBOL"
                target_kind = "symbol"
            elif call_name in index["def_to_fact"]:
                candidates = index["def_to_fact"][call_name][:8]
                action = "BIND_CALL_TO_SYMBOL"
                target_kind = "symbol"
            else:
                candidates = [fact]
                action = "RETRIEVE_MORE"
                target_kind = None
            rows.append(
                make_row(
                    row_index_base + len(rows),
                    repo_id,
                    str(repo_path),
                    "callsite",
                    action,
                    {"call_shape": sanitize_name_features(call_name), "source_file_is_test": fact.is_test},
                    target_kind,
                    facts,
                    candidates,
                )
            )

        for import_name in fact.imports:
            if len(rows) >= max_rows_per_repo:
                break
            candidates = []
            # Try exact or prefix module match without emitting the raw module.
            for module, module_fact in index["module_to_fact"].items():
                if module == import_name or module.endswith("." + import_name.split(".")[-1]) or import_name.startswith(module):
                    candidates.append(module_fact)
            if candidates:
                action = "BIND_IMPORT_TO_MODULE"
                target_kind = "module"
            else:
                action = "ABSTAIN_UNBOUND"
                target_kind = None
                candidates = [fact]
            rows.append(
                make_row(
                    row_index_base + len(rows),
                    repo_id,
                    str(repo_path),
                    "import",
                    action,
                    {"import_shape": sanitize_name_features(import_name), "source_file_is_test": fact.is_test},
                    target_kind,
                    facts,
                    candidates[:8],
                )
            )

        if fact.is_test:
            for test_name in fact.test_functions:
                if len(rows) >= max_rows_per_repo:
                    break
                normalized = re.sub(r"^test_", "", test_name)
                candidates = index["def_to_fact"].get(normalized, [])
                if candidates:
                    action = "BIND_TEST_TO_SYMBOL"
                    target_kind = "symbol"
                else:
                    action = "RETRIEVE_MORE"
                    target_kind = None
                    candidates = [fact]
                rows.append(
                    make_row(
                        row_index_base + len(rows),
                        repo_id,
                        str(repo_path),
                        "test",
                        action,
                        {"test_shape": sanitize_name_features(test_name), "source_file_is_test": True},
                        target_kind,
                        facts,
                        candidates[:8],
                    )
                )

    return rows[:max_rows_per_repo]


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    action_counts = Counter(row["target"]["binding_action"] for row in rows)
    query_counts = Counter(row["query"]["query_kind"] for row in rows)
    split_counts = Counter(row["split"] for row in rows)
    repo_counts = Counter(row["source_ref"]["repo_id"] for row in rows)
    endpoint_failures = 0
    label_id_leaks = 0
    raw_source_rows = 0
    authority_rows = 0
    decoder_rows = 0
    query_id_target_exact = 0
    query_id_to_action: dict[str, str] = {}
    for row in rows:
        graph = row["graph_input"]
        node_ids = {node["node_id"] for node in graph["nodes"]}
        for edge in graph["edges"]:
            if edge["src"] not in node_ids or edge["dst"] not in node_ids:
                endpoint_failures += 1
        ids = [row["row_id"], row["query"]["query_node_id"], graph["graph_id"]] + list(node_ids)
        if any(any(term in value.lower() for term in FORBIDDEN_ID_TERMS) for value in ids):
            label_id_leaks += 1
        if row["source_ref"].get("source_in_model_input") or row["anti_cheat"].get("raw_source_included"):
            raw_source_rows += 1
        if any(row.get("authority", {}).values()):
            authority_rows += 1
        if row.get("loss_mask", {}).get("decoder_ce"):
            decoder_rows += 1
        qid = row["query"]["query_node_id"]
        action = row["target"]["binding_action"]
        if qid in query_id_to_action and query_id_to_action[qid] == action:
            query_id_target_exact += 1
        query_id_to_action[qid] = action

    majority_action_exact = max(action_counts.values(), default=0) / len(rows) if rows else 0.0
    query_kind_exact = 0.0
    if rows:
        by_kind: dict[str, Counter[str]] = defaultdict(Counter)
        for row in rows:
            by_kind[row["query"]["query_kind"]][row["target"]["binding_action"]] += 1
        correct = sum(max(counter.values()) for counter in by_kind.values())
        query_kind_exact = correct / len(rows)
    return {
        "rows": len(rows),
        "repo_count": len(repo_counts),
        "split_counts": dict(split_counts),
        "query_kind_counts": dict(query_counts),
        "binding_action_counts": dict(action_counts),
        "endpoint_failures": endpoint_failures,
        "label_id_leak_rows": label_id_leaks,
        "raw_source_rows": raw_source_rows,
        "authority_rows": authority_rows,
        "decoder_ce_rows": decoder_rows,
        "model_ready_training_rows": 0,
        "majority_action_baseline_exact": round(majority_action_exact, 4),
        "query_kind_action_baseline_exact": round(query_kind_exact, 4),
        "query_node_id_repeat_exact": query_id_target_exact,
        "seed_candidate_rows_only": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-summaries", default="runs/local/artifacts/stage8600_arxiv_corpus_index/repository_summaries.jsonl")
    parser.add_argument("--output-dir", default="runs/local/artifacts/stage8604_arxiv_symbol_binding_candidates_id_patch")
    parser.add_argument("--max-repos", type=int, default=40)
    parser.add_argument("--max-rows-per-repo", type=int, default=24)
    parser.add_argument("--max-py-files-per-repo", type=int, default=800)
    args = parser.parse_args()

    summaries = load_jsonl(Path(args.repo_summaries))
    python_repos = [
        row
        for row in sorted(summaries, key=lambda r: int(r.get("maintainer_usefulness_score", 0)), reverse=True)
        if int((row.get("language_file_counts") or {}).get("python", 0)) > 0
    ][: args.max_repos]
    rows: list[dict[str, Any]] = []
    for summary in python_repos:
        rows.extend(binding_rows_for_repo(summary, args.max_rows_per_repo, args.max_py_files_per_repo))

    out = Path(args.output_dir)
    audit = audit_rows(rows)
    passed = (
        audit["rows"] > 0
        and audit["endpoint_failures"] == 0
        and audit["label_id_leak_rows"] == 0
        and audit["raw_source_rows"] == 0
        and audit["authority_rows"] == 0
        and audit["decoder_ce_rows"] == 0
        and audit["query_node_id_repeat_exact"] == 0
    )
    write_jsonl(out / "symbol_binding_candidates.jsonl", rows)
    write_json(out / "audit_card.json", audit)
    summary = {
        "stage": 8604,
        "name": "stage8604_reconstructed_arxiv_symbol_binding_candidates_id_patch",
        "passed": passed,
        "summary": "Patched Stage8603 symbol/import/test candidate extraction to remove label-coded row IDs. Rows use opaque IDs and contain no raw source.",
        "metrics": audit,
        "artifacts": {
            "symbol_binding_candidates": str(out / "symbol_binding_candidates.jsonl"),
            "audit_card": str(out / "audit_card.json")
        },
        "gates": {
            "endpoint_failures": audit["endpoint_failures"],
            "label_id_leak_rows": audit["label_id_leak_rows"],
            "raw_source_rows": audit["raw_source_rows"],
            "authority_rows": audit["authority_rows"],
            "decoder_ce_rows": audit["decoder_ce_rows"],
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
        "next_best_step": "Patch action/query balance and counterfactual sibling obligations for symbol binding, then run shortcut baselines before enabling any structured loss."
    }
    write_json(Path("runs/summaries/stage8604_reconstructed_arxiv_symbol_binding_candidates_id_patch.json"), summary)
    print(json.dumps({"passed": passed, "metrics": audit, "output_dir": str(out)}, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
