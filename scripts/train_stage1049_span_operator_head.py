#!/usr/bin/env python3
"""Train a frozen-span operator head from 100M token spans."""

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


QENT_RE = re.compile(r"\bqent_[A-Za-z0-9]+\b")
Qslot_RE = re.compile(r"\bqslot_[A-Za-z0-9]+\b")
STATEMENT_DENT_RE = re.compile(r"\bstatement=(?:claim\s+)?dent_[A-Za-z0-9]+\b")
DSLOT_RE = re.compile(r"\bdslot_[A-Za-z0-9]+\b")
DEFAULT_KIND_RE = re.compile(r"\bdefault\s+[A-Za-z0-9]+\b")
ANSWER_KIND_RE = re.compile(r"\banswer=[A-Za-z0-9]+_v[0-9A-Za-z]+\b")
DEFAULT_POLICY_RE = re.compile(r"\bstatement=default\s+[A-Za-z0-9]+\s+policy\b")


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


def _rows_by_split(path: Path) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {"train": [], "calibration": [], "eval": []}
    for row in _iter_jsonl(path):
        split = str(row.get("split", ""))
        if split in rows:
            rows[split].append(row)
    return rows


def _unique_docs(rows_by_split: dict[str, list[dict[str, Any]]]) -> list[str]:
    seen: set[str] = set()
    docs: list[str] = []
    for rows in rows_by_split.values():
        for row in rows:
            for candidate in list(row.get("candidates", []) or []):
                text = str(candidate.get("doc_text", "") or "")
                if text and text not in seen:
                    seen.add(text)
                    docs.append(text)
    return docs


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


def _span_vectors(
    model,
    tokenizer,
    text: str,
    *,
    patterns: dict[str, re.Pattern[str]],
    max_tokens: int,
    device: torch.device,
) -> dict[str, torch.Tensor]:
    pad_id = int(getattr(tokenizer, "pad_token_id", 0) or 0)
    ids, offsets = _encode_with_offsets(tokenizer, text, int(max_tokens))
    mask_values = [1] * len(ids)
    while len(ids) < int(max_tokens):
        ids.append(pad_id)
        offsets.append((0, 0))
        mask_values.append(0)
    input_ids = torch.tensor([ids[: int(max_tokens)]], dtype=torch.long, device=device)
    mask = torch.tensor(mask_values[: int(max_tokens)], dtype=torch.long, device=device)
    with torch.no_grad():
        hidden = model.encode(input_ids, mask.unsqueeze(0))[0].detach().float().cpu()
    out: dict[str, torch.Tensor] = {}
    for name, pattern in patterns.items():
        groups = _span_token_indices(offsets[: int(max_tokens)], _spans(pattern, text), mask.cpu())
        pooled = [hidden[group].mean(dim=0) for group in groups if group]
        out[name] = F.normalize(torch.stack(pooled, dim=0), dim=-1) if pooled else torch.empty((0, hidden.shape[-1]), dtype=torch.float32)
    return out


def _max_sim(a: torch.Tensor, b: torch.Tensor) -> float:
    if not a.numel() or not b.numel():
        return 0.0
    return float(torch.matmul(a, b.T).max().item())


def _soft_count(a: torch.Tensor, b: torch.Tensor, threshold: float = 0.55) -> float:
    if not a.numel() or not b.numel():
        return 0.0
    sims = torch.matmul(a, b.T)
    return float(torch.sigmoid((sims - float(threshold)) * 12.0).max(dim=1).values.sum().item())


