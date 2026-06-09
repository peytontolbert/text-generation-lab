#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import random
import shutil
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


def _load_runtime_checkpoint(repo_root: Path):
    runtime_root = repo_root / "other_repos" / "model-stack"
    if str(runtime_root) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(runtime_root))
    from runtime.checkpoint import save_pretrained

    return save_pretrained


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


def _filter_rows_by_operation(rows: dict[str, list[dict[str, Any]]], operation_filter: str) -> dict[str, list[dict[str, Any]]]:
    allowed = {item.strip() for item in str(operation_filter).split(",") if item.strip()}
    if not allowed:
        return rows
    return {split: [row for row in split_rows if str(row.get("operation", "") or "") in allowed] for split, split_rows in rows.items()}


def _label(candidates: list[dict[str, Any]]) -> int:
    for index, candidate in enumerate(candidates):
        if bool(candidate.get("is_exact")):
            return index
    for index, candidate in enumerate(candidates):
        if bool(candidate.get("is_answer_match")):
            return index
    return -1


def _unique_docs(rows: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for candidate in list(row.get("candidates", []) or []):
            text = str(candidate.get("doc_text", "") or "")
            if text and text not in seen:
                seen.add(text)
                out.append(text)
    return out


def _split_keys(keys: torch.Tensor) -> tuple[torch.Tensor | None, torch.Tensor | None]:
    if keys.ndim >= 3:
        return keys[:, 0, :], keys[:, 1, :]
    return keys, None


def _embed_query_from_cache(model, cache: dict[str, torch.Tensor], index: int) -> torch.Tensor:
    ids = cache["ids"][index : index + 1]
    mask = cache["mask"][index : index + 1]
    keys = cache.get("keys")
    aux = cache.get("aux_keys")
    if hasattr(model, "retrieval_query_embedding"):
        try:
            return model.retrieval_query_embedding(ids, mask, None if keys is None else keys[index : index + 1], None if aux is None else aux[index : index + 1])
        except TypeError:
            try:
                return model.retrieval_query_embedding(ids, mask, None if keys is None else keys[index : index + 1])
            except TypeError:
                return model.retrieval_query_embedding(ids, mask)
    hidden = model.encode(ids, mask)
    return F.normalize((hidden * mask.unsqueeze(-1)).sum(dim=1) / mask.sum(dim=1, keepdim=True).clamp_min(1), dim=-1)


def _embed_docs_from_cache(model, cache: dict[str, torch.Tensor], indices: list[int]) -> torch.Tensor:
    idx = torch.tensor(indices, dtype=torch.long, device=cache["ids"].device)
    ids = cache["ids"].index_select(0, idx)
    mask = cache["mask"].index_select(0, idx)
    keys = cache.get("keys")
    aux = cache.get("aux_keys")
    if hasattr(model, "retrieval_doc_embedding"):
        try:
            return model.retrieval_doc_embedding(ids, mask, None if keys is None else keys.index_select(0, idx), None if aux is None else aux.index_select(0, idx))
        except TypeError:
            try:
                return model.retrieval_doc_embedding(ids, mask, None if keys is None else keys.index_select(0, idx))
            except TypeError:
                return model.retrieval_doc_embedding(ids, mask)
    hidden = model.encode(ids, mask)
    return F.normalize((hidden * mask.unsqueeze(-1)).sum(dim=1) / mask.sum(dim=1, keepdim=True).clamp_min(1), dim=-1)


def _make_text_cache(retrieval_eval, tokenizer, texts: list[str], *, max_tokens: int, device: torch.device) -> dict[str, torch.Tensor]:
    ids, mask = retrieval_eval._encode_batch(tokenizer, texts, max_tokens=int(max_tokens), device=device)
    keys, aux = _split_keys(retrieval_eval._encode_key_batch(texts, device=device))
    return {"ids": ids, "mask": mask, "keys": keys, "aux_keys": aux}


def _score_row(model, row_index: int, row: dict[str, Any], query_cache: dict[str, torch.Tensor], doc_cache: dict[str, torch.Tensor], doc_to_index: dict[str, int]) -> torch.Tensor:
    candidates = list(row.get("candidates", []) or [])
    query = _embed_query_from_cache(model, query_cache, row_index)
    doc_indices = [doc_to_index[str(candidate.get("doc_text", "") or "")] for candidate in candidates]
    docs = _embed_docs_from_cache(model, doc_cache, doc_indices)
    return (query.expand_as(docs) * docs).sum(dim=-1)


def _score_split(model, rows: list[dict[str, Any]], query_cache: dict[str, torch.Tensor], doc_cache: dict[str, torch.Tensor], doc_to_index: dict[str, int]) -> dict[str, Any]:
    model.eval()
    answer = exact = base_answer = base_exact = recoverable_answer = recoverable_exact = 0
    mrr = 0.0
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            candidates = list(row.get("candidates", []) or [])
            if not candidates:
                continue
            scores = _score_row(model, row_index, row, query_cache, doc_cache, doc_to_index).detach().cpu()
            base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates])
            order = sorted(range(len(candidates)), key=lambda idx: (-float(scores[idx].item()), idx))
            base_order = sorted(range(len(candidates)), key=lambda idx: (-float(base_scores[idx].item()), idx))
            label = _label(candidates)
            if label >= 0:
                mrr += 1.0 / float(order.index(label) + 1)
            top = candidates[order[0]]
            base_top = candidates[base_order[0]]
            answer += int(bool(top.get("is_exact") or top.get("is_answer_match")))
            exact += int(bool(top.get("is_exact")))
            base_answer += int(bool(base_top.get("is_exact") or base_top.get("is_answer_match")))
            base_exact += int(bool(base_top.get("is_exact")))
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
    }


