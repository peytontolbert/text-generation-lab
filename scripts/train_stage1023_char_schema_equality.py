#!/usr/bin/env python3
"""Train a small character-position schema equality model for no-anchor rows."""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F


ENTITY = re.compile(r"\b(?:qent|dent|entity)_([A-Za-z0-9]+)\b")
SLOT = re.compile(r"\b(?:qslot|dslot|slot)_([A-Za-z0-9]+)\b")
ALPHABET = "0123456789abcdef"
INDEX = {ch: i for i, ch in enumerate(ALPHABET)}


class CharEq(torch.nn.Module):
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


def _features(a: str, b: str, max_len: int = 16) -> torch.Tensor:
    a = str(a).lower()
    b = str(b).lower()
    values: list[float] = []
    matches = 0
    for idx in range(max_len):
        ca = a[idx] if idx < len(a) else ""
        cb = b[idx] if idx < len(b) else ""
        same = float(ca == cb and ca != "")
        matches += int(same)
        values.append(same)
        values.append(float(INDEX.get(ca, -1)) / 15.0 if ca in INDEX else -1.0)
        values.append(float(INDEX.get(cb, -1)) / 15.0 if cb in INDEX else -1.0)
    values.extend([
        float(len(a) == len(b)),
        float(matches) / float(max_len),
        float(a == b),
    ])
    return torch.tensor(values, dtype=torch.float32)


def _examples(rows: list[dict[str, Any]], channel: str):
    pattern = ENTITY if channel == "entity" else SLOT
    out = []
    for row in rows:
        q = pattern.findall(str(row.get("query_text", "") or ""))
        for candidate in list(row.get("candidates", []) or []):
            d = pattern.findall(str(candidate.get("doc_text", "") or ""))
            for qs in q:
                for ds in d:
                    out.append((_features(qs, ds), float(str(qs) == str(ds))))
    return out


def _train(examples, hidden_dim: int, steps: int, batch_size: int, lr: float, seed: int):
    random.seed(seed)
    torch.manual_seed(seed)
    model = CharEq(int(examples[0][0].numel()), hidden_dim)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.001)
    positives = sum(x[1] for x in examples)
    pos_weight = torch.tensor(max(1.0, (len(examples) - positives) / max(1.0, positives)), dtype=torch.float32)
    for _ in range(steps):
        batch = random.choices(examples, k=batch_size)
        x = torch.stack([item[0] for item in batch])
        y = torch.tensor([item[1] for item in batch], dtype=torch.float32)
        loss = F.binary_cross_entropy_with_logits(model(x), y, pos_weight=pos_weight)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
    return model, float(pos_weight.item())


def _max_prob(model, q: list[str], d: list[str]) -> float:
    best = 0.0
    with torch.no_grad():
        for qs in q:
            for ds in d:
                prob = torch.sigmoid(model(_features(qs, ds).unsqueeze(0))).item()
                best = max(best, float(prob))
    return best


def _match_count(model, q: list[str], d: list[str], threshold: float) -> int:
    count = 0
    with torch.no_grad():
        for qs in q:
            matched = False
            for ds in d:
                prob = torch.sigmoid(model(_features(qs, ds).unsqueeze(0))).item()
                matched = matched or float(prob) >= float(threshold)
            count += int(matched)
    return count


def _hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _base_idx(candidates):
    return max(range(len(candidates)), key=lambda i: (float(candidates[i].get("base_score", 0.0) or 0.0), -int(candidates[i].get("rank", 9999) or 9999), -i))


def _score(rows: list[dict[str, Any]], ent_model, slot_model, policy: dict[str, tuple[int, int]], ent_t: float, slot_t: float):
    answer = exact = base_answer = base_exact = selected_rows = 0
    by_op: dict[str, dict[str, int]] = {}
    for row in rows:
        op = str(row.get("operation", "unknown"))
        stats = by_op.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0, "selected_rows": 0})
        stats["rows"] += 1
        candidates = list(row.get("candidates", []) or [])
        q_ent = ENTITY.findall(str(row.get("query_text", "") or ""))
        q_slot = SLOT.findall(str(row.get("query_text", "") or ""))
        ent_min, slot_min = policy.get(op, (0, 0))
        pool = []
        for idx, candidate in enumerate(candidates):
            doc = str(candidate.get("doc_text", "") or "")
            ent_matches = _match_count(ent_model, q_ent, ENTITY.findall(doc), ent_t) if ent_min > 0 else ent_min
            slot_matches = _match_count(slot_model, q_slot, SLOT.findall(doc), slot_t) if slot_min > 0 else slot_min
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
    return {"rows": len(rows), "answer": answer, "exact": exact, "base_answer": base_answer, "base_exact": base_exact, "selected_rows": selected_rows, "entity_threshold": ent_t, "slot_threshold": slot_t, "by_operation": by_op}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1013_no_anchor_targets.jsonl"))
    parser.add_argument("--steps", type=int, default=800)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--threshold-sweep", default="0.05,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9")
    parser.add_argument("--seed", type=int, default=1023)
    parser.add_argument("--output-state", type=Path, default=Path(""))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1023_char_schema_equality_summary.json"))
    args = parser.parse_args()

    rows = _rows_by_split(args.targets_jsonl)
    ent_model, ent_pos = _train(_examples(rows["train"], "entity"), int(args.hidden_dim), int(args.steps), int(args.batch_size), float(args.learning_rate), int(args.seed))
    slot_model, slot_pos = _train(_examples(rows["train"], "slot"), int(args.hidden_dim), int(args.steps), int(args.batch_size), float(args.learning_rate), int(args.seed) + 1)
    policy = {"composition": (0, 2), "relation": (1, 1)}
    thresholds = [float(x) for x in str(args.threshold_sweep).split(",") if x.strip()]
    cal_scores = [_score(rows["calibration"], ent_model, slot_model, policy, et, st) for et in thresholds for st in thresholds]
    selected = max(cal_scores, key=lambda x: (x["answer"], x["exact"], x["selected_rows"], -x["entity_threshold"] - x["slot_threshold"]))
    ev = _score(rows["eval"], ent_model, slot_model, policy, float(selected["entity_threshold"]), float(selected["slot_threshold"]))
    if str(args.output_state):
        args.output_state.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "entity_model_state": ent_model.state_dict(),
                "slot_model_state": slot_model.state_dict(),
                "dim": int(_features("0" * 16, "0" * 16).numel()),
                "hidden_dim": int(args.hidden_dim),
                "entity_threshold": float(selected["entity_threshold"]),
                "slot_threshold": float(selected["slot_threshold"]),
                "schema_policy": {k: list(v) for k, v in policy.items()},
            },
            args.output_state,
        )
    summary = {
        "artifact_kind": "stage1023_char_schema_equality",
        "status": "completed_char_schema_equality_probe",
        "targets_jsonl": str(args.targets_jsonl),
        "parameter_count_each": sum(p.numel() for p in ent_model.parameters()),
        "output_state": str(args.output_state) if str(args.output_state) else None,
        "entity_positive_weight": ent_pos,
        "slot_positive_weight": slot_pos,
        "schema_policy": {k: list(v) for k, v in policy.items()},
        "calibration_selected": selected,
        "eval": ev,
        "stage1018_deterministic_schema_ceiling": [150, 134],
        "stage1022_full_no_anchor_schema_hybrid": [334, 317],
        "decision": "Learned character-position equality over schema suffixes. No pair anchors are used; this is a counted learned string-equality circuit, not encoder-owned equality.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
