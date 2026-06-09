#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
import random
from typing import Any

import torch
import torch.nn.functional as F


def _load_stage926():
    path = Path(__file__).resolve().parent / "train_stage926_cached_residual_value_head.py"
    spec = importlib.util.spec_from_file_location("stage926", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load Stage926 helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MultiHeadValue(torch.nn.Module):
    def __init__(self, operations: list[str], input_dim: int, hidden_dim: int, residual_cls) -> None:
        super().__init__()
        self.heads = torch.nn.ModuleDict({op: residual_cls(input_dim, hidden_dim) for op in operations})

    def forward(self, operation: str, features: torch.Tensor) -> torch.Tensor:
        return self.heads[str(operation)](features)


def _score_split(stage926, helper, base_model, module, rows, query_cache, doc_cache, doc_to_index, alphas: dict[str, float] | None = None) -> dict[str, Any]:
    base_model.eval()
    module.eval()
    answer = exact = base_answer = base_exact = 0
    by_operation: dict[str, dict[str, int]] = {}
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            candidates = list(row.get("candidates", []) or [])
            if not candidates:
                continue
            op = str(row.get("operation", "") or "unknown")
            stats = by_operation.setdefault(op, {"examples": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0, "accepted_overrides": 0})
            stats["examples"] += 1
            head_scores = module(op, stage926._features(helper, base_model, row_index, row, query_cache, doc_cache, doc_to_index)).detach().cpu()
            base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates])
            alpha = 0.0 if alphas is None else float(alphas.get(op, 0.0))
            scores = head_scores if alphas is None else base_scores + alpha * head_scores
            order = sorted(range(len(candidates)), key=lambda idx: (-float(scores[idx].item()), idx))
            base_order = sorted(range(len(candidates)), key=lambda idx: (-float(base_scores[idx].item()), idx))
            top = candidates[order[0]]
            base_top = candidates[base_order[0]]
            top_answer = int(bool(top.get("is_exact") or top.get("is_answer_match")))
            top_exact = int(bool(top.get("is_exact")))
            base_top_answer = int(bool(base_top.get("is_exact") or base_top.get("is_answer_match")))
            base_top_exact = int(bool(base_top.get("is_exact")))
            answer += top_answer
            exact += top_exact
            base_answer += base_top_answer
            base_exact += base_top_exact
            stats["answer"] += top_answer
            stats["exact"] += top_exact
            stats["base_answer"] += base_top_answer
            stats["base_exact"] += base_top_exact
            stats["accepted_overrides"] += int(order[0] != base_order[0])
    return {
        "examples": len(rows),
        "answer_correct": answer,
        "exact_correct": exact,
        "base_answer_correct": base_answer,
        "base_exact_correct": base_exact,
        "by_operation": by_operation,
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    stage926 = _load_stage926()
    helper = stage926._load_stage924()
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    repo_root = Path(args.repo_root).resolve()
    retrieval_eval = helper._load_retrieval_eval(repo_root)
    rows = helper._rows_by_split(helper._iter_jsonl(Path(args.targets_jsonl)))
    teacher_targets = {}
    if str(args.teacher_policy_jsonl):
        for item in helper._iter_jsonl(Path(args.teacher_policy_jsonl)):
            teacher_targets[(str(item.get("split", "")), int(item.get("row_index", -1)))] = int(item.get("teacher_index", -1))
    operations = sorted({str(row.get("operation", "") or "unknown") for split_rows in rows.values() for row in split_rows})
    base_model, tokenizer, _ = retrieval_eval._load_model(Path(args.bundle_dir).resolve(), repo_root=repo_root, device=device)
    for parameter in base_model.parameters():
        parameter.requires_grad_(False)

    query_texts = {split: [str(row.get("query_text", "") or "") for row in split_rows] for split, split_rows in rows.items()}
    docs = {split: helper._unique_docs(split_rows) for split, split_rows in rows.items()}
    doc_to_index = {split: {doc: idx for idx, doc in enumerate(split_docs)} for split, split_docs in docs.items()}
    query_cache = {split: helper._make_text_cache(retrieval_eval, tokenizer, texts, max_tokens=int(args.max_query_tokens), device=device) for split, texts in query_texts.items()}
    doc_cache = {split: helper._make_text_cache(retrieval_eval, tokenizer, split_docs, max_tokens=int(args.max_doc_tokens), device=device) for split, split_docs in docs.items()}
    with torch.no_grad():
        embed_dim = int(helper._embed_query_from_cache(base_model, query_cache["train"], 0).shape[-1])
    module = MultiHeadValue(operations, embed_dim * 4 + 2, int(args.hidden_dim), stage926.ResidualHead).to(device)
    if str(args.init_module_state_pt):
        init_state = torch.load(str(args.init_module_state_pt), map_location=device)
        module.load_state_dict(init_state["module_state_dict"])
    preserve_module = None
    if float(args.preserve_weight) > 0.0:
        preserve_module = copy.deepcopy(module).to(device)
        preserve_module.eval()
        for parameter in preserve_module.parameters():
            parameter.requires_grad_(False)
    optimizer = torch.optim.AdamW(module.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))

    train_rows = [row for row in rows["train"] if stage926._label(list(row.get("candidates", []) or []), helper) >= 0]
    train_index_lookup = [rows["train"].index(row) for row in train_rows]
    by_operation: dict[str, list[int]] = {}
    for index, row in enumerate(train_rows):
        by_operation.setdefault(str(row.get("operation", "") or "unknown"), []).append(index)
    history = []
    best_state = None
    best_key = None
    for step in range(1, int(args.steps) + 1):
        selected = []
        per_operation = max(1, int(args.rows_per_step) // max(1, len(by_operation)))
        for op, indices in by_operation.items():
            selected.extend(random.choices(indices, k=per_operation))
        while len(selected) < int(args.rows_per_step):
            selected.append(random.randrange(len(train_rows)))
        random.shuffle(selected)
        losses = []
        module.train()
        for row_pos in selected[: int(args.rows_per_step)]:
            row = train_rows[row_pos]
            row_index = train_index_lookup[row_pos]
            candidates = list(row.get("candidates", []) or [])
            label = teacher_targets.get(("train", row_index), stage926._label(candidates, helper))
            if label < 0 or label >= len(candidates):
                label = stage926._label(candidates, helper)
            op = str(row.get("operation", "") or "unknown")
            features = stage926._features(helper, base_model, row_index, row, query_cache["train"], doc_cache["train"], doc_to_index["train"])
            scores = module(op, features)
            loss_item = F.cross_entropy(scores.unsqueeze(0), torch.tensor([label], dtype=torch.long, device=device))
            if preserve_module is not None:
                with torch.no_grad():
                    preserve_scores = preserve_module(op, features)
                    preserve_scores = preserve_scores - preserve_scores.mean()
                centered_scores = scores - scores.mean()
                loss_item = loss_item + float(args.preserve_weight) * F.mse_loss(centered_scores, preserve_scores)
            losses.append(loss_item)
        loss = torch.stack(losses).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % int(args.eval_every) == 0:
            calibration = _score_split(stage926, helper, base_model, module, rows["calibration"], query_cache["calibration"], doc_cache["calibration"], doc_to_index["calibration"], None)
            key = (calibration["answer_correct"], calibration["exact_correct"])
            history.append({"step": step, "loss": float(loss.detach().cpu().item()), "calibration_answer": calibration["answer_correct"], "calibration_exact": calibration["exact_correct"]})
            if best_key is None or key > best_key:
                best_key = key
                best_state = {name: value.detach().cpu().clone() for name, value in module.state_dict().items()}
    if best_state is not None:
        module.load_state_dict(best_state)

    alpha_grid = [float(item) for item in str(args.alpha_sweep).split(",") if item.strip()]
    selected_alphas = {}
    alpha_selection = {}
    for op in operations:
        best = None
        for alpha in alpha_grid:
            score = _score_split(stage926, helper, base_model, module, [row for row in rows["calibration"] if str(row.get("operation", "") or "unknown") == op], query_cache["calibration"], doc_cache["calibration"], doc_to_index["calibration"], {op: alpha})
            key = (score["answer_correct"], score["exact_correct"])
            if best is None or key > best[0]:
                best = (key, alpha, score)
        selected_alphas[op] = float(best[1])
        alpha_selection[op] = {"alpha": float(best[1]), "calibration": best[2]}

    fixed_alphas = json.loads(str(args.fixed_alphas_json)) if str(args.fixed_alphas_json) else None
    summary = {
        "artifact_kind": "stage935_multihead_value_module",
        "targets_jsonl": str(Path(args.targets_jsonl).resolve()),
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "operations": operations,
        "head_parameter_count": sum(p.numel() for p in module.parameters()),
        "hidden_dim": int(args.hidden_dim),
        "steps": int(args.steps),
        "rows_per_step": int(args.rows_per_step),
        "teacher_policy_jsonl": str(Path(args.teacher_policy_jsonl).resolve()) if str(args.teacher_policy_jsonl) else "",
        "teacher_policy_target_count": len(teacher_targets),
        "init_module_state_pt": str(Path(args.init_module_state_pt).resolve()) if str(args.init_module_state_pt) else "",
        "preserve_weight": float(args.preserve_weight),
        "fixed_alphas_json": fixed_alphas,
        "history": history,
        "selected_alphas": selected_alphas,
        "alpha_selection": alpha_selection,
        "train": _score_split(stage926, helper, base_model, module, rows["train"], query_cache["train"], doc_cache["train"], doc_to_index["train"], selected_alphas),
        "calibration": _score_split(stage926, helper, base_model, module, rows["calibration"], query_cache["calibration"], doc_cache["calibration"], doc_to_index["calibration"], selected_alphas),
        "eval": _score_split(stage926, helper, base_model, module, rows["eval"], query_cache["eval"], doc_cache["eval"], doc_to_index["eval"], selected_alphas),
        "stage933_frontier_answer_exact": [251, 234],
        "decision_hint": "One operation-routed multi-head residual module over frozen query/doc embeddings plus base/probability scalars. No suffix-similarity bridge features are input.",
    }
    if fixed_alphas is not None:
        summary["train_with_fixed_alphas"] = _score_split(stage926, helper, base_model, module, rows["train"], query_cache["train"], doc_cache["train"], doc_to_index["train"], fixed_alphas)
        summary["calibration_with_fixed_alphas"] = _score_split(stage926, helper, base_model, module, rows["calibration"], query_cache["calibration"], doc_cache["calibration"], doc_to_index["calibration"], fixed_alphas)
        summary["eval_with_fixed_alphas"] = _score_split(stage926, helper, base_model, module, rows["eval"], query_cache["eval"], doc_cache["eval"], doc_to_index["eval"], fixed_alphas)
    summary["implied_full_answer_exact"] = [summary["eval"]["answer_correct"] + 230, summary["eval"]["exact_correct"] + 229]
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
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--steps", type=int, default=160)
    parser.add_argument("--rows-per-step", type=int, default=32)
    parser.add_argument("--eval-every", type=int, default=40)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--alpha-sweep", default="0,0.01,0.025,0.05,0.075,0.1,0.15,0.2,0.3,0.5,0.75,1.0")
    parser.add_argument("--seed", type=int, default=935)
    parser.add_argument("--teacher-policy-jsonl", default="")
    parser.add_argument("--init-module-state-pt", default="")
    parser.add_argument("--preserve-weight", type=float, default=0.0)
    parser.add_argument("--fixed-alphas-json", default="")
    parser.add_argument("--output-json", required=True)
    train(parser.parse_args())


if __name__ == "__main__":
    main()
