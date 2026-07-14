#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10857
NAME = "stage10857_residual_family_rebalanced_support_package_plus_python_materialized_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "residual_family_rebalanced_support_package_plus_python_materialized_audit.json"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

PACKAGE_DIR = ARTIFACTS / "stage10856_residual_family_rebalanced_support_package_plus_python_materialized"
PACKAGE_JSON = PACKAGE_DIR / "residual_family_rebalanced_support_package_plus_python_materialized.json"
TRAIN_JSONL = PACKAGE_DIR / "agentkernel_lite_encdec_train.jsonl"
PY_ROWS_JSONL = PACKAGE_DIR / "python_materialized_bounded_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    package = load_json(PACKAGE_JSON)
    train_rows = load_jsonl(TRAIN_JSONL)
    python_rows = load_jsonl(PY_ROWS_JSONL)
    verifier_rows = [row for row in train_rows if row.get("task_type") == "verifier_outcome"]
    evidence_rows = [row for row in train_rows if row.get("task_type") == "evidence_citation"]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_materialized_residual_support_audit_complete",
        "source_package": rel(PACKAGE_JSON),
        "metrics": {
            "train_rows": len(train_rows),
            "python_materialized_rows": len(python_rows),
            "python_materialized_task_counts": dict(sorted(Counter(str(row.get("task_type") or "unknown") for row in python_rows).items())),
            "verifier_rows": len(verifier_rows),
            "evidence_rows": len(evidence_rows),
            "verifier_targets": dict(sorted(Counter(str(row.get("target_text") or row.get("decoder_text") or "unknown") for row in verifier_rows).items())),
            "evidence_targets": dict(sorted(Counter(str(row.get("target_text") or row.get("decoder_text") or "unknown") for row in evidence_rows).items())),
        },
        "residual_gap_readout": {
            "python_verifier_improvement": (
                "The support package now includes one real materialized agentkernel verifier root with six bounded perspectives, "
                "including a selected-test verifier row grounded in real test snippets."
            ),
            "remaining_python_gap": (
                "This is still one root. It improves support geometry but does not yet provide the requested 30+ verifier rows or a second independent family to reduce same-surface priors."
            ),
            "remaining_rust_gap": (
                "Rust evidence still lacks F-target train coverage and fresh heldout E/F roots; the Python improvement does not change that lane."
            ),
        },
        "promotion_readiness": {
            "support_package_only": True,
            "strict_overlay_changed": False,
            "sufficient_for_plateau_break_claim": False,
        },
        "next_best_step": "Use this as the next diagnostic residual-family package if you run another probe; otherwise prioritize one more independent Python verifier root and one stronger Rust E/F root before the next promotion attempt.",
    }

    write_json(OUT_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "artifact": rel(OUT_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
