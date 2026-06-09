#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import random
import re
from typing import Any

import torch
import torch.nn.functional as F


_QPAIR_RE = re.compile(r"\bqpair_[A-Za-z0-9]+\b")
_DPAIR_RE = re.compile(r"\bdpair_[A-Za-z0-9]+\b")
_QENT_RE = re.compile(r"\bqent_[A-Za-z0-9]+\b")
_DENT_RE = re.compile(r"\bdent_[A-Za-z0-9]+\b")


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
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _rows_by_split(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out = {"train": [], "calibration": [], "eval": []}
    for row in rows:
        split = str(row.get("split", ""))
        if split in out:
            out[split].append(row)
    return out


def _unique_docs(rows: list[dict[str, Any]]) -> list[str]:
    docs: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for candidate in list(row.get("candidates", []) or []):
            doc = str(candidate.get("doc_text", "") or "").strip()
            if doc and doc not in seen:
                seen.add(doc)
                docs.append(doc)
    return docs


def _span(pattern: re.Pattern[str], text: str) -> tuple[int, int] | None:
    match = pattern.search(str(text or ""))
    return (int(match.start()), int(match.end())) if match else None


def _token_indices_for_span(offsets: list[tuple[int, int]], span: tuple[int, int] | None, mask: torch.Tensor) -> list[int]:
    if span is None:
        return []
    start, end = span
    indices: list[int] = []
    for index, (token_start, token_end) in enumerate(offsets):
        if int(mask[index].item()) == 0:
            continue
        if token_end > start and token_start < end:
            indices.append(index)
    return indices


def _encode_with_offsets(tokenizer, text: str, max_tokens: int) -> tuple[list[int], list[tuple[int, int]]]:
    inner = getattr(tokenizer, "tokenizer", None)
    if inner is None:
        ids = tokenizer.encode(text, max_length=max_tokens)
        offsets = [(0, 0)] * len(ids)
        return ids, offsets
    encoded = inner.encode(str(text), add_special_tokens=True)
    return list(encoded.ids)[:max_tokens], list(encoded.offsets)[:max_tokens]


def _span_pools(
    model,
    tokenizer,
    texts: list[str],
    *,
    patterns: tuple[re.Pattern[str], re.Pattern[str]],
    max_tokens: int,
    device: torch.device,
) -> torch.Tensor:
    pad_id = int(getattr(tokenizer, "pad_token_id", 0) or 0)
    vectors: list[torch.Tensor] = []
    with torch.no_grad():
        for text in texts:
            ids, offsets = _encode_with_offsets(tokenizer, text, int(max_tokens))
            mask_values = [1] * len(ids)
            while len(ids) < int(max_tokens):
                ids.append(pad_id)
                mask_values.append(0)
                offsets.append((0, 0))
            input_ids = torch.tensor([ids[: int(max_tokens)]], dtype=torch.long, device=device)
            mask = torch.tensor(mask_values[: int(max_tokens)], dtype=torch.long, device=device)
            hidden = model.encode(input_ids, mask.unsqueeze(0))[0].detach().float().cpu()
            pooled: list[torch.Tensor] = []
            for pattern in patterns:
                indices = _token_indices_for_span(offsets[: int(max_tokens)], _span(pattern, text), mask.cpu())
                if indices:
                    pooled.append(hidden[indices].mean(dim=0))
                else:
                    weights = mask.cpu().to(dtype=hidden.dtype).unsqueeze(-1)
                    pooled.append((hidden * weights).sum(dim=0) / weights.sum().clamp_min(1.0))
            vectors.append(torch.cat(pooled, dim=0))
    return torch.stack(vectors, dim=0)


class SpanHead(torch.nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(int(input_dim), int(hidden_dim)),
            torch.nn.GELU(),
            torch.nn.Linear(int(hidden_dim), 1),
        )
        for module in self.modules():
            if isinstance(module, torch.nn.Linear):
                torch.nn.init.xavier_uniform_(module.weight)
                torch.nn.init.zeros_(module.bias)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.net(features).squeeze(-1)


def _label(candidates: list[dict[str, Any]]) -> int:
    for index, candidate in enumerate(candidates):
        if bool(candidate.get("is_exact")):
            return index
    for index, candidate in enumerate(candidates):
        if bool(candidate.get("is_answer_match")):
            return index
    return -1


def _features(query_span: torch.Tensor, doc_spans: torch.Tensor, candidates: list[dict[str, Any]], device: torch.device) -> torch.Tensor:
    query_span = query_span.to(device)
    doc_spans = doc_spans.to(device)
    query = query_span.unsqueeze(0).expand_as(doc_spans)
    base = torch.tensor([float(c.get("base_score", 0.0) or 0.0) for c in candidates], dtype=torch.float32, device=device).unsqueeze(-1)
    prob = torch.tensor([float(c.get("partition_probability", 0.0) or 0.0) for c in candidates], dtype=torch.float32, device=device).unsqueeze(-1)
    return torch.cat([query, doc_spans, query * doc_spans, (query - doc_spans).abs(), base, prob], dim=-1)


def _score_split(
    *,
    scorer: SpanHead,
    rows: list[dict[str, Any]],
    query_spans: torch.Tensor,
    doc_spans: torch.Tensor,
    doc_to_index: dict[str, int],
    device: torch.device,
) -> dict[str, Any]:
    answer = exact = base_answer = base_exact = recoverable = 0
    mrr = 0.0
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            candidates = list(row.get("candidates", []) or [])
            doc_indices = [doc_to_index[str(candidate.get("doc_text", "") or "")] for candidate in candidates]
            scores = scorer(_features(query_spans[row_index], doc_spans[doc_indices], candidates, device)).detach().cpu()
            base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates])
            order = sorted(range(len(candidates)), key=lambda idx: (-float(scores[idx].item()), idx))
            base_order = sorted(range(len(candidates)), key=lambda idx: (-float(base_scores[idx].item()), idx))
            label = _label(candidates)
            if label >= 0:
                mrr += 1.0 / float(order.index(label) + 1)
            recoverable += int(any(bool(c.get("is_exact")) or bool(c.get("is_answer_match")) for c in candidates))
            top = candidates[order[0]]
            base_top = candidates[base_order[0]]
            answer += int(bool(top.get("is_exact")) or bool(top.get("is_answer_match")))
            exact += int(bool(top.get("is_exact")))
            base_answer += int(bool(base_top.get("is_exact")) or bool(base_top.get("is_answer_match")))
            base_exact += int(bool(base_top.get("is_exact")))
    total = len(rows)
    return {
        "examples": total,
        "answer_correct": answer,
        "exact_correct": exact,
        "base_answer_correct": base_answer,
        "base_exact_correct": base_exact,
        "answer_recoverable": recoverable,
        "mrr": mrr / float(total or 1),
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    retrieval_eval = _load_retrieval_eval(Path(args.repo_root).resolve())
    rows = _rows_by_split(_iter_jsonl(Path(args.targets_jsonl)))
    model, tokenizer, _ = retrieval_eval._load_model(Path(args.bundle_dir).resolve(), repo_root=Path(args.repo_root).resolve(), device=device)
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    model.eval()

    split_docs = {split: _unique_docs(split_rows) for split, split_rows in rows.items()}
    split_doc_to_index = {split: {doc: index for index, doc in enumerate(docs)} for split, docs in split_docs.items()}
    query_spans = {
        split: _span_pools(model, tokenizer, [str(row.get("query_text", "") or "") for row in split_rows], patterns=(_QPAIR_RE, _QENT_RE), max_tokens=int(args.max_query_tokens), device=device)
        for split, split_rows in rows.items()
    }
    doc_spans = {
        split: _span_pools(model, tokenizer, split_docs[split], patterns=(_DPAIR_RE, _DENT_RE), max_tokens=int(args.max_doc_tokens), device=device)
        for split in rows
    }
    input_dim = int(query_spans["train"].shape[-1]) * 4 + 2
    scorer = SpanHead(input_dim, int(args.hidden_dim)).to(device)
    optimizer = torch.optim.AdamW(scorer.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))
    train_rows = [row for row in rows["train"] if _label(list(row.get("candidates", []) or [])) >= 0]
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
            scores = scorer(_features(query_spans["train"][row_id], doc_spans["train"][doc_indices], candidates, device))
            losses.append(F.cross_entropy(scores.unsqueeze(0), torch.tensor([_label(candidates)], dtype=torch.long, device=device)))
        loss = torch.stack(losses).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % int(args.eval_every) == 0:
            calibration = _score_split(scorer=scorer, rows=rows["calibration"], query_spans=query_spans["calibration"], doc_spans=doc_spans["calibration"], doc_to_index=split_doc_to_index["calibration"], device=device)
            history.append({"step": step, "loss": float(loss.detach().cpu().item()), "calibration_answer": calibration["answer_correct"], "calibration_exact": calibration["exact_correct"], "calibration_mrr": calibration["mrr"]})
            key = (calibration["answer_correct"], calibration["exact_correct"], calibration["mrr"])
            if best_key is None or key > best_key:
                best_key = key
                best_state = {name: value.detach().cpu().clone() for name, value in scorer.state_dict().items()}
    if best_state is not None:
        scorer.load_state_dict(best_state)
    summary = {
        "artifact_kind": "stage903_relation_span_pool_value_head",
        "targets_jsonl": str(Path(args.targets_jsonl).resolve()),
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "parameter_count": sum(parameter.numel() for parameter in scorer.parameters()),
        "hidden_dim": int(args.hidden_dim),
        "steps": int(args.steps),
        "history": history,
        "train": _score_split(scorer=scorer, rows=rows["train"], query_spans=query_spans["train"], doc_spans=doc_spans["train"], doc_to_index=split_doc_to_index["train"], device=device),
        "calibration": _score_split(scorer=scorer, rows=rows["calibration"], query_spans=query_spans["calibration"], doc_spans=doc_spans["calibration"], doc_to_index=split_doc_to_index["calibration"], device=device),
        "eval": _score_split(scorer=scorer, rows=rows["eval"], query_spans=query_spans["eval"], doc_spans=doc_spans["eval"], doc_to_index=split_doc_to_index["eval"], device=device),
        "decision_hint": "Uses localized qpair/qent and dpair/dent token-state pooling. This is a span-locator diagnostic, not fully open model-owned routing.",
    }
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(_repo_root()))
    parser.add_argument("--targets-jsonl", required=True)
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--max-query-tokens", type=int, default=128)
    parser.add_argument("--max-doc-tokens", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--rows-per-step", type=int, default=64)
    parser.add_argument("--eval-every", type=int, default=50)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=903)
    parser.add_argument("--output-json", required=True)
    train(parser.parse_args())


if __name__ == "__main__":
    main()
