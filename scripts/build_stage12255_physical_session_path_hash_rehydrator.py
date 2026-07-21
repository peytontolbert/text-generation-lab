#!/usr/bin/env python3
"""Build Stage12255 physical session path-hash rehydrator.

The original no-content inventory stores relative_path_hash, while parsed
derivative rows use source_file_hash computed from the full source path. This
stage scans physical roots to compute attachable non-content path hashes. It
does not read file contents or emit raw paths by default.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12255_physical_session_path_hash_rehydrator"
INV_ROOT = ROOT / "runs/local/artifacts/session_like_source_inventory_real"
COUNTS = INV_ROOT / "session_inventory_counts_by_root.json"
STAGE12253 = ROOT / "runs/local/artifacts/stage12253_physical_session_source_indexer/physical_source_records.jsonl"


def path_sha1(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


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
            yield line_no, json.loads(line)


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


def extension_matches(path: Path, extension_counts: dict[str, Any]) -> bool:
    ext = path.suffix or "<no_ext>"
    return ext in extension_counts


def main() -> int:
    counts = read_json(COUNTS)
    stage12253_records = [row for _, row in iter_jsonl(STAGE12253) or []]
    by_relative = {(row["source_root_label"], row["relative_path_hash"]): row for row in stage12253_records}

    records: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    observed_by_root: Counter[str] = Counter()
    matched_stage12253 = 0
    duplicate_full_path_hashes: dict[str, list[str]] = defaultdict(list)

    for label, info in sorted(counts.items()):
        root_path = Path(str(info.get("root_path") or "")).expanduser()
        extension_counts = dict(info.get("extension_counts") or {})
        if not root_path.exists():
            blocked.append({"source_root_label": label, "reason": "root_missing", "root_path_hash": path_sha1(str(root_path))})
            continue
        for path in root_path.rglob("*"):
            if not path.is_file() or not extension_matches(path, extension_counts):
                continue
            try:
                rel = str(path.relative_to(root_path))
            except Exception:
                rel = path.name
            rel_hash = path_sha1(rel)
            full_path_hash = path_sha1(str(path))
            stage12253_record = by_relative.get((label, rel_hash))
            physical_source_id = (
                stage12253_record.get("physical_source_id")
                if stage12253_record
                else stable_id("phys_src", label, rel_hash)
            )
            if stage12253_record:
                matched_stage12253 += 1
            row = {
                "physical_source_id": physical_source_id,
                "source_root_label": label,
                "source_kind": (stage12253_record or {}).get("source_kind"),
                "relative_path_hash": rel_hash,
                "source_file_hash_compat": full_path_hash,
                "extension": path.suffix or "<no_ext>",
                "file_size_bytes": path.stat().st_size,
                "mtime_ns": path.stat().st_mtime_ns,
                "source_path_emitted": False,
                "raw_content_read": False,
                "content_hash_emitted": False,
                "attach_key_for_derivative_source_file_hash": full_path_hash,
                "match_stage12253_parent": bool(stage12253_record),
                "rehydrator_version": "stage12255_v1",
            }
            records.append(row)
            observed_by_root[label] += 1
            duplicate_full_path_hashes[full_path_hash].append(physical_source_id)

    duplicate_clusters = [
        {"source_file_hash_compat": h, "physical_source_ids": ids}
        for h, ids in duplicate_full_path_hashes.items()
        if len(ids) > 1
    ]
    expected_total = sum(int((info.get("file_count") or 0)) for info in counts.values())
    coverage_by_root = {
        label: {
            "expected": int((info.get("file_count") or 0)),
            "observed": observed_by_root.get(label, 0),
            "matches": observed_by_root.get(label, 0) == int((info.get("file_count") or 0)),
        }
        for label, info in counts.items()
    }
    coverage_pass = len(records) == expected_total and all(v["matches"] for v in coverage_by_root.values())

    summary = {
        "stage": STAGE,
        "artifact_type": "physical_session_path_hash_rehydrator",
        "decision": "path_hash_attachment_index_ready" if coverage_pass else "path_hash_attachment_index_incomplete",
        "training_allowed": False,
        "claim_boundary": (
            "No-content path-hash attachment index only. Raw paths and raw contents are not emitted. "
            "No root admission or training is authorized."
        ),
        "coverage": {
            "expected_total_files": expected_total,
            "observed_path_hash_records": len(records),
            "coverage_pass": coverage_pass,
            "coverage_by_root": coverage_by_root,
            "matched_stage12253_parent_records": matched_stage12253,
            "stage12253_parent_records": len(stage12253_records),
            "blocked_count": len(blocked),
            "duplicate_full_path_hash_clusters": len(duplicate_clusters),
        },
        "outputs": {
            "path_hash_attachment_index": f"runs/local/artifacts/{STAGE}/path_hash_attachment_index.jsonl",
            "duplicate_full_path_hash_clusters": f"runs/local/artifacts/{STAGE}/duplicate_full_path_hash_clusters.jsonl",
            "blocked_sources": f"runs/local/artifacts/{STAGE}/blocked_sources.jsonl",
        },
        "next_stage": {
            "stage": "stage12256_session_derivative_view_attacher",
            "required_join": "derivative.source_file_hash == path_hash_attachment_index.source_file_hash_compat",
            "training_allowed": False,
        },
    }

    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_jsonl(out_dir / "path_hash_attachment_index.jsonl", records)
    if duplicate_clusters:
        write_jsonl(out_dir / "duplicate_full_path_hash_clusters.jsonl", duplicate_clusters)
    if blocked:
        write_jsonl(out_dir / "blocked_sources.jsonl", blocked)
    write_json(out_dir / "path_hash_rehydration_summary.json", summary)
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", summary)
    md = f"""# Stage12255 Physical Session Path-Hash Rehydrator

## Decision

`{summary["decision"]}`

No training is allowed.

## Purpose

Existing derivative rows use `source_file_hash` from full source paths. The no-content physical inventory had only `relative_path_hash`. This stage scans physical roots and emits non-content path hashes so derivative views can attach exactly without raw content.

## Coverage

- expected files: `{expected_total}`
- observed path-hash records: `{len(records)}`
- coverage pass: `{coverage_pass}`
- matched Stage12253 parents: `{matched_stage12253}/{len(stage12253_records)}`

Next: `stage12256_session_derivative_view_attacher`.
"""
    write_text(out_dir / "PHYSICAL_SESSION_PATH_HASH_REHYDRATOR_STAGE12255.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "path_hash_attachment_index.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
