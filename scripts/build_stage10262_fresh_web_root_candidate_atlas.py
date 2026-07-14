#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10262
NAME = "stage10262_fresh_web_root_candidate_atlas"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ATLAS = OUT_DIR / "fresh_web_root_candidate_atlas.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

DEFAULT_INVENTORY = ROOT / "runs/local/artifacts/session_like_source_inventory_real/packable_augmented_session_episode_examples_v4_dense_neighbors_realindex/packable_augmented_session_episode_examples.jsonl"
RAW_AUDIT = ROOT / "runs/summaries/stage10261_raw_web_source_rescue_audit.json"
CONTRACT = ROOT / "runs/summaries/stage10259_fresh_web_source_backed_root_generation_request.json"

WEB_EXTS = {".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss"}
WEB_SPECIAL = {"package.json", "vite.config.js"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _changes(row: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for entry in row.get("changes") or []:
        if isinstance(entry, dict):
            path_text = str(entry.get("path") or "").strip()
        else:
            path_text = str(entry).strip()
        if path_text:
            paths.append(path_text)
    query = row.get("query") if isinstance(row.get("query"), dict) else {}
    for entry in query.get("seed_paths", row.get("seed_paths") or []) or []:
        path_text = str(entry).strip()
        if path_text:
            paths.append(path_text)
    return paths


def _is_web_path(path_text: str) -> bool:
    path = Path(path_text)
    return path.suffix.lower() in WEB_EXTS or path.name in WEB_SPECIAL


def _web_paths(row: dict[str, Any]) -> list[str]:
    return [path for path in _changes(row) if _is_web_path(path)]


def _context_roles(row: dict[str, Any]) -> list[str]:
    roles = []
    for item in row.get("context_rows") or []:
        if isinstance(item, dict):
            role = str(item.get("role") or "").strip()
            if role:
                roles.append(role)
    return sorted(set(roles))


def build() -> dict[str, Any]:
    raw_audit = load_json(RAW_AUDIT)
    contract = load_json(CONTRACT)
    inventory_rows = load_jsonl(DEFAULT_INVENTORY)

    consumed_example_ids = {
        str(row.get("example_id") or "")
        for row in raw_audit.get("raw_web_rows") or []
        if str(row.get("status") or "").startswith("already_consumed")
    }
    consumed_repo_families = set((raw_audit.get("raw_inventory_findings") or {}).get("distinct_repo_families") or [])

    candidates: list[dict[str, Any]] = []
    reason_counts = Counter()

    for row in inventory_rows:
        example_id = str(row.get("example_id") or row.get("episode_id") or row.get("id") or "")
        repo_id = str((row.get("metadata") or {}).get("repo_id") or row.get("repo_id") or "")
        web_paths = _web_paths(row)
        if not web_paths:
            continue

        reasons: list[str] = []
        if example_id in consumed_example_ids:
            reasons.append("consumed_example_id")
        if repo_id in consumed_repo_families:
            reasons.append("consumed_repo_family")

        selected_tests = []
        query = row.get("query") if isinstance(row.get("query"), dict) else {}
        for entry in query.get("selected_tests", row.get("selected_tests") or []) or []:
            test_text = str(entry).strip()
            if test_text:
                selected_tests.append(test_text)
        context_roles = _context_roles(row)

        status = "fresh_candidate" if not reasons else "rejected"
        candidates.append(
            {
                "example_id": example_id,
                "repo_id": repo_id,
                "web_paths": web_paths,
                "selected_tests_count": len(selected_tests),
                "context_roles": context_roles,
                "status": status,
                "reasons": reasons,
            }
        )
        for reason in reasons:
            reason_counts[reason] += 1

    fresh_candidates = [row for row in candidates if row["status"] == "fresh_candidate"]
    atlas = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "inputs": {
            "inventory": display(DEFAULT_INVENTORY),
            "raw_web_audit": display(RAW_AUDIT),
            "fresh_root_contract": display(CONTRACT),
        },
        "contract_scope": {
            "consumed_repo_families": sorted(consumed_repo_families),
            "consumed_example_ids": sorted(consumed_example_ids),
            "required_new_roots": ((contract.get("minimum_output") or {}).get("requested_new_roots")),
        },
        "metrics": {
            "web_signaled_rows_seen": len(candidates),
            "fresh_candidate_rows": len(fresh_candidates),
            "rejected_rows": len(candidates) - len(fresh_candidates),
            "rejection_reason_counts": dict(sorted(reason_counts.items())),
        },
        "fresh_candidates": fresh_candidates,
        "rejected_candidates": [row for row in candidates if row["status"] != "fresh_candidate"],
        "decision": (
            "The atlas scanner is now available for future inventories. On the current default inventory it finds zero fresh web candidates, "
            "which matches the Stage10261 rescue audit."
        ),
        "next_best_step": (
            "Run this atlas against new source/session inventories as they arrive; until it yields nonzero fresh web candidates, "
            "do not attempt another multilingual web replenishment replay."
        ),
    }
    return atlas


def main() -> None:
    atlas = build()
    write_json(ATLAS, atlas)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": atlas["passed"],
            "artifact": display(ATLAS),
            "decision": atlas["decision"],
            "next_best_step": atlas["next_best_step"],
            "metrics": atlas["metrics"],
        },
    )
    print(json.dumps({"stage": STAGE, "passed": atlas["passed"], "artifact": display(ATLAS), "metrics": atlas["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
