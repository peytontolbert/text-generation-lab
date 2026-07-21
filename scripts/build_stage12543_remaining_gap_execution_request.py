#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12543_remaining_gap_execution_request"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12542_SUMMARY = ROOT / "runs/summaries/stage12542_remaining_command_output_gap_feasibility_audit.json"
STAGE12209_COMMAND_LOGS = ROOT / "runs/local/artifacts/stage12209_command_log_candidate_scanner/clean_candidate_command_logs.jsonl"

WORK_ITEMS_NAME = "stage12543_remaining_gap_execution_work_items.jsonl"
RUNBOOK_NAME = "stage12543_executor_runbook.json"
AUDIT_NAME = "stage12543_execution_request_audit.json"


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                value["__line_no"] = line_no
                rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def risky_claims_false() -> dict[str, Any]:
    return {
        "training_allowed": False,
        "countable_train_support": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "level4_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
    }


def repo_leads_from_stage12209() -> dict[str, dict[str, Any]]:
    leads: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(STAGE12209_COMMAND_LOGS):
        repo = str(row.get("repo_family") or "")
        if not repo or repo.startswith("stage"):
            continue
        existing = leads.setdefault(
            repo,
            {
                "repo_family_hash": stable_hash(repo),
                "language_family": row.get("language") or "unknown",
                "source_log_line_hashes": [],
                "observed_status_counts": {},
            },
        )
        existing["source_log_line_hashes"].append(stable_hash({"line": row.get("__line_no"), "repo": repo}))
        status = str(row.get("status") or "unknown")
        existing["observed_status_counts"][status] = existing["observed_status_counts"].get(status, 0) + 1
    return leads


def work_item(
    *,
    priority: int,
    target_status: str,
    repo_family: str,
    language_family: str,
    execution_intent: str,
    verifier_scope: str,
    expected_acceptance_signal: str,
    reject_if: list[str],
    source_log_line_hashes: list[str],
) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "record_type": "stage12543_remaining_gap_execution_work_item_v1",
        "work_item_id": stable_hash({"target": target_status, "repo": repo_family, "intent": execution_intent}),
        "priority": priority,
        "target_status_needed": target_status,
        "repo_family_hash": stable_hash(repo_family),
        "language_family": language_family,
        "source_adapter_family": "locally_hydratable_repo_broad_verifier_command_execution",
        "execution_intent_class": execution_intent,
        "verifier_scope_required": verifier_scope,
        "selected_or_exact_test_scope_allowed": False,
        "controlled_fixture_like_allowed": False,
        "stage_synthetic_repo_family_allowed": False,
        "projection_or_transition_derived_label_allowed": False,
        "raw_command_to_be_filled_by_private_executor": True,
        "raw_output_to_be_hashed_not_rendered": True,
        "expected_acceptance_signal": expected_acceptance_signal,
        "reject_if": reject_if,
        "source_log_line_hashes": source_log_line_hashes[:8],
        "candidate_row_emitted": False,
        **risky_claims_false(),
    }


