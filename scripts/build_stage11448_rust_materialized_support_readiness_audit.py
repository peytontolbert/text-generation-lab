#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11448
NAME = "stage11448_rust_materialized_support_readiness_audit"
OUT = ART / NAME
SUMMARY = OUT / "rust_materialized_support_readiness_audit.json"
OUT_ROOTS = OUT / "rust_materialized_support_root_audit.jsonl"
OUT_ROWS = OUT / "rust_materialized_support_row_audit.jsonl"

SOURCE_FILES = [
    ART / "stage11407_partial_candle_rust_train_support_rows/partial_candle_rust_train_support_rows.jsonl",
    ART / "stage11410_rust_verifier_log_backed_partial_support/rust_verifier_log_backed_partial_support_rows.jsonl",
    ART / "stage11413_non_candle_rust_verifier_log_backed_support/non_candle_rust_verifier_log_backed_support_rows.jsonl",
    ART / "stage11417_third_family_rust_verifier_log_backed_support/third_family_rust_verifier_log_backed_support_rows.jsonl",
    ART / "stage11420_perftree_rust_build_verifier_backed_support/perftree_rust_build_verifier_backed_support_rows.jsonl",
    ART / "stage11428_codex_rs_selected_test_support_rows/codex_rs_selected_test_support_rows.jsonl",
    ART / "stage11429_selected_test_rust_support_package/added_selected_test_rust_support_rows.jsonl",
]

RESERVED_REPO_FAMILIES = {"prusti-dev", "rust", "rust-analyzer"}
KNOWN_WEAK_REPO_FAMILIES = {"tokenizers"}
RUST_MARKERS = (".rs", "Cargo.toml", "Cargo.lock", "/cargo.toml", "/cargo.lock")
SELECTED_TEST_ROLES = {
    "DECISIVE_SELECTED_TEST_CONSTRAINT",
    "selected_test_source",
    "selected_test_constraint",
}
BUILD_VERIFIER_ROLES = {
    "DECISIVE_BUILD_VERIFIER_CONSTRAINT",
    "cargo_manifest_build_verifier_constraint",
    "build_verifier_constraint",
}
VERIFIER_LOG_ROLES = {
    "OBSERVED_VERIFIER_LOG",
    "OBSERVED_VERIFIER_PASS_LOG",
    "actual_verifier_log",
    "actual_verifier_pass_log",
}
CANDIDATE_ROLES = {
    "SUPPORTING_CANDIDATE_CHANGE_SURFACE",
    "candidate_change_surface",
}


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


def text(value: Any) -> str:
    return "" if value is None else str(value)


