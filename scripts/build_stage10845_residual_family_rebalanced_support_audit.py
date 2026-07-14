#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10845
NAME = "stage10845_residual_family_rebalanced_support_audit"
OUT_DIR = ARTIFACTS / NAME
AUDIT_JSON = OUT_DIR / "residual_family_rebalanced_support_audit.json"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

PACKAGE_DIR = ARTIFACTS / "stage10844_residual_family_rebalanced_support_package"
PACKAGE_JSON = PACKAGE_DIR / "residual_family_rebalanced_support_package.json"


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
    train_rows = load_jsonl(PACKAGE_DIR / "agentkernel_lite_encdec_train.jsonl")

    verifier_rows = [row for row in train_rows if row.get("task_type") == "verifier_outcome"]
    evidence_rows = [row for row in train_rows if row.get("task_type") == "evidence_citation"]

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "residual_family_rebalanced_support_audit_complete",
        "source_package": rel(PACKAGE_JSON),
        "metrics": {
            "train_rows": len(train_rows),
            "verifier_rows": len(verifier_rows),
            "evidence_rows": len(evidence_rows),
            "verifier_targets": dict(sorted(Counter(str(row.get("target_text") or row.get("decoder_text") or "unknown") for row in verifier_rows).items())),
            "evidence_targets": dict(sorted(Counter(str(row.get("target_text") or row.get("decoder_text") or "unknown") for row in evidence_rows).items())),
            "verifier_option_histogram": package["metrics"]["verifier_outcome_option_histogram"],
            "evidence_option_histogram": package["metrics"]["evidence_citation_option_histogram"],
            "single_option_verifier_rows_remaining": sum(1 for row in verifier_rows if len(row.get("opaque_options") or []) <= 1),
            "parsed_option_rows": sum(1 for row in train_rows if (row.get("anti_cheat") or {}).get("parsed_opaque_options_from_prompt")),
        },
        "residual_gap_readout": {
            "python_verifier_gap": "train geometry is improved but still does not provide B/C/G-style transition supervision at the requested scale",
            "rust_evidence_gap": "E is now present in train evidence_citation, but F remains absent from evidence_citation train targets and fresh strict E/F roots are still missing",
        },
        "promotion_readiness": {
            "support_package_only": True,
            "strict_overlay_changed": False,
            "sufficient_for_plateau_break_claim": False,
        },
        "next_best_step": "Use this as the next diagnostic package only if the probe request lowers preservation pressure and explicitly reports residual-family deltas; otherwise continue root-building first.",
    }

    write_json(AUDIT_JSON, audit)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": audit["decision"],
            "artifact": rel(AUDIT_JSON),
        },
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