def build_work_items() -> list[dict[str, Any]]:
    leads = repo_leads_from_stage12209()
    items: list[dict[str, Any]] = []
    priority = 1
    # The FAIL item must be broad behavioral/build failure, not a missing file or dependency/env failure.
    for repo in ["pytest-dev/pluggy", "BurntSushi/byteorder", "rust-cli/env_logger"]:
        lead = leads.get(repo, {"language_family": "unknown", "source_log_line_hashes": []})
        items.append(
            work_item(
                priority=priority,
                target_status="FAIL_CURRENT_STATE",
                repo_family=repo,
                language_family=str(lead.get("language_family") or "unknown"),
                execution_intent="broad_behavioral_or_build_verifier_failure_discovery",
                verifier_scope="broad_repo_or_package_verifier_not_selected_test_not_exact_filter",
                expected_acceptance_signal="nonzero verifier result caused by behavioral test failure or build/typecheck failure in repo code, not environment setup",
                reject_if=[
                    "missing_file_or_invalid_path",
                    "offline_dependency_resolution_failure",
                    "module_import_environment_failure",
                    "timeout_or_network_failure",
                    "selected_or_exact_test_filter",
                    "stage_synthetic_or_fixture_source",
                ],
                source_log_line_hashes=list(lead.get("source_log_line_hashes", [])),
            )
        )
        priority += 1
    # The INSUFFICIENT item needs one more non-selected zero-test/no-test observation beyond Stage12541.
    for repo in ["Neargye/magic_enum", "fastfloat/fast_float", "Tencent/rapidjson"]:
        lead = leads.get(repo, {"language_family": "c_cpp", "source_log_line_hashes": []})
        items.append(
            work_item(
                priority=priority,
                target_status="INSUFFICIENT_EVIDENCE",
                repo_family=repo,
                language_family=str(lead.get("language_family") or "c_cpp"),
                execution_intent="broad_zero_test_or_no_test_verifier_observation_discovery",
                verifier_scope="broad_discovery_or_list_command_not_selected_test_not_exact_filter",
                expected_acceptance_signal="exit-zero command output proves zero tests discovered or no runnable verifier evidence for current target scope",
                reject_if=[
                    "selected_or_exact_test_filter",
                    "duplicate_output_hash_of_stage12541",
                    "fixture_or_stage_synthetic_source",
                    "raw_log_not_hashable",
                    "command_result_without_source_identity",
                ],
                source_log_line_hashes=list(lead.get("source_log_line_hashes", [])),
            )
        )
        priority += 1
    return items


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12542 = read_json(STAGE12542_SUMMARY)
    work_items = build_work_items()
    work_items_path = OUT / WORK_ITEMS_NAME
    runbook_path = OUT / RUNBOOK_NAME
    audit_path = OUT / AUDIT_NAME
    write_jsonl(work_items_path, work_items)

    target_counts: dict[str, int] = {}
    for item in work_items:
        target = item["target_status_needed"]
        target_counts[target] = target_counts.get(target, 0) + 1

    runbook = {
        "stage": STAGE,
        "record_type": "stage12543_executor_runbook_v1",
        "decision": "execution_request_only_training_blocked",
        "executor_output_contract": {
            "required_private_fields": [
                "repo_root",
                "commit_sha_or_checkout_identity",
                "raw_command",
                "cwd",
                "returncode",
                "stdout",
                "stderr",
                "started_at_utc",
                "finished_at_utc",
            ],
            "required_public_return_fields": [
                "work_item_id",
                "repo_family_hash",
                "language_family",
                "target_status_candidate",
                "verifier_exit_status_class",
                "verifier_stdout_hash",
                "verifier_stderr_hash",
                "verifier_output_hash",
                "command_observation_join_hash",
                "semantic_acceptance_or_blocker_reason",
            ],
            "raw_content_public_return_allowed": False,
        },
        "acceptance_requires": [
            "same-source command/result/output/status provenance",
            "non-selected broad verifier scope",
            "non-fixture non-stage-synthetic repo family",
            "FAIL_CURRENT_STATE must be behavioral/build failure, not env/invalid command",
            "INSUFFICIENT_EVIDENCE must be zero-test/no-test or missing-verifier proof, not PASS bulk",
            "duplicate output collapse against Stage12541 and same batch",
        ],
        **risky_claims_false(),
    }
    write_json(runbook_path, runbook)

    audit = {
        "stage": STAGE,
        "record_type": "stage12543_execution_request_audit_v1",
        "input_hashes": {
            "stage12542_summary": file_hash(STAGE12542_SUMMARY),
            "stage12209_clean_command_logs": file_hash(STAGE12209_COMMAND_LOGS),
        },
        "stage12542_remaining_shortfall": stage12542.get("remaining_shortfall_after_stage12542"),
        "work_item_count": len(work_items),
        "target_status_work_item_counts": target_counts,
        "candidate_rows_emitted": 0,
        "raw_public_content_emitted": False,
        **risky_claims_false(),
    }
    write_json(audit_path, audit)

    summary = {
        "stage": STAGE,
        "record_type": "stage12543_remaining_gap_execution_request_summary_v1",
        "decision": "execution_request_only_no_rows_admitted",
        "claim_boundary": "Stage12543 emits hash-only work items for private execution/source acquisition. It emits no verifier-observation preflight rows, countable support, training rows, Level3 rows, patch traces, repair claims, or model-progress claims.",
        "stage12542_remaining_shortfall": stage12542.get("remaining_shortfall_after_stage12542"),
        "work_item_count": len(work_items),
        "target_status_work_item_counts": target_counts,
        "new_preflight_row_count": 0,
        "new_countable_train_support_count": 0,
        "raw_public_content_emitted": False,
        **risky_claims_false(),
        "artifact_refs": {
            "work_items": str(work_items_path.relative_to(ROOT)),
            "runbook": str(runbook_path.relative_to(ROOT)),
            "audit": str(audit_path.relative_to(ROOT)),
            "summary": str(SUMMARY.relative_to(ROOT)),
        },
    }
    write_json(SUMMARY, summary)
    return summary


if __name__ == "__main__":
    build()
