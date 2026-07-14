#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
STAGE = 10641
NAME = "stage10641_gold_handle_lineage_mismatch_audit"
PREVIEW_ROWS_PATH = (
    ROOT
    / "runs/local/artifacts/stage10640_corrected_slice_visible_evidence_materialization_audit"
    / "corrected_slice_visible_evidence_materialized_preview_rows.jsonl"
)
SPANS_PATH = Path("/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl")
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "gold_handle_lineage_mismatch_audit.json"

HANDLE_RE = re.compile(r"^(?P<kind>repo|localchunk|paper|dataset|localrepochunk)_(?P<body>.+)_(?P<slot>\d+)_(?P<hash>[0-9a-f]{10})$")
EXTS = {"py", "rs", "cpp", "cc", "c", "cu", "cuh", "h", "hpp", "toml", "md", "txt", "js", "ts", "tsx", "jsx", "html", "css"}


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def normalize(text: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(text).lower())).strip("_")


def basename_from_handle(handle: str) -> str | None:
    m = HANDLE_RE.match(handle)
    if not m:
        return None
    body = normalize(m.group("body"))
    parts = body.split("_")
    ext_idx = None
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] in EXTS:
            ext_idx = i
            break
    if ext_idx is None or ext_idx == 0:
        return None
    name = "_".join(parts[:ext_idx])
    ext = parts[ext_idx]
    filename = f"{name}.{ext}"
    return filename


def main() -> None:
    rows = load_jsonl(PREVIEW_ROWS_PATH)
    unresolved = [row for row in rows if row.get("gold_resolution_kind") != "repo_span_text"]

    basename_requests: dict[str, dict[str, Any]] = {}
    for row in unresolved:
        handle = str(row.get("gold_handle") or "")
        base = basename_from_handle(handle)
        if base:
            basename_requests[base] = {
                "expected_repo_id": str(row.get("repo_id") or ""),
                "expected_repo_norm": normalize(str(row.get("repo_id") or "")),
            }

    basename_hits: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if SPANS_PATH.exists() and basename_requests:
        with SPANS_PATH.open("r", encoding="utf-8") as handle:
            for line in handle:
                obj = json.loads(line)
                span_id = str(obj.get("span_id") or "")
                if ":" not in span_id:
                    continue
                corpus, path_text = span_id.split(":", 1)
                base = Path(path_text).name
                if base not in basename_requests:
                    continue
                hits = basename_hits[base]
                if len(hits) >= 5:
                    continue
                hits.append(
                    {
                        "corpus": corpus,
                        "path": path_text,
                        "source_id": str(obj.get("source_id") or ""),
                        "corpus_norm": normalize(corpus),
                    }
                )

    audit_rows: list[dict[str, Any]] = []
    mismatched = 0
    absent = 0
    local_unknown = 0
    for row in unresolved:
        handle = str(row.get("gold_handle") or "")
        base = basename_from_handle(handle)
        if str(row.get("gold_resolution_kind") or "").endswith("summary_only") and handle.startswith(("localchunk_", "localrepochunk_")):
            classification = "local_or_chunk_handle_not_resolved"
            local_unknown += 1
            matches = []
        elif not base:
            classification = "basename_not_derivable"
            matches = []
            absent += 1
        else:
            matches = basename_hits.get(base, [])
            expected_norm = normalize(str(row.get("repo_id") or ""))
            same_repo = [hit for hit in matches if hit["corpus_norm"] == expected_norm]
            if same_repo:
                classification = "basename_present_same_corpus_but_not_recovered"
            elif matches:
                classification = "basename_present_under_different_corpus"
                mismatched += 1
            else:
                classification = "basename_absent_from_span_export"
                absent += 1
        audit_rows.append(
            {
                "row_id": row["row_id"],
                "language_family": row.get("language_family"),
                "repo_id": row.get("repo_id"),
                "gold_handle": handle,
                "gold_resolution_kind": row.get("gold_resolution_kind"),
                "derived_basename": base,
                "classification": classification,
                "span_matches": matches,
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "unresolved_gold_handles_classified",
        "summary": {
            "unresolved_gold_rows": len(unresolved),
            "basename_present_under_different_corpus": mismatched,
            "basename_absent_from_span_export": absent,
            "local_or_chunk_handle_not_resolved": local_unknown,
        },
        "interpretation": [
            "Rows classified as basename_present_under_different_corpus indicate source-lineage drift or corpus naming mismatch, not just a weak prompt or decode contract.",
            "Rows classified as basename_absent_from_span_export likely need a different source inventory or a new root rebuild rather than more handle decoding.",
            "Local or chunk-only unresolved gold handles are not maintainers-grade evidence yet and should not be promoted without a real source materialization path.",
        ],
        "rows": audit_rows,
    }

    write_json(AUDIT_JSON, payload)
    print(json.dumps({"ok": True, "audit": str(AUDIT_JSON), "summary": payload["summary"]}, indent=2))


if __name__ == "__main__":
    main()
