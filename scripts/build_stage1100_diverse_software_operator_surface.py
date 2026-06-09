#!/usr/bin/env python3
"""Build a higher-diversity synthetic software-operator surface."""

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


def _numeric_specs() -> list[Spec]:
    specs: list[Spec] = []
    for k in range(1, 9):
        specs.append(Spec(f"add_{k}", ["x"], f"return x + {k}", "return x", f"Return x plus {k}.", f"add constant {k}", [f"assert {{fn}}(2) == {2 + k}"], [f"assert {{fn}}(-3) == {-3 + k}"]))
        specs.append(Spec(f"subtract_{k}", ["x"], f"return x - {k}", "return x", f"Return x minus {k}.", f"subtract constant {k}", [f"assert {{fn}}(10) == {10 - k}"], [f"assert {{fn}}(-3) == {-3 - k}"]))
    for k in range(2, 10):
        specs.append(Spec(f"multiply_{k}", ["x"], f"return x * {k}", "return x", f"Return x multiplied by {k}.", f"multiply by constant {k}", [f"assert {{fn}}(3) == {3 * k}"], [f"assert {{fn}}(-2) == {-2 * k}"]))
    for k in range(1, 9):
        specs.append(Spec(f"max_with_{k}", ["x"], f"return max(x, {k})", "return x", f"Return the larger value of x and {k}.", f"lower bound {k}", [f"assert {{fn}}({k - 1}) == {k}"], [f"assert {{fn}}({k + 2}) == {k + 2}"]))
    return specs


def _string_specs() -> list[Spec]:
    return [
        Spec("strip_text", ["text"], "return text.strip()", "return text", "Strip surrounding whitespace.", "trim outer whitespace", ["assert {fn}(' a ') == 'a'"], ["assert {fn}('\\tHi\\n') == 'Hi'"]),
        Spec("lower_text", ["text"], "return text.lower()", "return text", "Lowercase the text.", "lowercase letters", ["assert {fn}('Ab') == 'ab'"], ["assert {fn}('MIX') == 'mix'"]),
        Spec("upper_text", ["text"], "return text.upper()", "return text", "Uppercase the text.", "uppercase letters", ["assert {fn}('ab') == 'AB'"], ["assert {fn}('Mix') == 'MIX'"]),
        Spec("title_text", ["text"], "return text.title()", "return text", "Title-case the text.", "capitalize words", ["assert {fn}('hello world') == 'Hello World'"], ["assert {fn}('two words') == 'Two Words'"]),
        Spec("reverse_text", ["text"], "return text[::-1]", "return text", "Reverse the text.", "reverse character order", ["assert {fn}('abc') == 'cba'"], ["assert {fn}('stressed') == 'desserts'"]),
        Spec("replace_space_underscore", ["text"], "return text.replace(' ', '_')", "return text", "Replace spaces with underscores.", "space to underscore", ["assert {fn}('a b') == 'a_b'"], ["assert {fn}('a b c') == 'a_b_c'"]),
        Spec("remove_spaces", ["text"], "return text.replace(' ', '')", "return text", "Remove spaces from text.", "delete spaces", ["assert {fn}('a b') == 'ab'"], ["assert {fn}('a b c') == 'abc'"]),
        Spec("count_chars", ["text"], "return len(text)", "return 0", "Return the character count.", "length of text", ["assert {fn}('abc') == 3"], ["assert {fn}('') == 0"]),
        Spec("first_char", ["text"], "return text[0] if text else ''", "return text", "Return the first character or empty string.", "safe first character", ["assert {fn}('abc') == 'a'"], ["assert {fn}('') == ''"]),
        Spec("last_char", ["text"], "return text[-1] if text else ''", "return text", "Return the last character or empty string.", "safe last character", ["assert {fn}('abc') == 'c'"], ["assert {fn}('') == ''"]),
        Spec("contains_at", ["text"], "return '@' in text", "return False", "Return whether text contains @.", "membership at sign", ["assert {fn}('a@b') is True"], ["assert {fn}('abc') is False"]),
        Spec("count_commas", ["text"], "return text.count(',')", "return 0", "Count commas in text.", "comma count", ["assert {fn}('a,b') == 1"], ["assert {fn}('a,b,c') == 2"]),
        Spec("split_words", ["text"], "return text.split()", "return [text]", "Split text on whitespace.", "word split", ["assert {fn}('a b') == ['a', 'b']"], ["assert {fn}(' one  two ') == ['one', 'two']"]),
        Spec("prefix_hi", ["text"], "return 'hi_' + text", "return text", "Prefix text with hi_.", "fixed prefix", ["assert {fn}('x') == 'hi_x'"], ["assert {fn}('abc') == 'hi_abc'"]),
        Spec("suffix_done", ["text"], "return text + '_done'", "return text", "Suffix text with _done.", "fixed suffix", ["assert {fn}('x') == 'x_done'"], ["assert {fn}('abc') == 'abc_done'"]),
        Spec("is_empty_text", ["text"], "return text == ''", "return False", "Return whether text is empty.", "empty string equality", ["assert {fn}('') is True"], ["assert {fn}('x') is False"]),
    ]


