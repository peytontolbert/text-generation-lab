#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10786
NAME = "stage10786_larger_root_split_multilingual_training_package"
OUT_DIR = ARTIFACTS / NAME
PACKAGE_JSON = OUT_DIR / "larger_root_split_multilingual_training_package.json"
TRAIN_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
BOOTSTRAP_ADDED_ROWS_JSONL = OUT_DIR / "selected_bootstrap_train_rows.jsonl"
DIAGNOSTIC_ROOTS_JSONL = OUT_DIR / "diagnostic_root_inventory.jsonl"
BOOTSTRAP_DROPPED_ROWS_JSONL = OUT_DIR / "dropped_bootstrap_rows.jsonl"
RUN_SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

BASE_PACKAGE_JSON = ARTIFACTS / "stage10759_reviewed_v27_hf_local_repaired_support_refresh" / "reviewed_v27_hf_local_repaired_support_refresh.json"
BASE_TRAIN_ROWS = ARTIFACTS / "stage10759_reviewed_v27_hf_local_repaired_support_refresh" / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION_ROWS = ARTIFACTS / "stage10759_reviewed_v27_hf_local_repaired_support_refresh" / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT_ROWS = ARTIFACTS / "stage10759_reviewed_v27_hf_local_repaired_support_refresh" / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS_ROWS = ARTIFACTS / "stage10759_reviewed_v27_hf_local_repaired_support_refresh" / "agentkernel_lite_encdec_stress_eval.jsonl"

BULK_SUPPORT_PACKAGE_JSON = ARTIFACTS / "stage10778_bulk_reviewed_support_candidate_training_package" / "bulk_reviewed_support_candidate_training_package.json"
BULK_SUPPORT_ROWS = ARTIFACTS / "stage10778_bulk_reviewed_support_candidate_training_package" / "support_rows.jsonl"
BOOTSTRAP_ROWS = ARTIFACTS / "stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout" / "multitarget_bootstrap_with_heldout_rows.jsonl"
SCALE_INVENTORY = ARTIFACTS / "stage10785_multilingual_root_scale_package_v4" / "scale_ready_root_inventory.jsonl"

ALLOWED_BOOTSTRAP_TARGET_SUBTYPES = {
    "decisive_evidence",
    "retrieve_answer_abstain",
    "verifier_outcome",
}

BOOTSTRAP_ROOT_CAPS = {
    "python": 8,
    "c_cpp": 5,
    "rust": 0,
    "web_js_ts_html": 1,
}

BOOTSTRAP_REPO_CAPS = {
    "python": 1,
    "c_cpp": 2,
    "rust": 0,
    "web_js_ts_html": 1,
}


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


def tag_row(row: dict[str, Any], source_kind: str, package_split: str) -> dict[str, Any]:
    copied = json.loads(json.dumps(row))
    copied["package_source_kind"] = source_kind
    copied["package_split"] = package_split
    return copied


def normalize_decoder_target(row: dict[str, Any]) -> dict[str, Any]:
    copied = json.loads(json.dumps(row))
    target = copied.get("target") if isinstance(copied.get("target"), dict) else {}
    decoder_text = ""
    for value in (
        target.get("decoder_text"),
        copied.get("decoder_text"),
        target.get("target_ref"),
        copied.get("target_ref"),
        copied.get("target_text"),
    ):
        if isinstance(value, str) and value.strip():
            decoder_text = value.strip()
            break
    if decoder_text:
        copied["decoder_text"] = decoder_text
    return copied


def package_counts(rows: list[dict[str, Any]], split_name: str) -> dict[str, Any]:
    return {
        "split": split_name,
        "rows": len(rows),
        "language_counts": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in rows).items())),
        "repo_family_counts": dict(sorted(Counter(str(row.get("repo_family") or "unknown") for row in rows).items())),
        "source_kind_counts": dict(sorted(Counter(str(row.get("package_source_kind") or "unknown") for row in rows).items())),
        "task_type_counts": dict(
            sorted(
                Counter(
                    str(row.get("target_subtype") or row.get("task_type") or row.get("perspective") or "unknown")
                    for row in rows
                ).items()
            )
        ),
        "unique_roots": len(
            {
                str(
                    row.get("source_root_id")
                    or row.get("root_id")
                    or row.get("source_row_id")
                    or row.get("source_bundle_id")
                    or ""
                )
                for row in rows
            }
        ),
    }


