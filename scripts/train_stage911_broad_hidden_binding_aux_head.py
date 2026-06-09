#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import random
from typing import Any

import torch
import torch.nn.functional as F


BINDING_TARGETS = (
    "pair_suffix_match",
    "entity_suffix_match",
    "slot_suffix_match",
    "claim_suffix_match",
    "proof_edge_match",
)


def _load_stage899():
    path = Path(__file__).resolve().parent / "train_stage899_relation_bridge_distilled_value_head.py"
    spec = importlib.util.spec_from_file_location("stage899", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load Stage899 helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bridge_targets(candidates: list[dict[str, Any]], device: torch.device) -> torch.Tensor:
    rows = []
    for candidate in candidates:
        bridge = dict(candidate.get("bridge", {}) or {})
        rows.append([1.0 if bridge.get(target) else 0.0 for target in BINDING_TARGETS])
    return torch.tensor(rows, dtype=torch.float32, device=device)


class AuxHead(torch.nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, binding_dim: int = len(BINDING_TARGETS)) -> None:
        super().__init__()
        self.trunk = torch.nn.Sequential(torch.nn.Linear(int(input_dim), int(hidden_dim)), torch.nn.GELU())
        self.binding_head = torch.nn.Linear(int(hidden_dim), int(binding_dim))
        self.score_head = torch.nn.Linear(int(hidden_dim) + int(binding_dim), 1)
        for module in self.modules():
            if isinstance(module, torch.nn.Linear):
                torch.nn.init.xavier_uniform_(module.weight)
                torch.nn.init.zeros_(module.bias)

    def forward(self, features: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        hidden = self.trunk(features)
        binding_logits = self.binding_head(hidden)
        score_input = torch.cat([hidden, torch.sigmoid(binding_logits)], dim=-1)
        scores = self.score_head(score_input).squeeze(-1)
        return scores, binding_logits


def _score_split(
    *,
    helper,
    model: AuxHead,
    rows: list[dict[str, Any]],
    queries: torch.Tensor,
    doc_embeddings: torch.Tensor,
    doc_to_index: dict[str, int],
    device: torch.device,
) -> dict[str, Any]:
    answer = exact = base_answer = base_exact = recoverable_answer = recoverable_exact = 0
    mrr = 0.0
    binding_loss = 0.0
    by_operation: dict[str, dict[str, int]] = {}
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            candidates = list(row.get("candidates", []) or [])
            if not candidates:
                continue
            operation = str(row.get("operation", "") or "unknown")
            stats = by_operation.setdefault(operation, {"examples": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0})
            stats["examples"] += 1
            doc_indices = [doc_to_index[str(candidate.get("doc_text", "") or "")] for candidate in candidates]
            features = helper._features(queries[row_index], doc_embeddings[doc_indices], candidates, device)
            scores, binding_logits = model(features)
            binding_loss += float(F.binary_cross_entropy_with_logits(binding_logits, _bridge_targets(candidates, device)).detach().cpu().item())
            scores = scores.detach().cpu()
            base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates])
            order = sorted(range(len(candidates)), key=lambda idx: (-float(scores[idx].item()), idx))
            base_order = sorted(range(len(candidates)), key=lambda idx: (-float(base_scores[idx].item()), idx))
            label = helper._label(candidates)
            if label >= 0:
                mrr += 1.0 / float(order.index(label) + 1)
            recoverable_answer += int(any(bool(c.get("is_exact")) or bool(c.get("is_answer_match")) for c in candidates))
            recoverable_exact += int(any(bool(c.get("is_exact")) for c in candidates))
            top = candidates[order[0]]
            base_top = candidates[base_order[0]]
            top_answer = int(bool(top.get("is_exact")) or bool(top.get("is_answer_match")))
            top_exact = int(bool(top.get("is_exact")))
            base_top_answer = int(bool(base_top.get("is_exact")) or bool(base_top.get("is_answer_match")))
            base_top_exact = int(bool(base_top.get("is_exact")))
            answer += top_answer
            exact += top_exact
            base_answer += base_top_answer
            base_exact += base_top_exact
            stats["answer"] += top_answer
            stats["exact"] += top_exact
            stats["base_answer"] += base_top_answer
            stats["base_exact"] += base_top_exact
    total = len(rows)
    return {
        "examples": total,
        "answer_correct": answer,
        "exact_correct": exact,
        "answer_recoverable": recoverable_answer,
        "exact_recoverable": recoverable_exact,
        "base_answer_correct": base_answer,
        "base_exact_correct": base_exact,
        "mrr": mrr / float(total or 1),
        "binding_bce": binding_loss / float(total or 1),
        "by_operation": by_operation,
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    helper = _load_stage899()
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    repo_root = Path(args.repo_root).resolve()
    retrieval_eval = helper._load_retrieval_eval(repo_root)
    rows = helper._rows_by_split(helper._iter_jsonl(Path(args.targets_jsonl)))
    base_model, tokenizer, _ = retrieval_eval._load_model(Path(args.bundle_dir).resolve(), repo_root=repo_root, device=device)
    for parameter in base_model.parameters():
        parameter.requires_grad_(False)
    base_model.eval()

    split_docs = {split: helper._unique_docs(split_rows) for split, split_rows in rows.items()}
    split_doc_to_index = {split: {doc: index for index, doc in enumerate(docs)} for split, docs in split_docs.items()}
    queries = {
        split: helper._embed_queries(retrieval_eval, base_model, tokenizer, split_rows, max_tokens=int(args.max_query_tokens), batch_size=int(args.embed_batch_size), device=device)
        for split, split_rows in rows.items()
    }
    docs = {
        split: helper._embed_docs(retrieval_eval, base_model, tokenizer, split_docs[split], max_tokens=int(args.max_doc_tokens), batch_size=int(args.embed_batch_size), device=device)
        for split in rows
    }

    input_dim = int(queries["train"].shape[-1]) * 4 + 2
    model = AuxHead(input_dim, int(args.hidden_dim)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))
    train_rows = [row for row in rows["train"] if helper._label(list(row.get("candidates", []) or [])) >= 0]
    order = list(range(len(train_rows)))
    best_state = None
    best_key = None
    history = []
    for step in range(1, int(args.steps) + 1):
        random.shuffle(order)
        losses = []
        for row_id in order[: int(args.rows_per_step)]:
            row = train_rows[row_id]
            candidates = list(row.get("candidates", []) or [])
            doc_indices = [split_doc_to_index["train"][str(candidate.get("doc_text", "") or "")] for candidate in candidates]
            features = helper._features(queries["train"][row_id], docs["train"][doc_indices], candidates, device)
            scores, binding_logits = model(features)
            ce = F.cross_entropy(scores.unsqueeze(0), torch.tensor([helper._label(candidates)], dtype=torch.long, device=device))
            bce = F.binary_cross_entropy_with_logits(binding_logits, _bridge_targets(candidates, device))
            losses.append(ce + float(args.binding_loss_weight) * bce)
        loss = torch.stack(losses).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % int(args.eval_every) == 0:
            calibration = _score_split(helper=helper, model=model, rows=rows["calibration"], queries=queries["calibration"], doc_embeddings=docs["calibration"], doc_to_index=split_doc_to_index["calibration"], device=device)
            history.append({"step": step, "loss": float(loss.detach().cpu().item()), "calibration_answer": calibration["answer_correct"], "calibration_exact": calibration["exact_correct"], "calibration_binding_bce": calibration["binding_bce"], "calibration_mrr": calibration["mrr"]})
            key = (calibration["answer_correct"], calibration["exact_correct"], calibration["mrr"])
            if best_key is None or key > best_key:
                best_key = key
                best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    summary = {
        "artifact_kind": str(args.artifact_kind),
        "targets_jsonl": str(Path(args.targets_jsonl).resolve()),
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "binding_targets": list(BINDING_TARGETS),
        "hidden_dim": int(args.hidden_dim),
        "binding_loss_weight": float(args.binding_loss_weight),
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "steps": int(args.steps),
        "rows_per_step": int(args.rows_per_step),
        "history": history,
        "train": _score_split(helper=helper, model=model, rows=rows["train"], queries=queries["train"], doc_embeddings=docs["train"], doc_to_index=split_doc_to_index["train"], device=device),
        "calibration": _score_split(helper=helper, model=model, rows=rows["calibration"], queries=queries["calibration"], doc_embeddings=docs["calibration"], doc_to_index=split_doc_to_index["calibration"], device=device),
        "eval": _score_split(helper=helper, model=model, rows=rows["eval"], queries=queries["eval"], doc_embeddings=docs["eval"], doc_to_index=split_doc_to_index["eval"], device=device),
        "decision_hint": "Input has frozen hidden embedding pair features plus base/probability. Binding targets supervise pair/entity/slot/claim/proof match logits when present; no bridge suffix or proof features are input.",
    }
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--targets-jsonl", required=True)
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-query-tokens", type=int, default=128)
    parser.add_argument("--max-doc-tokens", type=int, default=128)
    parser.add_argument("--embed-batch-size", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--rows-per-step", type=int, default=128)
    parser.add_argument("--eval-every", type=int, default=50)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--binding-loss-weight", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=911)
    parser.add_argument("--artifact-kind", default="stage911_broad_hidden_binding_aux_head")
    parser.add_argument("--output-json", required=True)
    train(parser.parse_args())


if __name__ == "__main__":
    main()
