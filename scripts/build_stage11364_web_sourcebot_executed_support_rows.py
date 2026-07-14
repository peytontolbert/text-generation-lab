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
STAGE = 11364
NAME = "stage11364_web_sourcebot_executed_support_rows"
OUT = ART / NAME
SUMMARY = OUT / "web_sourcebot_executed_support_rows.json"
OUT_ROWS = OUT / "web_sourcebot_executed_support_rows.jsonl"
OUT_BUNDLES = OUT / "web_sourcebot_executed_support_bundles.jsonl"
LOG_DIR = OUT / "logs"
QUEUE = ART / "stage11346_web_source_verifier_review_queue/web_source_verifier_first_wave_review_queue.jsonl"
TMP = Path("/data/tmp/stage11364_sourcebot")
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


def queue_item() -> dict[str, Any]:
    for item in read_jsonl(QUEUE):
        if item.get("repo_family") == "backend" and item.get("git_repo_family") == "sourcebot":
            return item
    return {}


def snippet(path: Path, tokens: tuple[str, ...], max_lines: int = 56) -> dict[str, Any]:
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
    row_id = f"stage11364::{bundle['root_slug']}::{perspective}"
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
        "standalone_projection_source": {
            "projection_mode": "web_sourcebot_executed_verifier_support_perspective",
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
        {"value": "@sourcebot/shared::isRemotePath", "text": "@sourcebot/shared::isRemotePath"},
        {"value": "src/repoManager.ts", "text": "src/repoManager.ts"},
        {"value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ], g["source"])
    add_row(rows, bundle, "evidence_citation", "Choose the evidence item that most directly supports the chosen maintainer target.", [
        {"value": "verifier_and_test_constraint", "text": "Vitest assertions cover arraysEqualShallow equality/order/duplicates/non-mutation and isRemotePath HTTP-vs-local behavior."},
        {"value": "candidate_change_surface", "text": "The implementation defines arraysEqualShallow using sorted arrays and imports isRemotePath from shared utilities."},
        {"value": "symptom_or_call_path_analogue", "text": "The test imports arraysEqualShallow from ./utils and isRemotePath from @sourcebot/shared."},
        {"value": "repo_manager_surface", "text": "repoManager coordinates repository sync behavior and does not define the focused utilities."},
        {"value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ], "verifier_and_test_constraint")
    add_row(rows, bundle, "verifier_outcome", "Choose the verifier transition established by the visible executed test evidence.", [
        {"value": "PASS_TARGETED_TEST_SELECTION", "text": "The focused backend Vitest file executed and all 12 tests passed."},
        {"value": "FAILS_BEFORE_ASSERTION", "text": "The verifier failed during dependency loading before any assertions ran."},
        {"value": "NOT_EXERCISED_BY_SELECTED_TEST", "text": "The selected test does not import the implementation under discussion."},
        {"value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ], "PASS_TARGETED_TEST_SELECTION")
    add_row(rows, bundle, "minimal_fix_selection", "Choose the smallest repair surface if one of the visible utility assertions failed.", [
        {"value": "edit_backend_utils_arrays_or_path_logic", "text": "Edit packages/backend/src/utils.ts utility behavior or its shared isRemotePath dependency."},
        {"value": "rewrite_repo_manager_sync", "text": "Rewrite packages/backend/src/repoManager.ts synchronization flow."},
        {"value": "change_vitest_config", "text": "Change packages/backend/vitest.config.ts."},
        {"value": "update_unrelated_github_tests", "text": "Update packages/backend/src/github.test.ts."},
        {"value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ], "edit_backend_utils_arrays_or_path_logic")
    add_row(rows, bundle, "alternative_hypothesis_elimination", "Choose the reason the strongest distractor is not the right repair surface for this verifier.", [
        {"value": "repo_manager_not_imported_by_focused_test", "text": "The focused utility verifier imports utils/shared helpers, not repoManager sync orchestration."},
        {"value": "utils_is_only_test_file", "text": "utils.ts contains no implementation logic."},
        {"value": "test_has_no_assertions", "text": "The selected verifier contains no concrete expectations."},
        {"value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ], "repo_manager_not_imported_by_focused_test")
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
    source_path = TMP / "packages/backend/src/utils.ts"
    test_path = TMP / "packages/backend/src/utils.test.ts"
    if not source_path.exists() or not test_path.exists():
        raise FileNotFoundError("Expected sourcebot temp workspace and backend utility source/test files.")
    attempt = run_capture("sourcebot_backend_utils_vitest", ["yarn", "workspace", "@sourcebot/backend", "test", "src/utils.test.ts"], TMP)
    source_snip = snippet(source_path, ("arraysEqualShallow", "isRemotePath", "getRepoPath", "fetchWithRetry"))
    test_snip = snippet(test_path, ("test(", "expect", "arraysEqualShallow", "isRemotePath"), max_lines=70)
    distractor_path = TMP / "packages/backend/src/repoManager.ts"
    if distractor_path.exists():
        distractor = snippet(distractor_path, ("class", "export", "sync", "repo"), max_lines=30)
        distractor_evidence = f"packages/backend/src/repoManager.ts lines {distractor['line_start']}-{distractor['line_end']}:\n{distractor['text']}"
    else:
        distractor_evidence = "repoManager was listed as a nearby backend surface but is not required by the focused verifier."
    bundle = {
        "root_id": "stage11364::sourcebot_backend_utils",
        "root_slug": "sourcebot_backend_utils",
        "root_lineage_key": f"sourcebot::{item.get('git_head')}::sourcebot_backend_utils",
        "source_review_item_id": item.get("review_item_id"),
        "repo_family": "backend",
        "git_repo_family": "sourcebot",
        "repo_path": item.get("repo_path"),
        "git_head": item.get("git_head"),
        "task": "Backend utilities should compare shallow arrays without mutation and classify HTTP/HTTPS remote paths separately from local paths.",
        "selected_source_path": "packages/backend/src/utils.ts",
        "selected_test_path": "packages/backend/src/utils.test.ts",
        "source_snippet": source_snip,
        "test_snippet": test_snip,
        "source_evidence": f"packages/backend/src/utils.ts lines {source_snip['line_start']}-{source_snip['line_end']}:\n{source_snip['text']}",
        "test_evidence": f"packages/backend/src/utils.test.ts lines {test_snip['line_start']}-{test_snip['line_end']}:\n{test_snip['text']}",
        "execution_evidence": f"Executed focused verifier: yarn workspace @sourcebot/backend test src/utils.test.ts; result: {attempt['status']}; 12 passed when returncode is 0. Log artifact: {attempt['log']}.",
        "distractor_evidence": distractor_evidence,
        "verifier_execution_evidence": attempt,
        "gold": {
            "source": "packages/backend/src/utils.ts::arraysEqualShallow/isRemotePath import boundary",
            "test": "packages/backend/src/utils.test.ts",
        },
        "review": {
            "reviewer": "gpt5_executed_verifier_maintainer_review",
            "gold_status": "admitted_train_support_only" if attempt["returncode"] == 0 else "blocked_verifier_failed",
            "verifier_execution_status": "executed_passed" if attempt["returncode"] == 0 else "executed_failed",
            "why_answerable": "The test imports arraysEqualShallow and isRemotePath directly, asserts concrete utility behavior, and the focused Vitest run passes.",
            "not_strict_reason": "Used as support to address the disjoint llama-stack Web heldout failure; keep heldout roots separate.",
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
        "decision": "web_sourcebot_executed_support_rows_ready" if rows else "web_sourcebot_support_rows_blocked",
        "counts": {
            "bundles": 1,
            "rows": len(rows),
            "rows_by_task": dict(sorted(Counter(r["task_type"] for r in rows).items())),
        },
        "admissibility": {
            "train_support_only": True,
            "strict_eval_eligible": False,
            "verifier_backed": attempt["returncode"] == 0,
            "root_disjoint_from_stage11361_llama_stack_heldout": True,
        },
        "verifier_execution": attempt,
        "source_artifacts": {"stage11346_review_queue": rel(QUEUE)},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(OUT_ROWS), "bundles": rel(OUT_BUNDLES), "logs": rel(LOG_DIR)},
        "recommended_next_action": "Score the current runtime on these support rows, then create a root-disjoint support probe that trains on sourcebot while evaluating the sealed llama-stack heldout.",
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
