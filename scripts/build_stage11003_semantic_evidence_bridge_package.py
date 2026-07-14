#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11003
NAME = "stage11003_semantic_evidence_bridge_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "semantic_evidence_bridge_package.json"
TRAIN_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_ROWS_JSONL = OUT_DIR / "added_semantic_bridge_rows.jsonl"
STRICT_CANDIDATES_JSONL = OUT_DIR / "reviewed_replenishment_candidates.jsonl"

BASE_DIR = ARTIFACTS / "stage10975_multilingual_reviewed_replenishment_support_package"
SEMANTIC_DIR = ARTIFACTS / "stage10979_reviewed_evidence_role_curriculum_package"
REPLENISHMENT_DIR = ARTIFACTS / "stage10974_multilingual_reviewed_replenishment_package"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
    base_stress = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl")
    semantic_all = load_jsonl(SEMANTIC_DIR / "support_rows_all.jsonl")
    replenishment_candidates = load_jsonl(REPLENISHMENT_DIR / "strict_candidate_rows.jsonl")

    base_ids = {str(row.get("row_id") or "") for row in base_train}
    added_rows: list[dict[str, Any]] = []
    for row in semantic_all:
        if str(row.get("curriculum_source_stage") or "") != "stage10925_semantic":
            continue
        row_id = str(row.get("row_id") or "")
        if row_id in base_ids:
            continue
        updated = dict(row)
        updated["semantic_bridge_stage"] = STAGE
        updated["semantic_bridge_branch"] = True
        updated["train_support_only"] = True
        updated["strict_eval_eligible"] = False
        anti_cheat = dict(updated.get("anti_cheat") or {})
        anti_cheat["semantic_bridge_branch"] = True
        anti_cheat["overlap_support_only"] = True
        updated["anti_cheat"] = anti_cheat
        added_rows.append(updated)

    train_rows = [*base_train, *added_rows]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(added_rows),
        "decision": "semantic_evidence_bridge_branch_ready",
        "claim_scope": [
            "Build a broader diagnostic branch by adding semantic evidence-role supervision on top of the 217-row reviewed replenishment base.",
            "Keep the frozen overlay unchanged and preserve the 6-row reviewed replenishment candidate slice for postrun scoring.",
            "Measure whether semantic evidence-role supervision can move the candidate_change_surface prior without changing the heldout overlay contract.",
        ],
        "source_artifacts": {
            "base_support_package": rel(BASE_DIR / "multilingual_reviewed_replenishment_support_package.json"),
            "semantic_curriculum_package": rel(SEMANTIC_DIR / "reviewed_evidence_role_curriculum_package.json"),
            "reviewed_replenishment_candidates": rel(REPLENISHMENT_DIR / "strict_candidate_rows.jsonl"),
        },
        "metrics": {
            "train_rows_before": len(base_train),
            "train_rows_after": len(train_rows),
            "added_semantic_rows": len(added_rows),
            "added_by_language": count_by(added_rows, "language_family"),
            "added_by_repo_family": count_by(added_rows, "repo_family"),
            "added_by_objective": count_by(added_rows, "objective_family"),
            "added_by_target": count_by(added_rows, "decoder_text"),
            "candidate_rows_reserved": len(replenishment_candidates),
            "candidate_by_language": count_by(replenishment_candidates, "language_family"),
            "candidate_by_repo_family": count_by(replenishment_candidates, "repo_family"),
            "overlay_validation_rows_unchanged": len(base_validation),
            "overlay_strict_rows_unchanged": len(base_strict),
            "stress_rows_unchanged": len(base_stress),
        },
        "findings": [
            "This branch adds the only genuinely new cross-language evidence-role supervision currently available beyond the 217-row replenishment base.",
            "All added rows are train-support only and remain non-promotable because they overlap existing reviewed roots.",
            "The branch is still not a scale solution, but it is the cleanest available test of whether semantic evidence-role targets help the evidence scorer boundary.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_ROWS_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_ROWS_JSONL),
            "strict_rows_jsonl": rel(STRICT_ROWS_JSONL),
            "stress_rows_jsonl": rel(STRESS_ROWS_JSONL),
            "added_rows_jsonl": rel(ADDED_ROWS_JSONL),
            "reserved_candidate_rows_jsonl": rel(STRICT_CANDIDATES_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(TRAIN_ROWS_JSONL, train_rows)
    write_jsonl(VALIDATION_ROWS_JSONL, base_validation)
    write_jsonl(STRICT_ROWS_JSONL, base_strict)
    write_jsonl(STRESS_ROWS_JSONL, base_stress)
    write_jsonl(ADDED_ROWS_JSONL, added_rows)
    write_jsonl(STRICT_CANDIDATES_JSONL, replenishment_candidates)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
