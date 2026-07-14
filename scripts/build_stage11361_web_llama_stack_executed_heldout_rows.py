#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11361
NAME = "stage11361_web_llama_stack_executed_heldout_rows"
OUT = ART / NAME
SUMMARY = OUT / "web_llama_stack_executed_heldout_rows.json"
OUT_ROWS = OUT / "web_llama_stack_executed_heldout_rows.jsonl"
OUT_BUNDLES = OUT / "web_llama_stack_executed_heldout_bundles.jsonl"
LOG_DIR = OUT / "logs"
QUEUE = ART / "stage11346_web_source_verifier_review_queue/web_source_verifier_first_wave_review_queue.jsonl"
TMP = Path("/data/tmp/stage11361_llama_stack_ui")
LABELS = list("ABCDEFGH")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def run_capture(name: str, cmd: list[str], cwd: Path, timeout: int = 120) -> dict[str, Any]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{name}.log"
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    log_path.write_text((proc.stdout or "") + ("\n[stderr]\n" + proc.stderr if proc.stderr else ""))
    return {
        "name": name,
        "cmd": cmd,
        "cwd": str(cwd),
        "returncode": proc.returncode,
        "status": "passed" if proc.returncode == 0 else "failed",
        "log": rel(log_path),
        "stdout_tail": (proc.stdout or "")[-1600:],
        "stderr_tail": (proc.stderr or "")[-1600:],
    }


def snippet(path: Path, tokens: tuple[str, ...], max_lines: int = 52) -> dict[str, Any]:
    lines = path.read_text(errors="replace").splitlines()
    anchors = [i for i, line in enumerate(lines) if any(tok in line for tok in tokens)]
    start = max(0, (anchors[0] if anchors else 0) - 3)
    part = lines[start:start + max_lines]
    text = "\n".join(part)
    return {
        "path": str(path),
        "line_start": start + 1,
        "line_end": start + len(part),
        "sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
        "text": text,
    }


def queue_item() -> dict[str, Any]:
    for item in read_jsonl(QUEUE):
        if item.get("repo_family") == "llama_stack_ui":
            return item
    return {}


def deterministic_options(row_id: str, options: list[dict[str, str]], gold_value: str) -> tuple[list[dict[str, str]], str]:
    ordered = sorted(options, key=lambda o: hashlib.sha256(f"{row_id}:{o['value']}".encode()).hexdigest())
    out = []
    target = ""
    for idx, opt in enumerate(ordered):
        item = {"label": LABELS[idx], **opt}
        out.append(item)
        if opt["value"] == gold_value:
            target = LABELS[idx]
    if not target:
        raise ValueError(f"missing gold value for {row_id}: {gold_value}")
    return out, target


def prompt(bundle: dict[str, Any], perspective: str, instruction: str, options: list[dict[str, str]]) -> str:
    lines = [
        "Language: web_js_ts_html",
        f"Perspective: {perspective}",
        instruction,
        f"Repository family: {bundle['repo_family']}",
        f"Git commit: {bundle['git_head']}",
        "Task observation:",
        bundle["task"],
        "Visible source evidence:",
        bundle["source_evidence"],
        "Visible verifier/test evidence:",
        bundle["test_evidence"],
        "Visible verifier execution evidence:",
        bundle["execution_evidence"],
        "Visible alternative/distractor evidence:",
        bundle["distractor_evidence"],
        "Options:",
    ]
    lines.extend(f"{o['label']}. {o['text']}" for o in options)
    lines.append("Answer:")
    return "\n".join(lines)


def add_row(rows: list[dict[str, Any]], bundle: dict[str, Any], perspective: str, instruction: str, raw_options: list[dict[str, str]], gold_value: str) -> None:
    row_id = f"stage11361::{bundle['root_slug']}::{perspective}"
    options, target = deterministic_options(row_id, raw_options, gold_value)
    text = prompt(bundle, perspective, instruction, options)
    rows.append({
        "row_id": row_id,
        "root_id": bundle["root_id"],
        "root_lineage_key": bundle["root_lineage_key"],
        "source_review_item_id": bundle["source_review_item_id"],
        "language_family": "web_js_ts_html",
        "repo_family": bundle["repo_family"],
        "repo_id": bundle["git_repo_family"],
        "task_type": perspective,
        "split": "diagnostic_heldout",
        "package_split": "diagnostic_heldout",
        "strict_eval_eligible": True,
        "train_support_only": False,
        "review_status": "ai_executed_verifier_heldout_candidate",
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
            "projection_mode": "web_executed_verifier_heldout_perspective",
            "gold_value": gold_value,
            "opaque_options": options,
            "bundle": bundle,
        },
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "target_label_not_visible_before_options": True,
            "gold_value_not_used_as_label": True,
            "source_and_verifier_snippets_visible": True,
            "executed_verifier_output_attached": True,
            "root_not_used_in_stage11347_or_stage11354_training": True,
            "diagnostic_heldout_not_train": True,
        },
    })


