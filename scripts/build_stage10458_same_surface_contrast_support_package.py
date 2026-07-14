#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10458
NAME = "stage10458_same_surface_contrast_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "same_surface_contrast_support_package.json"
ROWS_JSONL = OUT_DIR / "same_surface_contrast_support_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PYTHON_SOURCE = ROOT / "runs/local/artifacts/stage10327_python_mirrormind_replenishment_execution_request/python_mirrormind_replenishment_manifest.jsonl"
RUST_SOURCE = ROOT / "runs/local/artifacts/stage10302_hf_local_support_execution_request/hf_local_support_manifest.jsonl"

PYTHON_BUNDLE = (
    "stage10327::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_29t02_41_34_019acd7c_b80e_7880_9f45_f500_"
    "models_mirrormind_coordinator_py_models_mirrormind_domain_py_models_mirrormind_m_3b079208d1_aug_1500000_8b46e7f662::python"
)
RUST_BUNDLE = "stage10126::tokenizers::tokenizers::rust"


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


def normalize(row: dict[str, Any], *, source_manifest: Path, support_class: str, same_surface: bool) -> dict[str, Any]:
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
    updated["same_surface_diagnostic_support"] = same_surface
    updated["support_provenance"] = {
        "support_package_stage": STAGE,
        "support_package_name": NAME,
        "source_manifest": display(source_manifest),
        "support_class": support_class,
        "same_surface_diagnostic_support": same_surface,
    }
    return updated


def main() -> None:
    python_rows = [
        normalize(
            row,
            source_manifest=PYTHON_SOURCE,
            support_class="python_verifier_bc_contrast",
            same_surface=False,
        )
        for row in load_jsonl(PYTHON_SOURCE)
        if str(row.get("source_bundle_id") or "") == PYTHON_BUNDLE
        and str(row.get("language_family") or "") == "python"
        and str(row.get("task_type") or "") == "verifier_outcome"
        and str(row.get("split") or "") == "train"
    ]
    rust_rows = [
        normalize(
            row,
            source_manifest=RUST_SOURCE,
            support_class="rust_citation_ef_same_surface_contrast",
            same_surface=True,
        )
        for row in load_jsonl(RUST_SOURCE)
        if str(row.get("source_bundle_id") or "") == RUST_BUNDLE
        and str(row.get("language_family") or "") == "rust"
        and str(row.get("task_type") or "") == "evidence_citation"
        and "verifier_and_test_constraint" in str(row.get("prompt_text") or "")
        and "symptom_or_call_path_analogue" in str(row.get("prompt_text") or "")
    ]
    python_rows.sort(key=lambda row: str(row.get("row_id") or ""))
    rust_rows.sort(key=lambda row: str(row.get("row_id") or ""))
    rows = python_rows + rust_rows

    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(rows),
        "decision": "same_surface_contrast_support_ready",
        "claim_scope": [
            "Build a contrast-focused diagnostic support packet around the two remaining residual confusions.",
            "Python verifier rows remain disjoint train support; Rust E-vs-F rows necessarily use same-surface diagnostic support because no disjoint equivalent currently exists.",
        ],
        "rows": len(rows),
        "python_rows": len(python_rows),
        "rust_rows": len(rust_rows),
        "row_ids": [str(row.get("row_id") or "") for row in rows],
        "outputs": {
            "package_json": display(PACKAGE_JSON),
            "rows_jsonl": display(ROWS_JSONL),
        },
        "required_honesty_gates": [
            "Any probe using the Rust tokenizers rows from this package is diagnostic-only and non-promotable.",
            "Do not merge same-surface diagnostic support into the live promotable v2.7 claim path.",
            "Use this packet only to test whether the residual decision boundary can move at all under direct contrast support.",
        ],
    }
    write_jsonl(ROWS_JSONL, rows)
    write_json(PACKAGE_JSON, package)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": package["passed"],
            "rows": package["rows"],
            "python_rows": package["python_rows"],
            "rust_rows": package["rust_rows"],
            "package": display(PACKAGE_JSON),
        },
    )
    print(json.dumps(package, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
