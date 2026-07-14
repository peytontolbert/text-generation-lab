#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11276
NAME = "stage11276_capped_direct_retrieval_evidence_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "capped_direct_retrieval_evidence_package.json"
TRAIN_JSONL = OUT_DIR / "capped_direct_retrieval_evidence_train_rows.jsonl"
VALIDATION_JSONL = OUT_DIR / "capped_direct_retrieval_evidence_validation_rows.jsonl"
STRICT_JSONL = OUT_DIR / "capped_direct_retrieval_evidence_strict_rows.jsonl"
ROOT_SELECTION_JSONL = OUT_DIR / "capped_direct_retrieval_evidence_root_selection.jsonl"

SOURCE_DIR = ARTIFACTS / "stage11275_direct_retrieval_multilingual_evidence_materialization"
SOURCE_SUMMARY = SOURCE_DIR / "direct_retrieval_multilingual_evidence_materialization.json"
SOURCE_ROWS = {
    "train": SOURCE_DIR / "direct_retrieval_multilingual_evidence_train_rows.jsonl",
    "validation": SOURCE_DIR / "direct_retrieval_multilingual_evidence_validation_rows.jsonl",
    "strict_eval": SOURCE_DIR / "direct_retrieval_multilingual_evidence_strict_rows.jsonl",
}

ROOT_CAPS = {
    "train": 8,
    "validation": 3,
    "strict_eval": 3,
}


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def group_roots(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("root_id"))].append(row)
    return grouped


def select_capped(split: str, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped = group_roots(rows)
    roots = []
    for root_id, root_rows in grouped.items():
        first = root_rows[0]
        roots.append({
            "root_id": root_id,
            "repo_family": str(first.get("repo_family") or "unknown"),
            "language_family": str(first.get("language_family") or "unknown"),
            "rows": root_rows,
        })
    selected_roots: list[dict[str, Any]] = []
    root_counts_by_repo: Counter[str] = Counter()
    cap = ROOT_CAPS[split]

    # Keep scarce languages first, then fill with capped repo-family diversity.
    roots.sort(key=lambda item: (Counter(r["language_family"] for r in roots)[item["language_family"]], item["repo_family"], item["root_id"]))
    for item in roots:
        if item["language_family"] in {"rust", "web_js_ts_html"}:
            selected_roots.append(item)
            root_counts_by_repo[item["repo_family"]] += 1
    for item in roots:
        if item in selected_roots:
            continue
        if root_counts_by_repo[item["repo_family"]] >= cap:
            continue
        selected_roots.append(item)
        root_counts_by_repo[item["repo_family"]] += 1

    selected_ids = {item["root_id"] for item in selected_roots}
    selected_rows = [row for row in rows if row.get("root_id") in selected_ids]
    selection_rows = [
        {
            "split": split,
            "root_id": item["root_id"],
            "repo_family": item["repo_family"],
            "language_family": item["language_family"],
            "selected": item["root_id"] in selected_ids,
            "row_count": len(item["rows"]),
        }
        for item in roots
    ]
    return selected_rows, selection_rows


def audit(rows_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    root_sets = {split: {str(row.get("root_id")) for row in rows} for split, rows in rows_by_split.items()}
    all_rows = [row for rows in rows_by_split.values() for row in rows]
    return {
        "duplicate_row_ids": len(all_rows) - len({str(row.get("row_id")) for row in all_rows}),
        "root_overlap": {
            "train_validation": sorted(root_sets["train"] & root_sets["validation"]),
            "train_strict": sorted(root_sets["train"] & root_sets["strict_eval"]),
            "validation_strict": sorted(root_sets["validation"] & root_sets["strict_eval"]),
        },
        "all_source_text_materialized": all((row.get("anti_cheat") or {}).get("source_text_materialized") for row in all_rows),
    }


def counts(rows_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for split, rows in rows_by_split.items():
        out[split] = {
            "rows": len(rows),
            "roots": len({str(row.get("root_id")) for row in rows}),
            "by_language": dict(Counter(str(row.get("language_family")) for row in rows)),
            "by_repo_top20": Counter(str(row.get("repo_family")) for row in rows).most_common(20),
            "by_target": dict(Counter(str(row.get("semantic_target_value")) for row in rows)),
        }
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_summary = load_json(SOURCE_SUMMARY)
    if not source_summary.get("passed"):
        raise SystemExit("Stage11275 source package has not passed")
    rows_by_split: dict[str, list[dict[str, Any]]] = {}
    selection: list[dict[str, Any]] = []
    for split, path in SOURCE_ROWS.items():
        selected_rows, selected_roots = select_capped(split, load_jsonl(path))
        rows_by_split[split] = selected_rows
        selection.extend(selected_roots)
    write_jsonl(TRAIN_JSONL, rows_by_split["train"])
    write_jsonl(VALIDATION_JSONL, rows_by_split["validation"])
    write_jsonl(STRICT_JSONL, rows_by_split["strict_eval"])
    write_jsonl(ROOT_SELECTION_JSONL, selection)
    audit_card = audit(rows_by_split)
    passed = (
        audit_card["duplicate_row_ids"] == 0
        and audit_card["all_source_text_materialized"]
        and not any(audit_card["root_overlap"].values())
        and all(counts(rows_by_split)[split]["rows"] > 0 for split in ["train", "validation", "strict_eval"])
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": passed,
        "decision": "capped_direct_retrieval_evidence_package_ready" if passed else "capped_direct_retrieval_evidence_package_blocked",
        "root_caps": ROOT_CAPS,
        "counts": counts(rows_by_split),
        "audit": audit_card,
        "interpretation": {
            "why": "Stage11275 proved direct retrieval mining has multilingual source-backed verifier/change evidence, but was repo-dominated. Stage11276 caps roots per repo family while preserving scarce Rust/Web rows.",
            "claim_limit": "Diagnostic evidence-candidate package only; not a full maintainer-bundle benchmark.",
        },
        "outputs": {
            "train_jsonl": rel(TRAIN_JSONL),
            "validation_jsonl": rel(VALIDATION_JSONL),
            "strict_jsonl": rel(STRICT_JSONL),
            "root_selection_jsonl": rel(ROOT_SELECTION_JSONL),
            "summary_json": rel(SUMMARY_JSON),
        },
        "source_artifacts": {
            "stage11275_summary": rel(SOURCE_SUMMARY),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
