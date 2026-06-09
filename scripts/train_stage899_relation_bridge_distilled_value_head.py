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


def _rows_by_split(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"train": [], "calibration": [], "eval": []}
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


def _embed_queries(retrieval_eval, model, tokenizer, rows: list[dict[str, Any]], *, max_tokens: int, batch_size: int, device: torch.device) -> torch.Tensor:
    chunks: list[torch.Tensor] = []
    with torch.no_grad():
        for offset in range(0, len(rows), int(batch_size)):
            texts = [str(row.get("query_text", "") or "") for row in rows[offset : offset + int(batch_size)]]
            chunks.append(retrieval_eval._embed_query(model, tokenizer, texts, max_tokens=int(max_tokens), device=device).detach().float().cpu())
    return torch.cat(chunks, dim=0) if chunks else torch.empty((0, 0))


def _embed_docs(retrieval_eval, model, tokenizer, docs: list[str], *, max_tokens: int, batch_size: int, device: torch.device) -> torch.Tensor:
    chunks: list[torch.Tensor] = []
    with torch.no_grad():
        for offset in range(0, len(docs), int(batch_size)):
            chunks.append(retrieval_eval._embed_doc(model, tokenizer, docs[offset : offset + int(batch_size)], max_tokens=int(max_tokens), device=device).detach().float().cpu())
    return torch.cat(chunks, dim=0) if chunks else torch.empty((0, 0))


class ValueHead(torch.nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int) -> None:
        super().__init__()
        if int(hidden_dim) <= 0:
            self.net = torch.nn.Linear(int(input_dim), 1)
        else:
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


def _features(query: torch.Tensor, docs: torch.Tensor, candidates: list[dict[str, Any]], device: torch.device) -> torch.Tensor:
    query = query.to(device)
    docs = docs.to(device)
    query_expanded = query.unsqueeze(0).expand_as(docs)
    base = torch.tensor([float(c.get("base_score", 0.0) or 0.0) for c in candidates], dtype=torch.float32, device=device).unsqueeze(-1)
    prob = torch.tensor([float(c.get("partition_probability", 0.0) or 0.0) for c in candidates], dtype=torch.float32, device=device).unsqueeze(-1)
    return torch.cat([query_expanded, docs, query_expanded * docs, (query_expanded - docs).abs(), base, prob], dim=-1)


def _label(candidates: list[dict[str, Any]]) -> int:
    for index, candidate in enumerate(candidates):
        if bool(candidate.get("is_exact")):
            return index
    for index, candidate in enumerate(candidates):
        if bool(candidate.get("is_answer_match")):
            return index
    return -1


def _score_split(
    *,
    scorer: ValueHead,
    rows: list[dict[str, Any]],
    queries: torch.Tensor,
    doc_embeddings: torch.Tensor,
    doc_to_index: dict[str, int],
    device: torch.device,
) -> dict[str, Any]:
    scorer.eval()
    answer = exact = recoverable_answer = recoverable_exact = base_answer = base_exact = teacher_answer = teacher_exact = 0
    mrr = 0.0
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            candidates = list(row.get("candidates", []) or [])
            if not candidates:
                continue
            doc_indices = [doc_to_index[str(candidate.get("doc_text", "") or "")] for candidate in candidates]
            features = _features(queries[row_index], doc_embeddings[doc_indices], candidates, device)
            scores = scorer(features).detach().cpu()
            base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates])
            teacher_scores = torch.tensor([float(candidate.get("teacher_bridge_score", 0.0) or 0.0) for candidate in candidates])
            orders = {
                "model": sorted(range(len(candidates)), key=lambda idx: (-float(scores[idx].item()), idx)),
                "base": sorted(range(len(candidates)), key=lambda idx: (-float(base_scores[idx].item()), idx)),
                "teacher": sorted(range(len(candidates)), key=lambda idx: (-float(teacher_scores[idx].item()), idx)),
            }
            label = _label(candidates)
            if label >= 0:
                mrr += 1.0 / float(orders["model"].index(label) + 1)
            recoverable_answer += int(any(bool(c.get("is_exact")) or bool(c.get("is_answer_match")) for c in candidates))
            recoverable_exact += int(any(bool(c.get("is_exact")) for c in candidates))
            top = candidates[orders["model"][0]]
            base_top = candidates[orders["base"][0]]
            teacher_top = candidates[orders["teacher"][0]]
            answer += int(bool(top.get("is_exact")) or bool(top.get("is_answer_match")))
            exact += int(bool(top.get("is_exact")))
            base_answer += int(bool(base_top.get("is_exact")) or bool(base_top.get("is_answer_match")))
            base_exact += int(bool(base_top.get("is_exact")))
            teacher_answer += int(bool(teacher_top.get("is_exact")) or bool(teacher_top.get("is_answer_match")))
            teacher_exact += int(bool(teacher_top.get("is_exact")))
    total = len(rows)
    return {
        "examples": total,
        "answer_correct": answer,
        "exact_correct": exact,
        "answer_recoverable": recoverable_answer,
        "exact_recoverable": recoverable_exact,
        "mrr": mrr / float(total or 1),
        "base_answer_correct": base_answer,
        "base_exact_correct": base_exact,
        "teacher_answer_correct": teacher_answer,
        "teacher_exact_correct": teacher_exact,
    }


