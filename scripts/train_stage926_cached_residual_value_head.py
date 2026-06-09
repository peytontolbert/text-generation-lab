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


def _load_stage924():
    path = Path(__file__).resolve().parent / "train_stage924_cached_encoder_bridge_finetune.py"
    spec = importlib.util.spec_from_file_location("stage924", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load Stage924 helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ResidualHead(torch.nn.Module):
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


def _label(candidates: list[dict[str, Any]], helper) -> int:
    return helper._label(candidates)


def _operation_filter(raw: str) -> set[str]:
    return {item.strip() for item in str(raw or "").split(",") if item.strip()}


def _features(helper, base_model, row_index: int, row: dict[str, Any], query_cache, doc_cache, doc_to_index: dict[str, int]) -> torch.Tensor:
    candidates = list(row.get("candidates", []) or [])
    query = helper._embed_query_from_cache(base_model, query_cache, row_index)
    doc_indices = [doc_to_index[str(candidate.get("doc_text", "") or "")] for candidate in candidates]
    docs = helper._embed_docs_from_cache(base_model, doc_cache, doc_indices)
    q = query.expand_as(docs)
    scalars = torch.tensor(
        [
            [float(candidate.get("base_score", 0.0) or 0.0), float(candidate.get("partition_probability", 0.0) or 0.0)]
            for candidate in candidates
        ],
        dtype=docs.dtype,
        device=docs.device,
    )
    return torch.cat([q, docs, q * docs, torch.abs(q - docs), scalars], dim=-1)


def _training_indices(candidates: list[dict[str, Any]], label: int, mode: str) -> tuple[list[int], int]:
    if str(mode) == "all":
        return list(range(len(candidates))), int(label)
    if str(mode) != "label_base_top":
        raise ValueError(f"unsupported candidate_training_mode={mode}")
    base_scores = [float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates]
    base_order = sorted(range(len(candidates)), key=lambda idx: (-base_scores[idx], idx))
    indices = [int(label)]
    for idx in base_order:
        if idx != int(label):
            indices.append(int(idx))
            break
    if len(indices) == 1:
        return indices, 0
    return indices, 0


def _base_rank(candidates: list[dict[str, Any]], label: int) -> int | None:
    if label < 0:
        return None
    base_scores = [float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates]
    base_order = sorted(range(len(candidates)), key=lambda idx: (-base_scores[idx], idx))
    return int(base_order.index(int(label)) + 1)


def _score_split(helper, base_model, head, rows, query_cache, doc_cache, doc_to_index) -> dict[str, Any]:
    base_model.eval()
    head.eval()
    answer = exact = base_answer = base_exact = recoverable_answer = recoverable_exact = 0
    mrr = 0.0
    by_operation: dict[str, dict[str, int]] = {}
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            candidates = list(row.get("candidates", []) or [])
            if not candidates:
                continue
            operation = str(row.get("operation", "") or "unknown")
            stats = by_operation.setdefault(operation, {"examples": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0})
            stats["examples"] += 1
            scores = head(_features(helper, base_model, row_index, row, query_cache, doc_cache, doc_to_index)).detach().cpu()
            base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates])
            order = sorted(range(len(candidates)), key=lambda idx: (-float(scores[idx].item()), idx))
            base_order = sorted(range(len(candidates)), key=lambda idx: (-float(base_scores[idx].item()), idx))
            label = _label(candidates, helper)
            if label >= 0:
                mrr += 1.0 / float(order.index(label) + 1)
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
            recoverable_answer += int(any(bool(c.get("is_exact") or c.get("is_answer_match")) for c in candidates))
            recoverable_exact += int(any(bool(c.get("is_exact")) for c in candidates))
    total = len(rows)
    return {
        "examples": total,
        "answer_correct": answer,
        "exact_correct": exact,
        "base_answer_correct": base_answer,
        "base_exact_correct": base_exact,
        "answer_recoverable": recoverable_answer,
        "exact_recoverable": recoverable_exact,
        "mrr": mrr / float(total or 1),
        "by_operation": by_operation,
    }