def select_bootstrap_root_ids(scale_rows: list[dict[str, Any]]) -> tuple[set[str], dict[str, Any]]:
    eligible = [
        row
        for row in scale_rows
        if str(row.get("admit_role") or "") == "train"
        and str(row.get("source_kind") or "") == "compiled_root_state"
        and str(row.get("materialization_status") or "") == "bootstrap_only"
    ]
    selected: set[str] = set()
    selection_summary: dict[str, Any] = {"by_language": {}}
    for language, root_cap in BOOTSTRAP_ROOT_CAPS.items():
        repo_cap = BOOTSTRAP_REPO_CAPS[language]
        repo_counts: Counter[str] = Counter()
        candidates = sorted(
            [row for row in eligible if str(row.get("language_family") or "") == language],
            key=lambda row: (
                -float(row.get("quality_score") or 0.0),
                str(row.get("repo_family") or ""),
                str(row.get("root_id") or ""),
            ),
        )
        kept: list[str] = []
        dropped: list[str] = []
        for row in candidates:
            root_id = str(row.get("root_id") or "")
            repo_family = str(row.get("repo_family") or "unknown")
            if len(kept) >= root_cap:
                dropped.append(root_id)
                continue
            if repo_counts[repo_family] >= repo_cap:
                dropped.append(root_id)
                continue
            kept.append(root_id)
            selected.add(root_id)
            repo_counts[repo_family] += 1
        selection_summary["by_language"][language] = {
            "root_cap": root_cap,
            "repo_cap": repo_cap,
            "available_roots": len(candidates),
            "kept_roots": kept,
            "dropped_roots": dropped,
        }
    selection_summary["selected_root_count"] = len(selected)
    return selected, selection_summary


def build_root_split_audit(train_rows: list[dict[str, Any]], validation_rows: list[dict[str, Any]], strict_rows: list[dict[str, Any]]) -> dict[str, Any]:
    def roots(rows: list[dict[str, Any]]) -> set[str]:
        return {
            str(
                row.get("source_root_id")
                or row.get("root_id")
                or row.get("source_row_id")
                or row.get("source_bundle_id")
                or ""
            )
            for row in rows
            if str(
                row.get("source_root_id")
                or row.get("root_id")
                or row.get("source_row_id")
                or row.get("source_bundle_id")
                or ""
            )
        }

    train_roots = roots(train_rows)
    validation_roots = roots(validation_rows)
    strict_roots = roots(strict_rows)
    violations = {
        "train_validation_overlap": sorted(train_roots & validation_roots),
        "train_strict_overlap": sorted(train_roots & strict_roots),
        "validation_strict_overlap": sorted(validation_roots & strict_roots),
    }
    return {
        "train_unique_roots": len(train_roots),
        "validation_unique_roots": len(validation_roots),
        "strict_unique_roots": len(strict_roots),
        "violation_count": sum(len(v) for v in violations.values()),
        "violations": violations,
    }


