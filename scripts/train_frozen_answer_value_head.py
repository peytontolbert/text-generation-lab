#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import random
import sys
from typing import Any

import torch
import torch.nn.functional as F


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


def _candidate_values(rows: list[dict[str, Any]], train_rows: list[dict[str, Any]], source: str) -> list[str]:
    if source == "eval":
        pool = rows
    elif source == "train":
        pool = train_rows
    elif source == "train_eval":
        pool = [*train_rows, *rows]
    else:
        raise ValueError(f"unknown candidate source: {source}")
    return sorted(
        {
            str(row.get("expected_content", "") or "").strip()
            for row in pool
            if str(row.get("expected_content", "") or "").strip()
        }
    )


def _row_text(row: dict[str, Any], source: str) -> str:
    value = str(row.get(source, "") or "").strip()
    if value:
        return value
    if source != "encoder_text":
        value = str(row.get("encoder_text", "") or "").strip()
    if not value:
        raise ValueError(f"row lacks usable text for source={source}: {row.get('source_id')}")
    return value


def _embed_rows(
    retrieval_eval,
    model,
    tokenizer,
    rows: list[dict[str, Any]],
    *,
    text_source: str,
    max_tokens: int,
    batch_size: int,
    device: torch.device,
) -> torch.Tensor:
    chunks: list[torch.Tensor] = []
    with torch.no_grad():
        for offset in range(0, len(rows), int(batch_size)):
            texts = [_row_text(row, text_source) for row in rows[offset : offset + int(batch_size)]]
            embed = retrieval_eval._embed(
                model,
                tokenizer,
                texts,
                max_tokens=int(max_tokens),
                device=device,
            )
            chunks.append(embed.detach().float().cpu())
    return torch.cat(chunks, dim=0)


def _evaluate(logits: torch.Tensor, labels: torch.Tensor, candidates: list[str], rows: list[dict[str, Any]], max_failures: int) -> dict[str, Any]:
    pred = logits.argmax(dim=-1)
    correct = pred.eq(labels)
    reciprocal = 0.0
    failures: list[dict[str, Any]] = []
    ranked = torch.argsort(logits, dim=-1, descending=True)
    for index, row in enumerate(rows):
        label = int(labels[index].item())
        rank = int((ranked[index] == label).nonzero(as_tuple=False)[0].item()) + 1
        reciprocal += 1.0 / float(rank)
        if pred[index].item() != label and len(failures) < int(max_failures):
            top5 = [
                {
                    "candidate": candidates[int(candidate_index.item())],
                    "score": float(logits[index, candidate_index].detach().cpu().item()),
                }
                for candidate_index in ranked[index, :5]
            ]
            failures.append(
                {
                    "source_id": row.get("source_id", ""),
                    "expected": candidates[label],
                    "predicted": candidates[int(pred[index].item())],
                    "rank": rank,
                    "top5": top5,
                }
            )
    total = int(labels.numel())
    return {
        "examples": total,
        "top1_correct": int(correct.sum().item()),
        "top1_accuracy": float(correct.float().mean().item()) if total else 0.0,
        "mrr": reciprocal / float(total or 1),
        "failures": failures,
    }


def _make_head(input_dim: int, output_dim: int, hidden_dim: int) -> torch.nn.Module:
    if int(hidden_dim) <= 0:
        head: torch.nn.Module = torch.nn.Linear(int(input_dim), int(output_dim))
        torch.nn.init.zeros_(head.weight)
        torch.nn.init.zeros_(head.bias)
        return head
    head = torch.nn.Sequential(
        torch.nn.Linear(int(input_dim), int(hidden_dim)),
        torch.nn.Tanh(),
        torch.nn.Linear(int(hidden_dim), int(output_dim)),
    )
    for module in head.modules():
        if isinstance(module, torch.nn.Linear):
            torch.nn.init.xavier_uniform_(module.weight)
            torch.nn.init.zeros_(module.bias)
    return head


