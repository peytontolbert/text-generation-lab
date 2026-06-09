#!/usr/bin/env python3
"""Train a candidate scorer from full query/doc token-state alignment features.

This removes explicit qpair/dpair span lookup at eval. The rendered text may still
contain bridge tokens, but the scorer sees only full token-state sequences.
"""

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


class AlignmentScorer(torch.nn.Module):
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


def _unique_docs(rows: dict[str, list[dict[str, Any]]]) -> tuple[list[str], dict[str, int]]:
    docs: list[str] = []
    seen: dict[str, int] = {}
    for split_rows in rows.values():
        for row in split_rows:
            for candidate in list(row.get("candidates", []) or []):
                text = str(candidate.get("doc_text", "") or "")
                if text and text not in seen:
                    seen[text] = len(docs)
                    docs.append(text)
    return docs, seen


def _encode_hidden(stage995, model, tokenizer, text: str, max_tokens: int, device: torch.device) -> torch.Tensor:
    pad_id = int(getattr(tokenizer, "pad_token_id", 0) or 0)
    ids, _ = stage995._encode_with_offsets(tokenizer, text, int(max_tokens))
    mask_values = [1] * len(ids)
    while len(ids) < int(max_tokens):
        ids.append(pad_id)
        mask_values.append(0)
    input_ids = torch.tensor([ids[: int(max_tokens)]], dtype=torch.long, device=device)
    mask = torch.tensor(mask_values[: int(max_tokens)], dtype=torch.long, device=device)
    with torch.no_grad():
        hidden = model.encode(input_ids, mask.unsqueeze(0))[0].detach().float().cpu()
    active = hidden[mask.cpu().bool()]
    if len(active) == 0:
        active = hidden[:1]
    return F.normalize(active, dim=-1)


def _encode_many(stage995, model, tokenizer, texts: list[str], max_tokens: int, device: torch.device) -> list[torch.Tensor]:
    return [_encode_hidden(stage995, model, tokenizer, text, max_tokens, device) for text in texts]


def _candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _base_index(candidates: list[dict[str, Any]]) -> int:
    return max(
        range(len(candidates)),
        key=lambda idx: (float(candidates[idx].get("base_score", 0.0) or 0.0), -int(candidates[idx].get("rank", 9999) or 9999), -idx),
    )


def _features(row: dict[str, Any], candidate: dict[str, Any], q_hidden: torch.Tensor, d_hidden: torch.Tensor) -> torch.Tensor:
    sim = torch.matmul(q_hidden, d_hidden.T)
    qmax = sim.max(dim=1).values
    dmax = sim.max(dim=0).values
    flat = sim.flatten()
    top = torch.topk(flat, k=min(8, int(flat.numel()))).values.tolist()
    top = top + [0.0] * (8 - len(top))
    thresholds = [0.65, 0.75, 0.85, 0.9]
    q_counts = [(qmax >= threshold).float().mean().item() for threshold in thresholds]
    d_counts = [(dmax >= threshold).float().mean().item() for threshold in thresholds]
    op = str(row.get("operation", "") or "")
    values = [
        float(candidate.get("base_score", 0.0) or 0.0),
        1.0 / float(candidate.get("rank", 9999) or 9999),
        float(q_hidden.shape[0]) / 128.0,
        float(d_hidden.shape[0]) / 128.0,
        float(qmax.max().item()),
        float(qmax.mean().item()),
        float(qmax.median().item()),
        float(dmax.max().item()),
        float(dmax.mean().item()),
        float(dmax.median().item()),
        *[float(x) for x in top],
        *q_counts,
        *d_counts,
        1.0 if op == "composition" else 0.0,
        1.0 if op == "relation" else 0.0,
    ]
    return torch.tensor(values, dtype=torch.float32)


def _examples(rows: list[dict[str, Any]], q_hidden: list[torch.Tensor], d_hidden: list[torch.Tensor], doc_to_idx: dict[str, int]):
    out = []
    for row_idx, row in enumerate(rows):
        for candidate in list(row.get("candidates", []) or []):
            feature = _features(row, candidate, q_hidden[row_idx], d_hidden[doc_to_idx[str(candidate.get("doc_text", "") or "")]])
            label = float(bool(candidate.get("is_exact") or candidate.get("is_answer_match")))
            out.append((feature, label))
    return out


