from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import argparse
import json


def value_at(row: dict[str, Any], field: str) -> Any:
    cur: Any = row
    for part in field.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    if isinstance(cur, (dict, list)):
        return json.dumps(cur, sort_keys=True)
    return cur


def majority_exact(rows: list[dict[str, Any]], target_field: str) -> float:
    targets = [value_at(row, target_field) for row in rows]
    if not targets:
        return 0.0
    count = Counter(targets)
    return max(count.values()) / len(targets)


def single_feature_exact(rows: list[dict[str, Any]], feature_field: str, target_field: str) -> float:
    if not rows:
        return 0.0
    groups: dict[Any, Counter] = defaultdict(Counter)
    for row in rows:
        groups[value_at(row, feature_field)][value_at(row, target_field)] += 1
    correct = 0
    for row in rows:
        pred = groups[value_at(row, feature_field)].most_common(1)[0][0]
        correct += int(pred == value_at(row, target_field))
    return correct / len(rows)


def combo_feature_exact(rows: list[dict[str, Any]], feature_fields: tuple[str, ...], target_field: str) -> float:
    if not rows:
        return 0.0
    groups: dict[tuple[Any, ...], Counter] = defaultdict(Counter)
    for row in rows:
        key = tuple(value_at(row, field) for field in feature_fields)
        groups[key][value_at(row, target_field)] += 1
    correct = 0
    for row in rows:
        key = tuple(value_at(row, field) for field in feature_fields)
        pred = groups[key].most_common(1)[0][0]
        correct += int(pred == value_at(row, target_field))
    return correct / len(rows)


def audit_shortcuts(rows: list[dict[str, Any]], *, target_field: str, feature_fields: list[str], combo_size: int = 2, ceiling: float = 0.8) -> dict[str, Any]:
    singles = {field: single_feature_exact(rows, field, target_field) for field in feature_fields}
    combos: dict[str, float] = {}
    if combo_size >= 2:
        for i, left in enumerate(feature_fields):
            for right in feature_fields[i + 1:]:
                combos[f"{left}+{right}"] = combo_feature_exact(rows, (left, right), target_field)
    strongest_single = max(singles.values(), default=0.0)
    strongest_combo = max(combos.values(), default=0.0)
    return {
        "rows": len(rows),
        "target_field": target_field,
        "majority_exact": majority_exact(rows, target_field),
        "single_feature_exact": singles,
        "combo_feature_exact": combos,
        "strongest_single_feature_exact": strongest_single,
        "strongest_combo_feature_exact": strongest_combo,
        "strongest_baseline_exact": max(strongest_single, strongest_combo, majority_exact(rows, target_field)),
        "ceiling": ceiling,
        "training_blocked_by_shortcut_dominance": max(strongest_single, strongest_combo) >= ceiling,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows=[]
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            value=json.loads(line)
            if not isinstance(value, dict):
                raise ValueError('row is not object')
            rows.append(value)
    return rows


def parse_args() -> argparse.Namespace:
    parser=argparse.ArgumentParser(description='Deterministic shortcut baseline audit for JSONL manifests.')
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--target-field', required=True)
    parser.add_argument('--feature-field', action='append', default=[])
    parser.add_argument('--ceiling', type=float, default=0.8)
    parser.add_argument('--output', type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args=parse_args()
    card=audit_shortcuts(read_jsonl(args.manifest), target_field=args.target_field, feature_fields=args.feature_field, ceiling=args.ceiling)
    text=json.dumps(card, indent=2, sort_keys=True)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
    print(text, end='')
    raise SystemExit(1 if card['training_blocked_by_shortcut_dominance'] else 0)


if __name__ == '__main__':
    main()
