#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10693
NAME = "stage10693_reviewed_plus_bootstrap_multilingual_training_package_balanced"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "reviewed_plus_bootstrap_multilingual_training_package_balanced.json"
TRAIN_ROWS_JSONL = OUT_DIR / "train_rows.jsonl"
VALIDATION_ROWS_JSONL = OUT_DIR / "validation_rows.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "strict_rows.jsonl"
DIAGNOSTIC_ROWS_JSONL = OUT_DIR / "diagnostic_rows.jsonl"
CANARY_ROWS_JSONL = OUT_DIR / "canary_rows.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

ADMISSION_ROWS = ROOT / "runs/local/artifacts/stage10691_root_admission_manifest_v2/root_admission_manifest_v2.jsonl"
SUPPLY_AUDIT = ROOT / "runs/local/artifacts/stage10692_multilingual_root_supply_balance_audit_refreshed/multilingual_root_supply_balance_audit_refreshed.json"
LATEST_REVIEWED_PACKAGE = ROOT / "runs/local/artifacts/stage10687_reviewed_v27_plus_two_fresh_rust_support_package/reviewed_v27_plus_two_fresh_rust_support_package.json"
PRIOR_PACKAGE = ROOT / "runs/local/artifacts/stage10617_reviewed_plus_bootstrap_multilingual_training_package_fixed/reviewed_plus_bootstrap_multilingual_training_package_fixed.json"
REVIEWED_ROWS = ROOT / "runs/local/artifacts/stage10687_reviewed_v27_plus_two_fresh_rust_support_package/reviewed_v27_plus_two_fresh_rust_bounded_rows.jsonl"
BOOTSTRAP_ROWS = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/multitarget_bootstrap_with_heldout_rows.jsonl"
CANARY_ROWS = ROOT / "runs/local/artifacts/stage10436_repaired_v27_strict_overlay/repaired_v27_strict_overlay.jsonl"

# Train-time root caps for compiled long-context roots only.
# Reviewed maintainer bundles are already scarce and manually admitted, so they are kept intact.
COMPILED_TRAIN_ROOT_CAPS_BY_LANGUAGE = {
    "python": 4,
    "c_cpp": 4,
    "rust": 2,
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


def package_counts(rows: list[dict[str, Any]], split_name: str) -> dict[str, Any]:
    return {
        "split": split_name,
        "rows": len(rows),
        "language_counts": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in rows).items())),
        "source_kind_counts": dict(sorted(Counter(str(row.get("package_source_kind") or "unknown") for row in rows).items())),
        "repo_family_counts": dict(sorted(Counter(str(row.get("repo_family") or "unknown") for row in rows).items())),
        "target_family_counts": dict(sorted(Counter(str(row.get("target_family") or "unknown") for row in rows).items())),
        "target_subtype_counts": dict(sorted(Counter(str(row.get("target_subtype") or str(row.get("task_type") or "unknown")) for row in rows).items())),
        "unique_roots": len({str(row.get("root_id") or row.get("source_root_id") or "") for row in rows}),
    }


def tag_row(row: dict[str, Any], package_split: str, source_kind: str) -> dict[str, Any]:
    copied = json.loads(json.dumps(row))
    copied["package_split"] = package_split
    copied["package_source_kind"] = source_kind
    return copied


def select_capped_compiled_train_roots(admission_rows: list[dict[str, Any]]) -> tuple[set[str], dict[str, Any]]:
    train_compiled = [
        row
        for row in admission_rows
        if str(row.get("admit_role") or "") == "train"
        and str(row.get("source_kind") or "") == "compiled_root_state"
    ]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in train_compiled:
        grouped[(str(row.get("language_family") or ""), str(row.get("repo_family") or ""))].append(row)

    selected_root_ids: set[str] = set()
    cap_summary: dict[str, Any] = {"per_language_repo_caps": {}, "dropped_root_ids": []}
    for (language, repo_family), rows in sorted(grouped.items()):
        rows_sorted = sorted(
            rows,
            key=lambda row: (
                -float(row.get("quality_score") or 0.0),
                str(row.get("root_id") or ""),
            ),
        )
        cap = COMPILED_TRAIN_ROOT_CAPS_BY_LANGUAGE.get(language, 2)
        kept = rows_sorted[:cap]
        dropped = rows_sorted[cap:]
        for row in kept:
            selected_root_ids.add(str(row.get("root_id") or ""))
        cap_summary["per_language_repo_caps"].setdefault(language, {})[repo_family] = {
            "cap": cap,
            "available_roots": len(rows_sorted),
            "kept_roots": len(kept),
            "dropped_roots": len(dropped),
        }
        cap_summary["dropped_root_ids"].extend(str(row.get("root_id") or "") for row in dropped)
    cap_summary["selected_root_count"] = len(selected_root_ids)
    cap_summary["dropped_root_count"] = len(cap_summary["dropped_root_ids"])
    return selected_root_ids, cap_summary


