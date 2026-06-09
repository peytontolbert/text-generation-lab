#!/usr/bin/env python3
"""Train relation-specific learned entity/slot equality thresholds without pair anchors."""

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


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _rows_by_split(path: Path) -> dict[str, list[dict[str, Any]]]:
    rows = {"train": [], "calibration": [], "eval": []}
    for row in _iter_jsonl(path):
        if str(row.get("operation", "")) == "relation":
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


def _encode_channel(stage995, model, tokenizer, records, *, key: str, prefix: str, pattern, device):
    return stage995._span_vectors_with_suffixes(
        model,
        tokenizer,
        [{"text": r["text"], "suffixes": r[key]} for r in records],
        prefix=prefix,
        pattern=pattern,
        max_tokens=32,
        device=device,
    )


def _pair_examples(rows, q_items, d_items, doc_to_idx, channel: str):
    out = []
    for row_idx, row in enumerate(rows):
        q = q_items[row_idx][channel]
        for candidate in list(row.get("candidates", []) or []):
            d = d_items[doc_to_idx[str(candidate.get("doc_text", "") or "")]][channel]
            for qi, qs in enumerate(q["suffixes"]):
                for di, ds in enumerate(d["suffixes"]):
                    out.append((q["vectors"][qi], d["vectors"][di], float(str(qs) == str(ds))))
    return out


def _train_eq(examples, hidden_dim: int, steps: int, batch_size: int, lr: float, seed: int):
    random.seed(seed)
    model = Eq(int(examples[0][0].numel()), hidden_dim)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.001)
    pos = max(1.0, (len(examples) - sum(x[2] for x in examples)) / max(1.0, sum(x[2] for x in examples)))
    pos_weight = torch.tensor(float(pos), dtype=torch.float32)
    for _ in range(steps):
        batch = random.choices(examples, k=batch_size)
        q = torch.stack([x[0] for x in batch])
        d = torch.stack([x[1] for x in batch])
        y = torch.tensor([x[2] for x in batch], dtype=torch.float32)
        loss = F.binary_cross_entropy_with_logits(model(q, d), y, pos_weight=pos_weight)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
    return model, pos


def _max_prob(model, q, d) -> float:
    best = 0.0
    with torch.no_grad():
        for qi in range(len(q["vectors"])):
            for di in range(len(d["vectors"])):
                prob = torch.sigmoid(model(q["vectors"][qi].unsqueeze(0), d["vectors"][di].unsqueeze(0))).item()
                best = max(best, float(prob))
    return best


def _hit(candidate):
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _base_idx(candidates):
    return max(range(len(candidates)), key=lambda i: (float(candidates[i].get("base_score", 0.0) or 0.0), -int(candidates[i].get("rank", 9999) or 9999), -i))


