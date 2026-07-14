#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11347
NAME = "stage11347_web_static_verifier_maintainer_rows"
OUT = ART / NAME
SUMMARY = OUT / "web_static_verifier_maintainer_rows.json"
OUT_ROWS = OUT / "web_static_verifier_train_support_rows.jsonl"
OUT_BUNDLES = OUT / "web_static_verifier_root_bundles.jsonl"
QUEUE = ART / "stage11346_web_source_verifier_review_queue/web_source_verifier_first_wave_review_queue.jsonl"
LABELS = list("ABCDEFGH")

ROOT_SPECS = [
    {
        "review_item_contains": "qa_lab",
        "root_slug": "qa_model_switch_continuity",
        "task": "A QA handoff checker should accept concise replies that mention a model switch/handoff and kickoff-task continuity, but reject unrelated or over-scoped wrap-ups.",
        "source_path": "src/model-switch-eval.ts",
        "test_path": "src/model-switch-eval.test.ts",
        "symbol": "hasModelSwitchContinuityEvidence",
        "test_focus": "accepts handoff/kickoff confirmations and rejects scope-leak or overlong final-tally text",
        "verifier_transition": "STATIC_PASS_TARGETED_ASSERTIONS",
        "distractor_paths": ["model-selection.ts", "bus-api.ts", "api.ts"],
        "gold": {
            "source": "src/model-switch-eval.ts::hasModelSwitchContinuityEvidence",
            "test": "src/model-switch-eval.test.ts",
            "evidence": "test_assertions_and_predicate_conditions",
            "minimal_fix": "adjust predicate conditions inside hasModelSwitchContinuityEvidence",
            "alternative": "model-selection and bus API exports do not implement the continuity predicate tested here",
            "abstention": "ANSWER_WITH_VISIBLE_EVIDENCE",
        },
    },
    {
        "review_item_contains": "sep_automation",
        "root_slug": "sep_transition_validation",
        "task": "SEP automation should allow valid lifecycle transitions and reject invalid transitions with an Invalid transition reason before mutating GitHub labels.",
        "source_path": "src/actions/transition.ts",
        "test_path": "test/unit/transition.test.ts",
        "symbol": "TransitionHandler.validateTransition",
        "test_focus": "proposal->draft and draft->in-review are valid, proposal->final is invalid, dry-run execution succeeds without GitHub label mutation",
        "verifier_transition": "STATIC_PASS_TARGETED_ASSERTIONS",
        "distractor_paths": ["src/config.ts", "src/types.ts", "src/processor.ts"],
        "gold": {
            "source": "src/actions/transition.ts::TransitionHandler",
            "test": "test/unit/transition.test.ts",
            "evidence": "transition_validation_assertions",
            "minimal_fix": "adjust validateTransition or transition rule lookup, not config loading",
            "alternative": "config/types describe environment and data shape but do not decide transition validity",
            "abstention": "ANSWER_WITH_VISIBLE_EVIDENCE",
        },
    },
    {
        "review_item_contains": "server",
        "root_slug": "mcp_stdio_transport_lifecycle",
        "task": "MCP stdio server transport should not read input until started, should read serialized JSON-RPC messages after start, and should close cleanly.",
        "source_path": "src/server/stdio.ts",
        "test_path": "test/server/stdio.test.ts",
        "symbol": "StdioServerTransport",
        "test_focus": "start registers data/error listeners, processReadBuffer dispatches messages, close clears buffer and calls onclose",
        "verifier_transition": "STATIC_PASS_TARGETED_ASSERTIONS",
        "distractor_paths": ["src/stdio.ts", "tsdown.config.ts", "vitest.config.js"],
        "gold": {
            "source": "src/server/stdio.ts::StdioServerTransport",
            "test": "test/server/stdio.test.ts",
            "evidence": "stdio_transport_lifecycle_assertions",
            "minimal_fix": "adjust StdioServerTransport listener/buffer lifecycle, not the subpath export wrapper",
            "alternative": "src/stdio.ts only re-exports the transport and does not implement listener lifecycle",
            "abstention": "ANSWER_WITH_VISIBLE_EVIDENCE",
        },
    },
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def snippet(path: Path, max_lines: int = 44) -> dict[str, Any]:
    lines = path.read_text(errors="replace").splitlines()
    anchors = [i for i, line in enumerate(lines) if any(tok in line.lower() for tok in ("test(", "it(", "expect", "export", "class", "function", "validate", "start", "close"))]
    start = max(0, (anchors[0] if anchors else 0) - 2)
    part = lines[start:start + max_lines]
    text = "\n".join(part)
    return {
        "repo_relative_path": str(path),
        "line_start": start + 1,
        "line_end": start + len(part),
        "sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
        "text": text,
    }


def find_review_item(queue: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any] | None:
    needle = spec["review_item_contains"]
    for item in queue:
        if needle in item.get("review_item_id", "") or needle in item.get("repo_family", ""):
            return item
    return None


def deterministic_options(row_id: str, options: list[dict[str, Any]], gold_value: str) -> tuple[list[dict[str, Any]], str]:
    ordered = sorted(options, key=lambda o: hashlib.sha256(f"{row_id}:{o['value']}".encode()).hexdigest())
    out = []
    target = ""
    for idx, opt in enumerate(ordered):
        label = LABELS[idx]
        item = {"label": label, **opt}
        out.append(item)
        if opt["value"] == gold_value:
            target = label
    if not target:
        raise ValueError(f"gold value missing for {row_id}: {gold_value}")
    return out, target


def row_prompt(bundle: dict[str, Any], perspective: str, instruction: str, options: list[dict[str, Any]]) -> str:
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
        "Visible distractor/alternative evidence:",
        bundle["distractor_evidence"],
        "Options:",
    ]
    lines.extend(f"{opt['label']}. {opt['text']}" for opt in options)
    lines.append("Answer:")
    return "\n".join(lines)


