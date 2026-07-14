#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11325
NAME = "stage11325_alias_free_evidence_scale_inventory"
OUT = ART / NAME
SUMMARY = OUT / "alias_free_evidence_scale_inventory.json"

SOURCES = {
    "stage11275_direct_train": ART
    / "stage11275_direct_retrieval_multilingual_evidence_materialization"
    / "direct_retrieval_multilingual_evidence_train_rows.jsonl",
    "stage11275_direct_validation": ART
    / "stage11275_direct_retrieval_multilingual_evidence_materialization"
    / "direct_retrieval_multilingual_evidence_validation_rows.jsonl",
    "stage11275_direct_strict": ART
    / "stage11275_direct_retrieval_multilingual_evidence_materialization"
    / "direct_retrieval_multilingual_evidence_strict_rows.jsonl",
    "stage11259_candidate_judgment_train": ART
    / "stage11259_true_evidence_candidate_judgment_package"
    / "true_evidence_candidate_judgment_train_rows.jsonl",
    "stage11269_source_specific_train": ART
    / "stage11269_source_specific_evidence_item_materialization"
    / "source_specific_evidence_item_train_rows.jsonl",
    "stage11269_source_specific_validation": ART
    / "stage11269_source_specific_evidence_item_materialization"
    / "source_specific_evidence_item_validation_rows.jsonl",
    "stage11269_source_specific_strict": ART
    / "stage11269_source_specific_evidence_item_materialization"
    / "source_specific_evidence_item_strict_rows.jsonl",
}

BLOCKED_SOURCES = {
    "stage11275_blocked": ART
    / "stage11275_direct_retrieval_multilingual_evidence_materialization"
    / "direct_retrieval_multilingual_evidence_blocked_roots.jsonl",
    "stage11269_blocked": ART
    / "stage11269_source_specific_evidence_item_materialization"
    / "source_specific_evidence_item_blocked_roots.jsonl",
}

TARGET_MAP = {
    "DECISIVE_VERIFIER_TEST_CONSTRAINT": "verifier_and_test_constraint",
    "SUPPORTING_CANDIDATE_CHANGE_SURFACE": "candidate_change_surface",
    "SUPPORTING_SYMPTOM_OR_CALL_PATH": "symptom_or_call_path_analogue",
    "DISTRACTOR_BACKGROUND_CONTEXT": "background_context",
}

