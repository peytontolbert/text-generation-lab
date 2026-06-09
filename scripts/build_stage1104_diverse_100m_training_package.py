#!/usr/bin/env python3
"""Package the Stage1103 diverse surface into 100M-owned targets."""

from __future__ import annotations

import argparse
import json
import re
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


def _target_row(row: dict[str, Any], split: str) -> dict[str, Any]:
    proof = row.get("proof_units", {}) or {}
    fn, args = _signature(str(row["reference_code"]))
    return {
        "task_id": row["task_id"],
        "source_split": split,
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--surface-manifest", type=Path, default=Path("runs/local/artifacts/stage1103_expanded_diverse_software_surface/manifest.json"))
    parser.add_argument("--surface-summary", type=Path, default=Path("runs/local/artifacts/stage1103_expanded_diverse_software_surface_summary.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("runs/local/artifacts/stage1104_diverse_100m_training_package"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1104_diverse_100m_training_package_summary.json"))
    args = parser.parse_args()

    manifest = json.loads(args.surface_manifest.read_text(encoding="utf-8"))
    surface_summary = json.loads(args.surface_summary.read_text(encoding="utf-8"))
    split_paths = {
        "train": Path(manifest["train_path"]),
        "eval": Path(manifest["eval_path"]),
        "hidden": Path(manifest["hidden_path"]),
    }
    targets_by_split = {
        split: [_target_row(row, split) for row in _iter_jsonl(path)]
        for split, path in split_paths.items()
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for split, rows in targets_by_split.items():
        _write_jsonl(args.output_dir / f"{split}_targets.jsonl", rows)
    package_manifest = {
        "artifact_kind": "stage1104_diverse_100m_training_package_manifest",
        "train_targets_path": str(args.output_dir / "train_targets.jsonl"),
        "eval_targets_path": str(args.output_dir / "eval_targets.jsonl"),
        "hidden_targets_path": str(args.output_dir / "hidden_targets.jsonl"),
        "source_surface_manifest": str(args.surface_manifest),
        "target_fields": [
            "operator_label",
            "signature_target",
            "template_body_target",
            "direct_code_target",
        ],
        "verifier_script": "scripts/score_stage1086_software_kbpp_predictions.py",
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(package_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "artifact_kind": "stage1104_diverse_100m_training_package",
        "status": "completed_diverse_100m_training_package",
        "manifest": str(args.output_dir / "manifest.json"),
        "source_surface_manifest": str(args.surface_manifest),
        "train_rows": len(targets_by_split["train"]),
        "eval_rows": len(targets_by_split["eval"]),
        "hidden_rows": len(targets_by_split["hidden"]),
        "hidden_verified_bits_if_solved": sum(int(row["verified_decision_bits"]) for row in targets_by_split["hidden"]),
        "operator_labels": int(surface_summary["operator_count"]),
        "unique_template_body_count": int(surface_summary["unique_template_body_count"]),
        "conservative_unique_family_bits": int(surface_summary["conservative_unique_family_bits"]),
        "decision": "Packages the expanded-diversity software surface into 100M-owned target format. This is a dataset package, not a model result.",
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
