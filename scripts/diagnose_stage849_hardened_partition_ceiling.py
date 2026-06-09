#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
from typing import Any

import torch


TARGET_OPS = {
    "atomic_fact",
    "relation",
    "composition",
    "counterfactual_false_claim",
    "exception",
}
ENTITY_RE = re.compile(r"^gdom_\d+_e\d+$")
VALUE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*_v\d+$")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_retrieval_eval(repo_root: Path):
    path = repo_root / "legacy_src" / "scripts" / "evaluate_agentkernel_lite_retrieval_embeddings.py"
    spec = importlib.util.spec_from_file_location("evaluate_agentkernel_lite_retrieval_embeddings", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load retrieval evaluator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _direct_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("task_type") == "active_agent_direct_answer"
        and str(row.get("operation", "") or "") in TARGET_OPS
        and str(row.get("retrieval_query_text", "") or "").strip()
        and str(row.get("retrieval_doc_text", "") or "").strip()
    ]


def _collision_key(row: dict[str, Any]) -> str:
    value = str(row.get("collision_key_value", "") or "").strip()
    if value:
        return value
    name = str(row.get("collision_key_name", "") or "").strip()
    if name and str(row.get(name, "") or "").strip():
        return str(row.get(name, "") or "").strip()
    return str(row.get("operation", "") or "global")


def _unique_docs(rows: list[dict[str, Any]]) -> tuple[list[str], dict[str, int], dict[str, list[int]], dict[str, dict[str, Any]]]:
    docs: list[str] = []
    doc_to_index: dict[str, int] = {}
    groups: dict[str, list[int]] = {}
    doc_to_row: dict[str, dict[str, Any]] = {}
    for row in rows:
        doc = str(row.get("retrieval_doc_text", "") or "").strip()
        if not doc:
            continue
        index = doc_to_index.get(doc)
        if index is None:
            index = len(docs)
            doc_to_index[doc] = index
            docs.append(doc)
            doc_to_row[doc] = row
        key = _collision_key(row)
        groups.setdefault(key, [])
        if index not in groups[key]:
            groups[key].append(index)
    return docs, doc_to_index, groups, doc_to_row


def _binding(row: dict[str, Any]) -> dict[str, Any]:
    binding = row.get("stage819_hardened_binding") or {}
    return binding if isinstance(binding, dict) else {}


def _originals(row: dict[str, Any], side: str, kind: str) -> set[str]:
    aliases = _binding(row).get(f"{side}_aliases") or {}
    if not isinstance(aliases, dict):
        return set()
    originals = set(str(original) for original in aliases)
    if kind == "all":
        return originals
    if kind == "entity":
        return {value for value in originals if ENTITY_RE.match(value)}
    if kind == "value":
        return {value for value in originals if VALUE_RE.match(value)}
    if kind == "slot":
        return {value for value in originals if not ENTITY_RE.match(value) and not VALUE_RE.match(value)}
    raise ValueError(f"unknown kind: {kind}")


def _partition(row: dict[str, Any], candidate_row: dict[str, Any], mode: str) -> bool:
    if mode == "all":
        return True
    if mode == "entity":
        query = _originals(row, "query", "entity")
        doc = _originals(candidate_row, "doc", "entity")
        return bool(query and query & doc)
    if mode == "slot":
        query = _originals(row, "query", "slot")
        doc = _originals(candidate_row, "doc", "slot")
        return bool(query and query & doc)
    if mode == "entity_slot":
        return _partition(row, candidate_row, "entity") and _partition(row, candidate_row, "slot")
    if mode == "any_binding":
        query = _originals(row, "query", "all")
        doc = _originals(candidate_row, "doc", "all")
        return bool(query and query & doc)
    if mode == "composition_proof":
        if str(row.get("operation", "") or "") != "composition":
            return True
        return _partition(row, candidate_row, "entity_slot")
    if mode == "operation_best_teacher":
        operation = str(row.get("operation", "") or "")
        if operation in {"atomic_fact", "counterfactual_false_claim"}:
            return _partition(row, candidate_row, "entity_slot")
        if operation in {"composition", "relation", "exception"}:
            return _partition(row, candidate_row, "entity")
        return True
    raise ValueError(f"unknown partition mode: {mode}")


def _doc_matches_expected(expected: str, doc: str) -> bool:
    return bool(expected and expected in doc)


def _embed_queries(retrieval_eval, model, tokenizer, rows: list[dict[str, Any]], *, max_tokens: int, batch_size: int, device: torch.device) -> torch.Tensor:
    chunks: list[torch.Tensor] = []
    with torch.no_grad():
        for offset in range(0, len(rows), int(batch_size)):
            texts = [
                str(row.get("retrieval_query_text", "") or row.get("encoder_text", "") or "")
                for row in rows[offset : offset + int(batch_size)]
            ]
            chunks.append(retrieval_eval._embed_query(model, tokenizer, texts, max_tokens=int(max_tokens), device=device).detach().float().cpu())
    return torch.cat(chunks, dim=0)


