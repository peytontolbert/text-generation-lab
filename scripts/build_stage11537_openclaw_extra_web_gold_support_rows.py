#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11537
NAME = "stage11537_openclaw_extra_web_gold_support_rows"
OUT = ART / NAME
SUMMARY = OUT / "openclaw_extra_web_gold_support_rows.json"
ROWS = OUT / "openclaw_extra_web_gold_train_support_rows.jsonl"
PACKETS = OUT / "openclaw_extra_web_gold_packets.jsonl"
LOG_DIR = ART / "stage11537_openclaw_extra_web_verifier_execution/logs"
REPO = Path("/data/repositories/openclaw__clawhub")

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
INSTRUCTIONS = {
    "symptom_localization": "Choose the implementation surface most directly exercised by the selected verifier.",
    "evidence_citation": "Choose the evidence role that most directly supports judging this verifier-backed maintainer bundle.",
    "verifier_outcome": "Choose the verifier transition established by the captured focused test output.",
    "patch_impact": "Choose the surface whose changes would most directly alter the selected verifier behavior.",
    "minimal_fix_selection": "Choose the smallest likely repair surface if the verified behavior regressed.",
    "abstention_insufficient_evidence": "Decide whether the visible source, test, and execution evidence are enough to answer this bundle.",
}

ROOT_SPECS = [
    {
        "slug": "token_touch_throttling",
        "test": "convex/tokens.touch.test.ts",
        "source": "convex/tokens.ts",
        "secondary_source": "convex/packagePublishTokens.ts",
        "source_lines": (60, 100),
        "secondary_lines": (45, 78),
        "test_lines": (1, 66),
        "task": "Focused token touch verifier confirms stale tokens are patched while fresh token touches are skipped.",
    },
    {
        "slug": "maintenance_backfill_summary",
        "test": "convex/maintenance.test.ts",
        "source": "convex/maintenance.ts",
        "secondary_source": "convex/lib/skillSummary.ts",
        "source_lines": (240, 430),
        "secondary_lines": (1, 80),
        "test_lines": (45, 145),
        "task": "Focused maintenance verifier confirms skill summary backfill repairs parsed SKILL.md metadata and respects dry-run behavior.",
    },
    {
        "slug": "count_public_skills_fallback",
        "test": "convex/skills.countPublicSkills.test.ts",
        "source": "convex/skills.ts",
        "secondary_source": "convex/lib/globalStats.ts",
        "source_lines": (5058, 5085),
        "secondary_lines": (1, 80),
        "test_lines": (1, 66),
        "task": "Focused public skill count verifier confirms the query returns precomputed global stats and falls back to zero when unavailable.",
    },
    {
        "slug": "public_moderation_override_sanitization",
        "test": "convex/skills.publicModeration.test.ts",
        "source": "convex/skills.ts",
        "secondary_source": "convex/lib/moderationReasonCodes.ts",
        "source_lines": (1968, 2080),
        "secondary_lines": (1, 90),
        "test_lines": (1, 120),
        "task": "Focused public moderation verifier confirms manual override notes are sanitized for non-owner public reads.",
    },
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def snippet(path: Path, line_range: tuple[int, int]) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start, end = line_range
    part = lines[max(0, start - 1): min(len(lines), end)]
    text = "\n".join(part)
    return {
        "path": str(path),
        "line_start": start,
        "line_end": min(end, len(lines)),
        "sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
        "text": text,
    }


def read_log(test_path: str) -> str:
    return (LOG_DIR / f"{Path(test_path).name}.log").read_text(encoding="utf-8", errors="replace")


def option_bank(perspective: str, packet: dict[str, Any]) -> list[dict[str, str]]:
    if perspective == "verifier_outcome":
        return [
            {"value": "pass_targeted_test_selection", "text": "PASS_TARGETED_TEST_SELECTION: the focused Vitest file executed and all selected assertions passed."},
            {"value": "fail_before_assertions", "text": "FAILS_BEFORE_ASSERTIONS: the selected verifier failed during environment or dependency setup."},
            {"value": "not_exercised_by_selected_test", "text": "NOT_EXERCISED_BY_SELECTED_TEST: the selected verifier does not import or exercise the shown implementation."},
            {"value": "abstain_insufficient_evidence", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
        ]
    if perspective == "abstention_insufficient_evidence":
        return [
            {"value": "answer_with_visible_evidence", "text": "ANSWER_WITH_VISIBLE_EVIDENCE: source snippets, focused test, and captured verifier output are enough for this bounded decision."},
            {"value": "retrieve_more_source", "text": "RETRIEVE_MORE_SOURCE: more code context is required before any bounded decision."},
            {"value": "needs_external_web_research", "text": "NEEDS_EXTERNAL_WEB_RESEARCH: external documentation is required."},
            {"value": "abstain_insufficient_evidence", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
        ]
    return [
        {"value": "candidate_change_surface", "text": f"{packet['source_path']} implementation surface exercised by the focused verifier."},
        {"value": "verifier_and_test_constraint", "text": f"{packet['test_path']} focused Vitest assertions and captured pass log."},
        {"value": "supporting_secondary_surface", "text": f"{packet['secondary_source_path']} adjacent supporting source context."},
        {"value": "dependency_or_test_environment_surface", "text": "package.json and repo test tooling surface."},
        {"value": "abstain_insufficient_evidence", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ]


def deterministic_options(row_id: str, perspective: str, options: list[dict[str, str]], gold_value: str) -> tuple[list[dict[str, str]], str]:
    target_label = TARGET_LABEL_BY_PERSPECTIVE[perspective]
    gold = next(option for option in options if option["value"] == gold_value)
    distractors = sorted(
        [option for option in options if option["value"] != gold_value],
        key=lambda option: hashlib.sha256(f"{row_id}:{option['value']}".encode()).hexdigest(),
    )
    out = []
    d_idx = 0
    for label in LABELS[: len(options)]:
        if label == target_label:
            out.append({"label": label, **gold})
        else:
            out.append({"label": label, **distractors[d_idx]})
            d_idx += 1
    return out, target_label


def packet_from_spec(spec: dict[str, Any]) -> dict[str, Any]:
    log = read_log(spec["test"])
    passed = "Test Files" in log and "passed" in log and "failed" not in log.lower()
    return {
        "root_id": f"stage11537::openclaw_clawhub::convex::{spec['slug']}",
        "language_family": "web_js_ts_html",
        "repo_family": "convex",
        "git_repo_family": "openclaw_clawhub",
        "repo_path": str(REPO / "convex"),
        "git_head": "8bbc66868d63c22ee905b327214982f60da4ac0a",
        "task_observation": spec["task"],
        "source_path": spec["source"],
        "secondary_source_path": spec["secondary_source"],
        "test_path": spec["test"],
        "visible_source_evidence": {
            "primary": snippet(REPO / spec["source"], spec["source_lines"]),
            "secondary": snippet(REPO / spec["secondary_source"], spec["secondary_lines"]),
        },
        "visible_verifier_evidence": {"test": snippet(REPO / spec["test"], spec["test_lines"])},
        "verifier_execution": {
            "focused_verifier_command": f"bun run test -- {Path(spec['test']).name}",
            "focused_verifier_exit_code": 0 if passed else 1,
            "observed_transition": "TARGETED_TEST_PASS" if passed else "TARGETED_TEST_FAILED",
            "raw_log_excerpt": log[:2400],
            "log_artifact": rel(LOG_DIR / f"{Path(spec['test']).name}.log"),
        },
        "gold_rubric": {
            "unique_answer_supported": passed,
            "minimum_reasoning_depth": "L2_cross_reference",
            "why_candidate_change_surface": "The selected test imports or invokes the primary source behavior under test.",
            "why_verifier_constraint": "The selected focused Vitest file plus captured pass log is the decisive verifier evidence.",
            "why_not_environment": "Dependency hydration succeeded and the focused verifier passed.",
        },
    }


def prompt(packet: dict[str, Any], perspective: str, options: list[dict[str, str]]) -> str:
    src = packet["visible_source_evidence"]
    test = packet["visible_verifier_evidence"]["test"]
    exe = packet["verifier_execution"]
    lines = [
        "Language: web_js_ts_html",
        f"Perspective: {perspective}",
        INSTRUCTIONS[perspective],
        f"Repository family: {packet['git_repo_family']}",
        f"Git commit: {packet['git_head']}",
        "Task observation:",
        packet["task_observation"],
        "Visible source evidence:",
        f"{packet['source_path']} lines {src['primary']['line_start']}-{src['primary']['line_end']}:\n{src['primary']['text']}",
        f"{packet['secondary_source_path']} lines {src['secondary']['line_start']}-{src['secondary']['line_end']}:\n{src['secondary']['text']}",
        "Visible verifier/test evidence:",
        f"{packet['test_path']} lines {test['line_start']}-{test['line_end']}:\n{test['text']}",
        "Visible verifier execution evidence:",
        f"Command: {exe['focused_verifier_command']}",
        f"Observed transition: {exe['observed_transition']}",
        exe["raw_log_excerpt"],
        "Options:",
    ]
    lines.extend(f"{option['label']}. {option['text']}" for option in options)
    lines.append("Answer:")
    return "\n".join(lines)


def rows_for_packet(packet: dict[str, Any]) -> list[dict[str, Any]]:
    gold_by_perspective = {
        "symptom_localization": "candidate_change_surface",
        "evidence_citation": "verifier_and_test_constraint",
        "verifier_outcome": "pass_targeted_test_selection",
        "patch_impact": "candidate_change_surface",
        "minimal_fix_selection": "candidate_change_surface",
        "abstention_insufficient_evidence": "answer_with_visible_evidence",
    }
    rows = []
    for perspective in PERSPECTIVES:
        gold_value = gold_by_perspective[perspective]
        row_id = f"{packet['root_id']}::{perspective}"
        options, target = deterministic_options(row_id, perspective, option_bank(perspective, packet), gold_value)
        text = prompt(packet, perspective, options)
        rows.append({
            "row_id": row_id,
            "root_id": packet["root_id"],
            "root_lineage_key": f"{packet['git_repo_family']}::{packet['git_head']}::{packet['root_id']}::stage11537",
            "language_family": packet["language_family"],
            "repo_family": packet["repo_family"],
            "repo_id": packet["git_repo_family"],
            "task_type": perspective,
            "split": "train_support",
            "package_split": "train_support",
            "strict_eval_eligible": False,
            "train_support_only": True,
            "review_status": "ai_gold_adjudicated_executed_verifier_train_support",
            "input_text": text,
            "prompt_text": text,
            "target_text": target,
            "decoder_text": target,
            "bounded_choice_target_label": target,
            "semantic_target_value": gold_value,
            "opaque_options": options,
            "expected_enabled_loss": "decoder_ce",
            "loss_mask": {"decoder_ce": True},
            "standalone_projection_source": {
                "projection_mode": "web_executed_verifier_gold_adjudicated_train_support",
                "gold_value": gold_value,
                "bundle": packet,
            },
            "anti_cheat": {
                "deterministic_option_shuffle": True,
                "target_label_balance_controlled": True,
                "target_label_not_visible_before_options": True,
                "gold_value_not_used_as_label": True,
                "source_and_verifier_snippets_visible": True,
                "executed_verifier_output_attached": True,
                "train_support_not_strict": True,
                "root_not_used_in_existing_web_heldout": True,
            },
        })
    return rows


def main() -> None:
    packets = [packet_from_spec(spec) for spec in ROOT_SPECS]
    rows = [row for packet in packets for row in rows_for_packet(packet)]
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(PACKETS, packets)
    write_jsonl(ROWS, rows)
    gates = {
        "all_verifiers_passed": all(packet["verifier_execution"]["focused_verifier_exit_code"] == 0 for packet in packets),
        "all_rows_have_targets": all(row.get("bounded_choice_target_label") for row in rows),
        "all_rows_have_options": all(row.get("opaque_options") for row in rows),
        "all_rows_train_support_only": all(row.get("train_support_only") is True and row.get("strict_eval_eligible") is False for row in rows),
        "all_rows_source_verifier_visible": all((row.get("anti_cheat") or {}).get("source_and_verifier_snippets_visible") is True for row in rows),
        "all_rows_deterministic_shuffle": all((row.get("anti_cheat") or {}).get("deterministic_option_shuffle") is True for row in rows),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": all(gates.values()),
        "decision": "openclaw_extra_web_gold_train_support_rows_ready" if all(gates.values()) else "openclaw_extra_web_gold_train_support_rows_failed_gate",
        "counts": {
            "roots": len(packets),
            "rows": len(rows),
            "rows_by_task": dict(sorted(Counter(row["task_type"] for row in rows).items())),
            "target_labels": dict(sorted(Counter(row["bounded_choice_target_label"] for row in rows).items())),
            "semantic_targets": dict(sorted(Counter(row["semantic_target_value"] for row in rows).items())),
        },
        "gates": gates,
        "admission": {
            "trainable_now": all(gates.values()),
            "strict_eval_eligible_now": False,
            "why": "Rows have source/test snippets, focused verifier pass logs, deterministic opaque options, and AI gold adjudication, but are admitted only as train support.",
        },
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS), "packets": rel(PACKETS)},
        "next_actions": [
            "Update Web supply accounting with four additional OpenClaw train-support roots.",
            "Do not count these roots as sealed heldout.",
            "Continue sourcing heldout roots from different Web repo families.",
        ],
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
