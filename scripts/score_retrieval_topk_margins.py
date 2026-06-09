#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch


ROOT = Path(__file__).resolve().parents[1]
EVAL_SCRIPT = ROOT / "legacy_src/scripts/evaluate_agentkernel_lite_retrieval_embeddings.py"


def load_eval_module():
    spec = importlib.util.spec_from_file_location("ak_eval", EVAL_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {EVAL_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--dataset-split", choices=("train", "eval"), default="eval")
    parser.add_argument("--repo-root", default="legacy_src")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--max-query-tokens", type=int, default=96)
    parser.add_argument("--max-doc-tokens", type=int, default=256)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument(
        "--key-factor-mode",
        choices=(
            "model",
            "kv",
            "gsel_parts",
            "gsel_full",
            "gsel_all_parts",
            "gsel_no_full_parts",
            "gsel_entity",
            "gsel_domain_field",
            "gsel_domain_field_entity",
            "text_entity",
            "text_domain_field_entity",
            "text_domain_field_nonanswer_entity",
            "text_domain_field_subject_entity",
            "text_domain_field_nonanswer_entity_pair",
            "text_gsel_axes_nonanswer_entity_pair",
            "text_multi_axis_nonanswer_entity_pair",
            "text_compose_role_entity_exact",
            "text_routed_multi_axis_compose_exact",
            "text_routed_multi_axis_compose_procedure",
            "text_domain_relation_field_nonanswer_entity",
            "text_domain_field_semantic",
        ),
        default="model",
    )
    parser.add_argument("--key-factor-weight", type=float, default=0.0)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-details-jsonl", required=True)
    args = parser.parse_args()

    ak_eval = load_eval_module()
    device = torch.device(args.device)
    model, tokenizer, model_manifest = ak_eval._load_model(
        Path(args.bundle_dir).resolve(),
        repo_root=(ROOT / args.repo_root).resolve(),
        device=device,
    )
    manifest = json.loads((ROOT / args.dataset_manifest).read_text(encoding="utf-8"))
    dataset_path = Path(manifest[f"{args.dataset_split}_dataset_path"])
    rows = [row for row in iter_jsonl(dataset_path) if row.get("retrieval_query_text") and row.get("retrieval_doc_text")]

    by_operation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_operation[str(row.get("operation", "") or "unknown")].append(row)

    details: list[dict[str, Any]] = []
    with torch.no_grad():
        for operation, op_rows in sorted(by_operation.items()):
            docs = [str(row["retrieval_doc_text"]) for row in op_rows]
            doc_embeddings = []
            for offset in range(0, len(docs), args.batch_size):
                doc_embeddings.append(
                    ak_eval._embed_doc(
                        model,
                        tokenizer,
                        docs[offset : offset + args.batch_size],
                        max_tokens=args.max_doc_tokens,
                        device=device,
                    )
                )
            doc_matrix = torch.cat(doc_embeddings, dim=0)
            doc_factor_matrix = ak_eval._key_factor_embeddings(
                model,
                docs,
                mode=str(args.key_factor_mode),
                device=device,
            )
            k = min(max(2, int(args.top_k)), len(op_rows))
            for offset in range(0, len(op_rows), args.batch_size):
                batch = op_rows[offset : offset + args.batch_size]
                queries = [str(row["retrieval_query_text"]) for row in batch]
                query_matrix = ak_eval._embed_query(
                    model,
                    tokenizer,
                    queries,
                    max_tokens=args.max_query_tokens,
                    device=device,
                )
                scores = query_matrix @ doc_matrix.transpose(0, 1)
                if float(args.key_factor_weight) != 0.0 and doc_factor_matrix is not None:
                    query_factor_matrix = ak_eval._key_factor_embeddings(
                        model,
                        queries,
                        mode=str(args.key_factor_mode),
                        device=device,
                    )
                    if query_factor_matrix is not None:
                        scores = scores + float(args.key_factor_weight) * (
                            query_factor_matrix @ doc_factor_matrix.transpose(0, 1)
                        ).to(dtype=scores.dtype)
                values, indices = torch.topk(scores, k=k, dim=1)
                for index, row in enumerate(batch):
                    source_id = str(row.get("source_id", "") or row.get("example_id", ""))
                    expected_doc = str(row.get("retrieval_doc_text", "") or "").strip()
                    expected_content = str(row.get("expected_content", "") or "")
                    top_entries: list[dict[str, Any]] = []
                    correct_score = None
                    best_wrong_score = None
                    best_wrong_source = ""
                    for rank_index in range(k):
                        candidate_index = int(indices[index, rank_index].detach().cpu().item())
                        candidate = op_rows[candidate_index]
                        candidate_doc = str(candidate.get("retrieval_doc_text", "") or "").strip()
                        candidate_source = str(candidate.get("source_id", "") or "")
                        score = float(values[index, rank_index].detach().float().cpu().item())
                        exact = candidate_doc == expected_doc
                        answer = exact or bool(ak_eval._doc_matches_expected_content(expected_content, candidate_doc))
                        if exact and correct_score is None:
                            correct_score = score
                        if not answer and best_wrong_score is None:
                            best_wrong_score = score
                            best_wrong_source = candidate_source
                        top_entries.append(
                            {
                                "rank": rank_index + 1,
                                "source_id": candidate_source,
                                "score": score,
                                "exact": exact,
                                "answer": answer,
                            }
                        )
                    if correct_score is None:
                        # Correct document may sit below top-k. Compute it directly from the row's local index.
                        local_index = op_rows.index(row)
                        correct_score = float(scores[index, local_index].detach().float().cpu().item())
                    predicted = top_entries[0]
                    answer_top1 = bool(predicted["answer"])
                    top1 = bool(predicted["exact"])
                    margin_to_wrong = (
                        float(correct_score - best_wrong_score)
                        if best_wrong_score is not None
                        else None
                    )
                    details.append(
                        {
                            "unit_id": source_id,
                            "operation": operation,
                            "expected_content": expected_content,
                            "predicted_source_id": str(predicted["source_id"]),
                            "top1": top1,
                            "answer_top1": answer_top1,
                            "correct_score": correct_score,
                            "best_wrong_score": best_wrong_score,
                            "best_wrong_source_id": best_wrong_source,
                            "margin_to_best_wrong": margin_to_wrong,
                            "rank": next((entry["rank"] for entry in top_entries if entry["exact"]), None),
                            "topk": top_entries,
                            "verified_bits_if_correct": float(row.get("stage653_verified_bits_if_correct", 0.0) or 0.0),
                        }
                    )

    params = float(model_manifest.get("parameter_count") or 0.0)
    total = len(details)
    answer_correct = sum(1 for row in details if row["answer_top1"])
    exact_correct = sum(1 for row in details if row["top1"])
    answer_bits = sum(float(row["verified_bits_if_correct"]) for row in details if row["answer_top1"])
    exact_bits = sum(float(row["verified_bits_if_correct"]) for row in details if row["top1"])
    margins = [float(row["margin_to_best_wrong"]) for row in details if row["margin_to_best_wrong"] is not None]
    result = {
        "artifact_kind": "retrieval_topk_margin_score",
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "dataset_manifest": str((ROOT / args.dataset_manifest).resolve()),
        "dataset_split": args.dataset_split,
        "top_k": int(args.top_k),
        "parameter_count": params,
        "key_factor_mode": str(args.key_factor_mode),
        "key_factor_weight": float(args.key_factor_weight),
        "total": total,
        "answer_correct": answer_correct,
        "exact_correct": exact_correct,
        "answer_kbpp": answer_bits / params if params else None,
        "exact_kbpp": exact_bits / params if params else None,
        "margin_min": min(margins) if margins else None,
        "margin_max": max(margins) if margins else None,
    }
    output = ROOT / args.output_json
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    details_path = ROOT / args.output_details_jsonl
    details_path.parent.mkdir(parents=True, exist_ok=True)
    with details_path.open("w", encoding="utf-8") as handle:
        for row in details:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
