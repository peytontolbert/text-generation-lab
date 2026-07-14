#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11009
NAME = "stage11009_diagnostic_geometry_curriculum_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "diagnostic_geometry_curriculum_package.json"
TRAIN_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
DIAGNOSTIC_ADDED_ROWS_JSONL = OUT_DIR / "diagnostic_added_rows.jsonl"

BASE_DIR = ARTIFACTS / "stage10975_multilingual_reviewed_replenishment_support_package"
EXPANDED_ROWS = ARTIFACTS / "stage10963_expanded_evidence_successor_family" / "expanded_successor_rows.jsonl"
SEMANTIC_ROWS = ARTIFACTS / "stage10979_reviewed_evidence_role_curriculum_package" / "support_rows_all.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counter = Counter(str(row.get(key) or "missing") for row in rows)
    return dict(sorted(counter.items()))


def main() -> None:
    base_train = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_train.jsonl")
    base_validation = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_validation.jsonl")
    base_strict = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl")
    expanded_rows = load_jsonl(EXPANDED_ROWS)
    semantic_rows = load_jsonl(SEMANTIC_ROWS)

    base_ids = {str(row.get("row_id") or "") for row in base_train}
    diagnostic_added: list[dict[str, Any]] = []

    for row in expanded_rows:
        updated = dict(row)
        updated["split"] = "train"
        updated["split_role"] = "diagnostic_train_support_same_root"
        updated["train_support_only"] = True
        updated["strict_eval_eligible"] = False
        updated["geometry_diagnostic_same_root_train"] = True
        updated["expected_enabled_loss"] = "decoder_ce"
        updated["loss_mask"] = {"decoder_ce": True}
        anti_cheat = dict(updated.get("anti_cheat") or {})
        anti_cheat["diagnostic_same_root_train"] = True
        anti_cheat["non_promotable_geometry_absorption"] = True
        updated["anti_cheat"] = anti_cheat
        diagnostic_added.append(updated)

    for row in semantic_rows:
        if str(row.get("curriculum_source_stage") or "") != "stage10925_semantic":
            continue
        row_id = str(row.get("row_id") or "")
        if row_id in base_ids:
            continue
        updated = dict(row)
        updated["diagnostic_semantic_bridge_train"] = True
        updated["train_support_only"] = True
        updated["strict_eval_eligible"] = False
        anti_cheat = dict(updated.get("anti_cheat") or {})
        anti_cheat["non_promotable_geometry_absorption"] = True
        updated["anti_cheat"] = anti_cheat
        diagnostic_added.append(updated)

    train_rows = [*base_train, *diagnostic_added]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "diagnostic_geometry_absorption_package_ready",
        "claim_scope": [
            "Build a non-promotable diagnostic package that directly trains on the expanded successor geometry variants.",
            "Test whether the model can absorb the evidence geometry at all before investing further in fresh-root generation.",
        ],
        "source_artifacts": {
            "base_support_package": rel(BASE_DIR / "multilingual_reviewed_replenishment_support_package.json"),
            "expanded_successor_family": rel(ARTIFACTS / "stage10963_expanded_evidence_successor_family" / "expanded_evidence_successor_family.json"),
            "semantic_curriculum": rel(ARTIFACTS / "stage10979_reviewed_evidence_role_curriculum_package" / "reviewed_evidence_role_curriculum_package.json"),
        },
        "metrics": {
            "train_rows_before": len(base_train),
            "train_rows_after": len(train_rows),
            "diagnostic_added_rows": len(diagnostic_added),
            "added_by_language": count_by(diagnostic_added, "language_family"),
            "added_by_repo_family": count_by(diagnostic_added, "repo_family"),
            "added_by_objective": count_by(diagnostic_added, "objective_family"),
            "validation_rows_unchanged": len(base_validation),
            "strict_rows_unchanged": len(base_strict),
        },
        "findings": [
            "This package is explicitly non-promotable because it trains on same-root expanded geometry variants.",
            "If this branch still cannot move the wider geometry bank, the remaining issue is unlikely to be solved by more packaging of the same roots.",
            "A positive result would only justify fresh-root generation with the same geometry, not a benchmark claim.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_ROWS_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_ROWS_JSONL),
            "strict_rows_jsonl": rel(STRICT_ROWS_JSONL),
            "diagnostic_added_rows_jsonl": rel(DIAGNOSTIC_ADDED_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(TRAIN_ROWS_JSONL, train_rows)
    write_jsonl(VALIDATION_ROWS_JSONL, base_validation)
    write_jsonl(STRICT_ROWS_JSONL, base_strict)
    write_jsonl(DIAGNOSTIC_ADDED_ROWS_JSONL, diagnostic_added)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
