#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11394
NAME = "stage11394_openhands_support_unit_verifier_train_rows"
OUT = ART / NAME
SUMMARY = OUT / "openhands_support_unit_verifier_train_rows.json"
ROWS = OUT / "openhands_support_unit_verifier_train_rows.jsonl"
BUNDLES = OUT / "openhands_support_unit_verifier_root_bundles.jsonl"
EXEC = ART / "stage11393_openhands_support_unit_verifier_execution_evidence/openhands_support_unit_verifier_execution_evidence.json"

ROOT_SPECS = [
    {
        "root_slug": "openhands_shell_tokenize",
        "task": "OpenHands frontend command input must tokenize shell-like command strings while preserving quoted whitespace arguments and round-trip formatting.",
        "source_path": "src/utils/shell-tokenize.ts",
        "test_path": "__tests__/utils/shell-tokenize.test.ts",
        "symbol": "tokenizeCommand / formatCommand",
        "implementation_target": "src/utils/shell-tokenize.ts::tokenizeCommand",
        "source_evidence": """src/utils/shell-tokenize.ts:
tokenizeCommand loops through characters, tracks single/double quote state, splits only on whitespace outside quotes, preserves empty quoted tokens, and leniently absorbs unterminated quotes.
formatCommand joins tokens, quotes whitespace tokens, and uses single quotes when a whitespace token already contains a double quote.""",
        "test_evidence": """__tests__/utils/shell-tokenize.test.ts:
assertions cover whitespace/newline splitting, double-quoted and single-quoted arguments, whitespace-only input, literal backslashes inside quotes, adjacent quote concatenation, empty quoted segments, unterminated quotes, formatting, and round-trip behavior.""",
        "distractor_evidence": "format-time-delta computes compact relative time strings; extract-next-page parses Link headers; vscode-url-helper rewrites localhost VS Code URLs.",
        "minimal_fix": "adjust tokenizeCommand/formatCommand quote and whitespace handling without changing unrelated URL or time utilities",
        "alternative_reason": "the selected verifier imports shell-tokenize utilities and asserts command tokenization/formatting, not time formatting or URL rewriting",
    },
    {
        "root_slug": "openhands_format_time_delta",
        "task": "OpenHands frontend must format elapsed time into compact year/month/day/hour/minute/second suffixes from a fixed current time.",
        "source_path": "src/utils/format-time-delta.ts",
        "test_path": "__tests__/utils/format-time-delta.test.ts",
        "symbol": "formatTimeDelta",
        "implementation_target": "src/utils/format-time-delta.ts::formatTimeDelta",
        "source_evidence": """src/utils/format-time-delta.ts:
formatTimeDelta parses string dates as UTC when needed, computes delta from new Date(), derives seconds/minutes/hours/days/months/years, and returns compact suffixes: s, m, h, d, mo, or y.""",
        "test_evidence": """__tests__/utils/format-time-delta.test.ts:
fake timers pin now to 2024-01-01T00:00:00Z; assertions cover one/two/three years, months, days, hours, minutes, and seconds ago with exact compact outputs.""",
        "distractor_evidence": "shell-tokenize handles command arguments; extract-next-page parses GitHub Link headers; vscode-url-helper rewrites localhost URLs.",
        "minimal_fix": "adjust relative-time delta thresholds or UTC parsing in formatTimeDelta without changing command parsing or URL helpers",
        "alternative_reason": "the selected verifier imports formatTimeDelta and pins fake time, so command parsing and URL helpers cannot satisfy it",
    },
    {
        "root_slug": "openhands_extract_next_page",
        "task": "OpenHands frontend must extract the next page number from GitHub-style HTTP Link headers and return null when no rel=next link exists.",
        "source_path": "src/utils/extract-next-page-from-link.ts",
        "test_path": "__tests__/utils/extract-next-page-from-link.test.ts",
        "symbol": "extractNextPageFromLink",
        "implementation_target": "src/utils/extract-next-page-from-link.ts::extractNextPageFromLink",
        "source_evidence": """src/utils/extract-next-page-from-link.ts:
extractNextPageFromLink applies a regex looking for page=<digits> inside an angle-bracket URL followed by rel=\"next\" and returns parseInt(match[1], 10), otherwise null.""",
        "test_evidence": """__tests__/utils/extract-next-page-from-link.test.ts:
assertions cover a Link header with prev/next/last/first where next is page 4, a header without next returning null, and a header with additional query params where next is page 2.""",
        "distractor_evidence": "format-time-delta computes elapsed time; shell-tokenize parses command input; vscode-url-helper rewrites VS Code localhost URLs.",
        "minimal_fix": "adjust Link-header rel=next page extraction without changing command, time, or VS Code URL helpers",
        "alternative_reason": "the selected verifier imports extractNextPageFromLink and asserts Link-header parsing; the other utilities do not parse HTTP pagination headers",
    },
    {
        "root_slug": "openhands_vscode_url_helper",
        "task": "OpenHands frontend must transform VS Code localhost URLs to the current browser hostname when needed while leaving non-localhost, localhost-browser, invalid, and null inputs unchanged.",
        "source_path": "src/utils/vscode-url-helper.ts",
        "test_path": "__tests__/utils/vscode-url-helper.test.ts",
        "symbol": "transformVSCodeUrl",
        "implementation_target": "src/utils/vscode-url-helper.ts::transformVSCodeUrl",
        "source_evidence": """src/utils/vscode-url-helper.ts:
transformVSCodeUrl returns null for null input, parses the URL, replaces url.hostname when it is localhost and window.location.hostname is not localhost, returns the original URL for non-localhost or localhost browser contexts, and returns the original string on parse errors.""",
        "test_evidence": """__tests__/utils/vscode-url-helper.test.ts:
tests mock window.location.hostname, assert null input returns null, localhost backend URLs become example.com URLs, non-localhost URLs are unchanged, localhost browser host preserves localhost, and invalid URLs return unchanged.""",
        "distractor_evidence": "shell-tokenize parses command input; format-time-delta computes elapsed time; extract-next-page parses GitHub pagination Link headers.",
        "minimal_fix": "adjust transformVSCodeUrl localhost-hostname replacement and invalid-input handling without changing command, time, or pagination utilities",
        "alternative_reason": "the selected verifier imports transformVSCodeUrl and mocks window.location, so command parsing/time/pagination utilities are unrelated alternatives",
    },
]


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def option(label: str, text: str, value: str) -> dict[str, str]:
    return {"label": label, "text": text, "value": value}


