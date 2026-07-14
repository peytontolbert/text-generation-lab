#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10921
NAME = "stage10921_broad_pure_web_source_acquisition_atlas"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "broad_pure_web_source_acquisition_atlas.json"

SESSION_ROOT = ARTIFACTS / "session_like_source_inventory_real"
PRIOR_ATLAS = ARTIFACTS / "stage10262_fresh_web_root_candidate_atlas" / "fresh_web_root_candidate_atlas.json"
WEB_GAP = ARTIFACTS / "stage10418_pure_web_verifier_anchor_gap_audit" / "pure_web_verifier_anchor_gap_audit.json"
WEB_RECOVERY = ARTIFACTS / "stage10920_pure_web_verifier_anchor_recovery_audit" / "pure_web_verifier_anchor_recovery_audit.json"

WEB_EXTS = {".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss"}
WEB_SPECIAL = {"package.json", "vite.config.js", "vite.config.ts", "tsconfig.json"}
INVENTORY_MARKERS = (
    "local_root_session_episodes",
    "augmented_session_episodes",
    "packable_session_episode_examples",
    "packable_augmented_session_episode_examples",
    "non_agentkernel_patch_plus_exec_target_subset",
)
EXCLUDE_MARKERS = (
    "parsed_bounded_jsonl_metadata",
    "session_execution_traces",
    "session_episode_seed_candidates",
    "resolved_session_episode_seeds",
    "long_context_pack_training_rows",
    "long_context_packs",
    "quality_reports",
    "novelty_report",
    "verification_family_filtered_report",
    "strict_long_context_pack_quality_reports",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def iter_inventory_paths() -> list[Path]:
    paths: list[Path] = []
    for path in sorted(SESSION_ROOT.rglob("*.jsonl")):
        text = str(path.relative_to(SESSION_ROOT))
        if not any(marker in text for marker in INVENTORY_MARKERS):
            continue
        if any(marker in text for marker in EXCLUDE_MARKERS):
            continue
        paths.append(path)
    return paths


def row_id(row: dict[str, Any]) -> str:
    return str(
        row.get("example_id")
        or row.get("episode_id")
        or row.get("id")
        or row.get("seed_id")
        or ""
    ).strip()


def repo_id(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    query = row.get("query") if isinstance(row.get("query"), dict) else {}
    return str(
        row.get("repo_id")
        or metadata.get("repo_id")
        or query.get("repo_id")
        or metadata.get("repo_hint")
        or row.get("repo_hint")
        or ""
    ).strip()


def change_paths(row: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for source in (
        row.get("changes") or [],
        row.get("seed_paths") or [],
        (row.get("query") or {}).get("seed_paths", []) if isinstance(row.get("query"), dict) else [],
    ):
        for entry in source or []:
            if isinstance(entry, dict):
                path_text = str(entry.get("path") or "").strip()
            else:
                path_text = str(entry).strip()
            if path_text:
                out.append(path_text)
    seen: set[str] = set()
    deduped: list[str] = []
    for item in out:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def is_web_path(path_text: str) -> bool:
    path = Path(path_text)
    return path.suffix.lower() in WEB_EXTS or path.name in WEB_SPECIAL


def web_paths(row: dict[str, Any]) -> list[str]:
    return [path for path in change_paths(row) if is_web_path(path)]


def selected_tests(row: dict[str, Any]) -> list[str]:
    tests: list[str] = []
    for source in (
        row.get("selected_tests") or [],
        (row.get("query") or {}).get("selected_tests", []) if isinstance(row.get("query"), dict) else [],
    ):
        for entry in source or []:
            text = str(entry).strip()
            if text:
                tests.append(text)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in tests:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def candidate_paths(row: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for source in (
        row.get("candidate_paths") or [],
        (row.get("bundle_summary") or {}).get("candidate_paths", []) if isinstance(row.get("bundle_summary"), dict) else [],
    ):
        for entry in source or []:
            text = str(entry).strip()
            if text:
                out.append(text)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in out:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def context_roles(row: dict[str, Any]) -> list[str]:
    roles: set[str] = set()
    for item in row.get("context_rows") or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        if role:
            roles.add(role)
    return sorted(roles)


def is_pure_web(row: dict[str, Any]) -> bool:
    paths = change_paths(row)
    if not paths:
        return False
    return all(is_web_path(path) for path in paths)


def build() -> dict[str, Any]:
    prior_atlas = load_json(PRIOR_ATLAS)
    web_gap = load_json(WEB_GAP)
    web_recovery = load_json(WEB_RECOVERY)
    consumed_repo_families = set((prior_atlas.get("contract_scope") or {}).get("consumed_repo_families") or [])
    consumed_example_ids = set((prior_atlas.get("contract_scope") or {}).get("consumed_example_ids") or [])

    inventory_paths = iter_inventory_paths()
    inventory_metrics: dict[str, dict[str, int]] = {}
    seen_unique_rows: dict[str, dict[str, Any]] = {}
    reason_counts = Counter()
    repo_counts = Counter()
    selected_test_repo_counts = Counter()
    fresh_candidates: list[dict[str, Any]] = []

    for path in inventory_paths:
        rows = load_jsonl(path)
        inv_key = rel(path)
        metrics = Counter()
        for row in rows:
            rid = row_id(row)
            rid = rid or f"{inv_key}::line_like::{metrics['rows_seen']}"
            rrepo = repo_id(row)
            wpaths = web_paths(row)
            if not wpaths:
                continue
            metrics["web_rows_seen"] += 1
            tests = selected_tests(row)
            pure_web = is_pure_web(row)
            reasons: list[str] = []
            if rid in consumed_example_ids:
                reasons.append("consumed_example_id")
            if rrepo in consumed_repo_families:
                reasons.append("consumed_repo_family")

            record = {
                "row_id": rid,
                "repo_id": rrepo,
                "inventory": inv_key,
                "pure_web": pure_web,
                "web_paths": wpaths,
                "change_paths": change_paths(row),
                "selected_tests": tests,
                "selected_tests_count": len(tests),
                "candidate_paths_count": len(candidate_paths(row)),
                "context_roles": context_roles(row),
                "test_selection_route": row.get("test_selection_route"),
                "status": "fresh_candidate" if not reasons else "rejected",
                "reasons": reasons,
            }

            unique_key = rid
            previous = seen_unique_rows.get(unique_key)
            if previous is None or record["selected_tests_count"] > previous["selected_tests_count"]:
                seen_unique_rows[unique_key] = record

            if reasons:
                metrics["rejected_rows"] += 1
                for reason in reasons:
                    reason_counts[reason] += 1
                continue

            metrics["fresh_rows"] += 1
            if pure_web:
                metrics["fresh_pure_web_rows"] += 1
            if tests:
                metrics["fresh_selected_test_rows"] += 1
            if pure_web and tests:
                metrics["fresh_pure_web_selected_test_rows"] += 1
            fresh_candidates.append(record)
        inventory_metrics[inv_key] = dict(sorted(metrics.items()))

    deduped_fresh: list[dict[str, Any]] = []
    for record in seen_unique_rows.values():
        if record["status"] != "fresh_candidate":
            continue
        deduped_fresh.append(record)
        repo_counts[record["repo_id"]] += 1
        if record["selected_tests_count"] > 0:
            selected_test_repo_counts[record["repo_id"]] += 1
    deduped_fresh.sort(
        key=lambda row: (
            -int(bool(row["pure_web"])),
            -int(row["selected_tests_count"]),
            -int(row["candidate_paths_count"]),
            row["repo_id"],
            row["row_id"],
        )
    )

    pure_web_selected = [row for row in deduped_fresh if row["pure_web"] and row["selected_tests_count"] > 0]
    mixed_web_selected = [row for row in deduped_fresh if (not row["pure_web"]) and row["selected_tests_count"] > 0]

    decision = (
        "No fresh pure-web verifier-anchored source family was found in the scanned refinery inventories."
        if not pure_web_selected
        else "Fresh pure-web verifier-anchored source rows were found and should be materialized before further multilingual evidence-policy promotion."
    )
    next_best_step = (
        "Materialize the highest-quality fresh pure-web selected-test rows into reviewed maintainer bundles and use them as the missing web control family."
        if pure_web_selected
        else "Acquire or ingest a new pure-web repo family with selected tests; until then, keep web evidence-policy promotion blocked and treat existing web rows as control/stress only."
    )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "source_artifacts": {
            "prior_fresh_web_atlas": rel(PRIOR_ATLAS),
            "pure_web_gap_audit": rel(WEB_GAP),
            "pure_web_recovery_audit": rel(WEB_RECOVERY),
            "scanned_inventories": [rel(path) for path in inventory_paths],
        },
        "contract_scope": {
            "consumed_repo_families": sorted(consumed_repo_families),
            "consumed_example_ids_count": len(consumed_example_ids),
            "prior_web_headline_ready": (web_gap.get("verdict") or {}).get("web_source_heldout_headline_ready"),
            "pure_web_recovery_status": (web_recovery.get("headline") or {}).get("recovery_status"),
        },
        "metrics": {
            "inventory_count": len(inventory_paths),
            "unique_fresh_web_rows": len(deduped_fresh),
            "unique_fresh_pure_web_rows": len([row for row in deduped_fresh if row["pure_web"]]),
            "unique_fresh_selected_test_rows": len([row for row in deduped_fresh if row["selected_tests_count"] > 0]),
            "unique_fresh_pure_web_selected_test_rows": len(pure_web_selected),
            "unique_fresh_mixed_web_selected_test_rows": len(mixed_web_selected),
            "rejection_reason_counts": dict(sorted(reason_counts.items())),
            "fresh_repo_counts": dict(sorted(repo_counts.items())),
            "selected_test_repo_counts": dict(sorted(selected_test_repo_counts.items())),
        },
        "inventory_metrics": inventory_metrics,
        "top_fresh_pure_web_selected_test_rows": pure_web_selected[:20],
        "top_fresh_mixed_web_selected_test_rows": mixed_web_selected[:20],
        "top_other_fresh_web_rows": [
            row for row in deduped_fresh
            if row not in pure_web_selected and row not in mixed_web_selected
        ][:20],
        "findings": [
            "The prior narrow atlas only scanned one default inventory; this broader pass checks the current source-episode and packable-example inventories directly.",
            "The scan preserves the same honesty boundary as Stage10262 by rejecting consumed example IDs and consumed repo families.",
            (
                "A fresh pure-web selected-test pool exists in current inventories."
                if pure_web_selected
                else "No fresh pure-web selected-test rows were found in the scanned inventories, which confirms the current web blocker is genuine source supply rather than a missed index entry."
            ),
            (
                "Fresh mixed-language web rows with selected tests are still available, but they should remain support/stress only until a pure-web control family exists."
                if mixed_web_selected
                else "Even mixed-language selected-test web supply is scarce in the current scanned inventories."
            ),
        ],
        "decision": decision,
        "next_best_step": next_best_step,
    }
    return payload


def main() -> None:
    payload = build()
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
