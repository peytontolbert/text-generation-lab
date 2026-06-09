#!/usr/bin/env python3
"""Sweep Stage976 exception blend alpha on no-anchor targets."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import torch


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _base_idx(candidates: list[dict[str, Any]]) -> int:
    return max(range(len(candidates)), key=lambda i: (float(candidates[i].get("base_score", 0.0) or 0.0), -int(candidates[i].get("rank", 9999) or 9999), -i))


def _score_exception(rows, query_embeddings, doc_embeddings, doc_to_index, alpha: float) -> dict[str, Any]:
    answer = exact = base_answer = base_exact = recoverable_answer = recoverable_exact = 0
    for row_index, row in enumerate(rows):
        if str(row.get("operation", "")) != "exception":
            continue
        candidates = list(row.get("candidates", []) or [])
        doc_indices = [doc_to_index[str(candidate.get("doc_text", "") or "")] for candidate in candidates]
        model_scores = torch.mv(doc_embeddings.index_select(0, torch.tensor(doc_indices, dtype=torch.long)), query_embeddings[row_index])
        base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates], dtype=torch.float32)
        scores = base_scores + float(alpha) * model_scores
        pred = max(range(len(candidates)), key=lambda i: (float(scores[i].item()), -i))
        base = _base_idx(candidates)
        ans, ex = _hit(candidates[pred])
        bans, bex = _hit(candidates[base])
        answer += ans
        exact += ex
        base_answer += bans
        base_exact += bex
        recoverable_answer += int(any(_hit(candidate)[0] for candidate in candidates))
        recoverable_exact += int(any(_hit(candidate)[1] for candidate in candidates))
    return {
        "rows": sum(1 for row in rows if str(row.get("operation", "")) == "exception"),
        "answer": answer,
        "exact": exact,
        "base_answer": base_answer,
        "base_exact": base_exact,
        "recoverable_answer": recoverable_answer,
        "recoverable_exact": recoverable_exact,
        "alpha": float(alpha),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--bundle-dir", type=Path, default=Path("runs/local/artifacts/pocketpal_controller_100m_stage976_stage975_pair_teacher_loadable_v415"))
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1013_no_anchor_targets.jsonl"))
    parser.add_argument("--alphas", default="0,0.1,0.25,0.5,0.75,1.0,1.5,2.0,3.0,4.0")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--query-batch-size", type=int, default=64)
    parser.add_argument("--doc-batch-size", type=int, default=64)
    parser.add_argument("--max-query-tokens", type=int, default=128)
    parser.add_argument("--max-doc-tokens", type=int, default=128)
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1035_exception_alpha_sweep_summary.json"))
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    stage974 = _load_module(repo_root / "scripts/score_stage974_model_owned_candidate_ranking.py", "stage974")
    retrieval_eval = stage974.load_retrieval_eval(repo_root)
    device = torch.device(str(args.device))
    rows_by_split = stage974.rows_by_split(args.targets_jsonl)
    all_rows = [row for split_rows in rows_by_split.values() for row in split_rows]
    all_docs = stage974.unique_docs(all_rows)
    doc_to_index = {doc: idx for idx, doc in enumerate(all_docs)}
    model, tokenizer, manifest = retrieval_eval._load_model(args.bundle_dir.resolve(), repo_root=repo_root, device=device)
    model.eval()
    doc_embeddings = stage974.encode_embeddings(
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
        split: stage974.encode_embeddings(
            retrieval_eval=retrieval_eval,
            tokenizer=tokenizer,
            model=model,
            texts=[str(row.get("query_text", "") or "") for row in rows],
            side="query",
            max_tokens=int(args.max_query_tokens),
            batch_size=int(args.query_batch_size),
            device=device,
        )
        for split, rows in rows_by_split.items()
    }
    alphas = [float(item) for item in str(args.alphas).split(",") if item.strip()]
    calibration = [_score_exception(rows_by_split["calibration"], query_embeddings["calibration"], doc_embeddings, doc_to_index, alpha) for alpha in alphas]
    selected = max(calibration, key=lambda item: (item["answer"], item["exact"], -item["alpha"]))
    eval_score = _score_exception(rows_by_split["eval"], query_embeddings["eval"], doc_embeddings, doc_to_index, float(selected["alpha"]))
    train_score = _score_exception(rows_by_split["train"], query_embeddings["train"], doc_embeddings, doc_to_index, float(selected["alpha"]))
    summary = {
        "artifact_kind": "stage1035_exception_alpha_sweep",
        "status": "completed_exception_alpha_sweep",
        "bundle_dir": str(args.bundle_dir),
        "targets_jsonl": str(args.targets_jsonl),
        "parameter_count": int(manifest.get("parameter_count", 0)),
        "calibration": calibration,
        "calibration_selected": selected,
        "eval": eval_score,
        "train": train_score,
        "stage1033_exception_answer_exact": [81, 81],
        "decision": "Sweeps exception-only alpha for the saved Stage976 100M model-owned blend on no-anchor targets.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
