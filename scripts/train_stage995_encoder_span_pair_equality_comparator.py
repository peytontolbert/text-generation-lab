#!/usr/bin/env python3
"""Train a pair-level encoder span equality comparator for qpair/dpair tokens."""

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

QPAIR_RE = re.compile(r"\bqpair_([A-Za-z0-9]+)\b")
DPAIR_RE = re.compile(r"\bdpair_([A-Za-z0-9]+)\b")


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
    rows = {"train": [], "calibration": [], "eval": []}
    for row in _iter_jsonl(path):
        if str(row.get("operation", "")) in {"composition", "relation"}:
            rows.setdefault(str(row.get("split")), []).append(row)
    return rows


def _prefix_re(prefix: str) -> re.Pattern[str]:
    return re.compile(rf"\b{re.escape(prefix)}_([A-Za-z0-9]+)\b")


def _unique_docs(rows: list[dict[str, Any]], *, use_bridge_fields: bool = True, doc_pattern: re.Pattern[str] = DPAIR_RE) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        for candidate in list(row.get("candidates", []) or []):
            text = str(candidate.get("doc_text", "") or "")
            if text and text not in seen:
                seen.add(text)
                bridge = candidate.get("bridge", {}) or {}
                suffixes = [str(item) for item in bridge.get("dpair", []) or []] if use_bridge_fields else []
                if not suffixes:
                    suffixes = doc_pattern.findall(text)
                out.append({"text": text, "suffixes": suffixes})
    return out


def _encode_with_offsets(tokenizer, text: str, max_tokens: int) -> tuple[list[int], list[tuple[int, int]]]:
    inner = getattr(tokenizer, "tokenizer", None)
    if inner is not None:
        encoded = inner.encode(str(text), add_special_tokens=True)
        return list(encoded.ids)[:max_tokens], list(encoded.offsets)[:max_tokens]
    ids = tokenizer.encode(str(text), max_length=max_tokens)
    return list(ids)[:max_tokens], [(0, 0)] * min(len(ids), max_tokens)


def _token_indices(offsets: list[tuple[int, int]], span: tuple[int, int], mask: torch.Tensor) -> list[int]:
    start, end = span
    return [
        idx
        for idx, (tok_start, tok_end) in enumerate(offsets)
        if int(mask[idx].item()) and tok_end > start and tok_start < end
    ]


def _span_vectors_with_suffixes(model, tokenizer, records: list[dict[str, Any]], *, prefix: str, pattern: re.Pattern[str], max_tokens: int, device: torch.device) -> list[dict[str, Any]]:
    pad_id = int(getattr(tokenizer, "pad_token_id", 0) or 0)
    out: list[dict[str, Any]] = []
    with torch.no_grad():
        for record in records:
            text = str(record.get("text", "") or "")
            suffixes = [str(item) for item in record.get("suffixes", []) or []]
            if not suffixes:
                suffixes = pattern.findall(text)
            vectors: list[torch.Tensor] = []
            hidden_dim = None
            for suffix in suffixes:
                bridge_token = f"{prefix}_{suffix}"
                ids, _ = _encode_with_offsets(tokenizer, bridge_token, int(max_tokens))
                mask_values = [1] * len(ids)
                while len(ids) < int(max_tokens):
                    ids.append(pad_id)
                    mask_values.append(0)
                input_ids = torch.tensor([ids[: int(max_tokens)]], dtype=torch.long, device=device)
                mask = torch.tensor(mask_values[: int(max_tokens)], dtype=torch.long, device=device)
                hidden = model.encode(input_ids, mask.unsqueeze(0))[0].detach().float().cpu()
                active = hidden[mask.cpu().bool()]
                hidden_dim = int(hidden.shape[-1])
                if len(active):
                    vectors.append(active.mean(dim=0))
            if vectors:
                matrix = F.normalize(torch.stack(vectors, dim=0), dim=-1)
            else:
                if hidden_dim is None:
                    probe_ids, _ = _encode_with_offsets(tokenizer, f"{prefix}_empty", int(max_tokens))
                    probe_mask = torch.ones((1, len(probe_ids)), dtype=torch.long, device=device)
                    probe_ids_tensor = torch.tensor([probe_ids], dtype=torch.long, device=device)
                    hidden_dim = int(model.encode(probe_ids_tensor, probe_mask)[0].shape[-1])
                matrix = torch.empty((0, int(hidden_dim)), dtype=torch.float32)
            out.append({"suffixes": suffixes, "vectors": matrix})
    return out


class PairEq(torch.nn.Module):
    def __init__(self, dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(dim * 4, int(hidden_dim)),
            torch.nn.GELU(),
            torch.nn.Linear(int(hidden_dim), 1),
        )

    def forward(self, q: torch.Tensor, d: torch.Tensor) -> torch.Tensor:
        return self.net(torch.cat([q, d, q * d, (q - d).abs()], dim=-1)).squeeze(-1)


