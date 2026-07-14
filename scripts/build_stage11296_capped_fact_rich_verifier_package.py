#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11296
NAME = "stage11296_capped_fact_rich_verifier_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "capped_fact_rich_verifier_package.json"
TRAIN_JSONL = OUT_DIR / "capped_fact_rich_verifier_train_rows.jsonl"
VALIDATION_JSONL = OUT_DIR / "capped_fact_rich_verifier_validation_rows.jsonl"
STRICT_JSONL = OUT_DIR / "capped_fact_rich_verifier_strict_rows.jsonl"
ROOT_SELECTION_JSONL = OUT_DIR / "capped_fact_rich_verifier_root_selection.jsonl"

SOURCE_DIR = ARTIFACTS / "stage11295_fact_rich_verifier_materialization"
SOURCE_ROWS = [
    SOURCE_DIR / "fact_rich_verifier_train_rows.jsonl",
    SOURCE_DIR / "fact_rich_verifier_validation_rows.jsonl",
    SOURCE_DIR / "fact_rich_verifier_strict_rows.jsonl",
]

MAX_ROOTS_PER_REPO = 16
MIN_STRICT_PER_LANGUAGE = 1
MIN_VALIDATION_PER_LANGUAGE = 1


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def group_pairs(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("root_id"))].append(row)
    return {root: vals for root, vals in grouped.items() if len(vals) == 2}


def select_roots(grouped: dict[str, list[dict[str, Any]]]) -> list[str]:
    roots = []
    for root, rows in grouped.items():
        first = rows[0]
        roots.append({
            "root_id": root,
            "repo_family": str(first.get("repo_family") or "unknown"),
            "language_family": str(first.get("language_family") or "unknown"),
        })
    by_repo: Counter[str] = Counter()
    selected: list[str] = []
    # Preserve scarce non-Python languages first; then cap repeated repo families.
    roots.sort(key=lambda x: (0 if x["language_family"] in {"rust", "web_js_ts_html", "c_cpp"} else 1, x["repo_family"], x["root_id"]))
    for item in roots:
        if by_repo[item["repo_family"]] >= MAX_ROOTS_PER_REPO:
            continue
        selected.append(item["root_id"])
        by_repo[item["repo_family"]] += 1
    return selected