def add_row(rows: list[dict[str, Any]], bundle: dict[str, Any], perspective: str, instruction: str, raw_options: list[dict[str, Any]], gold_value: str) -> None:
    row_id = f"stage11347::{bundle['root_slug']}::{perspective}"
    options, target = deterministic_options(row_id, raw_options, gold_value)
    text = row_prompt(bundle, perspective, instruction, options)
    rows.append({
        "row_id": row_id,
        "root_id": bundle["root_id"],
        "root_lineage_key": bundle["root_lineage_key"],
        "source_review_item_id": bundle["source_review_item_id"],
        "language_family": "web_js_ts_html",
        "repo_family": bundle["repo_family"],
        "repo_id": bundle["git_repo_family"],
        "task_type": perspective,
        "split": "train",
        "package_split": "train",
        "strict_eval_eligible": False,
        "train_support_only": True,
        "review_status": "ai_static_verifier_review_admitted_train_support_only",
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
            "projection_mode": "web_static_verifier_maintainer_perspective",
            "gold_value": gold_value,
            "opaque_options": options,
            "bundle": bundle,
        },
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "target_label_not_visible_before_options": True,
            "gold_value_not_used_as_label": True,
            "source_and_verifier_snippets_visible": True,
            "static_verifier_not_executed": True,
            "not_strict_eval_eligible": True,
        },
    })


