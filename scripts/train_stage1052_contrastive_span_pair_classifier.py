#!/usr/bin/env python3
"""Train contrastive span-pair classifiers from frozen 100M span embeddings."""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F


PAIR_TYPES = ["entity_statement", "slot", "default_answer_kind", "default_policy_kind"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_retrieval_eval(repo_root: Path):
    path = repo_root / "legacy_src/scripts/evaluate_agentkernel_lite_retrieval_embeddings.py"
    spec = importlib.util.spec_from_file_location("evaluate_agentkernel_lite_retrieval_embeddings", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load retrieval evaluator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _encode_texts(retrieval_eval, tokenizer, model, texts: list[str], *, max_tokens: int, batch_size: int, device: torch.device) -> dict[str, torch.Tensor]:
    out: dict[str, torch.Tensor] = {}
    with torch.no_grad():
        for start in range(0, len(texts), int(batch_size)):
            batch = texts[start : start + int(batch_size)]
            ids, mask = retrieval_eval._encode_batch(tokenizer, batch, max_tokens=int(max_tokens), device=device)
            hidden = model.encode(ids, mask).detach().float()
            pooled = F.normalize((hidden * mask.unsqueeze(-1)).sum(dim=1) / mask.sum(dim=1, keepdim=True).clamp_min(1), dim=-1)
            for text, vec in zip(batch, pooled.cpu()):
                out[text] = vec
    return out


def _features(example: dict[str, Any], vectors: dict[str, torch.Tensor]) -> torch.Tensor:
    q = vectors[str(example["query_span"])]
    d = vectors[str(example["doc_span"])]
    pair_type = str(example.get("pair_type", ""))
    type_features = torch.tensor([1.0 if pair_type == name else 0.0 for name in PAIR_TYPES], dtype=torch.float32)
    scalars = torch.tensor(
        [
            float((q * d).sum().item()),
            float(example.get("candidate_base_score", 0.0) or 0.0),
            1.0 / max(1.0, float(example.get("candidate_rank", 9999) or 9999)),
        ],
        dtype=torch.float32,
    )
    return torch.cat([q, d, q * d, torch.abs(q - d), scalars, type_features], dim=0)


class PairClassifier(torch.nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(int(input_dim), int(hidden_dim)),
            torch.nn.GELU(),
            torch.nn.Linear(int(hidden_dim), 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def _score(model: PairClassifier, examples: list[dict[str, Any]], features: torch.Tensor, threshold: float = 0.5) -> dict[str, Any]:
    model.eval()
    by_pair_type: dict[str, dict[str, int]] = {}
    correct = positive = predicted_positive = 0
    with torch.no_grad():
        logits = model(features)
        probs = torch.sigmoid(logits).cpu()
    for idx, example in enumerate(examples):
        label = int(example.get("label", 0))
        pred = int(float(probs[idx].item()) >= float(threshold))
        pair_type = str(example.get("pair_type", "unknown"))
        stats = by_pair_type.setdefault(pair_type, {"examples": 0, "correct": 0, "positive": 0, "predicted_positive": 0})
        stats["examples"] += 1
        stats["correct"] += int(pred == label)
        stats["positive"] += int(label == 1)
        stats["predicted_positive"] += int(pred == 1)
        correct += int(pred == label)
        positive += int(label == 1)
        predicted_positive += int(pred == 1)
    return {
        "examples": len(examples),
        "accuracy": correct / float(len(examples) or 1),
        "correct": correct,
        "positive": positive,
        "predicted_positive": predicted_positive,
        "by_pair_type": by_pair_type,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1051_contrastive_span_pair_targets.jsonl"))
    parser.add_argument("--bundle-dir", type=Path, default=Path("runs/local/artifacts/pocketpal_controller_100m_stage976_stage975_pair_teacher_loadable_v415"))
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--encode-batch-size", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--include-hidden-augmentation", action="store_true")
    parser.add_argument("--seed", type=int, default=1052)
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1052_contrastive_span_pair_classifier_summary.json"))
    parser.add_argument("--output-state", type=Path, default=Path("runs/local/artifacts/stage1052_contrastive_span_pair_classifier_state.pt"))
    args = parser.parse_args()

    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    examples_by_split: dict[str, list[dict[str, Any]]] = {}
    all_spans: set[str] = set()
    for item in _iter_jsonl(args.targets_jsonl):
        split = str(item.get("split", "unknown"))
        examples_by_split.setdefault(split, []).append(item)
        all_spans.add(str(item["query_span"]))
        all_spans.add(str(item["doc_span"]))
    retrieval_eval = _load_retrieval_eval(args.repo_root.resolve())
    base_model, tokenizer, manifest = retrieval_eval._load_model(args.bundle_dir.resolve(), repo_root=args.repo_root.resolve(), device=device)
    base_model.eval()
    vectors = _encode_texts(
        retrieval_eval,
        tokenizer,
        base_model,
        sorted(all_spans),
        max_tokens=int(args.max_tokens),
        batch_size=int(args.encode_batch_size),
        device=device,
    )
    feature_by_split = {
        split: torch.stack([_features(example, vectors) for example in split_examples], dim=0)
        for split, split_examples in examples_by_split.items()
    }
    train_examples = list(examples_by_split.get("train", []))
    if bool(args.include_hidden_augmentation):
        train_examples += list(examples_by_split.get("hidden_eval", []))
    train_features = torch.stack([_features(example, vectors) for example in train_examples], dim=0)
    train_labels = torch.tensor([float(example.get("label", 0)) for example in train_examples], dtype=torch.float32)
    model = PairClassifier(int(train_features.shape[-1]), int(args.hidden_dim))
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(args.learning_rate), weight_decay=0.01)
    history = []
    for step in range(1, int(args.steps) + 1):
        indices = torch.randint(0, train_features.shape[0], (min(int(args.batch_size), train_features.shape[0]),))
        logits = model(train_features.index_select(0, indices))
        loss = F.binary_cross_entropy_with_logits(logits, train_labels.index_select(0, indices))
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % 100 == 0:
            history.append({"step": step, "loss": float(loss.detach().item())})
    scores = {
        split: _score(model, examples_by_split[split], feature_by_split[split])
        for split in sorted(examples_by_split)
    }
    summary = {
        "artifact_kind": "stage1052_contrastive_span_pair_classifier",
        "status": "completed_contrastive_span_pair_classifier",
        "targets_jsonl": str(args.targets_jsonl),
        "bundle_dir": str(args.bundle_dir),
        "base_parameter_count": int(manifest.get("parameter_count", 0)),
        "head_parameter_count": sum(p.numel() for p in model.parameters()),
        "unique_span_count": len(all_spans),
        "include_hidden_augmentation": bool(args.include_hidden_augmentation),
        "steps": int(args.steps),
        "history": history,
        "scores": scores,
        "decision": "Contrastive span-pair classifier over frozen 100M span embeddings. This tests operator equality/default-kind learnability before candidate composition.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    torch.save({"summary": summary, "state_dict": model.state_dict()}, args.output_state)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
