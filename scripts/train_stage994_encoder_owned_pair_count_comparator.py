#!/usr/bin/env python3
"""Train an encoder-owned qpair/dpair comparator for the Stage981 pair policy."""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import re
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F


QPAIR_RE = re.compile(r"\bqpair_[A-Za-z0-9]+\b")
DPAIR_RE = re.compile(r"\bdpair_[A-Za-z0-9]+\b")


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


def _rows_by_split(path: Path, operations: set[str]) -> dict[str, list[dict[str, Any]]]:
    rows = {"train": [], "calibration": [], "eval": []}
    for row in _iter_jsonl(path):
        if str(row.get("operation", "")) in operations:
            rows.setdefault(str(row.get("split")), []).append(row)
    return rows


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


def _encode_with_offsets(tokenizer, text: str, max_tokens: int) -> tuple[list[int], list[tuple[int, int]]]:
    inner = getattr(tokenizer, "tokenizer", None)
    if inner is not None:
        encoded = inner.encode(str(text), add_special_tokens=True)
        return list(encoded.ids)[:max_tokens], list(encoded.offsets)[:max_tokens]
    ids = tokenizer.encode(str(text), max_length=max_tokens)
    return list(ids)[:max_tokens], [(0, 0)] * min(len(ids), max_tokens)


def _span_token_indices(offsets: list[tuple[int, int]], spans: list[tuple[int, int]], mask: torch.Tensor) -> list[list[int]]:
    groups: list[list[int]] = []
    for start, end in spans:
        indices: list[int] = []
        for idx, (tok_start, tok_end) in enumerate(offsets):
            if int(mask[idx].item()) == 0:
                continue
            if tok_end > start and tok_start < end:
                indices.append(idx)
        groups.append(indices)
    return groups


def _spans(pattern: re.Pattern[str], text: str) -> list[tuple[int, int]]:
    return [(int(match.start()), int(match.end())) for match in pattern.finditer(str(text or ""))]


def _pair_span_vectors(model, tokenizer, texts: list[str], *, pattern: re.Pattern[str], max_tokens: int, device: torch.device) -> list[torch.Tensor]:
    pad_id = int(getattr(tokenizer, "pad_token_id", 0) or 0)
    vectors: list[torch.Tensor] = []
    with torch.no_grad():
        for text in texts:
            ids, offsets = _encode_with_offsets(tokenizer, text, int(max_tokens))
            mask_values = [1] * len(ids)
            while len(ids) < int(max_tokens):
                ids.append(pad_id)
                offsets.append((0, 0))
                mask_values.append(0)
            input_ids = torch.tensor([ids[: int(max_tokens)]], dtype=torch.long, device=device)
            mask = torch.tensor(mask_values[: int(max_tokens)], dtype=torch.long, device=device)
            hidden = model.encode(input_ids, mask.unsqueeze(0))[0].detach().float().cpu()
            groups = _span_token_indices(offsets[: int(max_tokens)], _spans(pattern, text), mask.cpu())
            pooled: list[torch.Tensor] = []
            for group in groups:
                if group:
                    pooled.append(hidden[group].mean(dim=0))
            if pooled:
                vectors.append(F.normalize(torch.stack(pooled, dim=0), dim=-1))
            else:
                vectors.append(torch.empty((0, hidden.shape[-1]), dtype=torch.float32))
    return vectors


def _candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _label(candidate: dict[str, Any]) -> float:
    return float(int(candidate.get("selected_min_pair_overlap", 0) or 0) > 0 and int(candidate.get("pair_overlap_count", 0) or 0) >= int(candidate.get("selected_min_pair_overlap", 0) or 0))


