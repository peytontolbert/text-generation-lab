#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import random
import re
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


def _direct_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get("task_type", "") or "") == "active_agent_direct_answer"
        and str(row.get("retrieval_query_text", "") or "").strip()
        and str(row.get("retrieval_doc_text", "") or "").strip()
    ]


def _collision_key(row: dict[str, Any]) -> str:
    value = str(row.get("collision_key_value", "") or "").strip()
    if value:
        return value
    name = str(row.get("collision_key_name", "") or "").strip()
    if name and str(row.get(name, "") or "").strip():
        return str(row.get(name, "") or "").strip()
    return str(row.get("operation", "") or "global")


def _unique_docs(rows: list[dict[str, Any]]) -> list[str]:
    docs: list[str] = []
    seen: set[str] = set()
    groups: dict[str, set[str]] = {}
    for row in rows:
        doc = str(row.get("retrieval_doc_text", "") or "").strip()
        if not doc:
            continue
        if doc not in seen:
            seen.add(doc)
            docs.append(doc)
        groups.setdefault(_collision_key(row), set()).add(doc)
    return docs


def _embed_query_rows(
    retrieval_eval,
    model,
    tokenizer,
    rows: list[dict[str, Any]],
    *,
    max_tokens: int,
    batch_size: int,
    device: torch.device,
) -> torch.Tensor:
    chunks: list[torch.Tensor] = []
    with torch.no_grad():
        for offset in range(0, len(rows), int(batch_size)):
            texts = [str(row.get("retrieval_query_text", "") or "") for row in rows[offset : offset + int(batch_size)]]
            chunks.append(
                retrieval_eval._embed_query(model, tokenizer, texts, max_tokens=int(max_tokens), device=device)
                .detach()
                .float()
                .cpu()
            )
    return torch.cat(chunks, dim=0)


def _embed_docs(
    retrieval_eval,
    model,
    tokenizer,
    docs: list[str],
    *,
    max_tokens: int,
    batch_size: int,
    device: torch.device,
) -> torch.Tensor:
    chunks: list[torch.Tensor] = []
    with torch.no_grad():
        for offset in range(0, len(docs), int(batch_size)):
            chunks.append(
                retrieval_eval._embed_doc(model, tokenizer, docs[offset : offset + int(batch_size)], max_tokens=int(max_tokens), device=device)
                .detach()
                .float()
                .cpu()
            )
    return torch.cat(chunks, dim=0)


