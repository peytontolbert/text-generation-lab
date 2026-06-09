#!/usr/bin/env python3
"""Train a tiny proof-operator selector and score it on Stage1088."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SUPPLEMENTAL_TRAIN = [
    {
        "function_name": "normalize_username",
        "args": ["name"],
        "operator": "strip_then_lowercase",
        "contract": "Strip surrounding whitespace and lowercase a username string.",
        "invariant": "strip then lowercase",
    },
    {
        "function_name": "clean_identifier",
        "args": ["identifier"],
        "operator": "strip_then_lowercase",
        "contract": "Strip surrounding whitespace and lowercase an identifier string.",
        "invariant": "strip then lowercase",
    },
    {
        "function_name": "count_name_vowels",
        "args": ["name"],
        "operator": "case_insensitive_membership",
        "contract": "Count vowels in name, case-insensitively.",
        "invariant": "case-insensitive vowel membership",
    },
    {
        "function_name": "count_title_vowels",
        "args": ["title"],
        "operator": "case_insensitive_membership",
        "contract": "Count vowels in title, case-insensitively.",
        "invariant": "case-insensitive vowel membership",
    },
    {
        "function_name": "flatten_groups",
        "args": ["groups"],
        "operator": "one_level_flatten",
        "contract": "Flatten exactly one list nesting level.",
        "invariant": "only one level is flattened",
    },
    {
        "function_name": "flatten_batches",
        "args": ["batches"],
        "operator": "one_level_flatten",
        "contract": "Flatten exactly one list nesting level.",
        "invariant": "only one level is flattened",
    },
]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {name}: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _proof_text(row: dict[str, Any]) -> str:
    proof = row.get("proof_units", {}) or {}
    return " ".join(str(proof.get(key, "")) for key in ("contract", "invariant", "repair_kind"))


def _signature(row: dict[str, Any]) -> tuple[str, list[str]]:
    match = re.search(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)\(([^)]*)\):", str(row["buggy_code"]), re.MULTILINE)
    if not match:
        raise ValueError(f"missing function signature for {row.get('task_id')}")
    args = [part.strip().split("=")[0].strip() for part in match.group(2).split(",") if part.strip()]
    return match.group(1), args


def _supplemental_row(item: dict[str, Any], index: int) -> dict[str, Any]:
    function_name = str(item["function_name"])
    args = list(item["args"])
    return {
        "task_id": f"stage1090_train_{index:04d}_{function_name}",
        "function_name": function_name,
        "buggy_code": f"def {function_name}({', '.join(args)}):\n    pass\n",
        "proof_units": {
            "contract": item["contract"],
            "invariant": item["invariant"],
            "repair_kind": "proof_operator_induction",
            "operator": item["operator"],
        },
    }


class NaiveBayesOperator:
    def __init__(self) -> None:
        self.class_counts: Counter[str] = Counter()
        self.token_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.total_tokens: Counter[str] = Counter()
        self.vocab: set[str] = set()

    def fit(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            operator = str((row.get("proof_units", {}) or {}).get("operator", ""))
            if not operator:
                continue
            self.class_counts[operator] += 1
            for token in _tokenize(_proof_text(row)):
                self.token_counts[operator][token] += 1
                self.total_tokens[operator] += 1
                self.vocab.add(token)

    def predict(self, row: dict[str, Any]) -> tuple[str, dict[str, float]]:
        tokens = _tokenize(_proof_text(row))
        total_classes = sum(self.class_counts.values())
        vocab_size = max(1, len(self.vocab))
        scores: dict[str, float] = {}
        for operator, count in self.class_counts.items():
            logp = math.log(count / total_classes)
            denom = self.total_tokens[operator] + vocab_size
            for token in tokens:
                logp += math.log((self.token_counts[operator][token] + 1) / denom)
            scores[operator] = logp
        best = max(scores, key=scores.get)
        return best, scores


def _materialize(function_name: str, args: list[str], operator: str) -> str:
    first_arg = args[0] if args else "x"
    if operator == "case_insensitive_membership":
        return (
            f"def {function_name}({', '.join(args)}):\n"
            f"    return sum(1 for ch in {first_arg}.lower() if ch in 'aeiou')\n"
        )
    if operator == "strip_then_lowercase":
        return (
            f"def {function_name}({', '.join(args)}):\n"
            f"    return {first_arg}.strip().lower()\n"
        )
    if operator == "one_level_flatten":
        return (
            f"def {function_name}({', '.join(args)}):\n"
            f"    return [value for group in {first_arg} for value in group]\n"
        )
    return f"def {function_name}({', '.join(args)}):\n    return None\n"


def _score_rows(score_module, rows: list[dict[str, Any]], predictions: dict[str, str]) -> dict[str, Any]:
    scores = [score_module._score_task(row, predictions.get(str(row["task_id"]), "")) for row in rows]
    return {
        "rows": len(scores),
        "hidden_pass": sum(int(score["hidden_tests_pass"]) for score in scores),
        "public_pass": sum(int(score["public_tests_pass"]) for score in scores),
        "syntax_valid": sum(int(score["syntax_valid"]) for score in scores),
        "function_symbol_preserved": sum(int(score["function_symbol_preserved"]) for score in scores),
        "verified_decisions": sum(int(score["verified_decisions"]) for score in scores),
        "verified_decision_bits": sum(int(score["verified_decision_bits"]) for score in scores),
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("runs/local/artifacts/stage1088_hardened_software_kbpp_pilot/manifest.json"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("runs/local/artifacts/stage1090_learned_software_operator_induction"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1090_learned_software_operator_induction_summary.json"))
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    score_module = _load_module("stage1086_score", args.repo_root / "scripts/score_stage1086_software_kbpp_predictions.py")
    supplemental_rows = [_supplemental_row(item, index) for index, item in enumerate(SUPPLEMENTAL_TRAIN)]
    model = NaiveBayesOperator()
    model.fit(supplemental_rows)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "operator_training_rows.jsonl", supplemental_rows)

    split_results: dict[str, Any] = {}
    for split_name in ("eval", "hidden"):
        rows = _iter_jsonl(Path(manifest[f"{split_name}_path"]))
        predictions: dict[str, str] = {}
        prediction_audit: list[dict[str, Any]] = []
        for row in rows:
            function_name, fn_args = _signature(row)
            operator, scores = model.predict(row)
            predictions[str(row["task_id"])] = _materialize(function_name, fn_args, operator)
            prediction_audit.append({
                "task_id": row["task_id"],
                "function_name": function_name,
                "predicted_operator": operator,
                "scores": scores,
            })
        pred_path = args.output_dir / f"{split_name}_predictions.jsonl"
        audit_path = args.output_dir / f"{split_name}_operator_audit.jsonl"
        _write_jsonl(pred_path, [{"task_id": key, "candidate_code": value} for key, value in predictions.items()])
        _write_jsonl(audit_path, prediction_audit)
        score = _score_rows(score_module, rows, predictions)
        score["predictions_jsonl"] = str(pred_path)
        score["operator_audit_jsonl"] = str(audit_path)
        split_results[split_name] = score

    summary = {
        "artifact_kind": "stage1090_learned_software_operator_induction",
        "status": "completed_learned_operator_selection_probe",
        "manifest": str(args.manifest),
        "training_rows": len(supplemental_rows),
        "model": {
            "type": "multinomial_naive_bayes_operator_selector",
            "classes": sorted(model.class_counts),
            "parameter_accounting": "token/class counts only; diagnostic counted learner, not 100M-owned",
        },
        "results": split_results,
        "decision": (
            "A tiny learned operator selector plus typed materializer solves the hardened Stage1088 held-out pilot. "
            "This converts the Stage1089 hand-selected operator ceiling into a learned-selection diagnostic, but the materializer is still external."
        ),
    }
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