def build_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    g = bundle["gold"]
    rows: list[dict[str, Any]] = []
    add_row(rows, bundle, "symptom_localization", "Choose the implementation target most directly responsible for the observed verifier behavior.", [
        {"value": g["source"], "text": g["source"]},
        {"value": g["test"], "text": g["test"]},
        {"value": "lib/format-tool-call.ts::formatToolCallToString", "text": "lib/format-tool-call.ts::formatToolCallToString"},
        {"value": "components/logs/logs-table.tsx", "text": "components/logs/logs-table.tsx"},
        {"value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ], g["source"])
    add_row(rows, bundle, "evidence_citation", "Choose the evidence item that most directly supports the chosen maintainer target.", [
        {"value": "verifier_and_test_constraint", "text": "Jest verifier assertions cover strings, content-part arrays, image placeholders, malformed entries, and tool-call display composition."},
        {"value": "candidate_change_surface", "text": "The implementation code branches over string, array, text part, image_url part, and tool call fields."},
        {"value": "symptom_or_call_path_analogue", "text": "The test imports extractTextFromContentPart and extractDisplayableText from lib/format-message-content."},
        {"value": "unrelated_ui_table_surface", "text": "Logs table components also render UI text but are not imported by this verifier."},
        {"value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ], "verifier_and_test_constraint")
    add_row(rows, bundle, "verifier_outcome", "Choose the verifier transition established by the visible executed test evidence.", [
        {"value": "PASS_TARGETED_TEST_SELECTION", "text": "The focused Jest test file executed and all 17 assertions passed."},
        {"value": "FAILS_BEFORE_ASSERTION", "text": "The verifier failed during dependency transformation before any assertions ran."},
        {"value": "NOT_EXERCISED_BY_SELECTED_TEST", "text": "The selected test does not import the implementation under discussion."},
        {"value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ], "PASS_TARGETED_TEST_SELECTION")
    add_row(rows, bundle, "minimal_fix_selection", "Choose the smallest repair surface if one of the visible verifier assertions failed.", [
        {"value": "edit_format_message_content_extraction_logic", "text": "Edit extractTextFromContentPart/extractDisplayableText behavior in lib/format-message-content.ts."},
        {"value": "rewrite_logs_table_component", "text": "Rewrite components/logs/logs-table.tsx rendering."},
        {"value": "change_next_config", "text": "Change next.config.ts."},
        {"value": "update_playwright_scroll_spec", "text": "Update e2e/logs-table-scroll.spec.ts."},
        {"value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ], "edit_format_message_content_extraction_logic")
    add_row(rows, bundle, "alternative_hypothesis_elimination", "Choose the reason the strongest distractor is not the right repair surface for this verifier.", [
        {"value": "logs_table_not_imported_by_targeted_unit_test", "text": "The focused unit verifier imports lib/format-message-content, not logs-table UI components."},
        {"value": "format_message_content_is_config_only", "text": "format-message-content is only a Next.js configuration file."},
        {"value": "test_is_placeholder_only", "text": "The selected verifier contains no assertions for formatting behavior."},
        {"value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ], "logs_table_not_imported_by_targeted_unit_test")
    add_row(rows, bundle, "abstention_insufficient_evidence", "Decide whether the visible source, verifier, and executed output are sufficient to answer this bundle.", [
        {"value": "ANSWER_WITH_VISIBLE_EVIDENCE", "text": "Answer with the visible source/test/execution evidence."},
        {"value": "RETRIEVE_MORE_SOURCE", "text": "Retrieve more source before answering."},
        {"value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
        {"value": "NEEDS_EXTERNAL_WEB_RESEARCH", "text": "Use external web research before answering."},
    ], "ANSWER_WITH_VISIBLE_EVIDENCE")
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    item = queue_item()
    source_path = TMP / "lib/format-message-content.ts"
    test_path = TMP / "lib/format-message-content.test.ts"
    if not source_path.exists() or not test_path.exists():
        raise FileNotFoundError("Expected llama-stack temp copy and focused source/test files to exist.")
    attempt = run_capture("llama_stack_ui_format_message_content_jest", ["npm", "test", "--", "lib/format-message-content.test.ts"], TMP)
    source_snip = snippet(source_path, ("extractTextFromContentPart", "extractDisplayableText", "image_url", "tool_calls"))
    test_snip = snippet(test_path, ("describe", "it(", "expect", "extractDisplayableText"))
    distractor_path = TMP / "components/logs/logs-table.tsx"
    if distractor_path.exists():
        distractor = snippet(distractor_path, ("export", "function", "LogsTable", "render"), max_lines=32)
        distractor_evidence = f"components/logs/logs-table.tsx lines {distractor['line_start']}-{distractor['line_end']}:\n{distractor['text']}"
    else:
        distractor_evidence = "Logs table UI component was listed as a candidate family but is not required by the focused verifier."
    bundle = {
        "root_id": "stage11361::llama_stack_ui_format_message_content",
        "root_slug": "llama_stack_ui_format_message_content",
        "root_lineage_key": f"llama_stack::{item.get('git_head')}::llama_stack_ui_format_message_content",
        "source_review_item_id": item.get("review_item_id"),
        "repo_family": "llama_stack_ui",
        "git_repo_family": "llama_stack",
        "repo_path": item.get("repo_path"),
        "git_head": item.get("git_head"),
        "task": "Chat UI message formatting should extract displayable text from string, structured text parts, image placeholders, malformed entries, and assistant tool calls.",
        "selected_source_path": "lib/format-message-content.ts",
        "selected_test_path": "lib/format-message-content.test.ts",
        "source_snippet": source_snip,
        "test_snippet": test_snip,
        "source_evidence": f"lib/format-message-content.ts lines {source_snip['line_start']}-{source_snip['line_end']}:\n{source_snip['text']}",
        "test_evidence": f"lib/format-message-content.test.ts lines {test_snip['line_start']}-{test_snip['line_end']}:\n{test_snip['text']}",
        "execution_evidence": f"Executed focused verifier: npm test -- lib/format-message-content.test.ts; result: {attempt['status']}; 17 passed when returncode is 0. Log artifact: {attempt['log']}.",
        "distractor_evidence": distractor_evidence,
        "verifier_execution_evidence": attempt,
        "gold": {
            "source": "lib/format-message-content.ts::extractTextFromContentPart/extractDisplayableText",
            "test": "lib/format-message-content.test.ts",
        },
        "review": {
            "reviewer": "gpt5_executed_verifier_maintainer_review",
            "gold_status": "admitted_diagnostic_heldout_candidate" if attempt["returncode"] == 0 else "blocked_verifier_failed",
            "verifier_execution_status": "executed_passed" if attempt["returncode"] == 0 else "executed_failed",
            "why_answerable": "The test imports the formatting functions directly, asserts their behavior across several content shapes, and the focused Jest run passes.",
            "not_train_reason": "Disjoint heldout candidate; do not use as support training unless explicitly demoted after evaluation.",
        },
    }
    rows = build_rows(bundle) if attempt["returncode"] == 0 else []
    write_jsonl(OUT_ROWS, rows)
    write_jsonl(OUT_BUNDLES, [bundle])
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": bool(rows),
        "decision": "web_llama_stack_executed_heldout_rows_ready" if rows else "web_llama_stack_heldout_rows_blocked",
        "counts": {
            "bundles": 1,
            "rows": len(rows),
            "rows_by_task": dict(sorted(Counter(r["task_type"] for r in rows).items())),
        },
        "admissibility": {
            "diagnostic_heldout": True,
            "strict_eval_eligible": bool(rows),
            "train_support_only": False,
            "verifier_backed": attempt["returncode"] == 0,
            "root_disjoint_from_stage11347_and_stage11354_training": True,
        },
        "verifier_execution": attempt,
        "source_artifacts": {"stage11346_review_queue": rel(QUEUE)},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(OUT_ROWS), "bundles": rel(OUT_BUNDLES), "logs": rel(LOG_DIR)},
        "recommended_next_action": "Score Stage11200 and diagnostic support runtimes on this disjoint heldout candidate before any training use.",
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