def _score_split_blend(helper, base_model, head, rows, query_cache, doc_cache, doc_to_index, alpha: float) -> dict[str, Any]:
    base_model.eval()
    head.eval()
    answer = exact = 0
    mrr = 0.0
    by_operation: dict[str, dict[str, int]] = {}
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            candidates = list(row.get("candidates", []) or [])
            if not candidates:
                continue
            operation = str(row.get("operation", "") or "unknown")
            stats = by_operation.setdefault(operation, {"examples": 0, "answer": 0, "exact": 0})
            stats["examples"] += 1
            head_scores = head(_features(helper, base_model, row_index, row, query_cache, doc_cache, doc_to_index)).detach().cpu()
            base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates])
            scores = base_scores + float(alpha) * head_scores
            order = sorted(range(len(candidates)), key=lambda idx: (-float(scores[idx].item()), idx))
            label = _label(candidates, helper)
            if label >= 0:
                mrr += 1.0 / float(order.index(label) + 1)
            top = candidates[order[0]]
            top_answer = int(bool(top.get("is_exact") or top.get("is_answer_match")))
            top_exact = int(bool(top.get("is_exact")))
            answer += top_answer
            exact += top_exact
            stats["answer"] += top_answer
            stats["exact"] += top_exact
    total = len(rows)
    return {"examples": total, "answer_correct": answer, "exact_correct": exact, "mrr": mrr / float(total or 1), "alpha": float(alpha), "by_operation": by_operation}


def _candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return (
        int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))),
        int(bool(candidate.get("is_exact"))),
    )


def _write_predictions_jsonl(helper, base_model, head, rows_by_split, query_cache, doc_cache, doc_to_index, alpha: float, output_path: str) -> None:
    if not output_path:
        return
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    base_model.eval()
    head.eval()
    with output.open("w", encoding="utf-8") as handle:
        with torch.no_grad():
            for split, rows in rows_by_split.items():
                for row_index, row in enumerate(rows):
                    candidates = list(row.get("candidates", []) or [])
                    if not candidates:
                        continue
                    head_scores = head(_features(helper, base_model, row_index, row, query_cache[split], doc_cache[split], doc_to_index[split])).detach().cpu()
                    base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates])
                    blend_scores = base_scores + float(alpha) * head_scores
                    base_order = sorted(range(len(candidates)), key=lambda idx: (-float(base_scores[idx].item()), idx))
                    blend_order = sorted(range(len(candidates)), key=lambda idx: (-float(blend_scores[idx].item()), idx))
                    label = _label(candidates, helper)
                    base_top_idx = int(base_order[0])
                    blend_top_idx = int(blend_order[0])
                    base_answer, base_exact = _candidate_hit(candidates[base_top_idx])
                    blend_answer, blend_exact = _candidate_hit(candidates[blend_top_idx])
                    label_rank_base = int(base_order.index(label) + 1) if label >= 0 else None
                    label_rank_blend = int(blend_order.index(label) + 1) if label >= 0 else None
                    record = {
                        "split": split,
                        "row_index": row_index,
                        "query_index": row.get("query_index"),
                        "operation": str(row.get("operation", "") or "unknown"),
                        "alpha": float(alpha),
                        "label_index": label,
                        "label_rank_base": label_rank_base,
                        "label_rank_blend": label_rank_blend,
                        "base_top_index": base_top_idx,
                        "blend_top_index": blend_top_idx,
                        "base_top_answer": base_answer,
                        "base_top_exact": base_exact,
                        "blend_top_answer": blend_answer,
                        "blend_top_exact": blend_exact,
                        "query_text": str(row.get("query_text", "") or ""),
                        "base_top_doc_text": str(candidates[base_top_idx].get("doc_text", "") or ""),
                        "blend_top_doc_text": str(candidates[blend_top_idx].get("doc_text", "") or ""),
                        "label_doc_text": str(candidates[label].get("doc_text", "") or "") if label >= 0 else "",
                        "base_top_base_score": float(base_scores[base_top_idx].item()),
                        "blend_top_base_score": float(base_scores[blend_top_idx].item()),
                        "base_top_head_score": float(head_scores[base_top_idx].item()),
                        "blend_top_head_score": float(head_scores[blend_top_idx].item()),
                        "base_top_blend_score": float(blend_scores[base_top_idx].item()),
                        "blend_top_blend_score": float(blend_scores[blend_top_idx].item()),
                    }
                    handle.write(json.dumps(record, sort_keys=True) + "\n")


