#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8892
NAME = "stage8892_next_steps_decision_matrix_after_control_plane_regression"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NEXT_STEPS_DECISION_MATRIX_STAGE8892.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = {
    "stage8887_ticket_gate": ROOT / "runs/summaries/stage8887_stage8890_inactive_execution_ticket_gate_audit.json",
    "stage8889_inventory_ticket": ROOT / "runs/summaries/stage8889_metadata_inventory_inactive_ticket_gate.json",
    "stage8891_regression_audit": ROOT / "runs/summaries/stage8891_no_execution_control_plane_regression_audit.json",
}

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

BRANCHES = [
    {
        "branch_id": "A_stage8890_one_run_structured_probe",
        "status": "blocked_on_explicit_user_authorization",
        "purpose": "Run the tiny structured-policy probe candidate only after a fresh live authorization ticket.",
        "allowed_now": False,
        "required_next_stage_before_run": "live_one_run_authorization_ticket_and_pre_execution_check",
        "hard_limits": {
            "mode": "structured_policy_probe",
            "max_train_rows": 32,
            "max_eval_rows": 16,
            "max_strict_rows": 16,
            "max_steps": 8,
            "decoder_ce_weight": 0.0,
            "denoise_weight": 0.0,
            "runtime": False,
        },
        "must_pass_after_run": [
            "native_probe_interpretability_artifact_contract",
            "row_field_logits_nonempty_with_confidence_entropy_topk",
            "row_gradient_norms_nonempty",
            "activation_summary_nonempty",
            "module_delta_norms_decoder_delta_guard",
            "field_exact_by_cell_present",
        ],
    },
    {
        "branch_id": "B_no_execution_hardening",
        "status": "available_now",
        "purpose": "Add more regression tests, docs, and static audits without model execution or data mining.",
        "allowed_now": True,
        "recommended_when": "No explicit live probe authorization has been given.",
    },
    {
        "branch_id": "C_metadata_inventory",
        "status": "closed_inactive_ticket_only",
        "purpose": "Future metadata-only commit inventory, not repository walking or data mining.",
        "allowed_now": False,
        "required_next_stage_before_any_read": "new explicit metadata inventory ticket with caps",
        "current_counts": {
            "repository_walks_now": 0,
            "commit_reads_now": 0,
            "diff_patch_source_body_reads_now": 0,
            "training_rows_now": 0,
        },
    },
    {
        "branch_id": "D_denoise_repair",
        "status": "reviewed_no_execution_only",
        "purpose": "Output-repair denoise is conceptually recovered but CE/runtime remain closed.",
        "allowed_now": False,
        "required_next_stage_before_loss": "separate one-run denoise ticket after structured probe evidence",
    },
    {
        "branch_id": "E_dataset_mining_scaleup",
        "status": "closed",
        "purpose": "Mining / large data recovery / /arxiv walks stay closed until execution and telemetry decisions are made.",
        "allowed_now": False,
    },
]


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> None:
    registry = load(REGISTRY) or {"rows": [], "metrics": {}}
    cards = {name: load(path) for name, path in SOURCES.items()}
    failures: list[str] = []
    for name, path in SOURCES.items():
        card = cards[name]
        if not path.exists():
            failures.append(f"missing_source:{name}")
        elif card.get("passed") is not True:
            failures.append(f"source_failed:{name}")
        elif any((card.get("authority") or {}).values()):
            failures.append(f"source_authority_open:{name}")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    if (registry.get("metrics") or {}).get("latest_stage") not in {8891, STAGE}:
        failures.append(f"unexpected_registry_frontier:{(registry.get('metrics') or {}).get('latest_stage')}")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            "branches": len(BRANCHES),
            "branches_allowed_now": sum(1 for branch in BRANCHES if branch.get("allowed_now") is True),
            "live_probe_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_walk_authorized": False,
            "metadata_inventory_read_authorized": False,
        },
        "decision_matrix": BRANCHES,
        "decision": "Next-step decision matrix recorded. Only no-execution hardening is available without explicit live authorization." if not failures else "Next-step decision matrix failed source/authority checks.",
        "next_best_step": "If the user explicitly says to authorize the tiny Stage8890 structured probe, build a live one-run ticket next. Otherwise continue no-execution hardening or documentation; do not run training/mining.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8892 Next Steps Decision Matrix",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Current state: control plane recovered; Stage8890 is reserved but not authorized.",
        "",
        "Available now:",
        "",
        "- no-execution hardening and documentation",
        "",
        "Not available without explicit future authorization:",
        "",
        "- Stage8890 model execution",
        "- decoder CE",
        "- denoise CE",
        "- runtime/source/body/Gemma/harness/scoring",
        "- `/arxiv` walks, commit reads, data mining, or scale-up",
        "",
        "Stage8890 hard caps if explicitly authorized later: train 32, eval 16, strict 16, max steps 8, structured aux only, decoder CE 0, denoise CE 0, runtime false.",
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
    marker = "## Stage8892 Next Steps Decision Matrix"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8892 records the post-regression-audit branch decision. Without explicit future authorization, only no-execution hardening/documentation is available. Stage8890 remains a reserved tiny structured-policy probe candidate, not a live run.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
