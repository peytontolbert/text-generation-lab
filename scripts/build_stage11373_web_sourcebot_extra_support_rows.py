#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11373
NAME = "stage11373_web_sourcebot_extra_support_rows"
OUT = ART / NAME
SUMMARY = OUT / "web_sourcebot_extra_support_rows.json"
OUT_ROWS = OUT / "web_sourcebot_extra_support_rows.jsonl"
OUT_BUNDLES = OUT / "web_sourcebot_extra_support_bundles.jsonl"
LOG_DIR = OUT / "logs"
QUEUE = ART / "stage11346_web_source_verifier_review_queue/web_source_verifier_first_wave_review_queue.jsonl"
TMP = Path("/data/tmp/stage11364_sourcebot")
LABELS = list("ABCDEFGH")

ROOT_SPECS = [
    {
        "slug": "sourcebot_backend_github_exclusion",
        "source": "packages/backend/src/github.ts",
        "test": "packages/backend/src/github.test.ts",
        "cmd_test": "src/github.test.ts",
        "tests_passed": "8 passed",
        "task": "GitHub repository filtering should exclude repositories without clone URLs and apply fork, archived, topic, size, and repo-name include/exclude rules.",
        "source_gold": "packages/backend/src/github.ts::shouldExcludeRepo",
        "minimal_fix": "edit_github_should_exclude_repo_filter_logic",
        "distractor": "packages/backend/src/gitlab.ts",
        "distractor_value": "gitlab_project_filter_surface",
        "not_distractor": "gitlab_filter_not_imported_by_github_verifier",
        "snippet_tokens": ("shouldExcludeRepo", "include", "exclude", "topics", "fork"),
    },
    {
        "slug": "sourcebot_backend_gitlab_exclusion",
        "source": "packages/backend/src/gitlab.ts",
        "test": "packages/backend/src/gitlab.test.ts",
        "cmd_test": "src/gitlab.test.ts",
        "tests_passed": "5 passed",
        "task": "GitLab project filtering should apply archived, fork, and user-owned-project exclusion rules to project metadata.",
        "source_gold": "packages/backend/src/gitlab.ts::shouldExcludeProject",
        "minimal_fix": "edit_gitlab_should_exclude_project_filter_logic",
        "distractor": "packages/backend/src/github.ts",
        "distractor_value": "github_repo_filter_surface",
        "not_distractor": "github_filter_not_imported_by_gitlab_verifier",
        "snippet_tokens": ("shouldExcludeProject", "exclude", "archived", "fork", "namespace"),
    },
]


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


def queue_item() -> dict[str, Any]:
    for item in read_jsonl(QUEUE):
        if item.get("repo_family") == "backend" and item.get("git_repo_family") == "sourcebot":
            return item
    return {}


def run_capture(name: str, cmd: list[str], cwd: Path, timeout: int = 120) -> dict[str, Any]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{name}.log"
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    log_path.write_text((proc.stdout or "") + ("\n[stderr]\n" + proc.stderr if proc.stderr else ""))
    return {"name": name, "cmd": cmd, "cwd": str(cwd), "returncode": proc.returncode, "status": "passed" if proc.returncode == 0 else "failed", "log": rel(log_path), "stdout_tail": (proc.stdout or "")[-1400:], "stderr_tail": (proc.stderr or "")[-1400:]}


def snippet(path: Path, tokens: tuple[str, ...], max_lines: int = 58) -> dict[str, Any]:
    lines = path.read_text(errors="replace").splitlines()
    anchors = [i for i, line in enumerate(lines) if any(tok in line for tok in tokens)]
    start = max(0, (anchors[0] if anchors else 0) - 3)
    part = lines[start:start + max_lines]
    text = "\n".join(part)
    return {"path": str(path), "line_start": start + 1, "line_end": start + len(part), "sha256": hashlib.sha256(text.encode()).hexdigest(), "text": text}


