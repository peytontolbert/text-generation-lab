#!/usr/bin/env python3
"""Build a larger independent-template software operator surface."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Spec:
    operator: str
    args: list[str]
    body: str
    buggy_body: str
    contract: str
    invariant: str
    public_tests: list[str]
    hidden_tests: list[str]


def _specs(limit: int) -> list[Spec]:
    specs: list[Spec] = []
    for k in range(1, 65):
        specs.append(Spec(f"add_{k}", ["x"], f"return x + {k}", "return x", f"Return x plus {k}.", f"add {k}", [f"assert {{fn}}(2) == {2 + k}"], [f"assert {{fn}}(-5) == {-5 + k}"]))
        specs.append(Spec(f"subtract_{k}", ["x"], f"return x - {k}", "return x", f"Return x minus {k}.", f"subtract {k}", [f"assert {{fn}}(10) == {10 - k}"], [f"assert {{fn}}(-5) == {-5 - k}"]))
        specs.append(Spec(f"multiply_{k+1}", ["x"], f"return x * {k + 1}", "return x", f"Return x multiplied by {k + 1}.", f"multiply {k + 1}", [f"assert {{fn}}(3) == {3 * (k + 1)}"], [f"assert {{fn}}(-2) == {-2 * (k + 1)}"]))
        specs.append(Spec(f"max_with_{k}", ["x"], f"return max(x, {k})", "return x", f"Return the larger value of x and {k}.", f"lower bound {k}", [f"assert {{fn}}({k - 1}) == {k}"], [f"assert {{fn}}({k + 2}) == {k + 2}"]))
        specs.append(Spec(f"min_with_{k}", ["x"], f"return min(x, {k})", "return x", f"Return the smaller value of x and {k}.", f"upper bound {k}", [f"assert {{fn}}({k + 1}) == {k}"], [f"assert {{fn}}({k - 2}) == {k - 2}"]))
    for k in range(64):
        prefix = f"p{k}_"
        suffix = f"_s{k}"
        digit = str(k % 10)
        specs.append(Spec(f"prefix_{k}", ["text"], f"return '{prefix}' + text", "return text", f"Prefix text with {prefix}.", f"prefix {prefix}", [f"assert {{fn}}('x') == '{prefix}x'"], [f"assert {{fn}}('abc') == '{prefix}abc'"]))
        specs.append(Spec(f"suffix_{k}", ["text"], f"return text + '{suffix}'", "return text", f"Suffix text with {suffix}.", f"suffix {suffix}", [f"assert {{fn}}('x') == 'x{suffix}'"], [f"assert {{fn}}('abc') == 'abc{suffix}'"]))
        specs.append(Spec(f"contains_digit_{k}", ["text"], f"return '{digit}' in text", "return False", f"Return whether text contains digit {digit}.", f"contains digit {digit}", [f"assert {{fn}}('a{digit}b') is True"], [f"assert {{fn}}('abc') is False"]))
    return specs[:limit]


def _row(spec: Spec, split: str, index: int, variant: int) -> dict[str, Any]:
    name = f"{split}_{spec.operator}_{variant}_{index:06d}".replace("-", "_")
    args = ", ".join(spec.args)
    buggy_code = f"def {name}({args}):\n    {spec.buggy_body}\n"
    reference_code = f"def {name}({args}):\n    {spec.body}\n"
    contract = spec.contract if split == "train" else f"{spec.contract} Preserve invariant: {spec.invariant}."
    public_tests = [item.format(fn=name) for item in spec.public_tests]
    hidden_tests = [item.format(fn=name) for item in (spec.public_tests + spec.hidden_tests)]
    return {
        "benchmark": "stage1103_expanded_diverse_software_surface",
        "task_id": f"stage1103_{split}_{index:06d}_{spec.operator}_{variant}",
        "split": split,
        "category": "expanded_diverse_software_operator",
        "language": "python",
        "function_name": name,
        "buggy_code": buggy_code,
        "reference_code": reference_code,
        "prompt": f"Repair the Python function `{name}`.\nContract: {contract}\nReturn the complete corrected function only.\n\n{buggy_code}",
        "proof_units": {
            "operator": spec.operator,
            "contract": contract,
            "invariant": spec.invariant,
            "repair_kind": "expanded_diverse_software_operator",
            "relevant_symbol": name,
        },
        "public_tests": public_tests,
        "hidden_tests": hidden_tests,
        "verified_decision_bits": 8,
        "score_fields": ["public_tests_pass", "hidden_tests_pass", "function_symbol_preserved", "syntax_valid"],
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("runs/local/artifacts/stage1103_expanded_diverse_software_surface"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1103_expanded_diverse_software_surface_summary.json"))
    parser.add_argument("--operators", type=int, default=512)
    parser.add_argument("--train-variants", type=int, default=2)
    parser.add_argument("--eval-variants", type=int, default=1)
    parser.add_argument("--hidden-variants", type=int, default=2)
    args = parser.parse_args()

    specs = _specs(int(args.operators))
    variants = {
        "train": int(args.train_variants),
        "eval": int(args.eval_variants),
        "hidden": int(args.hidden_variants),
    }
    rows_by_split: dict[str, list[dict[str, Any]]] = {}
    for split, count in variants.items():
        rows: list[dict[str, Any]] = []
        for spec_index, spec in enumerate(specs):
            for variant in range(count):
                rows.append(_row(spec, split, spec_index * count + variant, variant))
        rows_by_split[split] = rows
        _write_jsonl(args.output_dir / f"{split}.jsonl", rows)

    unique_bodies = len({spec.body for spec in specs})
    manifest = {
        "artifact_kind": "stage1103_expanded_diverse_software_surface_manifest",
        "train_path": str(args.output_dir / "train.jsonl"),
        "eval_path": str(args.output_dir / "eval.jsonl"),
        "hidden_path": str(args.output_dir / "hidden.jsonl"),
        "operator_count": len(specs),
        "unique_template_body_count": unique_bodies,
        "holdout_rule": "eval/hidden function names are generated separately; hidden tests include public checks",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "artifact_kind": "stage1103_expanded_diverse_software_surface",
        "status": "completed_expanded_diverse_surface_generation",
        "manifest": str(args.output_dir / "manifest.json"),
        "operator_count": len(specs),
        "unique_template_body_count": unique_bodies,
        "by_split": {split: len(rows) for split, rows in rows_by_split.items()},
        "hidden_row_level_verified_bits": sum(int(row["verified_decision_bits"]) for row in rows_by_split["hidden"]),
        "conservative_unique_family_bits": unique_bodies * 8,
        "decision": "Expanded independent-template surface. This increases semantic family diversity before large row-count scaling.",
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