def _score_split_blend(model, rows: list[dict[str, Any]], query_cache: dict[str, torch.Tensor], doc_cache: dict[str, torch.Tensor], doc_to_index: dict[str, int], alpha: float) -> dict[str, Any]:
    model.eval()
    answer = exact = 0
    mrr = 0.0
    by_operation: dict[str, dict[str, int]] = {}
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            candidates = list(row.get("candidates", []) or [])
            if not candidates:
                continue
            operation = str(row.get("operation", "") or "unknown")
            stats = by_operation.setdefault(operation, {"rows": 0, "answer_correct": 0, "exact_correct": 0})
            stats["rows"] += 1
            model_scores = _score_row(model, row_index, row, query_cache, doc_cache, doc_to_index).detach().cpu()
            base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates])
            scores = base_scores + float(alpha) * model_scores
            order = sorted(range(len(candidates)), key=lambda idx: (-float(scores[idx].item()), idx))
            label = _label(candidates)
            if label >= 0:
                mrr += 1.0 / float(order.index(label) + 1)
            top = candidates[order[0]]
            ans = int(bool(top.get("is_exact") or top.get("is_answer_match")))
            ex = int(bool(top.get("is_exact")))
            answer += ans
            exact += ex
            stats["answer_correct"] += ans
            stats["exact_correct"] += ex
    total = len(rows)
    return {
        "examples": total,
        "answer_correct": answer,
        "exact_correct": exact,
        "mrr": mrr / float(total or 1),
        "alpha": float(alpha),
        "by_operation": by_operation,
    }


def _copy_tokenizer_from_manifest(source_manifest: dict[str, Any], source_bundle_dir: Path, output_tokenizer_dir: Path) -> str | None:
    tokenizer_dir = source_manifest.get("tokenizer_dir")
    if not tokenizer_dir:
        return None
    source_tokenizer_dir = Path(str(tokenizer_dir))
    if not source_tokenizer_dir.is_absolute():
        source_tokenizer_dir = source_bundle_dir / source_tokenizer_dir
    if not source_tokenizer_dir.exists():
        return None
    output_tokenizer_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_tokenizer_dir, output_tokenizer_dir, dirs_exist_ok=True)
    return str(source_tokenizer_dir.resolve())


def _model_config(model):
    for attr in ("cfg", "config"):
        if hasattr(model, attr):
            return getattr(model, attr)
    raise RuntimeError("loaded model does not expose cfg/config needed for save_pretrained")


