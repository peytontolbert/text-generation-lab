#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11438
NAME = "stage11438_root_purged_semantic_candidate_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "root_purged_semantic_candidate_package.json"
SOURCE = ARTIFACTS / "stage11437_semantic_candidate_probe_ready_filtered_package"
INPUTS = {
    "train": SOURCE / "agentkernel_lite_encdec_train.jsonl",
    "validation": SOURCE / "agentkernel_lite_encdec_validation.jsonl",
    "strict_eval": SOURCE / "agentkernel_lite_encdec_strict_eval.jsonl",
    "stress_eval": SOURCE / "agentkernel_lite_encdec_stress_eval.jsonl",
    "residual_bank": SOURCE / "semantic_candidate_residual_bank.jsonl",
    "quarantine": SOURCE / "semantic_candidate_quarantined_rows.jsonl",
}
OUTPUTS = {
    "train": OUT_DIR / "agentkernel_lite_encdec_train.jsonl",
    "validation": OUT_DIR / "agentkernel_lite_encdec_validation.jsonl",
    "strict_eval": OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl",
    "stress_eval": OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl",
    "residual_bank": OUT_DIR / "semantic_candidate_residual_bank.jsonl",
    "quarantine": OUT_DIR / "semantic_candidate_quarantined_rows.jsonl",
    "root_overlap_quarantine": OUT_DIR / "semantic_candidate_root_overlap_train_quarantine.jsonl",
}


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def root_key(row: dict[str, Any]) -> str:
    for key in ("root_id", "source_root_id", "root_lineage_key", "source_bundle_id"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(row.get("row_id") or "")


def task_type(row: dict[str, Any]) -> str:
    return str(row.get("task_type") or row.get("perspective") or "unknown")


def count(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "roots": len({root_key(row) for row in rows}),
        "by_language": dict(sorted(Counter(str(row.get("language_family") or row.get("language") or "unknown") for row in rows).items())),
        "by_task": dict(sorted(Counter(task_type(row) for row in rows).items())),
    }


def main() -> None:
    source_summary = json.loads((SOURCE / "semantic_candidate_probe_ready_filtered_package.json").read_text(encoding="utf-8"))
    train_rows = load_jsonl(INPUTS["train"])
    validation_rows = load_jsonl(INPUTS["validation"])
    strict_rows = load_jsonl(INPUTS["strict_eval"])
    stress_rows = load_jsonl(INPUTS["stress_eval"])
    residual_rows = load_jsonl(INPUTS["residual_bank"])
    existing_quarantine = load_jsonl(INPUTS["quarantine"])
    protected_roots = {root_key(row) for row in validation_rows + strict_rows + residual_rows}
    kept_train: list[dict[str, Any]] = []
    overlap_quarantine: list[dict[str, Any]] = []
    for row in train_rows:
        if root_key(row) in protected_roots:
            out = dict(row)
            out["stage11438_quarantine_reason"] = "train_root_overlaps_validation_strict_or_residual"
            overlap_quarantine.append(out)
        else:
            kept_train.append(row)
    write_jsonl(OUTPUTS["train"], kept_train)
    write_jsonl(OUTPUTS["validation"], validation_rows)
    write_jsonl(OUTPUTS["strict_eval"], strict_rows)
    write_jsonl(OUTPUTS["stress_eval"], stress_rows)
    write_jsonl(OUTPUTS["residual_bank"], residual_rows)
    write_jsonl(OUTPUTS["quarantine"], existing_quarantine + overlap_quarantine)
    write_jsonl(OUTPUTS["root_overlap_quarantine"], overlap_quarantine)
    train_roots = {root_key(row) for row in kept_train}
    overlaps_after = sorted(train_roots & protected_roots)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "root_purged_semantic_candidate_package_ready_for_probe_request",
        "claim_scope": "diagnostic package only; removes train rows overlapping protected validation/strict/residual roots",
        "source_stage": source_summary.get("stage_name"),
        "inputs": {key: rel(path) for key, path in INPUTS.items()},
        "outputs": {key: rel(path) for key, path in OUTPUTS.items()},
        "source_counts": {
            "train": count(train_rows),
            "validation": count(validation_rows),
            "strict_eval": count(strict_rows),
            "residual_bank": count(residual_rows),
        },
        "kept_counts": {
            "train": count(kept_train),
            "validation": count(validation_rows),
            "strict_eval": count(strict_rows),
            "residual_bank": count(residual_rows),
        },
        "quarantine_counts": {
            "root_overlap_train_rows": count(overlap_quarantine),
            "all_quarantined_rows": count(existing_quarantine + overlap_quarantine),
        },
        "gates": {
            "train_nonempty": len(kept_train) > 0,
            "validation_nonempty": len(validation_rows) > 0,
            "strict_nonempty": len(strict_rows) > 0,
            "residual_nonempty": len(residual_rows) > 0,
            "root_overlap_violations_after_purge": len(overlaps_after),
            "root_split_clean_for_probe": len(overlaps_after) == 0,
        },
        "purged_root_ids": sorted({root_key(row) for row in overlap_quarantine}),
        "decision_basis": [
            "Stage11438 request generation caught train/protected root overlap in the Stage11437 filtered package.",
            "This package removes overlapping train roots before any semantic-candidate-head training run.",
            "Filtered validation/strict denominators remain 22 rows each and must be reported separately from the old 23-row canary.",
        ],
        "recommended_next_action": "build and execute one semantic-candidate-head diagnostic request from this root-purged package, then audit old canary separately",
    }
    write_json(SUMMARY_JSON, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY_JSON, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "gates": summary["gates"], "kept_counts": summary["kept_counts"], "purged_roots": len(summary["purged_root_ids"])}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