def _write_full_scores_jsonl(helper, base_model, head, rows_by_split, query_cache, doc_cache, doc_to_index, alpha: float, output_path: str) -> None:
    if not output_path:
        return
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    base_model.eval()
    head.eval()
    with output.open("w", encoding="utf-8") as handle:
        with torch.no_grad():
            for split, rows in rows_by_split.items():
                for row_index, row in enumerate(rows):
                    candidates = list(row.get("candidates", []) or [])
                    if not candidates:
                        continue
                    head_scores = head(_features(helper, base_model, row_index, row, query_cache[split], doc_cache[split], doc_to_index[split])).detach().cpu()
                    base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates])
                    blend_scores = base_scores + float(alpha) * head_scores
                    label = _label(candidates, helper)
                    handle.write(json.dumps({
                        "split": split,
                        "row_index": row_index,
                        "query_index": row.get("query_index"),
                        "operation": str(row.get("operation", "") or "unknown"),
                        "alpha": float(alpha),
                        "label_index": label,
                        "base_scores": [float(x) for x in base_scores.tolist()],
                        "head_scores": [float(x) for x in head_scores.tolist()],
                        "blend_scores": [float(x) for x in blend_scores.tolist()],
                    }, sort_keys=True) + "\n")


def train(args: argparse.Namespace) -> dict[str, Any]:
    helper = _load_stage924()
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    repo_root = Path(args.repo_root).resolve()
    retrieval_eval = helper._load_retrieval_eval(repo_root)
    rows = helper._rows_by_split(helper._iter_jsonl(Path(args.targets_jsonl)))
    base_model, tokenizer, _ = retrieval_eval._load_model(Path(args.bundle_dir).resolve(), repo_root=repo_root, device=device)
    for name, parameter in base_model.named_parameters():
        enabled = bool(args.train_encoder) and ("encoder" in name or "retrieval_query" in name or "retrieval_doc" in name or "retrieval_key" in name)
        parameter.requires_grad_(enabled)

    query_texts = {split: [str(row.get("query_text", "") or "") for row in split_rows] for split, split_rows in rows.items()}
    docs = {split: helper._unique_docs(split_rows) for split, split_rows in rows.items()}
    doc_to_index = {split: {doc: idx for idx, doc in enumerate(split_docs)} for split, split_docs in docs.items()}
    query_cache = {split: helper._make_text_cache(retrieval_eval, tokenizer, texts, max_tokens=int(args.max_query_tokens), device=device) for split, texts in query_texts.items()}
    doc_cache = {split: helper._make_text_cache(retrieval_eval, tokenizer, split_docs, max_tokens=int(args.max_doc_tokens), device=device) for split, split_docs in docs.items()}
    embed_dim = int(query_cache["train"]["ids"].shape[-1])  # placeholder overwritten after one embed
    with torch.no_grad():
        sample = helper._embed_query_from_cache(base_model, query_cache["train"], 0)
        embed_dim = int(sample.shape[-1])
    head = ResidualHead(embed_dim * 4 + 2, int(args.hidden_dim)).to(device)
    params = list(head.parameters()) + [p for p in base_model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params, lr=float(args.learning_rate), weight_decay=float(args.weight_decay))

    include_train_operations = _operation_filter(str(args.include_train_operations))
    train_rows = []
    for row in rows["train"]:
        candidates = list(row.get("candidates", []) or [])
        label = _label(candidates, helper)
        rank = _base_rank(candidates, label)
        if label < 0:
            continue
        if include_train_operations and str(row.get("operation", "") or "unknown") not in include_train_operations:
            continue
        if int(args.train_label_base_rank_min) > 0 and (rank is None or rank < int(args.train_label_base_rank_min)):
            continue
        if int(args.train_label_base_rank_max) > 0 and (rank is None or rank > int(args.train_label_base_rank_max)):
            continue
        train_rows.append(row)
    if not train_rows:
        raise ValueError(f"no train rows matched include_train_operations={sorted(include_train_operations)}")
    train_index_lookup = [rows["train"].index(row) for row in train_rows]
    by_operation: dict[str, list[int]] = {}
    for index, row in enumerate(train_rows):
        by_operation.setdefault(str(row.get("operation", "") or "unknown"), []).append(index)
    operations = sorted(by_operation)
    all_indices = list(range(len(train_rows)))
    best_state = None
    best_key = None
    history = []
    for step in range(1, int(args.steps) + 1):
        if bool(args.operation_balanced_sampling):
            selected = []
            per_operation = max(1, int(args.rows_per_step) // max(1, len(operations)))
            for operation in operations:
                selected.extend(random.choices(by_operation[operation], k=per_operation))
            while len(selected) < int(args.rows_per_step):
                selected.append(random.choice(all_indices))
            random.shuffle(selected)
            step_rows = selected[: int(args.rows_per_step)]
        else:
            random.shuffle(all_indices)
            step_rows = all_indices[: int(args.rows_per_step)]
        base_model.train(bool(args.train_encoder))
        head.train()
        losses = []
        for row_pos in step_rows:
            row = train_rows[row_pos]
            row_index = train_index_lookup[row_pos]
            candidates = list(row.get("candidates", []) or [])
            label = _label(candidates, helper)
            training_indices, training_label = _training_indices(candidates, label, str(args.candidate_training_mode))
            scores = head(_features(helper, base_model, row_index, row, query_cache["train"], doc_cache["train"], doc_to_index["train"]))
            scores_for_loss = scores[torch.tensor(training_indices, dtype=torch.long, device=device)]
            ce = F.cross_entropy(scores_for_loss.unsqueeze(0), torch.tensor([training_label], dtype=torch.long, device=device))
            teacher = torch.tensor([float(candidates[idx].get(str(args.teacher_score_field), 0.0) or 0.0) for idx in training_indices], dtype=torch.float32, device=device)
            teacher = teacher - teacher.mean()
            pred = scores_for_loss - scores_for_loss.mean()
            losses.append(ce + float(args.teacher_mse_weight) * F.mse_loss(pred, teacher))
        loss = torch.stack(losses).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % int(args.eval_every) == 0:
            calibration = _score_split(helper, base_model, head, rows["calibration"], query_cache["calibration"], doc_cache["calibration"], doc_to_index["calibration"])
            history.append({"step": step, "loss": float(loss.detach().cpu().item()), "calibration_answer": calibration["answer_correct"], "calibration_exact": calibration["exact_correct"], "calibration_mrr": calibration["mrr"]})
            key = (calibration["answer_correct"], calibration["exact_correct"], calibration["mrr"])
            if best_key is None or key > best_key:
                best_key = key
                best_state = {
                    "base": {name: value.detach().cpu().clone() for name, value in base_model.state_dict().items()},
                    "head": {name: value.detach().cpu().clone() for name, value in head.state_dict().items()},
                }
    if best_state is not None:
        base_model.load_state_dict(best_state["base"])
        head.load_state_dict(best_state["head"])
    alphas = [float(item) for item in str(args.alpha_sweep).split(",") if item.strip()]
    calibration_blends = [_score_split_blend(helper, base_model, head, rows["calibration"], query_cache["calibration"], doc_cache["calibration"], doc_to_index["calibration"], alpha) for alpha in alphas]
    selected_alpha = max(calibration_blends, key=lambda item: (item["answer_correct"], item["exact_correct"], item["mrr"]))
    summary = {
        "artifact_kind": str(args.artifact_kind),
        "status": str(args.status),
        "targets_jsonl": str(Path(args.targets_jsonl).resolve()),
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "train_encoder": bool(args.train_encoder),
        "head_parameter_count": sum(p.numel() for p in head.parameters()),
        "trainable_encoder_parameter_count": sum(p.numel() for p in base_model.parameters() if p.requires_grad),
        "hidden_dim": int(args.hidden_dim),
        "steps": int(args.steps),
        "rows_per_step": int(args.rows_per_step),
        "include_train_operations": sorted(include_train_operations),
        "candidate_training_mode": str(args.candidate_training_mode),
        "train_label_base_rank_min": int(args.train_label_base_rank_min),
        "train_label_base_rank_max": int(args.train_label_base_rank_max),
        "operation_balanced_sampling": bool(args.operation_balanced_sampling),
        "teacher_mse_weight": float(args.teacher_mse_weight),
        "teacher_score_field": str(args.teacher_score_field),
        "history": history,
        "train": _score_split(helper, base_model, head, rows["train"], query_cache["train"], doc_cache["train"], doc_to_index["train"]),
        "calibration": _score_split(helper, base_model, head, rows["calibration"], query_cache["calibration"], doc_cache["calibration"], doc_to_index["calibration"]),
        "eval": _score_split(helper, base_model, head, rows["eval"], query_cache["eval"], doc_cache["eval"], doc_to_index["eval"]),
        "calibration_selected_blend": selected_alpha,
        "eval_with_calibration_selected_blend": _score_split_blend(helper, base_model, head, rows["eval"], query_cache["eval"], doc_cache["eval"], doc_to_index["eval"], float(selected_alpha["alpha"])),
        "decision_hint": "Residual/value head over query/doc embeddings and base/probability scalars. No suffix-similarity bridge features are input."
    }
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if str(args.output_state_pt):
        state_output = Path(args.output_state_pt)
        state_output.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "artifact_kind": "stage926_cached_residual_value_head_state",
                "summary": summary,
                "head_state_dict": {name: value.detach().cpu() for name, value in head.state_dict().items()},
                "head_input_dim": int(embed_dim * 4 + 2),
                "hidden_dim": int(args.hidden_dim),
                "selected_alpha": float(selected_alpha["alpha"]),
                "include_train_operations": sorted(include_train_operations),
                "candidate_training_mode": str(args.candidate_training_mode),
            },
            state_output,
        )
    _write_predictions_jsonl(
        helper,
        base_model,
        head,
        rows,
        query_cache,
        doc_cache,
        doc_to_index,
        float(selected_alpha["alpha"]),
        str(args.output_predictions_jsonl),
    )
    _write_full_scores_jsonl(
        helper,
        base_model,
        head,
        rows,
        query_cache,
        doc_cache,
        doc_to_index,
        float(selected_alpha["alpha"]),
        str(args.output_full_scores_jsonl),
    )
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
    parser.add_argument("--include-train-operations", default="")
    parser.add_argument("--candidate-training-mode", choices=["all", "label_base_top"], default="all")
    parser.add_argument("--train-label-base-rank-min", type=int, default=0)
    parser.add_argument("--train-label-base-rank-max", type=int, default=0)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--teacher-mse-weight", type=float, default=0.0)
    parser.add_argument("--teacher-score-field", default="teacher_bridge_score")
    parser.add_argument("--artifact-kind", default="stage926_cached_residual_value_head")
    parser.add_argument("--status", default="completed_cached_residual_value_head")
    parser.add_argument("--operation-balanced-sampling", action="store_true")
    parser.add_argument("--train-encoder", action="store_true")
    parser.add_argument("--alpha-sweep", default="0,0.01,0.025,0.05,0.075,0.1,0.15,0.2,0.3,0.5,0.75,1.0")
    parser.add_argument("--seed", type=int, default=926)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-predictions-jsonl", default="")
    parser.add_argument("--output-full-scores-jsonl", default="")
    parser.add_argument("--output-state-pt", default="")
    train(parser.parse_args())


if __name__ == "__main__":
    main()
