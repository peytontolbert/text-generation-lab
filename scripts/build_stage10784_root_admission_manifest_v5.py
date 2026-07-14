#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10784
NAME = "stage10784_root_admission_manifest_v5"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST_JSONL = OUT_DIR / "root_admission_manifest_v5.jsonl"
SUMMARY_JSON = OUT_DIR / "root_admission_manifest_v5.json"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

REVIEWED_ROOTS = ROOT / "runs/local/artifacts/stage10743_reviewed_v27_plus_cpp_bootstrap_train_support_package/reviewed_v27_plus_cpp_bootstrap_root_manifest.jsonl"
COMPILED_ROOTS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
BOOTSTRAP_ROWS = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/multitarget_bootstrap_with_heldout_rows.jsonl"
LATEST_REVIEWED_PACKAGE = ROOT / "runs/local/artifacts/stage10778_bulk_reviewed_support_candidate_training_package/bulk_reviewed_support_candidate_training_package.json"
BULK_PACKET_DECISIONS = ROOT / "runs/local/artifacts/stage10775_bulk_multilingual_packet_ai_adjudication/packet_ai_adjudication.jsonl"
BULK_ENRICHED_INDEX = ROOT / "runs/local/artifacts/stage10776_bulk_support_ready_packet_enrichment/enriched_packet_index.jsonl"
BULK_SUPPORT_ROWS = ROOT / "runs/local/artifacts/stage10778_bulk_reviewed_support_candidate_training_package/support_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def root_lineage_key(root: dict[str, Any]) -> str:
    repo_id = str(root.get("repo_id") or "unknown")
    snapshot_id = str(root.get("snapshot_id") or root.get("bundle_id") or root.get("root_id"))
    return f"{repo_id}::{snapshot_id}"


def reviewed_quality(root: dict[str, Any]) -> float:
    score = 0.65
    if root.get("reviewed_bundle_source"):
        score += 0.15
    if root.get("selected_test_anchor"):
        score += 0.08
    if root.get("verifier_anchor"):
        score += 0.08
    if root.get("strict_eval_eligible"):
        score += 0.02
    if root.get("abstention_heavy"):
        score -= 0.10
    if root.get("train_support_only"):
        score -= 0.03
    for note in root.get("claim_notes") or []:
        if note == "pure_web_no_selected_test_anchor":
            score -= 0.08
        elif note == "source_derived_verifier_constraint":
            score -= 0.04
        elif note == "not_admissible_for_same_surface_comparison":
            score -= 0.02
    return round(clamp(score), 4)


def reviewed_admit_role(root: dict[str, Any]) -> str:
    if root.get("stress_overlap_only"):
        return "diagnostic"
    if root.get("strict_eval_eligible"):
        return "strict_eval"
    split_role = str(root.get("split_role") or "")
    if split_role == "validation":
        return "validation"
    if root.get("train_support_only") or split_role == "train_support":
        return "train"
    return "diagnostic"


def aggregate_bootstrap_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        root_id = str(row["root_id"])
        entry = grouped.setdefault(
            root_id,
            {
                "row_count": 0,
                "prompt_target_leak_rows": 0,
                "opaque_option_rows": 0,
                "bounded_decision_rows": 0,
                "selected_test_like_rows": 0,
                "verifier_outcome_rows": 0,
            },
        )
        entry["row_count"] += 1
        anti_cheat = row.get("anti_cheat") or {}
        if anti_cheat.get("prompt_target_leak"):
            entry["prompt_target_leak_rows"] += 1
        if anti_cheat.get("opaque_option_contract"):
            entry["opaque_option_rows"] += 1
        if row.get("target_family") == "bounded_decision":
            entry["bounded_decision_rows"] += 1
        if row.get("target_subtype") in {"selected_test", "candidate_path", "verifier_outcome"}:
            entry["selected_test_like_rows"] += 1
        if row.get("target_subtype") == "verifier_outcome":
            entry["verifier_outcome_rows"] += 1
    return grouped


