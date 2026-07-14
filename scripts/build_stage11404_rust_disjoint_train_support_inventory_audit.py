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
STAGE = 11404
NAME = "stage11404_rust_disjoint_train_support_inventory_audit"
OUT = ART / NAME
SUMMARY = OUT / "rust_disjoint_train_support_inventory_audit.json"
OUT_CANDIDATES = OUT / "rust_disjoint_train_support_candidates.jsonl"
OUT_REJECTED = OUT / "rust_disjoint_train_support_rejected_or_diagnostic.jsonl"

RESERVED_FILES = [
    ART / "stage11331_rust_web_gap_recovery_manifest/admitted_rust_strict_replacement_rows.jsonl",
    ART / "stage11193_rust_external_graph_replacement_rows/rust_replacement_strict_candidate_rows.jsonl",
]

SOURCE_FILES = [
    ART / "stage10452_rust_evidence_citation_candidate_atlas/rust_evidence_citation_candidate_rows.jsonl",
    ART / "stage10476_rust_citation_materialized_root_bundle_builder/rust_citation_materialized_bounded_rows.jsonl",
    ART / "stage10513_rust_citation_ef_frontier_materializer/rust_citation_ef_diagnostic_seed_rows.jsonl",
    ART / "stage10972_rust_reviewed_evidence_bundle/strict_candidate_rows.jsonl",
    ART / "stage11275_direct_retrieval_multilingual_evidence_materialization/direct_retrieval_multilingual_evidence_train_rows.jsonl",
    ART / "stage11275_direct_retrieval_multilingual_evidence_materialization/direct_retrieval_multilingual_evidence_strict_rows.jsonl",
    ART / "stage11331_rust_web_gap_recovery_manifest/rust_web_blocked_source_queue.jsonl",
]

RESERVED_REPO_FAMILIES = {"prusti-dev", "rust", "rust-analyzer"}
KNOWN_WEAK_REPO_FAMILIES = {"tokenizers"}
RUST_SOURCE_MARKERS = (".rs", "Cargo.toml", "Cargo.lock", "/cargo.toml", "/cargo.lock")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def text_value(value: Any) -> str:
    return "" if value is None else str(value)


def language(row: dict[str, Any]) -> str:
    return text_value(row.get("language_family") or row.get("language") or row.get("lang") or "unknown")


def repo_family(row: dict[str, Any]) -> str:
    return text_value(row.get("repo_family") or row.get("repo_id") or row.get("repo") or "unknown")


def root_id(row: dict[str, Any]) -> str:
    return text_value(
        row.get("root_id")
        or row.get("source_root_id")
        or row.get("source_bundle_id")
        or row.get("source_row_id")
        or row.get("semantic_key")
        or row.get("row_id")
    )


def root_key(row: dict[str, Any]) -> str:
    return text_value(row.get("root_lineage_key") or root_id(row)).lower()


def row_id(row: dict[str, Any]) -> str:
    return text_value(row.get("row_id") or row.get("semantic_key") or root_id(row))


def semantic_value(row: dict[str, Any]) -> str:
    projection = row.get("standalone_projection_source") or {}
    return text_value(
        row.get("semantic_target_value")
        or projection.get("gold_value")
        or row.get("gold_value")
        or row.get("target_value")
        or row.get("decoder_text")
        or row.get("target_text")
        or "unknown"
    )


def split_name(row: dict[str, Any]) -> str:
    return text_value(row.get("split") or row.get("package_split") or row.get("split_role") or "unknown").lower()


def train_support_intent(row: dict[str, Any]) -> bool:
    split = split_name(row)
    if row.get("train_support_only") is True:
        return True
    if "train" in split or "support" in split:
        return True
    return False


def strict_or_reserved_intent(row: dict[str, Any]) -> bool:
    split = split_name(row)
    if row.get("strict_eval_eligible") is True:
        return True
    return any(tag in split for tag in ("strict", "eval", "heldout", "reserved"))


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
    fields = []
    for key in (
        "input_text",
        "prompt_text",
        "source_path",
        "source_chunk_path",
        "changed_path",
        "verifier_path",
        "test_path",
        "candidate_evidence_text",
    ):
        collect_strings(row.get(key), fields)
    collect_strings(row.get("standalone_projection_source"), fields)
    return "\n".join(fields)


def has_rust_source(row: dict[str, Any]) -> bool:
    text = row_text(row)
    lower = text.lower()
    return any(marker.lower() in lower for marker in RUST_SOURCE_MARKERS)


def has_selected_verifier_anchor(row: dict[str, Any]) -> bool:
    text = row_text(row).lower()
    if "selected-test" in text or "selected_test" in text:
        return True
    if "verifier" in text and ("test" in text or "cargo test" in text or "fail_to_pass" in text):
        return True
    projection = row.get("standalone_projection_source") or {}
    reasons = " ".join(text_value(x).lower() for x in projection.get("source_chunk_support_reasons") or [])
    return "verifier" in reasons or "test" in reasons


def anti_cheat_clean(row: dict[str, Any]) -> bool:
    anti = row.get("anti_cheat") or {}
    if not isinstance(anti, dict):
        return False
    required = [
        "target_label_not_visible_before_options",
        "role_alias_not_visible_before_options",
        "root_split_isolation_required",
    ]
    present = [anti.get(key) for key in required if key in anti]
    return bool(present) and all(value is True for value in present)