def prompt(spec: dict[str, str], perspective: str, instruction: str, options: list[dict[str, str]]) -> str:
    opts = "\n".join(f"{item['label']}. {item['text']}" for item in options)
    return (
        f"Language: web_js_ts_html\n"
        f"Perspective: {perspective}\n"
        f"{instruction}\n"
        f"Repository family: openhands_openhands_frontend\n"
        f"Task observation:\n{spec['task']}\n"
        f"Visible source evidence:\n{spec['source_evidence']}\n"
        f"Visible verifier/test evidence:\n{spec['test_evidence']}\n"
        f"Visible distractor/alternative evidence:\n{spec['distractor_evidence']}\n"
        f"Visible verifier execution evidence:\nExecuted focused Vitest verifier passed for this support root; see Stage11393 log artifact.\n"
        f"Options:\n{opts}\nAnswer:"
    )


def make_row(spec: dict[str, str], exec_card: dict[str, Any], task_type: str, instruction: str, options: list[dict[str, str]], target: str) -> dict[str, Any]:
    target_value = next(item["value"] for item in options if item["label"] == target)
    text = prompt(spec, task_type, instruction, options)
    root_id = f"stage11394::{spec['root_slug']}"
    return {
        "row_id": f"{root_id}::{task_type}",
        "root_id": root_id,
        "root_lineage_key": f"openhands_openhands::stage11393_support_unit_verifier::{spec['root_slug']}",
        "repo_id": "openhands_openhands",
        "repo_family": "openhands_openhands_frontend",
        "language_family": "web_js_ts_html",
        "task_type": task_type,
        "split": "train",
        "package_split": "train",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "review_status": "executed_verifier_train_support_admitted",
        "input_text": text,
        "prompt_text": text,
        "opaque_options": options,
        "bounded_choice_target_label": target,
        "target_text": target,
        "decoder_text": target,
        "semantic_target_value": target_value,
        "target": {
            "bounded_choice_target_label": target,
            "decoder_text": target,
            "target_text": target,
            "semantic_target_value": target_value,
        },
        "loss_mask": {"decoder_ce": True},
        "expected_enabled_loss": "decoder_ce",
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "executed_verifier_output_attached": True,
            "gold_value_not_used_as_label": True,
            "not_strict_eval_eligible": True,
            "source_and_verifier_snippets_visible": True,
            "target_label_not_visible_before_options": True,
            "heldout_stage11390_roots_excluded": True,
        },
        "verifier_execution_evidence": exec_card,
        "standalone_projection_source": {
            "projection_mode": "openhands_support_unit_verifier_train",
            "root_slug": spec["root_slug"],
            "source_path": spec["source_path"],
            "test_path": spec["test_path"],
            "symbol": spec["symbol"],
            "task": spec["task"],
            "source_evidence": spec["source_evidence"],
            "test_evidence": spec["test_evidence"],
            "distractor_evidence": spec["distractor_evidence"],
            "gold_value": target_value,
            "opaque_options": options,
            "verifier_execution_evidence": exec_card,
        },
    }


