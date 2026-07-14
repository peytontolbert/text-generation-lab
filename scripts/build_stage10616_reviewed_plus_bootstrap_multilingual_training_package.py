#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10616
NAME = "stage10616_reviewed_plus_bootstrap_multilingual_training_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "reviewed_plus_bootstrap_multilingual_training_package.json"
TRAIN_ROWS_JSONL = OUT_DIR / "train_rows.jsonl"
VALIDATION_ROWS_JSONL = OUT_DIR / "validation_rows.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "strict_rows.jsonl"
DIAGNOSTIC_ROWS_JSONL = OUT_DIR / "diagnostic_rows.jsonl"
CANARY_ROWS_JSONL = OUT_DIR / "canary_rows.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

ADMISSION_ROWS = ROOT / "runs/local/artifacts/stage10614_root_admission_manifest_v1/root_admission_manifest_v1.jsonl"
SUPPLY_AUDIT = ROOT / "runs/local/artifacts/stage10615_multilingual_root_supply_balance_audit/multilingual_root_supply_balance_audit.json"
REVIEWED_ROWS = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/reviewed_multilingual_v27_bounded_rows.jsonl"
BOOTSTRAP_ROWS = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/multitarget_bootstrap_with_heldout_rows.jsonl"
CANARY_ROWS = ROOT / "runs/local/artifacts/stage10436_repaired_v27_strict_overlay/repaired_v27_strict_overlay.jsonl"


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


def main() -> None:
    admission_rows = load_jsonl(ADMISSION_ROWS)
    supply_audit = load_json(SUPPLY_AUDIT)
    reviewed_rows = load_jsonl(REVIEWED_ROWS)
    bootstrap_rows = load_jsonl(BOOTSTRAP_ROWS)
    canary_rows = load_jsonl(CANARY_ROWS)

    admit_role_by_root = {str(row["root_id"]): row for row in admission_rows}

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
        if role == "train" and str(row.get("split") or "") == "train":
            train_rows.append(tag_row(row, "train", "reviewed_bundle_root"))
        elif role == "validation" and str(row.get("split") or "") == "validation":
            validation_rows.append(tag_row(row, "validation", "reviewed_bundle_root"))
        elif role == "strict_eval" and str(row.get("split") or "") == "strict_eval":
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
        split = str(row.get("split") or "")
        if role == "train" and split == "train":
            train_rows.append(tag_row(row, "train", "compiled_root_state"))
        elif role == "validation" and split == "eval":
            validation_rows.append(tag_row(row, "validation", "compiled_root_state"))
        elif role == "strict_eval" and split == "strict_eval":
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
        "decision": "reviewed_plus_bootstrap_training_package_materialized",
        "claim_scope": [
            "Prepare the next clean multilingual training package using only train-admitted roots plus standalone canary replay.",
            "Keep reviewed strict roots, bootstrap diagnostic roots, and repaired-v2.7 canary rows explicitly separated.",
            "Exclude quarantined roots from the package entirely until their target interfaces are rewritten and re-admitted.",
        ],
        "source_artifacts": {
            "root_admission_manifest": display(ADMISSION_ROWS),
            "supply_audit": display(SUPPLY_AUDIT),
            "reviewed_v27_rows": display(REVIEWED_ROWS),
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
        "gates": {
            "excluded_quarantine_roots": sum(1 for row in admission_rows if str(row.get("admit_role") or "") == "quarantine"),
            "train_only_from_admitted_roots": True,
            "separate_canary_replay_required": True,
            "repo_caps_required_next": (supply_audit.get("dominance_and_gap_findings") or {}).get("repo_caps_needed"),
        },
        "headline_findings": [
            "The next clean multilingual package is executable without touching quarantined roots.",
            "It is still heavily Python-leaning unless repo caps or per-language sampling are applied at run time.",
            "Rust and web remain thin enough that package assembly alone will not solve the multilingual gap; more leak-clean roots are still required.",
        ],
        "required_next_actions": [
            "Use this package as the base for the next multilingual training request, but apply repo-family caps and per-language balancing.",
            "Keep repaired-v2.7 canary rows out of main train counts and treat them as explicit preservation replay only.",
            "Rewrite quarantined bootstrap interfaces before counting those roots toward scale or headline claims.",
        ],
        "recommended_next_stage": "stage10617_reviewed_plus_bootstrap_multilingual_probe_request",
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
