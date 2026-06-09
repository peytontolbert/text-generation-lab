#!/usr/bin/env python3
"""Train encoder-owned schema equality/count heads for no-anchor rows."""

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


def _records(texts: list[str], *, ent_pattern: re.Pattern[str], slot_pattern: re.Pattern[str]) -> list[dict[str, Any]]:
    return [{"text": text, "ent": ent_pattern.findall(text), "slot": slot_pattern.findall(text)} for text in texts]


def _encode_channel(stage995, model, tokenizer, records, *, key: str, prefix: str, pattern: re.Pattern[str], device: torch.device):
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
    torch.manual_seed(seed)
    model = Eq(int(examples[0][0].numel()), hidden_dim)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.001)
    positives = sum(item[2] for item in examples)
    pos_weight = torch.tensor(max(1.0, (len(examples) - positives) / max(1.0, positives)), dtype=torch.float32)
    for _ in range(steps):
        batch = random.choices(examples, k=batch_size)
        q = torch.stack([item[0] for item in batch])
        d = torch.stack([item[1] for item in batch])
        y = torch.tensor([item[2] for item in batch], dtype=torch.float32)
        loss = F.binary_cross_entropy_with_logits(model(q, d), y, pos_weight=pos_weight)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
    return model, float(pos_weight.item())


def _match_count(model, q, d, threshold: float) -> int:
    count = 0
    with torch.no_grad():
        for qi in range(len(q["vectors"])):
            matched = False
            for di in range(len(d["vectors"])):
                prob = torch.sigmoid(model(q["vectors"][qi].unsqueeze(0), d["vectors"][di].unsqueeze(0))).item()
                matched = matched or float(prob) >= float(threshold)
            count += int(matched)
    return count


def _hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _base_idx(candidates: list[dict[str, Any]]) -> int:
    return max(
        range(len(candidates)),
        key=lambda i: (float(candidates[i].get("base_score", 0.0) or 0.0), -int(candidates[i].get("rank", 9999) or 9999), -i),
    )


