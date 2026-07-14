#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10479
NAME = "stage10479_python_verifier_dense_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "python_verifier_dense_support_package.json"
ROWS_JSONL = OUT_DIR / "python_verifier_dense_support_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

MIRRORMIND_MANIFEST = ROOT / "runs/local/artifacts/stage10327_python_mirrormind_replenishment_execution_request/python_mirrormind_replenishment_manifest.jsonl"
FRESH_SUPPORT_ROWS = ROOT / "runs/local/artifacts/stage10468_fresh_residual_root_support_package/fresh_residual_root_support_rows.jsonl"

EXTRA_ROW_IDS = {
    "stage10236::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662::python::verifier_outcome::compact_bounded",
}


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


def normalize(row: dict[str, Any], source_name: str, source_manifest: Path) -> dict[str, Any]:
    updated = json.loads(json.dumps(row))
    updated["split"] = "train"
    updated["split_role"] = "train_support"
    updated["loss_mask"] = {"decoder_ce": True}
    updated["expected_enabled_loss"] = "decoder_ce"
    updated["disable_losses"] = []
    updated["train_support_only"] = True
    updated["strict_eval_eligible"] = False
    updated["source_heldout_admissible"] = False
    updated["support_package_stage"] = STAGE
    updated["support_provenance"] = {
        "support_package_stage": STAGE,
        "support_package_name": NAME,
        "source_manifest": display(source_manifest),
        "support_class": source_name,
    }
    return updated


def main() -> None:
    rows: list[dict[str, Any]] = []

    for row in load_jsonl(MIRRORMIND_MANIFEST):
        if row.get("split") == "train" and row.get("language_family") == "python" and row.get("task_type") == "verifier_outcome":
            rows.append(normalize(row, "python_verifier_dense_base", MIRRORMIND_MANIFEST))

    existing_ids = {str(row.get("row_id") or "") for row in rows}
    for row in load_jsonl(FRESH_SUPPORT_ROWS):
        row_id = str(row.get("row_id") or "")
        if row_id in EXTRA_ROW_IDS and row_id not in existing_ids:
            rows.append(normalize(row, "python_verifier_dense_extra_context_pack", FRESH_SUPPORT_ROWS))
            existing_ids.add(row_id)

    rows.sort(key=lambda row: str(row.get("row_id") or ""))
    bundle_counts: dict[str, int] = {}
    for row in rows:
        bundle = str(row.get("source_bundle_id") or "unknown")
        bundle_counts[bundle] = bundle_counts.get(bundle, 0) + 1

    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(rows),
        "decision": "python_verifier_dense_support_ready",
        "claim_scope": [
            "Provide a denser Python verifier-only train support packet for the remaining repaired-overlay residual.",
            "Use only verifier_outcome rows and avoid mixing in Python evidence_citation or broader task support.",
        ],
        "source_artifacts": {
            "mirrormind_manifest": display(MIRRORMIND_MANIFEST),
            "fresh_support_rows": display(FRESH_SUPPORT_ROWS),
        },
        "rows": len(rows),
        "bundle_counts": dict(sorted(bundle_counts.items())),
        "decoder_targets": sorted({str(row.get("decoder_text") or "") for row in rows}),
        "row_ids": [str(row.get("row_id") or "") for row in rows],
        "outputs": {
            "package_json": display(PACKAGE_JSON),
            "rows_jsonl": display(ROWS_JSONL),
        },
        "required_honesty_gates": [
            "Support package must remain verifier_outcome-only for Python.",
            "No current strict overlay row is copied into train.",
            "Train rows remain train_support_only and strict_eval_eligible=false.",
        ],
    }
    write_jsonl(ROWS_JSONL, rows)
    write_json(PACKAGE_JSON, package)
    write_json(SUMMARY, package)
    print(json.dumps(package, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
