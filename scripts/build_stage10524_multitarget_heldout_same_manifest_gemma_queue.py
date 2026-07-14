#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10524
NAME = "stage10524_multitarget_heldout_same_manifest_gemma_queue"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
QUEUE_PATH = OUT_DIR / "multitarget_heldout_same_manifest_gemma_queue.json"
PACKETS_PATH = OUT_DIR / "multitarget_heldout_same_manifest_gemma_packets.jsonl"
SUMMARY_PATH = ROOT / "runs/summaries" / f"{NAME}.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST_SUMMARY = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/split_aware_multitarget_bootstrap_manifest_with_heldout.json"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/strict_eval_rows.jsonl"
EXPECTED_GEMMA_OUTPUTS = ROOT / "runs/local/artifacts/stage10525_multitarget_heldout_same_manifest_comparison/gemma_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
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


def prompt_surface_hash(rows: list[dict[str, Any]]) -> str:
    payload = [
        {
            "row_id": str(row.get("row_id") or ""),
            "language_family": str(row.get("language_family") or ""),
            "target_subtype": str(row.get("target_subtype") or ""),
            "input_text": str(row.get("input_text") or ""),
            "target_text": str(row.get("target_text") or ""),
        }
        for row in sorted(rows, key=lambda item: str(item.get("row_id") or ""))
    ]
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY_PATH),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_queue() -> dict[str, Any]:
    manifest_summary = load_json(MANIFEST_SUMMARY)
    rows = load_jsonl(STRICT_ROWS)
    language_counts: dict[str, int] = {}
    subtype_counts: dict[str, int] = {}
    repo_counts: dict[str, int] = {}
    for row in rows:
        language = str(row.get("language_family") or "unknown")
        subtype = str(row.get("target_subtype") or "unknown")
        repo = str(row.get("repo_id") or row.get("repo_family") or "unknown")
        language_counts[language] = language_counts.get(language, 0) + 1
        subtype_counts[subtype] = subtype_counts.get(subtype, 0) + 1
        repo_counts[repo] = repo_counts.get(repo, 0) + 1
    failures: list[str] = []
    if len(rows) != 36:
        failures.append("strict_rows_not_36")
    expected_languages = {"python": 12, "c_cpp": 8, "rust": 8, "web_js_ts_html": 8}
    for key, value in expected_languages.items():
        if language_counts.get(key, 0) != value:
            failures.append(f"strict_language_count_mismatch::{key}")
    expected_subtypes = {"decisive_evidence": 18, "retrieve_answer_abstain": 18}
    for key, value in expected_subtypes.items():
        if subtype_counts.get(key, 0) != value:
            failures.append(f"strict_subtype_count_mismatch::{key}")
    packet = {
        "cell_key": "root_based_multitarget_bootstrap::heldout_strict36::same_surface_gemma12b",
        "language_family": "multilingual",
        "skill_area": "root_based_multitarget_seq2seq",
        "review_packet_paths": {
            "strict_rows": display(STRICT_ROWS),
            "same_surface_gemma12b_outputs": display(EXPECTED_GEMMA_OUTPUTS),
        },
        "same_surface_packet": {
            "row_count": len(rows),
            "row_ids": [str(row.get("row_id") or "") for row in rows],
            "source_manifest_summary": display(MANIFEST_SUMMARY),
            "source_rows": display(STRICT_ROWS),
            "surface_hash": prompt_surface_hash(rows),
            "language_counts": dict(sorted(language_counts.items())),
            "target_subtype_counts": dict(sorted(subtype_counts.items())),
            "repo_counts": dict(sorted(repo_counts.items())),
            "claim_scope": [
                "Same-surface seq2seq generation on the heldout-safe strict rows from the root-based multitarget bootstrap manifest.",
                "Rows are limited to decisive_evidence and retrieve_answer_abstain projections.",
                "This is a bootstrap-heldout comparison, not the full maintainer benchmark endpoint.",
            ],
            "manifest_audit_references": {
                "stage10521_passed": bool(manifest_summary.get("passed")),
                "stage10521_root_split_violation_count": (((manifest_summary.get("root_split_audit") or {}).get("violation_count")) or 0),
                "stage10521_strict_rows": (((manifest_summary.get("split_counts") or {}).get("strict_eval")) or 0),
            },
        },
    }
    queue = {
        "queue_entries": [
            {
                "cell_key": packet["cell_key"],
                "language_family": "multilingual",
                "priority_rank": 1,
                "priority_reason": "Run Gemma on the exact same 36 strict heldout seq2seq rows used by the root-based multitarget bootstrap probe.",
                "ready_for_gemma_when_authorized": True,
                "gemma_execution_authorized_now": False,
                "harness_execution_authorized_now": False,
                "remaining_blockers": ["explicit_gemma_execution_authorization"],
                "required_missing_evidence": [],
                "review_packet_paths": packet["review_packet_paths"],
                "same_surface_packet": packet["same_surface_packet"],
            }
        ]
    }
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": {
            "strict_rows": len(rows),
            "language_counts": dict(sorted(language_counts.items())),
            "target_subtype_counts": dict(sorted(subtype_counts.items())),
            "repo_count": len(repo_counts),
        },
        "queue": queue,
        "packet": packet,
    }


def main() -> None:
    built = build_queue()
    write_json(QUEUE_PATH, built["queue"])
    write_jsonl(PACKETS_PATH, [built["packet"]])
    next_step = "After the stage10523 runtime bundle is written, run the stage10525 same-surface comparison so Gemma and the saved 100M runtime are both scored on these exact 36 strict rows."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "queue": display(QUEUE_PATH),
            "packets": display(PACKETS_PATH),
        },
        "decision": "Materialized a same-surface Gemma queue for the heldout-safe 36-row seq2seq strict slice produced by the root-based multitarget bootstrap manifest.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY_PATH, summary)
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
