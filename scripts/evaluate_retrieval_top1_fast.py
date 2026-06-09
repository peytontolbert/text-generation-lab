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


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    exact = sum(1 for row in rows if row["top1"])
    answer = sum(1 for row in rows if row["answer_top1"])
    exact_bits = sum(float(row["verified_bits_if_correct"]) for row in rows if row["top1"])
    answer_bits = sum(float(row["verified_bits_if_correct"]) for row in rows if row["answer_top1"])
    available_bits = sum(float(row["verified_bits_if_correct"]) for row in rows)
    return {
        "total": total,
        "exact_correct": exact,
        "answer_correct": answer,
        "exact_accuracy": exact / total if total else None,
        "answer_accuracy": answer / total if total else None,
        "available_bits": available_bits,
        "exact_verified_bits": exact_bits,
        "answer_verified_bits": answer_bits,
        "exact_bit_recovery": exact_bits / available_bits if available_bits else None,
        "answer_bit_recovery": answer_bits / available_bits if available_bits else None,
    }


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
    parser.add_argument("--output-details-jsonl", default="")
    args = parser.parse_args()

    ak_eval = load_eval_module()
    device = torch.device(args.device)
    model, tokenizer, model_manifest = ak_eval._load_model(
        Path(args.bundle_dir).resolve(),
        repo_root=(ROOT / args.repo_root).resolve(),
        device=device,
    )
    dataset_manifest = json.loads((ROOT / args.dataset_manifest).read_text(encoding="utf-8"))
    dataset_path = Path(dataset_manifest[f"{args.dataset_split}_dataset_path"])
    rows = [row for row in iter_jsonl(dataset_path) if row.get("retrieval_query_text") and row.get("retrieval_doc_text")]

    by_operation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_operation[str(row.get("operation", "") or "unknown")].append(row)

    scored: list[dict[str, Any]] = []
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
                values, indices = torch.max(scores, dim=1)
                for index, row in enumerate(batch):
                    predicted = op_rows[int(indices[index].detach().cpu().item())]
                    expected_doc = str(row.get("retrieval_doc_text", "") or "").strip()
                    predicted_doc = str(predicted.get("retrieval_doc_text", "") or "").strip()
                    expected_content = str(row.get("expected_content", "") or "")
                    exact = predicted_doc == expected_doc
                    answer = exact or bool(ak_eval._doc_matches_expected_content(expected_content, predicted_doc))
                    scored.append(
                        {
                            "unit_id": str(row.get("source_id", "") or row.get("example_id", "")),
                            "operation": operation,
                            "unit_family": str(row.get("stage653_unit_family", "") or ""),
                            "generalization_split": str(row.get("stage653_generalization_split", "") or ""),
                            "expected_content": expected_content,
                            "predicted_source_id": str(predicted.get("source_id", "") or ""),
                            "top1": exact,
                            "answer_top1": answer,
                            "score": float(values[index].detach().float().cpu().item()),
                            "verified_bits_if_correct": float(row.get("stage653_verified_bits_if_correct", 0.0) or 0.0),
                        }
                    )

    grouped_operation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grouped_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grouped_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scored:
        grouped_operation[row["operation"]].append(row)
        grouped_family[row["unit_family"]].append(row)
        grouped_split[row["generalization_split"]].append(row)

    total = summarize(scored)
    params = float(model_manifest.get("parameter_count") or 0.0)
    result = {
        "artifact_kind": "fast_retrieval_top1_score",
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "dataset_manifest": str((ROOT / args.dataset_manifest).resolve()),
        "dataset_split": args.dataset_split,
        "operation_gated": True,
        "full_corpus_by_operation": True,
        "key_factor_mode": str(args.key_factor_mode),
        "key_factor_weight": float(args.key_factor_weight),
        "parameter_count": params,
        "total": total,
        "exact_kbpp": total["exact_verified_bits"] / params if params else None,
        "answer_kbpp": total["answer_verified_bits"] / params if params else None,
        "by_operation": {key: summarize(value) for key, value in sorted(grouped_operation.items())},
        "by_unit_family": {key: summarize(value) for key, value in sorted(grouped_family.items())},
        "by_generalization_split": {key: summarize(value) for key, value in sorted(grouped_split.items())},
    }
    output = ROOT / args.output_json
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.output_details_jsonl:
        details = ROOT / args.output_details_jsonl
        details.parent.mkdir(parents=True, exist_ok=True)
        with details.open("w", encoding="utf-8") as handle:
            for row in scored:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
