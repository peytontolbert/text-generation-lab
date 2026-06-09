#!/usr/bin/env python3
"""Train a schema-marker equality/count scorer without pair anchors."""

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


QENT = re.compile(r"\bqent_([A-Za-z0-9]+)\b")
DENT = re.compile(r"\bdent_([A-Za-z0-9]+)\b")
QSLOT = re.compile(r"\bqslot_([A-Za-z0-9]+)\b")
DSLOT = re.compile(r"\bdslot_([A-Za-z0-9]+)\b")


def _prefix_re(prefix: str) -> re.Pattern[str]:
    return re.compile(rf"\b{re.escape(prefix)}_([A-Za-z0-9]+)\b")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Eq(torch.nn.Module):
    def __init__(self, dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(torch.nn.Linear(dim * 4, hidden_dim), torch.nn.GELU(), torch.nn.Linear(hidden_dim, 1))

    def forward(self, q: torch.Tensor, d: torch.Tensor) -> torch.Tensor:
        return self.net(torch.cat([q, d, q * d, (q - d).abs()], dim=-1)).squeeze(-1)


class CandidateScorer(torch.nn.Module):
    def __init__(self, dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(torch.nn.Linear(dim, hidden_dim), torch.nn.GELU(), torch.nn.Linear(hidden_dim, 1))

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


def _records(texts: list[str], *, ent_pattern, slot_pattern) -> list[dict[str, Any]]:
    return [{"text": text, "ent": ent_pattern.findall(text), "slot": slot_pattern.findall(text)} for text in texts]


def _encode_tokens(stage995, model, tokenizer, records, *, ent_prefix: str, slot_prefix: str, device: torch.device):
    ent_records = [{"text": r["text"], "suffixes": r["ent"]} for r in records]
    slot_records = [{"text": r["text"], "suffixes": r["slot"]} for r in records]
    ent = stage995._span_vectors_with_suffixes(model, tokenizer, ent_records, prefix=ent_prefix, pattern=stage995._prefix_re(ent_prefix), max_tokens=32, device=device)
    slot = stage995._span_vectors_with_suffixes(model, tokenizer, slot_records, prefix=slot_prefix, pattern=stage995._prefix_re(slot_prefix), max_tokens=32, device=device)
    return [{"ent": ent[i], "slot": slot[i]} for i in range(len(records))]


def _eq_examples(q_items, d_items, rows, doc_to_idx):
    out = []
    for row_idx, row in enumerate(rows):
        q = q_items[row_idx]
        for candidate in list(row.get("candidates", []) or []):
            d = d_items[doc_to_idx[str(candidate.get("doc_text", "") or "")]]
            for channel in ["ent", "slot"]:
                for qi, qs in enumerate(q[channel]["suffixes"]):
                    for di, ds in enumerate(d[channel]["suffixes"]):
                        out.append((q[channel]["vectors"][qi], d[channel]["vectors"][di], float(str(qs) == str(ds))))
    return out


def _max_probs(eq_model, q, d, channel: str) -> list[float]:
    probs = []
    with torch.no_grad():
        for qi in range(len(q[channel]["vectors"])):
            best = 0.0
            for di in range(len(d[channel]["vectors"])):
                prob = torch.sigmoid(eq_model(q[channel]["vectors"][qi].unsqueeze(0), d[channel]["vectors"][di].unsqueeze(0))).item()
                best = max(best, float(prob))
            probs.append(best)
    return probs


def _features(eq_model, row, candidate, q, d) -> torch.Tensor:
    ent = _max_probs(eq_model, q, d, "ent")
    slot = _max_probs(eq_model, q, d, "slot")
    values = [
        float(candidate.get("base_score", 0.0) or 0.0),
        1.0 / float(candidate.get("rank", 9999) or 9999),
        float(len(ent)) / 4.0,
        float(len(slot)) / 4.0,
        max(ent or [0.0]),
        sum(ent) / float(len(ent) or 1),
        sum(1.0 for x in ent if x >= 0.1) / 4.0,
        sum(1.0 for x in ent if x >= 0.5) / 4.0,
        max(slot or [0.0]),
        sum(slot) / float(len(slot) or 1),
        sum(1.0 for x in slot if x >= 0.1) / 4.0,
        sum(1.0 for x in slot if x >= 0.5) / 4.0,
        1.0 if str(row.get("operation")) == "composition" else 0.0,
        1.0 if str(row.get("operation")) == "relation" else 0.0,
    ]
    return torch.tensor(values, dtype=torch.float32)


def _schema_policy_label(row, candidate, policy: dict[str, tuple[int, int]]) -> float:
    op = str(row.get("operation", "unknown"))
    ent_min, slot_min = policy.get(op, (0, 0))
    q_ent = set(_prefix_re("entity").findall(str(row.get("query_text", "") or "")))
    q_ent.update(QENT.findall(str(row.get("query_text", "") or "")))
    q_slot = set(_prefix_re("slot").findall(str(row.get("query_text", "") or "")))
    q_slot.update(QSLOT.findall(str(row.get("query_text", "") or "")))
    doc = str(candidate.get("doc_text", "") or "")
    d_ent = set(_prefix_re("entity").findall(doc))
    d_ent.update(DENT.findall(doc))
    d_slot = set(_prefix_re("slot").findall(doc))
    d_slot.update(DSLOT.findall(doc))
    return float(len(q_ent.intersection(d_ent)) >= ent_min and len(q_slot.intersection(d_slot)) >= slot_min)


def _candidate_examples(eq_model, rows, q_items, d_items, doc_to_idx, *, label_mode: str, schema_policy: dict[str, tuple[int, int]]):
    out = []
    for row_idx, row in enumerate(rows):
        q = q_items[row_idx]
        for candidate in list(row.get("candidates", []) or []):
            d = d_items[doc_to_idx[str(candidate.get("doc_text", "") or "")]]
            if label_mode == "schema_policy":
                label = _schema_policy_label(row, candidate, schema_policy)
            else:
                label = float(bool(candidate.get("is_exact") or candidate.get("is_answer_match")))
            out.append((_features(eq_model, row, candidate, q, d), label))
    return out


def _hit(candidate):
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _base_index(candidates):
    return max(range(len(candidates)), key=lambda i: (float(candidates[i].get("base_score", 0.0) or 0.0), -int(candidates[i].get("rank", 9999) or 9999), -i))


def _score_rows(eq_model, scorer, rows, q_items, d_items, doc_to_idx, alpha: float):
    answer = exact = base_answer = base_exact = 0
    by_op: dict[str, dict[str, int]] = {}
    with torch.no_grad():
        scorer.eval()
        for row_idx, row in enumerate(rows):
            op = str(row.get("operation", "unknown"))
            stats = by_op.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0})
            stats["rows"] += 1
            candidates = list(row.get("candidates", []) or [])
            q = q_items[row_idx]
            scored = []
            for cand_idx, candidate in enumerate(candidates):
                d = d_items[doc_to_idx[str(candidate.get("doc_text", "") or "")]]
                feature = _features(eq_model, row, candidate, q, d).unsqueeze(0)
                score = float(scorer(feature).item()) + float(alpha) * float(candidate.get("base_score", 0.0) or 0.0)
                scored.append((cand_idx, score))
            pred = max(scored, key=lambda item: (item[1], -item[0]))[0]
            base = _base_index(candidates)
            ans, ex = _hit(candidates[pred])
            bans, bex = _hit(candidates[base])
            answer += ans
            exact += ex
            base_answer += bans
            base_exact += bex
            stats["answer"] += ans
            stats["exact"] += ex
            stats["base_answer"] += bans
            stats["base_exact"] += bex
    return {"rows": len(rows), "answer": answer, "exact": exact, "base_answer": base_answer, "base_exact": base_exact, "alpha": float(alpha), "by_operation": by_op}


