#!/usr/bin/env python3
"""Score Stage960 candidate rows with model-owned retrieval embeddings."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F


def load_retrieval_eval(repo_root: Path):
    path = repo_root / "legacy_src/scripts/evaluate_agentkernel_lite_retrieval_embeddings.py"
    spec = importlib.util.spec_from_file_location("evaluate_agentkernel_lite_retrieval_embeddings", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load retrieval evaluator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def rows_by_split(path: Path) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"train": [], "calibration": [], "eval": []}
    for row in iter_jsonl(path):
        split = str(row.get("split", ""))
        out.setdefault(split, []).append(row)
    return out


def split_keys(keys: torch.Tensor) -> tuple[torch.Tensor | None, torch.Tensor | None]:
    if keys.ndim >= 3:
        return keys[:, 0, :], keys[:, 1, :]
    return keys, None


def embed_query(model, ids, mask, keys, aux):
    if hasattr(model, "retrieval_query_embedding"):
        try:
            return model.retrieval_query_embedding(ids, mask, keys, aux)
        except TypeError:
            try:
                return model.retrieval_query_embedding(ids, mask, keys)
            except TypeError:
                return model.retrieval_query_embedding(ids, mask)
    hidden = model.encode(ids, mask)
    return F.normalize((hidden * mask.unsqueeze(-1)).sum(dim=1) / mask.sum(dim=1, keepdim=True).clamp_min(1), dim=-1)


def embed_doc(model, ids, mask, keys, aux):
    if hasattr(model, "retrieval_doc_embedding"):
        try:
            return model.retrieval_doc_embedding(ids, mask, keys, aux)
        except TypeError:
            try:
                return model.retrieval_doc_embedding(ids, mask, keys)
            except TypeError:
                return model.retrieval_doc_embedding(ids, mask)
    hidden = model.encode(ids, mask)
    return F.normalize((hidden * mask.unsqueeze(-1)).sum(dim=1) / mask.sum(dim=1, keepdim=True).clamp_min(1), dim=-1)


def encode_embeddings(
    *,
    retrieval_eval,
    tokenizer,
    model,
    texts: list[str],
    side: str,
    max_tokens: int,
    batch_size: int,
    device: torch.device,
) -> torch.Tensor:
    chunks: list[torch.Tensor] = []
    with torch.no_grad():
        for start in range(0, len(texts), int(batch_size)):
            batch = texts[start : start + int(batch_size)]
            ids, mask = retrieval_eval._encode_batch(tokenizer, batch, max_tokens=int(max_tokens), device=device)
            keys, aux = split_keys(retrieval_eval._encode_key_batch(batch, device=device))
            if side == "query":
                emb = embed_query(model, ids, mask, keys, aux)
            elif side == "doc":
                emb = embed_doc(model, ids, mask, keys, aux)
            else:
                raise ValueError(f"unknown side: {side}")
            chunks.append(F.normalize(emb.detach().float().cpu(), dim=-1))
    if not chunks:
        return torch.empty((0, 0), dtype=torch.float32)
    return torch.cat(chunks, dim=0)


def candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def label_index(candidates: list[dict[str, Any]]) -> int:
    for index, candidate in enumerate(candidates):
        if candidate.get("is_exact"):
            return index
    for index, candidate in enumerate(candidates):
        if candidate.get("is_answer_match"):
            return index
    return -1


def unique_docs(rows: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    docs: list[str] = []
    for row in rows:
        for candidate in row.get("candidates", []) or []:
            doc = str(candidate.get("doc_text", "") or "")
            if doc and doc not in seen:
                seen.add(doc)
                docs.append(doc)
    return docs


def score_rows(
    rows: list[dict[str, Any]],
    *,
    query_embeddings: torch.Tensor,
    doc_embeddings: torch.Tensor,
    doc_to_index: dict[str, int],
    alpha: float | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    answer = exact = recoverable_answer = recoverable_exact = 0
    base_answer = base_exact = 0
    mrr = 0.0
    predictions: list[dict[str, Any]] = []
    by_operation: dict[str, dict[str, int]] = {}
    for row_index, row in enumerate(rows):
        candidates = list(row.get("candidates", []) or [])
        if not candidates:
            continue
        op = str(row.get("operation", "unknown"))
        stats = by_operation.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0})
        stats["rows"] += 1
        doc_indices = [doc_to_index[str(candidate.get("doc_text", "") or "")] for candidate in candidates]
        model_scores = torch.mv(doc_embeddings.index_select(0, torch.tensor(doc_indices, dtype=torch.long)), query_embeddings[row_index])
        base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates], dtype=torch.float32)
        scores = model_scores if alpha is None else base_scores + float(alpha) * model_scores
        order = sorted(range(len(candidates)), key=lambda idx: (-float(scores[idx].item()), idx))
        base_order = sorted(range(len(candidates)), key=lambda idx: (-float(base_scores[idx].item()), idx))
        top = candidates[order[0]]
        base_top = candidates[base_order[0]]
        ans, ex = candidate_hit(top)
        bans, bex = candidate_hit(base_top)
        answer += ans
        exact += ex
        base_answer += bans
        base_exact += bex
        stats["answer"] += ans
        stats["exact"] += ex
        stats["base_answer"] += bans
        stats["base_exact"] += bex
        recoverable_answer += int(any(candidate_hit(candidate)[0] for candidate in candidates))
        recoverable_exact += int(any(candidate_hit(candidate)[1] for candidate in candidates))
        label = label_index(candidates)
        rank = order.index(label) + 1 if label >= 0 else None
        if rank is not None:
            mrr += 1.0 / float(rank)
        predictions.append(
            {
                "row_index": row_index,
                "operation": op,
                "predicted_candidate_index": int(order[0]),
                "base_candidate_index": int(base_order[0]),
                "answer_hit": ans,
                "exact_hit": ex,
                "base_answer_hit": bans,
                "base_exact_hit": bex,
                "label_rank": rank,
            }
        )
    rows_count = len(rows)
    return (
        {
            "rows": rows_count,
            "answer": answer,
            "exact": exact,
            "base_answer": base_answer,
            "base_exact": base_exact,
            "recoverable_answer": recoverable_answer,
            "recoverable_exact": recoverable_exact,
            "mrr": mrr / float(rows_count or 1),
            "alpha": None if alpha is None else float(alpha),
            "by_operation": by_operation,
        },
        predictions,
    )


def operation_gated_scores(selected_scores: dict[str, Any]) -> dict[str, Any]:
    calibration_ops = selected_scores["calibration"]["by_operation"]
    gated_ops: dict[str, str] = {}
    for operation, stats in calibration_ops.items():
        blend_key = (int(stats.get("answer", 0)), int(stats.get("exact", 0)))
        base_key = (int(stats.get("base_answer", 0)), int(stats.get("base_exact", 0)))
        gated_ops[operation] = "blend" if blend_key > base_key else "base"

    out: dict[str, Any] = {"policy": "calibration_improvement", "operations": gated_ops, "splits": {}}
    for split, split_scores in selected_scores.items():
        answer = exact = base_answer = base_exact = rows = 0
        by_operation: dict[str, dict[str, int | str]] = {}
        for operation, stats in split_scores["by_operation"].items():
            policy = gated_ops.get(operation, "base")
            op_answer = int(stats["answer"] if policy == "blend" else stats["base_answer"])
            op_exact = int(stats["exact"] if policy == "blend" else stats["base_exact"])
            op_base_answer = int(stats.get("base_answer", 0))
            op_base_exact = int(stats.get("base_exact", 0))
            op_rows = int(stats.get("rows", 0))
            answer += op_answer
            exact += op_exact
            base_answer += op_base_answer
            base_exact += op_base_exact
            rows += op_rows
            by_operation[operation] = {
                "policy": policy,
                "rows": op_rows,
                "answer": op_answer,
                "exact": op_exact,
                "base_answer": op_base_answer,
                "base_exact": op_base_exact,
                "blend_answer": int(stats.get("answer", 0)),
                "blend_exact": int(stats.get("exact", 0)),
            }
        out["splits"][split] = {
            "rows": rows,
            "answer": answer,
            "exact": exact,
            "base_answer": base_answer,
            "base_exact": base_exact,
            "by_operation": by_operation,
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage960_relation_qslot_bridge_targets.jsonl"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage974_model_owned_candidate_ranking_summary.json"))
    parser.add_argument("--predictions-jsonl", type=Path, default=Path("runs/local/artifacts/stage974_model_owned_candidate_ranking_predictions.jsonl"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--query-batch-size", type=int, default=64)
    parser.add_argument("--doc-batch-size", type=int, default=64)
    parser.add_argument("--max-query-tokens", type=int, default=96)
    parser.add_argument("--max-doc-tokens", type=int, default=256)
    parser.add_argument("--alphas", default="0,0.01,0.025,0.05,0.1,0.25,0.5,1.0")
    parser.add_argument("--operation-gate", choices=("none", "calibration-improvement"), default="none")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    device = torch.device(str(args.device))
    retrieval_eval = load_retrieval_eval(repo_root)
    model, tokenizer, manifest = retrieval_eval._load_model(args.bundle_dir.resolve(), repo_root=repo_root, device=device)
    rows = rows_by_split(args.targets_jsonl)
    all_docs = unique_docs([row for split_rows in rows.values() for row in split_rows])
    doc_to_index = {doc: idx for idx, doc in enumerate(all_docs)}

    model.eval()
    doc_embeddings = encode_embeddings(
        retrieval_eval=retrieval_eval,
        tokenizer=tokenizer,
        model=model,
        texts=all_docs,
        side="doc",
        max_tokens=int(args.max_doc_tokens),
        batch_size=int(args.doc_batch_size),
        device=device,
    )
    query_embeddings = {
        split: encode_embeddings(
            retrieval_eval=retrieval_eval,
            tokenizer=tokenizer,
            model=model,
            texts=[str(row.get("query_text", "") or "") for row in split_rows],
            side="query",
            max_tokens=int(args.max_query_tokens),
            batch_size=int(args.query_batch_size),
            device=device,
        )
        for split, split_rows in rows.items()
    }

    raw_scores = {}
    raw_predictions = {}
    for split, split_rows in rows.items():
        raw_scores[split], raw_predictions[split] = score_rows(
            split_rows,
            query_embeddings=query_embeddings[split],
            doc_embeddings=doc_embeddings,
            doc_to_index=doc_to_index,
            alpha=None,
        )

    alpha_values = [float(value.strip()) for value in str(args.alphas).split(",") if value.strip()]
    blend_by_alpha = {}
    for alpha in alpha_values:
        blend_by_alpha[str(alpha)] = {}
        for split, split_rows in rows.items():
            score, _ = score_rows(
                split_rows,
                query_embeddings=query_embeddings[split],
                doc_embeddings=doc_embeddings,
                doc_to_index=doc_to_index,
                alpha=alpha,
            )
            blend_by_alpha[str(alpha)][split] = score
    selected_alpha = max(
        alpha_values,
        key=lambda a: (
            blend_by_alpha[str(a)]["calibration"]["answer"],
            blend_by_alpha[str(a)]["calibration"]["exact"],
            blend_by_alpha[str(a)]["calibration"]["mrr"],
            -a,
        ),
    )
    selected_scores = {}
    selected_predictions = {}
    for split, split_rows in rows.items():
        selected_scores[split], selected_predictions[split] = score_rows(
            split_rows,
            query_embeddings=query_embeddings[split],
            doc_embeddings=doc_embeddings,
            doc_to_index=doc_to_index,
            alpha=selected_alpha,
        )

    summary = {
        "artifact_kind": "stage974_model_owned_candidate_ranking",
        "status": "completed_model_owned_candidate_ranking_eval",
        "bundle_dir": str(args.bundle_dir),
        "targets_jsonl": str(args.targets_jsonl),
        "parameter_count": int(manifest.get("parameter_count", 0)),
        "doc_count": len(all_docs),
        "raw_model_scores": raw_scores,
        "blend_by_alpha": blend_by_alpha,
        "selected_alpha": float(selected_alpha),
        "selected_blend_scores": selected_scores,
        "implied_full_answer_exact_selected": [
            230 + int(selected_scores["eval"]["answer"]),
            229 + int(selected_scores["eval"]["exact"]),
        ],
        "decision": "Model-owned candidate ranking uses only the checkpoint retrieval embeddings over query/doc text plus optional calibration-selected base-score residual blending. It does not use Stage968 pair-overlap set intersection.",
    }
    if args.operation_gate == "calibration-improvement":
        gated = operation_gated_scores(selected_scores)
        summary["operation_gated_selected_blend_scores"] = gated
        summary["implied_full_answer_exact_operation_gated"] = [
            230 + int(gated["splits"]["eval"]["answer"]),
            229 + int(gated["splits"]["eval"]["exact"]),
        ]
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with args.predictions_jsonl.open("w", encoding="utf-8") as f:
        for split, preds in selected_predictions.items():
            for pred in preds:
                pred = dict(pred)
                pred["split"] = split
                f.write(json.dumps(pred, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
