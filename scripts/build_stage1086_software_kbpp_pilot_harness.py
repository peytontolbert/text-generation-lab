#!/usr/bin/env python3
"""Build a small executable software-KBPP pilot harness."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


TEMPLATES: list[dict[str, Any]] = [
    {
        "category": "api_binding",
        "function_name": "clamp_value",
        "contract": "Return x clipped into the inclusive [lo, hi] interval.",
        "buggy_code": "def clamp_value(x, lo, hi):\n    return min(max(x, hi), lo)\n",
        "fixed_code": "def clamp_value(x, lo, hi):\n    return min(max(x, lo), hi)\n",
        "public_tests": ["assert clamp_value(5, 1, 10) == 5", "assert clamp_value(0, 1, 10) == 1"],
        "hidden_tests": ["assert clamp_value(11, 1, 10) == 10", "assert clamp_value(-3, -2, 7) == -2"],
        "invariant": "output >= lo and output <= hi",
    },
    {
        "category": "bug_repair",
        "function_name": "sum_to_n",
        "contract": "Return the sum of all integers from 0 through n inclusive.",
        "buggy_code": "def sum_to_n(n):\n    return sum(range(n))\n",
        "fixed_code": "def sum_to_n(n):\n    return sum(range(n + 1))\n",
        "public_tests": ["assert sum_to_n(3) == 6", "assert sum_to_n(0) == 0"],
        "hidden_tests": ["assert sum_to_n(10) == 55", "assert sum_to_n(1) == 1"],
        "invariant": "inclusive upper bound",
    },
    {
        "category": "generation",
        "function_name": "unique_preserve_order",
        "contract": "Return the input values with duplicates removed while preserving first-seen order.",
        "buggy_code": "def unique_preserve_order(values):\n    return sorted(set(values))\n",
        "fixed_code": "def unique_preserve_order(values):\n    out = []\n    seen = set()\n    for value in values:\n        if value not in seen:\n            seen.add(value)\n            out.append(value)\n    return out\n",
        "public_tests": ["assert unique_preserve_order([2, 1, 2]) == [2, 1]"],
        "hidden_tests": ["assert unique_preserve_order(['b', 'a', 'b', 'c']) == ['b', 'a', 'c']"],
        "invariant": "first occurrence order is stable",
    },
    {
        "category": "trace_debugging",
        "function_name": "safe_divide",
        "contract": "Return None when denominator is zero; otherwise return numerator divided by denominator.",
        "buggy_code": "def safe_divide(numerator, denominator):\n    return numerator / denominator\n",
        "fixed_code": "def safe_divide(numerator, denominator):\n    if denominator == 0:\n        return None\n    return numerator / denominator\n",
        "public_tests": ["assert safe_divide(8, 2) == 4"],
        "hidden_tests": ["assert safe_divide(5, 0) is None", "assert safe_divide(-9, 3) == -3"],
        "invariant": "zero denominator must not raise",
    },
    {
        "category": "api_binding",
        "function_name": "parse_int_or_default",
        "contract": "Convert text to int; return default when conversion fails.",
        "buggy_code": "def parse_int_or_default(text, default):\n    return int(text)\n",
        "fixed_code": "def parse_int_or_default(text, default):\n    try:\n        return int(text)\n    except (TypeError, ValueError):\n        return default\n",
        "public_tests": ["assert parse_int_or_default('7', 0) == 7"],
        "hidden_tests": ["assert parse_int_or_default('x', 3) == 3", "assert parse_int_or_default(None, -1) == -1"],
        "invariant": "invalid input returns default",
    },
    {
        "category": "bug_repair",
        "function_name": "normalize_email",
        "contract": "Strip surrounding whitespace and lowercase an email string.",
        "buggy_code": "def normalize_email(email):\n    return email.lower()\n",
        "fixed_code": "def normalize_email(email):\n    return email.strip().lower()\n",
        "public_tests": ["assert normalize_email('A@B.COM') == 'a@b.com'"],
        "hidden_tests": ["assert normalize_email('  User@Example.COM ') == 'user@example.com'"],
        "invariant": "strip then lowercase",
    },
    {
        "category": "generation",
        "function_name": "count_vowels",
        "contract": "Count vowels in text, case-insensitively.",
        "buggy_code": "def count_vowels(text):\n    return sum(1 for ch in text if ch in 'aeiou')\n",
        "fixed_code": "def count_vowels(text):\n    return sum(1 for ch in text.lower() if ch in 'aeiou')\n",
        "public_tests": ["assert count_vowels('tree') == 2"],
        "hidden_tests": ["assert count_vowels('AEIOU') == 5", "assert count_vowels('Sky') == 0"],
        "invariant": "case-insensitive vowel membership",
    },
    {
        "category": "repo_navigation",
        "function_name": "flatten_once",
        "contract": "Flatten exactly one list nesting level.",
        "buggy_code": "def flatten_once(items):\n    return [value for group in items for value in flatten_once(group)]\n",
        "fixed_code": "def flatten_once(items):\n    return [value for group in items for value in group]\n",
        "public_tests": ["assert flatten_once([[1, 2], [3]]) == [1, 2, 3]"],
        "hidden_tests": ["assert flatten_once([['a'], ['b', 'c']]) == ['a', 'b', 'c']"],
        "invariant": "only one level is flattened",
    },
]


def _task_from_template(template: dict[str, Any], index: int, split: str) -> dict[str, Any]:
    task_id = f"stage1086_{split}_{index:04d}_{template['function_name']}"
    prompt = (
        f"Repair the Python function `{template['function_name']}`.\n"
        f"Contract: {template['contract']}\n"
        "Return the complete corrected function only.\n\n"
        f"{template['buggy_code']}"
    )
    return {
        "task_id": task_id,
        "benchmark": "stage1086_software_kbpp_pilot",
        "split": split,
        "language": "python",
        "category": template["category"],
        "function_name": template["function_name"],
        "prompt": prompt,
        "buggy_code": template["buggy_code"],
        "reference_code": template["fixed_code"],
        "public_tests": template["public_tests"],
        "hidden_tests": template["hidden_tests"],
        "proof_units": {
            "contract": template["contract"],
            "invariant": template["invariant"],
            "relevant_symbol": template["function_name"],
            "repair_kind": template["category"],
        },
        "verified_decision_bits": 8,
        "score_fields": ["public_tests_pass", "hidden_tests_pass", "function_symbol_preserved", "syntax_valid"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("runs/local/artifacts/stage1086_software_kbpp_pilot"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1086_software_kbpp_pilot_summary.json"))
    parser.add_argument("--train-copies", type=int, default=16)
    parser.add_argument("--eval-copies", type=int, default=4)
    parser.add_argument("--hidden-copies", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1086)
    args = parser.parse_args()

    random.seed(int(args.seed))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    split_copies = {"train": int(args.train_copies), "eval": int(args.eval_copies), "hidden": int(args.hidden_copies)}
    all_rows: list[dict[str, Any]] = []
    by_split: dict[str, int] = {}
    by_category: dict[str, dict[str, int]] = {}
    for split, copies in split_copies.items():
        rows: list[dict[str, Any]] = []
        for copy_index in range(copies):
            templates = list(TEMPLATES)
            random.shuffle(templates)
            for template_index, template in enumerate(templates):
                row = _task_from_template(template, copy_index * len(TEMPLATES) + template_index, split)
                rows.append(row)
                all_rows.append(row)
                by_category.setdefault(split, {}).setdefault(template["category"], 0)
                by_category[split][template["category"]] += 1
        by_split[split] = len(rows)
        with (args.output_dir / f"{split}.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
    manifest = {
        "artifact_kind": "stage1086_software_kbpp_pilot_manifest",
        "train_path": str(args.output_dir / "train.jsonl"),
        "eval_path": str(args.output_dir / "eval.jsonl"),
        "hidden_path": str(args.output_dir / "hidden.jsonl"),
        "prediction_schema": {"task_id": "string", "candidate_code": "complete Python function string"},
        "verifier_script": "scripts/score_stage1086_software_kbpp_predictions.py",
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "artifact_kind": "stage1086_software_kbpp_pilot_harness",
        "status": "completed_software_kbpp_pilot_task_export",
        "manifest": str(args.output_dir / "manifest.json"),
        "by_split": by_split,
        "by_category": by_category,
        "rows": len(all_rows),
        "verified_decision_bits": sum(int(row["verified_decision_bits"]) for row in all_rows),
        "decision": "Creates a small executable software-KBPP pilot with hidden tests and proof fields. This is an instrumentation harness, not a 100M-vs-7B claim.",
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
