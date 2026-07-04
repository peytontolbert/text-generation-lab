from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping


AUTHORITY_CLOSED = {
    "model_execution": False,
    "training": False,
    "runtime": False,
    "source_body_emission": False,
    "scoring_authorized": False,
}

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")


def tokens(text: str) -> set[str]:
    return {tok.lower() for tok in TOKEN_RE.findall(text)}


def _text(row: Mapping[str, Any]) -> str:
    parts = []
    for key in ["task", "query", "prompt", "evidence", "source", "target", "label", "objective_family"]:
        val = row.get(key)
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, (dict, list)):
            parts.append(json.dumps(val, sort_keys=True))
    return "\n".join(parts)


def _tags(row: Mapping[str, Any]) -> set[str]:
    raw = row.get("task_tags", row.get("tags", []))
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return {str(x) for x in raw}
    return set()


def _label(row: Mapping[str, Any]) -> str:
    return str(row.get("label") or row.get("target_label") or row.get("route") or row.get("answer") or "")


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / max(1, len(a | b))


def influence_row(eval_row: Mapping[str, Any], train_row: Mapping[str, Any]) -> dict[str, Any]:
    eval_tokens = tokens(_text(eval_row))
    train_tokens = tokens(_text(train_row))
    token_overlap = jaccard(eval_tokens, train_tokens)
    tag_overlap = jaccard(_tags(eval_row), _tags(train_row))
    same_objective = str(eval_row.get("objective_family") or "") == str(train_row.get("objective_family") or "")
    same_label = bool(_label(eval_row) and _label(eval_row) == _label(train_row))
    conflicting_label = bool(_label(eval_row) and _label(train_row) and _label(eval_row) != _label(train_row) and (token_overlap >= 0.25 or tag_overlap >= 0.5))
    source_trust = float(train_row.get("source_trust", 1.0) or 0.0)
    label_issue = float(train_row.get("label_issue_score", 0.0) or 0.0)
    loss_mean = float(train_row.get("loss_mean", train_row.get("loss", 0.0)) or 0.0)
    helpful = (
        0.55 * token_overlap
        + 0.25 * tag_overlap
        + (0.15 if same_objective else 0.0)
        + (0.20 if same_label else 0.0)
        + 0.05 * source_trust
        - 0.20 * label_issue
    )
    harmful = (
        (0.45 if conflicting_label else 0.0)
        + 0.30 * label_issue
        + (0.10 if loss_mean >= 1.5 else 0.0)
        + 0.10 * token_overlap
        - (0.10 if same_label else 0.0)
    )
    if harmful >= 0.45 and harmful > helpful:
        influence_type = "harmful_conflicting"
    elif helpful >= 0.35:
        influence_type = "helpful_neighbor"
    elif token_overlap < 0.12 and tag_overlap < 0.25:
        influence_type = "missing_neighborhood"
    else:
        influence_type = "weak_or_ambiguous"
    return {
        "eval_id": str(eval_row.get("row_id") or eval_row.get("eval_id") or eval_row.get("id") or ""),
        "train_id": str(train_row.get("row_id") or train_row.get("train_id") or train_row.get("id") or ""),
        "token_overlap": token_overlap,
        "tag_overlap": tag_overlap,
        "same_objective": same_objective,
        "same_label": same_label,
        "conflicting_label": conflicting_label,
        "helpful_score": round(helpful, 6),
        "harmful_score": round(harmful, 6),
        "influence_type": influence_type,
        "authority": AUTHORITY_CLOSED,
    }


def attribution_card(eval_rows: list[Mapping[str, Any]], train_rows: list[Mapping[str, Any]], *, top_k: int = 5) -> dict[str, Any]:
    eval_cards = []
    all_types: Counter[str] = Counter()
    for eval_row in eval_rows:
        pairs = [influence_row(eval_row, train_row) for train_row in train_rows]
        pairs.sort(key=lambda r: (r["helpful_score"] - r["harmful_score"], r["token_overlap"], r["tag_overlap"]), reverse=True)
        harmful = sorted(pairs, key=lambda r: (r["harmful_score"], r["token_overlap"]), reverse=True)
        selected = pairs[:top_k]
        selected_harmful = [row for row in harmful if row["influence_type"] == "harmful_conflicting"][:top_k]
        type_counts = Counter(row["influence_type"] for row in pairs)
        all_types.update(type_counts)
        if type_counts.get("helpful_neighbor", 0) == 0:
            recommendation = "generate_or_retrieve_neighbors"
        elif type_counts.get("harmful_conflicting", 0) > 0:
            recommendation = "review_harmful_conflicts"
        else:
            recommendation = "keep_current_neighborhood"
        eval_cards.append({
            "eval_id": str(eval_row.get("row_id") or eval_row.get("eval_id") or eval_row.get("id") or ""),
            "recommendation": recommendation,
            "type_counts": dict(sorted(type_counts.items())),
            "top_helpful_candidates": selected,
            "top_harmful_candidates": selected_harmful,
            "authority": AUTHORITY_CLOSED,
        })
    return {
        "eval_rows": len(eval_rows),
        "train_rows": len(train_rows),
        "top_k": top_k,
        "global_type_counts": dict(sorted(all_types.items())),
        "eval_cards": eval_cards,
        "authority": AUTHORITY_CLOSED,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic training-data attribution/influence contract.")
    parser.add_argument("--eval", type=Path)
    parser.add_argument("--train", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    eval_rows = read_jsonl(args.eval) if args.eval else [{"row_id": "eval_auth", "task": "fix auth token expiry", "task_tags": ["auth", "pytest"], "label": "FIX_AUTH"}]
    train_rows = read_jsonl(args.train) if args.train else [
        {"row_id": "good", "task": "repair auth token expiry pytest", "task_tags": ["auth", "pytest"], "label": "FIX_AUTH"},
        {"row_id": "bad", "task": "repair auth token expiry pytest", "task_tags": ["auth", "pytest"], "label": "CHANGE_DOCS", "label_issue_score": 0.8},
    ]
    card = attribution_card(eval_rows, train_rows, top_k=args.top_k)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