def deterministic_options(row_id: str, options: list[dict[str, str]], gold_value: str) -> tuple[list[dict[str, str]], str]:
    ordered = sorted(options, key=lambda o: hashlib.sha256(f"{row_id}:{o['value']}".encode()).hexdigest())
    out, target = [], ""
    for idx, opt in enumerate(ordered):
        item = {"label": LABELS[idx], **opt}
        out.append(item)
        if opt["value"] == gold_value:
            target = LABELS[idx]
    if not target:
        raise ValueError(f"missing gold {gold_value} for {row_id}")
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
    row_id = f"stage11373::{bundle['root_slug']}::{perspective}"
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
        "split": "train",
        "package_split": "train",
        "strict_eval_eligible": False,
        "train_support_only": True,
        "review_status": "ai_executed_verifier_train_support_admitted",
        "input_text": text,
        "prompt_text": text,
        "target_text": target,
        "decoder_text": target,
        "bounded_choice_target_label": target,
        "semantic_target_value": gold_value,
        "opaque_options": options,
        "expected_enabled_loss": "decoder_ce",
        "loss_mask": {"decoder_ce": True},
        "standalone_projection_source": {"projection_mode": "web_sourcebot_extra_executed_support", "gold_value": gold_value, "opaque_options": options, "bundle": bundle},
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "target_label_not_visible_before_options": True,
            "gold_value_not_used_as_label": True,
            "source_and_verifier_snippets_visible": True,
            "executed_verifier_output_attached": True,
            "train_support_only_not_strict": True,
            "root_disjoint_from_stage11361_llama_stack_heldout": True,
        },
    })