def split_roots(selected: list[str], grouped: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    by_lang: dict[str, list[str]] = defaultdict(list)
    for root in selected:
        by_lang[str(grouped[root][0].get("language_family") or "unknown")].append(root)
    split: dict[str, str] = {}
    for _lang, roots in by_lang.items():
        roots = sorted(roots, key=lambda root: (str(grouped[root][0].get("repo_family") or ""), root))
        n = len(roots)
        strict_n = min(max(MIN_STRICT_PER_LANGUAGE, round(n * 0.15)), max(1, n - 2)) if n >= 4 else (1 if n >= 3 else 0)
        val_n = min(max(MIN_VALIDATION_PER_LANGUAGE, round(n * 0.15)), max(0, n - strict_n - 1)) if n >= 4 else (1 if n >= 3 else 0)
        for idx, root in enumerate(roots):
            if idx < strict_n:
                split[root] = "strict_eval"
            elif idx < strict_n + val_n:
                split[root] = "validation"
            else:
                split[root] = "train"
    return split


def rows_by_split(selected: list[str], grouped: dict[str, list[dict[str, Any]]], split_map: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    out = {"train": [], "validation": [], "strict_eval": []}
    for root in selected:
        split = split_map[root]
        for row in grouped[root]:
            payload = dict(row)
            payload["split"] = split
            payload["package_split"] = split
            payload["strict_eval_eligible"] = split == "strict_eval"
            payload["train_support_only"] = split == "train"
            payload["row_id"] = str(payload["row_id"]).replace("stage11295::", "stage11296::")
            sps = dict(payload.get("standalone_projection_source") or {})
            sps["source_inventory_stage"] = "stage11296_capped_fact_rich_verifier_package"
            payload["standalone_projection_source"] = sps
            out[split].append(payload)
    return out


def audit(rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    all_rows = [row for split_rows in rows.values() for row in split_rows]
    root_sets = {split: {str(row.get("root_id")) for row in split_rows} for split, split_rows in rows.items()}
    root_balance = {}
    for split, split_rows in rows.items():
        by_root: dict[str, Counter[str]] = defaultdict(Counter)
        for row in split_rows:
            by_root[str(row.get("root_id"))][str((row.get("standalone_projection_source") or {}).get("candidate_evidence_kind"))] += 1
        root_balance[split] = {
            "roots": len(by_root),
            "unpaired_roots": sorted(root for root, counts in by_root.items() if counts.get("changed") != 1 or counts.get("verifier") != 1),
        }
    return {
        "duplicate_row_ids": len(all_rows) - len({str(row.get("row_id")) for row in all_rows}),
        "root_overlap": {
            "train_validation": sorted(root_sets["train"] & root_sets["validation"]),
            "train_strict": sorted(root_sets["train"] & root_sets["strict_eval"]),
            "validation_strict": sorted(root_sets["validation"] & root_sets["strict_eval"]),
        },
        "root_balance": root_balance,
    }


def counts(rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for split, split_rows in rows.items():
        out[split] = {
            "rows": len(split_rows),
            "roots": len({str(row.get("root_id")) for row in split_rows}),
            "by_language": dict(Counter(str(row.get("language_family")) for row in split_rows)),
            "by_target": dict(Counter(str(row.get("semantic_target_value")) for row in split_rows)),
            "by_repo_top20": Counter(str(row.get("repo_family")) for row in split_rows).most_common(20),
        }
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_rows = [row for path in SOURCE_ROWS for row in load_jsonl(path)]
    grouped = group_pairs(source_rows)
    selected = select_roots(grouped)
    split_map = split_roots(selected, grouped)
    rows = rows_by_split(selected, grouped, split_map)
    audit_card = audit(rows)
    count_card = counts(rows)
    passed = (
        audit_card["duplicate_row_ids"] == 0
        and not any(audit_card["root_overlap"].values())
        and all(not v["unpaired_roots"] for v in audit_card["root_balance"].values())
        and count_card["train"]["roots"] >= 20
        and count_card["validation"]["roots"] >= 4
        and count_card["strict_eval"]["roots"] >= 4
    )
    selection_rows = [
        {
            "root_id": root,
            "repo_family": str(grouped[root][0].get("repo_family") or "unknown"),
            "language_family": str(grouped[root][0].get("language_family") or "unknown"),
            "split": split_map[root],
        }
        for root in selected
    ]
    write_jsonl(TRAIN_JSONL, rows["train"])
    write_jsonl(VALIDATION_JSONL, rows["validation"])
    write_jsonl(STRICT_JSONL, rows["strict_eval"])
    write_jsonl(ROOT_SELECTION_JSONL, selection_rows)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": passed,
        "decision": "capped_fact_rich_verifier_package_ready" if passed else "capped_fact_rich_verifier_package_blocked",
        "max_roots_per_repo": MAX_ROOTS_PER_REPO,
        "counts": count_card,
        "audit": audit_card,
        "source_root_count": len(grouped),
        "selected_root_count": len(selected),
        "rationale": "Cap Stage11295 repo-family dominance and re-split paired fact-rich verifier/change roots by language.",
        "outputs": {
            "train_jsonl": rel(TRAIN_JSONL),
            "validation_jsonl": rel(VALIDATION_JSONL),
            "strict_jsonl": rel(STRICT_JSONL),
            "root_selection_jsonl": rel(ROOT_SELECTION_JSONL),
            "summary_json": rel(SUMMARY_JSON),
        },
        "source_artifacts": {
            "stage11295_summary": rel(SOURCE_DIR / "fact_rich_verifier_materialization.json"),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