def _score_rows(model, rows, q_hidden, d_hidden, doc_to_idx, alpha: float) -> dict[str, Any]:
    answer = exact = base_answer = base_exact = 0
    by_operation: dict[str, dict[str, int]] = {}
    with torch.no_grad():
        model.eval()
        for row_idx, row in enumerate(rows):
            op = str(row.get("operation", "unknown"))
            stats = by_operation.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0})
            stats["rows"] += 1
            candidates = list(row.get("candidates", []) or [])
            scored = []
            for cand_idx, candidate in enumerate(candidates):
                feature = _features(row, candidate, q_hidden[row_idx], d_hidden[doc_to_idx[str(candidate.get("doc_text", "") or "")]]).unsqueeze(0)
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
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--max-query-tokens", type=int, default=128)
    parser.add_argument("--max-doc-tokens", type=int, default=128)
    parser.add_argument("--steps", type=int, default=600)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.001)
    parser.add_argument("--positive-weight", type=float, default=2.0)
    parser.add_argument("--alpha-sweep", default="0,0.1,0.25,0.5,0.75,1.0")
    parser.add_argument("--seed", type=int, default=1003)
    parser.add_argument("--output-state", type=Path, default=Path("runs/local/artifacts/stage1003_fulltoken_alignment_scorer_state.pt"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1003_fulltoken_alignment_scorer_summary.json"))
    args = parser.parse_args()

    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    repo_root = args.repo_root.resolve()
    stage995 = _load_module(repo_root / "scripts/train_stage995_encoder_span_pair_equality_comparator.py", "stage995")
    retrieval_eval = stage995._load_retrieval_eval(repo_root)
    device = torch.device(str(args.device))
    rows = _rows_by_split(args.targets_jsonl)
    docs, doc_to_idx = _unique_docs(rows)
    base_model, tokenizer, _ = retrieval_eval._load_model(args.bundle_dir.resolve(), repo_root=repo_root, device=device)
    base_model.eval()
    query_hidden = {
        split: _encode_many(stage995, base_model, tokenizer, [str(row.get("query_text", "") or "") for row in split_rows], int(args.max_query_tokens), device)
        for split, split_rows in rows.items()
    }
    doc_hidden = _encode_many(stage995, base_model, tokenizer, docs, int(args.max_doc_tokens), device)
    examples = _examples(rows["train"], query_hidden["train"], doc_hidden, doc_to_idx)
    dim = int(examples[0][0].numel())
    model = AlignmentScorer(dim, int(args.hidden_dim))
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))
    pos_weight = torch.tensor(float(args.positive_weight), dtype=torch.float32)
    alphas = [float(item) for item in str(args.alpha_sweep).split(",") if item.strip()]
    best_state = None
    best_key = None
    history = []
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
            cal_scores = [_score_rows(model, rows["calibration"], query_hidden["calibration"], doc_hidden, doc_to_idx, alpha) for alpha in alphas]
            selected = max(cal_scores, key=lambda item: (item["answer"], item["exact"], -item["alpha"]))
            history.append({"step": step, "loss": float(loss.item()), "selected_calibration": selected})
            key = (selected["answer"], selected["exact"])
            if best_key is None or key > best_key:
                best_key = key
                best_state = {name: value.detach().clone() for name, value in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    cal_scores = [_score_rows(model, rows["calibration"], query_hidden["calibration"], doc_hidden, doc_to_idx, alpha) for alpha in alphas]
    selected = max(cal_scores, key=lambda item: (item["answer"], item["exact"], -item["alpha"]))
    eval_score = _score_rows(model, rows["eval"], query_hidden["eval"], doc_hidden, doc_to_idx, float(selected["alpha"]))
    args.output_state.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model_state": model.state_dict(), "dim": dim, "hidden_dim": int(args.hidden_dim), "alpha": float(selected["alpha"])}, args.output_state)
    summary = {
        "artifact_kind": "stage1003_fulltoken_alignment_scorer",
        "status": "completed_fulltoken_alignment_probe",
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "examples": len(examples),
        "positive_examples": int(sum(item[1] for item in examples)),
        "calibration_selected": selected,
        "eval": eval_score,
        "history": history,
        "output_state": str(args.output_state),
        "stage1000_span_located_soft_count_answer_exact": [158, 142],
        "decision": "Uses full query/doc token-state alignment features and does not read query_bridge/candidate bridge fields or qpair/dpair span locations at eval. Rendered text still contains bridge tokens, so this tests locator removal before bridge-token removal.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
