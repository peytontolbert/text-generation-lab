#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10896
NAME = "stage10896_python_verifier_transition_strict_successor"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "python_verifier_transition_strict_successor.json"
TRAIN_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

BASE_DIR = ARTIFACTS / "stage10881_evidence_alias_quarantine_successor"
CANDIDATE_ROWS_JSONL = ARTIFACTS / "stage10894_code_assist_python_verifier_transition_strict_candidate" / "strict_candidate_rows.jsonl"

MIRRORMIND_STRICT_ROW_ID = (
    "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_"
    "models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python::"
    "verifier_outcome::reviewed_v27_compact"
)


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


def language_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in rows).items()))


def main() -> None:
    train_rows = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_train.jsonl")
    validation_rows = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_validation.jsonl")
    strict_rows = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl")
    stress_rows = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl")
    candidate_rows = load_jsonl(CANDIDATE_ROWS_JSONL)

    if len(candidate_rows) != 1:
        raise ValueError(f"expected exactly 1 strict candidate row, found {len(candidate_rows)}")

    mirror_rows = [row for row in strict_rows if str(row.get("row_id")) == MIRRORMIND_STRICT_ROW_ID]
    if len(mirror_rows) != 1:
        raise ValueError(f"expected exactly 1 MirrorMind strict row, found {len(mirror_rows)}")

    successor_candidate = dict(candidate_rows[0])
    successor_candidate["split"] = "strict_eval"
    successor_candidate["split_role"] = "strict_heldout_successor"
    successor_candidate["strict_eval_eligible"] = True
    successor_candidate["same_manifest_successor"] = True
    successor_candidate["strict_successor_replaces_row_id"] = MIRRORMIND_STRICT_ROW_ID
    anti_cheat = dict(successor_candidate.get("anti_cheat") or {})
    anti_cheat["same_surface_eval_admissible"] = False
    anti_cheat["fresh_successor_slice"] = True
    successor_candidate["anti_cheat"] = anti_cheat

    successor_strict_rows: list[dict[str, Any]] = []
    replaced = False
    for row in strict_rows:
        if str(row.get("row_id")) == MIRRORMIND_STRICT_ROW_ID:
            successor_strict_rows.append(successor_candidate)
            replaced = True
        else:
            successor_strict_rows.append(row)
    if not replaced:
        raise ValueError("failed to replace MirrorMind strict verifier row")

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_verifier_transition_strict_successor_ready",
        "claim_scope": [
            "Prepare a fresh strict-heldout successor slice by replacing the old MirrorMind Python verifier row with the stage10894 opaque code_assist verifier-transition candidate.",
            "Preserve train, validation, and stress splits exactly so only the Python strict verifier interface changes.",
        ],
        "source_package": rel(BASE_DIR / "evidence_alias_quarantine_successor.json"),
        "source_candidate_rows": rel(CANDIDATE_ROWS_JSONL),
        "metrics": {
            "train_rows": len(train_rows),
            "validation_rows": len(validation_rows),
            "strict_rows": len(successor_strict_rows),
            "stress_rows": len(stress_rows),
            "strict_row_replaced": MIRRORMIND_STRICT_ROW_ID,
            "strict_row_inserted": successor_candidate["row_id"],
        },
        "language_counts_by_split": {
            "train": language_counts(train_rows),
            "validation": language_counts(validation_rows),
            "strict_eval": language_counts(successor_strict_rows),
            "stress_eval": language_counts(stress_rows),
        },
        "claim_boundary": {
            "changes_heldout_surface": True,
            "same_train_support_as_stage10881": True,
            "same_validation_surface_as_stage10881": True,
            "same_stress_surface_as_stage10881": True,
            "same_strict_count_as_stage10881": len(successor_strict_rows) == len(strict_rows),
            "headline_continuation_of_22_over_23": False,
        },
        "next_best_step": "Run the current 100M runtime and the same Gemma comparator on this successor strict slice, then report it as a new heldout baseline rather than an extension of the old 22/23 surface.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_ROWS_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_ROWS_JSONL),
            "strict_rows_jsonl": rel(STRICT_ROWS_JSONL),
            "stress_rows_jsonl": rel(STRESS_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_jsonl(TRAIN_ROWS_JSONL, train_rows)
    write_jsonl(VALIDATION_ROWS_JSONL, validation_rows)
    write_jsonl(STRICT_ROWS_JSONL, successor_strict_rows)
    write_jsonl(STRESS_ROWS_JSONL, stress_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