def _score_split_blend(
    *,
    scorer: ValueHead,
    rows: list[dict[str, Any]],
    queries: torch.Tensor,
    doc_embeddings: torch.Tensor,
    doc_to_index: dict[str, int],
    device: torch.device,
    alpha: float,
) -> dict[str, Any]:
    scorer.eval()
    answer = exact = 0
    mrr = 0.0
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            candidates = list(row.get("candidates", []) or [])
            if not candidates:
                continue
            doc_indices = [doc_to_index[str(candidate.get("doc_text", "") or "")] for candidate in candidates]
            features = _features(queries[row_index], doc_embeddings[doc_indices], candidates, device)
            model_scores = scorer(features).detach().cpu()
            base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates])
            scores = base_scores + float(alpha) * model_scores
            order = sorted(range(len(candidates)), key=lambda idx: (-float(scores[idx].item()), idx))
            label = _label(candidates)
            if label >= 0:
                mrr += 1.0 / float(order.index(label) + 1)
            top = candidates[order[0]]
            answer += int(bool(top.get("is_exact")) or bool(top.get("is_answer_match")))
            exact += int(bool(top.get("is_exact")))
    total = len(rows)
    return {
        "examples": total,
        "answer_correct": answer,
        "exact_correct": exact,
        "mrr": mrr / float(total or 1),
        "alpha": float(alpha),
    }


def _alpha_sweep(
    *,
    scorer: ValueHead,
    rows: list[dict[str, Any]],
    queries: torch.Tensor,
    doc_embeddings: torch.Tensor,
    doc_to_index: dict[str, int],
    device: torch.device,
    alphas: list[float],
) -> dict[str, Any]:
    scored = [
        _score_split_blend(
            scorer=scorer,
            rows=rows,
            queries=queries,
            doc_embeddings=doc_embeddings,
            doc_to_index=doc_to_index,
            device=device,
            alpha=float(alpha),
        )
        for alpha in alphas
    ]
    return max(scored, key=lambda item: (item["answer_correct"], item["exact_correct"], item["mrr"]))


