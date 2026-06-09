#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterator


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _iter_rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _load_tokenizer(manifest: dict[str, Any]):
    sampler_path = _repo_root() / "scripts" / "sample_agentkernel_lite_encdec.py"
    spec = importlib.util.spec_from_file_location("sample_agentkernel_lite_encdec", sampler_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load sampler script: {sampler_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    tokenizer_kind = str(manifest.get("tokenizer_kind", "byte") or "byte").lower()
    tokenizer_dir = Path(str(manifest.get("tokenizer_dir", "") or ""))
    if tokenizer_kind == "byte":
        return module.ByteTokenizer()
    if tokenizer_kind == "agentkernel-bpe":
        return module.TokenizersBpe(tokenizer_dir / "tokenizer.json")
    return module.HuggingFaceTokenizer(tokenizer_dir, str(manifest.get("tokenizer_name", "")))


def _token_count(tokenizer: Any, text: str, *, max_tokens: int) -> int:
    return len(tokenizer.encode(str(text), max_length=int(max_tokens))[: int(max_tokens)])


def _parse_run(value: str) -> tuple[str, Path, Path]:
    parts = value.split(":", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("--run must be LABEL:BUNDLE_DIR:EVAL_JSON")
    return parts[0], Path(parts[1]), Path(parts[2])


def _dataset_token_stats(
    *,
    tokenizer: Any,
    train_path: Path,
    eval_path: Path,
    max_query_tokens: int,
    max_doc_tokens: int,
) -> dict[str, Any]:
    train_rows = 0
    train_tokens = 0
    for row in _iter_rows(train_path):
        query = str(row.get("retrieval_query_text", "") or "")
        doc = str(row.get("retrieval_doc_text", "") or "")
        if query and doc:
            train_rows += 1
            train_tokens += _token_count(tokenizer, query, max_tokens=max_query_tokens)
            train_tokens += _token_count(tokenizer, doc, max_tokens=max_doc_tokens)

    eval_docs: set[str] = set()
    eval_rows = 0
    for row in _iter_rows(eval_path):
        query = str(row.get("retrieval_query_text", "") or "")
        doc = str(row.get("retrieval_doc_text", "") or "")
        if query and doc:
            eval_rows += 1
            eval_docs.add(doc.strip())

    return {
        "train_rows": train_rows,
        "train_retrieval_tokens": train_tokens,
        "avg_train_retrieval_tokens_per_pair": train_tokens / train_rows if train_rows else 0.0,
        "eval_rows": eval_rows,
        "unique_eval_answer_cards": len(eval_docs),
        "bits_per_eval_card_choice": math.log2(max(2, len(eval_docs))),
    }


def summarize(args: argparse.Namespace) -> dict[str, Any]:
    dataset_manifest = json.loads(Path(args.dataset_manifest).read_text(encoding="utf-8"))
    train_path = Path(str(dataset_manifest["train_dataset_path"]))
    eval_path = Path(str(dataset_manifest["eval_dataset_path"]))

    results: list[dict[str, Any]] = []
    for label, bundle_dir, eval_json in args.run:
        manifest = json.loads((bundle_dir / "agentkernel_lite_encdec_manifest.json").read_text(encoding="utf-8"))
        training = dict(manifest.get("training_summary", {}))
        eval_result = json.loads(eval_json.read_text(encoding="utf-8"))
        tokenizer = _load_tokenizer(manifest)
        max_query_tokens = int(training.get("max_retrieval_query_tokens") or args.default_max_query_tokens)
        max_doc_tokens = int(training.get("max_retrieval_doc_tokens") or args.default_max_doc_tokens)
        token_stats = _dataset_token_stats(
            tokenizer=tokenizer,
            train_path=train_path,
            eval_path=eval_path,
            max_query_tokens=max_query_tokens,
            max_doc_tokens=max_doc_tokens,
        )

        params = int(manifest.get("parameter_count") or training.get("parameter_count") or 0)
        top1 = float(eval_result.get("top1_accuracy") or 0.0)
        mrr = float(eval_result.get("mean_reciprocal_rank") or 0.0)
        evaluated = int(eval_result.get("evaluated_pairs") or token_stats["eval_rows"] or 0)
        correct = top1 * evaluated
        verified_bits = correct * float(token_stats["bits_per_eval_card_choice"])
        completed_steps = int(training.get("completed_steps") or training.get("max_steps") or 0)
        train_tokens_est = (
            completed_steps
            * int(args.train_batch_size)
            * float(token_stats["avg_train_retrieval_tokens_per_pair"])
        )
        results.append(
            {
                "label": label,
                "bundle_dir": str(bundle_dir),
                "params": params,
                "completed_steps": completed_steps,
                "top1": top1,
                "mrr": mrr,
                "evaluated_pairs": evaluated,
                "correct_estimate": correct,
                "verified_bits": verified_bits,
                "verified_bits_per_param": verified_bits / params if params else 0.0,
                "verified_bits_per_million_params": verified_bits / (params / 1_000_000) if params else 0.0,
                "estimated_training_retrieval_tokens": train_tokens_est,
                "verified_bits_per_training_token": verified_bits / train_tokens_est if train_tokens_est else 0.0,
                "token_stats": token_stats,
            }
        )

    return {
        "dataset_manifest": str(Path(args.dataset_manifest).resolve()),
        "train_batch_size_assumption": int(args.train_batch_size),
        "metric_definition": (
            "verified_bits = top1_correct_answer_card_retrievals * log2(unique_eval_answer_cards); "
            "training tokens are estimated from completed_steps * batch_size * average train retrieval query+doc token count"
        ),
        "runs": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--run", action="append", type=_parse_run, required=True)
    parser.add_argument("--train-batch-size", type=int, default=64)
    parser.add_argument("--default-max-query-tokens", type=int, default=96)
    parser.add_argument("--default-max-doc-tokens", type=int, default=96)
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()
    result = summarize(args)
    if str(args.output_json).strip():
        Path(args.output_json).write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