def _score(rows, q_items, d_items, doc_to_idx, ent_model, slot_model, ent_t: float, slot_t: float):
    answer = exact = base_answer = base_exact = selected_rows = 0
    for row_idx, row in enumerate(rows):
        candidates = list(row.get("candidates", []) or [])
        q = q_items[row_idx]
        pool = []
        for idx, candidate in enumerate(candidates):
            d = d_items[doc_to_idx[str(candidate.get("doc_text", "") or "")]]
            ent_prob = _max_prob(ent_model, q["ent"], d["ent"])
            slot_prob = _max_prob(slot_model, q["slot"], d["slot"])
            if ent_prob >= ent_t and slot_prob >= slot_t:
                pool.append(idx)
        if pool:
            pred = max(pool, key=lambda i: (float(candidates[i].get("base_score", 0.0) or 0.0), -int(candidates[i].get("rank", 9999) or 9999), -i))
            selected_rows += 1
        else:
            pred = _base_idx(candidates)
        base = _base_idx(candidates)
        ans, ex = _hit(candidates[pred])
        bans, bex = _hit(candidates[base])
        answer += ans
        exact += ex
        base_answer += bans
        base_exact += bex
    return {"rows": len(rows), "answer": answer, "exact": exact, "base_answer": base_answer, "base_exact": base_exact, "selected_rows": selected_rows, "entity_threshold": ent_t, "slot_threshold": slot_t}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1013_no_anchor_targets.jsonl"))
    parser.add_argument("--bundle-dir", type=Path, default=Path("runs/local/artifacts/pocketpal_controller_100m_stage976_stage975_pair_teacher_loadable_v415"))
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--steps", type=int, default=800)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--threshold-sweep", default="0.05,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9")
    parser.add_argument("--query-entity-prefix", default="qent")
    parser.add_argument("--doc-entity-prefix", default="dent")
    parser.add_argument("--query-slot-prefix", default="qslot")
    parser.add_argument("--doc-slot-prefix", default="dslot")
    parser.add_argument("--seed", type=int, default=1020)
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1020_relation_entity_slot_threshold_summary.json"))
    args = parser.parse_args()

    stage995 = _load_module(args.repo_root.resolve() / "scripts/train_stage995_encoder_span_pair_equality_comparator.py", "stage995")
    retrieval_eval = stage995._load_retrieval_eval(args.repo_root.resolve())
    device = torch.device(str(args.device))
    rows = _rows_by_split(args.targets_jsonl)
    docs, doc_to_idx = _unique_docs(rows)
    base_model, tokenizer, _ = retrieval_eval._load_model(args.bundle_dir.resolve(), repo_root=args.repo_root.resolve(), device=device)
    base_model.eval()
    q_ent_pattern = _prefix_re(str(args.query_entity_prefix))
    d_ent_pattern = _prefix_re(str(args.doc_entity_prefix))
    q_slot_pattern = _prefix_re(str(args.query_slot_prefix))
    d_slot_pattern = _prefix_re(str(args.doc_slot_prefix))
    q_records = {split: _records([str(row.get("query_text", "") or "") for row in split_rows], ent_pattern=q_ent_pattern, slot_pattern=q_slot_pattern) for split, split_rows in rows.items()}
    d_records = _records(docs, ent_pattern=d_ent_pattern, slot_pattern=d_slot_pattern)
    q_items = {}
    for split in rows:
        q_ent = _encode_channel(stage995, base_model, tokenizer, q_records[split], key="ent", prefix=str(args.query_entity_prefix), pattern=q_ent_pattern, device=device)
        q_slot = _encode_channel(stage995, base_model, tokenizer, q_records[split], key="slot", prefix=str(args.query_slot_prefix), pattern=q_slot_pattern, device=device)
        q_items[split] = [{"ent": q_ent[i], "slot": q_slot[i]} for i in range(len(q_ent))]
    d_ent = _encode_channel(stage995, base_model, tokenizer, d_records, key="ent", prefix=str(args.doc_entity_prefix), pattern=d_ent_pattern, device=device)
    d_slot = _encode_channel(stage995, base_model, tokenizer, d_records, key="slot", prefix=str(args.doc_slot_prefix), pattern=d_slot_pattern, device=device)
    d_items = [{"ent": d_ent[i], "slot": d_slot[i]} for i in range(len(d_ent))]
    ent_examples = _pair_examples(rows["train"], q_items["train"], d_items, doc_to_idx, "ent")
    slot_examples = _pair_examples(rows["train"], q_items["train"], d_items, doc_to_idx, "slot")
    ent_model, ent_pos_weight = _train_eq(ent_examples, int(args.hidden_dim), int(args.steps), int(args.batch_size), float(args.learning_rate), int(args.seed))
    slot_model, slot_pos_weight = _train_eq(slot_examples, int(args.hidden_dim), int(args.steps), int(args.batch_size), float(args.learning_rate), int(args.seed) + 1)
    thresholds = [float(x) for x in str(args.threshold_sweep).split(",") if x.strip()]
    cal_scores = [_score(rows["calibration"], q_items["calibration"], d_items, doc_to_idx, ent_model, slot_model, et, st) for et in thresholds for st in thresholds]
    selected = max(cal_scores, key=lambda x: (x["answer"], x["exact"], x["selected_rows"], -x["entity_threshold"] - x["slot_threshold"]))
    eval_score = _score(rows["eval"], q_items["eval"], d_items, doc_to_idx, ent_model, slot_model, float(selected["entity_threshold"]), float(selected["slot_threshold"]))
    summary = {
        "artifact_kind": "stage1020_relation_entity_slot_threshold",
        "status": "completed_relation_threshold_probe",
        "targets_jsonl": str(args.targets_jsonl),
        "entity_examples": len(ent_examples),
        "slot_examples": len(slot_examples),
        "entity_positive_weight": ent_pos_weight,
        "slot_positive_weight": slot_pos_weight,
        "eq_parameter_count_each": sum(p.numel() for p in ent_model.parameters()),
        "calibration_selected": selected,
        "eval": eval_score,
        "stage1018_relation_schema_ceiling": [99, 99],
        "stage1019_relation_policy_distilled": [49, 49],
        "schema_prefixes": {
            "query_entity": str(args.query_entity_prefix),
            "doc_entity": str(args.doc_entity_prefix),
            "query_slot": str(args.query_slot_prefix),
            "doc_slot": str(args.doc_slot_prefix),
        },
        "decision": "Relation-only learned entity/slot equality with thresholded base fallback. No pair anchors are used.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