def collect_strings(value: Any, out: list[str]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for inner in value.values():
            collect_strings(inner, out)
    elif isinstance(value, list):
        for inner in value:
            collect_strings(inner, out)


def row_text(row: dict[str, Any]) -> str:
    values: list[str] = []
    for key in (
        "input_text",
        "prompt_text",
        "source_path",
        "source_chunk_path",
        "verifier_log_path",
        "test_path",
        "candidate_evidence_text",
        "standalone_projection_source",
    ):
        collect_strings(row.get(key), values)
    return "\n".join(values)


def language(row: dict[str, Any]) -> str:
    return text(row.get("language_family") or row.get("language") or row.get("lang") or "unknown")


def repo_family(row: dict[str, Any]) -> str:
    return text(row.get("repo_family") or row.get("repo_id") or row.get("repo") or "unknown")


def root_key(row: dict[str, Any]) -> str:
    return text(row.get("root_lineage_key") or row.get("root_id") or row.get("source_row_id") or row.get("row_id") or "unknown")


def semantic_value(row: dict[str, Any]) -> str:
    source = row.get("standalone_projection_source") or {}
    return text(row.get("semantic_target_value") or source.get("gold_value") or row.get("target_value") or row.get("decoder_text") or "unknown")


def evidence_kind(row: dict[str, Any]) -> str:
    source = row.get("standalone_projection_source") or {}
    return text(source.get("candidate_evidence_kind") or source.get("source_chunk_role") or row.get("source_chunk_role") or semantic_value(row))


def has_rust_material(row: dict[str, Any]) -> bool:
    lower = row_text(row).lower()
    return any(marker.lower() in lower for marker in RUST_MARKERS)


def anti_cheat_clean(row: dict[str, Any]) -> bool:
    anti = row.get("anti_cheat") or {}
    if not isinstance(anti, dict):
        return False
    required = [
        "target_label_not_visible_before_options",
        "role_alias_not_visible_before_options",
        "root_split_isolation_required",
        "source_text_materialized",
        "deterministic_option_shuffle",
    ]
    return all(anti.get(key) is True for key in required)


def has_selected_test(row: dict[str, Any]) -> bool:
    anti = row.get("anti_cheat") or {}
    lower = row_text(row).lower()
    return (
        row.get("selected_test_anchor_present") is True
        or anti.get("selected_test_anchor_present") is True
        or "selected-test anchor: present" in lower
        or "selected_test" in lower
    )


def has_build_verifier(row: dict[str, Any]) -> bool:
    anti = row.get("anti_cheat") or {}
    lower = row_text(row).lower()
    return (
        row.get("build_verifier_only") is True
        or anti.get("build_verifier_anchor_present") is True
        or "build-verifier" in lower
        or "cargo test --manifest-path" in lower
    )


def has_verifier_log(row: dict[str, Any]) -> bool:
    anti = row.get("anti_cheat") or {}
    lower = row_text(row).lower()
    return (
        anti.get("actual_verifier_log_attached") is True
        or "verifier log" in lower
        or "verifier status:" in lower
        or "test result:" in lower
    )


def train_support(row: dict[str, Any]) -> bool:
    split = text(row.get("split") or row.get("package_split") or "").lower()
    return row.get("train_support_only") is True or split == "train" or "support" in split


def role_flags(rows: list[dict[str, Any]]) -> dict[str, bool]:
    values = {semantic_value(row) for row in rows} | {evidence_kind(row) for row in rows}
    return {
        "has_candidate_change_surface": bool(values & CANDIDATE_ROLES),
        "has_selected_test_constraint": bool(values & SELECTED_TEST_ROLES),
        "has_build_verifier_constraint": bool(values & BUILD_VERIFIER_ROLES),
        "has_verifier_log": bool(values & VERIFIER_LOG_ROLES),
    }


def row_record(row: dict[str, Any], source_path: Path) -> dict[str, Any]:
    return {
        "source_artifact": rel(source_path),
        "row_id": text(row.get("row_id")),
        "root_lineage_key": root_key(row),
        "repo_family": repo_family(row),
        "semantic_target_value": semantic_value(row),
        "evidence_kind": evidence_kind(row),
        "task_type": text(row.get("task_type") or row.get("perspective") or "unknown"),
        "train_support": train_support(row),
        "has_rust_material": has_rust_material(row),
        "has_selected_test_anchor": has_selected_test(row),
        "has_build_verifier_anchor": has_build_verifier(row),
        "has_verifier_log": has_verifier_log(row),
        "anti_cheat_clean": anti_cheat_clean(row),
    }


def root_record(repo: str, root: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    flags = role_flags(rows)
    row_reasons = []
    if repo in RESERVED_REPO_FAMILIES:
        row_reasons.append("reserved_repo_family")
    if repo in KNOWN_WEAK_REPO_FAMILIES:
        row_reasons.append("known_weak_or_quarantined_repo_family")
    if not all(row["train_support"] for row in rows):
        row_reasons.append("non_train_support_row_present")
    if not all(row["has_rust_material"] for row in rows):
        row_reasons.append("missing_rust_source_or_cargo_material")
    if not any(row["has_selected_test_anchor"] or row["has_build_verifier_anchor"] for row in rows):
        row_reasons.append("missing_selected_test_or_build_verifier_anchor")
    if not any(row["has_verifier_log"] for row in rows):
        row_reasons.append("missing_actual_verifier_log")
    if not all(row["anti_cheat_clean"] for row in rows):
        row_reasons.append("anti_cheat_contract_incomplete")
    if not flags["has_candidate_change_surface"]:
        row_reasons.append("missing_candidate_change_surface_role")
    if not (flags["has_selected_test_constraint"] or flags["has_build_verifier_constraint"]):
        row_reasons.append("missing_verifier_constraint_role")
    if not flags["has_verifier_log"]:
        row_reasons.append("missing_verifier_log_role")

    selected_test_ready = not row_reasons and flags["has_selected_test_constraint"]
    build_verifier_only_ready = not row_reasons and flags["has_build_verifier_constraint"] and not flags["has_selected_test_constraint"]
    if selected_test_ready:
        lane = "selected_test_verifier_grounded_train_support"
    elif build_verifier_only_ready:
        lane = "build_verifier_only_diagnostic_support"
    else:
        lane = "blocked_or_diagnostic"

    return {
        "repo_family": repo,
        "root_lineage_key": root,
        "rows": len(rows),
        "semantic_target_values": sorted({row["semantic_target_value"] for row in rows}),
        "evidence_kinds": sorted({row["evidence_kind"] for row in rows}),
        "role_flags": flags,
        "lane": lane,
        "admitted_for_train_support": selected_test_ready,
        "diagnostic_build_verifier_only": build_verifier_only_ready,
        "blockers": row_reasons,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    row_audit: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}

    for path in SOURCE_FILES:
        rows = [row for row in read_jsonl(path) if language(row) == "rust"]
        source_counts[rel(path)] = len(rows)
        for row in rows:
            row_audit.append(row_record(row, path))

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in row_audit:
        grouped[(row["repo_family"], row["root_lineage_key"])].append(row)
    root_audit = [root_record(repo, root, rows) for (repo, root), rows in sorted(grouped.items())]

    admitted = [row for row in root_audit if row["admitted_for_train_support"]]
    diagnostic = [row for row in root_audit if row["diagnostic_build_verifier_only"]]
    blockers = Counter(reason for row in root_audit for reason in row["blockers"])
    lane_counts = Counter(row["lane"] for row in root_audit)
    admitted_repos = {row["repo_family"] for row in admitted}
    admitted_roles = Counter(value for row in admitted for value in row["semantic_target_values"])
    minimum_roots = 10
    ready_for_package = len(admitted) >= minimum_roots and len(admitted_repos) >= 3

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "rust_materialized_support_not_ready_for_training_package"
        if not ready_for_package
        else "rust_materialized_support_ready_for_training_package",
        "source_counts": source_counts,
        "counts": {
            "rows_examined": len(row_audit),
            "unique_roots_examined": len(root_audit),
            "admitted_selected_test_train_roots": len(admitted),
            "diagnostic_build_verifier_only_roots": len(diagnostic),
            "admitted_repo_families": len(admitted_repos),
            "minimum_train_roots_required": minimum_roots,
        },
        "lane_counts": dict(sorted(lane_counts.items())),
        "blocker_counts": dict(sorted(blockers.items())),
        "admitted_by_repo_family": dict(sorted(Counter(row["repo_family"] for row in admitted).items())),
        "diagnostic_by_repo_family": dict(sorted(Counter(row["repo_family"] for row in diagnostic).items())),
        "admitted_by_semantic_target_value": dict(sorted(admitted_roles.items())),
        "quality_gate": {
            "minimum_selected_test_roots_met": len(admitted) >= minimum_roots,
            "minimum_repo_breadth_met": len(admitted_repos) >= 3,
            "ready_for_training_package": ready_for_package,
        },
        "policy": {
            "do_not_train_now": not ready_for_package,
            "build_verifier_only_rows_are_diagnostic": True,
            "selected_test_or_equivalent_verifier_transition_required_for_promotable_rust_support": True,
        },
        "recommended_next_action": (
            "Do not run a Rust support probe unless admitted_selected_test_train_roots reaches at least 10 across "
            "3+ repo families. Build-verifier-only roots can remain diagnostic support, but they should not be used "
            "as the primary Rust verifier/evidence capability expansion."
        ),
        "outputs": {
            "summary": rel(SUMMARY),
            "root_audit": rel(OUT_ROOTS),
            "row_audit": rel(OUT_ROWS),
        },
    }

    write_jsonl(OUT_ROWS, row_audit)
    write_jsonl(OUT_ROOTS, root_audit)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["quality_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
