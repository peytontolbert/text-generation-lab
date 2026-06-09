#!/usr/bin/env python3
"""Batched direct decoder value-ranking evaluation for Stage1072 targets."""

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


def _candidate_values(rows: list[dict[str, Any]], train_rows: list[dict[str, Any]], source: str) -> list[str]:
    pool = {"eval": rows, "train": train_rows, "train_eval": [*train_rows, *rows]}[source]
    return sorted({str(row.get("expected_content", "") or "").strip() for row in pool if str(row.get("expected_content", "") or "").strip()})


def _target_ids(tokenizer, text: str, max_decoder_tokens: int) -> list[int]:
    ids = [int(token_id) for token_id in tokenizer.encode(str(text), max_length=max_decoder_tokens) if int(token_id) != int(tokenizer.pad_token_id)]
    if ids and ids[0] == int(tokenizer.bos_token_id):
        ids = ids[1:]
    return ids[: int(max_decoder_tokens)]


def _candidate_decoder_text(candidate: str, candidate_format: str) -> str:
    if candidate_format == "content":
        return candidate
    if candidate_format == "structured":
        return f"<AK_STRUCTURED> <AK_ACTION_RESPOND> <AK_TASK_TYPE> active_agent_direct_answer <AK_CONTENT> {candidate} </AK_CONTENT> <AK_END>"
    if candidate_format == "json":
        return json.dumps({"action": "respond", "content": candidate}, sort_keys=True)
    raise ValueError(f"unsupported candidate_format={candidate_format}")


