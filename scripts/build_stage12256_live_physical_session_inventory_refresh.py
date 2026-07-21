#!/usr/bin/env python3
"""Build Stage12256 live physical session inventory refresh.

Refreshes the physical session parent inventory from live source roots. Emits
no raw session content and no raw paths; only hashed path identifiers and file
metadata needed for coverage and derivative attachment.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12256_live_physical_session_inventory_refresh"

SOURCE_ROOTS = {
    "codex_sessions": Path("/home/peyton/.codex/sessions"),
    "cursor_chats": Path("/home/peyton/.cursor/chats"),
    "cursor_projects": Path("/home/peyton/.cursor/projects"),
}


def sha1(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def sha256_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def iso_utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def source_kind(label: str, ext: str) -> str:
    if label == "codex_sessions" and ext == ".jsonl":
        return "codex_session_jsonl"
    if label == "cursor_chats" and ext == ".db":
        return "cursor_chat_db"
    if label == "cursor_projects":
        if ext in {".json", ".jsonl"}:
            return "cursor_project_event_or_metadata"
        if ext in {".ts", ".tsx", ".md", ".txt", ".log"}:
            return "cursor_project_context_file"
        return "cursor_project_other"
    return "unknown_session_like_source"


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


def main() -> int:
    records: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    counts_by_root: dict[str, dict[str, Any]] = {}
    root_card_labels: list[str] = []

    for label, root_path in SOURCE_ROOTS.items():
        root_card_labels.append(label)
        ext_counts: Counter[str] = Counter()
        bytes_by_ext: Counter[str] = Counter()
        mtimes: list[float] = []
        total_bytes = 0
        root_exists = root_path.exists()
        if not root_exists:
            blocked.append({"source_root_label": label, "reason": "root_missing", "root_path_hash": sha1(str(root_path))})
            counts_by_root[label] = {
                "root_exists": False,
                "root_path_hash": sha1(str(root_path)),
                "file_count": 0,
                "total_bytes": 0,
                "extension_counts": {},
                "total_bytes_by_extension": {},
            }
            continue
        for path in root_path.rglob("*"):
            if not path.is_file():
                continue
            try:
                st = path.stat()
            except OSError as exc:
                blocked.append({"source_root_label": label, "reason": "stat_failed", "path_hash": sha1(str(path)), "error": str(exc)})
                continue
            ext = path.suffix or "<no_ext>"
            rel = str(path.relative_to(root_path))
            rel_hash = sha1(rel)
            full_path_hash = sha1(str(path))
            physical_id = sha256_id("phys_src", label, rel_hash)
            row = {
                "physical_source_id": physical_id,
                "source_root_label": label,
                "source_kind": source_kind(label, ext),
                "relative_path_hash": rel_hash,
                "source_file_hash_compat": full_path_hash,
                "extension": ext,
                "file_size_bytes": st.st_size,
                "mtime_utc": iso_utc(st.st_mtime),
                "depth": len(Path(rel).parts),
                "source_root_exists": True,
                "source_path_emitted": False,
                "raw_content_read": False,
                "content_hash_emitted": False,
                "path_policy": "hashed_path_only",
                "refresh_version": "stage12256_v1",
            }
            records.append(row)
            ext_counts[ext] += 1
            bytes_by_ext[ext] += st.st_size
            total_bytes += st.st_size
            mtimes.append(st.st_mtime)
        counts_by_root[label] = {
            "root_exists": True,
            "root_path_hash": sha1(str(root_path)),
            "file_count": sum(ext_counts.values()),
            "total_bytes": total_bytes,
            "extension_counts": dict(ext_counts),
            "total_bytes_by_extension": dict(bytes_by_ext),
            "mtime_range_utc": {
                "min": iso_utc(min(mtimes)) if mtimes else None,
                "max": iso_utc(max(mtimes)) if mtimes else None,
            },
        }

    total_files = len(records)
    total_bytes = sum(int(row["file_size_bytes"]) for row in records)
    root_card = {
        "root_count": len(SOURCE_ROOTS),
        "roots_present": sum(1 for info in counts_by_root.values() if info.get("root_exists")),
        "roots_missing": sum(1 for info in counts_by_root.values() if not info.get("root_exists")),
        "source_root_labels": root_card_labels,
        "total_files": total_files,
        "total_bytes": total_bytes,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "path_policy": "hashed_path_only_no_raw_content",
    }
    previous = {}
    old_counts = ROOT / "runs/local/artifacts/session_like_source_inventory_real/session_inventory_counts_by_root.json"
    if old_counts.exists():
        previous = json.loads(old_counts.read_text(encoding="utf-8"))
    drift = {
        label: {
            "previous_file_count": int((previous.get(label) or {}).get("file_count") or 0),
            "live_file_count": int((counts_by_root.get(label) or {}).get("file_count") or 0),
            "delta": int((counts_by_root.get(label) or {}).get("file_count") or 0) - int((previous.get(label) or {}).get("file_count") or 0),
        }
        for label in SOURCE_ROOTS
    }
    summary = {
        "stage": STAGE,
        "artifact_type": "live_physical_session_inventory_refresh",
        "decision": "live_parent_inventory_refreshed_training_still_blocked",
        "training_allowed": False,
        "claim_boundary": "Live parent inventory only. Emits hashed path metadata, no raw content, no row admission, no training.",
        "root_card": root_card,
        "counts_by_root": counts_by_root,
        "drift_vs_previous_inventory": drift,
        "blocked_count": len(blocked),
        "output_artifacts": {
            "live_physical_source_records": f"runs/local/artifacts/{STAGE}/live_physical_source_records.jsonl",
            "live_session_inventory_root_card": f"runs/local/artifacts/{STAGE}/live_session_inventory_root_card.json",
            "live_session_inventory_counts_by_root": f"runs/local/artifacts/{STAGE}/live_session_inventory_counts_by_root.json",
        },
        "next_stage": {
            "stage": "stage12257_session_derivative_view_attacher",
            "required_join": "derivative.source_file_hash == live_physical_source_records.source_file_hash_compat",
            "training_allowed": False,
        },
    }

    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_jsonl(out_dir / "live_physical_source_records.jsonl", records)
    write_json(out_dir / "live_session_inventory_root_card.json", root_card)
    write_json(out_dir / "live_session_inventory_counts_by_root.json", counts_by_root)
    if blocked:
        write_jsonl(out_dir / "blocked_sources.jsonl", blocked)
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", summary)
    md = f"""# Stage12256 Live Physical Session Inventory Refresh

## Decision

`{summary["decision"]}`

No training is allowed.

## Live Parent Inventory

- total files: `{total_files}`
- total bytes: `{total_bytes}`
- counts by root: `{ {k: v.get('file_count') for k, v in counts_by_root.items()} }`

## Drift vs Previous Snapshot

`{drift}`

This confirms Stage12255 failed for the right reason: the old parent inventory snapshot was stale relative to live source roots.
"""
    write_text(out_dir / "LIVE_PHYSICAL_SESSION_INVENTORY_REFRESH_STAGE12256.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "live_physical_source_records.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
