#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12334_web_verifier_recovery_request"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
QUEUE = ROOT / "runs/local/artifacts/stage12330_selected_test_language_balance_queue/web_selected_test_hydration_queue.jsonl"


def read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    queue = read_jsonl(QUEUE)
    requests = []
    for item in queue:
        repo = item.get("repo_family")
        repo_path = Path(item.get("repo_path") or "")
        command = None
        priority = 99
        blocked = list(item.get("blocked_reasons") or [])
        if repo == "dspy":
            priority = 1
            command = "CI=true npm test -- --watchAll=false src/App.test.js"
            blocked = [b for b in blocked if b not in {"observed_verifier_transition", "selected_verifier_path"}]
            blocked.extend(["needs_no_network_execution_check", "needs_log_capture", "needs_source_test_hash_capture"])
        elif repo == "ai_town":
            priority = 2
            command = "repo_root_resolution_required_before_command"
            blocked.extend(["repo_path_inside_convex_missing_package_json", "needs_repo_root_resolution"])
        elif repo == "openclaw_clawhub":
            priority = 3
            command = "bunx_or_bun_vitest_after_bun_runtime_available"
            blocked.extend(["missing_bun_executable", "repo_dependencies_not_installed"])
        elif repo == "openclaw_openclaw":
            priority = 4
            command = "npm exec -- vitest run src/model-switch-eval.test.ts after dependency repair"
            blocked.extend(["pnpm_corepack_dynamic_import_failure", "repo_dependencies_not_installed"])
        requests.append({
            "stage": STAGE,
            "record_type": "web_focused_verifier_recovery_request",
            "review_item_id": item.get("review_item_id"),
            "repo_family": repo,
            "subrepo_family": item.get("subrepo_family"),
            "repo_path": str(repo_path),
            "priority_rank": priority,
            "proposed_focused_verifier_command": command,
            "expected_rows_if_hydrated": item.get("expected_rows_if_hydrated"),
            "training_allowed": False,
            "train_support_admitted": False,
            "blocked_reasons": sorted(set(blocked)),
            "required_qc_fields_before_admission": [
                "focused_verifier_command",
                "focused_verifier_cwd",
                "focused_verifier_exit_code",
                "focused_verifier_output_artifact_hash",
                "selected_verifier_path",
                "selected_changed_path",
                "selected_symptom_or_call_path_evidence",
                "source_hash_refs",
                "test_hash_refs",
                "anti_cheat_decision",
                "target_label_value_not_visible_before_options",
                "deterministic_option_shuffle",
                "root_split_assignment",
            ],
        })
    requests.sort(key=lambda row: row["priority_rank"])
    write_jsonl(OUT / "web_focused_verifier_recovery_requests.jsonl", requests)
    summary = {
        "stage": STAGE,
        "decision": "web_focused_verifier_recovery_request_ready_training_still_blocked",
        "training_allowed": False,
        "claim_boundary": "Request/control artifact only. No web rows admitted. DSpy is the first no-install verifier recovery target; OpenClaw remains dependency/runtime blocked.",
        "request_count": len(requests),
        "priority_order": [row.get("repo_family") for row in requests],
        "first_target": requests[0] if requests else None,
        "next_stage": "stage12335_dspy_web_focused_verifier_executor_if_no_network_or_install_needed",
    }
    (OUT / "web_verifier_recovery_request_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "WEB_VERIFIER_RECOVERY_REQUEST_STAGE12334.md").write_text(
        "# Stage12334 Web Verifier Recovery Request\n\nDSpy/react-app is the first focused verifier recovery target. This stage admits zero rows.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