def _pair_examples(rows: list[dict[str, Any]], q_spans: list[dict[str, Any]], d_spans: list[dict[str, Any]], doc_to_idx: dict[str, int]) -> list[tuple[torch.Tensor, torch.Tensor, float]]:
    examples: list[tuple[torch.Tensor, torch.Tensor, float]] = []
    for row_idx, row in enumerate(rows):
        q = q_spans[row_idx]
        for candidate in list(row.get("candidates", []) or []):
            d = d_spans[doc_to_idx[str(candidate.get("doc_text", "") or "")]]
            for qi, qs in enumerate(q["suffixes"]):
                for di, ds in enumerate(d["suffixes"]):
                    examples.append((q["vectors"][qi], d["vectors"][di], float(qs == ds)))
    return examples


def _candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _score_rows(model: PairEq, rows: list[dict[str, Any]], q_spans: list[dict[str, Any]], d_spans: list[dict[str, Any]], doc_to_idx: dict[str, int], threshold: float | dict[str, float]) -> dict[str, Any]:
    answer = exact = base_answer = base_exact = predicted_rows = 0
    by_operation: dict[str, dict[str, int]] = {}
    with torch.no_grad():
        model.eval()
        for row_idx, row in enumerate(rows):
            op = str(row.get("operation", "unknown"))
            stats = by_operation.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0, "predicted_rows": 0})
            stats["rows"] += 1
            op_threshold = float(threshold.get(op, threshold.get("default", 0.5))) if isinstance(threshold, dict) else float(threshold)
            candidates = list(row.get("candidates", []) or [])
            base_idx = max(range(len(candidates)), key=lambda idx: (float(candidates[idx].get("base_score", 0.0) or 0.0), -int(candidates[idx].get("rank", 9999) or 9999), -idx))
            q = q_spans[row_idx]
            pool: list[int] = []
            for cand_idx, candidate in enumerate(candidates):
                d = d_spans[doc_to_idx[str(candidate.get("doc_text", "") or "")]]
                selected_arity = int(candidate.get("selected_min_pair_overlap", 0) or 0)
                count = 0
                if len(q["vectors"]) and len(d["vectors"]) and selected_arity > 0:
                    for qi in range(len(q["vectors"])):
                        row_match = False
                        for di in range(len(d["vectors"])):
                            prob = torch.sigmoid(model(q["vectors"][qi].unsqueeze(0), d["vectors"][di].unsqueeze(0))).item()
                            row_match = row_match or prob >= op_threshold
                        count += int(row_match)
                if selected_arity > 0 and count >= selected_arity:
                    pool.append(cand_idx)
            if pool:
                predicted_rows += 1
                stats["predicted_rows"] += 1
                pred_idx = max(pool, key=lambda idx: (float(candidates[idx].get("base_score", 0.0) or 0.0), -int(candidates[idx].get("rank", 9999) or 9999), -idx))
            else:
                pred_idx = base_idx
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
    return {"rows": len(rows), "answer": answer, "exact": exact, "base_answer": base_answer, "base_exact": base_exact, "predicted_rows": predicted_rows, "threshold": threshold, "by_operation": by_operation}


def _select_operation_thresholds(model: PairEq, rows: list[dict[str, Any]], q_spans: list[dict[str, Any]], d_spans: list[dict[str, Any]], doc_to_idx: dict[str, int], thresholds: list[float]) -> dict[str, Any]:
    by_threshold = [_score_rows(model, rows, q_spans, d_spans, doc_to_idx, threshold) for threshold in thresholds]
    selected: dict[str, float] = {}
    selected_stats: dict[str, Any] = {}
    operations = sorted({str(row.get("operation", "unknown")) for row in rows})
    for op in operations:
        best = max(
            by_threshold,
            key=lambda item: (
                item["by_operation"].get(op, {}).get("answer", 0),
                item["by_operation"].get(op, {}).get("exact", 0),
                item["by_operation"].get(op, {}).get("predicted_rows", 0),
                -float(item["threshold"]),
            ),
        )
        selected[op] = float(best["threshold"])
        selected_stats[op] = best["by_operation"].get(op, {})
    return {"thresholds_by_operation": selected, "selected_calibration_by_operation": selected_stats}


