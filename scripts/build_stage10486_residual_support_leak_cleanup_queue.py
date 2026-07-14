#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10486
NAME = "stage10486_residual_support_leak_cleanup_queue"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
QUEUE_JSON = OUT_DIR / "residual_support_leak_cleanup_queue.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

AUDIT_JSON = ROOT / "runs/local/artifacts/stage10485_partitioned_residual_support_anti_cheat_audit/partitioned_residual_support_anti_cheat_audit.json"
PYTHON_ROWS = ROOT / "runs/local/artifacts/stage10484_partitioned_residual_support_package/promotable_python_verifier_rows.jsonl"
RUST_ROWS = ROOT / "runs/local/artifacts/stage10484_partitioned_residual_support_package/diagnostic_rust_citation_rows.jsonl"


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


def classify_leak(row: dict[str, Any]) -> dict[str, Any]:
    prompt = prompt_body(row)
    gold = target_value(row)
    header_form = f"[{gold}]"
    lane = "python_promotable_candidate" if str(row.get("language_family") or "") == "python" else "rust_diagnostic_only"
    return {
        "row_id": str(row.get("row_id") or ""),
        "language_family": str(row.get("language_family") or ""),
        "task_type": str(row.get("task_type") or ""),
        "source_bundle_id": str(row.get("source_bundle_id") or ""),
        "target_value": gold,
        "target_visible_verbatim": bool(gold and gold in prompt),
        "target_visible_in_header": bool(gold and header_form in prompt),
        "lane": lane,
        "likely_leak_source": "candidate_surface_header_or_visible_path",
        "cleanup_recommendation": [
            "replace literal candidate paths in evidence headers with opaque candidate IDs or role-only headers",
            "preserve evidence semantics in snippet body without repeating the gold target string verbatim before options",
            "rerun prompt-target-leak audit before any execution request",
        ],
    }


def main() -> None:
    audit = load_json(AUDIT_JSON)
    rows = load_jsonl(PYTHON_ROWS) + load_jsonl(RUST_ROWS)
    leaked = [classify_leak(row) for row in rows if str(row.get("row_id") or "") in set((audit["checks"]["prompt_target_leak"]["rows"]))]

    queue = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "residual_support_leak_cleanup_queue_ready",
        "claim_scope": [
            "Convert the anti-cheat failure from stage10485 into an explicit cleanup queue for support-row de-leakage.",
            "This queue blocks promotable use until the target string is no longer visible verbatim in prompt-visible evidence.",
        ],
        "source_artifacts": {
            "anti_cheat_audit": display(AUDIT_JSON),
            "python_rows": display(PYTHON_ROWS),
            "rust_rows": display(RUST_ROWS),
        },
        "leaked_rows": leaked,
        "summary": {
            "leaked_row_count": len(leaked),
            "python_promotable_candidate_leaks": sum(1 for row in leaked if row["lane"] == "python_promotable_candidate"),
            "rust_diagnostic_leaks": sum(1 for row in leaked if row["lane"] == "rust_diagnostic_only"),
        },
        "required_cleanup_before_next_promotable_run": [
            "De-leak the two Python verifier support rows first; they are the only candidate promotable lane.",
            "Keep Rust rows diagnostic-only even after de-leakage until fresh non-tokenizers E-vs-F roots exist.",
            "Do not rerun a promotion-style probe until stage10485 passes with prompt_target_leak=false.",
        ],
    }

    write_json(QUEUE_JSON, queue)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": queue["decision"],
            "queue": display(QUEUE_JSON),
        },
    )
    print(json.dumps(queue, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