def _features(q_vecs: torch.Tensor, d_vecs: torch.Tensor, row: dict[str, Any], candidate: dict[str, Any]) -> torch.Tensor:
    if q_vecs.numel() and d_vecs.numel():
        sim = torch.matmul(q_vecs, d_vecs.T)
        max_sim = sim.max()
        mean_max_q = sim.max(dim=1).values.mean()
        mean_max_d = sim.max(dim=0).values.mean()
        soft_count = torch.sigmoid((sim - 0.55) * 12.0).sum()
    else:
        max_sim = mean_max_q = mean_max_d = soft_count = torch.tensor(0.0)
    op = str(row.get("operation", ""))
    return torch.tensor(
        [
            float(max_sim.item()),
            float(mean_max_q.item()),
            float(mean_max_d.item()),
            float(soft_count.item()) / 4.0,
            float(len(q_vecs)) / 4.0,
            float(len(d_vecs)) / 4.0,
            float(candidate.get("base_score", 0.0) or 0.0),
            1.0 / max(1.0, float(candidate.get("rank", 9999) or 9999)),
            float(candidate.get("selected_min_pair_overlap", 0) or 0) / 4.0,
            1.0 if op == "composition" else 0.0,
            1.0 if op == "relation" else 0.0,
        ],
        dtype=torch.float32,
    )


