#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8891
NAME = "stage8891_no_execution_control_plane_regression_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NO_EXECUTION_CONTROL_PLANE_REGRESSION_AUDIT_STAGE8891.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"

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

REQUIRED_TESTS = {
    "tests/test_stage888x_inactive_authority_tickets.py": [
        "test_stage8890_inactive_ticket_cannot_execute_or_train",
        "test_metadata_inventory_inactive_ticket_reads_nothing_and_protects_arxiv",
        "test_stage8889_summary_and_registry_frontier_remains_closed",
    ],
    "tests/test_native_probe_preflight_gate.py": [
        "denoise_ce_training_authorized_next",
        "test_preflight_accepts_closed_tiny_structured_plan",
        "test_preflight_rejects_decoder_weight_for_structured_mode",
    ],
    "tests/test_safe_cleanup.py": [
        "test_refuses_arxiv_as_cleanup_output",
        "test_refuses_repo_root",
        "test_refuses_parent_of_output_dir",
    ],
    "tests/test_authority_ticket_schema_builder.py": [
        "allowed_operations",
        "denied_operations",
    ],
    "tests/test_authority_ticket_schema_gate_audit.py": [
        "compute_decoder_ce",
        "compute_denoise_ce",
    ],
}

SOURCE_SUMMARIES = [
    ROOT / "runs/summaries/stage8887_stage8890_inactive_execution_ticket_gate_audit.json",
    ROOT / "runs/summaries/stage8889_metadata_inventory_inactive_ticket_gate.json",
]


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def text_contains(path: Path, needles: list[str]) -> tuple[bool, list[str]]:
    if not path.exists():
        return False, needles
    text = path.read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    return not missing, missing


def main() -> None:
    registry = load(REGISTRY) or {"rows": [], "metrics": {}}
    summaries = [load(path) for path in SOURCE_SUMMARIES]
    failures: list[str] = []
    test_checks = []
    for rel, needles in REQUIRED_TESTS.items():
        ok, missing = text_contains(ROOT / rel, needles)
        test_checks.append({"test_file": rel, "passed": ok, "missing_markers": missing})
        if not ok:
            failures.append(f"missing_test_markers:{rel}:{','.join(missing)}")
    for path, summary in zip(SOURCE_SUMMARIES, summaries):
        if not path.exists():
            failures.append(f"missing_summary:{path}")
        elif summary.get("passed") is not True:
            failures.append(f"failed_summary:{summary.get('stage_name')}")
        elif any((summary.get("authority") or {}).values()):
            failures.append(f"authority_open:{summary.get('stage_name')}")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    if "denoise_ce_training_authorized_next" not in authority_counts:
        failures.append("registry_missing_denoise_authority_count")
    latest_stage = (registry.get("metrics") or {}).get("latest_stage")
    if latest_stage not in {8889, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest_stage}")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            "required_test_files": len(REQUIRED_TESTS),
            "test_files_with_required_markers": sum(1 for check in test_checks if check["passed"]),
            "source_summaries_checked": len(SOURCE_SUMMARIES),
            "registry_latest_stage_before_update": latest_stage,
            "registry_has_denoise_authority_count": "denoise_ce_training_authorized_next" in authority_counts,
            "registry_authority_counts_zero": not any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED),
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
        },
        "test_checks": test_checks,
        "source_summaries": [str(path.relative_to(ROOT)) for path in SOURCE_SUMMARIES],
        "decision": "No-execution control-plane regression audit passed. Inactive tickets, cleanup guards, native preflight, and authority schema are now protected by tests." if not failures else "No-execution control-plane regression audit failed.",
        "next_best_step": "Stage8890 remains reserved for explicit future one-run structured probe authorization. Without that authorization, continue only no-execution hardening or documentation.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8891 No-Execution Control-Plane Regression Audit",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage records regression coverage for the recovered no-execution control plane.",
        "",
        "Covered guard files:",
        "",
        *[f"- `{rel}`" for rel in REQUIRED_TESTS],
        "",
        "It does not run a model, authorize training, walk `/arxiv`, read commits, open decoder CE, open denoise CE, execute runtime, call Gemma/harness/scoring, export checkpoints, or promote.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": card["passed"],
        "path": str(SUMMARY),
        "authority": AUTHORITY_CLOSED,
        "next_best_step": card["next_best_step"],
    })
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {
        **registry.get("metrics", {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": card["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8891 No-Execution Control-Plane Regression Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8891 records that the recovered authority tickets, metadata-inventory ticket, native probe preflight, cleanup guard, and authority-ticket schema are covered by regression tests. It keeps Stage8890 reserved and opens no execution/training authority.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