def train(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(args.repo_root).resolve()
    retrieval_eval = _load_retrieval_eval(repo_root)
    device = torch.device(str(args.device))
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))

    manifest_path = Path(args.dataset_manifest).resolve()
    dataset_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    train_rows = _iter_jsonl(Path(dataset_manifest["train_dataset_path"]))
    eval_rows = _iter_jsonl(Path(dataset_manifest["eval_dataset_path"]))
    if int(args.max_train_examples) > 0:
        train_rows = train_rows[: int(args.max_train_examples)]
    if int(args.max_eval_examples) > 0:
        eval_rows = eval_rows[: int(args.max_eval_examples)]
    candidates = _candidate_values(eval_rows, train_rows, str(args.candidate_source))
    if int(args.max_candidates) > 0:
        candidates = candidates[: int(args.max_candidates)]
    candidate_to_id = {value: index for index, value in enumerate(candidates)}
    train_rows = [row for row in train_rows if str(row.get("expected_content", "") or "").strip() in candidate_to_id]
    eval_rows = [row for row in eval_rows if str(row.get("expected_content", "") or "").strip() in candidate_to_id]
    if not train_rows or not eval_rows:
        raise RuntimeError("no train/eval rows remain after candidate filtering")

    model, tokenizer, model_manifest = retrieval_eval._load_model(
        Path(args.bundle_dir).resolve(),
        repo_root=repo_root,
        device=device,
    )
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    model.eval()

    train_x = _embed_rows(
        retrieval_eval,
        model,
        tokenizer,
        train_rows,
        text_source=str(args.text_source),
        max_tokens=int(args.max_encoder_tokens),
        batch_size=int(args.embed_batch_size),
        device=device,
    )
    eval_x = _embed_rows(
        retrieval_eval,
        model,
        tokenizer,
        eval_rows,
        text_source=str(args.text_source),
        max_tokens=int(args.max_encoder_tokens),
        batch_size=int(args.embed_batch_size),
        device=device,
    )
    train_y = torch.tensor(
        [candidate_to_id[str(row.get("expected_content", "") or "").strip()] for row in train_rows],
        dtype=torch.long,
    )
    eval_y = torch.tensor(
        [candidate_to_id[str(row.get("expected_content", "") or "").strip()] for row in eval_rows],
        dtype=torch.long,
    )

    head = _make_head(int(train_x.shape[1]), len(candidates), int(args.hidden_dim))
    head.to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))
    train_x_device = train_x.to(device)
    train_y_device = train_y.to(device)
    history: list[dict[str, float | int]] = []
    for step in range(1, int(args.steps) + 1):
        logits = head(train_x_device)
        loss = F.cross_entropy(logits, train_y_device)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % int(args.log_every) == 0:
            train_acc = logits.argmax(dim=-1).eq(train_y_device).float().mean().item()
            history.append({"step": step, "loss": float(loss.detach().cpu().item()), "train_accuracy": float(train_acc)})

    head.eval()
    with torch.no_grad():
        train_logits = head(train_x.to(device)).detach().cpu()
        eval_logits = head(eval_x.to(device)).detach().cpu()
    train_eval = _evaluate(train_logits, train_y, candidates, train_rows, int(args.max_failures))
    eval_eval = _evaluate(eval_logits, eval_y, candidates, eval_rows, int(args.max_failures))
    head_params = sum(parameter.numel() for parameter in head.parameters())
    base_params = int(model_manifest.get("parameter_count") or model_manifest.get("training_summary", {}).get("parameter_count") or 0)
    summary = {
        "artifact_kind": "frozen_answer_value_head_eval",
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "dataset_manifest": str(manifest_path),
        "text_source": str(args.text_source),
        "candidate_source": str(args.candidate_source),
        "candidate_count": len(candidates),
        "train_examples": len(train_rows),
        "eval_examples": len(eval_rows),
        "embedding_dim": int(train_x.shape[1]),
        "base_parameter_count": base_params,
        "answer_head_parameter_count": int(head_params),
        "answer_head_hidden_dim": int(args.hidden_dim),
        "total_with_answer_head_parameter_count": int(base_params + head_params),
        "steps": int(args.steps),
        "learning_rate": float(args.learning_rate),
        "weight_decay": float(args.weight_decay),
        "history": history,
        "train": train_eval,
        "eval": eval_eval,
        "decision_hint": (
            "If eval top1 is high while retrieval metrics remain unchanged by construction, "
            "the next path is to integrate this value-ranking head or a contrastive variant "
            "inside the model boundary and test held-out/generalized rows."
        ),
    }
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if str(args.output_head).strip():
        torch.save(
            {
                "state_dict": head.state_dict(),
                "candidates": candidates,
                "text_source": str(args.text_source),
                "embedding_dim": int(train_x.shape[1]),
                "base_bundle_dir": str(Path(args.bundle_dir).resolve()),
            },
            str(Path(args.output_head)),
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(_repo_root()))
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--text-source", choices=("encoder_text", "retrieval_query_text"), default="encoder_text")
    parser.add_argument("--candidate-source", choices=("eval", "train", "train_eval"), default="train_eval")
    parser.add_argument("--max-train-examples", type=int, default=0)
    parser.add_argument("--max-eval-examples", type=int, default=0)
    parser.add_argument("--max-candidates", type=int, default=0)
    parser.add_argument("--max-encoder-tokens", type=int, default=256)
    parser.add_argument("--embed-batch-size", type=int, default=64)
    parser.add_argument("--steps", type=int, default=2000)
    parser.add_argument("--hidden-dim", type=int, default=0)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--log-every", type=int, default=100)
    parser.add_argument("--seed", type=int, default=790)
    parser.add_argument("--max-failures", type=int, default=20)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-head", default="")
    args = parser.parse_args()
    summary = train(args)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