def bootstrap_quality(root: dict[str, Any], agg: dict[str, Any]) -> float:
    score = 0.35
    verifier_id = str(root.get("verifier_id") or "")
    split_component = str(root.get("split_component") or "")
    if verifier_id == "PASS_TARGETED_TEST_SELECTION":
        score += 0.10
    if verifier_id == "PASS_TRACE_VERIFICATION_TARGETS":
        score += 0.14
    if split_component == "strict_eval_long_context_heldout":
        score += 0.08
    if agg["selected_test_like_rows"] > 0:
        score += 0.07
    if agg["verifier_outcome_rows"] > 0:
        score += 0.06
    if agg["prompt_target_leak_rows"] > 0:
        score -= 0.25
    if agg["opaque_option_rows"] == 0 and agg["bounded_decision_rows"] > 0:
        score -= 0.10
    if split_component in {"reference_bounded_eval", "diagnostic_bounded"}:
        score -= 0.05
    return round(clamp(score), 4)


def bootstrap_admit_role(root: dict[str, Any], agg: dict[str, Any]) -> str:
    split_component = str(root.get("split_component") or "")
    if agg["prompt_target_leak_rows"] > 0:
        if split_component == "strict_eval_long_context_heldout":
            return "diagnostic"
        return "quarantine"
    if split_component in {"reference_bounded_eval", "diagnostic_bounded"}:
        return "diagnostic"
    if split_component == "strict_eval_long_context_heldout":
        return "diagnostic"
    if split_component == "validation_bootstrap_bounded":
        return "validation"
    if split_component.startswith("train_"):
        return "train"
    return "diagnostic"


def aggregate_support_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        root_id = str(row.get("source_row_id") or row.get("root_id") or "")
        if not root_id:
            continue
        entry = grouped.setdefault(
            root_id,
            {
                "root_id": root_id,
                "repo_id": row.get("repo_id"),
                "repo_family": row.get("repo_family"),
                "language_family": row.get("language_family"),
                "source_family_id": root_id.split("::", 1)[0] if "::" in root_id else "unknown",
                "row_count": 0,
                "perspectives": set(),
                "selected_test_anchor": False,
                "verifier_anchor": False,
                "abstention_heavy": False,
                "priority_score_max": 0,
                "enrichment_status": None,
            },
        )
        entry["row_count"] += 1
        entry["perspectives"].add(str(row.get("perspective") or row.get("task_type") or "unknown"))
        entry["selected_test_anchor"] = entry["selected_test_anchor"] or bool(row.get("selected_test_anchor"))
        entry["verifier_anchor"] = entry["verifier_anchor"] or bool(row.get("verifier_anchor"))
        entry["abstention_heavy"] = entry["abstention_heavy"] or bool(row.get("abstention_heavy"))
        support_provenance = row.get("support_provenance") or {}
        entry["priority_score_max"] = max(entry["priority_score_max"], int(support_provenance.get("priority_score") or 0))
        entry["enrichment_status"] = support_provenance.get("enrichment_status") or entry["enrichment_status"]
    for entry in grouped.values():
        entry["perspectives"] = sorted(entry["perspectives"])
    return grouped


