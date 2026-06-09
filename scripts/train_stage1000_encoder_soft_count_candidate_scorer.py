#!/usr/bin/env python3
"""Train a soft-count candidate scorer over learned encoder pair equality signals."""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CandidateScorer(torch.nn.Module):
    def __init__(self, dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(dim, hidden_dim),
            torch.nn.GELU(),
            torch.nn.Linear(hidden_dim, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _rows_by_split(path: Path) -> dict[str, list[dict[str, Any]]]:
    rows = {"train": [], "calibration": [], "eval": []}
    for row in _iter_jsonl(path):
        if str(row.get("operation", "")) in {"composition", "relation"}:
            rows.setdefault(str(row.get("split")), []).append(row)
    return rows


def _candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _base_index(candidates: list[dict[str, Any]]) -> int:
    return max(
        range(len(candidates)),
        key=lambda idx: (float(candidates[idx].get("base_score", 0.0) or 0.0), -int(candidates[idx].get("rank", 9999) or 9999), -idx),
    )


def _pair_probs(pair_model, q: dict[str, Any], d: dict[str, Any]) -> list[float]:
    probs: list[float] = []
    with torch.no_grad():
        for qi in range(len(q["vectors"])):
            best = 0.0
            for di in range(len(d["vectors"])):
                prob = torch.sigmoid(pair_model(q["vectors"][qi].unsqueeze(0), d["vectors"][di].unsqueeze(0))).item()
                best = max(best, float(prob))
            probs.append(best)
    return probs


def _features(pair_model, row: dict[str, Any], candidate: dict[str, Any], q: dict[str, Any], d: dict[str, Any]) -> torch.Tensor:
    probs = _pair_probs(pair_model, q, d)
    selected_arity = float(candidate.get("selected_min_pair_overlap", 0) or 0)
    thresholds = [0.05, 0.1, 0.2, 0.4]
    counts = [sum(1.0 for prob in probs if prob >= threshold) for threshold in thresholds]
    sorted_probs = sorted(probs, reverse=True)
    top = sorted_probs + [0.0, 0.0, 0.0, 0.0]
    op = str(row.get("operation", "") or "")
    op_bits = [1.0 if op == "composition" else 0.0, 1.0 if op == "relation" else 0.0]
    values = [
        float(candidate.get("base_score", 0.0) or 0.0),
        1.0 / float(candidate.get("rank", 9999) or 9999),
        selected_arity / 4.0,
        float(len(q["vectors"])) / 4.0,
        float(len(d["vectors"])) / 4.0,
        sum(probs) / 4.0,
        (sum(probs) / float(len(probs))) if probs else 0.0,
        min(probs) if probs else 0.0,
        top[0],
        top[1],
        top[2],
        top[3],
        counts[0] / 4.0,
        counts[1] / 4.0,
        counts[2] / 4.0,
        counts[3] / 4.0,
        max(0.0, counts[1] - selected_arity) / 4.0,
        1.0 if counts[1] >= selected_arity and selected_arity > 0 else 0.0,
    ] + op_bits
    return torch.tensor(values, dtype=torch.float32)


def _build_span_cache(stage995, base_model, tokenizer, rows: dict[str, list[dict[str, Any]]], device: torch.device, max_query_tokens: int, max_doc_tokens: int, use_bridge_fields: bool, pair_token_prefix: str):
    query_prefix = str(pair_token_prefix or "qpair")
    doc_prefix = str(pair_token_prefix or "dpair")
    query_pattern = stage995._prefix_re(query_prefix)
    doc_pattern = stage995._prefix_re(doc_prefix)
    docs = {split: stage995._unique_docs(split_rows, use_bridge_fields=use_bridge_fields, doc_pattern=doc_pattern) for split, split_rows in rows.items()}
    doc_to_idx = {split: {str(doc["text"]): idx for idx, doc in enumerate(split_docs)} for split, split_docs in docs.items()}
    query_records = {
        split: [
            {
                "text": str(row.get("query_text", "") or ""),
                "suffixes": [str(item) for item in (row.get("query_bridge", {}) or {}).get("qpair", []) or []] if use_bridge_fields else [],
            }
            for row in split_rows
        ]
        for split, split_rows in rows.items()
    }
    q_spans = {
        split: stage995._span_vectors_with_suffixes(base_model, tokenizer, query_records[split], prefix=query_prefix, pattern=query_pattern, max_tokens=max_query_tokens, device=device)
        for split in rows
    }
    d_spans = {
        split: stage995._span_vectors_with_suffixes(base_model, tokenizer, docs[split], prefix=doc_prefix, pattern=doc_pattern, max_tokens=max_doc_tokens, device=device)
        for split in rows
    }
    return q_spans, d_spans, doc_to_idx


def _examples(pair_model, rows: list[dict[str, Any]], q_spans: list[dict[str, Any]], d_spans: list[dict[str, Any]], doc_to_idx: dict[str, int]):
    out = []
    for row_idx, row in enumerate(rows):
        q = q_spans[row_idx]
        for candidate in list(row.get("candidates", []) or []):
            d = d_spans[doc_to_idx[str(candidate.get("doc_text", "") or "")]]
            label = float(bool(candidate.get("is_exact") or candidate.get("is_answer_match")))
            out.append((_features(pair_model, row, candidate, q, d), label))
    return out


def _score_rows(model, pair_model, rows, q_spans, d_spans, doc_to_idx, alpha: float) -> dict[str, Any]:
    answer = exact = base_answer = base_exact = 0
    by_operation: dict[str, dict[str, int]] = {}
    with torch.no_grad():
        model.eval()
        for row_idx, row in enumerate(rows):
            op = str(row.get("operation", "unknown"))
            stats = by_operation.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0})
            stats["rows"] += 1
            candidates = list(row.get("candidates", []) or [])
            q = q_spans[row_idx]
            scored = []
            for cand_idx, candidate in enumerate(candidates):
                d = d_spans[doc_to_idx[str(candidate.get("doc_text", "") or "")]]
                feature = _features(pair_model, row, candidate, q, d).unsqueeze(0)
                logit = float(model(feature).item())
                base = float(candidate.get("base_score", 0.0) or 0.0)
                scored.append((cand_idx, logit + float(alpha) * base))
            pred_idx = max(scored, key=lambda item: (item[1], -item[0]))[0]
            base_idx = _base_index(candidates)
            ans, ex = _candidate_hit(candidates[pred_idx])
            bans, bex = _candidate_hit(candidates[base_idx])
            answer += ans
            exact += ex
            base_answer += bans
            base_exact += bex
            stats["answer"] += ans
            stats["exact"] += ex
            stats["base_answer"] += bans
            stats["base_exact"] += bex
    return {"rows": len(rows), "answer": answer, "exact": exact, "base_answer": base_answer, "base_exact": base_exact, "alpha": float(alpha), "by_operation": by_operation}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage975_pair_overlap_teacher_targets.jsonl"))
    parser.add_argument("--bundle-dir", type=Path, default=Path("runs/local/artifacts/pocketpal_controller_100m_stage976_stage975_pair_teacher_loadable_v415"))
    parser.add_argument("--pair-state", type=Path, default=Path("runs/local/artifacts/stage996_encoder_span_pair_equality_comparator_state.pt"))
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--steps", type=int, default=600)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.001)
    parser.add_argument("--positive-weight", type=float, default=2.0)
    parser.add_argument("--use-text-regex-suffixes", action="store_true")
    parser.add_argument("--pair-token-prefix", default="")
    parser.add_argument("--alpha-sweep", default="0,0.1,0.25,0.5,0.75,1.0")
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--output-state", type=Path, default=Path("runs/local/artifacts/stage1000_encoder_soft_count_candidate_scorer_state.pt"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1000_encoder_soft_count_candidate_scorer_summary.json"))
    args = parser.parse_args()

    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    repo_root = args.repo_root.resolve()
    stage995 = _load_module(repo_root / "scripts/train_stage995_encoder_span_pair_equality_comparator.py", "stage995")
    retrieval_eval = stage995._load_retrieval_eval(repo_root)
    device = torch.device(str(args.device))
    rows = _rows_by_split(args.targets_jsonl)
    base_model, tokenizer, _ = retrieval_eval._load_model(args.bundle_dir.resolve(), repo_root=repo_root, device=device)
    base_model.eval()
    pair_state = torch.load(args.pair_state, map_location="cpu")
    pair_model = stage995.PairEq(int(pair_state["dim"]), int(pair_state["hidden_dim"]))
    pair_model.load_state_dict(pair_state["model_state"])
    pair_model.eval()
    use_bridge_fields = not bool(args.use_text_regex_suffixes)
    q_spans, d_spans, doc_to_idx = _build_span_cache(stage995, base_model, tokenizer, rows, device, 128, 128, use_bridge_fields, str(args.pair_token_prefix))
    examples = _examples(pair_model, rows["train"], q_spans["train"], d_spans["train"], doc_to_idx["train"])
    dim = int(examples[0][0].numel())
    model = CandidateScorer(dim, int(args.hidden_dim))
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))
    pos_weight = torch.tensor(float(args.positive_weight), dtype=torch.float32)
    best_state = None
    best_key = None
    history = []
    alphas = [float(item) for item in str(args.alpha_sweep).split(",") if item.strip()]
    for step in range(1, int(args.steps) + 1):
        batch = random.choices(examples, k=int(args.batch_size))
        x = torch.stack([item[0] for item in batch])
        y = torch.tensor([item[1] for item in batch], dtype=torch.float32)
        logits = model(x)
        loss = F.binary_cross_entropy_with_logits(logits, y, pos_weight=pos_weight)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % 100 == 0:
            cal_scores = [_score_rows(model, pair_model, rows["calibration"], q_spans["calibration"], d_spans["calibration"], doc_to_idx["calibration"], alpha) for alpha in alphas]
            selected = max(cal_scores, key=lambda item: (item["answer"], item["exact"], -item["alpha"]))
            history.append({"step": step, "loss": float(loss.item()), "selected_calibration": selected})
            key = (selected["answer"], selected["exact"])
            if best_key is None or key > best_key:
                best_key = key
                best_state = {name: value.detach().clone() for name, value in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    cal_scores = [_score_rows(model, pair_model, rows["calibration"], q_spans["calibration"], d_spans["calibration"], doc_to_idx["calibration"], alpha) for alpha in alphas]
    selected = max(cal_scores, key=lambda item: (item["answer"], item["exact"], -item["alpha"]))
    eval_score = _score_rows(model, pair_model, rows["eval"], q_spans["eval"], d_spans["eval"], doc_to_idx["eval"], float(selected["alpha"]))
    args.output_state.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model_state": model.state_dict(), "dim": dim, "hidden_dim": int(args.hidden_dim), "alpha": float(selected["alpha"]), "pair_state": str(args.pair_state)}, args.output_state)
    summary = {
        "artifact_kind": "stage1000_encoder_soft_count_candidate_scorer",
        "status": "completed_soft_count_candidate_scorer",
        "pair_state": str(args.pair_state),
        "suffix_source": "rendered_text_regex" if bool(args.use_text_regex_suffixes) else "structured_bridge_fields",
        "pair_token_prefix": str(args.pair_token_prefix or "side_specific_qpair_dpair"),
        "output_state": str(args.output_state),
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "pair_parameter_count": sum(parameter.numel() for parameter in pair_model.parameters()),
        "examples": len(examples),
        "positive_examples": int(sum(item[1] for item in examples)),
        "history": history,
        "calibration_selected": selected,
        "eval": eval_score,
        "stage996_hard_count_eval_answer_exact": [152, 136],
        "stage981_fixed_pair_interface_same_ops_answer_exact": [158, 142],
        "decision": "Uses learned pair equality probabilities to build soft count features for candidate ranking. Eval does not use suffix set intersection; qpair/dpair markers remain the located comparison interface.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