def build_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    g = bundle["gold"]
    rows: list[dict[str, Any]] = []
    add_row(rows, bundle, "symptom_localization", "Choose the implementation target most directly responsible for the observed verifier behavior.", [
        {"value": g["source"], "text": g["source"]},
        {"value": g["test"], "text": g["test"]},
        {"value": g["distractor_value"], "text": g["distractor_value"]},
        {"value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ], g["source"])
    add_row(rows, bundle, "evidence_citation", "Choose the evidence item that most directly supports the chosen maintainer target.", [
        {"value": "verifier_and_test_constraint", "text": "Focused verifier assertions exercise the specific repository/project exclusion rules and edge cases."},
        {"value": "candidate_change_surface", "text": "The implementation contains the exclusion predicate and pattern matching checks."},
        {"value": "symptom_or_call_path_analogue", "text": "The test imports the exclusion predicate from the same backend module."},
        {"value": g["distractor_value"], "text": "The opposite provider surface is nearby but not imported by this verifier."},
        {"value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ], "verifier_and_test_constraint")
    add_row(rows, bundle, "verifier_outcome", "Choose the verifier transition established by the visible executed test evidence.", [
        {"value": "PASS_TARGETED_TEST_SELECTION", "text": f"The focused Vitest file executed and all assertions passed: {g['tests_passed']}."},
        {"value": "FAILS_BEFORE_ASSERTION", "text": "The verifier failed during dependency loading before assertions ran."},
        {"value": "NOT_EXERCISED_BY_SELECTED_TEST", "text": "The selected test does not import the implementation under discussion."},
        {"value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ], "PASS_TARGETED_TEST_SELECTION")
    add_row(rows, bundle, "minimal_fix_selection", "Choose the smallest repair surface if one of the visible verifier assertions failed.", [
        {"value": g["minimal_fix"], "text": g["minimal_fix"]},
        {"value": g["distractor_value"], "text": g["distractor_value"]},
        {"value": "change_vitest_config", "text": "change_vitest_config"},
        {"value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ], g["minimal_fix"])
    add_row(rows, bundle, "alternative_hypothesis_elimination", "Choose the reason the strongest distractor is not the right repair surface for this verifier.", [
        {"value": g["not_distractor"], "text": g["not_distractor"]},
        {"value": "selected_test_has_no_assertions", "text": "selected_test_has_no_assertions"},
        {"value": "source_file_is_only_configuration", "text": "source_file_is_only_configuration"},
        {"value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ], g["not_distractor"])
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
    rows: list[dict[str, Any]] = []
    bundles: list[dict[str, Any]] = []
    blocked = []
    for spec in ROOT_SPECS:
        attempt = run_capture(f"{spec['slug']}_vitest", ["yarn", "workspace", "@sourcebot/backend", "test", spec["cmd_test"]], TMP)
        source_path = TMP / spec["source"]
        test_path = TMP / spec["test"]
        distractor_path = TMP / spec["distractor"]
        if attempt["returncode"] != 0 or not source_path.exists() or not test_path.exists():
            blocked.append({"root_slug": spec["slug"], "attempt": attempt, "reason": "verifier_failed_or_missing_files"})
            continue
        source_snip = snippet(source_path, tuple(spec["snippet_tokens"]))
        test_snip = snippet(test_path, ("test(", "expect", "shouldExclude"))
        distractor_snip = snippet(distractor_path, ("shouldExclude", "export", "exclude"), max_lines=30) if distractor_path.exists() else None
        bundle = {
            "root_id": f"stage11373::{spec['slug']}",
            "root_slug": spec["slug"],
            "root_lineage_key": f"sourcebot::{item.get('git_head')}::{spec['slug']}",
            "source_review_item_id": item.get("review_item_id"),
            "repo_family": "backend",
            "git_repo_family": "sourcebot",
            "repo_path": item.get("repo_path"),
            "git_head": item.get("git_head"),
            "task": spec["task"],
            "selected_source_path": spec["source"],
            "selected_test_path": spec["test"],
            "source_snippet": source_snip,
            "test_snippet": test_snip,
            "source_evidence": f"{spec['source']} lines {source_snip['line_start']}-{source_snip['line_end']}:\n{source_snip['text']}",
            "test_evidence": f"{spec['test']} lines {test_snip['line_start']}-{test_snip['line_end']}:\n{test_snip['text']}",
            "execution_evidence": f"Executed focused verifier: yarn workspace @sourcebot/backend test {spec['cmd_test']}; result: {attempt['status']}; {spec['tests_passed']} when returncode is 0. Log artifact: {attempt['log']}.",
            "distractor_evidence": f"{spec['distractor']} lines {distractor_snip['line_start']}-{distractor_snip['line_end']}:\n{distractor_snip['text']}" if distractor_snip else "No distractor snippet available.",
            "verifier_execution_evidence": attempt,
            "gold": {"source": spec["source_gold"], "test": spec["test"], **{k: spec[k] for k in ("minimal_fix", "distractor_value", "not_distractor", "tests_passed")}},
            "review": {"reviewer": "gpt5_executed_verifier_maintainer_review", "gold_status": "admitted_train_support_only", "verifier_execution_status": "executed_passed", "not_strict_reason": "Additional sourcebot support roots; heldout llama-stack remains sealed."},
        }
        bundles.append(bundle)
        rows.extend(build_rows(bundle))
    write_jsonl(OUT_ROWS, rows)
    write_jsonl(OUT_BUNDLES, bundles)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": bool(rows),
        "decision": "web_sourcebot_extra_support_rows_ready" if rows else "web_sourcebot_extra_support_rows_blocked",
        "counts": {"bundles": len(bundles), "rows": len(rows), "blocked": len(blocked), "rows_by_task": dict(sorted(Counter(r["task_type"] for r in rows).items()))},
        "admissibility": {"train_support_only": True, "strict_eval_eligible": False, "verifier_backed": bool(rows), "root_disjoint_from_stage11361_llama_stack_heldout": True},
        "blocked": blocked,
        "source_artifacts": {"stage11346_review_queue": rel(QUEUE)},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(OUT_ROWS), "bundles": rel(OUT_BUNDLES), "logs": rel(LOG_DIR)},
        "recommended_next_action": "Combine Stage11364 and Stage11373 support rows for the next Web support probe, while keeping Stage11361 sealed as heldout.",
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