def _save_loadable_bundle(
    *,
    repo_root: Path,
    source_bundle_dir: Path,
    output_bundle_dir: Path,
    model,
    tokenizer,
    source_manifest: dict[str, Any],
    parameter_count: int,
    training_summary: dict[str, Any],
) -> dict[str, Any]:
    save_pretrained = _load_runtime_checkpoint(repo_root)
    output_bundle_dir.mkdir(parents=True, exist_ok=True)
    model_dir = output_bundle_dir / "model"
    tokenizer_dir = output_bundle_dir / "tokenizer"
    source_tokenizer_dir = _copy_tokenizer_from_manifest(source_manifest, source_bundle_dir, tokenizer_dir)
    if source_tokenizer_dir is None and hasattr(tokenizer, "save_pretrained"):
        tokenizer_dir.mkdir(parents=True, exist_ok=True)
        tokenizer.save_pretrained(str(tokenizer_dir))
        source_tokenizer_dir = "tokenizer.save_pretrained"

    model_cpu = model.eval().cpu()
    save_pretrained(model_cpu, _model_config(model_cpu), model_dir)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "bundle_kind": "agentkernel_lite_encdec",
            "model_dir": str(model_dir.resolve()),
            "tokenizer_dir": str(tokenizer_dir.resolve()),
            "parameter_count": int(parameter_count),
            "training_summary": training_summary,
            "source_bundle_dir": str(source_bundle_dir.resolve()),
            "source_tokenizer_dir": source_tokenizer_dir,
        }
    )
    manifest_path = output_bundle_dir / "agentkernel_lite_encdec_manifest.json"
    manifest["manifest_path"] = str(manifest_path.resolve())
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "bundle_dir": str(output_bundle_dir.resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "model_dir": str(model_dir.resolve()),
        "tokenizer_dir": str(tokenizer_dir.resolve()),
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    repo_root = Path(args.repo_root).resolve()
    retrieval_eval = _load_retrieval_eval(repo_root)
    rows = _filter_rows_by_operation(_rows_by_split(_iter_jsonl(Path(args.targets_jsonl))), str(args.operation_filter))
    bundle_dir = Path(args.bundle_dir).resolve()
    source_manifest_path = bundle_dir / "agentkernel_lite_encdec_manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8")) if source_manifest_path.exists() else {}
    model, tokenizer, manifest = retrieval_eval._load_model(bundle_dir, repo_root=repo_root, device=device)
    for name, parameter in model.named_parameters():
        parameter.requires_grad_("encoder" in name or "retrieval_query" in name or "retrieval_doc" in name or "retrieval_key" in name)
    trainable_parameter_count = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=float(args.learning_rate), weight_decay=float(args.weight_decay))

    query_texts = {split: [str(row.get("query_text", "") or "") for row in split_rows] for split, split_rows in rows.items()}
    docs = {split: _unique_docs(split_rows) for split, split_rows in rows.items()}
    doc_to_index = {split: {doc: idx for idx, doc in enumerate(split_docs)} for split, split_docs in docs.items()}
    query_cache = {split: _make_text_cache(retrieval_eval, tokenizer, texts, max_tokens=int(args.max_query_tokens), device=device) for split, texts in query_texts.items()}
    doc_cache = {split: _make_text_cache(retrieval_eval, tokenizer, split_docs, max_tokens=int(args.max_doc_tokens), device=device) for split, split_docs in docs.items()}

    train_rows = [row for row in rows["train"] if _label(list(row.get("candidates", []) or [])) >= 0]
    train_index_lookup = [rows["train"].index(row) for row in train_rows]
    order = list(range(len(train_rows)))
    by_operation: dict[str, list[int]] = {}
    for index, row in enumerate(train_rows):
        by_operation.setdefault(str(row.get("operation", "") or "unknown"), []).append(index)
    operations = sorted(by_operation)
    history = []
    best_state = None
    best_key = None
    for step in range(1, int(args.steps) + 1):
        if bool(args.operation_balanced_sampling):
            selected: list[int] = []
            per_operation = max(1, int(args.rows_per_step) // max(1, len(operations)))
            for operation in operations:
                selected.extend(random.choices(by_operation[operation], k=per_operation))
            while len(selected) < int(args.rows_per_step):
                selected.append(random.choice(order))
            random.shuffle(selected)
            step_rows = selected[: int(args.rows_per_step)]
        else:
            random.shuffle(order)
            step_rows = order[: int(args.rows_per_step)]
        losses = []
        model.train()
        for row_pos in step_rows:
            row = train_rows[row_pos]
            row_index = train_index_lookup[row_pos]
            candidates = list(row.get("candidates", []) or [])
            scores = _score_row(model, row_index, row, query_cache["train"], doc_cache["train"], doc_to_index["train"])
            label = _label(candidates)
            ce = F.cross_entropy(scores.unsqueeze(0), torch.tensor([label], dtype=torch.long, device=device))
            teacher = torch.tensor([float(candidate.get("teacher_bridge_score", 0.0) or 0.0) for candidate in candidates], dtype=torch.float32, device=device)
            teacher = teacher - teacher.mean()
            pred = scores - scores.mean()
            losses.append(float(args.candidate_ce_weight) * ce + float(args.teacher_mse_weight) * F.mse_loss(pred, teacher))
        loss = torch.stack(losses).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % int(args.eval_every) == 0:
            calibration = _score_split(model, rows["calibration"], query_cache["calibration"], doc_cache["calibration"], doc_to_index["calibration"])
            history.append({"step": step, "loss": float(loss.detach().cpu().item()), "calibration_answer": calibration["answer_correct"], "calibration_exact": calibration["exact_correct"], "calibration_mrr": calibration["mrr"]})
            key = (calibration["answer_correct"], calibration["exact_correct"], calibration["mrr"])
            if best_key is None or key > best_key:
                best_key = key
                best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    alphas = [float(item) for item in str(args.alpha_sweep).split(",") if item.strip()]
    calibration_blends = [_score_split_blend(model, rows["calibration"], query_cache["calibration"], doc_cache["calibration"], doc_to_index["calibration"], alpha) for alpha in alphas]
    calibration_selected = max(calibration_blends, key=lambda item: (item["answer_correct"], item["exact_correct"], item["mrr"]))
    eval_blend = _score_split_blend(model, rows["eval"], query_cache["eval"], doc_cache["eval"], doc_to_index["eval"], float(calibration_selected["alpha"]))
    summary = {
        "artifact_kind": "stage924_cached_encoder_bridge_finetune",
        "targets_jsonl": str(Path(args.targets_jsonl).resolve()),
        "bundle_dir": str(bundle_dir),
        "trainable_parameter_count": int(trainable_parameter_count),
        "steps": int(args.steps),
        "rows_per_step": int(args.rows_per_step),
        "operation_balanced_sampling": bool(args.operation_balanced_sampling),
        "operation_filter": str(args.operation_filter),
        "operations": operations,
        "teacher_mse_weight": float(args.teacher_mse_weight),
        "candidate_ce_weight": float(args.candidate_ce_weight),
        "history": history,
        "train": _score_split(model, rows["train"], query_cache["train"], doc_cache["train"], doc_to_index["train"]),
        "calibration": _score_split(model, rows["calibration"], query_cache["calibration"], doc_cache["calibration"], doc_to_index["calibration"]),
        "eval": _score_split(model, rows["eval"], query_cache["eval"], doc_cache["eval"], doc_to_index["eval"]),
        "calibration_selected_blend": calibration_selected,
        "eval_with_calibration_selected_blend": eval_blend,
        "decision_hint": "Caches tokenized query/doc candidate groups, then fine-tunes encoder/retrieval parameters with candidate CE plus optional bridge-teacher MSE. Eval uses raw model scores or base+alpha*model residual, no suffix-similarity features."
    }
    if str(args.save_best_state_pt or "").strip():
        state_path = Path(args.save_best_state_pt)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"state_dict": model.state_dict(), "summary": summary}, state_path)
        summary["saved_best_state_pt"] = str(state_path.resolve())
    if str(args.save_best_bundle_dir or "").strip():
        saved_bundle = _save_loadable_bundle(
            repo_root=repo_root,
            source_bundle_dir=bundle_dir,
            output_bundle_dir=Path(args.save_best_bundle_dir),
            model=model,
            tokenizer=tokenizer,
            source_manifest=source_manifest or manifest,
            parameter_count=sum(parameter.numel() for parameter in model.parameters()),
            training_summary={
                "stage": "stage976_loadable_stage975_pair_teacher",
                "source_summary": str(Path(args.output_json).resolve()),
                "targets_jsonl": str(Path(args.targets_jsonl).resolve()),
                "steps": int(args.steps),
                "rows_per_step": int(args.rows_per_step),
                "teacher_mse_weight": float(args.teacher_mse_weight),
                "candidate_ce_weight": float(args.candidate_ce_weight),
                "operation_balanced_sampling": bool(args.operation_balanced_sampling),
                "calibration_selected_blend": calibration_selected,
                "eval_with_calibration_selected_blend": eval_blend,
            },
        )
        summary["saved_best_bundle"] = saved_bundle
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
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-query-tokens", type=int, default=128)
    parser.add_argument("--max-doc-tokens", type=int, default=128)
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--rows-per-step", type=int, default=16)
    parser.add_argument("--eval-every", type=int, default=50)
    parser.add_argument("--learning-rate", type=float, default=0.00005)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--teacher-mse-weight", type=float, default=0.25)
    parser.add_argument("--candidate-ce-weight", type=float, default=1.0)
    parser.add_argument("--operation-balanced-sampling", action="store_true")
    parser.add_argument("--operation-filter", default="")
    parser.add_argument("--alpha-sweep", default="0,0.01,0.025,0.05,0.075,0.1,0.15,0.2,0.3,0.5,0.75,1.0")
    parser.add_argument("--save-best-state-pt", default="")
    parser.add_argument("--save-best-bundle-dir", default="")
    parser.add_argument("--seed", type=int, default=924)
    parser.add_argument("--output-json", required=True)
    train(parser.parse_args())


if __name__ == "__main__":
    main()
