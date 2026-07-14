#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11198
NAME = "stage11198_role_focused_residual_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "role_focused_residual_support_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_JSONL = OUT_DIR / "added_role_focused_support_rows.jsonl"

BASE_DIR = ARTIFACTS / "stage11180_cleaned_plus_contract_evidence_support_package"
BASE_TRAIN = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
SUPPORT_ROWS = ARTIFACTS / "stage11178_contract_aware_evidence_rows/contract_aware_evidence_rows.jsonl"
RESIDUAL_BANK = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"

FOCUS_ROLES = {"verifier_and_test_constraint", "symptom_or_call_path_analogue"}
CONTROL_ROLE = "candidate_change_surface"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


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


def gold_value(row: dict[str, Any]) -> str:
    return str((row.get("standalone_projection_source") or {}).get("gold_value") or "missing")


def clone_for_replay(row: dict[str, Any], replay_idx: int, replay_kind: str) -> dict[str, Any]:
    cloned = dict(row)
    cloned["row_id"] = f"{row.get('row_id')}::stage11198_{replay_kind}_replay_{replay_idx:02d}"
    cloned["stage11198_source_row_id"] = row.get("row_id")
    cloned["stage11198_replay_kind"] = replay_kind
    cloned["train_support_only"] = True
    cloned["strict_eval_eligible"] = False
    anti = dict(cloned.get("anti_cheat") or {})
    anti["stage11198_replay_duplicate_for_diagnostic_training"] = True
    cloned["anti_cheat"] = anti
    return cloned


def main() -> None:
    base_train = load_jsonl(BASE_TRAIN)
    validation = load_jsonl(BASE_VALIDATION)
    strict = load_jsonl(BASE_STRICT)
    stress = load_jsonl(BASE_STRESS)
    support = load_jsonl(SUPPORT_ROWS)
    residual = load_jsonl(RESIDUAL_BANK)

    eval_roots = {str(row.get("root_id") or row.get("source_root_id") or "") for row in [*validation, *strict, *stress, *residual] if row.get("root_id") or row.get("source_root_id")}
    eligible = [row for row in support if str(row.get("root_id") or row.get("source_root_id") or "") not in eval_roots]
    focus = [row for row in eligible if gold_value(row) in FOCUS_ROLES]
    controls = [row for row in eligible if gold_value(row) == CONTROL_ROLE]

    # Make this a diagnostic pressure probe: repeated non-heldout support rows alter gradient geometry
    # without touching the residual successor bank itself.
    added: list[dict[str, Any]] = []
    for idx in range(4):
        for row in focus:
            added.append(clone_for_replay(row, idx, "focus_role"))
    for idx in range(1):
        for row in controls:
            added.append(clone_for_replay(row, idx, "candidate_control"))

    train = [*base_train, *added]
    added_roots = {str(row.get("root_id") or row.get("source_root_id") or "") for row in added if row.get("root_id") or row.get("source_root_id")}
    root_overlap = sorted(added_roots & eval_roots)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(added) and not root_overlap,
        "decision": "role_focused_support_package_ready" if added and not root_overlap else "role_focused_support_package_blocked",
        "claim_scope": [
            "Diagnostic package only: oversamples root-disjoint train-support evidence rows for roles where the clean residual bank loses to Gemma.",
            "Does not train on clean residual successor bank rows.",
            "Must be judged on clean strict preservation and same-manifest residual successor scoring after training.",
        ],
        "source_artifacts": {
            "base_train": rel(BASE_TRAIN),
            "support_rows": rel(SUPPORT_ROWS),
            "residual_bank": rel(RESIDUAL_BANK),
        },
        "metrics": {
            "base_train_rows": len(base_train),
            "train_rows_after": len(train),
            "support_rows_total": len(support),
            "eligible_support_rows": len(eligible),
            "focus_source_rows": len(focus),
            "control_source_rows": len(controls),
            "added_rows": len(added),
            "added_unique_source_rows": len({row.get("stage11198_source_row_id") for row in added}),
            "added_unique_roots": len(added_roots),
            "root_overlap_with_eval_or_residual": root_overlap,
            "added_by_gold_value": dict(sorted(Counter(gold_value(row) for row in added).items())),
            "added_by_language": dict(sorted(Counter(str(row.get("language_family") or "missing") for row in added).items())),
            "added_by_replay_kind": dict(sorted(Counter(str(row.get("stage11198_replay_kind") or "missing") for row in added).items())),
        },
        "limits": [
            "Replay duplicates make this diagnostic, not promotable training evidence by itself.",
            "If this fails to move verifier/symptom roles, the next step is a scorer/objective change rather than more row duplication.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_JSONL),
            "strict_rows_jsonl": rel(STRICT_JSONL),
            "stress_rows_jsonl": rel(STRESS_JSONL),
            "added_rows_jsonl": rel(ADDED_JSONL),
        },
    }
    write_jsonl(TRAIN_JSONL, train)
    write_jsonl(VALIDATION_JSONL, validation)
    write_jsonl(STRICT_JSONL, strict)
    write_jsonl(STRESS_JSONL, stress)
    write_jsonl(ADDED_JSONL, added)
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
