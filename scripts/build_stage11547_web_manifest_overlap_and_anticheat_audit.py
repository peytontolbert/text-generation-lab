#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11547
NAME = "stage11547_web_manifest_overlap_and_anticheat_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_manifest_overlap_and_anticheat_audit.json"
MANIFEST = OUT / "web_manifest_rows.jsonl"

SOURCE_ROWS = [
    ("stage11528_existing_supply", ART / "stage11528_web_verifier_root_supply_audit/web_verifier_root_supply_rows.jsonl"),
    ("stage11535_openclaw_train", ART / "stage11535_openclaw_web_gold_adjudicated_support_rows/openclaw_web_gold_adjudicated_train_support_rows.jsonl"),
    ("stage11537_openclaw_extra_train", ART / "stage11537_openclaw_extra_web_gold_support_rows/openclaw_extra_web_gold_train_support_rows.jsonl"),
    ("stage11545_openclaw_more_train", ART / "stage11545_openclaw_more_web_gold_train_rows/openclaw_more_web_gold_train_rows.jsonl"),
    ("stage11541_mcp_heldout", ART / "stage11541_mcp_typescript_sdk_web_gold_heldout_rows/mcp_typescript_sdk_web_gold_heldout_rows.jsonl"),
    ("stage11543_sep_heldout", ART / "stage11543_sep_automation_web_gold_heldout_rows/sep_automation_web_gold_heldout_rows.jsonl"),
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def normalize(source_id: str, row: dict[str, Any]) -> dict[str, Any]:
    role = str(row.get("role") or row.get("split_component") or "")
    train = bool(row.get("train_support_only")) or role.startswith("train_support")
    strict = bool(row.get("strict_eval_eligible")) or bool(row.get("strict_eval_candidate")) or role in {"sealed_heldout", "sealed_heldout_candidate", "sealed_web_heldout"}
    if role == "sealed_web_heldout":
        strict = True
        train = False
    if role == "train_support":
        train = True
        strict = False
    anti = row.get("anti_cheat") or row.get("anti_cheat_flags") or {}
    option_count = row.get("option_count")
    if option_count is None:
        option_count = len(row.get("opaque_options") or [])
    repo_family = row.get("git_repo_family") or row.get("repo_family") or "unknown"
    executed = bool(row.get("executed")) or bool(row.get("verifier_anchor")) or bool(anti.get("executed_verifier_output_attached"))
    return {
        "source_id": source_id,
        "row_id": row.get("row_id"),
        "root_id": row.get("root_id"),
        "repo_family": repo_family,
        "task_type": row.get("task_type"),
        "role": role,
        "train": train,
        "strict_heldout": strict,
        "executed": executed,
        "option_count": option_count,
        "deterministic_option_shuffle": bool(anti.get("deterministic_option_shuffle")),
        "target_label_not_visible_before_options": bool(anti.get("target_label_not_visible_before_options")),
        "semantic_target_not_visible_before_options": anti.get("semantic_target_not_visible_before_options", True),
        "admission": row.get("admission") or ("admitted" if not row.get("blockers") else "blocked"),
        "quality": row.get("quality") or "gold_new_materialized",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    missing_sources: list[str] = []
    for source_id, path in SOURCE_ROWS:
        if not path.exists():
            missing_sources.append(rel(path))
            continue
        rows.extend(normalize(source_id, row) for row in load_jsonl(path))

    # Deduplicate by row_id, preferring later materialized rows over stage11528 inventory summaries.
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        by_id[str(row["row_id"])] = row
    rows = list(by_id.values())
    train_roots = {row["root_id"] for row in rows if row["train"] and row["admission"] == "admitted" and row["executed"]}
    heldout_roots = {row["root_id"] for row in rows if row["strict_heldout"] and row["admission"] == "admitted" and row["executed"]}
    train_families = {row["repo_family"] for row in rows if row["root_id"] in train_roots}
    heldout_families = {row["repo_family"] for row in rows if row["root_id"] in heldout_roots}
    root_overlap = sorted(train_roots & heldout_roots)
    family_overlap = sorted(train_families & heldout_families)
    blockers = defaultdict(list)
    for row in rows:
        if row["admission"] != "admitted":
            blockers["not_admitted"].append(row["row_id"])
        if row["strict_heldout"] and row["option_count"] and int(row["option_count"]) < 2:
            blockers["singleton_or_missing_options"].append(row["row_id"])
        if row["strict_heldout"] and not row["deterministic_option_shuffle"]:
            blockers["heldout_missing_deterministic_shuffle"].append(row["row_id"])
        if row["strict_heldout"] and not row["target_label_not_visible_before_options"]:
            blockers["heldout_target_label_leak"].append(row["row_id"])
        if row["strict_heldout"] and row["semantic_target_not_visible_before_options"] is False:
            blockers["heldout_semantic_target_leak"].append(row["row_id"])
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": not missing_sources and not root_overlap and len(train_roots) >= 20 and len(heldout_roots) >= 10,
        "decision": "web_manifest_root_clean_family_overlap_present" if family_overlap else "web_manifest_root_and_family_clean",
        "counts": {
            "rows": len(rows),
            "train_roots_executed_admitted": len(train_roots),
            "heldout_roots_executed_admitted": len(heldout_roots),
            "train_repo_families": len(train_families),
            "heldout_repo_families": len(heldout_families),
            "root_overlap": len(root_overlap),
            "repo_family_overlap": len(family_overlap),
            "rows_by_task": dict(Counter(str(row["task_type"]) for row in rows)),
            "rows_by_source": dict(Counter(row["source_id"] for row in rows)),
        },
        "overlap": {
            "root_overlap": root_overlap,
            "repo_family_overlap": family_overlap,
            "train_repo_families": sorted(train_families),
            "heldout_repo_families": sorted(heldout_families),
        },
        "blocker_counts": {key: len(value) for key, value in blockers.items()},
        "missing_sources": missing_sources,
        "claim_boundary": [
            "Root-level train/heldout overlap is the hard blocker for immediate scoring; repo-family overlap weakens broad Web generalization claims.",
            "This manifest is acceptable for a root-heldout Web diagnostic if root overlap remains zero.",
            "It is not acceptable for a strong repo-family-heldout Web claim until heldout families are separated from train families.",
        ],
        "outputs": {"summary": rel(SUMMARY), "manifest": rel(MANIFEST)},
    }
    write_jsonl(MANIFEST, rows)
    write_json(SUMMARY, summary)
    write_json(SUMMARIES / f"{NAME}.json", summary)


if __name__ == "__main__":
    main()