def _score_row_candidates(
    model,
    tokenizer,
    prompt: str,
    candidates: list[str],
    candidate_label_ids: dict[str, list[int]],
    *,
    device: torch.device,
    max_encoder_tokens: int,
    batch_size: int,
) -> list[tuple[str, float, float]]:
    enc_ids = tokenizer.encode(prompt, max_length=max_encoder_tokens)
    scored: list[tuple[str, float, float]] = []
    for start in range(0, len(candidates), int(batch_size)):
        batch_candidates = candidates[start : start + int(batch_size)]
        labels = [candidate_label_ids[candidate] for candidate in batch_candidates]
        max_len = max(len(item) for item in labels)
        dec_rows = []
        target_rows = []
        target_mask = []
        for label_ids in labels:
            dec_ids = [int(tokenizer.bos_token_id), *label_ids[:-1]]
            pad = max_len - len(label_ids)
            dec_rows.append(dec_ids + [int(tokenizer.pad_token_id)] * pad)
            target_rows.append(label_ids + [int(tokenizer.pad_token_id)] * pad)
            target_mask.append([1.0] * len(label_ids) + [0.0] * pad)
        enc = torch.tensor([enc_ids] * len(batch_candidates), dtype=torch.long, device=device)
        enc_mask = torch.ones_like(enc, dtype=torch.long, device=device)
        dec = torch.tensor(dec_rows, dtype=torch.long, device=device)
        target = torch.tensor(target_rows, dtype=torch.long, device=device)
        mask = torch.tensor(target_mask, dtype=torch.float32, device=device)
        logits = model(enc, dec, enc_mask, None).float()
        losses = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), target.reshape(-1), reduction="none").reshape(target.shape)
        sum_loss = (losses * mask).sum(dim=1)
        mean_loss = sum_loss / mask.sum(dim=1).clamp_min(1.0)
        for candidate, mean_value, sum_value in zip(batch_candidates, mean_loss.detach().cpu(), sum_loss.detach().cpu()):
            scored.append((candidate, float(mean_value.item()), float(sum_value.item())))
    return scored


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(args.repo_root).resolve()
    _install_paths(repo_root)
    sampler = _load_sampler(repo_root)

    from runtime.checkpoint import load_config, load_pretrained
    from runtime.seq2seq import EncoderDecoderLM

    dataset_manifest = json.loads(Path(args.dataset_manifest).read_text(encoding="utf-8"))
    rows = list(_iter_jsonl(Path(dataset_manifest["eval_dataset_path"])))
    train_rows = list(_iter_jsonl(Path(dataset_manifest["train_dataset_path"])))
    if int(args.max_examples) > 0:
        rows = rows[: int(args.max_examples)]
    candidates = _candidate_values(rows, train_rows, str(args.candidate_source))
    if int(args.max_candidates) > 0:
        candidates = candidates[: int(args.max_candidates)]
    bundle_manifest = sampler._load_manifest(Path(args.bundle_dir).resolve())
    config = load_config(str(bundle_manifest["model_dir"]))
    tokenizer = sampler._load_tokenizer(bundle_manifest)
    candidate_label_ids = {
        candidate: _target_ids(tokenizer, _candidate_decoder_text(candidate, str(args.candidate_format)), int(args.max_decoder_tokens))
        for candidate in candidates
    }
    candidates = [candidate for candidate in candidates if candidate_label_ids[candidate]]
    if not candidates:
        raise RuntimeError("no candidate values to score")
    model = EncoderDecoderLM(config, tie_embeddings=True, vocab_size=int(config.vocab_size))
    sampler._materialize_lazy_modules(model)
    load_pretrained(model, str(bundle_manifest["model_dir"]), strict=True)
    device = torch.device(str(args.device))
    model.to(device).eval()

    correct_mean = correct_sum = 0
    mrr_mean = mrr_sum = 0.0
    failures: list[dict[str, Any]] = []
    with torch.no_grad():
        for row in rows:
            expected = str(row.get("expected_content", "") or "").strip()
            scored = _score_row_candidates(
                model,
                tokenizer,
                str(row["encoder_text"]),
                candidates,
                candidate_label_ids,
                device=device,
                max_encoder_tokens=int(args.max_encoder_tokens),
                batch_size=int(args.batch_size),
            )
            by_mean = sorted(scored, key=lambda item: (item[1], item[2], item[0]))
            by_sum = sorted(scored, key=lambda item: (item[2], item[1], item[0]))
            pred_mean = by_mean[0][0]
            pred_sum = by_sum[0][0]
            rank_mean = next((index + 1 for index, item in enumerate(by_mean) if item[0] == expected), len(by_mean) + 1)
            rank_sum = next((index + 1 for index, item in enumerate(by_sum) if item[0] == expected), len(by_sum) + 1)
            correct_mean += int(pred_mean == expected)
            correct_sum += int(pred_sum == expected)
            mrr_mean += 1.0 / float(rank_mean)
            mrr_sum += 1.0 / float(rank_sum)
            if pred_mean != expected and len(failures) < int(args.max_failures):
                failures.append(
                    {
                        "row_index": row.get("row_index"),
                        "operation": row.get("operation"),
                        "expected": expected,
                        "pred_mean": pred_mean,
                        "pred_sum": pred_sum,
                        "rank_mean": rank_mean,
                        "rank_sum": rank_sum,
                        "top5_mean": [{"candidate": item[0], "mean_loss": item[1], "sum_loss": item[2]} for item in by_mean[:5]],
                    }
                )
    total = len(rows)
    return {
        "artifact_kind": "stage1073_batched_direct_value_ranking",
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "dataset_manifest": str(Path(args.dataset_manifest).resolve()),
        "candidate_source": str(args.candidate_source),
        "candidates": len(candidates),
        "examples": total,
        "mean_loss_top1_correct": correct_mean,
        "mean_loss_top1_accuracy": correct_mean / float(total or 1),
        "mean_loss_mrr": mrr_mean / float(total or 1),
        "sum_loss_top1_correct": correct_sum,
        "sum_loss_top1_accuracy": correct_sum / float(total or 1),
        "sum_loss_mrr": mrr_sum / float(total or 1),
        "max_encoder_tokens": int(args.max_encoder_tokens),
        "max_decoder_tokens": int(args.max_decoder_tokens),
        "candidate_format": str(args.candidate_format),
        "failures": failures,
        "decision": "Batched direct decoder value-ranking diagnostic over Stage1072 direct-answer targets. This measures decoder likelihood ranking over answer values, not free-form generation.",
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
    parser.add_argument("--max-decoder-tokens", type=int, default=32)
    parser.add_argument("--candidate-format", choices=("content", "structured", "json"), default="content")
    parser.add_argument("--batch-size", type=int, default=128)
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