def _load_split_embeddings(args: argparse.Namespace, data: dict[str, Any], device: torch.device) -> dict[str, tuple[torch.Tensor, torch.Tensor]]:
    manifest_path = Path(str(args.dataset_manifest or data.get("dataset_manifest", ""))).resolve()
    if not manifest_path.exists():
        raise RuntimeError("--use-embeddings requires --dataset-manifest or a partition JSON dataset_manifest")
    if not str(args.bundle_dir).strip():
        raise RuntimeError("--use-embeddings requires --bundle-dir")
    repo_root = Path(args.repo_root).resolve()
    retrieval_eval = _load_retrieval_eval(repo_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    train_rows = _direct_rows(_iter_jsonl(Path(manifest["train_dataset_path"])))
    eval_rows = _direct_rows(_iter_jsonl(Path(manifest["eval_dataset_path"])))
    calibration_path = manifest.get("calibration_dataset_path") or manifest.get("calibration_jsonl")
    calibration_rows = _direct_rows(_iter_jsonl(Path(calibration_path))) if calibration_path else []
    split_rows = {"train": train_rows, "calibration": calibration_rows, "eval": eval_rows}
    model, tokenizer, _ = retrieval_eval._load_model(Path(args.bundle_dir).resolve(), repo_root=repo_root, device=device)
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    model.eval()
    embeddings: dict[str, tuple[torch.Tensor, torch.Tensor]] = {}
    for split, rows in split_rows.items():
        if not rows:
            embeddings[split] = (torch.empty((0, 0)), torch.empty((0, 0)))
            continue
        docs = _unique_docs(rows)
        embeddings[split] = (
            _embed_query_rows(
                retrieval_eval,
                model,
                tokenizer,
                rows,
                max_tokens=int(args.max_query_tokens),
                batch_size=int(args.embed_batch_size),
                device=device,
            ),
            _embed_docs(
                retrieval_eval,
                model,
                tokenizer,
                docs,
                max_tokens=int(args.max_doc_tokens),
                batch_size=int(args.embed_batch_size),
                device=device,
            ),
        )
    return embeddings


def _load_split_text_context(args: argparse.Namespace, data: dict[str, Any]) -> dict[str, tuple[list[dict[str, Any]], list[str]]]:
    manifest_path = Path(str(args.dataset_manifest or data.get("dataset_manifest", ""))).resolve()
    if not manifest_path.exists():
        raise RuntimeError("--use-text-bridge-features requires --dataset-manifest or a partition JSON dataset_manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    train_rows = _direct_rows(_iter_jsonl(Path(manifest["train_dataset_path"])))
    eval_rows = _direct_rows(_iter_jsonl(Path(manifest["eval_dataset_path"])))
    calibration_path = manifest.get("calibration_dataset_path") or manifest.get("calibration_jsonl")
    calibration_rows = _direct_rows(_iter_jsonl(Path(calibration_path))) if calibration_path else []
    return {
        "train": (train_rows, _unique_docs(train_rows)),
        "calibration": (calibration_rows, _unique_docs(calibration_rows)),
        "eval": (eval_rows, _unique_docs(eval_rows)),
    }


_QPAIR_RE = re.compile(r"\bqpair_([A-Za-z0-9]+)\b")
_DPAIR_RE = re.compile(r"\bdpair_([A-Za-z0-9]+)\b")
_QENT_RE = re.compile(r"\bqent_([A-Za-z0-9]+)\b")
_DENT_RE = re.compile(r"\bdent_([A-Za-z0-9]+)\b")
_QSLOT_RE = re.compile(r"\b(?:owned_by|linked_to)\b")
_DSLOT_RE = re.compile(r"\bdslot_([A-Za-z0-9]+)\b")
TEXT_BRIDGE_FEATURE_NAMES = (
    "pair_match",
    "source_entity_match",
    "has_query_pair",
    "has_doc_pair",
    "has_query_entity",
    "has_doc_entity",
    "has_query_relation",
    "has_doc_slot",
    "has_query_relation_and_doc_slot",
)


def _first_group(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(str(text or ""))
    return str(match.group(1)) if match else ""


def _text_bridge_features(query_text: str, doc_text: str) -> list[float]:
    qpair = _first_group(_QPAIR_RE, query_text)
    dpair = _first_group(_DPAIR_RE, doc_text)
    qent = _first_group(_QENT_RE, query_text)
    dent = _first_group(_DENT_RE, doc_text)
    has_query_relation = 1.0 if _QSLOT_RE.search(str(query_text or "")) else 0.0
    has_doc_slot = 1.0 if _DSLOT_RE.search(str(doc_text or "")) else 0.0
    return [
        1.0 if qpair and qpair == dpair else 0.0,
        1.0 if qent and qent == dent else 0.0,
        1.0 if qpair else 0.0,
        1.0 if dpair else 0.0,
        1.0 if qent else 0.0,
        1.0 if dent else 0.0,
        has_query_relation,
        has_doc_slot,
        1.0 if has_query_relation and has_doc_slot else 0.0,
    ]


def _parse_feature_mask(value: str) -> set[int]:
    names = {item.strip() for item in str(value or "").split(",") if item.strip()}
    unknown = sorted(names - set(TEXT_BRIDGE_FEATURE_NAMES))
    if unknown:
        raise ValueError(f"unknown text bridge feature name(s): {unknown}; expected {list(TEXT_BRIDGE_FEATURE_NAMES)}")
    return {index for index, name in enumerate(TEXT_BRIDGE_FEATURE_NAMES) if name in names}


def _feature_vector(candidate: dict[str, Any], row: dict[str, Any], op_to_index: dict[str, int]) -> list[float]:
    operation = str(row.get("operation", "") or "unknown")
    selected_count = max(1, int(row.get("selected_count", 0) or len(row.get("candidates", [])) or 1))
    rank = int(candidate.get("selected_rank", 0) or 0)
    values = [
        float(candidate.get("base_score", 0.0) or 0.0),
        float(candidate.get("partition_probability", 0.0) or 0.0),
        float(rank) / float(selected_count),
        1.0 / float(max(1, rank)),
        math.log1p(float(selected_count)),
        float(candidate.get("base_score", 0.0) or 0.0) * float(candidate.get("partition_probability", 0.0) or 0.0),
    ]
    one_hot = [0.0] * len(op_to_index)
    if operation in op_to_index:
        one_hot[op_to_index[operation]] = 1.0
    return [*values, *one_hot]


def _prepare_rows(
    rows: list[dict[str, Any]],
    op_to_index: dict[str, int],
    *,
    query_embeddings: torch.Tensor | None = None,
    doc_embeddings: torch.Tensor | None = None,
    text_rows: list[dict[str, Any]] | None = None,
    text_docs: list[str] | None = None,
    text_bridge_drop_indices: set[int] | None = None,
) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for row in rows:
        candidates = list(row.get("candidates", []) or [])
        if not candidates:
            continue
        for index, candidate in enumerate(candidates, start=1):
            candidate["selected_rank"] = index
        labels = [idx for idx, candidate in enumerate(candidates) if bool(candidate.get("is_exact"))]
        if not labels:
            labels = [idx for idx, candidate in enumerate(candidates) if bool(candidate.get("is_answer_match"))]
        label = int(labels[0]) if labels else -1
        vectors: list[list[float]] = []
        for candidate in candidates:
            vector = _feature_vector(candidate, row, op_to_index)
            if query_embeddings is not None and doc_embeddings is not None and query_embeddings.numel() and doc_embeddings.numel():
                query_index = int(row.get("query_index", -1))
                doc_index = int(candidate.get("doc_index", -1))
                if query_index < 0 or query_index >= query_embeddings.shape[0] or doc_index < 0 or doc_index >= doc_embeddings.shape[0]:
                    raise IndexError(f"partition index out of range for operation={row.get('operation')} query={query_index} doc={doc_index}")
                query_vec = query_embeddings[query_index].float()
                doc_vec = doc_embeddings[doc_index].float()
                pair = torch.cat([query_vec, doc_vec, query_vec * doc_vec, torch.abs(query_vec - doc_vec)], dim=0)
                vector.extend(float(value) for value in pair.tolist())
            if text_rows is not None and text_docs is not None:
                query_index = int(row.get("query_index", -1))
                doc_index = int(candidate.get("doc_index", -1))
                if query_index < 0 or query_index >= len(text_rows) or doc_index < 0 or doc_index >= len(text_docs):
                    raise IndexError(f"text bridge index out of range for operation={row.get('operation')} query={query_index} doc={doc_index}")
                bridge_features = _text_bridge_features(
                    str(text_rows[query_index].get("retrieval_query_text", "") or ""),
                    str(text_docs[doc_index] or ""),
                )
                for feature_index in text_bridge_drop_indices or set():
                    bridge_features[int(feature_index)] = 0.0
                vector.extend(bridge_features)
            vectors.append(vector)
        features = torch.tensor(vectors, dtype=torch.float32)
        prepared.append({"row": row, "features": features, "label": label})
    return prepared


class Reranker(torch.nn.Module):
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

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.net(features).squeeze(-1)


def _score_split(model: Reranker, prepared: list[dict[str, Any]], device: torch.device) -> dict[str, Any]:
    by_operation: dict[str, dict[str, Any]] = {}
    answer = 0
    exact = 0
    mrr = 0.0
    answer_recoverable = 0
    exact_recoverable = 0
    total = len(prepared)
    for item in prepared:
        row = item["row"]
        candidates = list(row.get("candidates", []) or [])
        operation = str(row.get("operation", "") or "unknown")
        bucket = by_operation.setdefault(
            operation,
            {"examples": 0, "answer_correct": 0, "exact_correct": 0, "mrr": 0.0, "answer_recoverable": 0, "exact_recoverable": 0},
        )
        with torch.no_grad():
            scores = model(item["features"].to(device)).detach().cpu()
        order = sorted(range(len(candidates)), key=lambda idx: (-float(scores[idx].item()), idx))
        top = candidates[order[0]]
        top_answer = bool(top.get("is_exact")) or bool(top.get("is_answer_match"))
        top_exact = bool(top.get("is_exact"))
        if top_answer:
            answer += 1
            bucket["answer_correct"] += 1
        if top_exact:
            exact += 1
            bucket["exact_correct"] += 1
        label = int(item["label"])
        rank = order.index(label) + 1 if label >= 0 and label in order else len(order) + 1
        reciprocal = 1.0 / float(rank)
        mrr += reciprocal
        bucket["mrr"] += reciprocal
        if any(bool(candidate.get("is_exact")) or bool(candidate.get("is_answer_match")) for candidate in candidates):
            answer_recoverable += 1
            bucket["answer_recoverable"] += 1
        if any(bool(candidate.get("is_exact")) for candidate in candidates):
            exact_recoverable += 1
            bucket["exact_recoverable"] += 1
        bucket["examples"] += 1
    for bucket in by_operation.values():
        examples = int(bucket["examples"])
        bucket["mrr"] = float(bucket["mrr"]) / float(examples or 1)
    return {
        "examples": total,
        "answer_correct": answer,
        "exact_correct": exact,
        "mrr": mrr / float(total or 1),
        "answer_recoverable": answer_recoverable,
        "exact_recoverable": exact_recoverable,
        "by_operation": by_operation,
    }


def _base_split(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_operation: dict[str, dict[str, Any]] = {}
    answer = 0
    exact = 0
    for row in rows:
        operation = str(row.get("operation", "") or "unknown")
        bucket = by_operation.setdefault(operation, {"examples": 0, "answer_correct": 0, "exact_correct": 0, "answer_recoverable": 0, "exact_recoverable": 0})
        top_answer = bool(row.get("top_candidate_answer_match"))
        top_exact = bool(row.get("top_candidate_exact"))
        if top_answer:
            answer += 1
            bucket["answer_correct"] += 1
        if top_exact:
            exact += 1
            bucket["exact_correct"] += 1
        candidates = list(row.get("candidates", []) or [])
        if any(bool(candidate.get("is_exact")) or bool(candidate.get("is_answer_match")) for candidate in candidates):
            bucket["answer_recoverable"] += 1
        if any(bool(candidate.get("is_exact")) for candidate in candidates):
            bucket["exact_recoverable"] += 1
        bucket["examples"] += 1
    return {"examples": len(rows), "answer_correct": answer, "exact_correct": exact, "by_operation": by_operation}


def _parse_operation_filter(value: str) -> set[str]:
    return {item.strip() for item in str(value or "").split(",") if item.strip()}


def train(args: argparse.Namespace) -> dict[str, Any]:
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    data = json.loads(Path(args.partitions_json).read_text(encoding="utf-8"))
    operations = sorted({str(row.get("operation", "") or "unknown") for split in ("train", "calibration", "eval") for row in data.get(split, [])})
    op_to_index = {operation: index for index, operation in enumerate(operations)}
    train_rows = list(data.get("train", []) or [])
    calibration_rows = list(data.get("calibration", []) or [])
    eval_rows = list(data.get("eval", []) or [])
    include_operations = _parse_operation_filter(str(args.include_operations))
    if include_operations:
        train_rows = [row for row in train_rows if str(row.get("operation", "") or "unknown") in include_operations]
        calibration_rows = [row for row in calibration_rows if str(row.get("operation", "") or "unknown") in include_operations]
        eval_rows = [row for row in eval_rows if str(row.get("operation", "") or "unknown") in include_operations]
        if not train_rows or not calibration_rows or not eval_rows:
            raise RuntimeError(f"operation filter left an empty split: {sorted(include_operations)}")
    embeddings = _load_split_embeddings(args, data, device) if bool(args.use_embeddings) else {}
    text_context = _load_split_text_context(args, data) if bool(args.use_text_bridge_features) else {}
    text_bridge_drop_indices = _parse_feature_mask(str(args.drop_text_bridge_features))
    train_text_rows, train_text_docs = text_context.get("train", (None, None))
    calibration_text_rows, calibration_text_docs = text_context.get("calibration", (None, None))
    eval_text_rows, eval_text_docs = text_context.get("eval", (None, None))
    train_prepared = _prepare_rows(
        train_rows,
        op_to_index,
        query_embeddings=embeddings.get("train", (None, None))[0],
        doc_embeddings=embeddings.get("train", (None, None))[1],
        text_rows=train_text_rows,
        text_docs=train_text_docs,
        text_bridge_drop_indices=text_bridge_drop_indices,
    )
    calibration_prepared = _prepare_rows(
        calibration_rows,
        op_to_index,
        query_embeddings=embeddings.get("calibration", (None, None))[0],
        doc_embeddings=embeddings.get("calibration", (None, None))[1],
        text_rows=calibration_text_rows,
        text_docs=calibration_text_docs,
        text_bridge_drop_indices=text_bridge_drop_indices,
    )
    eval_prepared = _prepare_rows(
        eval_rows,
        op_to_index,
        query_embeddings=embeddings.get("eval", (None, None))[0],
        doc_embeddings=embeddings.get("eval", (None, None))[1],
        text_rows=eval_text_rows,
        text_docs=eval_text_docs,
        text_bridge_drop_indices=text_bridge_drop_indices,
    )
    train_supervised = [item for item in train_prepared if int(item["label"]) >= 0]
    if not train_supervised:
        raise RuntimeError("no supervised train rows with a positive candidate in frozen partitions")
    input_dim = int(train_prepared[0]["features"].shape[1])
    model = Reranker(input_dim, int(args.hidden_dim)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))
    best_state: dict[str, torch.Tensor] | None = None
    best_calibration: dict[str, Any] | None = None
    history: list[dict[str, Any]] = []
    order = list(range(len(train_supervised)))
    for step in range(1, int(args.steps) + 1):
        random.shuffle(order)
        losses: list[torch.Tensor] = []
        for idx in order[: int(args.rows_per_step)]:
            item = train_supervised[idx]
            scores = model(item["features"].to(device))
            target = torch.tensor([int(item["label"])], dtype=torch.long, device=device)
            losses.append(F.cross_entropy(scores.unsqueeze(0), target))
        loss = torch.stack(losses).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % int(args.eval_every) == 0:
            calibration = _score_split(model, calibration_prepared, device)
            record = {"step": step, "loss": float(loss.detach().cpu().item()), "calibration_answer": calibration["answer_correct"], "calibration_exact": calibration["exact_correct"], "calibration_mrr": calibration["mrr"]}
            history.append(record)
            if best_calibration is None or (calibration["answer_correct"], calibration["exact_correct"], calibration["mrr"]) > (
                best_calibration["answer_correct"],
                best_calibration["exact_correct"],
                best_calibration["mrr"],
            ):
                best_calibration = calibration
                best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    summary = {
        "artifact_kind": "stage860_frozen_partition_reranker_eval",
        "partitions_json": str(Path(args.partitions_json).resolve()),
        "bundle_dir": str(Path(args.bundle_dir).resolve()) if str(args.bundle_dir).strip() else "",
        "dataset_manifest": str(Path(str(args.dataset_manifest or data.get("dataset_manifest", ""))).resolve()) if str(args.dataset_manifest or data.get("dataset_manifest", "")).strip() else "",
        "use_embeddings": bool(args.use_embeddings),
        "use_text_bridge_features": bool(args.use_text_bridge_features),
        "drop_text_bridge_features": str(args.drop_text_bridge_features),
        "text_bridge_feature_names": list(TEXT_BRIDGE_FEATURE_NAMES),
        "operations": operations,
        "include_operations": sorted(include_operations),
        "input_dim": input_dim,
        "hidden_dim": int(args.hidden_dim),
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "train_rows": len(train_prepared),
        "train_supervised_rows": len(train_supervised),
        "calibration_rows": len(calibration_prepared),
        "eval_rows": len(eval_prepared),
        "steps": int(args.steps),
        "rows_per_step": int(args.rows_per_step),
        "learning_rate": float(args.learning_rate),
        "weight_decay": float(args.weight_decay),
        "history": history,
        "base_train": _base_split(train_rows),
        "base_calibration": _base_split(calibration_rows),
        "base_eval": _base_split(eval_rows),
        "train": _score_split(model, train_prepared, device),
        "calibration": _score_split(model, calibration_prepared, device),
        "eval": _score_split(model, eval_prepared, device),
        "decision_hint": "Accept only if eval beats the frozen Stage853 base ordering of 237/220 without changing first-stage partitions.",
    }
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(_repo_root()))
    parser.add_argument("--partitions-json", required=True)
    parser.add_argument("--include-operations", default="")
    parser.add_argument("--bundle-dir", default="")
    parser.add_argument("--dataset-manifest", default="")
    parser.add_argument("--use-embeddings", action="store_true")
    parser.add_argument("--use-text-bridge-features", action="store_true")
    parser.add_argument("--drop-text-bridge-features", default="")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--max-query-tokens", type=int, default=128)
    parser.add_argument("--max-doc-tokens", type=int, default=256)
    parser.add_argument("--embed-batch-size", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=16)
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--rows-per-step", type=int, default=128)
    parser.add_argument("--eval-every", type=int, default=25)
    parser.add_argument("--learning-rate", type=float, default=0.005)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=860)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    train(args)


if __name__ == "__main__":
    main()
