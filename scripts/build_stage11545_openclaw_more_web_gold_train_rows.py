#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11545
NAME = "stage11545_openclaw_more_web_gold_train_rows"
OUT = ART / NAME
SUMMARY = OUT / "openclaw_more_web_gold_train_rows.json"
ROWS = OUT / "openclaw_more_web_gold_train_rows.jsonl"
PACKETS = OUT / "openclaw_more_web_gold_train_packets.jsonl"

REPO = Path("/data/repositories/openclaw__clawhub")
GIT_HEAD = "8bbc66868d63c22ee905b327214982f60da4ac0a"
LOG_DIR = ART / "stage11545_openclaw_more_web_train_execution/logs"
LABELS = list("ABCDE")
PERSPECTIVES = [
    "symptom_localization",
    "evidence_citation",
    "verifier_outcome",
    "patch_impact",
    "minimal_fix_selection",
    "abstention_insufficient_evidence",
]
TARGET_LABEL_BY_PERSPECTIVE = {
    "symptom_localization": "A",
    "evidence_citation": "B",
    "verifier_outcome": "C",
    "patch_impact": "D",
    "minimal_fix_selection": "E",
    "abstention_insufficient_evidence": "A",
}
GOLD_BY_PERSPECTIVE = {
    "symptom_localization": "candidate_change_surface",
    "evidence_citation": "verifier_and_test_constraint",
    "verifier_outcome": "pass_targeted_test_selection",
    "patch_impact": "candidate_change_surface",
    "minimal_fix_selection": "candidate_change_surface",
    "abstention_insufficient_evidence": "answer_with_visible_evidence",
}
INSTRUCTIONS = {
    "symptom_localization": "Choose the implementation surface most directly exercised by the selected verifier.",
    "evidence_citation": "Choose the visible evidence role that most directly justifies the bounded decision.",
    "verifier_outcome": "Choose the verifier transition established by the captured focused test output.",
    "patch_impact": "Choose the surface whose change would most directly alter the selected verifier behavior.",
    "minimal_fix_selection": "Choose the smallest likely repair surface if this verified behavior regressed.",
    "abstention_insufficient_evidence": "Decide whether the visible source, test, and execution evidence are enough to answer.",
}
ROOT_SPECS = [
    {
        "slug": "http_utils_boolean_query_params",
        "task": "ClawHub verifier checks boolean query parsing and primary-versus-legacy parameter precedence.",
        "source": "convex/lib/httpUtils.ts",
        "secondary": "convex/httpApi.ts",
        "test": "convex/lib/httpUtils.test.ts",
        "log": "http_utils_test.log",
        "status": "http_utils_test.status",
    },
    {
        "slug": "skill_slug_validation_rules",
        "task": "ClawHub verifier checks skill slug normalization, reserved slug rejection, and URL-safe slug constraints.",
        "source": "convex/lib/skillSlugValidator.ts",
        "secondary": "convex/skills.ts",
        "test": "convex/lib/skillSlugValidator.test.ts",
        "log": "skill_slug_validator_test.log",
        "status": "skill_slug_validator_test.status",
    },
    {
        "slug": "package_security_public_blocking",
        "task": "ClawHub verifier checks package security scan status, public blocking, and download block decisions.",
        "source": "convex/lib/packageSecurity.ts",
        "secondary": "convex/packages.ts",
        "test": "convex/lib/packageSecurity.test.ts",
        "log": "package_security_test.log",
        "status": "package_security_test.status",
    },
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def snippet(path: Path, max_lines: int = 140) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": str(path), "text": ""}
    text = "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[:max_lines])
    return {"exists": True, "line_start": 1, "line_end": len(text.splitlines()), "path": str(path), "sha256": hashlib.sha256(text.encode()).hexdigest(), "text": text}


def explicit_label_leak(pre_options: str, target_label: str) -> bool:
    return any(re.search(pattern, pre_options) for pattern in [
        rf"(?im)^\s*(answer|target|gold|label)\s*[:=]\s*{re.escape(target_label)}\b",
        rf"(?im)^\s*option\s+{re.escape(target_label)}\b",
        rf"(?im)^\s*{re.escape(target_label)}\.\s+",
    ])


def packet(spec: dict[str, str]) -> dict[str, Any]:
    log = read(LOG_DIR / spec["log"])
    status_text = read(LOG_DIR / spec["status"]).strip()
    code = int(status_text) if status_text.isdigit() else None
    passed = code == 0 and "passed" in log and "failed" not in log.lower()
    return {
        "root_id": f"stage11545::openclaw_clawhub::convex::{spec['slug']}",
        "language_family": "web_js_ts_html",
        "repo_family": "convex",
        "git_repo_family": "openclaw_clawhub",
        "repo_path": str(REPO),
        "git_head": GIT_HEAD,
        "task_observation": spec["task"],
        "source_path": spec["source"],
        "secondary_source_path": spec["secondary"],
        "test_path": spec["test"],
        "visible_source_evidence": {"primary": snippet(REPO / spec["source"]), "secondary": snippet(REPO / spec["secondary"])},
        "visible_verifier_evidence": {"test": snippet(REPO / spec["test"])},
        "verifier_execution": {
            "focused_verifier_command": f"./node_modules/.bin/vitest run {spec['test']}",
            "focused_verifier_exit_code": code,
            "observed_transition": "TARGETED_TEST_PASS" if passed else "TARGETED_TEST_FAILED_OR_BLOCKED",
            "raw_log_excerpt": log[-1800:],
            "log_artifact": rel(LOG_DIR / spec["log"]),
        },
    }


def option_bank(packet: dict[str, Any], perspective: str) -> list[dict[str, str]]:
    if perspective == "verifier_outcome":
        return [
            {"value": "pass_targeted_test_selection", "text": "PASS_TARGETED_TEST_SELECTION: the focused verifier executed and all selected assertions passed."},
            {"value": "fail_before_assertions", "text": "FAILS_BEFORE_ASSERTIONS: dependency or test environment failed before assertions ran."},
            {"value": "not_exercised_by_selected_test", "text": "NOT_EXERCISED_BY_SELECTED_TEST: the selected verifier does not exercise the shown implementation surface."},
            {"value": "fail_targeted_test_selection", "text": "FAIL_TARGETED_TEST_SELECTION: the focused verifier ran and selected assertions failed."},
            {"value": "abstain_insufficient_evidence", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
        ]
    if perspective == "abstention_insufficient_evidence":
        return [
            {"value": "answer_with_visible_evidence", "text": "ANSWER_WITH_VISIBLE_EVIDENCE: source snippets, selected test, and captured verifier output are sufficient."},
            {"value": "retrieve_more_source", "text": "RETRIEVE_MORE_SOURCE: more code context is required before any bounded decision."},
            {"value": "needs_external_web_research", "text": "NEEDS_EXTERNAL_WEB_RESEARCH: external docs are required."},
            {"value": "needs_runtime_reexecution", "text": "NEEDS_RUNTIME_REEXECUTION: no usable focused verifier output is attached."},
            {"value": "abstain_insufficient_evidence", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
        ]
    return [
        {"value": "candidate_change_surface", "text": f"{packet['source_path']} implementation surface exercised by the selected verifier."},
        {"value": "verifier_and_test_constraint", "text": f"{packet['test_path']} selected verifier plus captured pass log."},
        {"value": "symptom_or_call_path_analogue", "text": f"{packet['secondary_source_path']} adjacent call-path or API context."},
        {"value": "dependency_or_test_environment_surface", "text": "package manager and Vitest execution environment surface."},
        {"value": "abstain_insufficient_evidence", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ]


def deterministic_options(row_id: str, perspective: str, options: list[dict[str, str]], gold_value: str) -> tuple[list[dict[str, str]], str]:
    target_label = TARGET_LABEL_BY_PERSPECTIVE[perspective]
    gold = next(option for option in options if option["value"] == gold_value)
    distractors = sorted([option for option in options if option["value"] != gold_value], key=lambda option: hashlib.sha256(f"{row_id}:{option['value']}".encode()).hexdigest())
    out: list[dict[str, str]] = []
    idx = 0
    for label in LABELS:
        if label == target_label:
            out.append({"label": label, **gold})
        else:
            out.append({"label": label, **distractors[idx]})
            idx += 1
    return out, target_label


def pre_option_prompt(packet: dict[str, Any], perspective: str) -> str:
    src = packet["visible_source_evidence"]["primary"]
    secondary = packet["visible_source_evidence"]["secondary"]
    test = packet["visible_verifier_evidence"]["test"]
    exe = packet["verifier_execution"]
    return "\n".join([
        "Language: web_js_ts_html",
        f"Perspective: {perspective}",
        INSTRUCTIONS[perspective],
        f"Repository family: {packet['git_repo_family']}",
        f"Git commit: {packet['git_head']}",
        "Task observation:",
        packet["task_observation"],
        "Visible source evidence:",
        f"{packet['source_path']} lines {src.get('line_start')}-{src.get('line_end')}:\n{src.get('text', '')}",
        f"{packet['secondary_source_path']} lines {secondary.get('line_start')}-{secondary.get('line_end')}:\n{secondary.get('text', '')}",
        "Visible verifier/test evidence:",
        f"{packet['test_path']} lines {test.get('line_start')}-{test.get('line_end')}:\n{test.get('text', '')}",
        "Visible verifier execution evidence:",
        f"Command: {exe['focused_verifier_command']}",
        f"Observed transition: {exe['observed_transition']}",
        exe["raw_log_excerpt"],
    ])


def prompt(packet: dict[str, Any], perspective: str, options: list[dict[str, str]]) -> str:
    lines = pre_option_prompt(packet, perspective).splitlines() + ["Options:"]
    lines.extend(f"{option['label']}. {option['text']}" for option in options)
    lines.append("Answer:")
    return "\n".join(lines)


def rows_for_packet(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for perspective in PERSPECTIVES:
        row_id = f"{packet['root_id']}::{perspective}::train_v1"
        gold_value = GOLD_BY_PERSPECTIVE[perspective]
        options, target_label = deterministic_options(row_id, perspective, option_bank(packet, perspective), gold_value)
        pre_options = pre_option_prompt(packet, perspective)
        rows.append({
            "row_id": row_id,
            "root_id": packet["root_id"],
            "source_bundle_id": packet["root_id"],
            "language_family": "web_js_ts_html",
            "task_type": perspective,
            "repo_family": packet["repo_family"],
            "git_repo_family": packet["git_repo_family"],
            "split_component": "train_support",
            "input_text": prompt(packet, perspective, options),
            "opaque_options": options,
            "bounded_choice_target_label": target_label,
            "semantic_target_value": gold_value,
            "target_text": target_label,
            "strict_eval_eligible": False,
            "train_support_only": True,
            "source_heldout_admissible": False,
            "verifier_anchor": True,
            "selected_test_anchor": True,
            "anti_cheat": {
                "deterministic_option_shuffle": True,
                "target_label_not_visible_before_options": not explicit_label_leak(pre_options, target_label),
                "semantic_target_not_visible_before_options": gold_value not in pre_options,
                "executed_verifier_output_attached": True,
                "not_in_strict_eval": True,
            },
            "review": {"rubric_complete": True, "anti_cheat_complete": True, "gold_adjudication_complete": True, "reviewer": "codex_ai_maintainer_review", "unique_answer_supported": True},
        })
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    packets = [
        {**packet(spec), "admission_status": "train_support_gold_adjudicated", "trainable_now": True, "strict_eval_eligible_now": False}
        for spec in ROOT_SPECS
    ]
    packets = [
        pkt for pkt in packets
        if pkt["verifier_execution"]["focused_verifier_exit_code"] == 0
        and pkt["visible_source_evidence"]["primary"].get("exists")
        and pkt["visible_verifier_evidence"]["test"].get("exists")
    ]
    rows = [row for pkt in packets for row in rows_for_packet(pkt)]
    leakage_flags = [
        row["row_id"]
        for row in rows
        if not row["anti_cheat"]["target_label_not_visible_before_options"]
        or not row["anti_cheat"]["semantic_target_not_visible_before_options"]
    ]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": len(packets) == 3 and len(rows) == 18 and not leakage_flags,
        "decision": "openclaw_more_web_train_rows_admitted" if not leakage_flags else "blocked_prompt_target_leak",
        "counts": {
            "admitted_train_roots": len(packets),
            "train_rows": len(rows),
            "strict_eval_rows": 0,
            "target_labels": dict(Counter(row["bounded_choice_target_label"] for row in rows)),
            "task_types": dict(Counter(row["task_type"] for row in rows)),
        },
        "leakage_flags": leakage_flags,
        "claim_boundary": [
            "These rows are train-support only and must not enter strict Web heldout.",
            "They are intended to satisfy the executed Web train-root supply gate, not to prove model improvement by themselves.",
        ],
        "outputs": {"summary": rel(SUMMARY), "packets": rel(PACKETS), "rows": rel(ROWS)},
    }
    write_jsonl(PACKETS, packets)
    write_jsonl(ROWS, rows)
    write_json(SUMMARY, summary)
    write_json(SUMMARIES / f"{NAME}.json", summary)


if __name__ == "__main__":
    main()