def _score(rows, q_items, d_items, doc_to_idx, ent_model, slot_model, policy: dict[str, tuple[int, int]], ent_t: float, slot_t: float):
    answer = exact = base_answer = base_exact = selected_rows = 0
    by_op: dict[str, dict[str, int]] = {}
    with torch.no_grad():
        ent_model.eval()
        slot_model.eval()
        for row_idx, row in enumerate(rows):
            op = str(row.get("operation", "unknown"))
            stats = by_op.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0, "selected_rows": 0})
            stats["rows"] += 1
            candidates = list(row.get("candidates", []) or [])
            q = q_items[row_idx]
            ent_min, slot_min = policy.get(op, (0, 0))
            pool: list[int] = []
            for idx, candidate in enumerate(candidates):
                d = d_items[doc_to_idx[str(candidate.get("doc_text", "") or "")]]
                ent_matches = _match_count(ent_model, q["ent"], d["ent"], ent_t) if ent_min > 0 else ent_min
                slot_matches = _match_count(slot_model, q["slot"], d["slot"], slot_t) if slot_min > 0 else slot_min
                if ent_matches >= ent_min and slot_matches >= slot_min:
                    pool.append(idx)
            if pool:
                pred = max(pool, key=lambda i: (float(candidates[i].get("base_score", 0.0) or 0.0), -int(candidates[i].get("rank", 9999) or 9999), -i))
                selected_rows += 1
                stats["selected_rows"] += 1
            else:
                pred = _base_idx(candidates)
            base = _base_idx(candidates)
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
    return {
        "rows": len(rows),
        "answer": answer,
        "exact": exact,
        "base_answer": base_answer,
        "base_exact": base_exact,
        "selected_rows": selected_rows,
        "entity_threshold": float(ent_t),
        "slot_threshold": float(slot_t),
        "by_operation": by_op,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1013_no_anchor_targets.jsonl"))
    parser.add_argument("--bundle-dir", type=Path, default=Path("runs/local/artifacts/pocketpal_controller_100m_stage976_stage975_pair_teacher_loadable_v415"))
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--steps", type=int, default=1200)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--threshold-sweep", default="0.01,0.02,0.05,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9")
    parser.add_argument("--seed", type=int, default=1027)
    parser.add_argument("--output-state", type=Path, default=Path("runs/local/artifacts/stage1027_encoder_schema_count_comparator_state.pt"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1027_encoder_schema_count_comparator_summary.json"))
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    stage995 = _load_module(repo_root / "scripts/train_stage995_encoder_span_pair_equality_comparator.py", "stage995")
    retrieval_eval = stage995._load_retrieval_eval(repo_root)
    device = torch.device(str(args.device))
    rows = _rows_by_split(args.targets_jsonl)
    docs, doc_to_idx = _unique_docs(rows)
    base_model, tokenizer, _ = retrieval_eval._load_model(args.bundle_dir.resolve(), repo_root=repo_root, device=device)
    base_model.eval()
    q_records = {split: _records([str(row.get("query_text", "") or "") for row in split_rows], ent_pattern=QENT, slot_pattern=QSLOT) for split, split_rows in rows.items()}
    d_records = _records(docs, ent_pattern=DENT, slot_pattern=DSLOT)
    q_items = {}
    for split in rows:
        q_ent = _encode_channel(stage995, base_model, tokenizer, q_records[split], key="ent", prefix="qent", pattern=QENT, device=device)
        q_slot = _encode_channel(stage995, base_model, tokenizer, q_records[split], key="slot", prefix="qslot", pattern=QSLOT, device=device)
        q_items[split] = [{"ent": q_ent[i], "slot": q_slot[i]} for i in range(len(q_ent))]
    d_ent = _encode_channel(stage995, base_model, tokenizer, d_records, key="ent", prefix="dent", pattern=DENT, device=device)
    d_slot = _encode_channel(stage995, base_model, tokenizer, d_records, key="slot", prefix="dslot", pattern=DSLOT, device=device)
    d_items = [{"ent": d_ent[i], "slot": d_slot[i]} for i in range(len(d_ent))]

    ent_examples = _pair_examples(rows["train"], q_items["train"], d_items, doc_to_idx, "ent")
    slot_examples = _pair_examples(rows["train"], q_items["train"], d_items, doc_to_idx, "slot")
    ent_model, ent_pos_weight = _train_eq(ent_examples, int(args.hidden_dim), int(args.steps), int(args.batch_size), float(args.learning_rate), int(args.seed))
    slot_model, slot_pos_weight = _train_eq(slot_examples, int(args.hidden_dim), int(args.steps), int(args.batch_size), float(args.learning_rate), int(args.seed) + 1)

    policy = {"composition": (0, 2), "relation": (1, 1)}
    thresholds = [float(item) for item in str(args.threshold_sweep).split(",") if item.strip()]
    cal_scores = [_score(rows["calibration"], q_items["calibration"], d_items, doc_to_idx, ent_model, slot_model, policy, et, st) for et in thresholds for st in thresholds]
    selected = max(cal_scores, key=lambda x: (x["answer"], x["exact"], x["selected_rows"], -x["entity_threshold"] - x["slot_threshold"]))
    eval_score = _score(rows["eval"], q_items["eval"], d_items, doc_to_idx, ent_model, slot_model, policy, float(selected["entity_threshold"]), float(selected["slot_threshold"]))

    args.output_state.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "entity_model_state": ent_model.state_dict(),
            "slot_model_state": slot_model.state_dict(),
            "dim": int(ent_examples[0][0].numel()),
            "hidden_dim": int(args.hidden_dim),
            "entity_threshold": float(selected["entity_threshold"]),
            "slot_threshold": float(selected["slot_threshold"]),
            "schema_policy": {key: list(value) for key, value in policy.items()},
        },
        args.output_state,
    )
    summary = {
        "artifact_kind": "stage1027_encoder_schema_count_comparator",
        "status": "completed_encoder_schema_count_probe",
        "targets_jsonl": str(args.targets_jsonl),
        "bundle_dir": str(args.bundle_dir),
        "output_state": str(args.output_state),
        "entity_examples": len(ent_examples),
        "slot_examples": len(slot_examples),
        "entity_positive_weight": ent_pos_weight,
        "slot_positive_weight": slot_pos_weight,
        "eq_parameter_count_each": sum(p.numel() for p in ent_model.parameters()),
        "eq_total_parameter_count": sum(p.numel() for p in ent_model.parameters()) + sum(p.numel() for p in slot_model.parameters()),
        "schema_policy": {key: list(value) for key, value in policy.items()},
        "calibration_selected": selected,
        "eval": eval_score,
        "stage1024_char_schema_eval_answer_exact": [150, 134],
        "stage1015_schema_marker_eval_answer_exact": [65, 49],
        "stage1020_relation_eval_answer_exact": [69, 69],
        "stage1021_side_neutral_relation_eval_answer_exact": [71, 71],
        "decision": "Frozen-100M encoder schema-token equality/count probe. Eval uses learned equality probabilities over encoder hidden states, not deterministic suffix matching or the Stage1024 character comparator.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
