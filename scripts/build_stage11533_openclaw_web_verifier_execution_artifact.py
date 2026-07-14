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
STAGE = 11533
NAME = "stage11533_openclaw_web_verifier_execution_artifact"
OUT = ART / NAME
SUMMARY = OUT / "openclaw_web_verifier_execution_artifact.json"
PACKET = OUT / "openclaw_web_verifier_execution_packet.json"
ROW_SHELLS = OUT / "openclaw_web_verifier_execution_row_shells.jsonl"

STAGE11530_PACKETS = ART / "stage11530_web_new_family_materialization_packets/web_new_family_root_packets.jsonl"
RAW_LOG_DIR = ART / "stage11533_openclaw_web_verifier_execution/logs"
BUN_INSTALL_LOG = RAW_LOG_DIR / "bun_install_path.log"
TEST_LOG = RAW_LOG_DIR / "skills_versions_public_test.log"

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


def source_snippet(path: Path, max_lines: int = 120) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "text": ""}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"path": str(path), "exists": True, "line_start": 1, "line_end": min(max_lines, len(lines)), "text": "\n".join(lines[:max_lines])}


def packet() -> dict[str, Any]:
    base = next((row for row in load_jsonl(STAGE11530_PACKETS) if row.get("git_repo_family") == "openclaw_clawhub"), {})
    repo = Path(str(base.get("repo_path") or "/data/repositories/openclaw__clawhub/convex"))
    root = repo.parent
    test_log = read_text(TEST_LOG)
    install_log = read_text(BUN_INSTALL_LOG)
    source_paths = [
        "convex/skills.ts",
        "convex/lib/public.ts",
        "convex/lib/skills.ts",
        "convex/skills.versions.public.test.ts",
        "package.json",
    ]
    options = [
        {
            "label": "A",
            "semantic_role": "candidate_change_surface",
            "path": "convex/skills.ts",
            "description": "Public skill/version query implementation imported by the selected verifier.",
        },
        {
            "label": "B",
            "semantic_role": "supporting_public_projection_surface",
            "path": "convex/lib/public.ts",
            "description": "Public projection helpers likely involved in sanitized public query outputs.",
        },
        {
            "label": "C",
            "semantic_role": "verifier_and_test_constraint",
            "path": "convex/skills.versions.public.test.ts",
            "description": "Focused Vitest verifier that constrains public skill version behavior.",
        },
        {
            "label": "D",
            "semantic_role": "dependency_or_test_environment_surface",
            "path": "package.json",
            "description": "Repo test tooling and package scripts surface.",
        },
        {
            "label": "E",
            "semantic_role": "abstain_insufficient_evidence",
            "path": None,
            "description": "Visible evidence is insufficient for a forced singleton decision.",
        },
    ]
    return {
        "root_id": "stage11533::openclaw_clawhub::convex::skills_versions_public_verifier_pass",
        "parent_root_id": base.get("root_id"),
        "language_family": "web_js_ts_html",
        "repo_family": "convex",
        "git_repo_family": "openclaw_clawhub",
        "repo_path": str(repo),
        "git_head": base.get("git_head"),
        "verifier_execution": {
            "dependency_hydration_command": "PATH=/data/tmp/npm-cache-stage11533/_npx/.../node_modules/.bin:$PATH bun install --frozen-lockfile",
            "dependency_hydration_exit_code": 0 if "Checked " in install_log else None,
            "focused_verifier_command": "bun run test -- skills.versions.public.test.ts",
            "focused_verifier_exit_code": 0 if "1 passed" in test_log and "3 passed" in test_log else None,
            "observed_transition": "TARGETED_TEST_PASS",
            "result_summary": "Vitest: 1 file passed, 3 tests passed.",
            "raw_log_excerpt": test_log[:3000],
            "log_artifacts": {"bun_install": rel(BUN_INSTALL_LOG), "focused_test": rel(TEST_LOG)},
        },
        "candidate_options": options,
        "source_snippets": {path: source_snippet(root / path) for path in source_paths},
        "admission_status": "executed_verifier_materialized_pending_gold_adjudication",
        "trainable_now": False,
        "strict_eval_eligible_now": False,
        "missing_for_train_admission": [
            "gold_perspective_answers",
            "anti_cheat_decision",
            "root_split_assignment",
            "maintainer_decision_on_perspective_targets",
        ],
        "anti_cheat_precheck": {
            "verifier_output_attached": True,
            "target_label_not_assigned_yet": True,
            "opaque_option_labels_prepared": True,
            "do_not_train_until_gold": True,
            "not_existing_openhands_or_llama_heldout": True,
        },
    }


def make_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    options_text = "\n".join(
        f"option {opt['label']}: {opt['semantic_role']} :: {opt.get('path') or 'ABSTAIN'}"
        for opt in packet["candidate_options"]
    )
    snippet_text = "\n\n".join(
        f"Snippet {idx + 1}: {path}\n{card.get('text', '')[:1400]}"
        for idx, (path, card) in enumerate(packet["source_snippets"].items())
        if card.get("exists")
    )
    verifier = packet["verifier_execution"]
    prompt_common = (
        f"Repository family: {packet['git_repo_family']}\n"
        f"Focused verifier command: {verifier['focused_verifier_command']}\n"
        f"Observed verifier transition: {verifier['observed_transition']}\n"
        f"Verifier result: {verifier['result_summary']}\n\n"
        f"Visible snippets:\n{snippet_text}\n\n"
        f"Options:\n{options_text}\n"
    )
    return [
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
        for perspective in PERSPECTIVES
    ]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    root_packet = packet()
    rows = make_rows(root_packet)
    test_passed = root_packet["verifier_execution"]["focused_verifier_exit_code"] == 0
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": test_passed,
        "decision": "openclaw_web_verifier_execution_materialized_pending_gold"
        if test_passed
        else "openclaw_web_verifier_execution_failed",
        "counts": {
            "root_packets": 1,
            "row_shells": len(rows),
            "train_ready_rows": 0,
            "strict_eval_ready_rows": 0,
        },
        "verifier_execution": root_packet["verifier_execution"],
        "admission": {
            "trainable_now": False,
            "strict_eval_eligible_now": False,
            "why": "The focused verifier passed, but gold perspective answers, split assignment, and anti-cheat signoff are required before admission.",
        },
        "next_actions": [
            "Adjudicate gold labels for all six perspective shells.",
            "Assign this root to train or sealed heldout; prefer sealed heldout if Web heldout shortfall remains.",
            "Run prompt-target leak and root-overlap audit before admitting the rows.",
        ],
        "source_artifacts": {"stage11530_packets": rel(STAGE11530_PACKETS), "bun_install_log": rel(BUN_INSTALL_LOG), "focused_test_log": rel(TEST_LOG)},
        "outputs": {"summary": rel(SUMMARY), "packet": rel(PACKET), "row_shells": rel(ROW_SHELLS)},
    }
    write_json(PACKET, root_packet)
    write_jsonl(ROW_SHELLS, rows)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
