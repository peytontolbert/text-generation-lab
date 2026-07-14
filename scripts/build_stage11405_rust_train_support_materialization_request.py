#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11405
NAME = "stage11405_rust_train_support_materialization_request"
OUT = ART / NAME
SUMMARY = OUT / "rust_train_support_materialization_request.json"
OUT_REQUESTS = OUT / "rust_train_support_materialization_requests.jsonl"

AUDIT_REJECTED = ART / "stage11404_rust_disjoint_train_support_inventory_audit/rust_disjoint_train_support_rejected_or_diagnostic.jsonl"
BLOCKER_QUEUE = ART / "stage11344_rust_web_source_verifier_blocker_audit/source_verifier_blocker_queue.jsonl"


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def repo_family(row: dict[str, Any]) -> str:
    return str(row.get("repo_family") or "unknown")


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_lineage_key") or row.get("root_id") or row.get("source_row_id") or "unknown")


def reasons(row: dict[str, Any]) -> set[str]:
    return {str(reason) for reason in row.get("rejection_reasons") or row.get("blockers") or []}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rejected = read_jsonl(AUDIT_REJECTED)
    blocker_rows = [row for row in read_jsonl(BLOCKER_QUEUE) if row.get("language_family") == "rust"]

    requests: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rejected:
        grouped.setdefault((repo_family(row), root_key(row)), []).append(row)

    priority = 1
    for (repo, root), rows in sorted(grouped.items()):
        all_reasons = sorted({reason for row in rows for reason in reasons(row)})
        has_rust_source = any(row.get("has_rust_source") for row in rows)
        has_verifier = any(row.get("has_selected_verifier_anchor") for row in rows)
        split_intents = sorted({str(row.get("split") or "unknown") for row in rows})
        semantic_values = sorted({str(row.get("semantic_target_value") or "unknown") for row in rows})

        if "strict_eval_or_reserved_intent" in all_reasons:
            lane = "reserved_or_eval_do_not_train"
            action = "keep_out_of_train_support"
        elif not has_rust_source:
            lane = "false_or_unmaterialized_rust_source"
            action = "resolve_real_rust_source_spans_or_quarantine"
        elif not has_verifier:
            lane = "repairable_missing_verifier_anchor"
            action = "add_selected_test_or_verifier_anchor_and_refresh_anticheat"
        else:
            lane = "repairable_contract_refresh"
            action = "refresh_anticheat_contract_and role_distinctness"

        requests.append(
            {
                "priority": priority,
                "lane": lane,
                "action": action,
                "repo_family": repo,
                "root_lineage_key": root,
                "candidate_rows": len(rows),
                "split_intents": split_intents,
                "semantic_target_values": semantic_values,
                "rejection_reasons": all_reasons,
                "minimum_acceptance": [
                    "real Rust source path or Cargo manifest visible in prompt",
                    "selected test, verifier command, or verifier-result anchor",
                    "distinct candidate_change_surface evidence",
                    "distinct symptom_or_call_path evidence",
                    "distinct verifier_and_test_constraint evidence",
                    "target label and role alias not visible before options",
                    "root lineage not overlapping reserved strict replacements",
                ],
                "train_package_allowed_after_repair": lane.startswith("repairable"),
            }
        )
        priority += 1

    for row in blocker_rows:
        requests.append(
            {
                "priority": priority,
                "lane": "blocked_source_row_materialization",
                "action": "recover_local_repo_verifier_or_changed_pair",
                "repo_family": row.get("repo_family") or "unknown",
                "root_lineage_key": row.get("root_id") or row.get("source_row_id"),
                "source_row_id": row.get("source_row_id"),
                "candidate_rows": 1,
                "rejection_reasons": row.get("blockers") or ["missing_local_repo_verifier_or_changed_pair"],
                "minimum_acceptance": [
                    "local_or_fetchable_repo_snapshot",
                    "changed_source_or_config_path",
                    "selected_test_or_verifier_path",
                    "distinct_visible_snippets_for_candidate_roles",
                    "no_role_alias_or_prompt_target_leak",
                ],
                "train_package_allowed_after_repair": True,
            }
        )
        priority += 1

    lane_counts = Counter(row["lane"] for row in requests)
    repairable = [row for row in requests if row["train_package_allowed_after_repair"]]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "rust_train_support_materialization_request_ready",
        "counts": {
            "request_items": len(requests),
            "repairable_after_materialization": len(repairable),
            "blocked_source_rows": len(blocker_rows),
            "minimum_new_roots_needed": 10,
        },
        "lane_counts": dict(sorted(lane_counts.items())),
        "policy": {
            "do_not_train_now": True,
            "why": "Stage11404 admitted zero clean disjoint Rust train-support candidates.",
            "train_allowed_only_after": [
                "at least 10 repaired Rust roots admitted by Stage11404-equivalent gates",
                "reserved strict replacement rows remain excluded",
                "tokenizers-family rows remain diagnostic unless fresh non-overlap is proven",
            ],
        },
        "recommended_next_action": (
            "Materialize the blocked Rust source rows or repair the few Rust-source rows with verifier anchors and anti-cheat "
            "contracts. Re-run Stage11404 after repair; only build a support probe if admitted_unique_roots >= 10."
        ),
        "source_artifacts": {
            "stage11404_rejected": rel(AUDIT_REJECTED),
            "stage11344_blocker_queue": rel(BLOCKER_QUEUE),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "materialization_requests": rel(OUT_REQUESTS),
        },
    }
    write_jsonl(OUT_REQUESTS, requests)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["lane_counts"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
