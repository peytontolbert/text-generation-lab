#!/usr/bin/env python3
"""Validate structured probe telemetry artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_STRUCTURED_TELEMETRY = (
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "field_exact_by_split.json",
    "field_exact_by_cell.json",
    "confusion_matrix.json",
    "margin_confidence_entropy.jsonl",
    "high_confidence_wrong_rows.jsonl",
    "row_gradient_norms.jsonl",
    "failure_bucket_card.json",
    "module_delta_norms.json",
)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_artifacts(output_dir: Path) -> dict[str, Any]:
    present = {name: (output_dir / name).is_file() for name in REQUIRED_STRUCTURED_TELEMETRY}
    missing = [name for name, ok in present.items() if not ok]
    nonempty_jsonl = {}
    for name in REQUIRED_STRUCTURED_TELEMETRY:
        path = output_dir / name
        if path.suffix == ".jsonl" and path.exists():
            nonempty_jsonl[name] = bool(path.read_text(encoding="utf-8").strip())
    return {
        "output_dir": str(output_dir),
        "required_artifacts": list(REQUIRED_STRUCTURED_TELEMETRY),
        "present": present,
        "missing": missing,
        "nonempty_jsonl": nonempty_jsonl,
        "passed": not missing,
    }


def emit_placeholder_contract(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_STRUCTURED_TELEMETRY:
        path = output_dir / name
        if path.suffix == ".jsonl":
            path.write_text("", encoding="utf-8")
        else:
            write_json(path, {"artifact": name, "placeholder": True, "model_execution_attempted": False})
    return validate_artifacts(output_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--emit-placeholder-contract", action="store_true")
    args = parser.parse_args()
    card = emit_placeholder_contract(args.output_dir) if args.emit_placeholder_contract else validate_artifacts(args.output_dir)
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0 if card["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
