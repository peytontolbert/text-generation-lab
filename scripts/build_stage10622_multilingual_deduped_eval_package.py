#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10622
NAME = "stage10622_multilingual_deduped_eval_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "multilingual_deduped_eval_package.json"
MANIFEST_JSONL = OUT_DIR / "multilingual_deduped_eval_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage10620_reviewed_plus_bootstrap_multilingual_probe_request_capped/reviewed_plus_bootstrap_multilingual_probe_manifest_capped.jsonl"


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


def preference_key(row: dict[str, Any]) -> tuple[int, int, str]:
    source_kind = str(row.get("package_source_kind") or "")
    source_score = 0 if source_kind == "reviewed_bundle_root" else 1
    option_score = 0 if "Options:\n" in str(row.get("prompt_text") or "") else 1
    return (source_score, option_score, str(row.get("row_id") or ""))


def main() -> None:
    rows = load_jsonl(SOURCE_MANIFEST)
    by_row_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_row_id[str(row.get("row_id") or "")].append(row)

    kept_rows: list[dict[str, Any]] = []
    removed_rows: list[dict[str, Any]] = []
    for row_id, group in sorted(by_row_id.items()):
        if len(group) == 1:
            kept_rows.append(group[0])
            continue
        split_set = {str(row.get("split") or "unknown") for row in group}
        if split_set <= {"eval", "strict_eval"}:
            ordered = sorted(group, key=preference_key)
            kept_rows.append(ordered[0])
            removed_rows.extend(ordered[1:])
        else:
            kept_rows.extend(group)

    kept_rows.sort(key=lambda row: (str(row.get("split") or ""), str(row.get("row_id") or ""), str(row.get("package_source_kind") or "")))
    write_jsonl(MANIFEST_JSONL, kept_rows)

    split_counts = Counter(str(row.get("split") or "unknown") for row in kept_rows)
    language_counts = Counter(str(row.get("language_family") or "unknown") for row in kept_rows if row.get("split") in {"eval", "strict_eval"})
    removed_split_counts = Counter(str(row.get("split") or "unknown") for row in removed_rows)
    removed_source_counts = Counter(str(row.get("package_source_kind") or "unknown") for row in removed_rows)

    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "multilingual_eval_deduped_by_row_id",
        "claim_scope": [
            "Repair the stage10620 multilingual package for honest promotable evaluation by deduplicating eval and strict_eval row_ids.",
            "Prefer reviewed_bundle_root variants when reviewed and compiled rows share the same logical row_id.",
            "Retain train rows unchanged; this package is an eval-honesty successor, not a new training curriculum.",
        ],
        "source_manifest": display(SOURCE_MANIFEST),
        "manifest": display(MANIFEST_JSONL),
        "rows": len(kept_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "eval_language_counts": dict(sorted(language_counts.items())),
        "removed_duplicate_rows": {
            "count": len(removed_rows),
            "split_counts": dict(sorted(removed_split_counts.items())),
            "source_kind_counts": dict(sorted(removed_source_counts.items())),
            "sample_row_ids": [str(row.get("row_id") or "") for row in removed_rows[:24]],
        },
        "promotable_eval_note": "Strict and eval no longer contain duplicate logical decisions under the same row_id. This repairs row-level eval bookkeeping, but does not by itself create fresh broader heldout roots.",
        "next_best_step": "Rerun the probe or comparison stack on this deduped package for an honest multilingual score, then build genuinely new bootstrap-heldout roots rather than duplicate reviewed rows.",
    }
    write_json(PACKAGE_JSON, package)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "manifest": display(MANIFEST_JSONL),
            "rows": len(kept_rows),
            "strict_eval_rows": split_counts.get("strict_eval", 0),
        },
    )
    print(json.dumps({"stage": STAGE, "passed": True, "rows": len(kept_rows), "strict_eval_rows": split_counts.get("strict_eval", 0)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
