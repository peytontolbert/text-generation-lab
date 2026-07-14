#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import build_stage11269_source_specific_evidence_item_materialization as s11269

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11274
NAME = "stage11274_partial_source_specific_evidence_item_materialization"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "partial_source_specific_evidence_item_materialization.json"
TRAIN_JSONL = OUT_DIR / "partial_source_specific_evidence_item_train_rows.jsonl"
VALIDATION_JSONL = OUT_DIR / "partial_source_specific_evidence_item_validation_rows.jsonl"
STRICT_JSONL = OUT_DIR / "partial_source_specific_evidence_item_strict_rows.jsonl"
BLOCKED_JSONL = OUT_DIR / "partial_source_specific_evidence_item_blocked_roots.jsonl"
ROOT_SPLITS_JSONL = OUT_DIR / "partial_source_specific_evidence_item_root_splits.jsonl"

ROLE_TARGETS = [
    ("verifier", "DECISIVE_VERIFIER_TEST_CONSTRAINT"),
    ("changed", "SUPPORTING_CANDIDATE_CHANGE_SURFACE"),
    ("symptom", "SUPPORTING_SYMPTOM_OR_CALL_PATH"),
    ("distractor", "DISTRACTOR_BACKGROUND_CONTEXT"),
]


def choose_partial_support(
    item: dict[str, Any],
    retrieval: dict[str, Any],
    chunks: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    candidates: dict[str, list[dict[str, Any]]] = {
        "verifier": [],
        "changed": [],
        "symptom": [],
        "distractor": [],
    }
    changed_paths = [s11269.norm_path(x) for x in item.get("candidate_change_surface_paths") or []]
    verifier_paths = [s11269.norm_path(x) for x in item.get("verifier_and_test_constraint_paths") or []]
    symptom_paths = [s11269.norm_path(x) for x in item.get("symptom_or_call_path_analogue_paths") or []]

    for score in retrieval.get("support_scores") or []:
        cid = str(score.get("chunk_id") or "")
        chunk = chunks.get(cid)
        if not chunk:
            continue
        if str(score.get("source_type") or chunk.get("source_type") or "") != "local_repo":
            continue
        path = s11269.norm_path(score.get("path") or chunk.get("path") or "")
        enriched = {**score, "text": chunk.get("text") or "", "doc_id": chunk.get("doc_id") or path, "path": path}
        role = str(score.get("role") or "")
        if any(s11269.path_matches(p, path) for p in verifier_paths) or role == "verification_constraint":
            candidates["verifier"].append(enriched)
        if any(s11269.path_matches(p, path) for p in changed_paths) or role == "seed_change":
            candidates["changed"].append(enriched)
        if any(s11269.path_matches(p, path) for p in symptom_paths) or role == "trace_analogue":
            candidates["symptom"].append(enriched)
        if role in {"algorithm_grounding", "cross_repo_analogue", "repo_graph_neighbor", "test_neighbor"}:
            candidates["distractor"].append(enriched)

    selected: dict[str, dict[str, Any]] = {}
    used: set[str] = set()
    for key in ["verifier", "changed", "symptom", "distractor"]:
        ordered = sorted(
            candidates[key],
            key=lambda score: (-float(score.get("score") or 0), str(score.get("chunk_id") or "")),
        )
        for score in ordered:
            cid = str(score.get("chunk_id") or "")
            if cid not in used and s11269.excerpt(score.get("text") or ""):
                selected[key] = score
                used.add(cid)
                break
    return selected


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def build_partial_rows_for_root(
    item: dict[str, Any],
    split: str,
    retrieval_by_id: dict[str, dict[str, Any]],
    chunks: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    blockers: list[str] = []
    if item.get("language_family") not in {"python", "rust", "c_cpp", "web_js_ts_html"}:
        blockers.append("unsupported_language")
    if not item.get("candidate_change_surface_paths"):
        blockers.append("missing_candidate_paths")
    if not item.get("verifier_and_test_constraint_paths"):
        blockers.append("missing_verifier_paths")
    if set(item.get("candidate_change_surface_paths") or []) & set(item.get("verifier_and_test_constraint_paths") or []):
        blockers.append("candidate_verifier_path_overlap")
    retrieval = retrieval_by_id.get(str(item.get("source_row_id") or ""))
    if not retrieval:
        blockers.append("missing_retrieval_source_row")
    if blockers:
        return [], [{"root_id": item.get("root_id"), "source_row_id": item.get("source_row_id"), "language_family": item.get("language_family"), "blockers": sorted(set(blockers))}]

    selected = choose_partial_support(item, retrieval, chunks)
    available = [(kind, target) for kind, target in ROLE_TARGETS if kind in selected]
    if len(available) < 2:
        return [], [{"root_id": item.get("root_id"), "source_row_id": item.get("source_row_id"), "language_family": item.get("language_family"), "blockers": ["fewer_than_two_distinct_source_backed_roles"]}]

    rows: list[dict[str, Any]] = []
    for kind, target in available:
        text = s11269.candidate_text(kind, selected[kind])
        seed = f"{item.get('root_id')}::{kind}::{target}::partial"
        options = s11269.deterministic_options(seed)
        target_label = next(opt["label"] for opt in options if opt["value"] == target)
        prompt = s11269.prompt_for(item, text, options)
        row_id = f"stage11274::{item.get('source_root_id')}::partial_source_specific_evidence_candidate_judgment::{kind}"
        rows.append({
            "row_id": row_id,
            "root_id": item.get("root_id"),
            "source_root_id": item.get("source_root_id"),
            "root_lineage_key": item.get("root_lineage_key"),
            "source_row_id": item.get("source_row_id"),
            "source_family_id": item.get("source_family_id"),
            "repo_family": item.get("repo_family"),
            "repo_id": item.get("repo_id"),
            "language_family": item.get("language_family"),
            "task_type": "evidence_candidate_judgment",
            "surface": "maintainer_partial_source_specific_evidence_candidate_judgment_bounded_choice",
            "split": split,
            "package_split": split,
            "input_text": prompt,
            "prompt_text": prompt,
            "decoder_text": target_label,
            "target_text": target_label,
            "bounded_choice_target_label": target_label,
            "semantic_target_value": target,
            "opaque_options": options,
            "expected_enabled_loss": "decoder_ce",
            "loss_mask": {"decoder_ce": True},
            "strict_eval_eligible": split == "strict_eval",
            "train_support_only": split == "train",
            "anti_cheat": {
                "deterministic_option_shuffle": True,
                "root_split_isolation_required": True,
                "single_candidate_item_judgment": True,
                "target_label_not_visible_before_options": True,
                "role_alias_not_visible_before_options": True,
                "source_text_materialized": True,
                "partial_role_root_allowed": True,
            },
            "standalone_projection_source": {
                "gold_label": target_label,
                "gold_value": target,
                "opaque_options": options,
                "candidate_evidence_kind": kind,
                "candidate_evidence_text": text,
                "source_chunk_id": selected[kind].get("chunk_id"),
                "source_chunk_path": selected[kind].get("path"),
                "source_chunk_role": selected[kind].get("role"),
                "source_chunk_support_reasons": selected[kind].get("support_reasons") or [],
                "candidate_change_surface_paths": item.get("candidate_change_surface_paths") or [],
                "verifier_and_test_constraint_paths": item.get("verifier_and_test_constraint_paths") or [],
                "symptom_or_call_path_analogue_paths": item.get("symptom_or_call_path_analogue_paths") or [],
                "key_symbols": item.get("key_symbols") or [],
                "source_row_id": item.get("source_row_id"),
                "source_inventory_stage": "stage11237",
                "objective": "partial_source_specific_candidate_evidence_judgment",
            },
        })
    return rows, []


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    duplicate_ids = len(rows) - len({row["row_id"] for row in rows})
    label_leaks = 0
    role_alias_leaks = 0
    internal_reason_leaks = 0
    for row in rows:
        before_options = str(row.get("prompt_text") or "").split("Options:", 1)[0]
        label = str(row.get("bounded_choice_target_label") or "")
        lowered = before_options.lower()
        if f"target label: {label.lower()}" in lowered or f"answer: {label.lower()}" in lowered:
            label_leaks += 1
        for token in s11269.ROLE_ALIAS_TOKENS:
            if token in before_options:
                role_alias_leaks += 1
                break
        if "Evidence note: grounded_" in before_options or ("Evidence note: " in before_options and "_path_match" in before_options):
            internal_reason_leaks += 1
    roots_by_split: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        roots_by_split[str(row.get("split"))].add(str(row.get("root_id")))
    overlaps = {
        "train_validation": sorted(roots_by_split["train"] & roots_by_split["validation"]),
        "train_strict": sorted(roots_by_split["train"] & roots_by_split["strict_eval"]),
        "validation_strict": sorted(roots_by_split["validation"] & roots_by_split["strict_eval"]),
    }
    return {
        "duplicate_row_ids": duplicate_ids,
        "target_label_leak_rows": label_leaks,
        "role_alias_leak_rows": role_alias_leaks,
        "internal_support_reason_leak_rows": internal_reason_leaks,
        "root_overlap": overlaps,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_candidates = [row for row in s11269.load_jsonl(s11269.SOURCE_CANDIDATES) if row.get("admission_ready")]
    retrieval_by_id = s11269.index_retrieval_rows()
    chunks = s11269.index_chunk_text()
    root_splits = s11269.split_roots(source_candidates)

    rows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []
    for item in source_candidates:
        split = root_splits.get(str(item.get("root_id")), "train")
        split_rows.append({
            "root_id": item.get("root_id"),
            "source_row_id": item.get("source_row_id"),
            "root_lineage_key": item.get("root_lineage_key"),
            "language_family": item.get("language_family"),
            "repo_family": item.get("repo_family"),
            "split": split,
        })
        built, block = build_partial_rows_for_root(item, split, retrieval_by_id, chunks)
        rows.extend(built)
        blocked.extend(block)

    by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_split[str(row.get("split"))].append(row)
    train = by_split["train"]
    validation = by_split["validation"]
    strict = by_split["strict_eval"]

    write_jsonl(TRAIN_JSONL, train)
    write_jsonl(VALIDATION_JSONL, validation)
    write_jsonl(STRICT_JSONL, strict)
    write_jsonl(BLOCKED_JSONL, blocked)
    write_jsonl(ROOT_SPLITS_JSONL, split_rows)

    audit = audit_rows(rows)
    counts = {
        "source_ready_candidates": len(source_candidates),
        "materialized_roots": len({row["root_id"] for row in rows}),
        "blocked_roots": len(blocked),
        "train_rows": len(train),
        "validation_rows": len(validation),
        "strict_rows": len(strict),
        "by_split_language": {
            split: dict(Counter(str(row.get("language_family")) for row in split_rows_))
            for split, split_rows_ in [("train", train), ("validation", validation), ("strict_eval", strict)]
        },
        "by_split_target": {
            split: dict(Counter(str(row.get("semantic_target_value")) for row in split_rows_))
            for split, split_rows_ in [("train", train), ("validation", validation), ("strict_eval", strict)]
        },
        "by_split_candidate_kind": {
            split: dict(Counter(str((row.get("standalone_projection_source") or {}).get("candidate_evidence_kind")) for row in split_rows_))
            for split, split_rows_ in [("train", train), ("validation", validation), ("strict_eval", strict)]
        },
        "source_chunks_indexed": len(chunks),
        "retrieval_rows_indexed": len(retrieval_by_id),
        "c_cpp_gap": {
            "ready_c_cpp_roots": sum(1 for row in source_candidates if row.get("language_family") == "c_cpp"),
            "reason": "stage11237 found no clean C/C++ verifier-constraint source candidates under current filters",
        },
    }
    passed = bool(rows) and not audit["duplicate_row_ids"] and not audit["target_label_leak_rows"] and not audit["role_alias_leak_rows"] and not audit["internal_support_reason_leak_rows"] and not any(audit["root_overlap"].values())
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": passed,
        "decision": "partial_source_specific_evidence_item_materialization_ready" if passed else "partial_source_specific_evidence_item_materialization_blocked",
        "counts": counts,
        "audit": audit,
        "quality_gates": {
            "uses_materialized_chunk_text": all((row.get("anti_cheat") or {}).get("source_text_materialized") for row in rows),
            "root_split_disjoint": not any(audit["root_overlap"].values()),
            "unique_row_ids": audit["duplicate_row_ids"] == 0,
            "target_label_not_visible_before_options": audit["target_label_leak_rows"] == 0,
            "role_alias_not_visible_before_options": audit["role_alias_leak_rows"] == 0,
            "internal_support_reasons_not_visible": audit["internal_support_reason_leak_rows"] == 0,
            "has_validation_and_strict": bool(validation and strict),
        },
        "interpretation": {
            "why_this_differs_from_stage11269": "Rows are admitted for every available distinct source-backed evidence role; roots no longer need all four roles. This avoids fabricating sparse distractor evidence and admits Web/Rust source-backed rows.",
            "claim_limit": "Still diagnostic: C/C++ source supply remains absent and Rust/Web supply is small.",
        },
        "outputs": {
            "train_jsonl": rel(TRAIN_JSONL),
            "validation_jsonl": rel(VALIDATION_JSONL),
            "strict_jsonl": rel(STRICT_JSONL),
            "blocked_jsonl": rel(BLOCKED_JSONL),
            "root_splits_jsonl": rel(ROOT_SPLITS_JSONL),
            "summary_json": rel(SUMMARY_JSON),
        },
        "source_artifacts": {
            "stage11237_candidates": rel(s11269.SOURCE_CANDIDATES),
            "retrieval_rows": rel(s11269.RETRIEVAL_ROWS),
            "full_context_rows": rel(s11269.FULL_CONTEXT_ROWS),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
