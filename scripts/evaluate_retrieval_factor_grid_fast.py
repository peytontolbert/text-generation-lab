#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
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


def summarize(stats: dict[str, float], *, params: float) -> dict[str, Any]:
    total = int(stats["total"])
    available_bits = float(stats["available_bits"])
    exact_bits = float(stats["exact_bits"])
    answer_bits = float(stats["answer_bits"])
    return {
        "total": total,
        "exact_correct": int(stats["exact"]),
        "answer_correct": int(stats["answer"]),
        "exact_accuracy": float(stats["exact"]) / total if total else None,
        "answer_accuracy": float(stats["answer"]) / total if total else None,
        "available_bits": available_bits,
        "exact_verified_bits": exact_bits,
        "answer_verified_bits": answer_bits,
        "exact_bit_recovery": exact_bits / available_bits if available_bits else None,
        "answer_bit_recovery": answer_bits / available_bits if available_bits else None,
        "exact_kbpp": exact_bits / params if params else None,
        "answer_kbpp": answer_bits / params if params else None,
    }


def normalized_content_id(value: Any, ids: dict[str, int]) -> int:
    key = str(value or "").strip().lower()
    if not key:
        key = "<empty>"
    existing = ids.get(key)
    if existing is not None:
        return existing
    current = len(ids) + 1
    ids[key] = current
    return current


def cache_fingerprint(
    *,
    dataset_path: Path,
    dataset_split: str,
    operation: str,
    side: str,
    mode: str,
    count: int,
) -> str:
    stat = dataset_path.stat()
    payload = {
        "dataset_path": str(dataset_path.resolve()),
        "dataset_split": str(dataset_split),
        "operation": str(operation),
        "side": str(side),
        "mode": str(mode),
        "count": int(count),
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]