def _embed_docs(retrieval_eval, model, tokenizer, docs: list[str], *, max_tokens: int, batch_size: int, device: torch.device) -> torch.Tensor:
    chunks: list[torch.Tensor] = []
    with torch.no_grad():
        for offset in range(0, len(docs), int(batch_size)):
            chunks.append(retrieval_eval._embed_doc(model, tokenizer, docs[offset : offset + int(batch_size)], max_tokens=int(max_tokens), device=device).detach().float().cpu())
    return torch.cat(chunks, dim=0)


def _evaluate_mode(
    rows: list[dict[str, Any]],
    docs: list[str],
    doc_to_index: dict[str, int],
    groups: dict[str, list[int]],
    doc_to_row: dict[str, dict[str, Any]],
    query_vectors: torch.Tensor,
    doc_vectors: torch.Tensor,
    mode: str,
) -> dict[str, Any]:
    answer = 0
    exact = 0
    reciprocal = 0.0
    sizes: list[int] = []
    coverage = 0
    by_operation: dict[str, dict[str, Any]] = {}
    for row_index, row in enumerate(rows):
        operation = str(row.get("operation", "") or "unknown")
        group = groups[_collision_key(row)]
        label_doc = str(row.get("retrieval_doc_text", "") or "").strip()
        label_index = doc_to_index[label_doc]
        partition = [
            index
            for index in group
            if _partition(row, doc_to_row[docs[index]], mode)
        ]
        if label_index not in partition:
            partition = list(group)
        else:
            coverage += 1
        sizes.append(len(partition))
        scores = (query_vectors[row_index].unsqueeze(0) * doc_vectors[partition]).sum(dim=-1)
        order = torch.argsort(scores, descending=True).tolist()
        pred = int(order[0])
        ranked_doc_indices = [partition[index] for index in order]
        rank = ranked_doc_indices.index(label_index) + 1
        reciprocal += 1.0 / float(rank)
        predicted_doc = docs[partition[pred]]
        expected = str(row.get("expected_content", "") or "")
        stats = by_operation.setdefault(operation, {"examples": 0, "answer_correct": 0, "exact_correct": 0, "mrr": 0.0})
        stats["examples"] += 1
        stats["mrr"] += 1.0 / float(rank)
        if partition[pred] == label_index:
            exact += 1
            stats["exact_correct"] += 1
        if partition[pred] == label_index or _doc_matches_expected(expected, predicted_doc):
            answer += 1
            stats["answer_correct"] += 1
    for stats in by_operation.values():
        stats["mrr"] /= float(stats["examples"] or 1)
    sizes_sorted = sorted(sizes)
    total = len(rows)
    return {
        "examples": total,
        "answer_correct": int(answer),
        "exact_correct": int(exact),
        "mrr": reciprocal / float(total or 1),
        "positive_coverage": int(coverage),
        "mean_partition_size": sum(sizes) / float(len(sizes) or 1),
        "median_partition_size": sizes_sorted[len(sizes_sorted) // 2] if sizes_sorted else 0,
        "max_partition_size": max(sizes) if sizes else 0,
        "by_operation": by_operation,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    manifest = json.loads(Path(args.dataset_manifest).read_text(encoding="utf-8"))
    rows = _direct_rows(_iter_jsonl(Path(manifest["eval_dataset_path"])))
    docs, doc_to_index, groups, doc_to_row = _unique_docs(rows)
    repo_root = Path(args.repo_root).resolve()
    retrieval_eval = _load_retrieval_eval(repo_root)
    model, tokenizer, _manifest = retrieval_eval._load_model(Path(args.bundle_dir).resolve(), repo_root=repo_root, device=torch.device(str(args.device)))
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    device = torch.device(str(args.device))
    query_vectors = _embed_queries(retrieval_eval, model, tokenizer, rows, max_tokens=int(args.max_query_tokens), batch_size=int(args.batch_size), device=device)
    doc_vectors = _embed_docs(retrieval_eval, model, tokenizer, docs, max_tokens=int(args.max_doc_tokens), batch_size=int(args.batch_size), device=device)
    modes = [item.strip() for item in str(args.modes).split(",") if item.strip()]
    results = {
        mode: _evaluate_mode(rows, docs, doc_to_index, groups, doc_to_row, query_vectors, doc_vectors, mode)
        for mode in modes
    }
    best_answer_mode = max(results, key=lambda mode: (results[mode]["answer_correct"], results[mode]["exact_correct"]))
    best_exact_mode = max(results, key=lambda mode: (results[mode]["exact_correct"], results[mode]["answer_correct"]))
    summary = {
        "artifact_kind": "stage849_hardened_partition_ceiling",
        "dataset_manifest": str(Path(args.dataset_manifest).resolve()),
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "eval_examples": len(rows),
        "candidate_docs": len(docs),
        "modes": results,
        "best_answer_mode": best_answer_mode,
        "best_answer": results[best_answer_mode],
        "best_exact_mode": best_exact_mode,
        "best_exact": results[best_exact_mode],
        "decision_hint": "Teacher/ceiling diagnostic only; partitions use hardened metadata and are not accepted model-only KBPP.",
    }
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(_repo_root()))
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--modes", default="all,entity,slot,entity_slot,any_binding,composition_proof,operation_best_teacher")
    parser.add_argument("--max-query-tokens", type=int, default=128)
    parser.add_argument("--max-doc-tokens", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--output-json", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
