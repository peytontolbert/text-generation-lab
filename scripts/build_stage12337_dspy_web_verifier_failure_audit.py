#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12337_dspy_web_verifier_failure_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
DSPY_SUMMARY = ROOT / "runs/summaries/stage12335_dspy_web_focused_verifier_executor.json"
DSPY_STDERR = ROOT / "runs/local/artifacts/stage12335_dspy_web_focused_verifier_executor/logs/dspy_react_app_focused_stderr.log"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def classify_failure(stderr: str) -> tuple[str, list[str]]:
    lowered = stderr.lower()
    evidence = []
    if "cannot use import statement outside a module" in lowered and "node_modules/axios/index.js" in lowered:
        evidence.append("axios_esm_in_jest_transform_failure")
        return "verifier_environment_or_test_config_failure", evidence
    if "no tests found" in lowered:
        evidence.append("focused_test_pattern_no_match")
        return "selected_test_resolution_failure", evidence
    if "fail" in lowered:
        evidence.append("test_suite_failed")
        return "focused_verifier_failed_uncategorized", evidence
    return "focused_verifier_unknown_nonzero", evidence


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_summary = read_json(DSPY_SUMMARY)
    stderr = DSPY_STDERR.read_text(encoding="utf-8", errors="replace") if DSPY_STDERR.exists() else ""
    failure_class, evidence_markers = classify_failure(stderr)
    summary = {
        "stage": STAGE,
        "decision": "dspy_web_selected_test_admission_blocked_verifier_failure",
        "training_allowed": False,
        "claim_boundary": (
            "Verifier-failure audit only. DSpy is not admitted as train-support, strict eval, Level-3, "
            "patch-trace, repair, or source-heldout data."
        ),
        "source_stage": "stage12335_dspy_web_focused_verifier_executor",
        "focused_verifier_exit_code": source_summary.get("focused_verifier_exit_code"),
        "focused_verifier_passed": source_summary.get("focused_verifier_passed"),
        "failure_class": failure_class,
        "evidence_markers": evidence_markers,
        "stderr_sha256": sha_text(stderr) if stderr else None,
        "stderr_excerpt_no_raw_training_use": stderr[-1600:] if stderr else "",
        "blocked_reasons": [
            "focused_verifier_nonzero",
            failure_class,
            "no_gold_perspective_rows_materialized",
            "anti_cheat_renderer_missing",
            "lineage_audit_missing",
        ],
        "not_admitted_counters": {
            "train_support_rows": 0,
            "strict_eval_rows": 0,
            "level3_rows": 0,
            "patch_trace_rows": 0,
            "repair_rows": 0,
        },
        "recommended_next_actions": [
            "treat DSpy as verifier-recovery/env-config work item, not selected-test support",
            "try next Web candidate only if dependencies already exist and focused verifier can run without repo edits",
            "if DSpy is repaired later, rerun Stage12335 and only then build task-specific anti-cheat rows",
        ],
    }
    (OUT / "dspy_web_verifier_failure_audit.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "DSPY_WEB_VERIFIER_FAILURE_AUDIT_STAGE12337.md").write_text(
        "# Stage12337 DSpy Web Verifier Failure Audit\n\n"
        "DSpy focused verifier failed before row admission. The failure is classified and the row path remains blocked.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