def cached_key_factor_embeddings(
    ak_eval,
    model,
    texts: list[str],
    *,
    mode: str,
    device: torch.device,
    cache_dir: Path | None,
    dataset_path: Path,
    dataset_split: str,
    operation: str,
    side: str,
    cache_events: list[dict[str, Any]],
) -> torch.Tensor | None:
    if cache_dir is None:
        return ak_eval._key_factor_embeddings(model, texts, mode=mode, device=device)
    cache_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = cache_fingerprint(
        dataset_path=dataset_path,
        dataset_split=dataset_split,
        operation=operation,
        side=side,
        mode=mode,
        count=len(texts),
    )
    cache_path = cache_dir / f"{fingerprint}_{operation}_{side}_{mode}.pt"
    if cache_path.exists():
        payload = torch.load(cache_path, map_location="cpu")
        tensor = payload["tensor"] if isinstance(payload, dict) and "tensor" in payload else payload
        cache_events.append(
            {
                "event": "hit",
                "path": str(cache_path),
                "operation": str(operation),
                "side": str(side),
                "mode": str(mode),
                "rows": len(texts),
            }
        )
        return tensor.to(device=device)

    tensor = ak_eval._key_factor_embeddings(model, texts, mode=mode, device=device)
    if tensor is None:
        cache_events.append(
            {
                "event": "unsupported",
                "operation": str(operation),
                "side": str(side),
                "mode": str(mode),
                "rows": len(texts),
            }
        )
        return None
    torch.save(
        {
            "tensor": tensor.detach().cpu(),
            "operation": str(operation),
            "side": str(side),
            "mode": str(mode),
            "rows": len(texts),
        },
        cache_path,
    )
    cache_events.append(
        {
            "event": "miss_write",
            "path": str(cache_path),
            "operation": str(operation),
            "side": str(side),
            "mode": str(mode),
            "rows": len(texts),
        }
    )
    return tensor


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--dataset-split", choices=("train", "eval"), default="eval")
    parser.add_argument("--repo-root", default="legacy_src")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--max-query-tokens", type=int, default=96)
    parser.add_argument("--max-doc-tokens", type=int, default=256)
    parser.add_argument("--key-factor-modes", default="model,gsel_no_full_parts,gsel_all_parts,gsel_full")
    parser.add_argument("--key-factor-weights", default="0,0.05,0.1,0.2,0.4,0.8")
    parser.add_argument("--operations", default="", help="Optional comma-separated operation filter for sharded eval.")
    parser.add_argument("--factor-cache-dir", default="", help="Optional directory for cached full-operation key factor tensors.")
    parser.add_argument(
        "--fast-row-content-answer-match",
        type=int,
        default=0,
        help="Use row expected_content ids for answer equivalence. Faster, but accepted scoring keeps the doc-text matcher.",
    )
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    modes = [item.strip() for item in str(args.key_factor_modes).split(",") if item.strip()]
    weights = [float(item.strip()) for item in str(args.key_factor_weights).split(",") if item.strip()]
    combos = [(mode, weight) for mode in modes for weight in weights]

    ak_eval = load_eval_module()
    device = torch.device(args.device)
    model, tokenizer, model_manifest = ak_eval._load_model(
        Path(args.bundle_dir).resolve(),
        repo_root=(ROOT / args.repo_root).resolve(),
        device=device,
    )
    manifest = json.loads((ROOT / args.dataset_manifest).read_text(encoding="utf-8"))
    dataset_path = Path(manifest[f"{args.dataset_split}_dataset_path"])
    operation_filter = {item.strip() for item in str(args.operations).split(",") if item.strip()}
    rows = [
        row
        for row in iter_jsonl(dataset_path)
        if row.get("retrieval_query_text")
        and row.get("retrieval_doc_text")
        and (not operation_filter or str(row.get("operation", "") or "unknown") in operation_filter)
    ]

    by_operation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_operation[str(row.get("operation", "") or "unknown")].append(row)

    stats = {
        combo: {"total": 0.0, "exact": 0.0, "answer": 0.0, "available_bits": 0.0, "exact_bits": 0.0, "answer_bits": 0.0}
        for combo in combos
    }
    params = float(model_manifest.get("parameter_count") or 0.0)
    cache_dir = (ROOT / str(args.factor_cache_dir)).resolve() if str(args.factor_cache_dir).strip() else None
    cache_events: list[dict[str, Any]] = []
    active_modes = [
        mode
        for mode in modes
        if any(weight != 0.0 for combo_mode, weight in combos if combo_mode == mode)
    ]

    with torch.no_grad():
        for operation, op_rows in sorted(by_operation.items()):
            docs = [str(row["retrieval_doc_text"]) for row in op_rows]
            doc_embeddings = []
            for offset in range(0, len(docs), int(args.batch_size)):
                doc_embeddings.append(
                    ak_eval._embed_doc(
                        model,
                        tokenizer,
                        docs[offset : offset + int(args.batch_size)],
                        max_tokens=int(args.max_doc_tokens),
                        device=device,
                    )
                )
            doc_matrix = torch.cat(doc_embeddings, dim=0)
            doc_factor_by_mode = {
                mode: cached_key_factor_embeddings(
                    ak_eval,
                    model,
                    docs,
                    mode=mode,
                    device=device,
                    cache_dir=cache_dir,
                    dataset_path=dataset_path,
                    dataset_split=str(args.dataset_split),
                    operation=operation,
                    side="doc",
                    cache_events=cache_events,
                )
                for mode in active_modes
            }
            queries_all = [str(row["retrieval_query_text"]) for row in op_rows]
            query_factor_all_by_mode = {
                mode: cached_key_factor_embeddings(
                    ak_eval,
                    model,
                    queries_all,
                    mode=mode,
                    device=device,
                    cache_dir=cache_dir,
                    dataset_path=dataset_path,
                    dataset_split=str(args.dataset_split),
                    operation=operation,
                    side="query",
                    cache_events=cache_events,
                )
                for mode in doc_factor_by_mode
                if doc_factor_by_mode.get(mode) is not None
            }
            content_vocab: dict[str, int] = {}
            content_ids = torch.tensor(
                [normalized_content_id(row.get("expected_content", ""), content_vocab) for row in op_rows],
                dtype=torch.long,
                device=device,
            )
            verified_bits = torch.tensor(
                [float(row.get("stage653_verified_bits_if_correct", 0.0) or 0.0) for row in op_rows],
                dtype=torch.float32,
                device=device,
            )
            for offset in range(0, len(op_rows), int(args.batch_size)):
                batch = op_rows[offset : offset + int(args.batch_size)]
                queries = [str(row["retrieval_query_text"]) for row in batch]
                query_matrix = ak_eval._embed_query(
                    model,
                    tokenizer,
                    queries,
                    max_tokens=int(args.max_query_tokens),
                    device=device,
                )
                base_scores = query_matrix @ doc_matrix.transpose(0, 1)
                query_factor_by_mode = {
                    mode: factors[offset : offset + len(batch)]
                    for mode, factors in query_factor_all_by_mode.items()
                }
                for mode, weight in combos:
                    scores = base_scores
                    if float(weight) != 0.0:
                        query_factors = query_factor_by_mode.get(mode)
                        doc_factors = doc_factor_by_mode.get(mode)
                        if query_factors is not None and doc_factors is not None:
                            scores = scores + float(weight) * (query_factors @ doc_factors.transpose(0, 1)).to(
                                dtype=scores.dtype
                            )
                    indices = torch.argmax(scores, dim=1)
                    combo_stats = stats[(mode, weight)]
                    if int(args.fast_row_content_answer_match):
                        batch_len = len(batch)
                        positions = torch.arange(offset, offset + batch_len, dtype=torch.long, device=device)
                        batch_bits = verified_bits[offset : offset + batch_len]
                        exact_mask = indices.eq(positions)
                        answer_mask = exact_mask | content_ids[indices].eq(content_ids[offset : offset + batch_len])
                        combo_stats["total"] += float(batch_len)
                        combo_stats["available_bits"] += float(batch_bits.sum().detach().cpu().item())
                        combo_stats["exact"] += float(exact_mask.sum().detach().cpu().item())
                        combo_stats["answer"] += float(answer_mask.sum().detach().cpu().item())
                        combo_stats["exact_bits"] += float(batch_bits.masked_select(exact_mask).sum().detach().cpu().item())
                        combo_stats["answer_bits"] += float(batch_bits.masked_select(answer_mask).sum().detach().cpu().item())
                    else:
                        for index, row in enumerate(batch):
                            predicted = op_rows[int(indices[index].detach().cpu().item())]
                            expected_doc = str(row.get("retrieval_doc_text", "") or "").strip()
                            predicted_doc = str(predicted.get("retrieval_doc_text", "") or "").strip()
                            expected_content = str(row.get("expected_content", "") or "")
                            bits = float(row.get("stage653_verified_bits_if_correct", 0.0) or 0.0)
                            exact = predicted_doc == expected_doc
                            answer = exact or bool(ak_eval._doc_matches_expected_content(expected_content, predicted_doc))
                            combo_stats["total"] += 1.0
                            combo_stats["available_bits"] += bits
                            if exact:
                                combo_stats["exact"] += 1.0
                                combo_stats["exact_bits"] += bits
                            if answer:
                                combo_stats["answer"] += 1.0
                                combo_stats["answer_bits"] += bits

    results = []
    for mode, weight in combos:
        result = summarize(stats[(mode, weight)], params=params)
        result["key_factor_mode"] = mode
        result["key_factor_weight"] = float(weight)
        results.append(result)
    results.sort(key=lambda item: (float(item.get("answer_kbpp") or 0.0), float(item.get("exact_kbpp") or 0.0)), reverse=True)

    output = {
        "artifact_kind": "retrieval_factor_grid_fast",
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "dataset_manifest": str((ROOT / args.dataset_manifest).resolve()),
        "dataset_split": str(args.dataset_split),
        "factor_cache_dir": str(cache_dir) if cache_dir is not None else "",
        "factor_cache_events": cache_events,
        "fast_row_content_answer_match": int(args.fast_row_content_answer_match),
        "operation_filter": sorted(operation_filter),
        "parameter_count": params,
        "results": results,
    }
    path = ROOT / args.output_json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
