#!/usr/bin/env python3
"""Package Stage1095 into trainable 100M-owned software-operator targets."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _signature(code: str) -> tuple[str, list[str]]:
    match = re.search(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)\(([^)]*)\):", code, re.MULTILINE)
    if not match:
        raise ValueError(f"missing signature: {code[:80]}")
    args = [part.strip().split("=")[0].strip() for part in match.group(2).split(",") if part.strip()]
    return match.group(1), args


def _body(code: str) -> str:
    return code.split("\n", 1)[1] if "\n" in code else ""


def _target_row(row: dict[str, Any], source_split: str) -> dict[str, Any]:
    proof = row.get("proof_units", {}) or {}
    fn, args = _signature(str(row["reference_code"]))
    return {
        "task_id": row["task_id"],
        "source_split": source_split,
        "prompt": row["prompt"],
        "function_name": row["function_name"],
        "operator_label": proof.get("operator"),
        "operator_input": f"{proof.get('contract', '')}\n{proof.get('invariant', '')}",
        "signature_target": f"def {fn}({', '.join(args)}):",
        "template_body_target": _body(str(row["reference_code"])),
        "direct_code_target": row["reference_code"],
        "public_tests": row.get("public_tests", []),
        "hidden_tests": row.get("hidden_tests", []),
        "verified_decision_bits": row.get("verified_decision_bits", 8),
    }


def _build_generated_train(stage1091, row_count: int) -> list[dict[str, Any]]:
    operators = list(stage1091.OPERATORS)
    rows: list[dict[str, Any]] = []
    for index in range(row_count):
        operator = operators[index % len(operators)]
        name = f"train_owned_{operator.replace('_', '')}_{index:06d}"
        rows.append(stage1091._row(operator, name, "train", index % 2 == 1, index))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--stage1095-manifest", type=Path, default=Path("runs/local/artifacts/stage1095_controlled_scale_software_operator_surface/manifest.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("runs/local/artifacts/stage1096_100m_software_operator_training_package"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1096_100m_software_operator_training_package_summary.json"))
    parser.add_argument("--train-rows", type=int, default=100000)
    args = parser.parse_args()

    stage1091 = _load_module("stage1091", args.repo_root / "scripts/run_stage1091_scaled_software_operator_curriculum.py")
    stage1095_manifest = json.loads(args.stage1095_manifest.read_text(encoding="utf-8"))
    train_source = _build_generated_train(stage1091, int(args.train_rows))
    eval_source = _iter_jsonl(Path(stage1095_manifest["eval_path"]))
    hidden_source = _iter_jsonl(Path(stage1095_manifest["hidden_path"]))

    train_targets = [_target_row(row, "train") for row in train_source]
    eval_targets = [_target_row(row, "eval") for row in eval_source]
    hidden_targets = [_target_row(row, "hidden") for row in hidden_source]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "train_targets.jsonl", train_targets)
    _write_jsonl(args.output_dir / "eval_targets.jsonl", eval_targets)
    _write_jsonl(args.output_dir / "hidden_targets.jsonl", hidden_targets)
    manifest = {
        "artifact_kind": "stage1096_100m_software_operator_training_package_manifest",
        "train_targets_path": str(args.output_dir / "train_targets.jsonl"),
        "eval_targets_path": str(args.output_dir / "eval_targets.jsonl"),
        "hidden_targets_path": str(args.output_dir / "hidden_targets.jsonl"),
        "stage1095_manifest": str(args.stage1095_manifest),
        "target_fields": [
            "operator_label",
            "signature_target",
            "template_body_target",
            "direct_code_target",
        ],
        "verifier_script": "scripts/score_stage1086_software_kbpp_predictions.py",
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "artifact_kind": "stage1096_100m_software_operator_training_package",
        "status": "completed_100m_training_target_package",
        "manifest": str(args.output_dir / "manifest.json"),
        "train_rows": len(train_targets),
        "eval_rows": len(eval_targets),
        "hidden_rows": len(hidden_targets),
        "train_verified_bits_if_solved": sum(int(row["verified_decision_bits"]) for row in train_targets),
        "eval_verified_bits_if_solved": sum(int(row["verified_decision_bits"]) for row in eval_targets),
        "hidden_verified_bits_if_solved": sum(int(row["verified_decision_bits"]) for row in hidden_targets),
        "decision": (
            "Packages the controlled-scale software operator surface into 100M-owned training targets: operator classification, "
            "signature generation, template-body generation, and direct code generation. This is the dataset package, not a completed 100M training run."
        ),
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
