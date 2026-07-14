#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10485
NAME = "stage10485_partitioned_residual_support_anti_cheat_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "partitioned_residual_support_anti_cheat_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PACKAGE_JSON = ROOT / "runs/local/artifacts/stage10484_partitioned_residual_support_package/partitioned_residual_support_package.json"
PYTHON_ROWS = ROOT / "runs/local/artifacts/stage10484_partitioned_residual_support_package/promotable_python_verifier_rows.jsonl"
RUST_ROWS = ROOT / "runs/local/artifacts/stage10484_partitioned_residual_support_package/diagnostic_rust_citation_rows.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10436_repaired_v27_strict_overlay/repaired_v27_strict_overlay.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def prompt_body(row: dict[str, Any]) -> str:
    text = str(row.get("prompt_text") or row.get("input_text") or "")
    return text.split("\nOptions:\n", 1)[0]


def target_value(row: dict[str, Any]) -> str:
    source = row.get("standalone_projection_source") or {}
    return str(source.get("gold_value") or row.get("gold_value") or "")


def prompt_leaks_target(row: dict[str, Any]) -> bool:
    gold = target_value(row)
    return bool(gold and gold in prompt_body(row))


def main() -> None:
    package = load_json(PACKAGE_JSON)
    python_rows = load_jsonl(PYTHON_ROWS)
    rust_rows = load_jsonl(RUST_ROWS)
    strict_rows = load_jsonl(STRICT_ROWS)
    support_rows = python_rows + rust_rows

    strict_row_ids = {str(row.get("row_id") or "") for row in strict_rows}
    strict_root_ids = {str(row.get("source_root_id") or row.get("source_bundle_id") or "") for row in strict_rows}
    strict_bundle_ids = {str(row.get("source_bundle_id") or "") for row in strict_rows}

    exact_row_overlap = sorted(str(row.get("row_id") or "") for row in support_rows if str(row.get("row_id") or "") in strict_row_ids)
    root_overlap_rows = sorted(
        str(row.get("row_id") or "")
        for row in support_rows
        if str(row.get("source_root_id") or row.get("source_bundle_id") or "") in strict_root_ids
    )
    bundle_overlap_rows = sorted(
        str(row.get("row_id") or "")
        for row in support_rows
        if str(row.get("source_bundle_id") or "") in strict_bundle_ids
    )
    prompt_leak_rows = sorted(str(row.get("row_id") or "") for row in support_rows if prompt_leaks_target(row))
    python_non_verifier = sorted(
        str(row.get("row_id") or "") for row in python_rows if str(row.get("task_type") or "") != "verifier_outcome"
    )
    rust_non_citation = sorted(
        str(row.get("row_id") or "") for row in rust_rows if str(row.get("task_type") or "") != "evidence_citation"
    )
    rust_tokenizers_rows = sorted(
        str(row.get("row_id") or "") for row in rust_rows if "tokenizers" in str(row.get("source_bundle_id") or "")
    )
    python_same_family_rows = sorted(
        str(row.get("row_id") or "")
        for row in python_rows
        if str(row.get("repo_family") or "") == "repository_library"
    )

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not exact_row_overlap and not root_overlap_rows and not prompt_leak_rows and not python_non_verifier and not rust_non_citation and not rust_tokenizers_rows and not python_same_family_rows,
        "decision": "partitioned_residual_support_anti_cheat_classified",
        "claim_scope": [
            "Audit the partitioned residual support package for row leakage, root leakage, prompt target leakage, and lane-discipline violations before any new residual probe.",
            "This is a support-package audit, not a new model score claim.",
        ],
        "source_artifacts": {
            "package_json": display(PACKAGE_JSON),
            "promotable_python_rows": display(PYTHON_ROWS),
            "diagnostic_rust_rows": display(RUST_ROWS),
            "strict_overlay": display(STRICT_ROWS),
        },
        "support_rows": len(support_rows),
        "checks": {
            "exact_row_overlap": {"passed": not exact_row_overlap, "rows": exact_row_overlap},
            "root_overlap": {"passed": not root_overlap_rows, "rows": root_overlap_rows},
            "bundle_overlap": {"passed": not bundle_overlap_rows, "rows": bundle_overlap_rows},
            "prompt_target_leak": {"passed": not prompt_leak_rows, "rows": prompt_leak_rows},
            "python_lane_verifier_only": {"passed": not python_non_verifier, "rows": python_non_verifier},
            "rust_lane_citation_only": {"passed": not rust_non_citation, "rows": rust_non_citation},
            "rust_lane_excludes_tokenizers": {"passed": not rust_tokenizers_rows, "rows": rust_tokenizers_rows},
            "python_lane_excludes_repository_library_family": {"passed": not python_same_family_rows, "rows": python_same_family_rows},
        },
        "next_allowed_use": {
            "promotable_python_run_allowed": not exact_row_overlap and not root_overlap_rows and not prompt_leak_rows and not python_non_verifier and not python_same_family_rows,
            "rust_promotable_run_allowed": False,
            "rust_reason": "fresh non-tokenizers E-vs-F disjoint roots are still missing",
        },
        "required_honesty_gates": package["required_honesty_gates"],
    }

    write_json(AUDIT_JSON, audit)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": audit["passed"],
            "decision": audit["decision"],
            "audit": display(AUDIT_JSON),
        },
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
