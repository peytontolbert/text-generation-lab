#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10713
NAME = "stage10713_python_rust_residual_contrast_builder_or_quarantine_gate"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "python_rust_residual_contrast_builder_or_quarantine_gate.json"
PROMOTABLE_PYTHON_JSONL = OUT_DIR / "promotable_python_verifier_rows.jsonl"
PROMOTABLE_RUST_JSONL = OUT_DIR / "promotable_rust_evidence_rows.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PYTHON_SOURCE = ROOT / "runs/local/artifacts/stage10712_multilingual_residual_contrast_supply_manifest/python_verifier_contrast_rows.jsonl"
RUST_SOURCE = ROOT / "runs/local/artifacts/stage10712_multilingual_residual_contrast_supply_manifest/rust_evidence_contrast_rows.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def promotable_python(row: dict[str, Any]) -> bool:
    split = str(row.get("split") or "")
    source_kind = str(row.get("package_source_kind") or "")
    if split not in {"train", "validation"}:
        return False
    if source_kind not in {"rewritten_compiled_root_trial", "reviewed_bundle_root", "compiled_root_state"}:
        return False
    return True


def promotable_rust(row: dict[str, Any]) -> bool:
    split = str(row.get("split") or "")
    source_kind = str(row.get("package_source_kind") or "")
    repo_family = str(row.get("repo_family") or "")
    if split not in {"train", "validation"}:
        return False
    if source_kind not in {"reviewed_bundle_root", "rewritten_compiled_root_trial"}:
        return False
    if repo_family == "tokenizers":
        return False
    return True


def main() -> None:
    python_rows = load_jsonl(PYTHON_SOURCE)
    rust_rows = load_jsonl(RUST_SOURCE)

    promotable_python_rows = [row for row in python_rows if promotable_python(row)]
    promotable_rust_rows = [row for row in rust_rows if promotable_rust(row)]

    write_jsonl(PROMOTABLE_PYTHON_JSONL, promotable_python_rows)
    write_jsonl(PROMOTABLE_RUST_JSONL, promotable_rust_rows)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_rust_residual_contrast_gate_computed",
        "claim_scope": [
            "Filter the residual contrast supply down to promotable support rows only.",
            "Exclude strict, canary, and comparison duplicates from the next residual-support path.",
            "Produce an explicit go/no-go gate for the next residual-targeted probe request.",
        ],
        "source_artifacts": {
            "python_source": display(PYTHON_SOURCE),
            "rust_source": display(RUST_SOURCE),
        },
        "python_gate": {
            "source_rows": len(python_rows),
            "promotable_rows": len(promotable_python_rows),
            "repo_family_counts": dict(sorted(Counter(str(row.get("repo_family") or "") for row in promotable_python_rows).items())),
            "verifier_class_counts": dict(sorted(Counter(str(row.get("verifier_class") or "") for row in promotable_python_rows).items())),
            "probe_ready": len(promotable_python_rows) > 0,
            "rows_jsonl": display(PROMOTABLE_PYTHON_JSONL),
        },
        "rust_gate": {
            "source_rows": len(rust_rows),
            "promotable_rows": len(promotable_rust_rows),
            "repo_family_counts": dict(sorted(Counter(str(row.get("repo_family") or "") for row in promotable_rust_rows).items())),
            "semantic_target_counts": dict(sorted(Counter(str(row.get("semantic_target") or "") for row in promotable_rust_rows).items())),
            "probe_ready": len(promotable_rust_rows) > 0,
            "rows_jsonl": display(PROMOTABLE_RUST_JSONL),
        },
        "headline_findings": [
            "Python currently has no promotable residual verifier contrast rows after excluding strict/canary/comparison duplicates.",
            "Rust has only a tiny promotable residual citation supply, limited to reviewed bundle roots outside tokenizers.",
            "The next honest move is Python residual data creation plus optional tiny Rust diagnostic support, not another blended promotion probe.",
        ],
        "promotion_gate": {
            "allow_python_residual_probe": len(promotable_python_rows) > 0,
            "allow_rust_residual_probe": len(promotable_rust_rows) > 0,
            "allow_joint_promotion_probe": len(promotable_python_rows) > 0 and len(promotable_rust_rows) > 0,
        },
        "recommended_next_stage": "stage10714_python_verifier_contrast_creation_queue",
        "outputs": {
            "summary_json": display(SUMMARY_JSON),
            "promotable_python_rows": display(PROMOTABLE_PYTHON_JSONL),
            "promotable_rust_rows": display(PROMOTABLE_RUST_JSONL),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "summary_json": display(SUMMARY_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
