#!/usr/bin/env python3
"""Build candidate actions and attempt verifier-output joins for Stage12201 records.

No training, tests, network, or repo mutation. This script only joins existing
artifacts and emits level-3 readiness audits. Candidate actions are deterministic
and grounded in recovered diff metadata plus selected test intent; they do not by
 themselves make a row level-3. Level-3 requires same-lineage verifier output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def as_path(v: str | Path) -> Path:
    p = Path(v)
    return p if p.is_absolute() else ROOT / p


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield line_no, json.loads(line)
            except Exception as exc:
                yield line_no, {"_json_error": str(exc)}


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [row for _, row in iter_jsonl(path) or []]


def repo_key(value: str) -> str:
    value = value.lower().strip().replace("__", "/").replace("_", "-")
    for prefix in ("/arxiv/repositories/", "https://github.com/"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    return value.strip("/")


def selected_test_command(language: str, selected_tests: list[str]) -> dict[str, Any]:
    first = selected_tests[0] if selected_tests else None
    if not first:
        return {"type": "abstain", "arguments": {"reason": "no_selected_test"}}
    if language == "python":
        return {"type": "run", "arguments": {"cmd": f"pytest {first} -q", "target": first}}
    if language == "rust":
        return {"type": "run", "arguments": {"cmd": "cargo test --locked --offline", "target": first}}
    if language == "c_cpp":
        return {"type": "run", "arguments": {"cmd": f"ctest -R {Path(first).stem} --output-on-failure", "target": first}}
    if language == "web_js_ts_html":
        return {"type": "run", "arguments": {"cmd": f"npm test -- {first}", "target": first}}
    return {"type": "run", "arguments": {"cmd": f"run selected verifier for {first}", "target": first}}


def build_candidate_set(ep: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    selected_tests = ep.get("selected_tests") or []
    changed_paths = ep.get("changed_paths") or []
    first_changed = changed_paths[0] if changed_paths else None
    test_action = selected_test_command(str(ep.get("language") or ""), selected_tests)
    actions = [
        {
            "action_id": "A",
            "type": test_action["type"],
            "arguments": test_action["arguments"],
            "is_chosen": True,
            "semantic_role": "run_selected_verifier_before_or_after_patch",
            "negative_kind": "positive_from_selected_test_intent",
            "plausibility_source": "selected_tests",
        },
        {
            "action_id": "B",
            "type": "inspect",
            "arguments": {"path": first_changed},
            "is_chosen": False,
            "semantic_role": "inspect_changed_surface_only",
            "negative_kind": "semantic_hard_negative",
            "plausibility_source": "changed_paths",
        },
        {
            "action_id": "C",
            "type": "patch",
            "arguments": {"diff_digest": patch.get("diff_digest"), "mode": "apply_known_commit_patch"},
            "is_chosen": False,
            "semantic_role": "patch_before_verifier_interpretation",
            "negative_kind": "semantic_hard_negative",
            "plausibility_source": "diff_metadata",
        },
        {
            "action_id": "D",
            "type": "run",
            "arguments": {"cmd": "run broad test suite", "target": "broad_suite"},
            "is_chosen": False,
            "semantic_role": "overbroad_verifier_first",
            "negative_kind": "semantic_hard_negative",
            "plausibility_source": "generic_repo_maintenance_policy",
        },
        {
            "action_id": "E",
            "type": "abstain",
            "arguments": {"reason": "missing_same_lineage_verifier_output"},
            "is_chosen": False,
            "semantic_role": "abstain_despite_available_selected_test_intent",
            "negative_kind": "semantic_hard_negative",
            "plausibility_source": "missing_verifier_output_audit",
        },
    ]
    return {
        "action_set_id": stable_id("stage12202_action_set", ep.get("episode_id")),
        "episode_id": ep.get("episode_id"),
        "state_id": stable_id("stage12202_state_before", ep.get("episode_id")),
        "chosen_action_id": "A",
        "candidate_action_count": len(actions),
        "semantic_hard_negative_count": sum(1 for a in actions if a.get("negative_kind") == "semantic_hard_negative"),
        "decision_training_ready": False,
        "decision_training_blocker": "chosen_action_is_selected_test_intent_not_observed_executed_action",
        "action_ids": [a["action_id"] for a in actions],
        "hard_negative_action_ids": [a["action_id"] for a in actions if a.get("negative_kind") == "semantic_hard_negative"],
        "candidate_actions": actions,
    }


def scan_verifier_artifacts(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for base in paths:
        if not base.exists():
            continue
        for path in base.rglob("*.jsonl"):
            name = str(path)
            if not any(tok in name for tok in ("results", "trace", "smoke", "execution")):
                continue
            for line_no, row in iter_jsonl(path) or []:
                text = json.dumps(row, sort_keys=True, default=str).lower()
                if any(tok in text for tok in ("exit_code", "returncode", "command", "command_text")):
                    rows.append({"source_path": str(path), "line_no": line_no, "row": row, "text": text})
    return rows


def verifier_join(ep: dict[str, Any], verifier_rows: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    repo = repo_key(str(ep.get("repo_family") or ep.get("root_id") or ""))
    repo_root = str(ep.get("root_id") or "")
    commit = str(ep.get("repo_commit_after") or "").lower()
    selected_tests = [str(t).lower() for t in ep.get("selected_tests") or []]
    candidates = []
    for vr in verifier_rows:
        row = vr["row"]
        text = vr["text"]
        cwd = str(row.get("workdir") or row.get("cwd") or "")
        cmd = str(row.get("command") or row.get("command_text") or row.get("cmd") or "")
        # Same-lineage verifier output must originate inside the recovered repo root.
        # Old analysis commands in this lab often mention external repo/test names in
        # pandas/grep queries; those are not verifier executions for the recovered repo.
        if not repo_root or not cwd.startswith(repo_root):
            continue
        score = 10
        if repo and repo in text:
            score += 2
        if commit and commit in text:
            score += 4
        selected_match = bool(selected_tests and any(t and (t in text or t in cmd.lower()) for t in selected_tests[:8]))
        # Same-repo environment probes are not verifier outputs for this episode.
        # Require the command/log to mention at least one selected verifier target.
        if not selected_match:
            continue
        score += 3
        candidates.append((score, vr))
    candidates.sort(key=lambda item: (-item[0], item[1]["source_path"], item[1]["line_no"]))
    if not candidates:
        return None, {"episode_id": ep.get("episode_id"), "join_status": "rejected", "join_blockers": ["no_same_repo_cwd_verifier_rows"]}
    best_score, best = candidates[0]
    row = best["row"]
    cmd = row.get("command") or row.get("command_text") or row.get("cmd")
    exit_code = row.get("exit_code") if row.get("exit_code") is not None else row.get("returncode")
    if cmd in (None, "") or exit_code is None:
        return None, {
            "episode_id": ep.get("episode_id"),
            "join_status": "rejected",
            "join_blockers": ["candidate_missing_command_or_exit_code"],
            "best_source_path": best["source_path"],
            "best_line_no": best["line_no"],
        }
    return {
        "verifier_id": stable_id("stage12202_verifier", ep.get("episode_id"), best["source_path"], best["line_no"]),
        "episode_id": ep.get("episode_id"),
        "command": cmd,
        "cwd": row.get("workdir") or row.get("cwd"),
        "test_identity": ep.get("selected_tests"),
        "verifier_family": "existing_artifact_command_output_join",
        "returncode": exit_code,
        "status": "PASS_TO_PASS" if int(exit_code) == 0 else "FAIL_OR_ENV_BLOCKED",
        "stdout_digest": stable_id("stdout", row.get("stdout") or row.get("summary_text") or ""),
        "stderr_digest": stable_id("stderr", row.get("stderr") or ""),
        "log_ref": f"{best['source_path']}:{best['line_no']}",
        "same_root_verifier": True,
        "blocked_verifier_reason": None,
        "join_score": best_score,
    }, {"episode_id": ep.get("episode_id"), "join_status": "joined", "join_score": best_score, "source_path": best["source_path"], "line_no": best["line_no"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage12201-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--verifier-search-root", action="append", default=[])
    ap.add_argument("--no-training", action="store_true")
    ap.add_argument("--no-tests", action="store_true")
    ap.add_argument("--no-network", action="store_true")
    ap.add_argument("--no-repo-mutation", action="store_true")
    args = ap.parse_args()
    if not all([args.no_training, args.no_tests, args.no_network, args.no_repo_mutation]):
        raise SystemExit("must pass --no-training --no-tests --no-network --no-repo-mutation")
    stage12201 = as_path(args.stage12201_dir)
    out = as_path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    episodes = load_jsonl(stage12201 / "recovered_episode_records.jsonl")
    patches = {p.get("episode_id"): p for p in load_jsonl(stage12201 / "recovered_patch_traces.jsonl")}
    action_sets = [build_candidate_set(ep, patches.get(ep.get("episode_id"), {})) for ep in episodes]
    roots = [as_path(p) for p in args.verifier_search_root] if args.verifier_search_root else [ROOT / "runs/local/artifacts"]
    verifier_rows = scan_verifier_artifacts(roots)
    verifier_transitions: list[dict[str, Any]] = []
    verifier_join_audit: list[dict[str, Any]] = []
    for ep in episodes:
        joined, audit = verifier_join(ep, verifier_rows)
        verifier_join_audit.append(audit)
        if joined:
            verifier_transitions.append(joined)
    level3_ready = []
    blocked = []
    action_by_ep = {a["episode_id"]: a for a in action_sets}
    verifier_by_ep = {v["episode_id"]: v for v in verifier_transitions}
    for ep in episodes:
        blockers = []
        aset = action_by_ep.get(ep.get("episode_id"))
        if not aset or aset["candidate_action_count"] < 5:
            blockers.append("candidate_action_set_fewer_than_5")
        if not aset or aset["semantic_hard_negative_count"] < 3:
            blockers.append("hard_negatives_fewer_than_3_or_implausible")
        if not verifier_by_ep.get(ep.get("episode_id")):
            blockers.append("verifier_command_output_missing_same_lineage")
        if aset and aset.get("decision_training_blocker"):
            blockers.append(aset["decision_training_blocker"])
        if blockers:
            blocked.append({"episode_id": ep.get("episode_id"), "source_record_id": ep.get("source_record_id"), "blocked_reason_codes": sorted(set(blockers)), "highest_possible_level_if_repaired": "level_3_single_step_closed_loop"})
        else:
            row = dict(ep)
            row["admission_level"] = "level_3_single_step_closed_loop"
            level3_ready.append(row)
    write_jsonl(out / "candidate_action_sets.jsonl", action_sets)
    write_jsonl(out / "verifier_transitions.jsonl", verifier_transitions)
    write_jsonl(out / "verifier_join_audit.jsonl", verifier_join_audit)
    write_jsonl(out / "level3_ready_episode_records.jsonl", level3_ready)
    write_jsonl(out / "level3_blocked_candidates.jsonl", blocked)
    blocker_counts = Counter(code for row in blocked for code in row["blocked_reason_codes"])
    summary = {
        "stage": "stage12202_level3_readiness_joiner",
        "artifact_type": "candidate_action_and_verifier_join_readiness",
        "training_executed": False,
        "training_allowed": False,
        "tests_executed": False,
        "network_used": False,
        "repo_mutation_performed": False,
        "source_stage": str(stage12201),
        "input_episode_count": len(episodes),
        "candidate_action_set_count": len(action_sets),
        "candidate_action_sets_with_5_actions": sum(1 for a in action_sets if a["candidate_action_count"] >= 5),
        "candidate_action_sets_with_3_hard_negatives": sum(1 for a in action_sets if a["semantic_hard_negative_count"] >= 3),
        "verifier_candidate_rows_scanned": len(verifier_rows),
        "verifier_transition_join_count": len(verifier_transitions),
        "level3_ready_episode_count": len(level3_ready),
        "level3_blocked_count": len(blocked),
        "top_blockers": blocker_counts.most_common(20),
        "decision": "level3_training_blocked" if not level3_ready else "level3_candidates_ready_needs_contract_audit",
        "why_training_blocked": [] if level3_ready else ["no_level3_records_with_observed_action_and_same_lineage_verifier_output"],
        "output_artifacts": {
            "candidate_action_sets": str(out / "candidate_action_sets.jsonl"),
            "verifier_transitions": str(out / "verifier_transitions.jsonl"),
            "verifier_join_audit": str(out / "verifier_join_audit.jsonl"),
            "level3_ready_episode_records": str(out / "level3_ready_episode_records.jsonl"),
            "level3_blocked_candidates": str(out / "level3_blocked_candidates.jsonl"),
            "summary": str(out / "summary.json"),
        },
    }
    write_json(out / "summary.json", summary)
    write_json(ROOT / "runs/summaries/stage12202_level3_readiness_joiner.json", summary)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