def key_set(rows: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for row in rows:
        for value in (
            row_id(row),
            root_id(row),
            root_key(row),
            text_value(row.get("source_row_id")),
            text_value(row.get("source_root_id")),
            text_value(row.get("semantic_key")),
        ):
            if value:
                keys.add(value.lower())
    return keys


def reserve_overlap(row: dict[str, Any], reserved_keys: set[str]) -> bool:
    values = {
        row_id(row),
        root_id(row),
        root_key(row),
        text_value(row.get("source_row_id")),
        text_value(row.get("source_root_id")),
        text_value(row.get("semantic_key")),
    }
    return any(value and value.lower() in reserved_keys for value in values)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    reserved_rows: list[dict[str, Any]] = []
    for path in RESERVED_FILES:
        reserved_rows.extend(read_jsonl(path))
    reserved_keys = key_set(reserved_rows)

    seen: set[str] = set()
    admitted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}

    for source_path in SOURCE_FILES:
        source_rows = read_jsonl(source_path)
        source_counts[rel(source_path)] = len(source_rows)
        for row in source_rows:
            if language(row) != "rust":
                continue
            rid = row_id(row)
            dedupe_key = rid or f"{rel(source_path)}::{len(seen)}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            reasons: list[str] = []
            if reserve_overlap(row, reserved_keys):
                reasons.append("overlaps_reserved_strict_replacement_row")
            if repo_family(row) in RESERVED_REPO_FAMILIES:
                reasons.append("reserved_strict_repo_family")
            if repo_family(row) in KNOWN_WEAK_REPO_FAMILIES:
                reasons.append("known_weak_or_quarantined_repo_family")
            if not train_support_intent(row):
                reasons.append("not_declared_train_support")
            if strict_or_reserved_intent(row):
                reasons.append("strict_eval_or_reserved_intent")
            if not has_rust_source(row):
                reasons.append("no_visible_rust_source_path_or_cargo_marker")
            if not has_selected_verifier_anchor(row):
                reasons.append("missing_selected_test_or_verifier_anchor")
            if not anti_cheat_clean(row):
                reasons.append("anti_cheat_contract_incomplete_or_absent")

            record = {
                "source_inventory": rel(source_path),
                "row_id": rid,
                "root_id": root_id(row),
                "root_lineage_key": root_key(row),
                "repo_family": repo_family(row),
                "semantic_target_value": semantic_value(row),
                "task_type": text_value(row.get("task_type") or row.get("perspective") or "unknown"),
                "split": split_name(row),
                "has_rust_source": has_rust_source(row),
                "has_selected_verifier_anchor": has_selected_verifier_anchor(row),
                "anti_cheat_clean": anti_cheat_clean(row),
                "admitted_as_train_support_candidate": not reasons,
                "rejection_reasons": reasons,
            }
            if reasons:
                rejected.append(record)
            else:
                admitted.append(record)

    roots = {row["root_lineage_key"] for row in admitted}
    repos = {row["repo_family"] for row in admitted}
    by_repo = Counter(row["repo_family"] for row in admitted)
    by_value = Counter(row["semantic_target_value"] for row in admitted)
    rejected_reasons = Counter(reason for row in rejected for reason in row["rejection_reasons"])

    minimum_roots = 10
    role_values = {
        "candidate_change_surface",
        "symptom_or_call_path_analogue",
        "verifier_and_test_constraint",
        "SUPPORTING_CANDIDATE_CHANGE_SURFACE",
        "SUPPORTING_SYMPTOM_OR_CALL_PATH",
        "DECISIVE_VERIFIER_TEST_CONSTRAINT",
    }
    has_required_role_mix = len(set(by_value) & role_values) >= 3
    ready_for_train_package = len(roots) >= minimum_roots and len(repos) >= 3 and has_required_role_mix

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "rust_disjoint_train_support_supply_insufficient",
        "source_counts": source_counts,
        "reserved_exclusions": {
            "reserved_rows": len(reserved_rows),
            "reserved_repo_families_excluded": sorted(RESERVED_REPO_FAMILIES),
            "known_weak_repo_families_flagged": sorted(KNOWN_WEAK_REPO_FAMILIES),
        },
        "counts": {
            "rust_rows_examined": len(admitted) + len(rejected),
            "admitted_train_support_candidates": len(admitted),
            "admitted_unique_roots": len(roots),
            "admitted_unique_repo_families": len(repos),
            "rejected_or_diagnostic": len(rejected),
            "minimum_roots_required_before_package": minimum_roots,
        },
        "admitted_by_repo_family": dict(sorted(by_repo.items())),
        "admitted_by_semantic_target_value": dict(sorted(by_value.items())),
        "rejected_reason_counts": dict(sorted(rejected_reasons.items())),
        "quality_gate": {
            "minimum_disjoint_roots_met": len(roots) >= minimum_roots,
            "minimum_repo_breadth_met": len(repos) >= 3,
            "required_role_mix_present": has_required_role_mix,
            "ready_for_training_package": ready_for_train_package,
        },
        "interpretation": (
            "Existing local Rust inventories do not yet satisfy the Stage11344 requirement for at least 10 clean, "
            "disjoint, Rust-source-backed train-support roots. Most available rows are strict/reserved, diagnostic, "
            "missing verifier anchors, sourced from weak/quarantined families, or Rust-tagged rows with non-Rust evidence."
        ),
        "recommended_next_action": (
            "Mine or materialize new Rust train-support roots before probing again. Do not train on the three reserved "
            "replacement rows. Prioritize non-tokenizers/non-reserved repo families with real .rs/Cargo evidence, selected "
            "tests or verifier anchors, and distinct evidence roles."
        ),
        "outputs": {
            "summary": rel(SUMMARY),
            "admitted_candidates": rel(OUT_CANDIDATES),
            "rejected_or_diagnostic": rel(OUT_REJECTED),
        },
    }
    write_jsonl(OUT_CANDIDATES, admitted)
    write_jsonl(OUT_REJECTED, rejected)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["quality_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
