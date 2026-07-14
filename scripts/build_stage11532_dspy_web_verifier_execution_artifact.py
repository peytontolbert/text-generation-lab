#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11532
NAME = "stage11532_dspy_web_verifier_execution_artifact"
OUT = ART / NAME
SUMMARY = OUT / "dspy_web_verifier_execution_artifact.json"
PACKET = OUT / "dspy_web_verifier_execution_packet.json"
ROW_SHELLS = OUT / "dspy_web_verifier_execution_row_shells.jsonl"

STAGE11530_PACKETS = ART / "stage11530_web_new_family_materialization_packets/web_new_family_root_packets.jsonl"
RAW_LOG_DIR = ART / "stage11532_dspy_web_verifier_execution/logs"
NPM_CI_LOG = RAW_LOG_DIR / "npm_ci.log"
APP_TEST_LOG = RAW_LOG_DIR / "app_test.log"

PERSPECTIVES = [
    "symptom_localization",
    "evidence_citation",
    "verifier_outcome",
    "patch_impact",
    "minimal_fix_selection",
    "abstention_insufficient_evidence",
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def source_snippet(path: Path, max_lines: int = 80) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "text": ""}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"path": str(path), "exists": True, "line_start": 1, "line_end": min(max_lines, len(lines)), "text": "\n".join(lines[:max_lines])}


def dspy_packet() -> dict[str, Any]:
    base = next((row for row in load_jsonl(STAGE11530_PACKETS) if row.get("git_repo_family") == "dspy"), {})
    repo = Path(str(base.get("repo_path") or "/data/repositories/dspy/inspect-app/react-app"))
    log = read_text(APP_TEST_LOG)
    npm_log = read_text(NPM_CI_LOG)
    inferred_paths = [
        "src/components/display/display.js",
        "src/App.js",
        "src/App.test.js",
        "package.json",
        "package-lock.json",
    ]
    options = [
        {
            "label": "A",
            "semantic_role": "candidate_change_surface",
            "path": "src/components/display/display.js",
            "description": "Component imports axios; verifier fails before assertions while transforming this dependency import chain.",
        },
        {
            "label": "B",
            "semantic_role": "entrypoint_or_invocation_surface",
            "path": "src/App.js",
            "description": "Application entry component imports the display component and appears in the failure stack.",
        },
        {
            "label": "C",
            "semantic_role": "verifier_and_test_constraint",
            "path": "src/App.test.js",
            "description": "Selected focused verifier test that failed to execute assertions.",
        },
        {
            "label": "D",
            "semantic_role": "dependency_or_test_environment_surface",
            "path": "package.json",
            "description": "Package/test environment configuration controlling Jest, react-scripts, and axios dependency behavior.",
        },
        {
            "label": "E",
            "semantic_role": "abstain_insufficient_evidence",
            "path": None,
            "description": "Visible evidence is insufficient to choose one repair target without more environment or maintainer intent.",
        },
    ]
    return {
        "root_id": "stage11532::dspy::react_app::axios_jest_esm_verifier_failure",
        "parent_root_id": base.get("root_id"),
        "language_family": "web_js_ts_html",
        "repo_family": "react_app",
        "git_repo_family": "dspy",
        "repo_path": str(repo),
        "git_head": base.get("git_head"),
        "verifier_execution": {
            "dependency_hydration_command": "npm ci --cache /data/tmp/npm-cache-stage11532 --prefer-offline --no-audit --no-fund",
            "dependency_hydration_exit_code": 0 if "added " in npm_log else None,
            "focused_verifier_command": "CI=true npm test -- --watchAll=false src/App.test.js",
            "focused_verifier_exit_code": 1,
            "observed_transition": "TEST_SUITE_FAILED_BEFORE_ASSERTIONS",
            "failure_signature": "Jest cannot parse axios/index.js ESM import: Cannot use import statement outside a module.",
            "raw_log_excerpt": log[:4000],
            "log_artifacts": {"npm_ci": rel(NPM_CI_LOG), "focused_test": rel(APP_TEST_LOG)},
        },
        "candidate_options": options,
        "source_snippets": {path: source_snippet(repo / path) for path in inferred_paths},
        "admission_status": "executed_verifier_materialized_pending_gold_adjudication",
        "trainable_now": False,
        "strict_eval_eligible_now": False,
        "missing_for_train_admission": [
            "gold_perspective_answers",
            "anti_cheat_decision",
            "root_split_assignment",
            "maintainer_decision_on_whether_this_is_dependency_config_or_component_surface",
        ],
        "anti_cheat_precheck": {
            "verifier_output_attached": True,
            "target_label_not_assigned_yet": True,
            "opaque_option_labels_prepared": True,
            "do_not_train_until_gold": True,
        },
    }