def aggregate_packet_status(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        root_id = str(row.get("root_id") or "")
        if not root_id:
            continue
        grouped[root_id] = {
            "root_id": root_id,
            "repo_family": row.get("repo_family"),
            "language_family": row.get("language_family"),
            "ai_status": row.get("ai_status"),
            "candidate_option_count": int(row.get("candidate_option_count") or 0),
            "priority_score": int(row.get("priority_score") or 0),
            "queue_rank": int(row.get("queue_rank") or 0),
            "enrichment_status": row.get("enrichment_status"),
        }
    return grouped


def enriched_support_quality(base_quality: float, support_entry: dict[str, Any]) -> float:
    score = max(base_quality, 0.50)
    score += 0.10
    if support_entry.get("selected_test_anchor"):
        score += 0.05
    if support_entry.get("verifier_anchor"):
        score += 0.05
    if int(support_entry.get("row_count") or 0) >= 6:
        score += 0.04
    if support_entry.get("abstention_heavy"):
        score -= 0.06
    score = min(score, 0.74)
    return round(clamp(score), 4)


def packet_ready_quality(base_quality: float, packet_entry: dict[str, Any]) -> float:
    score = max(base_quality, 0.46)
    if str(packet_entry.get("ai_status") or "") == "support_ready_after_enrichment":
        score += 0.08
    if int(packet_entry.get("candidate_option_count") or 0) >= 6:
        score += 0.03
    return round(clamp(score), 4)


def main() -> None:
    reviewed_roots = load_jsonl(REVIEWED_ROOTS)
    compiled_roots = load_jsonl(COMPILED_ROOTS)
    bootstrap_rows = load_jsonl(BOOTSTRAP_ROWS)
    latest_reviewed_package = load_json(LATEST_REVIEWED_PACKAGE)
    packet_rows = load_jsonl(BULK_PACKET_DECISIONS)
    enriched_rows = load_jsonl(BULK_ENRICHED_INDEX)
    support_rows = load_jsonl(BULK_SUPPORT_ROWS)

    bootstrap_agg = aggregate_bootstrap_rows(bootstrap_rows)
    support_agg = aggregate_support_rows(support_rows)
    packet_status = aggregate_packet_status(packet_rows)
    enriched_root_ids = {str(row.get("root_id") or "") for row in enriched_rows if row.get("root_id")}

    manifest_rows: list[dict[str, Any]] = []
    seen_root_ids: set[str] = set()

    for root in reviewed_roots:
        row = {
            "root_id": root["root_id"],
            "repo_id": root["repo_id"],
            "repo_family": root["repo_family"],
            "language_family": root["language_family"],
            "task_family": "reviewed_maintainer_bundle",
            "snapshot_id": root.get("bundle_id") or root["root_id"],
            "verifier_id": "REVIEWED_MAINTAINER_BUNDLE" if root.get("verifier_anchor") else "REVIEWED_MAINTAINER_BUNDLE_NO_VERIFIER",
            "source_family_id": "reviewed_v27_plus_cpp_bootstrap_train_support",
            "root_lineage_key": root_lineage_key(root),
            "quality_score": reviewed_quality(root),
            "admit_role": reviewed_admit_role(root),
            "source_kind": "reviewed_bundle_root",
            "split_component": root.get("split_role"),
            "selected_test_anchor": bool(root.get("selected_test_anchor")),
            "verifier_anchor": bool(root.get("verifier_anchor")),
            "prompt_target_leak_rows": 0,
            "abstention_heavy": bool(root.get("abstention_heavy")),
            "notes": list(root.get("claim_notes") or []),
            "materialization_status": "reviewed_bundle",
        }
        manifest_rows.append(row)
        seen_root_ids.add(row["root_id"])

    for root in compiled_roots:
        root_id = str(root["root_id"])
        agg = bootstrap_agg.get(
            root_id,
            {
                "row_count": 0,
                "prompt_target_leak_rows": 0,
                "opaque_option_rows": 0,
                "bounded_decision_rows": 0,
                "selected_test_like_rows": 0,
                "verifier_outcome_rows": 0,
            },
        )
        notes: list[str] = []
        if agg["prompt_target_leak_rows"] > 0:
            notes.append("prompt_target_leak_rows_present")
        if str(root.get("split_component")) == "strict_eval_long_context_heldout":
            notes.append("heldout_bootstrap_root")
        if agg["verifier_outcome_rows"] > 0:
            notes.append("contains_verifier_outcome_targets")

        quality = bootstrap_quality(root, agg)
        admit_role = bootstrap_admit_role(root, agg)
        source_kind = "compiled_root_state"
        materialization_status = "bootstrap_only"
        selected_test_anchor = agg["selected_test_like_rows"] > 0
        verifier_anchor = str(root.get("verifier_id") or "").startswith("PASS_")
        abstention_heavy = False

        support_entry = support_agg.get(root_id)
        packet_entry = packet_status.get(root_id)
        if support_entry:
            quality = enriched_support_quality(quality, support_entry)
            admit_role = "train"
            source_kind = "compiled_root_state_materialized_bulk_support"
            materialization_status = "bulk_support_materialized"
            selected_test_anchor = selected_test_anchor or bool(support_entry.get("selected_test_anchor"))
            verifier_anchor = verifier_anchor or bool(support_entry.get("verifier_anchor"))
            abstention_heavy = bool(support_entry.get("abstention_heavy"))
            notes.extend(
                [
                    "bulk_reviewed_support_materialized",
                    f"bulk_support_rows={support_entry['row_count']}",
                    f"bulk_support_perspectives={len(support_entry['perspectives'])}",
                ]
            )
        elif packet_entry:
            ai_status = str(packet_entry.get("ai_status") or "")
            quality = packet_ready_quality(quality, packet_entry)
            if ai_status == "support_ready_after_enrichment":
                admit_role = "diagnostic"
                source_kind = "compiled_root_state_support_ready_candidate"
                materialization_status = "support_ready_not_materialized"
                notes.append("bulk_support_ready_after_enrichment")
            elif ai_status == "fresh_candidate_needs_richer_competition":
                admit_role = "diagnostic"
                source_kind = "compiled_root_state_competition_gap_candidate"
                materialization_status = "needs_richer_competition"
                notes.append("fresh_candidate_needs_richer_competition")
            elif ai_status == "blocked_on_shortcut_or_source_enrichment":
                admit_role = "quarantine"
                source_kind = "compiled_root_state_shortcut_blocked_candidate"
                materialization_status = "blocked_on_shortcut_or_source_enrichment"
                notes.append("blocked_on_shortcut_or_source_enrichment")
            if root_id in enriched_root_ids:
                notes.append("selected_for_bulk_enrichment_queue")

        row = {
            "root_id": root_id,
            "repo_id": root.get("repo_id"),
            "repo_family": root.get("repo_family"),
            "language_family": root.get("language_family"),
            "task_family": root.get("task_family"),
            "snapshot_id": root.get("snapshot_id"),
            "verifier_id": root.get("verifier_id"),
            "source_family_id": ((root.get("provenance") or {}).get("source_family_id")) or "unknown",
            "root_lineage_key": root_lineage_key(root),
            "quality_score": quality,
            "admit_role": admit_role,
            "source_kind": source_kind,
            "split_component": root.get("split_component"),
            "selected_test_anchor": selected_test_anchor,
            "verifier_anchor": verifier_anchor,
            "prompt_target_leak_rows": agg["prompt_target_leak_rows"],
            "abstention_heavy": abstention_heavy,
            "notes": notes,
            "materialization_status": materialization_status,
        }
        manifest_rows.append(row)
        seen_root_ids.add(root_id)

    for root_id, support_entry in support_agg.items():
        if root_id in seen_root_ids:
            continue
        row = {
            "root_id": root_id,
            "repo_id": support_entry.get("repo_id"),
            "repo_family": support_entry.get("repo_family"),
            "language_family": support_entry.get("language_family"),
            "task_family": "bulk_reviewed_support_candidate",
            "snapshot_id": root_id,
            "verifier_id": "BULK_REVIEWED_SUPPORT_CANDIDATE" if support_entry.get("verifier_anchor") else "BULK_REVIEWED_SUPPORT_CANDIDATE_NO_VERIFIER",
            "source_family_id": support_entry.get("source_family_id"),
            "root_lineage_key": f"{support_entry.get('repo_id') or 'unknown'}::{root_id}",
            "quality_score": enriched_support_quality(0.50, support_entry),
            "admit_role": "train",
            "source_kind": "bulk_reviewed_support_candidate_only",
            "split_component": "train_support",
            "selected_test_anchor": bool(support_entry.get("selected_test_anchor")),
            "verifier_anchor": bool(support_entry.get("verifier_anchor")),
            "prompt_target_leak_rows": 0,
            "abstention_heavy": bool(support_entry.get("abstention_heavy")),
            "notes": [
                "bulk_reviewed_support_materialized",
                f"bulk_support_rows={support_entry['row_count']}",
                f"bulk_support_perspectives={len(support_entry['perspectives'])}",
            ],
            "materialization_status": "bulk_support_materialized",
        }
        manifest_rows.append(row)
        seen_root_ids.add(root_id)


    for root_id, packet_entry in packet_status.items():
        if root_id in seen_root_ids:
            continue
        ai_status = str(packet_entry.get("ai_status") or "")
        if ai_status == "support_ready_after_enrichment":
            admit_role = "diagnostic"
            materialization_status = "support_ready_not_materialized"
        elif ai_status == "fresh_candidate_needs_richer_competition":
            admit_role = "diagnostic"
            materialization_status = "needs_richer_competition"
        else:
            admit_role = "quarantine"
            materialization_status = "blocked_on_shortcut_or_source_enrichment"
        row = {
            "root_id": root_id,
            "repo_id": packet_entry.get("repo_family"),
            "repo_family": packet_entry.get("repo_family"),
            "language_family": packet_entry.get("language_family"),
            "task_family": "bulk_review_packet_candidate",
            "snapshot_id": root_id,
            "verifier_id": "BULK_REVIEW_PACKET_CANDIDATE",
            "source_family_id": root_id.split("::", 1)[0] if "::" in root_id else "unknown",
            "root_lineage_key": f"{packet_entry.get('repo_family') or 'unknown'}::{root_id}",
            "quality_score": packet_ready_quality(0.40, packet_entry),
            "admit_role": admit_role,
            "source_kind": "bulk_review_packet_candidate_only",
            "split_component": "train_support",
            "selected_test_anchor": False,
            "verifier_anchor": False,
            "prompt_target_leak_rows": 0,
            "abstention_heavy": False,
            "notes": [
                ai_status,
                f"candidate_option_count={int(packet_entry.get('candidate_option_count') or 0)}",
                f"queue_rank={int(packet_entry.get('queue_rank') or 0)}",
            ],
            "materialization_status": materialization_status,
        }
        manifest_rows.append(row)
        seen_root_ids.add(root_id)

    manifest_rows.sort(key=lambda row: (str(row["admit_role"]), str(row["language_family"]), str(row["repo_family"]), str(row["root_id"])))
    write_jsonl(MANIFEST_JSONL, manifest_rows)

    materialization_counts = dict(sorted(Counter(str(row.get("materialization_status") or "unknown") for row in manifest_rows).items()))
    packet_language_counts = dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in packet_rows).items()))
    materialized_bulk_by_language = dict(
        sorted(
            Counter(
                str(row.get("language_family") or "unknown")
                for row in manifest_rows
                if str(row.get("materialization_status") or "") == "bulk_support_materialized"
            ).items()
        )
    )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "root_admission_manifest_v5_ready",
        "claim_scope": [
            "Refresh the root admission manifest so it incorporates the newer bulk reviewed support lane from stages10775-10778 instead of stopping at stage10743.",
            "Upgrade compiled roots when they now have real materialized bulk support rows, while keeping merely support-ready candidates visible but non-promotable.",
            "This is still a scale-control artifact, not a new 100M-vs-Gemma result.",
        ],
        "headline_findings": [
            "The admission manifest no longer stops at the older reviewed-v27-plus-cpp package; it now marks which compiled roots gained actual materialized bulk support rows.",
            "Support-ready-but-unmaterialized bulk candidates remain visible as diagnostic supply instead of being silently dropped from the scale inventory.",
            "This gives a truer language-by-language picture of current trainable supply before the next larger root-split package is built.",
        ],
        "metrics": {
            "manifest_rows": len(manifest_rows),
            "reviewed_root_rows": len(reviewed_roots),
            "compiled_root_rows": len(compiled_roots),
            "bulk_packet_rows": len(packet_rows),
            "bulk_enriched_selected_roots": len(enriched_root_ids),
            "bulk_support_materialized_root_count": sum(1 for row in manifest_rows if row["materialization_status"] == "bulk_support_materialized"),
            "materialization_status_counts": materialization_counts,
            "admit_role_counts": dict(sorted(Counter(str(row.get("admit_role") or "unknown") for row in manifest_rows).items())),
            "language_counts": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in manifest_rows).items())),
            "materialized_bulk_by_language": materialized_bulk_by_language,
            "packet_language_counts": packet_language_counts,
            "current_reviewed_train_rows": int((latest_reviewed_package.get("metrics") or {}).get("merged_train_rows") or 0),
        },
        "source_artifacts": {
            "reviewed_root_manifest": display(REVIEWED_ROOTS),
            "compiled_roots": display(COMPILED_ROOTS),
            "bootstrap_rows": display(BOOTSTRAP_ROWS),
            "bulk_packet_ai_adjudication": display(BULK_PACKET_DECISIONS),
            "bulk_enriched_index": display(BULK_ENRICHED_INDEX),
            "bulk_support_rows": display(BULK_SUPPORT_ROWS),
            "latest_reviewed_support_package": display(LATEST_REVIEWED_PACKAGE),
        },
        "next_best_step": "Build the next scale package from this v5 manifest so the quality-ratchet and phase-readiness reports reflect the newer bulk reviewed support lane, then use that package to plan the next larger root-split multilingual manifest.",
        "outputs": {
            "manifest": display(MANIFEST_JSONL),
            "summary": display(SUMMARY_JSON),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "summary": display(SUMMARY_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
