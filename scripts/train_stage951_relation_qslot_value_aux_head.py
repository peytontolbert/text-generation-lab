#!/usr/bin/env python3
"""Train a relation qslot/value auxiliary head from Stage950 targets."""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F


def _load_stage924():
    path = Path(__file__).resolve().parent / "train_stage924_cached_encoder_bridge_finetune.py"
    spec = importlib.util.spec_from_file_location("stage924", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load Stage924 helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AuxHead(torch.nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int) -> None:
        super().__init__()
        if hidden_dim <= 0:
            self.net = torch.nn.Linear(input_dim, 1)
        else:
            self.net = torch.nn.Sequential(
                torch.nn.Linear(input_dim, hidden_dim),
                torch.nn.GELU(),
                torch.nn.Linear(hidden_dim, 1),
            )
        for module in self.modules():
            if isinstance(module, torch.nn.Linear):
                torch.nn.init.xavier_uniform_(module.weight)
                torch.nn.init.zeros_(module.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def iter_jsonl(path: Path):
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def rows_by_split(path: Path) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"train": [], "calibration": [], "eval": []}
    for row in iter_jsonl(path):
        out.setdefault(str(row.get("split")), []).append(row)
    return out


def positive_index(row: dict[str, Any]) -> int:
    positives = [int(i) for i in row.get("positive_candidate_indices", [])]
    return positives[0] if positives else -1


def candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def unique_docs(rows: list[dict[str, Any]]) -> list[str]:
    seen: dict[str, None] = {}
    for row in rows:
        for candidate in row.get("candidates", []) or []:
            seen.setdefault(str(candidate.get("doc_text", "") or ""), None)
    return list(seen)


def make_features(helper, base_model, row_index: int, row: dict[str, Any], query_cache, doc_cache, doc_to_index: dict[str, int]) -> torch.Tensor:
    candidates = list(row.get("candidates", []) or [])
    query = helper._embed_query_from_cache(base_model, query_cache, row_index)
    doc_indices = [doc_to_index[str(candidate.get("doc_text", "") or "")] for candidate in candidates]
    docs = helper._embed_docs_from_cache(base_model, doc_cache, doc_indices)
    q = query.expand_as(docs)
    scalars = torch.tensor(
        [
            [
                float(candidate.get("base_score", 0.0) or 0.0),
                float(candidate.get("partition_probability", 0.0) or 0.0),
                1.0 / max(1.0, float(candidate.get("rank", 9999) or 9999)),
            ]
            for candidate in candidates
        ],
        dtype=docs.dtype,
        device=docs.device,
    )
    return torch.cat([q, docs, q * docs, torch.abs(q - docs), scalars], dim=-1)


def training_pool(row: dict[str, Any], mode: str) -> tuple[list[int], int]:
    label = positive_index(row)
    if label < 0:
        return [], -1
    if mode == "all":
        return list(range(len(row.get("candidates", []) or []))), label
    if mode == "hard_entity_pair":
        pool = [label]
        pool.extend(int(i) for i in row.get("entity_pair_hard_negative_indices", []) if int(i) != label)
        pool = sorted(set(pool))
        return pool, pool.index(label)
    if mode == "hard_entity_pair_plus_base":
        pool = [label]
        pool.extend(int(i) for i in row.get("entity_pair_hard_negative_indices", []) if int(i) != label)
        base_top = min(
            range(len(row.get("candidates", []) or [])),
            key=lambda i: (-float(row["candidates"][i].get("base_score", 0.0) or 0.0), i),
        )
        pool.append(base_top)
        pool = sorted(set(pool))
        return pool, pool.index(label)
    raise ValueError(f"unsupported training_pool={mode}")


def score_split(helper, base_model, head, rows, query_cache, doc_cache, doc_to_index, alpha: float) -> dict[str, Any]:
    answer = exact = recoverable = selected_missing = 0
    mrr = 0.0
    with torch.no_grad():
        base_model.eval()
        head.eval()
        for row_index, row in enumerate(rows):
            candidates = list(row.get("candidates", []) or [])
            if not candidates:
                continue
            features = make_features(helper, base_model, row_index, row, query_cache, doc_cache, doc_to_index)
            head_scores = head(features).detach().cpu()
            base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates])
            scores = base_scores + float(alpha) * head_scores
            order = sorted(range(len(candidates)), key=lambda i: (-float(scores[i].item()), i))
            label = positive_index(row)
            if label >= 0:
                recoverable += 1
                mrr += 1.0 / float(order.index(label) + 1)
            if not order:
                selected_missing += 1
                continue
            ans, ex = candidate_hit(candidates[order[0]])
            answer += ans
            exact += ex
    total = len(rows)
    return {
        "rows": total,
        "answer": answer,
        "exact": exact,
        "recoverable": recoverable,
        "selected_missing": selected_missing,
        "mrr": mrr / float(total or 1),
        "alpha": float(alpha),
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    helper = _load_stage924()
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    repo_root = Path(args.repo_root).resolve()
    retrieval_eval = helper._load_retrieval_eval(repo_root)
    rows = rows_by_split(Path(args.targets_jsonl))
    base_model, tokenizer, _ = retrieval_eval._load_model(Path(args.bundle_dir).resolve(), repo_root=repo_root, device=device)
    for parameter in base_model.parameters():
        parameter.requires_grad_(False)

    query_texts = {split: [str(row.get("query_text", "") or "") for row in split_rows] for split, split_rows in rows.items()}
    docs = {split: unique_docs(split_rows) for split, split_rows in rows.items()}
    doc_to_index = {split: {doc: idx for idx, doc in enumerate(split_docs)} for split, split_docs in docs.items()}
    query_cache = {
        split: helper._make_text_cache(retrieval_eval, tokenizer, texts, max_tokens=int(args.max_query_tokens), device=device)
        for split, texts in query_texts.items()
    }
    doc_cache = {
        split: helper._make_text_cache(retrieval_eval, tokenizer, split_docs, max_tokens=int(args.max_doc_tokens), device=device)
        for split, split_docs in docs.items()
    }
    with torch.no_grad():
        embed_dim = int(helper._embed_query_from_cache(base_model, query_cache["train"], 0).shape[-1])
    head = AuxHead(embed_dim * 4 + 3, int(args.hidden_dim)).to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))

    train_rows = [row for row in rows["train"] if positive_index(row) >= 0]
    if not train_rows:
        raise ValueError("no train rows with positive relation qslot/value target")
    train_indices = [rows["train"].index(row) for row in train_rows]
    all_indices = list(range(len(train_rows)))
    best_state = None
    best_key = None
    history = []
    for step in range(1, int(args.steps) + 1):
        selected = random.choices(all_indices, k=int(args.rows_per_step))
        losses = []
        head.train()
        for pos in selected:
            row = train_rows[pos]
            row_index = train_indices[pos]
            pool, label = training_pool(row, str(args.training_pool))
            if label < 0 or len(pool) < 2:
                continue
            scores = head(make_features(helper, base_model, row_index, row, query_cache["train"], doc_cache["train"], doc_to_index["train"]))
            pool_tensor = torch.tensor(pool, dtype=torch.long, device=device)
            losses.append(F.cross_entropy(scores[pool_tensor].unsqueeze(0), torch.tensor([label], dtype=torch.long, device=device)))
        if not losses:
            continue
        loss = torch.stack(losses).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % int(args.eval_every) == 0:
            cal_scores = [
                score_split(helper, base_model, head, rows["calibration"], query_cache["calibration"], doc_cache["calibration"], doc_to_index["calibration"], alpha)
                for alpha in [float(x) for x in str(args.alpha_sweep).split(",") if x.strip()]
            ]
            selected_cal = max(cal_scores, key=lambda r: (r["answer"], r["exact"], r["mrr"]))
            history.append({"step": step, "loss": float(loss.detach().cpu().item()), "selected_calibration": selected_cal})
            key = (selected_cal["answer"], selected_cal["exact"], selected_cal["mrr"])
            if best_key is None or key > best_key:
                best_key = key
                best_state = {name: value.detach().cpu().clone() for name, value in head.state_dict().items()}
    if best_state is not None:
        head.load_state_dict(best_state)

    alphas = [float(x) for x in str(args.alpha_sweep).split(",") if x.strip()]
    calibration = [
        score_split(helper, base_model, head, rows["calibration"], query_cache["calibration"], doc_cache["calibration"], doc_to_index["calibration"], alpha)
        for alpha in alphas
    ]
    selected = max(calibration, key=lambda r: (r["answer"], r["exact"], r["mrr"]))
    eval_selected = score_split(helper, base_model, head, rows["eval"], query_cache["eval"], doc_cache["eval"], doc_to_index["eval"], float(selected["alpha"]))
    summary = {
        "artifact_kind": "stage951_relation_qslot_value_aux_head",
        "targets_jsonl": str(Path(args.targets_jsonl).resolve()),
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "hidden_dim": int(args.hidden_dim),
        "steps": int(args.steps),
        "rows_per_step": int(args.rows_per_step),
        "training_pool": str(args.training_pool),
        "history": history,
        "calibration_sweep": calibration,
        "calibration_selected": selected,
        "eval_with_calibration_selected": eval_selected,
        "stage944_relation_answer_exact": [52, 52],
        "stage944_nonrelation_answer_exact": [200, 183],
        "stage944_preserved_else_policy_answer_exact": [200 + eval_selected["answer"], 183 + eval_selected["exact"]],
        "decision_hint": "Frozen model query/doc embedding auxiliary. No qslot target, bridge suffix equality, or entity_pair flags are fed at eval.",
    }
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--targets-jsonl", default="runs/local/artifacts/stage950_relation_qslot_value_auxiliary_targets.jsonl")
    parser.add_argument("--bundle-dir", default="runs/local/artifacts/stage784_stage783_content_only_direct_n2048_steps320")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-query-tokens", type=int, default=128)
    parser.add_argument("--max-doc-tokens", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--steps", type=int, default=160)
    parser.add_argument("--rows-per-step", type=int, default=32)
    parser.add_argument("--eval-every", type=int, default=40)
    parser.add_argument("--training-pool", choices=["all", "hard_entity_pair", "hard_entity_pair_plus_base"], default="hard_entity_pair_plus_base")
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--alpha-sweep", default="0,0.005,0.01,0.015,0.02,0.025,0.03,0.04,0.05,0.075,0.1,0.15,0.2,0.3,0.5,0.75,1.0")
    parser.add_argument("--seed", type=int, default=951)
    parser.add_argument("--output-json", required=True)
    train(parser.parse_args())


if __name__ == "__main__":
    main()