def make_bundle(item: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    repo = Path(item["repo_path"])
    source = repo / spec["source_path"]
    test = repo / spec["test_path"]
    distractors = [repo / p for p in spec.get("distractor_paths", []) if (repo / p).exists()]
    if not source.exists() or not test.exists():
        raise FileNotFoundError((source, test))
    source_snip = snippet(source)
    test_snip = snippet(test)
    dist_texts = []
    for path in distractors[:2]:
        snip = snippet(path, max_lines=18)
        dist_texts.append(f"{path.relative_to(repo)} lines {snip['line_start']}-{snip['line_end']}:\n{snip['text']}")
    return {
        "root_id": f"stage11347::{spec['root_slug']}",
        "root_slug": spec["root_slug"],
        "root_lineage_key": f"{item['git_repo_family']}::{item['git_head']}::{spec['root_slug']}",
        "source_review_item_id": item["review_item_id"],
        "repo_family": item["repo_family"],
        "git_repo_family": item["git_repo_family"],
        "repo_path": item["repo_path"],
        "git_head": item["git_head"],
        "task": spec["task"],
        "symbol": spec["symbol"],
        "test_focus": spec["test_focus"],
        "verifier_transition": spec["verifier_transition"],
        "selected_source_path": spec["source_path"],
        "selected_test_path": spec["test_path"],
        "source_snippet": source_snip,
        "test_snippet": test_snip,
        "source_evidence": f"{spec['source_path']} lines {source_snip['line_start']}-{source_snip['line_end']}:\n{source_snip['text']}",
        "test_evidence": f"{spec['test_path']} lines {test_snip['line_start']}-{test_snip['line_end']}:\n{test_snip['text']}",
        "distractor_evidence": "\n---\n".join(dist_texts) if dist_texts else "No stronger distractor evidence was selected for this static review root.",
        "gold": spec["gold"],
        "review": {
            "reviewer": "gpt5_static_maintainer_review",
            "gold_status": "admitted_train_support_only",
            "verifier_execution_status": "not_executed_static_assertion_recovered",
            "why_answerable": "The visible test assertions import or exercise the named implementation symbol and the visible source snippet contains the relevant behavior boundary.",
            "not_promotable_reason": "No fresh runtime verifier execution was captured for this stage.",
        },
    }


def build_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    g = bundle["gold"]
    rows: list[dict[str, Any]] = []
    add_row(rows, bundle, "symptom_localization", "Choose the implementation target most directly responsible for the observed verifier behavior.", [
        {"value": g["source"], "text": g["source"]},
        {"value": g["test"], "text": g["test"]},
        {"value": "configuration_or_build_wrapper", "text": "configuration/build wrapper surface"},
        {"value": "unrelated_export_or_type_surface", "text": "nearby export/type surface not implementing the tested behavior"},
    ], g["source"])
    add_row(rows, bundle, "evidence_citation", "Choose the evidence item that most directly supports the maintainer decision.", [
        {"value": g["evidence"], "text": "test assertions plus implementation predicate/lifecycle evidence"},
        {"value": "candidate_change_surface_only", "text": "changed implementation file path without verifier assertions"},
        {"value": "config_presence_only", "text": "build or config file exists"},
        {"value": "background_type_shape_only", "text": "type declarations or exports without behavioral assertions"},
    ], g["evidence"])
    add_row(rows, bundle, "verifier_outcome", "Choose the verifier transition supported by the visible static test assertions.", [
        {"value": bundle["verifier_transition"], "text": f"targeted static assertions should pass if {bundle['symbol']} keeps the visible behavior"},
        {"value": "NOT_EXERCISED", "text": "the selected test does not exercise the implementation symbol"},
        {"value": "INSUFFICIENT_EVIDENCE", "text": "the visible evidence is insufficient to predict the target verifier"},
        {"value": "CONFIG_ONLY_FAILURE", "text": "the failure is only a config/build wrapper issue"},
    ], bundle["verifier_transition"])
    add_row(rows, bundle, "minimal_fix_selection", "Choose the smallest likely repair surface if the shown verifier assertions fail.", [
        {"value": g["minimal_fix"], "text": g["minimal_fix"]},
        {"value": "rewrite_all_tests", "text": "rewrite the test expectations first"},
        {"value": "change_package_config", "text": "change package/build config before inspecting implementation"},
        {"value": "edit_unrelated_exports", "text": "edit nearby export wrappers or type declarations"},
    ], g["minimal_fix"])
    add_row(rows, bundle, "alternative_hypothesis_elimination", "Choose the reason the plausible distractor target is weaker than the selected implementation target.", [
        {"value": g["alternative"], "text": g["alternative"]},
        {"value": "test_is_obviously_stale", "text": "the test is visibly stale and should be changed first"},
        {"value": "config_controls_all_behavior", "text": "configuration alone controls the tested behavior"},
        {"value": "no_visible_relation", "text": "there is no visible relation between test and implementation"},
    ], g["alternative"])
    add_row(rows, bundle, "abstention_insufficient_evidence", "Decide whether the visible evidence is sufficient for a bounded maintainer decision.", [
        {"value": g["abstention"], "text": "answer with visible source and verifier evidence"},
        {"value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "abstain because no test/source relationship is visible"},
        {"value": "RETRIEVE_MORE_BEFORE_ANY_DECISION", "text": "retrieve more before making even a bounded localization decision"},
        {"value": "IGNORE_VERIFIER_USE_FILENAME_ONLY", "text": "ignore verifier evidence and decide from filename only"},
    ], g["abstention"])
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    queue = read_jsonl(QUEUE)
    bundles = []
    rows = []
    blocked = []
    for spec in ROOT_SPECS:
        item = find_review_item(queue, spec)
        if not item:
            blocked.append({"root_slug": spec["root_slug"], "blocker": "missing_stage11346_review_item"})
            continue
        try:
            bundle = make_bundle(item, spec)
            bundles.append(bundle)
            rows.extend(build_rows(bundle))
        except Exception as exc:
            blocked.append({"root_slug": spec["root_slug"], "blocker": type(exc).__name__, "detail": str(exc)})
    write_jsonl(OUT_BUNDLES, bundles)
    write_jsonl(OUT_ROWS, rows)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": bool(rows) and not blocked,
        "decision": "web_static_verifier_maintainer_train_support_rows_ready" if rows else "web_static_verifier_maintainer_rows_blocked",
        "counts": {
            "bundles": len(bundles),
            "rows": len(rows),
            "blocked": len(blocked),
            "rows_by_task": dict(sorted(Counter(r["task_type"] for r in rows).items())),
            "rows_by_repo_family": dict(sorted(Counter(r["repo_family"] for r in rows).items())),
        },
        "admissibility": {
            "train_support_only": True,
            "strict_eval_eligible": False,
            "scoreable_now": True,
            "why_not_promotable": "Verifier assertions were statically recovered from tests, but targeted tests were not executed in this stage.",
        },
        "anti_cheat": {
            "root_split_isolation": "all rows from each root share one train-support root_id",
            "opaque_label_shuffle": True,
            "gold_label_hidden_before_options": True,
            "source_and_verifier_snippets_visible": True,
            "no_reserved_strict_rows_reused": True,
        },
        "blocked": blocked,
        "source_artifacts": {"stage11346_queue": rel(QUEUE)},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(OUT_ROWS), "bundles": rel(OUT_BUNDLES)},
        "recommended_next_action": "Merge these rows into a canary-preserving diagnostic support package, or execute the targeted tests to upgrade the roots from static train-support to verifier-backed admissible rows.",
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
