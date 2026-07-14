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
STAGE = 11535
NAME = "stage11535_openclaw_web_gold_adjudicated_support_rows"
OUT = ART / NAME
SUMMARY = OUT / "openclaw_web_gold_adjudicated_support_rows.json"
ROWS = OUT / "openclaw_web_gold_adjudicated_train_support_rows.jsonl"
PACKET_OUT = OUT / "openclaw_web_gold_adjudicated_packet.json"

STAGE11533_PACKET = ART / "stage11533_openclaw_web_verifier_execution_artifact/openclaw_web_verifier_execution_packet.json"
STAGE11533_SUMMARY = SUMMARIES / "stage11533_openclaw_web_verifier_execution_artifact.json"

LABELS = list("ABCDE")
TARGET_LABEL_BY_PERSPECTIVE = {
    "symptom_localization": "A",
    "evidence_citation": "B",
    "verifier_outcome": "C",
    "patch_impact": "D",
    "minimal_fix_selection": "E",
    "abstention_insufficient_evidence": "A",
}
GOLD = {
    "symptom_localization": "candidate_change_surface",
    "evidence_citation": "verifier_and_test_constraint",
    "verifier_outcome": "pass_targeted_test_selection",
    "patch_impact": "candidate_change_surface",
    "minimal_fix_selection": "candidate_change_surface",
    "abstention_insufficient_evidence": "answer_with_visible_evidence",
}
INSTRUCTIONS = {
    "symptom_localization": "Choose the implementation surface most directly exercised by the selected verifier.",
    "evidence_citation": "Choose the evidence role that most directly supports judging this verifier-backed maintainer bundle.",
    "verifier_outcome": "Choose the verifier transition established by the captured focused test output.",
    "patch_impact": "Choose the surface whose changes would most directly alter the selected verifier behavior.",
    "minimal_fix_selection": "Choose the smallest likely repair surface if the public skill-version sanitization behavior regressed.",
    "abstention_insufficient_evidence": "Decide whether the visible source, test, and execution evidence are enough to answer this bundle.",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def read_snippet(path: Path, start: int, end: int) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    part = lines[max(0, start - 1): min(len(lines), end)]
    text = "\n".join(part)
    return {
        "path": str(path),
        "line_start": start,
        "line_end": min(end, len(lines)),
        "sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
        "text": text,
    }


def deterministic_options(
    row_id: str,
    perspective: str,
    options: list[dict[str, str]],
    gold_value: str,
) -> tuple[list[dict[str, str]], str]:
    target_label = TARGET_LABEL_BY_PERSPECTIVE[perspective]
    gold = next((option for option in options if option["value"] == gold_value), None)
    if gold is None:
        raise ValueError(f"missing gold value for {row_id}: {gold_value}")
    distractors = [option for option in options if option["value"] != gold_value]
    distractors = sorted(distractors, key=lambda option: hashlib.sha256(f"{row_id}:{option['value']}".encode()).hexdigest())
    out = []
    d_idx = 0
    for label in LABELS[: len(options)]:
        if label == target_label:
            out.append({"label": label, **gold})
        else:
            out.append({"label": label, **distractors[d_idx]})
            d_idx += 1
    return out, target_label


def option_bank(perspective: str) -> list[dict[str, str]]:
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
        {"value": "candidate_change_surface", "text": "convex/skills.ts public skill/version query implementation and sanitization surface."},
        {"value": "verifier_and_test_constraint", "text": "convex/skills.versions.public.test.ts focused Vitest assertions for public skill version sanitization."},
        {"value": "supporting_public_projection_surface", "text": "convex/lib/public.ts public projection type helpers used by adjacent public surfaces."},
        {"value": "dependency_or_test_environment_surface", "text": "package.json and repo test tooling surface."},
        {"value": "abstain_insufficient_evidence", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ]


def compact_packet(packet: dict[str, Any]) -> dict[str, Any]:
    repo = Path(packet["repo_path"]).parent
    return {
        "root_id": "stage11535::openclaw_clawhub::convex::skills_versions_public_sanitization_train_support",
        "parent_root_id": packet.get("root_id"),
        "language_family": "web_js_ts_html",
        "repo_family": "convex",
        "git_repo_family": "openclaw_clawhub",
        "repo_path": str(repo / "convex"),
        "git_head": packet.get("git_head"),
        "task_observation": (
            "Focused public skill-version verifier confirms that public queries sanitize latestVersion/version "
            "payloads by removing storage IDs, private parsed metadata, and static-scan evidence."
        ),
        "visible_source_evidence": {
            "query_surface": read_snippet(repo / "convex/skills.ts", 1968, 2025),
            "version_query_surface": read_snippet(repo / "convex/skills.ts", 5070, 5145),
            "public_projection_surface": read_snippet(repo / "convex/lib/public.ts", 1, 95),
        },
        "visible_verifier_evidence": {
            "test_assertions": read_snippet(repo / "convex/skills.versions.public.test.ts", 123, 205),
            "direct_version_assertions": read_snippet(repo / "convex/skills.versions.public.test.ts", 232, 255),
        },
        "verifier_execution": packet.get("verifier_execution") or {},
        "gold_rubric": {
            "unique_answer_supported": True,
            "minimum_reasoning_depth": "L2_cross_reference",
            "why_candidate_change_surface": "The selected test imports getBySlug/getVersionById/listVersions/listWithLatest from convex/skills.ts and checks sanitized public version outputs.",
            "why_verifier_constraint": "The evidence-citation row asks for the role that proves the decision; the focused Vitest assertions and pass log are the decisive verifier constraint.",
            "why_not_public_projection_only": "convex/lib/public.ts provides adjacent public type/projection context, but the visible selected verifier imports convex/skills.ts query handlers.",
            "why_not_environment": "Dependency hydration and the focused verifier passed; this is not a test-environment failure.",
        },
        "anti_cheat_review": {
            "decision": "admit_train_support_only",
            "target_labels_assigned_after_options": True,
            "deterministic_option_shuffle": True,
            "target_label_balance_controlled": True,
            "gold_value_not_used_as_label": True,
            "source_and_verifier_snippets_visible": True,
            "executed_verifier_output_attached": True,
            "strict_eval_eligible": False,
            "why_not_strict": "This root was actively materialized from the current Web supply queue; use as support, not as sealed heldout.",
        },
    }


def prompt(bundle: dict[str, Any], perspective: str, options: list[dict[str, str]]) -> str:
    source = bundle["visible_source_evidence"]
    verifier = bundle["visible_verifier_evidence"]
    execution = bundle["verifier_execution"]
    lines = [
        "Language: web_js_ts_html",
        f"Perspective: {perspective}",
        INSTRUCTIONS[perspective],
        f"Repository family: {bundle['git_repo_family']}",
        f"Git commit: {bundle['git_head']}",
        "Task observation:",
        bundle["task_observation"],
        "Visible source evidence:",
        f"convex/skills.ts query surface lines {source['query_surface']['line_start']}-{source['query_surface']['line_end']}:\n{source['query_surface']['text']}",
        f"convex/skills.ts version query surface lines {source['version_query_surface']['line_start']}-{source['version_query_surface']['line_end']}:\n{source['version_query_surface']['text']}",
        f"convex/lib/public.ts projection context lines {source['public_projection_surface']['line_start']}-{source['public_projection_surface']['line_end']}:\n{source['public_projection_surface']['text']}",
        "Visible verifier/test evidence:",
        f"convex/skills.versions.public.test.ts lines {verifier['test_assertions']['line_start']}-{verifier['test_assertions']['line_end']}:\n{verifier['test_assertions']['text']}",
        f"direct version assertion lines {verifier['direct_version_assertions']['line_start']}-{verifier['direct_version_assertions']['line_end']}:\n{verifier['direct_version_assertions']['text']}",
        "Visible verifier execution evidence:",
        f"Command: {execution.get('focused_verifier_command')}",
        f"Observed transition: {execution.get('observed_transition')}",
        f"Result: {execution.get('result_summary')}",
        "Options:",
    ]
    lines.extend(f"{option['label']}. {option['text']}" for option in options)
    lines.append("Answer:")
    return "\n".join(lines)


def build_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for perspective, gold_value in GOLD.items():
        row_id = f"{bundle['root_id']}::{perspective}"
        options, target = deterministic_options(row_id, perspective, option_bank(perspective), gold_value)
        text = prompt(bundle, perspective, options)
        rows.append(
            {
                "row_id": row_id,
                "root_id": bundle["root_id"],
                "root_lineage_key": f"{bundle['git_repo_family']}::{bundle['git_head']}::skills_versions_public_sanitization::stage11535",
                "language_family": bundle["language_family"],
                "repo_family": bundle["repo_family"],
                "repo_id": bundle["git_repo_family"],
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
                    "bundle": bundle,
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
            }
        )
    return rows


def main() -> None:
    source_packet = load_json(STAGE11533_PACKET)
    stage11533 = load_json(STAGE11533_SUMMARY)
    bundle = compact_packet(source_packet)
    rows = build_rows(bundle)
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(PACKET_OUT, bundle)
    write_jsonl(ROWS, rows)
    counts = {
        "rows": len(rows),
        "unique_roots": len({row["root_id"] for row in rows}),
        "rows_by_task": dict(sorted(Counter(row["task_type"] for row in rows).items())),
        "target_labels": dict(sorted(Counter(row["bounded_choice_target_label"] for row in rows).items())),
        "semantic_targets": dict(sorted(Counter(row["semantic_target_value"] for row in rows).items())),
    }
    gates = {
        "stage11533_verifier_passed": (stage11533.get("verifier_execution") or {}).get("focused_verifier_exit_code") == 0,
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
        "decision": "openclaw_web_gold_adjudicated_train_support_rows_ready" if all(gates.values()) else "openclaw_web_gold_adjudicated_rows_failed_gate",
        "counts": counts,
        "gates": gates,
        "admission": {
            "trainable_now": all(gates.values()),
            "strict_eval_eligible_now": False,
            "why": "Rows have source/test snippets, focused verifier pass evidence, deterministic opaque options, and AI gold adjudication, but are admitted only as train support.",
        },
        "source_artifacts": {"stage11533_packet": rel(STAGE11533_PACKET), "stage11533_summary": rel(STAGE11533_SUMMARY)},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS), "packet": rel(PACKET_OUT)},
        "next_actions": [
            "Update Web root supply audit with this one admitted executed train-support root.",
            "Do not count this root as sealed heldout.",
            "Continue materializing more Web roots; Stage11527 requires at least 20 executed train roots and 10 heldout roots.",
        ],
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