def train(args: argparse.Namespace) -> dict[str, Any]:
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    repo_root = Path(args.repo_root).resolve()
    retrieval_eval = _load_retrieval_eval(repo_root)
    rows = _rows_by_split(_iter_jsonl(Path(args.targets_jsonl)))

    model, tokenizer, _ = retrieval_eval._load_model(Path(args.bundle_dir).resolve(), repo_root=repo_root, device=device)
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    model.eval()

    split_docs = {split: _unique_docs(split_rows) for split, split_rows in rows.items()}
    split_doc_to_index = {split: {doc: index for index, doc in enumerate(docs)} for split, docs in split_docs.items()}
    queries = {
        split: _embed_queries(
            retrieval_eval,
            model,
            tokenizer,
            split_rows,
            max_tokens=int(args.max_query_tokens),
            batch_size=int(args.embed_batch_size),
            device=device,
        )
        for split, split_rows in rows.items()
    }
    docs = {
        split: _embed_docs(
            retrieval_eval,
            model,
            tokenizer,
            split_docs[split],
            max_tokens=int(args.max_doc_tokens),
            batch_size=int(args.embed_batch_size),
            device=device,
        )
        for split in rows
    }
    input_dim = int(queries["train"].shape[-1]) * 4 + 2
    scorer = ValueHead(input_dim, int(args.hidden_dim)).to(device)
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
            features = _features(queries["train"][row_id], docs["train"][doc_indices], candidates, device)
            scores = scorer(features)
            label = _label(candidates)
            ce = F.cross_entropy(scores.unsqueeze(0), torch.tensor([label], dtype=torch.long, device=device))
            teacher = torch.tensor([float(candidate.get("teacher_bridge_score", 0.0) or 0.0) for candidate in candidates], dtype=torch.float32, device=device)
            teacher = teacher - teacher.mean()
            pred = scores - scores.mean()
            mse = F.mse_loss(pred, teacher)
            losses.append(ce + float(args.teacher_mse_weight) * mse)
        loss = torch.stack(losses).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % int(args.eval_every) == 0:
            calibration = _score_split(
                scorer=scorer,
                rows=rows["calibration"],
                queries=queries["calibration"],
                doc_embeddings=docs["calibration"],
                doc_to_index=split_doc_to_index["calibration"],
                device=device,
            )
            history.append(
                {
                    "step": step,
                    "loss": float(loss.detach().cpu().item()),
                    "calibration_answer": calibration["answer_correct"],
                    "calibration_exact": calibration["exact_correct"],
                    "calibration_mrr": calibration["mrr"],
                }
            )
            key = (calibration["answer_correct"], calibration["exact_correct"], calibration["mrr"])
            if best_key is None or key > best_key:
                best_key = key
                best_state = {name: value.detach().cpu().clone() for name, value in scorer.state_dict().items()}
    if best_state is not None:
        scorer.load_state_dict(best_state)

    alpha_values = [float(item) for item in str(args.alpha_sweep).split(",") if item.strip()]
    calibration_alpha = _alpha_sweep(
        scorer=scorer,
        rows=rows["calibration"],
        queries=queries["calibration"],
        doc_embeddings=docs["calibration"],
        doc_to_index=split_doc_to_index["calibration"],
        device=device,
        alphas=alpha_values,
    )
    eval_alpha = _score_split_blend(
        scorer=scorer,
        rows=rows["eval"],
        queries=queries["eval"],
        doc_embeddings=docs["eval"],
        doc_to_index=split_doc_to_index["eval"],
        device=device,
        alpha=float(calibration_alpha["alpha"]),
    )
    summary = {
        "artifact_kind": "stage899_relation_bridge_distilled_value_head",
        "targets_jsonl": str(Path(args.targets_jsonl).resolve()),
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "parameter_count": sum(parameter.numel() for parameter in scorer.parameters()),
        "hidden_dim": int(args.hidden_dim),
        "teacher_mse_weight": float(args.teacher_mse_weight),
        "steps": int(args.steps),
        "rows_per_step": int(args.rows_per_step),
        "history": history,
        "train": _score_split(scorer=scorer, rows=rows["train"], queries=queries["train"], doc_embeddings=docs["train"], doc_to_index=split_doc_to_index["train"], device=device),
        "calibration": _score_split(scorer=scorer, rows=rows["calibration"], queries=queries["calibration"], doc_embeddings=docs["calibration"], doc_to_index=split_doc_to_index["calibration"], device=device),
        "eval": _score_split(scorer=scorer, rows=rows["eval"], queries=queries["eval"], doc_embeddings=docs["eval"], doc_to_index=split_doc_to_index["eval"], device=device),
        "calibration_selected_blend": calibration_alpha,
        "eval_with_calibration_selected_blend": eval_alpha,
        "decision_hint": "Model scores use frozen query/doc hidden embeddings plus base/probability scalars; no pair_similarity, entity_similarity, or external bridge score is provided as input.",
    }
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if str(args.output_pt or "").strip():
        torch.save({"state_dict": scorer.state_dict(), "summary": summary}, Path(args.output_pt))
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
    parser.add_argument("--embed-batch-size", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--rows-per-step", type=int, default=64)
    parser.add_argument("--eval-every", type=int, default=50)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--teacher-mse-weight", type=float, default=0.25)
    parser.add_argument("--alpha-sweep", default="0,0.01,0.025,0.05,0.075,0.1,0.15,0.2,0.3,0.5,0.75,1.0")
    parser.add_argument("--seed", type=int, default=899)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-pt", default="")
    train(parser.parse_args())


if __name__ == "__main__":
    main()
