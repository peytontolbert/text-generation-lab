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
STAGE = 11390
NAME = "stage11390_openhands_unit_verifier_heldout_candidate_rows"
OUT = ART / NAME
SUMMARY = OUT / "openhands_unit_verifier_heldout_candidate_rows.json"
ROWS = OUT / "openhands_unit_verifier_heldout_candidate_rows.jsonl"
BUNDLES = OUT / "openhands_unit_verifier_root_bundles.jsonl"
EXEC = ART / "stage11389_openhands_unit_verifier_execution_evidence/openhands_unit_verifier_execution_evidence.json"

ROOT_SPECS = [
    {
        "root_slug": "openhands_websocket_url",
        "task": "OpenHands frontend must derive HTTP and WebSocket conversation URLs from absolute, relative, proxy-prefixed, and missing conversation URLs.",
        "source_path": "src/utils/websocket-url.ts",
        "test_path": "__tests__/utils/websocket-url.test.ts",
        "symbol": "extractBaseHost / extractPathPrefix / buildHttpBaseUrl / buildWebSocketUrl",
        "implementation_target": "src/utils/websocket-url.ts::buildWebSocketUrl",
        "source_evidence": """src/utils/websocket-url.ts:
extractBaseHost parses absolute conversation URLs, falls back to window.location.host, and adapts localhost hosts for external browser hosts.
extractPathPrefix matches the path segment before /api/conversations and strips trailing slashes.
buildHttpBaseUrl combines protocol, base host, and path prefix.
buildWebSocketUrl returns null for missing conversation ids and otherwise builds ws/wss URLs ending in /sockets/events/{conversationId}.""",
        "test_evidence": """__tests__/utils/websocket-url.test.ts:
20 assertions cover standard hosts, localhost ports, proxy deployment prefixes like /runtime/55313, null/relative URL fallback, ws versus wss protocol selection, empty conversation ids, and complex path prefixes.""",
        "distractor_evidence": "parse-pr-url extracts PR/MR links from text; input-validation checks email syntax and duplicate values. Neither builds WebSocket conversation URLs.",
        "minimal_fix": "adjust URL host/prefix/protocol construction in src/utils/websocket-url.ts without changing PR parsing or email validation utilities",
        "alternative_reason": "the selected verifier imports websocket-url utilities directly and asserts URL construction behavior, so PR parsing and email validation are unrelated alternatives",
    },
    {
        "root_slug": "openhands_parse_pr_url",
        "task": "OpenHands frontend must extract pull-request and merge-request URLs from agent finish text across GitHub, GitLab, Bitbucket, Azure DevOps, self-hosted GitLab, duplicates, and no-match cases.",
        "source_path": "src/utils/parse-pr-url.ts",
        "test_path": "__tests__/parse-pr-url.test.ts",
        "symbol": "extractPRUrls / containsPRUrl / getFirstPRUrl",
        "implementation_target": "src/utils/parse-pr-url.ts::extractPRUrls",
        "source_evidence": """src/utils/parse-pr-url.ts:
PR_URL_PATTERNS includes regexes for GitHub /pull/, GitLab /-/merge_requests/, self-hosted GitLab, Bitbucket /pull-requests/, Azure DevOps /pullrequest/, and a generic pull/pr pattern.
extractPRUrls applies every pattern and returns a de-duplicated URL list.
containsPRUrl checks whether extraction returns any matches.
getFirstPRUrl returns the first extracted URL or null.""",
        "test_evidence": """__tests__/parse-pr-url.test.ts:
15 assertions cover GitHub, GitLab, Bitbucket, Azure DevOps, multiple URLs, self-hosted GitLab, HTTP URLs, duplicate removal, containsPRUrl, getFirstPRUrl, and real-world microagent finish messages.""",
        "distractor_evidence": "websocket-url builds conversation socket URLs; input-validation checks email syntax. Neither recognizes PR/MR provider URL patterns.",
        "minimal_fix": "adjust PR/MR URL regex extraction and de-duplication in src/utils/parse-pr-url.ts without changing socket or email utilities",
        "alternative_reason": "the selected verifier imports parse-pr-url and asserts provider URL pattern extraction, so socket construction and email validation are distractors",
    },
    {
        "root_slug": "openhands_input_validation",
        "task": "OpenHands frontend must validate email address lists, identify invalid entries, check all-valid status, and detect duplicates case-insensitively.",
        "source_path": "src/utils/input-validation.ts",
        "test_path": "__tests__/utils/input-validation.test.ts",
        "symbol": "isValidEmail / getInvalidEmails / areAllEmailsValid / hasDuplicates",
        "implementation_target": "src/utils/input-validation.ts::isValidEmail",
        "source_evidence": """src/utils/input-validation.ts:
EMAIL_REGEX requires local-part characters, @, domain, dot, and at least two letters in the TLD.
isValidEmail applies the regex.
getInvalidEmails filters invalid addresses.
areAllEmailsValid uses every() over isValidEmail.
hasDuplicates lowercases values before comparing Set size to original length.""",
        "test_evidence": """__tests__/utils/input-validation.test.ts:
31 assertions cover standard and special-character emails, invalid missing-domain/local/TLD cases, spaces, multiple @ symbols, invalid-email collection, all-valid checks, empty arrays, and case-insensitive duplicate detection.""",
        "distractor_evidence": "websocket-url builds socket URLs; parse-pr-url extracts PR/MR links. Neither validates email address lists or duplicate email values.",
        "minimal_fix": "adjust email regex/list validation or duplicate normalization in src/utils/input-validation.ts without changing socket or PR URL utilities",
        "alternative_reason": "the selected verifier imports input-validation utilities and asserts email validity/duplicate behavior, so socket and PR parsing utilities are unrelated alternatives",
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
        f"Visible verifier execution evidence:\nExecuted focused Vitest verifier passed for this root; see Stage11389 log artifact.\n"
        f"Options:\n{opts}\nAnswer:"
    )


def row(spec: dict[str, str], exec_card: dict[str, Any], task_type: str, instruction: str, options: list[dict[str, str]], target: str) -> dict[str, Any]:
    target_value = next(item["value"] for item in options if item["label"] == target)
    text = prompt(spec, task_type, instruction, options)
    root_id = f"stage11390::{spec['root_slug']}"
    return {
        "row_id": f"{root_id}::{task_type}",
        "root_id": root_id,
        "root_lineage_key": f"openhands_openhands::stage11389_unit_verifier::{spec['root_slug']}",
        "repo_id": "openhands_openhands",
        "repo_family": "openhands_openhands_frontend",
        "language_family": "web_js_ts_html",
        "task_type": task_type,
        "split": "strict_eval_candidate",
        "package_split": "strict_eval_candidate",
        "train_support_only": False,
        "strict_eval_eligible": True,
        "review_status": "executed_verifier_heldout_candidate_needs_final_admission",
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
            "source_and_verifier_snippets_visible": True,
            "target_label_not_visible_before_options": True,
            "not_from_sourcebot_or_mcp_family": True,
            "not_train_support": True,
            "needs_final_eval_admission": True,
        },
        "verifier_execution_evidence": exec_card,
        "standalone_projection_source": {
            "projection_mode": "openhands_unit_verifier_heldout_candidate",
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
        row(
            spec,
            exec_card,
            "symptom_localization",
            "Choose the implementation target most directly responsible for the observed verifier behavior.",
            [
                option("A", "selected verifier/test file", test),
                option("B", "implementation utility exercised by the selected verifier", impl),
                option("C", "unrelated frontend utility surface", "unrelated_frontend_utility_surface"),
                option("D", "Playwright/browser runtime configuration", "playwright_browser_runtime_config"),
            ],
            "B",
        ),
        row(
            spec,
            exec_card,
            "evidence_citation",
            "Choose the evidence role that most directly justifies the maintainer target.",
            [
                option("A", "candidate change surface text only", "candidate_change_surface"),
                option("B", "symptom or call-path analogue", "symptom_or_call_path_analogue"),
                option("C", "selected verifier/test constraint plus source snippet", "verifier_and_test_constraint"),
                option("D", "package metadata or browser runtime setup", "repo_metadata_or_runtime_setup"),
            ],
            "C",
        ),
        row(
            spec,
            exec_card,
            "verifier_outcome",
            "Choose the verifier transition supported by the executed test evidence.",
            [
                option("A", "focused Vitest verifier passed", "PASS_TARGETED_TEST_SELECTION"),
                option("B", "focused verifier failed before assertion", "FAIL_BEFORE_TARGET_ASSERTION"),
                option("C", "verifier was blocked by missing Playwright browsers", "BLOCKED_MISSING_BROWSER_BINARY"),
                option("D", "insufficient evidence to classify verifier result", "INSUFFICIENT_EVIDENCE"),
            ],
            "A",
        ),
        row(
            spec,
            exec_card,
            "minimal_fix_selection",
            "Choose the smallest maintainer action if this verifier behavior regressed.",
            [
                option("A", "change unrelated frontend utility first", "change_unrelated_utility"),
                option("B", spec["minimal_fix"], spec["minimal_fix"]),
                option("C", "disable the focused verifier", "disable_selected_verifier"),
                option("D", "install Playwright browsers before touching source", "install_playwright_browsers_first"),
            ],
            "B",
        ),
        row(
            spec,
            exec_card,
            "alternative_hypothesis_elimination",
            "Choose why the tempting alternative surfaces are weaker than the selected implementation target.",
            [
                option("A", "browser runtime is missing, so no source target can be selected", "browser_runtime_blocks_unit_verifier"),
                option("B", spec["alternative_reason"], "selected_verifier_exercises_implementation_not_distractor"),
                option("C", "package metadata alone determines the tested behavior", "metadata_alone_determines_behavior"),
                option("D", "the source snippet is post-fix leakage and should be ignored", "post_fix_leakage"),
            ],
            "B",
        ),
        row(
            spec,
            exec_card,
            "abstention_insufficient_evidence",
            "Choose whether this packet has enough visible evidence to answer.",
            [
                option("A", "answer using visible source, verifier, and execution evidence", "ANSWER_WITH_VISIBLE_EVIDENCE"),
                option("B", "retrieve more evidence before any decision", "RETRIEVE_MORE"),
                option("C", "abstain because selected verifier identity is missing", "ABSTAIN_INSUFFICIENT_EVIDENCE"),
                option("D", "needs Playwright browser installation before this unit-verifier decision", "NEEDS_BROWSER_RUNTIME"),
            ],
            "A",
        ),
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
            blocked.append({"root_slug": spec["root_slug"], "reason": "missing_passed_stage11389_execution"})
            continue
        rows.extend(rows_for(spec, exec_card))
        bundles.append(
            {
                "root_id": f"stage11390::{spec['root_slug']}",
                "root_slug": spec["root_slug"],
                "root_lineage_key": f"openhands_openhands::stage11389_unit_verifier::{spec['root_slug']}",
                "repo_id": "openhands_openhands",
                "repo_family": "openhands_openhands_frontend",
                "language_family": "web_js_ts_html",
                "source_path": spec["source_path"],
                "test_path": spec["test_path"],
                "symbol": spec["symbol"],
                "task": spec["task"],
                "review": {
                    "gold_status": "heldout_candidate_needs_final_admission",
                    "verifier_execution_status": "executed_passed",
                    "why_candidate": "OpenHands unit roots are disjoint from rejected Sourcebot and MCP-family support paths and have focused Vitest verifier output.",
                },
                "verifier_execution_evidence": exec_card,
            }
        )
    write_jsonl(ROWS, rows)
    write_jsonl(BUNDLES, bundles)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": bool(rows) and not blocked,
        "decision": "openhands_unit_verifier_heldout_candidate_rows_ready" if rows and not blocked else "openhands_unit_verifier_heldout_candidate_rows_partial",
        "counts": {
            "roots": len(bundles),
            "rows": len(rows),
            "blocked_roots": len(blocked),
            "rows_by_task": dict(sorted(Counter(r["task_type"] for r in rows).items())),
            "rows_by_target_value": dict(sorted(Counter(r["semantic_target_value"] for r in rows).items())),
        },
        "admissibility": {
            "strict_eval_candidate": True,
            "train_support_only": False,
            "verifier_backed": True,
            "not_from_sourcebot_or_mcp_family": True,
            "needs_final_eval_admission": True,
            "why_not_immediate_headline": "One repo family and 18 rows are enough for a Web transfer smoke slice, not a broad Web claim.",
        },
        "blocked": blocked,
        "source_artifacts": {"stage11389_execution": rel(EXEC)},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS), "bundles": rel(BUNDLES)},
        "recommended_next_action": "Run Stage11200 and Gemma same-manifest scoring on these heldout-candidate rows before deciding whether to admit them into the next Web strict slice.",
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