def main() -> None:
    base_package = load_json(BASE_PACKAGE_JSON)
    bulk_package = load_json(BULK_SUPPORT_PACKAGE_JSON)
    base_train_rows = [normalize_decoder_target(tag_row(row, "reviewed_v27_base_train", "train")) for row in load_jsonl(BASE_TRAIN_ROWS)]
    validation_rows = [normalize_decoder_target(tag_row(row, "reviewed_v27_validation", "validation")) for row in load_jsonl(BASE_VALIDATION_ROWS)]
    strict_rows = [normalize_decoder_target(tag_row(row, "reviewed_v27_strict", "strict_eval")) for row in load_jsonl(BASE_STRICT_ROWS)]
    stress_rows = [normalize_decoder_target(tag_row(row, "reviewed_v27_stress", "stress_eval")) for row in load_jsonl(BASE_STRESS_ROWS)]
    bulk_support_rows = [normalize_decoder_target(tag_row(row, "bulk_reviewed_support_materialized", "train")) for row in load_jsonl(BULK_SUPPORT_ROWS)]
    bootstrap_rows = load_jsonl(BOOTSTRAP_ROWS)
    scale_rows = load_jsonl(SCALE_INVENTORY)

    selected_bootstrap_root_ids, bootstrap_selection = select_bootstrap_root_ids(scale_rows)
    selected_bootstrap_rows: list[dict[str, Any]] = []
    dropped_bootstrap_rows: list[dict[str, Any]] = []
    for row in bootstrap_rows:
        if str(row.get("root_id") or "") not in selected_bootstrap_root_ids:
            continue
        if str(row.get("target_family") or "") != "bounded_decision":
            continue
        if str(row.get("target_subtype") or "") not in ALLOWED_BOOTSTRAP_TARGET_SUBTYPES:
            continue
        if not str(row.get("split_component") or "").startswith("train_"):
            continue
        if not str(row.get("target_text") or "").strip():
            dropped_bootstrap_rows.append(
                {
                    "row_id": row.get("row_id"),
                    "root_id": row.get("root_id"),
                    "language_family": row.get("language_family"),
                    "repo_family": row.get("repo_family"),
                    "target_subtype": row.get("target_subtype"),
                    "drop_reason": "empty_target_text",
                }
            )
            continue
        selected_bootstrap_rows.append(normalize_decoder_target(tag_row(row, "bootstrap_bounded_decision", "train")))

    train_rows = [*base_train_rows, *bulk_support_rows, *selected_bootstrap_rows]

    diagnostic_roots = [
        {
            "root_id": row.get("root_id"),
            "language_family": row.get("language_family"),
            "repo_family": row.get("repo_family"),
            "quality_score": row.get("quality_score"),
            "materialization_status": row.get("materialization_status"),
            "admit_role": row.get("admit_role"),
            "notes": row.get("notes") or [],
        }
        for row in scale_rows
        if str(row.get("admit_role") or "") == "diagnostic"
    ]

    train_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    validation_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    strict_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    stress_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    selected_bootstrap_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    diagnostic_roots.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("root_id") or "")))

    write_jsonl(TRAIN_ROWS_JSONL, train_rows)
    write_jsonl(VALIDATION_ROWS_JSONL, validation_rows)
    write_jsonl(STRICT_ROWS_JSONL, strict_rows)
    write_jsonl(STRESS_ROWS_JSONL, stress_rows)
    write_jsonl(BOOTSTRAP_ADDED_ROWS_JSONL, selected_bootstrap_rows)
    write_jsonl(DIAGNOSTIC_ROOTS_JSONL, diagnostic_roots)
    write_jsonl(BOOTSTRAP_DROPPED_ROWS_JSONL, dropped_bootstrap_rows)

    root_split_audit = build_root_split_audit(train_rows, validation_rows, strict_rows)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": root_split_audit["violation_count"] == 0,
        "decision": "larger_root_split_multilingual_training_package_ready",
        "claim_scope": [
            "Keep the reviewed v2.7 honest 24-row strict frontier fixed while widening train support with materialized bulk reviewed roots and a capped bounded-decision bootstrap slice.",
            "Preserve validation and stress from the current reviewed v2.7 base package instead of redefining the headline eval surface.",
            "This package is a larger root-split training base, not a new promotion claim by itself.",
        ],
        "headline_findings": [
            "The train package now includes the 18 materialized bulk reviewed support roots from stages10775-10778.",
            "A capped bootstrap bounded-decision slice adds broader Python, C/C++, and web support without dragging the probe into long-target freeform objectives.",
            "Strict and validation remain fixed to the current honest reviewed-v2.7 package, so any next probe still lives or dies on the same 24-row frontier.",
        ],
        "source_artifacts": {
            "base_package": display(BASE_PACKAGE_JSON),
            "bulk_support_package": display(BULK_SUPPORT_PACKAGE_JSON),
            "bootstrap_rows": display(BOOTSTRAP_ROWS),
            "scale_inventory": display(SCALE_INVENTORY),
        },
        "splits": {
            "train": package_counts(train_rows, "train"),
            "validation": package_counts(validation_rows, "validation"),
            "strict_eval": package_counts(strict_rows, "strict_eval"),
            "stress_eval": package_counts(stress_rows, "stress_eval"),
        },
        "root_split_audit": root_split_audit,
        "train_sources": {
            "base_reviewed_train_rows": len(base_train_rows),
            "bulk_support_rows_added": len(bulk_support_rows),
            "bootstrap_bounded_rows_added": len(selected_bootstrap_rows),
            "bootstrap_rows_dropped_for_empty_target": len(dropped_bootstrap_rows),
        },
        "bootstrap_selection": bootstrap_selection,
        "diagnostic_root_counts": {
            "total": len(diagnostic_roots),
            "by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in diagnostic_roots).items())),
            "by_materialization_status": dict(sorted(Counter(str(row.get("materialization_status") or "unknown") for row in diagnostic_roots).items())),
        },
        "base_package_snapshot": base_package.get("metrics") or {},
        "bulk_package_snapshot": bulk_package.get("metrics") or {},
        "anti_cheat_contract": [
            "Strict rows are copied unchanged from the current honest reviewed v2.7 base package.",
            "Validation rows are copied unchanged from the current honest reviewed v2.7 base package.",
            "Bootstrap additions are train-only, bounded-decision only, and root-capped by language and repo family.",
            "Diagnostic packet-only roots are surfaced separately and do not enter train until materialized.",
        ],
        "next_best_step": "Use this package for the next larger support-only probe request, then audit whether the broader bounded-decision train base improves the honest 24-row frontier without regressions.",
        "outputs": {
            "package_json": display(PACKAGE_JSON),
            "train_rows": display(TRAIN_ROWS_JSONL),
            "validation_rows": display(VALIDATION_ROWS_JSONL),
            "strict_rows": display(STRICT_ROWS_JSONL),
            "stress_rows": display(STRESS_ROWS_JSONL),
            "bootstrap_added_rows": display(BOOTSTRAP_ADDED_ROWS_JSONL),
            "bootstrap_dropped_rows": display(BOOTSTRAP_DROPPED_ROWS_JSONL),
            "diagnostic_roots": display(DIAGNOSTIC_ROOTS_JSONL),
        },
    }

    write_json(PACKAGE_JSON, payload)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": payload["passed"],
            "decision": payload["decision"],
            "package_json": display(PACKAGE_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
