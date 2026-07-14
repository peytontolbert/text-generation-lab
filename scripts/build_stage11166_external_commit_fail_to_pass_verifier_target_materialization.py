#!/usr/bin/env python3
"""Materialize external commit-backed FAIL_TO_PASS verifier-target candidates.

This targets the remaining strict miss shape more directly than transition
classification: all options are FAIL_TO_PASS, and the model must choose which
verifier target is causally supported by the visible repair/commit evidence.

Rows are review candidates.  They use historical COMMIT_PLUS_VERIFY metadata
and git snapshots/diffs from mounted /arxiv repositories; they do not claim a
fresh runtime test execution.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/local/artifacts/external_repo_commit_family_scale/filtered_selected_repo_commit_episodes_testtouch_top40_strict.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts/stage11166_external_commit_fail_to_pass_verifier_target_materialization"
CURRENT_PACKAGE_DIR = ROOT / "runs/local/artifacts/stage11146_singleton_strict_quarantine_successor"
LABELS = list("ABCDEFGH")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def run_git(repo_root: Path, args: list[str], timeout: int = 30) -> dict[str, Any]:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "args": ["git", "-C", str(repo_root), *args],
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def git_text(repo_root: Path, spec: str, max_chars: int = 1600) -> str:
    result = run_git(repo_root, ["show", spec], timeout=20)
    if result["returncode"] != 0:
        return ""
    return result["stdout"][:max_chars].strip()


def compact(text: str, max_chars: int = 1200) -> str:
    return " ".join(text.split())[:max_chars]


def package_roots() -> set[str]:
    roots = set()
    for name in [
        "agentkernel_lite_encdec_train.jsonl",
        "agentkernel_lite_encdec_validation.jsonl",
        "agentkernel_lite_encdec_strict_eval.jsonl",
        "agentkernel_lite_encdec_stress_eval.jsonl",
    ]:
        for row in read_jsonl(CURRENT_PACKAGE_DIR / name):
            if row.get("source_root_id"):
                roots.add(str(row["source_root_id"]))
    return roots


def context_by_role(episode: dict[str, Any], role: str) -> list[dict[str, Any]]:
    return [row for row in episode.get("context_rows", []) if row.get("role") == role]


def first_context_text(episode: dict[str, Any], *, path: str | None = None, role: str | None = None) -> str:
    for row in episode.get("context_rows", []):
        if path and row.get("path") != path and row.get("doc_id") != path:
            continue
        if role and row.get("role") != role:
            continue
        text = row.get("text")
        if isinstance(text, str) and text.strip():
            return compact(text)
    return ""


def option_shuffle(row_id: str, values: list[str]) -> list[dict[str, str]]:
    keyed = []
    for i, value in enumerate(values):
        digest = hashlib.sha256(f"{row_id}::{i}::{value}".encode()).hexdigest()
        keyed.append((digest, value))
    return [{"label": label, "value": value} for label, (_, value) in zip(LABELS, sorted(keyed))]


def repo_relative_test(repo_id: str, selected_test: str) -> str:
    prefix = f"{repo_id}/"
    return selected_test[len(prefix) :] if selected_test.startswith(prefix) else selected_test


def make_row(episode: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    blockers: list[str] = []
    repo_id = str(episode.get("repo_id") or "")
    metadata = episode.get("source_metadata") if isinstance(episode.get("source_metadata"), dict) else {}
    commit = str(metadata.get("commit_sha") or "")
    repo_root = Path(str(metadata.get("repo_root") or ""))
    selected_tests = list(episode.get("selected_tests") or [])
    changes = [str(change.get("path") or "") for change in episode.get("changes", []) if isinstance(change, dict)]
    root_id = f"stage11166::external_commit::{repo_id}::{commit}"

    if not repo_id:
        blockers.append("missing_repo_id")
    if not commit:
        blockers.append("missing_commit_sha")
    if not repo_root.exists():
        blockers.append("repo_root_missing")
    if len(selected_tests) != 1:
        blockers.append("requires_single_selected_test_for_unambiguous_target")
    if not changes:
        blockers.append("missing_changed_files")
    if blockers:
        return None, blockers

    selected_test = selected_tests[0]
    selected_rel = repo_relative_test(repo_id, selected_test)
    row_id = f"{root_id}::verifier_outcome_fail_to_pass_target::review_candidate"
    changed_non_tests = [path for path in changes if "test" not in path.lower()]
    selected_context = first_context_text(episode, path=selected_test, role="verification_constraint")
    if not selected_context:
        selected_context = first_context_text(episode, path=selected_rel, role="verification_constraint")
    changed_context = first_context_text(episode, path=changes[0], role="seed_change")
    if not selected_context:
        blockers.append("missing_selected_test_context")
    if not changed_context and changed_non_tests:
        changed_context = git_text(repo_root, f"{commit}:{changed_non_tests[0]}", max_chars=1200)
    show_summary = run_git(repo_root, ["show", "--stat", "--oneline", "--no-renames", commit], timeout=20)
    if show_summary["returncode"] != 0:
        blockers.append("git_show_commit_failed")
    target_state = episode.get("target", {}).get("state_after", {}) if isinstance(episode.get("target"), dict) else {}
    verification_targets = list(target_state.get("verification_targets") or selected_tests)
    if selected_test not in verification_targets:
        blockers.append("selected_test_not_in_verification_targets")
    if blockers:
        return None, blockers

    distractor_1 = changed_non_tests[0] if changed_non_tests else (changes[0] if changes else "unknown_changed_file")
    neighbor_tests = [
        str(row.get("path") or row.get("doc_id") or "")
        for row in context_by_role(episode, "test_neighbor")
        if str(row.get("path") or row.get("doc_id") or "") and str(row.get("path") or row.get("doc_id") or "") != selected_test
    ]
    distractor_2 = neighbor_tests[0] if neighbor_tests else (changes[-1] if changes[-1] != selected_rel else "unlisted_neighbor_test")
    values = [
        f"T1 | FAIL_TO_PASS | selected verifier target {selected_test}",
        f"T2 | FAIL_TO_PASS | changed implementation/config surface {distractor_1}",
        f"T3 | FAIL_TO_PASS | nearby or tempting verifier target {distractor_2}",
        "T4 | FAIL_TO_PASS | unrelated artifact path not supported by commit-plus-verify evidence",
    ]
    options = option_shuffle(row_id, values)
    target_value = values[0]
    target_label = next(opt["label"] for opt in options if opt["value"] == target_value)
    prompt = (
        "Language: python\n"
        "Perspective: verifier_outcome\n"
        "Task: Choose the verifier target most directly expected to flip from FAIL to PASS if the visible commit-level repair is recreated. "
        "All options use the same transition type; decide from commit evidence, selected verifier targets, changed files, and visible test/source snippets.\n"
        f"Repository: {repo_id}\n"
        f"Commit subject: {metadata.get('commit_subject')}\n"
        f"Commit sha: {commit}\n"
        f"Changed files: {', '.join(changes)}\n"
        f"Verification targets from commit-plus-verify metadata: {', '.join(verification_targets)}\n"
        f"Test selection route: {episode.get('test_selection_route')}\n"
        "Evidence:\n"
        f"E1 commit stat: {compact(show_summary['stdout'], 1000)}\n"
        f"E2 selected verifier snippet [{selected_test}]: {selected_context}\n"
        f"E3 changed surface snippet [{distractor_1}]: {compact(changed_context, 1000)}\n"
        f"E4 expected outcome: {episode.get('target', {}).get('expected_outcome') if isinstance(episode.get('target'), dict) else ''}\n"
        "Verifier target ledger:\n"
        + "\n".join(opt["value"] for opt in options)
        + "\nOptions:\n"
        + "\n".join(f"{opt['label']}. {opt['value']}" for opt in options)
        + "\nAnswer:\n"
    )
    row = {
        "row_id": row_id,
        "source_root_id": root_id,
        "source_bundle_id": root_id,
        "repo_id": repo_id,
        "repo_family": repo_id,
        "language_family": "python",
        "task_type": "verifier_outcome",
        "surface": "maintainer_bundle_compact_bounded_choice",
        "split": "train",
        "split_role": "review_queue_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "selected_test_anchor": True,
        "verifier_anchor": True,
        "objective_family": "bounded_decoder_ce",
        "expected_enabled_loss": "decoder_ce",
        "disable_losses": [],
        "loss_mask": {"decoder_ce": True},
        "input_text": prompt,
        "prompt_text": prompt,
        "target_text": target_label,
        "decoder_text": target_label,
        "target_token_len": 1,
        "opaque_options": options,
        "semantic_target_value": target_value,
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "all_options_same_transition": True,
            "target_label_not_in_prompt_before_options": True,
            "historical_commit_plus_verify_not_runtime_execution": True,
            "selected_test_from_metadata_visible": True,
            "commit_stat_visible": True,
        },
        "standalone_projection_source": {
            "projection_mode": "stage11166_external_commit_fail_to_pass_verifier_target_materialization",
            "source_episode": rel(SOURCE),
            "repo_root": str(repo_root),
            "commit_sha": commit,
            "selected_test": selected_test,
            "changed_files": changes,
            "verification_targets": verification_targets,
            "git_show_stat_returncode": show_summary["returncode"],
        },
    }
    return row, []


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    protected = package_roots()
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for episode in read_jsonl(SOURCE):
        row, reasons = make_row(episode)
        if row is not None and row.get("source_root_id") in protected:
            reasons.append("source_root_overlap_current_package")
            row = None
        if reasons:
            blockers.append({"repo_id": episode.get("repo_id"), "episode_id": episode.get("episode_id"), "blockers": reasons})
        elif row is not None:
            rows.append(row)

    summary = {
        "stage": 11166,
        "stage_name": "external_commit_fail_to_pass_verifier_target_materialization",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "source_episodes": rel(SOURCE),
            "current_package_dir": rel(CURRENT_PACKAGE_DIR),
        },
        "metrics": {
            "input_episodes": len(read_jsonl(SOURCE)),
            "materialized_rows": len(rows),
            "blocked_episodes": len(blockers),
            "unique_roots": len({row.get("source_root_id") for row in rows}),
            "target_label_counts": dict(sorted(Counter(str(row.get("target_text")) for row in rows).items())),
            "repo_counts": dict(sorted(Counter(str(row.get("repo_id")) for row in rows).items())),
        },
        "blockers": blockers,
        "decision": "review_queue_only_not_train_package",
        "claim_scope": (
            "External commit-backed FAIL_TO_PASS verifier target candidates. These use mounted git snapshots and "
            "historical COMMIT_PLUS_VERIFY metadata, not fresh runtime test execution; admission must preserve that caveat."
        ),
        "outputs": {
            "rows_jsonl": rel(OUT_DIR / "external_commit_fail_to_pass_verifier_target_review_rows.jsonl"),
            "summary_json": rel(OUT_DIR / "external_commit_fail_to_pass_verifier_target_materialization.json"),
        },
    }
    write_jsonl(OUT_DIR / "external_commit_fail_to_pass_verifier_target_review_rows.jsonl", rows)
    (OUT_DIR / "external_commit_fail_to_pass_verifier_target_materialization.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
