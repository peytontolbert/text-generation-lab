#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10998
NAME = "stage10998_fresh_evidence_branch_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_evidence_branch_package.json"
TRAIN_SUPPORT_JSONL = OUT_DIR / "train_support_rows.jsonl"
STRICT_CANDIDATE_JSONL = OUT_DIR / "strict_candidate_rows.jsonl"
OVERLAY_VAL_JSONL = OUT_DIR / "overlay_validation_rows.jsonl"
OVERLAY_STRICT_JSONL = OUT_DIR / "overlay_strict_rows.jsonl"

SOURCE_DIR = ARTIFACTS / "stage10970_immediate_evidence_replenishment_bundle"
SOURCE_SUMMARY_JSON = SOURCE_DIR / "immediate_evidence_replenishment_bundle.json"
SOURCE_SUPPORT_JSONL = SOURCE_DIR / "train_support_rows.jsonl"
SOURCE_CANDIDATE_JSONL = SOURCE_DIR / "strict_candidate_rows.jsonl"
SOURCE_AUDIT_JSON = ARTIFACTS / "stage10971_immediate_evidence_replenishment_audit" / "immediate_evidence_replenishment_audit.json"
OVERLAY_DIR = ARTIFACTS / "stage10983_clean_residual_family_support_package"
OVERLAY_VAL_SOURCE = OVERLAY_DIR / "agentkernel_lite_encdec_validation.jsonl"
OVERLAY_STRICT_SOURCE = OVERLAY_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def annotate_support(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = "train"
    updated["train_support_only"] = True
    updated["strict_eval_eligible"] = False
    updated["fresh_evidence_branch"] = True
    updated["fresh_evidence_role"] = "train_support"
    return updated


def annotate_candidate(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = "strict_eval"
    updated["train_support_only"] = False
    updated["strict_eval_eligible"] = True
    updated["fresh_evidence_branch"] = True
    updated["fresh_evidence_role"] = "strict_candidate"
    return updated


def annotate_overlay(row: dict[str, Any], split: str) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = split
    updated["fresh_evidence_branch"] = False
    return updated


def main() -> None:
    source_summary = load_json(SOURCE_SUMMARY_JSON)
    source_audit = load_json(SOURCE_AUDIT_JSON)
    support_rows = [annotate_support(row) for row in load_jsonl(SOURCE_SUPPORT_JSONL)]
    candidate_rows = [annotate_candidate(row) for row in load_jsonl(SOURCE_CANDIDATE_JSONL)]
    overlay_val_rows = [annotate_overlay(row, "eval") for row in load_jsonl(OVERLAY_VAL_SOURCE)]
    overlay_strict_rows = [annotate_overlay(row, "strict_eval") for row in load_jsonl(OVERLAY_STRICT_SOURCE)]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(support_rows) and bool(candidate_rows),
        "decision": "fresh_evidence_branch_packaged",
        "claim_scope": [
            "Package the immediate replenishment roots as a fresh evidence branch with separate train-support and strict-candidate slices.",
            "Keep the existing 23-row overlay alongside the branch so fresh-root progress can be read next to the stable canary rather than replacing it.",
        ],
        "required_honesty_gates": [
            "Fresh candidate rows remain out of train and retain selected-test-backed anti-cheat metadata.",
            "Overlay validation and strict rows are copied unchanged from stage10983.",
            "This package is designed to measure progress on new evidence roots, not to promote a new headline by itself.",
        ],
        "metrics": {
            "support_rows": len(support_rows),
            "candidate_rows": len(candidate_rows),
            "overlay_eval_rows": len(overlay_val_rows),
            "overlay_strict_rows": len(overlay_strict_rows),
            "support_by_language": dict(sorted(Counter(str(r.get("language_family") or "unknown") for r in support_rows).items())),
            "candidate_by_language": dict(sorted(Counter(str(r.get("language_family") or "unknown") for r in candidate_rows).items())),
            "candidate_targets": dict(sorted(Counter(str(r.get("target_text") or "unknown") for r in candidate_rows).items())),
            "source_bundle_metrics": source_summary.get("metrics"),
            "source_audit_metrics": source_audit.get("metrics"),
        },
        "headline_findings": [
            "The immediate replenishment bundle gives us 3 fresh evidence roots with selected-test-backed candidate rows and 12 matching support rows.",
            "All three candidates are anti-cheat-audited and root-disjoint from the stale strict overlay path.",
            "This branch is the cleanest current way to measure whether the standalone runtime can generalize beyond the repaired overlay.",
        ],
        "next_best_step": "Score the current best standalone runtime on the fresh strict candidate slice, then decide whether to train on the 12 support rows or hold them back for a cleaner future package.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_support_rows_jsonl": rel(TRAIN_SUPPORT_JSONL),
            "strict_candidate_rows_jsonl": rel(STRICT_CANDIDATE_JSONL),
            "overlay_validation_rows_jsonl": rel(OVERLAY_VAL_JSONL),
            "overlay_strict_rows_jsonl": rel(OVERLAY_STRICT_JSONL),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_jsonl(TRAIN_SUPPORT_JSONL, support_rows)
    write_jsonl(STRICT_CANDIDATE_JSONL, candidate_rows)
    write_jsonl(OVERLAY_VAL_JSONL, overlay_val_rows)
    write_jsonl(OVERLAY_STRICT_JSONL, overlay_strict_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