def _score_rows_threshold(eq_model, scorer, rows, q_items, d_items, doc_to_idx, threshold: float):
    answer = exact = base_answer = base_exact = selected_rows = 0
    by_op: dict[str, dict[str, int]] = {}
    with torch.no_grad():
        scorer.eval()
        for row_idx, row in enumerate(rows):
            op = str(row.get("operation", "unknown"))
            stats = by_op.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0, "selected_rows": 0})
            stats["rows"] += 1
            candidates = list(row.get("candidates", []) or [])
            q = q_items[row_idx]
            pool = []
            logits = []
            for cand_idx, candidate in enumerate(candidates):
                d = d_items[doc_to_idx[str(candidate.get("doc_text", "") or "")]]
                feature = _features(eq_model, row, candidate, q, d).unsqueeze(0)
                logit = float(scorer(feature).item())
                logits.append((cand_idx, logit))
                if torch.sigmoid(torch.tensor(logit)).item() >= float(threshold):
                    pool.append(cand_idx)
            if pool:
                pred = max(pool, key=lambda i: (float(candidates[i].get("base_score", 0.0) or 0.0), -int(candidates[i].get("rank", 9999) or 9999), -i))
                selected_rows += 1
                stats["selected_rows"] += 1
            else:
                pred = _base_index(candidates)
            base = _base_index(candidates)
            ans, ex = _hit(candidates[pred])
            bans, bex = _hit(candidates[base])
            answer += ans
            exact += ex
            base_answer += bans
            base_exact += bex
            stats["answer"] += ans
            stats["exact"] += ex
            stats["base_answer"] += bans
            stats["base_exact"] += bex
    return {"rows": len(rows), "answer": answer, "exact": exact, "base_answer": base_answer, "base_exact": base_exact, "threshold": float(threshold), "selected_rows": selected_rows, "by_operation": by_op}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1013_no_anchor_targets.jsonl"))
    parser.add_argument("--bundle-dir", type=Path, default=Path("runs/local/artifacts/pocketpal_controller_100m_stage976_stage975_pair_teacher_loadable_v415"))
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--eq-steps", type=int, default=500)
    parser.add_argument("--scorer-steps", type=int, default=600)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--scorer-hidden-dim", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--alpha-sweep", default="0,0.1,0.25,0.5,0.75,1.0")
    parser.add_argument("--label-mode", choices=["answer", "schema_policy"], default="answer")
    parser.add_argument("--threshold-sweep", default="0.05,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9")
    parser.add_argument("--query-entity-prefix", default="qent")
    parser.add_argument("--doc-entity-prefix", default="dent")
    parser.add_argument("--query-slot-prefix", default="qslot")
    parser.add_argument("--doc-slot-prefix", default="dslot")
    parser.add_argument("--seed", type=int, default=1015)
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1015_schema_marker_comparator_summary.json"))
    args = parser.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    repo_root = args.repo_root.resolve()
    stage995 = _load_module(repo_root / "scripts/train_stage995_encoder_span_pair_equality_comparator.py", "stage995")
    retrieval_eval = stage995._load_retrieval_eval(repo_root)
    device = torch.device(str(args.device))
    rows = _rows_by_split(args.targets_jsonl)
    docs, doc_to_idx = _unique_docs(rows)
    base_model, tokenizer, _ = retrieval_eval._load_model(args.bundle_dir.resolve(), repo_root=repo_root, device=device)
    base_model.eval()
    q_ent_pattern = _prefix_re(str(args.query_entity_prefix))
    d_ent_pattern = _prefix_re(str(args.doc_entity_prefix))
    q_slot_pattern = _prefix_re(str(args.query_slot_prefix))
    d_slot_pattern = _prefix_re(str(args.doc_slot_prefix))
    q_records = {split: _records([str(row.get("query_text", "") or "") for row in split_rows], ent_pattern=q_ent_pattern, slot_pattern=q_slot_pattern) for split, split_rows in rows.items()}
    d_records = _records(docs, ent_pattern=d_ent_pattern, slot_pattern=d_slot_pattern)
    q_items = {split: _encode_tokens(stage995, base_model, tokenizer, q_records[split], ent_prefix=str(args.query_entity_prefix), slot_prefix=str(args.query_slot_prefix), device=device) for split in rows}
    d_items = _encode_tokens(stage995, base_model, tokenizer, d_records, ent_prefix=str(args.doc_entity_prefix), slot_prefix=str(args.doc_slot_prefix), device=device)
    eq_examples = _eq_examples(q_items["train"], d_items, rows["train"], doc_to_idx)
    eq_model = Eq(int(eq_examples[0][0].numel()), int(args.hidden_dim))
    eq_opt = torch.optim.AdamW(eq_model.parameters(), lr=float(args.learning_rate), weight_decay=0.001)
    for _ in range(int(args.eq_steps)):
        batch = random.choices(eq_examples, k=int(args.batch_size))
        q = torch.stack([item[0] for item in batch])
        d = torch.stack([item[1] for item in batch])
        y = torch.tensor([item[2] for item in batch], dtype=torch.float32)
        loss = F.binary_cross_entropy_with_logits(eq_model(q, d), y)
        eq_opt.zero_grad(set_to_none=True)
        loss.backward()
        eq_opt.step()
    schema_policy = {"composition": (0, 2), "relation": (1, 1)}
    cand_examples = _candidate_examples(eq_model, rows["train"], q_items["train"], d_items, doc_to_idx, label_mode=str(args.label_mode), schema_policy=schema_policy)
    scorer = CandidateScorer(int(cand_examples[0][0].numel()), int(args.scorer_hidden_dim))
    scorer_opt = torch.optim.AdamW(scorer.parameters(), lr=float(args.learning_rate), weight_decay=0.001)
    pos_weight = torch.tensor(2.0, dtype=torch.float32)
    alphas = [float(item) for item in str(args.alpha_sweep).split(",") if item.strip()]
    best_state = None
    best_key = None
    history = []
    for step in range(1, int(args.scorer_steps) + 1):
        batch = random.choices(cand_examples, k=int(args.batch_size))
        x = torch.stack([item[0] for item in batch])
        y = torch.tensor([item[1] for item in batch], dtype=torch.float32)
        loss = F.binary_cross_entropy_with_logits(scorer(x), y, pos_weight=pos_weight)
        scorer_opt.zero_grad(set_to_none=True)
        loss.backward()
        scorer_opt.step()
        if step == 1 or step == int(args.scorer_steps) or step % 100 == 0:
            if str(args.label_mode) == "schema_policy":
                thresholds = [float(item) for item in str(args.threshold_sweep).split(",") if item.strip()]
                scores = [_score_rows_threshold(eq_model, scorer, rows["calibration"], q_items["calibration"], d_items, doc_to_idx, threshold) for threshold in thresholds]
                selected = max(scores, key=lambda item: (item["answer"], item["exact"], item["selected_rows"], -item["threshold"]))
            else:
                scores = [_score_rows(eq_model, scorer, rows["calibration"], q_items["calibration"], d_items, doc_to_idx, alpha) for alpha in alphas]
                selected = max(scores, key=lambda item: (item["answer"], item["exact"], -item["alpha"]))
            history.append({"step": step, "loss": float(loss.item()), "selected_calibration": selected})
            key = (selected["answer"], selected["exact"])
            if best_key is None or key > best_key:
                best_key = key
                best_state = {name: value.detach().clone() for name, value in scorer.state_dict().items()}
    if best_state is not None:
        scorer.load_state_dict(best_state)
    if str(args.label_mode) == "schema_policy":
        thresholds = [float(item) for item in str(args.threshold_sweep).split(",") if item.strip()]
        scores = [_score_rows_threshold(eq_model, scorer, rows["calibration"], q_items["calibration"], d_items, doc_to_idx, threshold) for threshold in thresholds]
        selected = max(scores, key=lambda item: (item["answer"], item["exact"], item["selected_rows"], -item["threshold"]))
        eval_score = _score_rows_threshold(eq_model, scorer, rows["eval"], q_items["eval"], d_items, doc_to_idx, float(selected["threshold"]))
    else:
        scores = [_score_rows(eq_model, scorer, rows["calibration"], q_items["calibration"], d_items, doc_to_idx, alpha) for alpha in alphas]
        selected = max(scores, key=lambda item: (item["answer"], item["exact"], -item["alpha"]))
        eval_score = _score_rows(eq_model, scorer, rows["eval"], q_items["eval"], d_items, doc_to_idx, float(selected["alpha"]))
    summary = {
        "artifact_kind": "stage1015_schema_marker_comparator",
        "status": "completed_schema_marker_comparator_probe",
        "targets_jsonl": str(args.targets_jsonl),
        "eq_parameter_count": sum(p.numel() for p in eq_model.parameters()),
        "scorer_parameter_count": sum(p.numel() for p in scorer.parameters()),
        "eq_examples": len(eq_examples),
        "candidate_examples": len(cand_examples),
        "candidate_label_mode": str(args.label_mode),
        "schema_policy": {k: list(v) for k, v in schema_policy.items()},
        "calibration_selected": selected,
        "eval": eval_score,
        "history": history,
        "stage1011_anchor_frontier_answer_exact": [158, 142],
        "stage1014_no_anchor_fulltoken_answer_exact": [82, 66],
        "schema_prefixes": {
            "query_entity": str(args.query_entity_prefix),
            "doc_entity": str(args.doc_entity_prefix),
            "query_slot": str(args.query_slot_prefix),
            "doc_slot": str(args.doc_slot_prefix),
        },
        "decision": "Uses schema-derived qent/dent and qslot/dslot marker equality instead of pair anchors. No qpair/dpair/anchor tokens are used.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
