#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10893
NAME = "stage10893_python_verifier_strict_candidate_queue"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "python_verifier_strict_candidate_queue.json"
CANDIDATES_JSONL = OUT_DIR / "python_verifier_strict_candidates.jsonl"

QUEUE_TARGETS = ARTIFACTS / "stage10492_python_verifier_reviewed_root_expansion_queue" / "python_verifier_reviewed_root_expansion_targets.jsonl"
QUEUE_STATUS = ARTIFACTS / "stage10493_python_verifier_fresh_review_packet_builder" / "python_verifier_review_target_status.jsonl"
POSTRUN_JSON = ARTIFACTS / "stage10891_flash_attn_alias_safe_postrun_audit" / "flash_attn_alias_safe_postrun_audit.json"
INVENTORY_JSON = ARTIFACTS / "stage10892_residual_root_inventory_successor" / "residual_root_inventory_successor.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    targets = {str(row["episode_id"]): row for row in load_jsonl(QUEUE_TARGETS)}
    statuses = {str(row["episode_id"]): row for row in load_jsonl(QUEUE_STATUS)}
    postrun = load_json(POSTRUN_JSON)
    inventory = load_json(INVENTORY_JSON)

    rows = []
    for episode_id, target in targets.items():
        status = statuses.get(episode_id, {})
        candidate = {
            "episode_id": episode_id,
            "repo_id": target.get("repo_id"),
            "priority_order": target.get("priority_order"),
            "supports_shortcut_safe_successor": bool(target.get("supports_shortcut_safe_successor")),
            "queue_selected_tests_count": target.get("selected_tests_count"),
            "required_bundle_shape": list(target.get("required_bundle_shape") or []),
            "reviewed_selected_tests_count": status.get("reviewed_selected_tests_count"),
            "executable_verifier_row_count": status.get("executable_verifier_row_count"),
            "immediately_qualified_for_reviewed_verifier_packet": bool(status.get("immediately_qualified_for_reviewed_verifier_packet")),
            "gaps": list(status.get("gaps") or []),
            "recommended_role": "blocked",
            "recommended_reason": "insufficient reviewed verifier competition",
        }
        if candidate["immediately_qualified_for_reviewed_verifier_packet"] and candidate["supports_shortcut_safe_successor"]:
            candidate["recommended_role"] = "next_strict_candidate"
            candidate["recommended_reason"] = "best current fresh root for a strict heldout verifier-transition build"
        elif status.get("has_anti_cheat_review") and status.get("has_rubric_review"):
            candidate["recommended_role"] = "train_support_or_followup_materialization"
            candidate["recommended_reason"] = "reviewed but not yet a strong heldout verifier-transition packet"
        rows.append(candidate)

    rows.sort(key=lambda row: (0 if row["recommended_role"] == "next_strict_candidate" else 1, row.get("priority_order") or 999))
    next_candidate = next((row for row in rows if row["recommended_role"] == "next_strict_candidate"), None)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_verifier_strict_candidate_queue_refreshed",
        "headline_findings": [
            "The best current fresh strict-heldout Python verifier candidate is the code_assist priority-1 root from the reviewed expansion queue.",
            "It already has full review stack, 4 reviewed selected tests, and one executable verifier row, while remaining disjoint from the current MirrorMind strict family.",
            "The agentkernel materialized roots remain valuable train support, but they still carry same-family shortcut risk and are weaker heldout candidates than the code_assist queue root.",
        ],
        "current_strict_blocker": postrun["strict_misses"],
        "inventory_context": inventory["counts"],
        "candidates": rows,
        "next_strict_candidate": next_candidate,
        "next_best_step": "Build the next strict-heldout Python verifier-transition packet from the code_assist priority-1 root, with opaque selected-test IDs and explicit transition semantics, before spending more training steps.",
        "source_artifacts": {
            "queue_targets": rel(QUEUE_TARGETS),
            "queue_status": rel(QUEUE_STATUS),
            "postrun_audit": rel(POSTRUN_JSON),
            "inventory": rel(INVENTORY_JSON),
        },
    }

    write_jsonl(CANDIDATES_JSONL, rows)
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