def make_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    options_text = "\n".join(
        f"option {opt['label']}: {opt['semantic_role']} :: {opt.get('path') or 'ABSTAIN'}"
        for opt in packet["candidate_options"]
    )
    snippet_text = "\n\n".join(
        f"Snippet {idx + 1}: {path}\n{card.get('text', '')[:1200]}"
        for idx, (path, card) in enumerate(packet["source_snippets"].items())
        if card.get("exists")
    )
    verifier = packet["verifier_execution"]
    prompt_common = (
        f"Repository family: {packet['git_repo_family']}\n"
        f"Focused verifier command: {verifier['focused_verifier_command']}\n"
        f"Observed verifier transition: {verifier['observed_transition']}\n"
        f"Failure signature: {verifier['failure_signature']}\n\n"
        f"Visible snippets:\n{snippet_text}\n\n"
        f"Options:\n{options_text}\n"
    )
    rows = []
    for perspective in PERSPECTIVES:
        rows.append(
            {
                "row_id": f"{packet['root_id']}::{perspective}",
                "root_id": packet["root_id"],
                "language_family": packet["language_family"],
                "task_type": perspective,
                "input_text": f"Task: {perspective}. Use the verifier evidence and snippets only.\n\n{prompt_common}",
                "opaque_options": packet["candidate_options"],
                "bounded_choice_target_label": None,
                "semantic_target_value": None,
                "target_status": "pending_gold_adjudication",
                "strict_eval_eligible": False,
                "train_support_only": False,
                "admission_status": "executed_row_shell_pending_gold",
                "anti_cheat": {
                    "executed_verifier_output_attached": True,
                    "target_not_assigned": True,
                    "target_label_not_visible_before_options": True,
                    "do_not_score_or_train": True,
                },
            }
        )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    packet = dspy_packet()
    rows = make_rows(packet)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "dspy_web_verifier_execution_materialized_pending_gold",
        "counts": {
            "root_packets": 1,
            "row_shells": len(rows),
            "train_ready_rows": 0,
            "strict_eval_ready_rows": 0,
        },
        "verifier_execution": packet["verifier_execution"],
        "admission": {
            "trainable_now": False,
            "strict_eval_eligible_now": False,
            "why": "The focused verifier was executed and failed before assertions, but gold maintainer perspective answers and anti-cheat signoff are not complete.",
        },
        "next_actions": [
            "Adjudicate whether this root should be a verifier-failure routing row, dependency/test-environment row, or be excluded as environment-only.",
            "If admitted, assign gold answers for all six perspective shells and run prompt-target leak audit.",
            "Do not use this row as evidence of product-behavior localization until maintainer adjudication confirms answerability.",
        ],
        "source_artifacts": {"stage11530_packets": rel(STAGE11530_PACKETS), "npm_ci_log": rel(NPM_CI_LOG), "app_test_log": rel(APP_TEST_LOG)},
        "outputs": {"summary": rel(SUMMARY), "packet": rel(PACKET), "row_shells": rel(ROW_SHELLS)},
    }
    write_json(PACKET, packet)
    write_jsonl(ROW_SHELLS, rows)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