def train(args: argparse.Namespace) -> dict[str, Any]:
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    repo_root = Path(args.repo_root).resolve()
    retrieval_eval = _load_retrieval_eval(repo_root)
    rows = _rows_by_split(Path(args.targets_jsonl))
    base_model, tokenizer, _ = retrieval_eval._load_model(Path(args.bundle_dir).resolve(), repo_root=repo_root, device=device)
    base_model.eval()
    for parameter in base_model.parameters():
        parameter.requires_grad_(False)
    use_bridge_fields = not bool(args.use_text_regex_suffixes)
    query_prefix = str(args.pair_token_prefix or "qpair")
    doc_prefix = str(args.pair_token_prefix or "dpair")
    query_pattern = _prefix_re(query_prefix)
    doc_pattern = _prefix_re(doc_prefix)
    docs = {split: _unique_docs(split_rows, use_bridge_fields=use_bridge_fields, doc_pattern=doc_pattern) for split, split_rows in rows.items()}
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
    q_spans = {split: _span_vectors_with_suffixes(base_model, tokenizer, query_records[split], prefix=query_prefix, pattern=query_pattern, max_tokens=int(args.max_query_tokens), device=device) for split in rows}
    d_spans = {split: _span_vectors_with_suffixes(base_model, tokenizer, docs[split], prefix=doc_prefix, pattern=doc_pattern, max_tokens=int(args.max_doc_tokens), device=device) for split in rows}
    examples = _pair_examples(rows["train"], q_spans["train"], d_spans["train"], doc_to_idx["train"])
    if not examples:
        raise RuntimeError("no pair examples")
    dim = int(examples[0][0].numel())
    model = PairEq(dim, int(args.hidden_dim))
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))
    thresholds = [float(item) for item in str(args.threshold_sweep).split(",") if item.strip()]
    best_state = None
    best_key = None
    history = []
    for step in range(1, int(args.steps) + 1):
        batch = random.choices(examples, k=int(args.batch_size))
        q = torch.stack([item[0] for item in batch])
        d = torch.stack([item[1] for item in batch])
        y = torch.tensor([item[2] for item in batch], dtype=torch.float32)
        logits = model(q, d)
        pos_weight = torch.tensor(float(args.positive_weight), dtype=torch.float32)
        loss = F.binary_cross_entropy_with_logits(logits, y, pos_weight=pos_weight)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % int(args.eval_every) == 0:
            cal_scores = [_score_rows(model, rows["calibration"], q_spans["calibration"], d_spans["calibration"], doc_to_idx["calibration"], threshold) for threshold in thresholds]
            selected = max(cal_scores, key=lambda item: (item["answer"], item["exact"], item["predicted_rows"], -item["threshold"]))
            history.append({"step": step, "loss": float(loss.detach().item()), "selected_calibration": selected})
            key = (selected["answer"], selected["exact"], selected["predicted_rows"])
            if best_key is None or key > best_key:
                best_key = key
                best_state = {name: value.detach().clone() for name, value in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    cal_scores = [_score_rows(model, rows["calibration"], q_spans["calibration"], d_spans["calibration"], doc_to_idx["calibration"], threshold) for threshold in thresholds]
    selected = max(cal_scores, key=lambda item: (item["answer"], item["exact"], item["predicted_rows"], -item["threshold"]))
    eval_score = _score_rows(model, rows["eval"], q_spans["eval"], d_spans["eval"], doc_to_idx["eval"], float(selected["threshold"]))
    op_thresholds = _select_operation_thresholds(model, rows["calibration"], q_spans["calibration"], d_spans["calibration"], doc_to_idx["calibration"], thresholds)
    op_eval_score = _score_rows(model, rows["eval"], q_spans["eval"], d_spans["eval"], doc_to_idx["eval"], op_thresholds["thresholds_by_operation"])
    if str(args.output_state):
        state_path = Path(args.output_state)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "model_state": model.state_dict(),
                "dim": dim,
                "hidden_dim": int(args.hidden_dim),
                "global_threshold": float(selected["threshold"]),
                "thresholds_by_operation": op_thresholds["thresholds_by_operation"],
            },
            state_path,
        )
    summary = {
        "artifact_kind": str(args.artifact_kind),
        "status": "completed_encoder_span_pair_equality_probe",
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "targets_jsonl": str(Path(args.targets_jsonl).resolve()),
        "pair_training_examples": len(examples),
        "suffix_source": "rendered_text_regex" if bool(args.use_text_regex_suffixes) else "structured_bridge_fields",
        "pair_token_prefix": str(args.pair_token_prefix or "side_specific_qpair_dpair"),
        "positive_pair_examples": int(sum(item[2] for item in examples)),
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "steps": int(args.steps),
        "batch_size": int(args.batch_size),
        "positive_weight": float(args.positive_weight),
        "history": history,
        "calibration_selected": selected,
        "eval_with_calibration_threshold": eval_score,
        "operation_calibrated_thresholds": op_thresholds,
        "eval_with_operation_calibrated_thresholds": op_eval_score,
        "output_state": str(Path(args.output_state).resolve()) if str(args.output_state) else None,
        "stage981_pair_interface_eval_answer_exact_for_same_ops": {"composition": [58, 42], "relation": [100, 100], "combined": [158, 142]},
        "decision": "Trains pair-level equality from frozen 100M qpair/dpair span states and uses predicted equality counts at eval. Eval does not use suffix set intersection, but span locations are still found from qpair/dpair markers.",
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
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--eval-every", type=int, default=100)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.001)
    parser.add_argument("--positive-weight", type=float, default=1.0)
    parser.add_argument("--threshold-sweep", default="0.05,0.1,0.15,0.2,0.25,0.3,0.4,0.5,0.6,0.7,0.8,0.9")
    parser.add_argument("--seed", type=int, default=995)
    parser.add_argument("--artifact-kind", default="stage995_encoder_span_pair_equality_comparator")
    parser.add_argument("--output-state", default="")
    parser.add_argument("--use-text-regex-suffixes", action="store_true")
    parser.add_argument("--pair-token-prefix", default="")
    parser.add_argument("--output-json", required=True)
    train(parser.parse_args())


if __name__ == "__main__":
    main()
