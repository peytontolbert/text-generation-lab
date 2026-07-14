#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11035
NAME = "stage11035_successor_residual_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "successor_residual_support_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_VERIFIER_ROWS_JSONL = OUT_DIR / "added_python_verifier_semantic_rows.jsonl"
RESERVED_CANDIDATES_JSONL = OUT_DIR / "reserved_residual_candidates.jsonl"

BASE_DIR = ARTIFACTS / "stage11030_next_root_support_package"
BASE_SUMMARY = BASE_DIR / "next_root_support_package.json"
BASE_TRAIN = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_RESERVED = BASE_DIR / "reserved_next_root_candidates.jsonl"

SUCCESSOR_DIR = ARTIFACTS / "stage10896_python_verifier_transition_strict_successor"
SUCCESSOR_SUMMARY = SUCCESSOR_DIR / "python_verifier_transition_strict_successor.json"
SUCCESSOR_VALIDATION = SUCCESSOR_DIR / "agentkernel_lite_encdec_validation.jsonl"
SUCCESSOR_STRICT = SUCCESSOR_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
SUCCESSOR_STRESS = SUCCESSOR_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

VERIFIER_SEMANTIC_DIR = ARTIFACTS / "stage10871_verifier_candidate_semantic_support_package"
VERIFIER_SEMANTIC_ROWS = VERIFIER_SEMANTIC_DIR / "added_verifier_candidate_rows.jsonl"

PYTHON_CANDIDATE_SLICE = ARTIFACTS / "stage10902_python_verifier_transition_candidate_slice" / "strict_candidate_rows.jsonl"
SUCCESSOR_STRICT_ROW_ID = "stage10894::code_assist::python::verifier_outcome_semantic_transition::strict_candidate_v1"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
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
    return dict(sorted(Counter(str(row.get(key) or "missing") for row in rows).items()))


def normalize_scored_row(row: dict[str, Any], split: str) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = split
    updated["disable_losses"] = []
    updated["loss_mask"] = {"decoder_ce": True}
    return updated


def main() -> None:
    base_summary = load_json(BASE_SUMMARY)
    successor_summary = load_json(SUCCESSOR_SUMMARY)

    base_train = load_jsonl(BASE_TRAIN)
    base_reserved = load_jsonl(BASE_RESERVED)
    successor_validation = [normalize_scored_row(row, "eval") for row in load_jsonl(SUCCESSOR_VALIDATION)]
    successor_strict = [normalize_scored_row(row, "strict_eval") for row in load_jsonl(SUCCESSOR_STRICT)]
    successor_stress = load_jsonl(SUCCESSOR_STRESS)
    verifier_semantic_rows = load_jsonl(VERIFIER_SEMANTIC_ROWS)
    python_candidate_slice = load_jsonl(PYTHON_CANDIDATE_SLICE)

    base_ids = {str(row.get("row_id") or "") for row in base_train}
    added_verifier_rows: list[dict[str, Any]] = []
    for row in verifier_semantic_rows:
        if str(row.get("language_family") or "") != "python":
            continue
        row_id = str(row.get("row_id") or "")
        if row_id in base_ids:
            continue
        updated = dict(row)
        updated["successor_residual_stage"] = STAGE
        updated["successor_residual_branch"] = True
        updated["train_support_only"] = True
        updated["strict_eval_eligible"] = False
        anti_cheat = dict(updated.get("anti_cheat") or {})
        anti_cheat["successor_residual_branch"] = True
        anti_cheat["python_verifier_semantic_support"] = True
        updated["anti_cheat"] = anti_cheat
        added_verifier_rows.append(updated)

    train_rows = [*base_train, *added_verifier_rows]

    successor_reserved = [
        row for row in python_candidate_slice
        if str(row.get("row_id") or "") != SUCCESSOR_STRICT_ROW_ID
    ]
    reserved_candidates = [*base_reserved, *successor_reserved]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "successor_residual_support_package_ready",
        "claim_scope": [
            "Move the heldout surface onto the stage10896 Python verifier-transition strict successor instead of the older MirrorMind row.",
            "Keep the latest next-root evidence bridge base intact while adding Python verifier-candidate semantic support rows.",
            "Reserve both evidence residual candidates and the second unseen Python verifier-transition candidate for postrun scoring outside train.",
        ],
        "source_artifacts": {
            "base_support_package": rel(BASE_SUMMARY),
            "successor_strict_surface": rel(SUCCESSOR_SUMMARY),
            "python_verifier_semantic_support": rel(VERIFIER_SEMANTIC_DIR / "verifier_candidate_semantic_support_package.json"),
            "python_verifier_candidate_slice": rel(PYTHON_CANDIDATE_SLICE),
        },
        "metrics": {
            "train_rows_before": len(base_train),
            "train_rows_after": len(train_rows),
            "added_python_verifier_semantic_rows": len(added_verifier_rows),
            "added_verifier_rows_by_task": count_by(added_verifier_rows, "task_type"),
            "added_verifier_rows_by_target": count_by(added_verifier_rows, "decoder_text"),
            "added_verifier_rows_by_repo_family": count_by(added_verifier_rows, "repo_family"),
            "validation_rows": len(successor_validation),
            "strict_rows": len(successor_strict),
            "stress_rows": len(successor_stress),
            "reserved_candidates_before": len(base_reserved),
            "reserved_candidates_after": len(reserved_candidates),
            "reserved_candidates_by_language": count_by(reserved_candidates, "language_family"),
            "reserved_candidates_by_repo_family": count_by(reserved_candidates, "repo_family"),
            "strict_python_successor_row": successor_summary.get("metrics", {}).get("strict_row_inserted"),
            "strict_python_replaced_row": successor_summary.get("metrics", {}).get("strict_row_replaced"),
        },
        "findings": [
            "This package attacks the real residual geometry: Python verifier-transition plus explicit-ledger evidence selection.",
            "The old MirrorMind strict row is no longer part of the main strict surface; the successor strict row is scoreable inside the package.",
            "The second code_assist verifier-transition candidate stays reserved so postrun scoring can distinguish generalization from overfitting to the inserted successor row.",
        ],
        "limits": [
            "The added next-root evidence supply is still only a few resolved roots and remains too small for a strong frontier claim.",
            "This package mainly expands evidence-citation plus Python verifier-candidate semantics; it does not add fresh Rust replenishment or promotable web roots.",
            "Treat this branch as residual diagnostic work unless the reserved candidate bank moves materially.",
        ],
        "required_honesty_gates": [
            "Successor strict slice is a new heldout surface and must not be reported as continuity of the old 22/23 headline.",
            "Reserved candidates remain out of train and out of the 23-row successor strict score.",
            "Any gain claim must report successor validation/strict and reserved-candidate results separately.",
        ],
        "next_best_step": "Run one bounded probe initialized from the latest stage11032 runtime, then audit successor validation/strict and the 10-row reserved residual candidate bank separately.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_JSONL),
            "strict_rows_jsonl": rel(STRICT_JSONL),
            "stress_rows_jsonl": rel(STRESS_JSONL),
            "added_python_verifier_rows_jsonl": rel(ADDED_VERIFIER_ROWS_JSONL),
            "reserved_candidates_jsonl": rel(RESERVED_CANDIDATES_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, successor_validation)
    write_jsonl(STRICT_JSONL, successor_strict)
    write_jsonl(STRESS_JSONL, successor_stress)
    write_jsonl(ADDED_VERIFIER_ROWS_JSONL, added_verifier_rows)
    write_jsonl(RESERVED_CANDIDATES_JSONL, reserved_candidates)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