def _list_specs() -> list[Spec]:
    return [
        Spec("list_length", ["items"], "return len(items)", "return 0", "Return the list length.", "length of list", ["assert {fn}([1, 2]) == 2"], ["assert {fn}([]) == 0"]),
        Spec("first_item", ["items"], "return items[0] if items else None", "return None", "Return the first item or None.", "safe first item", ["assert {fn}([1, 2]) == 1"], ["assert {fn}([]) is None"]),
        Spec("last_item", ["items"], "return items[-1] if items else None", "return None", "Return the last item or None.", "safe last item", ["assert {fn}([1, 2]) == 2"], ["assert {fn}([]) is None"]),
        Spec("reverse_list", ["items"], "return list(reversed(items))", "return items", "Reverse the list.", "reverse item order", ["assert {fn}([1, 2]) == [2, 1]"], ["assert {fn}(['a', 'b', 'c']) == ['c', 'b', 'a']"]),
        Spec("sort_list", ["items"], "return sorted(items)", "return items", "Sort the list.", "ascending sort", ["assert {fn}([2, 1]) == [1, 2]"], ["assert {fn}(['b', 'a']) == ['a', 'b']"]),
        Spec("sum_list", ["items"], "return sum(items)", "return 0", "Return the sum of list values.", "list sum", ["assert {fn}([1, 2]) == 3"], ["assert {fn}([]) == 0"]),
        Spec("max_list", ["items"], "return max(items) if items else None", "return None", "Return the max item or None.", "safe max", ["assert {fn}([1, 3, 2]) == 3"], ["assert {fn}([]) is None"]),
        Spec("min_list", ["items"], "return min(items) if items else None", "return None", "Return the min item or None.", "safe min", ["assert {fn}([1, 3, 2]) == 1"], ["assert {fn}([]) is None"]),
    ]


def _all_specs() -> list[Spec]:
    return (_numeric_specs() + _string_specs() + _list_specs())[:64]


def _row(spec: Spec, split: str, index: int, variant: int) -> dict[str, Any]:
    name = f"{split}_{spec.operator}_{index:06d}".replace("-", "_")
    args = ", ".join(spec.args)
    buggy_code = f"def {name}({args}):\n    {spec.buggy_body}\n"
    reference_code = f"def {name}({args}):\n    {spec.body}\n"
    contract = spec.contract if split == "train" else f"{spec.contract} Ensure the invariant: {spec.invariant}."
    public_tests = [item.format(fn=name) for item in spec.public_tests]
    hidden_tests = [item.format(fn=name) for item in (spec.public_tests + spec.hidden_tests)]
    return {
        "benchmark": "stage1100_diverse_software_operator_surface",
        "task_id": f"stage1100_{split}_{index:06d}_{spec.operator}_{variant}",
        "split": split,
        "category": "diverse_software_operator",
        "language": "python",
        "function_name": name,
        "buggy_code": buggy_code,
        "reference_code": reference_code,
        "prompt": f"Repair the Python function `{name}`.\nContract: {contract}\nReturn the complete corrected function only.\n\n{buggy_code}",
        "proof_units": {
            "operator": spec.operator,
            "contract": contract,
            "invariant": spec.invariant,
            "repair_kind": "diverse_software_operator",
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
    parser.add_argument("--output-dir", type=Path, default=Path("runs/local/artifacts/stage1100_diverse_software_operator_surface"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1100_diverse_software_operator_surface_summary.json"))
    parser.add_argument("--train-variants", type=int, default=3)
    parser.add_argument("--eval-variants", type=int, default=4)
    parser.add_argument("--hidden-variants", type=int, default=16)
    parser.add_argument("--artifact-kind", default="stage1100_diverse_software_operator_surface")
    parser.add_argument("--status", default="completed_diverse_surface_generation")
    args = parser.parse_args()

    specs = _all_specs()
    splits = {
        "train": int(args.train_variants),
        "eval": int(args.eval_variants),
        "hidden": int(args.hidden_variants),
    }
    rows_by_split: dict[str, list[dict[str, Any]]] = {}
    for split, variants in splits.items():
        rows: list[dict[str, Any]] = []
        for spec_index, spec in enumerate(specs):
            for variant in range(variants):
                rows.append(_row(spec, split, spec_index * variants + variant, variant))
        rows_by_split[split] = rows
        _write_jsonl(args.output_dir / f"{split}.jsonl", rows)
    manifest = {
        "artifact_kind": f"{args.artifact_kind}_manifest",
        "train_path": str(args.output_dir / "train.jsonl"),
        "eval_path": str(args.output_dir / "eval.jsonl"),
        "hidden_path": str(args.output_dir / "hidden.jsonl"),
        "operator_count": len(specs),
        "unique_template_body_count": len({spec.body for spec in specs}),
        "holdout_rule": "eval/hidden function names are generated separately; hidden labels are not in prompts",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "artifact_kind": args.artifact_kind,
        "status": args.status,
        "manifest": str(args.output_dir / "manifest.json"),
        "operator_count": len(specs),
        "unique_template_body_count": len({spec.body for spec in specs}),
        "by_split": {split: len(rows) for split, rows in rows_by_split.items()},
        "hidden_row_level_verified_bits": sum(int(row["verified_decision_bits"]) for row in rows_by_split["hidden"]),
        "conservative_unique_family_bits": len({spec.body for spec in specs}) * 8,
        "decision": "Higher-diversity software surface for independent semantic-bit expansion. This raises unique operator/template families before scaling row count.",
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