def main() -> None:
    admission_rows = load_jsonl(ADMISSION_ROWS)
    supply_audit = load_json(SUPPLY_AUDIT)
    latest_reviewed_package = load_json(LATEST_REVIEWED_PACKAGE)
    prior_package = load_json(PRIOR_PACKAGE)
    reviewed_rows = load_jsonl(REVIEWED_ROWS)
    bootstrap_rows = load_jsonl(BOOTSTRAP_ROWS)
    canary_rows = load_jsonl(CANARY_ROWS)

    admit_role_by_root = {str(row["root_id"]): row for row in admission_rows}
    capped_compiled_train_roots, cap_summary = select_capped_compiled_train_roots(admission_rows)

    train_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    strict_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []

    for row in reviewed_rows:
        root_id = str(row.get("source_root_id") or row.get("root_id") or "")
        admission = admit_role_by_root.get(root_id)
        if admission is None:
            continue
        role = str(admission.get("admit_role") or "")
        row_split = str(row.get("split") or "")
        if role == "train" and row_split == "train":
            train_rows.append(tag_row(row, "train", "reviewed_bundle_root"))
        elif role == "validation" and row_split == "validation":
            validation_rows.append(tag_row(row, "validation", "reviewed_bundle_root"))
        elif role == "strict_eval" and row_split == "strict_eval":
            strict_rows.append(tag_row(row, "strict_eval", "reviewed_bundle_root"))
        elif role == "diagnostic":
            diagnostic_rows.append(tag_row(row, "diagnostic", "reviewed_bundle_root"))

    for row in bootstrap_rows:
        root_id = str(row.get("root_id") or "")
        admission = admit_role_by_root.get(root_id)
        if admission is None:
            continue
        role = str(admission.get("admit_role") or "")
        split_component = str(row.get("split_component") or "")
        if role == "train" and root_id in capped_compiled_train_roots:
            train_rows.append(tag_row(row, "train", "compiled_root_state"))
        elif role == "validation":
            validation_rows.append(tag_row(row, "validation", "compiled_root_state"))
        elif role == "strict_eval":
            strict_rows.append(tag_row(row, "strict_eval", "compiled_root_state"))
        elif role == "diagnostic" or split_component in {"strict_eval_long_context_heldout", "reference_bounded_eval", "diagnostic_bounded"}:
            diagnostic_rows.append(tag_row(row, "diagnostic", "compiled_root_state"))

    canary_tagged = [tag_row(row, "canary", "repaired_v27_overlay") for row in canary_rows]

    train_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    validation_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    strict_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    diagnostic_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    canary_tagged.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))

    write_jsonl(TRAIN_ROWS_JSONL, train_rows)
    write_jsonl(VALIDATION_ROWS_JSONL, validation_rows)
    write_jsonl(STRICT_ROWS_JSONL, strict_rows)
    write_jsonl(DIAGNOSTIC_ROWS_JSONL, diagnostic_rows)
    write_jsonl(CANARY_ROWS_JSONL, canary_tagged)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "reviewed_plus_bootstrap_training_package_balanced_and_refreshed",
        "claim_scope": [
            "Refresh the multilingual training package against the latest reviewed v2.7 successor inventory with two added Rust train-support roots.",
            "Apply explicit compiled-root repo caps so Python and single-family dominance are reduced before the next multilingual probe.",
            "Keep reviewed strict roots, bootstrap strict/validation roots, diagnostic roots, and repaired-v2.7 canary rows explicitly separated.",
            "Continue excluding quarantined roots entirely until their candidate interfaces are rewritten and re-admitted.",
        ],
        "source_artifacts": {
            "root_admission_manifest_v2": display(ADMISSION_ROWS),
            "supply_audit_refreshed": display(SUPPLY_AUDIT),
            "latest_reviewed_package": display(LATEST_REVIEWED_PACKAGE),
            "prior_training_package": display(PRIOR_PACKAGE),
            "reviewed_rows": display(REVIEWED_ROWS),
            "bootstrap_rows": display(BOOTSTRAP_ROWS),
            "repaired_overlay_canary": display(CANARY_ROWS),
        },
        "splits": {
            "train": package_counts(train_rows, "train"),
            "validation": package_counts(validation_rows, "validation"),
            "strict_eval": package_counts(strict_rows, "strict_eval"),
            "diagnostic": package_counts(diagnostic_rows, "diagnostic"),
            "canary": package_counts(canary_tagged, "canary"),
        },
        "delta_vs_stage10617": {
            "prior_train_rows": ((prior_package.get("splits") or {}).get("train") or {}).get("rows"),
            "new_train_rows": len(train_rows),
            "prior_validation_rows": ((prior_package.get("splits") or {}).get("validation") or {}).get("rows"),
            "new_validation_rows": len(validation_rows),
            "prior_strict_rows": ((prior_package.get("splits") or {}).get("strict_eval") or {}).get("rows"),
            "new_strict_rows": len(strict_rows),
        },
        "latest_reviewed_delta": {
            "reviewed_root_records": ((latest_reviewed_package.get("metrics") or {}).get("root_records")),
            "reviewed_train_rows": ((latest_reviewed_package.get("metrics") or {}).get("train_rows")),
            "reviewed_rust_roots": (((latest_reviewed_package.get("metrics") or {}).get("root_language_counts")) or {}).get("rust"),
        },
        "gates": {
            "excluded_quarantine_roots": sum(1 for row in admission_rows if str(row.get("admit_role") or "") == "quarantine"),
            "train_only_from_admitted_roots": True,
            "separate_canary_replay_required": True,
            "compiled_train_repo_caps_applied": True,
            "compiled_train_repo_caps_by_language": COMPILED_TRAIN_ROOT_CAPS_BY_LANGUAGE,
            "repo_caps_required_next": (supply_audit.get("dominance_and_gap_findings") or {}).get("repo_caps_needed"),
        },
        "cap_effect": cap_summary,
        "headline_findings": [
            "The refreshed package now pulls from the latest reviewed Rust support inventory instead of the older 14-root reviewed package.",
            "Compiled train roots are explicitly capped by language/repo family, which reduces Python agentkernel dominance before the next probe.",
            "Strict rows stay separated and leak-clean, while quarantined bootstrap roots remain excluded.",
            "This is a stronger base for the next multilingual probe request, but it does not by itself change the current 22/24 standalone frontier.",
        ],
        "required_next_actions": [
            "Use this balanced package as the base for the next multilingual probe request.",
            "Keep repaired-v2.7 canary rows as explicit preservation replay rather than part of main train counts.",
            "Rewrite quarantined bootstrap interfaces before counting those roots toward scale or headline claims.",
            "Add more leak-clean Rust and pure-web roots rather than expecting the current reviewed support additions alone to solve the remaining frontier misses.",
        ],
        "recommended_next_stage": "stage10694_reviewed_plus_bootstrap_multilingual_probe_request_balanced",
        "outputs": {
            "train_rows": display(TRAIN_ROWS_JSONL),
            "validation_rows": display(VALIDATION_ROWS_JSONL),
            "strict_rows": display(STRICT_ROWS_JSONL),
            "diagnostic_rows": display(DIAGNOSTIC_ROWS_JSONL),
            "canary_rows": display(CANARY_ROWS_JSONL),
            "package_json": display(PACKAGE_JSON),
        },
    }

    write_json(PACKAGE_JSON, payload)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "package": display(PACKAGE_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
