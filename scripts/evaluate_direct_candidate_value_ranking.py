#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import torch
import torch.nn.functional as F


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_sampler(repo_root: Path):
    path = repo_root / "legacy_src" / "scripts" / "sample_agentkernel_lite_encdec.py"
    spec = importlib.util.spec_from_file_location("sample_agentkernel_lite_encdec", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load sampler script: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _install_paths(repo_root: Path) -> None:
    for path in (repo_root, repo_root / "other_repos" / "model-stack"):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)


def _candidate_values(rows: list[dict[str, Any]], train_rows: list[dict[str, Any]], *, source: str) -> list[str]:
    if source == "eval":
        pool = rows
    elif source == "train":
        pool = train_rows
    elif source == "train_eval":
        pool = [*train_rows, *rows]
    else:
        raise ValueError(f"unknown candidate source: {source}")
    values = sorted({str(row.get("expected_content", "") or "").strip() for row in pool if str(row.get("expected_content", "") or "").strip()})
    return values


def _target_ids(tokenizer, text: str, *, max_decoder_tokens: int) -> list[int]:
    ids = [
        int(token_id)
        for token_id in tokenizer.encode(str(text), max_length=max_decoder_tokens)
        if int(token_id) != int(tokenizer.pad_token_id)
    ]
    if ids and ids[0] == int(tokenizer.bos_token_id):
        ids = ids[1:]
    return ids[: int(max_decoder_tokens)]


def _score_candidate(
    model,
    tokenizer,
    prompt: str,
    candidate: str,
    *,
    device: torch.device,
    max_encoder_tokens: int,
    max_decoder_tokens: int,
) -> tuple[float, float]:
    enc_ids = tokenizer.encode(prompt, max_length=max_encoder_tokens)
    labels = _target_ids(tokenizer, candidate, max_decoder_tokens=max_decoder_tokens)
    if not labels:
        return float("inf"), float("inf")
    dec_ids = [int(tokenizer.bos_token_id), *labels[:-1]]
    enc = torch.tensor([enc_ids], dtype=torch.long, device=device)
    enc_mask = torch.ones_like(enc, dtype=torch.long, device=device)
    dec = torch.tensor([dec_ids], dtype=torch.long, device=device)
    target = torch.tensor(labels, dtype=torch.long, device=device)
    logits = model(enc, dec, enc_mask, None)[0, : len(labels), :].float()
    token_losses = F.cross_entropy(logits, target, reduction="none")
    return float(token_losses.mean().detach().cpu().item()), float(token_losses.sum().detach().cpu().item())


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(args.repo_root).resolve()
    _install_paths(repo_root)
    sampler = _load_sampler(repo_root)

    from runtime.checkpoint import load_config, load_pretrained
    from runtime.seq2seq import EncoderDecoderLM

    manifest_path = Path(args.dataset_manifest).resolve()
    dataset_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = list(_iter_jsonl(Path(dataset_manifest["eval_dataset_path"])))
    train_rows = list(_iter_jsonl(Path(dataset_manifest["train_dataset_path"])))
    if int(args.max_examples) > 0:
        rows = rows[: int(args.max_examples)]
    candidates = _candidate_values(rows, train_rows, source=str(args.candidate_source))
    if int(args.max_candidates) > 0:
        candidates = candidates[: int(args.max_candidates)]
    if not candidates:
        raise RuntimeError("no candidate values found")

    bundle_dir = Path(args.bundle_dir).resolve()
    bundle_manifest = sampler._load_manifest(bundle_dir)
    config = load_config(str(bundle_manifest["model_dir"]))
    tokenizer = sampler._load_tokenizer(bundle_manifest)
    model = EncoderDecoderLM(config, tie_embeddings=True, vocab_size=int(config.vocab_size))
    sampler._materialize_lazy_modules(model)
    load_pretrained(model, str(bundle_manifest["model_dir"]), strict=True)
    device = torch.device(str(args.device))
    model.to(device).eval()

    correct_mean = 0
    correct_sum = 0
    mrr_mean = 0.0
    mrr_sum = 0.0
    failures: list[dict[str, Any]] = []
    with torch.no_grad():
        for row in rows:
            expected = str(row.get("expected_content", "") or "").strip()
            scored = []
            for candidate in candidates:
                mean_loss, sum_loss = _score_candidate(
                    model,
                    tokenizer,
                    str(row["encoder_text"]),
                    candidate,
                    device=device,
                    max_encoder_tokens=int(args.max_encoder_tokens),
                    max_decoder_tokens=int(args.max_decoder_tokens),
                )
                scored.append((candidate, mean_loss, sum_loss))
            by_mean = sorted(scored, key=lambda item: (item[1], item[2], item[0]))
            by_sum = sorted(scored, key=lambda item: (item[2], item[1], item[0]))
            pred_mean = by_mean[0][0]
            pred_sum = by_sum[0][0]
            rank_mean = next((index + 1 for index, item in enumerate(by_mean) if item[0] == expected), len(by_mean) + 1)
            rank_sum = next((index + 1 for index, item in enumerate(by_sum) if item[0] == expected), len(by_sum) + 1)
            if pred_mean == expected:
                correct_mean += 1
            if pred_sum == expected:
                correct_sum += 1
            mrr_mean += 1.0 / float(rank_mean)
            mrr_sum += 1.0 / float(rank_sum)
            if pred_mean != expected and len(failures) < int(args.max_failures):
                failures.append(
                    {
                        "source_id": row.get("source_id", ""),
                        "expected": expected,
                        "pred_mean": pred_mean,
                        "pred_sum": pred_sum,
                        "rank_mean": rank_mean,
                        "rank_sum": rank_sum,
                        "top5_mean": [
                            {"candidate": item[0], "mean_loss": item[1], "sum_loss": item[2]}
                            for item in by_mean[:5]
                        ],
                    }
                )
    total = len(rows)
    return {
        "artifact_kind": "direct_candidate_value_ranking_eval",
        "bundle_dir": str(bundle_dir),
        "dataset_manifest": str(manifest_path),
        "candidate_source": str(args.candidate_source),
        "candidates": len(candidates),
        "examples": total,
        "mean_loss_top1_correct": correct_mean,
        "mean_loss_top1_accuracy": correct_mean / float(total or 1),
        "mean_loss_mrr": mrr_mean / float(total or 1),
        "sum_loss_top1_correct": correct_sum,
        "sum_loss_top1_accuracy": correct_sum / float(total or 1),
        "sum_loss_mrr": mrr_sum / float(total or 1),
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(_repo_root()))
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--candidate-source", choices=("eval", "train", "train_eval"), default="train_eval")
    parser.add_argument("--max-examples", type=int, default=0)
    parser.add_argument("--max-candidates", type=int, default=0)
    parser.add_argument("--max-encoder-tokens", type=int, default=1024)
    parser.add_argument("--max-decoder-tokens", type=int, default=64)
    parser.add_argument("--max-failures", type=int, default=20)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    summary = evaluate(args)
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
