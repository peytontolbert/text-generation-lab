#!/usr/bin/env python3
"""Build and score a scaled typed-operator software-KBPP curriculum."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


OPERATORS = {
    "clamp_bounds": {
        "args": ["x", "lo", "hi"],
        "train_names": ["clip_number", "bound_value", "limit_score"],
        "test_names": ["clamp_value", "cap_reading"],
        "contract": "Return x clipped into the inclusive [lo, hi] interval.",
        "alt_contract": "Constrain x so it stays between lo and hi, including both endpoints.",
        "invariant": "output >= lo and output <= hi",
        "public": ["assert {fn}(5, 1, 10) == 5", "assert {fn}(0, 1, 10) == 1"],
        "hidden": ["assert {fn}(11, 1, 10) == 10", "assert {fn}(-3, -2, 7) == -2"],
        "buggy": "return min(max(x, hi), lo)",
    },
    "inclusive_sum": {
        "args": ["n"],
        "train_names": ["total_through", "sum_inclusive", "prefix_total"],
        "test_names": ["sum_to_n", "inclusive_total"],
        "contract": "Return the sum of all integers from 0 through n inclusive.",
        "alt_contract": "Add every integer from zero up to and including n.",
        "invariant": "inclusive upper bound",
        "public": ["assert {fn}(3) == 6", "assert {fn}(0) == 0"],
        "hidden": ["assert {fn}(10) == 55", "assert {fn}(1) == 1"],
        "buggy": "return sum(range(n))",
    },
    "unique_preserve_order": {
        "args": ["values"],
        "train_names": ["dedupe_stable", "unique_in_order", "first_seen_values"],
        "test_names": ["unique_preserve_order", "stable_unique"],
        "contract": "Return the input values with duplicates removed while preserving first-seen order.",
        "alt_contract": "Remove repeated values but keep the order of first occurrence.",
        "invariant": "first occurrence order is stable",
        "public": ["assert {fn}([2, 1, 2]) == [2, 1]"],
        "hidden": ["assert {fn}(['b', 'a', 'b', 'c']) == ['b', 'a', 'c']"],
        "buggy": "return sorted(set(values))",
    },
    "safe_divide": {
        "args": ["numerator", "denominator"],
        "train_names": ["divide_or_none", "guarded_divide", "ratio_or_none"],
        "test_names": ["safe_divide", "checked_divide"],
        "contract": "Return None when denominator is zero; otherwise return numerator divided by denominator.",
        "alt_contract": "Avoid division by zero by returning None; otherwise compute the quotient.",
        "invariant": "zero denominator must not raise",
        "public": ["assert {fn}(8, 2) == 4"],
        "hidden": ["assert {fn}(5, 0) is None", "assert {fn}(-9, 3) == -3"],
        "buggy": "return numerator / denominator",
    },
    "parse_int_default": {
        "args": ["text", "default"],
        "train_names": ["int_or_default", "parse_number_or", "coerce_int_default"],
        "test_names": ["parse_int_or_default", "to_int_or_default"],
        "contract": "Convert text to int; return default when conversion fails.",
        "alt_contract": "Parse an integer, falling back to default for invalid input.",
        "invariant": "invalid input returns default",
        "public": ["assert {fn}('7', 0) == 7"],
        "hidden": ["assert {fn}('x', 3) == 3", "assert {fn}(None, -1) == -1"],
        "buggy": "return int(text)",
    },
    "strip_then_lowercase": {
        "args": ["text"],
        "train_names": ["normalize_username", "clean_identifier", "canonical_text"],
        "test_names": ["normalize_email", "clean_label"],
        "contract": "Strip surrounding whitespace and lowercase a string.",
        "alt_contract": "Trim outer spaces, then convert all letters to lowercase.",
        "invariant": "strip then lowercase",
        "public": ["assert {fn}('A@B.COM') == 'a@b.com'"],
        "hidden": ["assert {fn}('  User@Example.COM ') == 'user@example.com'"],
        "buggy": "return text.lower()",
    },
    "case_insensitive_membership": {
        "args": ["text"],
        "train_names": ["count_name_vowels", "count_title_vowels", "vowels_in_word"],
        "test_names": ["count_vowels", "count_label_vowels"],
        "contract": "Count vowels in text, case-insensitively.",
        "alt_contract": "Count vowel characters regardless of uppercase or lowercase spelling.",
        "invariant": "case-insensitive vowel membership",
        "public": ["assert {fn}('tree') == 2"],
        "hidden": ["assert {fn}('AEIOU') == 5", "assert {fn}('Sky') == 0"],
        "buggy": "return sum(1 for ch in text if ch in 'aeiou')",
    },
    "one_level_flatten": {
        "args": ["items"],
        "train_names": ["flatten_groups", "flatten_batches", "one_level_items"],
        "test_names": ["flatten_once", "flatten_rows"],
        "contract": "Flatten exactly one list nesting level.",
        "alt_contract": "Concatenate child lists without recursively flattening deeper levels.",
        "invariant": "only one level is flattened",
        "public": ["assert {fn}([[1, 2], [3]]) == [1, 2, 3]"],
        "hidden": ["assert {fn}([['a'], ['b', 'c']]) == ['a', 'b', 'c']"],
        "buggy": "return [value for group in items for value in flatten_once(group)]",
    },
}


def _load_score_module(repo_root: Path):
    path = repo_root / "scripts/score_stage1086_software_kbpp_predictions.py"
    spec = importlib.util.spec_from_file_location("stage1086_score", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load score module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _materialize(fn: str, args: list[str], operator: str) -> str:
    if operator == "clamp_bounds":
        return f"def {fn}({', '.join(args)}):\n    return min(max(x, lo), hi)\n"
    if operator == "inclusive_sum":
        return f"def {fn}({', '.join(args)}):\n    return sum(range(n + 1))\n"
    if operator == "unique_preserve_order":
        return f"def {fn}({', '.join(args)}):\n    out = []\n    seen = set()\n    for value in values:\n        if value not in seen:\n            seen.add(value)\n            out.append(value)\n    return out\n"
    if operator == "safe_divide":
        return f"def {fn}({', '.join(args)}):\n    if denominator == 0:\n        return None\n    return numerator / denominator\n"
    if operator == "parse_int_default":
        return f"def {fn}({', '.join(args)}):\n    try:\n        return int(text)\n    except (TypeError, ValueError):\n        return default\n"
    if operator == "strip_then_lowercase":
        return f"def {fn}({', '.join(args)}):\n    return text.strip().lower()\n"
    if operator == "case_insensitive_membership":
        return f"def {fn}({', '.join(args)}):\n    return sum(1 for ch in text.lower() if ch in 'aeiou')\n"
    if operator == "one_level_flatten":
        return f"def {fn}({', '.join(args)}):\n    return [value for group in items for value in group]\n"
    return f"def {fn}({', '.join(args)}):\n    return None\n"


def _row(operator: str, name: str, split: str, use_alt: bool, index: int) -> dict[str, Any]:
    spec = OPERATORS[operator]
    args = list(spec["args"])
    contract = str(spec["alt_contract"] if use_alt else spec["contract"])
    function_code = f"def {name}({', '.join(args)}):\n    {spec['buggy']}\n"
    return {
        "benchmark": "stage1091_scaled_software_operator_curriculum",
        "task_id": f"stage1091_{split}_{index:04d}_{name}",
        "split": split,
        "category": "software_operator_induction",
        "language": "python",
        "function_name": name,
        "buggy_code": function_code,
        "reference_code": _materialize(name, args, operator),
        "public_tests": [item.format(fn=name) for item in spec["public"]],
        "hidden_tests": [item.format(fn=name) for item in spec["hidden"]],
        "prompt": f"Repair the Python function `{name}`.\nContract: {contract}\nReturn the complete corrected function only.\n\n{function_code}",
        "proof_units": {
            "contract": contract,
            "invariant": spec["invariant"],
            "operator": operator,
            "repair_kind": "software_operator_induction",
            "relevant_symbol": name,
        },
        "verified_decision_bits": 8,
        "score_fields": ["public_tests_pass", "hidden_tests_pass", "function_symbol_preserved", "syntax_valid"],
    }


def _build_rows() -> dict[str, list[dict[str, Any]]]:
    rows = {"train": [], "eval": [], "hidden": []}
    counters = Counter()
    for operator, spec in OPERATORS.items():
        for name in spec["train_names"]:
            rows["train"].append(_row(operator, str(name), "train", False, counters["train"]))
            counters["train"] += 1
        for name in spec["test_names"][:1]:
            rows["eval"].append(_row(operator, str(name), "eval", True, counters["eval"]))
            counters["eval"] += 1
        for name in spec["test_names"][1:]:
            rows["hidden"].append(_row(operator, str(name), "hidden", True, counters["hidden"]))
            counters["hidden"] += 1
    random.Random(1091).shuffle(rows["train"])
    random.Random(1092).shuffle(rows["eval"])
    random.Random(1093).shuffle(rows["hidden"])
    return rows


class NaiveBayes:
    def __init__(self) -> None:
        self.class_counts: Counter[str] = Counter()
        self.token_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.total_tokens: Counter[str] = Counter()
        self.vocab: set[str] = set()

    def fit(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            operator = str(row["proof_units"]["operator"])
            self.class_counts[operator] += 1
            text = f"{row['proof_units']['contract']} {row['proof_units']['invariant']}"
            for token in _tokenize(text):
                self.token_counts[operator][token] += 1
                self.total_tokens[operator] += 1
                self.vocab.add(token)

    def predict(self, row: dict[str, Any]) -> str:
        text = f"{row['proof_units']['contract']} {row['proof_units']['invariant']}"
        tokens = _tokenize(text)
        vocab_size = max(1, len(self.vocab))
        total_classes = sum(self.class_counts.values())
        scores: dict[str, float] = {}
        for operator, count in self.class_counts.items():
            score = math.log(count / total_classes)
            denom = self.total_tokens[operator] + vocab_size
            for token in tokens:
                score += math.log((self.token_counts[operator][token] + 1) / denom)
            scores[operator] = score
        return max(scores, key=scores.get)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _score(score_module, rows: list[dict[str, Any]], predictions: dict[str, str]) -> dict[str, Any]:
    scores = [score_module._score_task(row, predictions[str(row["task_id"])]) for row in rows]
    return {
        "rows": len(scores),
        "hidden_pass": sum(int(score["hidden_tests_pass"]) for score in scores),
        "public_pass": sum(int(score["public_tests_pass"]) for score in scores),
        "syntax_valid": sum(int(score["syntax_valid"]) for score in scores),
        "function_symbol_preserved": sum(int(score["function_symbol_preserved"]) for score in scores),
        "verified_decisions": sum(int(score["verified_decisions"]) for score in scores),
        "verified_decision_bits": sum(int(score["verified_decision_bits"]) for score in scores),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("runs/local/artifacts/stage1091_scaled_software_operator_curriculum"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1091_scaled_software_operator_curriculum_summary.json"))
    args = parser.parse_args()

    rows = _build_rows()
    for split, split_rows in rows.items():
        _write_jsonl(args.output_dir / f"{split}.jsonl", split_rows)
    manifest = {
        "artifact_kind": "stage1091_scaled_software_operator_curriculum_manifest",
        "train_path": str(args.output_dir / "train.jsonl"),
        "eval_path": str(args.output_dir / "eval.jsonl"),
        "hidden_path": str(args.output_dir / "hidden.jsonl"),
        "operators": sorted(OPERATORS),
        "holdout_rule": "eval/hidden function symbols and contract phrasings are held out from train",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    model = NaiveBayes()
    model.fit(rows["train"])
    score_module = _load_score_module(args.repo_root)
    results: dict[str, Any] = {}
    for split in ("eval", "hidden"):
        predictions: dict[str, str] = {}
        audit_rows: list[dict[str, Any]] = []
        for row in rows[split]:
            operator = model.predict(row)
            predictions[str(row["task_id"])] = _materialize(str(row["function_name"]), list(row["reference_code"].split("(", 1)[1].split(")", 1)[0].split(", ")), operator)
            audit_rows.append({
                "task_id": row["task_id"],
                "true_operator": row["proof_units"]["operator"],
                "predicted_operator": operator,
                "correct_operator": operator == row["proof_units"]["operator"],
            })
        _write_jsonl(args.output_dir / f"{split}_predictions.jsonl", [{"task_id": key, "candidate_code": value} for key, value in predictions.items()])
        _write_jsonl(args.output_dir / f"{split}_operator_audit.jsonl", audit_rows)
        split_score = _score(score_module, rows[split], predictions)
        split_score["operator_accuracy"] = sum(int(row["correct_operator"]) for row in audit_rows)
        split_score["predictions_jsonl"] = str(args.output_dir / f"{split}_predictions.jsonl")
        split_score["operator_audit_jsonl"] = str(args.output_dir / f"{split}_operator_audit.jsonl")
        results[split] = split_score

    summary = {
        "artifact_kind": "stage1091_scaled_software_operator_curriculum",
        "status": "completed_scaled_operator_selection_probe",
        "manifest": str(args.output_dir / "manifest.json"),
        "operator_count": len(OPERATORS),
        "by_split": {split: len(split_rows) for split, split_rows in rows.items()},
        "results": results,
        "decision": (
            "Scaled typed-operator software curriculum with held-out symbols and alternate contract phrasings. "
            "Selection is learned by a tiny text classifier; materialization remains a typed external interface."
        ),
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
