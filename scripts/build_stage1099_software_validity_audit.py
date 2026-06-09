#!/usr/bin/env python3
"""Audit validity limits of the Stage1095/1096 software-KBPP surface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _body_from_code(code: str) -> str:
    return code.split("\n", 1)[1].strip() if "\n" in code else code.strip()


def _surface_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    operators = [str((row.get("proof_units", {}) or {}).get("operator", "")) for row in rows]
    functions = [str(row.get("function_name", "")) for row in rows]
    bodies = [_body_from_code(str(row.get("reference_code", ""))) for row in rows]
    public_patterns = [json.dumps(row.get("public_tests", []), sort_keys=True) for row in rows]
    hidden_patterns = [json.dumps(row.get("hidden_tests", []), sort_keys=True) for row in rows]
    return {
        "rows": len(rows),
        "unique_operators": len(set(operators)),
        "unique_function_names": len(set(functions)),
        "unique_reference_bodies": len(set(bodies)),
        "unique_public_test_patterns": len(set(public_patterns)),
        "unique_hidden_test_patterns": len(set(hidden_patterns)),
        "operator_counts": {operator: operators.count(operator) for operator in sorted(set(operators))},
    }


def _target_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    operators = [str(row.get("operator_label", "")) for row in rows]
    bodies = [str(row.get("template_body_target", "")).strip() for row in rows]
    prompts = [str(row.get("prompt", "")) for row in rows]
    return {
        "rows": len(rows),
        "unique_operators": len(set(operators)),
        "unique_template_body_targets": len(set(bodies)),
        "unique_prompt_surfaces": len(set(prompts)),
        "operator_counts": {operator: operators.count(operator) for operator in sorted(set(operators))},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage1095-manifest", type=Path, default=Path("runs/local/artifacts/stage1095_controlled_scale_software_operator_surface/manifest.json"))
    parser.add_argument("--stage1096-manifest", type=Path, default=Path("runs/local/artifacts/stage1096_100m_software_operator_training_package/manifest.json"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1099_software_validity_audit_summary.json"))
    args = parser.parse_args()

    surface_manifest = json.loads(args.stage1095_manifest.read_text(encoding="utf-8"))
    target_manifest = json.loads(args.stage1096_manifest.read_text(encoding="utf-8"))
    surface_train = _iter_jsonl(Path(surface_manifest["train_path"]))
    surface_eval = _iter_jsonl(Path(surface_manifest["eval_path"]))
    surface_hidden = _iter_jsonl(Path(surface_manifest["hidden_path"]))
    target_train = _iter_jsonl(Path(target_manifest["train_targets_path"]))
    target_eval = _iter_jsonl(Path(target_manifest["eval_targets_path"]))
    target_hidden = _iter_jsonl(Path(target_manifest["hidden_targets_path"]))

    train_functions = {str(row["function_name"]) for row in surface_train}
    eval_functions = {str(row["function_name"]) for row in surface_eval}
    hidden_functions = {str(row["function_name"]) for row in surface_hidden}
    hidden_prompt_leaks_direct_target = sum(int(str(row.get("direct_code_target", "")) in str(row.get("prompt", ""))) for row in target_hidden)
    hidden_prompt_leaks_body_target = sum(int(str(row.get("template_body_target", "")).strip() in str(row.get("prompt", ""))) for row in target_hidden)
    hidden_unique_template_bodies = len({str(row.get("template_body_target", "")).strip() for row in target_hidden})
    hidden_row_bits = sum(int(row.get("verified_decision_bits", 8)) for row in target_hidden)
    conservative_family_bits = hidden_unique_template_bodies * 8

    summary = {
        "artifact_kind": "stage1099_software_validity_audit",
        "status": "completed_validity_audit",
        "stage1095_manifest": str(args.stage1095_manifest),
        "stage1096_manifest": str(args.stage1096_manifest),
        "surface_stats": {
            "train": _surface_stats(surface_train),
            "eval": _surface_stats(surface_eval),
            "hidden": _surface_stats(surface_hidden),
        },
        "target_stats": {
            "train": _target_stats(target_train),
            "eval": _target_stats(target_eval),
            "hidden": _target_stats(target_hidden),
        },
        "split_overlap": {
            "train_eval_function_overlap": len(train_functions & eval_functions),
            "train_hidden_function_overlap": len(train_functions & hidden_functions),
            "eval_hidden_function_overlap": len(eval_functions & hidden_functions),
        },
        "prompt_label_leakage": {
            "hidden_prompt_contains_direct_code_target_rows": hidden_prompt_leaks_direct_target,
            "hidden_prompt_contains_template_body_target_rows": hidden_prompt_leaks_body_target,
        },
        "bit_accounting": {
            "row_level_hidden_verified_bits": hidden_row_bits,
            "hidden_unique_template_bodies": hidden_unique_template_bodies,
            "conservative_unique_family_bits": conservative_family_bits,
            "row_bits_are_not_independent_semantic_bits": True,
        },
        "validity": {
            "valid_as_verifier_pipeline": True,
            "valid_as_controlled_synthetic_operator_transfer": True,
            "valid_as_100m_owned_result": False,
            "valid_as_100m_beats_7b_claim": False,
            "main_limits": [
                "No actual 100M predictions have been scored.",
                "No named 7B baseline has been scored on the same hidden verifier.",
                "The 125,000 hidden rows are generated from only 8 operator families and 8 template bodies.",
                "Row-level verified bits overstate independent semantic diversity.",
            ],
        },
        "decision": (
            "The Stage1095-1097 pipeline is valid for controlled verifier engineering and for testing owned prediction plumbing. "
            "It is not valid as a 100M-vs-7B intelligence claim until model predictions, named 7B baselines, and higher independent semantic diversity are added."
        ),
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
