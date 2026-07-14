#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10447
NAME = "stage10447_python_disjoint_residual_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "python_disjoint_residual_support_package.json"
ROWS_JSONL = OUT_DIR / "python_disjoint_residual_support_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

STAGE10445_ATLAS = ROOT / "runs/local/artifacts/stage10445_python_disjoint_root_candidate_atlas/python_disjoint_root_candidate_atlas.json"
STAGE10248_MANIFEST = ROOT / "runs/local/artifacts/stage10248_weakness_counterbalance_execution_request/weakness_counterbalance_manifest.jsonl"
STAGE10302_MANIFEST = ROOT / "runs/local/artifacts/stage10302_hf_local_support_execution_request/hf_local_support_manifest.jsonl"

STAGE10236_BUNDLE = (
    "stage10236::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_"
    "src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662::python"
)
STAGE10300_BUNDLE = (
    "stage10300::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_"
    "src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662::python"
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def normalize_train_support(row: dict[str, Any], *, source_manifest: str, support_class: str) -> dict[str, Any]:
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
    provenance = dict(updated.get("support_provenance") or {})
    provenance.update(
        {
            "support_package_stage": STAGE,
            "support_package_name": NAME,
            "source_manifest": source_manifest,
            "support_class": support_class,
        }
    )
    updated["support_provenance"] = provenance
    return updated


def select_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    atlas = load_json(STAGE10445_ATLAS)
    stage10248_rows = load_jsonl(STAGE10248_MANIFEST)
    stage10302_rows = load_jsonl(STAGE10302_MANIFEST)

    stage10236_selected = [
        normalize_train_support(row, source_manifest=display(STAGE10248_MANIFEST), support_class="selected_test_anchor_disjoint_python")
        for row in stage10248_rows
        if str(row.get("source_bundle_id") or "") == STAGE10236_BUNDLE and str(row.get("language_family") or "") == "python"
    ]
    stage10300_selected = [
        normalize_train_support(row, source_manifest=display(STAGE10302_MANIFEST), support_class="python_verifier_disambiguation_disjoint_python")
        for row in stage10302_rows
        if str(row.get("source_bundle_id") or "") == STAGE10300_BUNDLE and str(row.get("language_family") or "") == "python"
    ]

    stage10236_selected.sort(key=lambda row: str(row.get("row_id") or ""))
    stage10300_selected.sort(key=lambda row: str(row.get("row_id") or ""))
    rows = stage10236_selected + stage10300_selected

    task_counts: dict[str, int] = {}
    bundle_counts: dict[str, int] = {}
    for row in rows:
        task = str(row.get("task_type") or "unknown")
        task_counts[task] = task_counts.get(task, 0) + 1
        bundle = str(row.get("source_bundle_id") or "unknown")
        bundle_counts[bundle] = bundle_counts.get(bundle, 0) + 1

    details = {
        "atlas": atlas,
        "counts": {
            "total_rows": len(rows),
            "stage10236_rows": len(stage10236_selected),
            "stage10300_rows": len(stage10300_selected),
        },
        "task_counts": dict(sorted(task_counts.items())),
        "bundle_counts": dict(sorted(bundle_counts.items())),
        "row_ids": [str(row.get("row_id") or "") for row in rows],
    }
    return rows, details


def main() -> None:
    rows, details = select_rows()
    write_jsonl(ROWS_JSONL, rows)

    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(rows) and details["counts"]["stage10236_rows"] == 4 and details["counts"]["stage10300_rows"] == 22,
        "decision": "python_disjoint_residual_support_ready",
        "claim_scope": [
            "Provide disjoint Python train-support rows for residual recovery work without replaying current v2.7 strict rows into train.",
            "Preserve source prompt and opaque-option structure from already-materialized compact bounded rows.",
            "Use stage10236 selected-test anchored support and stage10300 hf-local verifier-disambiguation support together.",
        ],
        "source_artifacts": {
            "stage10445_python_atlas": display(STAGE10445_ATLAS),
            "stage10248_manifest": display(STAGE10248_MANIFEST),
            "stage10302_manifest": display(STAGE10302_MANIFEST),
        },
        "support_bundles": [
            {
                "bundle_id": STAGE10236_BUNDLE,
                "role": "selected_test_anchor_disjoint_python",
                "rows": details["counts"]["stage10236_rows"],
            },
            {
                "bundle_id": STAGE10300_BUNDLE,
                "role": "python_verifier_disambiguation_disjoint_python",
                "rows": details["counts"]["stage10300_rows"],
            },
        ],
        "rows": details["counts"]["total_rows"],
        "task_counts": details["task_counts"],
        "bundle_counts": details["bundle_counts"],
        "row_ids": details["row_ids"],
        "outputs": {
            "package_json": display(PACKAGE_JSON),
            "rows_jsonl": display(ROWS_JSONL),
        },
        "required_honesty_gates": [
            "All rows remain train_support_only and strict_eval_eligible=false.",
            "No current stage10420/stage10424 strict rows are copied into this support package.",
            "Any post-run claim must stay same-manifest unless tested on fresh strict roots separately.",
        ],
    }
    write_json(PACKAGE_JSON, package)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": package["passed"],
            "rows": package["rows"],
            "task_counts": package["task_counts"],
            "package": display(PACKAGE_JSON),
        },
    )
    print(json.dumps(package, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