PROTECTED_CANARY = ART / "stage11320_alias_free_evidence_item_selection_package"
PROTECTED_FILES = [
    PROTECTED_CANARY / "alias_free_evidence_item_selection_validation_rows.jsonl",
    PROTECTED_CANARY / "alias_free_evidence_item_selection_strict_rows.jsonl",
    PROTECTED_CANARY / "alias_free_residual_diagnostic_rows.jsonl",
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def root_id(row: dict[str, Any]) -> str:
    return str(
        row.get("root_id")
        or row.get("source_root_id")
        or row.get("root_lineage_key")
        or row.get("row_id")
        or ""
    )


def semantic_target(row: dict[str, Any]) -> str:
    source = row.get("standalone_projection_source") or {}
    raw = str(source.get("gold_value") or row.get("semantic_target_value") or "")
    return TARGET_MAP.get(raw, raw)


def split_name(row: dict[str, Any], source_name: str) -> str:
    raw = str(row.get("package_split") or row.get("split") or "")
    if "strict" in raw or source_name.endswith("_strict"):
        return "strict"
    if "validation" in raw or raw == "eval" or source_name.endswith("_validation"):
        return "validation"
    return "train"


def source_family(source_name: str) -> str:
    return source_name.split("_", 1)[0]


def count_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    roots = {root_id(row) for row in rows}
    return {
        "rows": len(rows),
        "roots": len(roots),
        "by_language": dict(
            sorted(Counter(str(row.get("language_family") or "unknown") for row in rows).items())
        ),
        "by_role": dict(sorted(Counter(semantic_target(row) for row in rows).items())),
        "by_repo_top20": Counter(str(row.get("repo_family") or "unknown") for row in rows).most_common(20),
        "split_rows": dict(sorted(Counter(str(row.get("_inventory_split")) for row in rows).items())),
    }


def protected_roots() -> set[str]:
    roots: set[str] = set()
    for path in PROTECTED_FILES:
        for row in read_jsonl(path):
            roots.add(root_id(row))
    return roots


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    protected = protected_roots()
    all_rows: list[dict[str, Any]] = []
    source_summaries: dict[str, Any] = {}

    for name, path in SOURCES.items():
        rows = read_jsonl(path)
        normalized: list[dict[str, Any]] = []
        for row in rows:
            target = semantic_target(row)
            if target not in set(TARGET_MAP.values()):
                continue
            entry = dict(row)
            entry["_inventory_source"] = name
            entry["_inventory_family"] = source_family(name)
            entry["_inventory_split"] = split_name(row, name)
            entry["_inventory_target_role"] = target
            entry["_protected_root_overlap"] = root_id(row) in protected
            normalized.append(entry)
        source_summaries[name] = {
            "path": rel(path),
            "exists": path.exists(),
            "usable": count_rows(normalized),
            "protected_root_overlap_rows": sum(1 for row in normalized if row["_protected_root_overlap"]),
        }
        all_rows.extend(normalized)

    rows_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        rows_by_root[root_id(row)].append(row)

    root_records = []
    for rid, rows in rows_by_root.items():
        roles = sorted({row["_inventory_target_role"] for row in rows})
        languages = sorted({str(row.get("language_family") or "unknown") for row in rows})
        splits = sorted({row["_inventory_split"] for row in rows})
        sources = sorted({row["_inventory_source"] for row in rows})
        root_records.append(
            {
                "root_id": rid,
                "row_count": len(rows),
                "language_family": languages[0] if len(languages) == 1 else "mixed",
                "repo_family": rows[0].get("repo_family"),
                "roles": roles,
                "splits": splits,
                "sources": sources,
                "protected_root_overlap": any(row["_protected_root_overlap"] for row in rows),
                "has_verifier_and_change_pair": {
                    "verifier_and_test_constraint",
                    "candidate_change_surface",
                }.issubset(set(roles)),
                "has_all_four_evidence_roles": set(TARGET_MAP.values()).issubset(set(roles)),
            }
        )

    clean_train_rows = [
        row
        for row in all_rows
        if row["_inventory_split"] == "train" and not row["_protected_root_overlap"]
    ]
    clean_train_roots = {
        record["root_id"]: record
        for record in root_records
        if not record["protected_root_overlap"]
        and any(row["_inventory_split"] == "train" for row in rows_by_root[record["root_id"]])
    }
    verifier_change_roots = [
        record for record in clean_train_roots.values() if record["has_verifier_and_change_pair"]
    ]
    all_role_roots = [
        record for record in clean_train_roots.values() if record["has_all_four_evidence_roles"]
    ]

    blocked_summary = {}
    for name, path in BLOCKED_SOURCES.items():
        rows = read_jsonl(path)
        blocked_summary[name] = {
            "path": rel(path),
            "rows": len(rows),
            "by_language": dict(
                sorted(Counter(str(row.get("language_family") or "unknown") for row in rows).items())
            ),
            "by_blocker": Counter(
                tuple(row.get("blockers") or row.get("reasons") or ["unknown"]) for row in rows
            ).most_common(20),
        }

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "scale_inventory_ready_not_probe_request",
        "source_summaries": source_summaries,
        "aggregate": count_rows(all_rows),
        "clean_train_supply": count_rows(clean_train_rows),
        "clean_train_roots": len(clean_train_roots),
        "clean_train_roots_by_language": dict(
            sorted(Counter(record["language_family"] for record in clean_train_roots.values()).items())
        ),
        "verifier_change_pair_roots": {
            "count": len(verifier_change_roots),
            "by_language": dict(sorted(Counter(r["language_family"] for r in verifier_change_roots).items())),
        },
        "all_four_role_roots": {
            "count": len(all_role_roots),
            "by_language": dict(sorted(Counter(r["language_family"] for r in all_role_roots).items())),
        },
        "blocked_supply": blocked_summary,
        "protected_roots": {
            "count": len(protected),
            "source_files": [rel(path) for path in PROTECTED_FILES],
        },
        "readiness": {
            "can_build_larger_python_alias_free_package": count_rows(clean_train_rows)["by_language"].get("python", 0)
            >= 500,
            "can_build_balanced_multilingual_package": all(
                count_rows(clean_train_rows)["by_language"].get(lang, 0) >= 100
                for lang in ["c_cpp", "python", "rust", "web_js_ts_html"]
            ),
            "rust_supply_still_blocking": count_rows(clean_train_rows)["by_language"].get("rust", 0) < 100,
            "web_supply_still_blocking": count_rows(clean_train_rows)["by_language"].get("web_js_ts_html", 0)
            < 100,
        },
        "recommended_next_action": (
            "build_python_heavy_alias_free_package_only_if_marked_diagnostic; "
            "for promotable multilingual progress, mine/admit fresh Rust and pure-Web verifier/change roots first"
        ),
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
