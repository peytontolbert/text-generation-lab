#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11030
NAME = "stage11030_next_root_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "next_root_support_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_ROWS_JSONL = OUT_DIR / "added_next_root_rows.jsonl"
RESERVED_CANDIDATES_JSONL = OUT_DIR / "reserved_next_root_candidates.jsonl"

BASE_DIR = ARTIFACTS / "stage11003_semantic_evidence_bridge_package"
BASE_SUMMARY = BASE_DIR / "semantic_evidence_bridge_package.json"
BASE_TRAIN = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
BASE_CANDIDATES = BASE_DIR / "reviewed_replenishment_candidates.jsonl"

NEXT_ROOT_DIR = ARTIFACTS / "stage11029_reviewed_multilingual_next_root_bundle_resolved"
NEXT_ROOT_SUMMARY = NEXT_ROOT_DIR / "reviewed_multilingual_next_root_bundle_resolved.json"
NEXT_ROOT_SUPPORT = NEXT_ROOT_DIR / "train_support_rows.jsonl"
NEXT_ROOT_CANDIDATES = NEXT_ROOT_DIR / "strict_candidate_rows.jsonl"


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


def main() -> None:
    base_summary = load_json(BASE_SUMMARY)
    next_root_summary = load_json(NEXT_ROOT_SUMMARY)

    base_train = load_jsonl(BASE_TRAIN)
    base_validation = load_jsonl(BASE_VALIDATION)
    base_strict = load_jsonl(BASE_STRICT)
    base_stress = load_jsonl(BASE_STRESS)
    base_candidates = load_jsonl(BASE_CANDIDATES)

    added_rows = load_jsonl(NEXT_ROOT_SUPPORT)
    next_candidates = load_jsonl(NEXT_ROOT_CANDIDATES)

    train_rows = base_train + added_rows
    reserved_candidates = base_candidates + next_candidates

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "next_root_support_package_ready",
        "claim_scope": [
            "Add the stage11029 reviewed next-root support rows on top of the strongest current evidence base.",
            "Keep the frozen 23-row overlay unchanged and reserve the next-root candidate rows outside train for postrun scoring.",
        ],
        "source_artifacts": {
            "base_support_package": rel(BASE_SUMMARY),
            "next_root_bundle": rel(NEXT_ROOT_SUMMARY),
        },
        "metrics": {
            "train_rows_before": len(base_train),
            "train_rows_after": len(train_rows),
            "added_next_root_rows": len(added_rows),
            "validation_rows_unchanged": len(base_validation),
            "strict_rows_unchanged": len(base_strict),
            "stress_rows_unchanged": len(base_stress),
            "reserved_candidates_before": len(base_candidates),
            "reserved_candidates_after": len(reserved_candidates),
            "added_by_language": {
                language: sum(1 for row in added_rows if str(row.get("language_family") or "") == language)
                for language in sorted({str(row.get("language_family") or "") for row in added_rows})
            },
            "candidate_by_language": {
                language: sum(1 for row in reserved_candidates if str(row.get("language_family") or "") == language)
                for language in sorted({str(row.get("language_family") or "") for row in reserved_candidates})
            },
        },
        "findings": [
            "This package keeps the semantic evidence bridge base intact while adding fresh reviewed Python/C++ next-root support.",
            "The overlay contract stays fixed; any future movement can be attributed to train-support changes rather than eval drift.",
            "The web lane remains absent from added train rows because the reviewed code_assist web control root is still unresolved in the current source-row corpus.",
        ],
        "next_best_step": "Run one bounded probe from this package and score both the frozen overlay and the enlarged reserved candidate slice separately.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_JSONL),
            "strict_rows_jsonl": rel(STRICT_JSONL),
            "stress_rows_jsonl": rel(STRESS_JSONL),
            "added_rows_jsonl": rel(ADDED_ROWS_JSONL),
            "reserved_candidates_jsonl": rel(RESERVED_CANDIDATES_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, base_validation)
    write_jsonl(STRICT_JSONL, base_strict)
    write_jsonl(STRESS_JSONL, base_stress)
    write_jsonl(ADDED_ROWS_JSONL, added_rows)
    write_jsonl(RESERVED_CANDIDATES_JSONL, reserved_candidates)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