class PairComparator(torch.nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(11, int(hidden_dim)),
            torch.nn.GELU(),
            torch.nn.Linear(int(hidden_dim), 1),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.net(features).squeeze(-1)


def _build_examples(rows: list[dict[str, Any]], q_vecs: list[torch.Tensor], doc_vecs: list[torch.Tensor], doc_to_idx: dict[str, int]) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for row_idx, row in enumerate(rows):
        for cand_idx, candidate in enumerate(list(row.get("candidates", []) or [])):
            doc_text = str(candidate.get("doc_text", "") or "")
            examples.append(
                {
                    "row_idx": row_idx,
                    "cand_idx": cand_idx,
                    "operation": str(row.get("operation", "")),
                    "features": _features(q_vecs[row_idx], doc_vecs[doc_to_idx[doc_text]], row, candidate),
                    "target": _label(candidate),
                    "answer": _candidate_hit(candidate)[0],
                    "exact": _candidate_hit(candidate)[1],
                    "base_score": float(candidate.get("base_score", 0.0) or 0.0),
                    "rank": int(candidate.get("rank", 9999) or 9999),
                }
            )
    return examples


def _score_rows(model: PairComparator, rows: list[dict[str, Any]], examples: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    by_row: dict[int, list[dict[str, Any]]] = {}
    with torch.no_grad():
        model.eval()
        for ex in examples:
            item = dict(ex)
            item["prob"] = float(torch.sigmoid(model(ex["features"].unsqueeze(0))).item())
            by_row.setdefault(int(ex["row_idx"]), []).append(item)
    answer = exact = base_answer = base_exact = predicted_rows = 0
    by_operation: dict[str, dict[str, int]] = {}
    for row_idx, row in enumerate(rows):
        candidates = list(row.get("candidates", []) or [])
        row_examples = by_row.get(row_idx, [])
        op = str(row.get("operation", "unknown"))
        stats = by_operation.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0, "predicted_rows": 0})
        stats["rows"] += 1
        base_idx = max(range(len(candidates)), key=lambda idx: (float(candidates[idx].get("base_score", 0.0) or 0.0), -int(candidates[idx].get("rank", 9999) or 9999), -idx))
        pool = [ex for ex in row_examples if float(ex["prob"]) >= float(threshold)]
        if pool:
            predicted_rows += 1
            stats["predicted_rows"] += 1
            selected = max(pool, key=lambda ex: (float(ex["base_score"]), -int(ex["rank"]), -int(ex["cand_idx"])))
            pred_idx = int(selected["cand_idx"])
        else:
            pred_idx = base_idx
        ans, exa = _candidate_hit(candidates[pred_idx])
        bans, bex = _candidate_hit(candidates[base_idx])
        answer += ans
        exact += exa
        base_answer += bans
        base_exact += bex
        stats["answer"] += ans
        stats["exact"] += exa
        stats["base_answer"] += bans
        stats["base_exact"] += bex
    return {
        "rows": len(rows),
        "answer": answer,
        "exact": exact,
        "base_answer": base_answer,
        "base_exact": base_exact,
        "predicted_rows": predicted_rows,
        "threshold": float(threshold),
        "by_operation": by_operation,
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    repo_root = Path(args.repo_root).resolve()
    retrieval_eval = _load_retrieval_eval(repo_root)
    rows = _rows_by_split(Path(args.targets_jsonl), {"composition", "relation"})
    base_model, tokenizer, _ = retrieval_eval._load_model(Path(args.bundle_dir).resolve(), repo_root=repo_root, device=device)
    base_model.eval()
    for parameter in base_model.parameters():
        parameter.requires_grad_(False)
    docs = {split: _unique_docs(split_rows) for split, split_rows in rows.items()}
    doc_to_idx = {split: {doc: idx for idx, doc in enumerate(split_docs)} for split, split_docs in docs.items()}
    q_vecs = {
        split: _pair_span_vectors(base_model, tokenizer, [str(row.get("query_text", "") or "") for row in split_rows], pattern=QPAIR_RE, max_tokens=int(args.max_query_tokens), device=device)
        for split, split_rows in rows.items()
    }
    d_vecs = {
        split: _pair_span_vectors(base_model, tokenizer, docs[split], pattern=DPAIR_RE, max_tokens=int(args.max_doc_tokens), device=device)
        for split in rows
    }
    examples = {split: _build_examples(rows[split], q_vecs[split], d_vecs[split], doc_to_idx[split]) for split in rows}
    model = PairComparator(int(args.hidden_dim)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))
    train_examples = examples["train"]
    best_state = None
    best_key = None
    history = []
    thresholds = [float(item) for item in str(args.threshold_sweep).split(",") if item.strip()]
    for step in range(1, int(args.steps) + 1):
        batch = random.choices(train_examples, k=int(args.batch_size))
        feats = torch.stack([item["features"] for item in batch]).to(device)
        labels = torch.tensor([float(item["target"]) for item in batch], dtype=torch.float32, device=device)
        logits = model(feats)
        loss = F.binary_cross_entropy_with_logits(logits, labels)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % int(args.eval_every) == 0:
            cal_scores = [_score_rows(model.cpu(), rows["calibration"], examples["calibration"], threshold) for threshold in thresholds]
            model.to(device)
            selected = max(cal_scores, key=lambda item: (item["answer"], item["exact"], item["predicted_rows"], -item["threshold"]))
            history.append({"step": step, "loss": float(loss.detach().cpu().item()), "selected_calibration": selected})
            key = (selected["answer"], selected["exact"], selected["predicted_rows"])
            if best_key is None or key > best_key:
                best_key = key
                best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    model.cpu()
    cal_scores = [_score_rows(model, rows["calibration"], examples["calibration"], threshold) for threshold in thresholds]
    selected_cal = max(cal_scores, key=lambda item: (item["answer"], item["exact"], item["predicted_rows"], -item["threshold"]))
    eval_score = _score_rows(model, rows["eval"], examples["eval"], float(selected_cal["threshold"]))
    summary = {
        "artifact_kind": "stage994_encoder_owned_pair_count_comparator",
        "status": "completed_encoder_owned_pair_comparator_probe",
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "targets_jsonl": str(Path(args.targets_jsonl).resolve()),
        "operations": ["composition", "relation"],
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "steps": int(args.steps),
        "batch_size": int(args.batch_size),
        "history": history,
        "calibration_selected": selected_cal,
        "eval_with_calibration_threshold": eval_score,
        "stage981_pair_interface_eval_answer_exact_for_same_ops": {
            "composition": [58, 42],
            "relation": [100, 100],
            "combined": [158, 142],
        },
        "decision": "Uses frozen 100M encoder token states at qpair/dpair spans to predict pair-arity positives. Eval does not use suffix set intersection, but still uses qpair/dpair span markers to locate encoder states.",
    }
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(_repo_root()))
    parser.add_argument("--targets-jsonl", default="runs/local/artifacts/stage975_pair_overlap_teacher_targets.jsonl")
    parser.add_argument("--bundle-dir", default="runs/local/artifacts/pocketpal_controller_100m_stage976_stage975_pair_teacher_loadable_v415")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--max-query-tokens", type=int, default=128)
    parser.add_argument("--max-doc-tokens", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--eval-every", type=int, default=100)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.001)
    parser.add_argument("--threshold-sweep", default="0.05,0.1,0.15,0.2,0.25,0.3,0.4,0.5,0.6,0.7,0.8,0.9")
    parser.add_argument("--seed", type=int, default=994)
    parser.add_argument("--output-json", required=True)
    train(parser.parse_args())


if __name__ == "__main__":
    main()