def _candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _features(row: dict[str, Any], candidate: dict[str, Any], q: dict[str, torch.Tensor], d: dict[str, torch.Tensor]) -> torch.Tensor:
    op = str(row.get("operation", "") or "")
    return torch.tensor(
        [
            _max_sim(q["qent"], d["statement_dent"]),
            _max_sim(q["qslot"], d["dslot"]),
            _soft_count(q["qslot"], d["dslot"]) / 4.0,
            _max_sim(q["default_kind"], d["answer_kind"]),
            _max_sim(q["default_kind"], d["default_policy"]),
            float(candidate.get("base_score", 0.0) or 0.0),
            1.0 / max(1.0, float(candidate.get("rank", 9999) or 9999)),
            1.0 if op == "composition" else 0.0,
            1.0 if op == "relation" else 0.0,
            1.0 if op == "counterfactual_false_claim" else 0.0,
            1.0 if op == "exception" else 0.0,
            1.0 if op == "atomic_fact" else 0.0,
        ],
        dtype=torch.float32,
    )


class SpanOperatorHead(torch.nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(12, int(hidden_dim)),
            torch.nn.GELU(),
            torch.nn.Linear(int(hidden_dim), 1),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.net(features).squeeze(-1)


def _build_examples(rows: list[dict[str, Any]], query_vecs: list[dict[str, torch.Tensor]], doc_vecs: dict[str, dict[str, torch.Tensor]]) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for row_idx, row in enumerate(rows):
        for cand_idx, candidate in enumerate(list(row.get("candidates", []) or [])):
            doc = str(candidate.get("doc_text", "") or "")
            examples.append(
                {
                    "row_idx": row_idx,
                    "cand_idx": cand_idx,
                    "operation": str(row.get("operation", "")),
                    "features": _features(row, candidate, query_vecs[row_idx], doc_vecs[doc]),
                    "target": float(candidate.get("teacher_candidate_value_score", 0.0) or 0.0),
                    "operator_target": float(candidate.get("teacher_operator_score", 0.0) or 0.0),
                    "answer": _candidate_hit(candidate)[0],
                    "exact": _candidate_hit(candidate)[1],
                    "base_score": float(candidate.get("base_score", 0.0) or 0.0),
                    "rank": int(candidate.get("rank", 9999) or 9999),
                }
            )
    return examples


def _score_rows(model: SpanOperatorHead, rows: list[dict[str, Any]], examples: list[dict[str, Any]], alpha: float, use_blend_ops: set[str]) -> dict[str, Any]:
    by_row: dict[int, list[dict[str, Any]]] = {}
    model.eval()
    with torch.no_grad():
        for ex in examples:
            item = dict(ex)
            item["head_score"] = float(model(ex["features"].unsqueeze(0)).item())
            by_row.setdefault(int(ex["row_idx"]), []).append(item)
    answer = exact = base_answer = base_exact = 0
    by_operation: dict[str, dict[str, int]] = {}
    for row_idx, row in enumerate(rows):
        candidates = list(row.get("candidates", []) or [])
        row_examples = by_row.get(row_idx, [])
        op = str(row.get("operation", "unknown"))
        stats = by_operation.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0})
        stats["rows"] += 1
        base_idx = max(range(len(candidates)), key=lambda idx: (float(candidates[idx].get("base_score", 0.0) or 0.0), -idx))
        if op in use_blend_ops:
            selected = max(row_examples, key=lambda ex: (float(ex["base_score"]) + float(alpha) * float(ex["head_score"]), -int(ex["cand_idx"])))
        else:
            selected = row_examples[base_idx]
        pred_idx = int(selected["cand_idx"])
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
    return {"rows": len(rows), "answer": answer, "exact": exact, "base_answer": base_answer, "base_exact": base_exact, "by_operation": by_operation}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1043_operator_teacher_targets.jsonl"))
    parser.add_argument("--bundle-dir", type=Path, default=Path("runs/local/artifacts/pocketpal_controller_100m_stage976_stage975_pair_teacher_loadable_v415"))
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--max-query-tokens", type=int, default=128)
    parser.add_argument("--max-doc-tokens", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--learning-rate", type=float, default=0.003)
    parser.add_argument("--seed", type=int, default=1049)
    parser.add_argument("--alpha-sweep", default="0,0.05,0.1,0.2,0.3,0.5,0.75,1.0,1.5,2.0")
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1049_span_operator_head_summary.json"))
    parser.add_argument("--output-state", type=Path, default=Path("runs/local/artifacts/stage1049_span_operator_head_state.pt"))
    args = parser.parse_args()

    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    retrieval_eval = _load_retrieval_eval(args.repo_root.resolve())
    model, tokenizer, manifest = retrieval_eval._load_model(args.bundle_dir.resolve(), repo_root=args.repo_root.resolve(), device=device)
    model.eval()
    rows = _rows_by_split(args.targets_jsonl)
    query_patterns = {"qent": QENT_RE, "qslot": Qslot_RE, "default_kind": DEFAULT_KIND_RE}
    doc_patterns = {"statement_dent": STATEMENT_DENT_RE, "dslot": DSLOT_RE, "answer_kind": ANSWER_KIND_RE, "default_policy": DEFAULT_POLICY_RE}
    query_vecs = {
        split: [
            _span_vectors(model, tokenizer, str(row.get("query_text", "") or ""), patterns=query_patterns, max_tokens=int(args.max_query_tokens), device=device)
            for row in split_rows
        ]
        for split, split_rows in rows.items()
    }
    all_docs = _unique_docs(rows)
    doc_vecs = {
        doc: _span_vectors(model, tokenizer, doc, patterns=doc_patterns, max_tokens=int(args.max_doc_tokens), device=device)
        for doc in all_docs
    }
    examples = {split: _build_examples(split_rows, query_vecs[split], doc_vecs) for split, split_rows in rows.items()}
    head = SpanOperatorHead(int(args.hidden_dim))
    optimizer = torch.optim.AdamW(head.parameters(), lr=float(args.learning_rate), weight_decay=0.01)
    train_examples = examples["train"]
    history = []
    for step in range(1, int(args.steps) + 1):
        batch = random.choices(train_examples, k=min(int(args.batch_size), len(train_examples)))
        feats = torch.stack([ex["features"] for ex in batch], dim=0)
        targets = torch.tensor([float(ex["target"]) for ex in batch], dtype=torch.float32)
        logits = head(feats)
        loss = F.binary_cross_entropy_with_logits(logits, targets)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % 50 == 0:
            history.append({"step": step, "loss": float(loss.detach().item())})
    alphas = [float(x) for x in str(args.alpha_sweep).split(",") if x.strip()]
    operations = sorted({str(row.get("operation", "")) for row in rows["calibration"]})
    best_cal = None
    best_eval_for_cal = None
    for mask in range(1 << len(operations)):
        use_ops = {operations[i] for i in range(len(operations)) if mask & (1 << i)}
        for alpha in alphas:
            cal = _score_rows(head, rows["calibration"], examples["calibration"], alpha, use_ops)
            key = (cal["answer"], cal["exact"])
            if best_cal is None or key > (best_cal["answer"], best_cal["exact"]):
                best_cal = dict(cal, alpha=alpha, use_blend_operations=sorted(use_ops))
                best_eval_for_cal = _score_rows(head, rows["eval"], examples["eval"], alpha, use_ops)
    assert best_cal is not None and best_eval_for_cal is not None
    summary = {
        "artifact_kind": "stage1049_span_operator_head",
        "status": "completed_span_operator_head_probe",
        "targets_jsonl": str(args.targets_jsonl),
        "bundle_dir": str(args.bundle_dir),
        "parameter_count": int(manifest.get("parameter_count", 0)),
        "head_parameter_count": sum(p.numel() for p in head.parameters()),
        "steps": int(args.steps),
        "batch_size": int(args.batch_size),
        "history": history,
        "train_base": _score_rows(head, rows["train"], examples["train"], 0.0, set()),
        "calibration_selected": best_cal,
        "eval_for_calibration_selected": best_eval_for_cal,
        "decision": "Frozen 100M token-span operator head over rendered qent/dent, qslot/dslot, and default/answer-kind spans. No structured bridge fields or char comparator are used as model inputs.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    torch.save({"summary": summary, "state_dict": head.state_dict()}, args.output_state)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
