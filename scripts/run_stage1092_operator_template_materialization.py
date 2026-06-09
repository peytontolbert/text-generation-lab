#!/usr/bin/env python3
"""Induce operator-conditioned code templates from Stage1091 train references."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


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
    return f"{proof.get('contract', '')} {proof.get('invariant', '')}"


def _signature(code: str) -> tuple[str, list[str]]:
    match = re.search(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)\(([^)]*)\):", code, re.MULTILINE)
    if not match:
        raise ValueError(f"missing function signature in code: {code[:80]}")
    args = [part.strip().split("=")[0].strip() for part in match.group(2).split(",") if part.strip()]
    return match.group(1), args


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
            for token in _tokenize(_proof_text(row)):
                self.token_counts[operator][token] += 1
                self.total_tokens[operator] += 1
                self.vocab.add(token)

    def predict(self, row: dict[str, Any]) -> str:
        tokens = _tokenize(_proof_text(row))
        total_classes = sum(self.class_counts.values())
        vocab_size = max(1, len(self.vocab))
        scores: dict[str, float] = {}
        for operator, count in self.class_counts.items():
            score = math.log(count / total_classes)
            denom = self.total_tokens[operator] + vocab_size
            for token in tokens:
                score += math.log((self.token_counts[operator][token] + 1) / denom)
            scores[operator] = score
        return max(scores, key=scores.get)


def _template_bank(train_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    bank: dict[str, dict[str, Any]] = {}
    for row in train_rows:
        operator = str(row["proof_units"]["operator"])
        if operator in bank:
            continue
        code = str(row["reference_code"])
        fn, args = _signature(code)
        body = code.split("\n", 1)[1] if "\n" in code else ""
        bank[operator] = {"source_function": fn, "source_args": args, "body": body}
    return bank


def _materialize_from_template(row: dict[str, Any], template: dict[str, Any]) -> str:
    target_fn, target_args = _signature(str(row["buggy_code"]))
    source_args = list(template["source_args"])
    body = str(template["body"])
    for source, target in zip(source_args, target_args):
        body = re.sub(rf"\b{re.escape(source)}\b", target, body)
    return f"def {target_fn}({', '.join(target_args)}):\n{body}"


def _score_rows(score_module, rows: list[dict[str, Any]], predictions: dict[str, str]) -> dict[str, Any]:
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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("runs/local/artifacts/stage1091_scaled_software_operator_curriculum/manifest.json"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("runs/local/artifacts/stage1092_operator_template_materialization"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1092_operator_template_materialization_summary.json"))
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    train_rows = _iter_jsonl(Path(manifest["train_path"]))
    model = NaiveBayes()
    model.fit(train_rows)
    templates = _template_bank(train_rows)
    score_module = _load_module("stage1086_score", args.repo_root / "scripts/score_stage1086_software_kbpp_predictions.py")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "induced_templates.jsonl", [
        {"operator": operator, **template} for operator, template in sorted(templates.items())
    ])

    results: dict[str, Any] = {}
    for split in ("eval", "hidden"):
        rows = _iter_jsonl(Path(manifest[f"{split}_path"]))
        predictions: dict[str, str] = {}
        audit: list[dict[str, Any]] = []
        for row in rows:
            operator = model.predict(row)
            predictions[str(row["task_id"])] = _materialize_from_template(row, templates[operator])
            audit.append({
                "task_id": row["task_id"],
                "true_operator": row["proof_units"]["operator"],
                "predicted_operator": operator,
                "operator_correct": operator == row["proof_units"]["operator"],
                "template_source_function": templates[operator]["source_function"],
            })
        pred_path = args.output_dir / f"{split}_predictions.jsonl"
        audit_path = args.output_dir / f"{split}_template_audit.jsonl"
        _write_jsonl(pred_path, [{"task_id": key, "candidate_code": value} for key, value in predictions.items()])
        _write_jsonl(audit_path, audit)
        score = _score_rows(score_module, rows, predictions)
        score["operator_accuracy"] = sum(int(item["operator_correct"]) for item in audit)
        score["predictions_jsonl"] = str(pred_path)
        score["template_audit_jsonl"] = str(audit_path)
        results[split] = score

    summary = {
        "artifact_kind": "stage1092_operator_template_materialization",
        "status": "completed_operator_template_materialization_probe",
        "manifest": str(args.manifest),
        "template_count": len(templates),
        "selector": "multinomial_naive_bayes_operator_selector",
        "materializer": "operator_conditioned_reference_template_transfer",
        "results": results,
        "decision": (
            "Operator selection and code body materialization are both induced from train rows, then transferred to held-out symbols. "
            "This is a stronger symbolic-adapter diagnostic than Stage1091, but still not 100M-owned generation."
        ),
    }
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
