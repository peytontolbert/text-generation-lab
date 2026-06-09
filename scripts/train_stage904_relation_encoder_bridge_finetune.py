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
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _rows_by_split(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out = {"train": [], "calibration": [], "eval": []}
    for row in rows:
        split = str(row.get("split", ""))
        if split in out:
            out[split].append(row)
    return out


def _label(candidates: list[dict[str, Any]]) -> int:
    for index, candidate in enumerate(candidates):
        if bool(candidate.get("is_exact")):
            return index
    for index, candidate in enumerate(candidates):
        if bool(candidate.get("is_answer_match")):
            return index
    return -1


def _embed_query(retrieval_eval, model, tokenizer, text: str, *, max_tokens: int, device: torch.device) -> torch.Tensor:
    ids, mask = retrieval_eval._encode_batch(tokenizer, [text], max_tokens=int(max_tokens), device=device)
    if hasattr(model, "retrieval_query_embedding"):
        keys = retrieval_eval._encode_key_batch([text], device=device)
        aux_keys = None
        if keys.ndim >= 3:
            aux_keys = keys[:, 1, :]
            keys = keys[:, 0, :]
        try:
            return model.retrieval_query_embedding(ids, mask, keys, aux_keys)
        except TypeError:
            try:
                return model.retrieval_query_embedding(ids, mask, keys)
            except TypeError:
                return model.retrieval_query_embedding(ids, mask)
    hidden = model.encode(ids, mask)
    return F.normalize(retrieval_eval._mean_pool(hidden, mask), dim=-1)


def _embed_docs(retrieval_eval, model, tokenizer, texts: list[str], *, max_tokens: int, device: torch.device) -> torch.Tensor:
    ids, mask = retrieval_eval._encode_batch(tokenizer, texts, max_tokens=int(max_tokens), device=device)
    if hasattr(model, "retrieval_doc_embedding"):
        keys = retrieval_eval._encode_key_batch(texts, device=device)
        aux_keys = None
        if keys.ndim >= 3:
            aux_keys = keys[:, 1, :]
            keys = keys[:, 0, :]
        try:
            return model.retrieval_doc_embedding(ids, mask, keys, aux_keys)
        except TypeError:
            try:
                return model.retrieval_doc_embedding(ids, mask, keys)
            except TypeError:
                return model.retrieval_doc_embedding(ids, mask)
    hidden = model.encode(ids, mask)
    return F.normalize(retrieval_eval._mean_pool(hidden, mask), dim=-1)


def _scores_for_row(
    retrieval_eval,
    model,
    tokenizer,
    row: dict[str, Any],
    *,
    max_query_tokens: int,
    max_doc_tokens: int,
    device: torch.device,
) -> torch.Tensor:
    candidates = list(row.get("candidates", []) or [])
    query = _embed_query(retrieval_eval, model, tokenizer, str(row.get("query_text", "") or ""), max_tokens=max_query_tokens, device=device)
    docs = _embed_docs(
        retrieval_eval,
        model,
        tokenizer,
        [str(candidate.get("doc_text", "") or "") for candidate in candidates],
        max_tokens=max_doc_tokens,
        device=device,
    )
    return (query.expand_as(docs) * docs).sum(dim=-1)


def _score_split(
    retrieval_eval,
    model,
    tokenizer,
    rows: list[dict[str, Any]],
    *,
    max_query_tokens: int,
    max_doc_tokens: int,
    device: torch.device,
) -> dict[str, Any]:
    model.eval()
    answer = exact = base_answer = base_exact = recoverable = 0
    mrr = 0.0
    with torch.no_grad():
        for row in rows:
            candidates = list(row.get("candidates", []) or [])
            if not candidates:
                continue
            scores = _scores_for_row(
                retrieval_eval,
                model,
                tokenizer,
                row,
                max_query_tokens=max_query_tokens,
                max_doc_tokens=max_doc_tokens,
                device=device,
            ).detach().cpu()
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


def _score_split_blend(
    retrieval_eval,
    model,
    tokenizer,
    rows: list[dict[str, Any]],
    *,
    max_query_tokens: int,
    max_doc_tokens: int,
    device: torch.device,
    alpha: float,
) -> dict[str, Any]:
    model.eval()
    answer = exact = 0
    mrr = 0.0
    with torch.no_grad():
        for row in rows:
            candidates = list(row.get("candidates", []) or [])
            if not candidates:
                continue
            model_scores = _scores_for_row(
                retrieval_eval,
                model,
                tokenizer,
                row,
                max_query_tokens=max_query_tokens,
                max_doc_tokens=max_doc_tokens,
                device=device,
            ).detach().cpu()
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
    retrieval_eval,
    model,
    tokenizer,
    rows: list[dict[str, Any]],
    *,
    max_query_tokens: int,
    max_doc_tokens: int,
    device: torch.device,
    alphas: list[float],
) -> dict[str, Any]:
    scored = [
        _score_split_blend(
            retrieval_eval,
            model,
            tokenizer,
            rows,
            max_query_tokens=max_query_tokens,
            max_doc_tokens=max_doc_tokens,
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
    model.train()

    trainable_names: list[str] = []
    for name, parameter in model.named_parameters():
        enabled = (
            "encoder" in name
            or "retrieval_query" in name
            or "retrieval_doc" in name
            or "retrieval_key" in name
        )
        parameter.requires_grad_(enabled)
        if enabled:
            trainable_names.append(name)
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=float(args.learning_rate),
        weight_decay=float(args.weight_decay),
    )
    train_rows = [row for row in rows["train"] if _label(list(row.get("candidates", []) or [])) >= 0]
    order = list(range(len(train_rows)))
    best_state = None
    best_key = None
    history = []
    for step in range(1, int(args.steps) + 1):
        random.shuffle(order)
        losses = []
        model.train()
        for row_id in order[: int(args.rows_per_step)]:
            row = train_rows[row_id]
            scores = _scores_for_row(
                retrieval_eval,
                model,
                tokenizer,
                row,
                max_query_tokens=int(args.max_query_tokens),
                max_doc_tokens=int(args.max_doc_tokens),
                device=device,
            )
            label = _label(list(row.get("candidates", []) or []))
            ce = F.cross_entropy(scores.unsqueeze(0), torch.tensor([label], dtype=torch.long, device=device))
            teacher = torch.tensor(
                [float(candidate.get("teacher_bridge_score", 0.0) or 0.0) for candidate in list(row.get("candidates", []) or [])],
                dtype=torch.float32,
                device=device,
            )
            teacher = teacher - teacher.mean()
            pred = scores - scores.mean()
            losses.append(ce + float(args.teacher_mse_weight) * F.mse_loss(pred, teacher))
        loss = torch.stack(losses).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % int(args.eval_every) == 0:
            calibration = _score_split(
                retrieval_eval,
                model,
                tokenizer,
                rows["calibration"],
                max_query_tokens=int(args.max_query_tokens),
                max_doc_tokens=int(args.max_doc_tokens),
                device=device,
            )
            history.append({"step": step, "loss": float(loss.detach().cpu().item()), "calibration_answer": calibration["answer_correct"], "calibration_exact": calibration["exact_correct"], "calibration_mrr": calibration["mrr"]})
            key = (calibration["answer_correct"], calibration["exact_correct"], calibration["mrr"])
            if best_key is None or key > best_key:
                best_key = key
                best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    alpha_values = [float(item) for item in str(args.alpha_sweep).split(",") if item.strip()]
    calibration_alpha = _alpha_sweep(
        retrieval_eval,
        model,
        tokenizer,
        rows["calibration"],
        max_query_tokens=int(args.max_query_tokens),
        max_doc_tokens=int(args.max_doc_tokens),
        device=device,
        alphas=alpha_values,
    )
    eval_alpha = _score_split_blend(
        retrieval_eval,
        model,
        tokenizer,
        rows["eval"],
        max_query_tokens=int(args.max_query_tokens),
        max_doc_tokens=int(args.max_doc_tokens),
        device=device,
        alpha=float(calibration_alpha["alpha"]),
    )
    summary = {
        "artifact_kind": "stage904_relation_encoder_bridge_finetune",
        "targets_jsonl": str(Path(args.targets_jsonl).resolve()),
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "trainable_parameter_count": sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad),
        "trainable_name_count": len(trainable_names),
        "steps": int(args.steps),
        "rows_per_step": int(args.rows_per_step),
        "teacher_mse_weight": float(args.teacher_mse_weight),
        "history": history,
        "train": _score_split(retrieval_eval, model, tokenizer, rows["train"], max_query_tokens=int(args.max_query_tokens), max_doc_tokens=int(args.max_doc_tokens), device=device),
        "calibration": _score_split(retrieval_eval, model, tokenizer, rows["calibration"], max_query_tokens=int(args.max_query_tokens), max_doc_tokens=int(args.max_doc_tokens), device=device),
        "eval": _score_split(retrieval_eval, model, tokenizer, rows["eval"], max_query_tokens=int(args.max_query_tokens), max_doc_tokens=int(args.max_doc_tokens), device=device),
        "calibration_selected_blend": calibration_alpha,
        "eval_with_calibration_selected_blend": eval_alpha,
        "decision_hint": "Fine-tunes encoder/retrieval parameters on same-collision relation candidates. Eval uses only model retrieval dot products, no external bridge similarity features.",
    }
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if str(args.output_pt or "").strip():
        torch.save({"state_dict": model.state_dict(), "summary": summary}, Path(args.output_pt))
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
    parser.add_argument("--steps", type=int, default=120)
    parser.add_argument("--rows-per-step", type=int, default=16)
    parser.add_argument("--eval-every", type=int, default=20)
    parser.add_argument("--learning-rate", type=float, default=0.0001)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--teacher-mse-weight", type=float, default=0.0)
    parser.add_argument("--alpha-sweep", default="0,0.01,0.025,0.05,0.075,0.1,0.15,0.2,0.3,0.5,0.75,1.0")
    parser.add_argument("--seed", type=int, default=904)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-pt", default="")
    train(parser.parse_args())


if __name__ == "__main__":
    main()
