#!/usr/bin/env python3
"""Build Stage12253 physical session source index.

This turns the physical session inventory into parent records. It does not read
raw session content and does not emit training rows. Its purpose is coverage:
future parsed/trace/episode views must reconcile back to these parent records or
explicitly report an unattached derivative.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12253_physical_session_source_indexer"
INV_ROOT = ROOT / "runs/local/artifacts/session_like_source_inventory_real"
HASHES = INV_ROOT / "session_inventory_relative_path_hashes.jsonl"
COUNTS = INV_ROOT / "session_inventory_counts_by_root.json"
ROOT_CARD = INV_ROOT / "session_inventory_root_card.json"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield line_no, json.loads(line)
            except Exception as exc:
                yield line_no, {"_json_error": str(exc)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def source_kind(label: str, extension: str) -> str:
    if label == "codex_sessions" and extension == ".jsonl":
        return "codex_session_jsonl"
    if label == "cursor_chats" and extension == ".db":
        return "cursor_chat_db"
    if label == "cursor_projects":
        if extension in {".jsonl", ".json"}:
            return "cursor_project_event_or_metadata"
        if extension in {".ts", ".tsx", ".md", ".txt", ".log"}:
            return "cursor_project_context_file"
        return "cursor_project_other"
    return "unknown_session_like_source"


def main() -> int:
    counts = read_json(COUNTS)
    root_card = read_json(ROOT_CARD)
    records: list[dict[str, Any]] = []
    malformed: list[dict[str, Any]] = []
    root_counter: Counter[str] = Counter()
    ext_counter_by_root: dict[str, Counter[str]] = defaultdict(Counter)
    bytes_by_root: Counter[str] = Counter()

    for line_no, row in iter_jsonl(HASHES) or []:
        if "_json_error" in row:
            malformed.append({"line_no": line_no, "error": row["_json_error"]})
            continue
        label = str(row.get("source_root_label") or "")
        rel_hash = str(row.get("relative_path_hash") or "")
        ext = str(row.get("extension") or "")
        size = int(row.get("file_size_bytes") or 0)
        physical_id = stable_id("phys_src", label, rel_hash)
        record = {
            "physical_source_id": physical_id,
            "source_root_label": label,
            "relative_path_hash": rel_hash,
            "extension": ext,
            "source_kind": source_kind(label, ext),
            "file_size_bytes": size,
            "mtime_utc": row.get("mtime_utc"),
            "depth": row.get("depth"),
            "source_root_exists": bool(row.get("source_root_exists")),
            "raw_path_visible": False,
            "path_policy": "relative_path_hash_only",
            "training_allowed": False,
        }
        records.append(record)
        root_counter[label] += 1
        ext_counter_by_root[label][ext] += 1
        bytes_by_root[label] += size

    expected_total = int(root_card.get("total_files") or 0)
    expected_by_root = {k: int(v.get("file_count") or 0) for k, v in counts.items()}
    observed_by_root = dict(root_counter)
    coverage_by_root = {
        label: {
            "expected": expected,
            "observed": observed_by_root.get(label, 0),
            "matches": observed_by_root.get(label, 0) == expected,
        }
        for label, expected in expected_by_root.items()
    }
    coverage_pass = len(records) == expected_total and all(v["matches"] for v in coverage_by_root.values())

    summary = {
        "stage": STAGE,
        "artifact_type": "physical_session_source_index",
        "decision": "physical_parent_index_ready_for_derivative_view_attachment" if coverage_pass else "physical_parent_index_incomplete",
        "training_allowed": False,
        "claim_boundary": "Physical source index only. No raw content, no training rows, no root admission.",
        "input_files": {
            "root_card": str(ROOT_CARD.relative_to(ROOT)),
            "counts_by_root": str(COUNTS.relative_to(ROOT)),
            "relative_path_hashes": str(HASHES.relative_to(ROOT)),
        },
        "coverage": {
            "expected_total_files": expected_total,
            "observed_physical_source_records": len(records),
            "coverage_pass": coverage_pass,
            "coverage_by_root": coverage_by_root,
            "malformed_rows": len(malformed),
        },
        "observed_counts": {
            "by_root": observed_by_root,
            "extensions_by_root": {label: dict(counter) for label, counter in ext_counter_by_root.items()},
            "bytes_by_root": dict(bytes_by_root),
        },
        "output_artifacts": {
            "physical_source_records": f"runs/local/artifacts/{STAGE}/physical_source_records.jsonl",
            "coverage_audit": f"runs/local/artifacts/{STAGE}/coverage_audit.json",
            "summary": f"runs/summaries/{STAGE}.json",
        },
        "next_stage": {
            "stage": "stage12254_session_derivative_view_attacher",
            "required_invariant": "Every parsed/trace/episode/pack/Stage101xx view must attach to physical_source_id or report unattached_derivative_reason.",
            "training_allowed": False,
        },
    }

    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_jsonl(out_dir / "physical_source_records.jsonl", records)
    write_json(out_dir / "coverage_audit.json", summary)
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", summary)
    if malformed:
        write_jsonl(out_dir / "malformed_inventory_rows.jsonl", malformed)
    md = f"""# Stage12253 Physical Session Source Indexer

## Decision

`{summary["decision"]}`

No training is allowed.

## Coverage

- expected physical files: `{expected_total}`
- observed physical source records: `{len(records)}`
- coverage pass: `{coverage_pass}`
- by root: `{observed_by_root}`

## Why This Would Have Caught The Earlier Flaw

Any miner using only the 9-session `current_raw` parsed subset would have failed to report coverage against these `{expected_total}` parent records. The source coverage gate would have marked it as a partial view, not a corpus-level dataset.
"""
    write_text(out_dir / "PHYSICAL_SESSION_SOURCE_INDEX_STAGE12253.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "physical_source_records.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