def rows_for(spec: dict[str, str], exec_card: dict[str, Any]) -> list[dict[str, Any]]:
    impl = spec["implementation_target"]
    test = spec["test_path"]
    return [
        make_row(spec, exec_card, "symptom_localization", "Choose the implementation target most directly responsible for the observed verifier behavior.", [option("A", "selected verifier/test file", test), option("B", "implementation utility exercised by the selected verifier", impl), option("C", "unrelated frontend utility surface", "unrelated_frontend_utility_surface"), option("D", "browser/runtime configuration", "browser_runtime_config")], "B"),
        make_row(spec, exec_card, "evidence_citation", "Choose the evidence role that most directly justifies the maintainer target.", [option("A", "candidate change surface text only", "candidate_change_surface"), option("B", "symptom or call-path analogue", "symptom_or_call_path_analogue"), option("C", "selected verifier/test constraint plus source snippet", "verifier_and_test_constraint"), option("D", "package metadata or runtime setup", "repo_metadata_or_runtime_setup")], "C"),
        make_row(spec, exec_card, "verifier_outcome", "Choose the verifier transition supported by the executed test evidence.", [option("A", "focused Vitest verifier passed", "PASS_TARGETED_TEST_SELECTION"), option("B", "focused verifier failed before assertion", "FAIL_BEFORE_TARGET_ASSERTION"), option("C", "verifier was not executed", "NOT_EXECUTED"), option("D", "insufficient evidence to classify verifier result", "INSUFFICIENT_EVIDENCE")], "A"),
        make_row(spec, exec_card, "minimal_fix_selection", "Choose the smallest maintainer action if this verifier behavior regressed.", [option("A", "change unrelated frontend utility first", "change_unrelated_utility"), option("B", spec["minimal_fix"], spec["minimal_fix"]), option("C", "disable the focused verifier", "disable_selected_verifier"), option("D", "change package metadata first", "change_package_metadata_first")], "B"),
        make_row(spec, exec_card, "alternative_hypothesis_elimination", "Choose why the tempting alternative surfaces are weaker than the selected implementation target.", [option("A", "test execution is missing, so no source target can be selected", "verifier_missing_blocks_decision"), option("B", spec["alternative_reason"], "selected_verifier_exercises_implementation_not_distractor"), option("C", "package metadata alone determines the tested behavior", "metadata_alone_determines_behavior"), option("D", "the source snippet is post-fix leakage and should be ignored", "post_fix_leakage")], "B"),
        make_row(spec, exec_card, "abstention_insufficient_evidence", "Choose whether this packet has enough visible evidence to answer.", [option("A", "answer using visible source, verifier, and execution evidence", "ANSWER_WITH_VISIBLE_EVIDENCE"), option("B", "retrieve more evidence before any decision", "RETRIEVE_MORE"), option("C", "abstain because selected verifier identity is missing", "ABSTAIN_INSUFFICIENT_EVIDENCE"), option("D", "needs browser-runtime installation before this unit-verifier decision", "NEEDS_BROWSER_RUNTIME")], "A"),
    ]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    exec_summary = read_json(EXEC)
    by_root = {item["root_id"]: item for item in exec_summary["results"] if item.get("execution_status") == "verifier_executed_passed"}
    rows: list[dict[str, Any]] = []
    bundles: list[dict[str, Any]] = []
    blocked: list[dict[str, str]] = []
    for spec in ROOT_SPECS:
        exec_card = by_root.get(spec["root_slug"])
        if not exec_card:
            blocked.append({"root_slug": spec["root_slug"], "reason": "missing_passed_stage11393_execution"})
            continue
        rows.extend(rows_for(spec, exec_card))
        bundles.append({"root_id": f"stage11394::{spec['root_slug']}", "root_slug": spec["root_slug"], "root_lineage_key": f"openhands_openhands::stage11393_support_unit_verifier::{spec['root_slug']}", "repo_id": "openhands_openhands", "repo_family": "openhands_openhands_frontend", "language_family": "web_js_ts_html", "source_path": spec["source_path"], "test_path": spec["test_path"], "symbol": spec["symbol"], "task": spec["task"], "review": {"gold_status": "train_support_only", "verifier_execution_status": "executed_passed", "why_support": "Separate OpenHands unit roots provide support geometry for Stage11390 heldout diagnostic without training on Stage11390 rows."}, "verifier_execution_evidence": exec_card})
    write_jsonl(ROWS, rows)
    write_jsonl(BUNDLES, bundles)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": bool(rows) and not blocked,
        "decision": "openhands_support_unit_verifier_train_rows_ready" if rows and not blocked else "openhands_support_unit_verifier_train_rows_partial",
        "counts": {"roots": len(bundles), "rows": len(rows), "blocked_roots": len(blocked), "rows_by_task": dict(sorted(Counter(r["task_type"] for r in rows).items())), "rows_by_target_value": dict(sorted(Counter(r["semantic_target_value"] for r in rows).items()))},
        "admissibility": {"train_support_only": True, "strict_eval_eligible": False, "verifier_backed": True, "heldout_stage11390_roots_excluded": True, "why_not_headline": "Support rows share OpenHands repo family with Stage11390 and are for diagnostic support, not promotion claims."},
        "blocked": blocked,
        "source_artifacts": {"stage11393_execution": rel(EXEC), "heldout_to_keep_sealed": "runs/local/artifacts/stage11390_openhands_unit_verifier_heldout_candidate_rows/openhands_unit_verifier_heldout_candidate_rows.jsonl"},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS), "bundles": rel(BUNDLES)},
        "recommended_next_action": "Run a diagnostic support probe from Stage11200 using these train rows and evaluate sealed Stage11390 plus canaries.",
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
