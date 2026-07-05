#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/summaries/stage8753_parallel_recovery_gap_audit.json"
STAGE = 8792
NAME = "stage8792_parallel_recovery_readiness_audit"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PARALLEL_RECOVERY_READINESS_AUDIT_STAGE8792.md"
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def readiness_summaries(module_id: str) -> list[str]:
    needle = module_id.lower()
    out = []
    for path in (ROOT / "runs/summaries").glob("stage87*_*.json"):
        name = path.name.lower()
        if needle in name:
            out.append(str(path.relative_to(ROOT)))
    return sorted(out)


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = []
    for record in data.get("records", []):
        if record.get("effective_status") != "missing_real":
            continue
        files = [ROOT / f for f in record.get("files", [])]
        summaries = readiness_summaries(str(record.get("module_id")))
        rows.append(
            {
                "module_id": record.get("module_id"),
                "required_files": record.get("files", []),
                "missing_files": [str(path.relative_to(ROOT)) for path in files if not path.exists()],
                "readiness_summaries": summaries,
                "ready_local": all(path.exists() for path in files) and bool(summaries),
            }
        )
    missing_files = [row for row in rows if row["missing_files"]]
    missing_readiness = [row for row in rows if not row["readiness_summaries"]]
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not missing_files and not missing_readiness,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "audited_missing_real_modules": len(rows),
            "ready_local_modules": sum(1 for row in rows if row["ready_local"]),
            "modules_with_missing_files": len(missing_files),
            "modules_missing_readiness_summary": len(missing_readiness),
            "authority_rows": 0,
        },
        "records": rows,
        "decision": (
            "All Stage8753 missing_real support modules now have local script/test files and readiness summaries."
            if not missing_files and not missing_readiness
            else "Some Stage8753 missing_real support modules still need files or readiness summaries."
        ),
        "next_best_step": "Reconcile central spine and registry in one controlled pass; do not resume mining/training until compiler gate-status integration is stable.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    unresolved = [row["module_id"] for row in rows if not row["ready_local"]]
    DOC.write_text(
        "\n".join(
            [
                "# Stage8792 Parallel Recovery Readiness Audit",
                "",
                f"Passed: `{card['passed']}`",
                "",
                f"Audited Stage8753 missing-real modules: `{len(rows)}`",
                f"Ready local modules: `{card['metrics']['ready_local_modules']}`",
                f"Modules with missing files: `{card['metrics']['modules_with_missing_files']}`",
                f"Modules missing readiness summaries: `{card['metrics']['modules_missing_readiness_summary']}`",
                "",
                f"Unresolved: `{unresolved}`",
                "",
                "Authority remains closed. This audit does not update registry, graph, mining, training, runtime, source/body emission, or promotion.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
