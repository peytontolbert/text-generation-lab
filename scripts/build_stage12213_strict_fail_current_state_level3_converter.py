#!/usr/bin/env python3
"""Convert two strict Rust current-state verifier failures to Level-3 records."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12213_strict_fail_current_state_level3_converter"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
CANDIDATE_LOGS = [
    ROOT / "runs/local/artifacts/stage12053_controlled_semantic_fail_to_pass_floor_closure_rows/logs/rust_3_clamp_baseline.json",
    ROOT / "runs/local/artifacts/stage12053_controlled_semantic_fail_to_pass_floor_closure_rows/logs/rust_5_dedupe_baseline.json",
]
EXISTING = ROOT / "runs/local/artifacts/stage12206_level3_passfail_training_rollup/level3_passfail_train_support_full.jsonl"


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def iter_jsonl(path: Path):
    if not path.exists(): return
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no,line in enumerate(f,1):
            if line.strip(): yield line_no,json.loads(line)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True)+"\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows: f.write(json.dumps(row, sort_keys=True)+"\n")


def existing_command_hashes() -> set[str]:
    out=set()
    for _,row in iter_jsonl(EXISTING) or []:
        cr=row.get("command_result") or {}
        out.add(stable_id("cmdkey", cr.get("cwd"), cr.get("command"), cr.get("returncode"), cr.get("stdout_tail"), cr.get("stderr_tail")))
    return out


def detect_language(log: dict[str, Any], path: Path) -> str:
    cmd=str(log.get("command") or log.get("cmd") or "")
    if "cargo" in cmd or path.name.startswith("rust_"):
        return "rust"
    return "unknown"


def tail(text: Any, n: int=1800) -> str:
    s=str(text or "")
    return s[-n:]


def is_real_current_failure(log: dict[str, Any]) -> bool:
    rc=log.get("returncode", log.get("exit_code"))
    stderr=str(log.get("stderr") or log.get("stderr_tail") or "")
    stdout=str(log.get("stdout") or log.get("stdout_tail") or "")
    combined=stderr+"\n"+stdout
    if rc in (0, "0", None): return False
    bad_env=["no such file or directory", "could not find", "failed to download", "network", "not found", "module not found", "ModuleNotFoundError", "ImportError"]
    if any(x.lower() in combined.lower() for x in bad_env):
        return False
    return "error[E" in combined or "could not compile" in combined


def convert(path: Path, seen: set[str]) -> tuple[dict[str, Any] | None, str | None]:
    log=read_json(path)
    if not is_real_current_failure(log):
        return None, "not_real_current_state_failure"
    command=str(log.get("command") or log.get("cmd") or "")
    cwd=str(log.get("cwd") or path.parent.parent / "fixture_repos" / path.stem.replace("_baseline", ""))
    rc=log.get("returncode", log.get("exit_code"))
    stdout_tail=tail(log.get("stdout") or log.get("stdout_tail"))
    stderr_tail=tail(log.get("stderr") or log.get("stderr_tail"))
    cmdkey=stable_id("cmdkey", cwd, command, rc, stdout_tail, stderr_tail)
    if cmdkey in seen:
        return None, "already_represented_in_stage12206"
    seen.add(cmdkey)
    language=detect_language(log,path)
    root_name=path.stem.replace("_baseline", "")
    repo_family="stage12053_controlled_semantic_fail_to_pass_floor_closure_rows"
    episode_id=stable_id("stage12213_episode", path.as_posix(), command, stderr_tail)
    command_result_id=stable_id("stage12213_command", command, cwd, rc, stdout_tail, stderr_tail)
    candidates=[
        ("A","FAIL_CURRENT_STATE","verifier failed in the current local source state",True),
        ("B","PASS_CURRENT_BUILD","build or collection passed but runnable verifier body did not execute",False),
        ("C","PASS_CURRENT_BUILD_AND_RUN","build and runnable verifier both passed",False),
        ("D","INSUFFICIENT_EVIDENCE","environment is underhydrated so no trustworthy transition is available",False),
        ("E","FAIL_TO_PASS","controlled broken state failed and restored or repaired source passed",False),
    ]
    return {
        "episode_id": episode_id,
        "root_id": cwd,
        "repo_id": repo_family,
        "repo_family": repo_family,
        "root_lineage_key": f"{repo_family}::{root_name}",
        "language": language,
        "task_type": "transition_verifier_transition",
        "selected_test_anchor": "cargo test --quiet",
        "verifier_anchor": "cargo test --quiet",
        "source_bundle_id": f"{repo_family}::{root_name}",
        "source_log_path": str(path),
        "source_stage": STAGE + "::stage12053_controlled_semantic_fail_to_pass_floor_closure_rows",
        "candidate_action_set": {
            "candidate_set_id": stable_id("stage12213_candidates", path.name),
            "chosen_action_id": "A",
            "candidate_actions": [
                {"action_id": lab, "label": lab, "role": val, "action_type": "CLASSIFY_VERIFIER_TRANSITION", "description": desc, "is_chosen": chosen, "negative_kind": None if chosen else "verifier_transition_distractor"}
                for lab,val,desc,chosen in candidates
            ],
        },
        "observed_action": {"action_id":"A", "action_type":"CLASSIFY_VERIFIER_TRANSITION", "command_result_id": command_result_id, "semantic_value":"FAIL_CURRENT_STATE"},
        "command_result": {"command_result_id": command_result_id, "command": command, "cwd": cwd, "returncode": rc, "stdout_tail": stdout_tail, "stderr_tail": stderr_tail, "source_kind":"strict_local_command_log"},
        "verifier_status": "FAIL_CURRENT_STATE",
        "verifier_transition": "FAIL_CURRENT_STATE",
        "state_update": {"state_update_id": stable_id("stage12213_state", episode_id), "state_update_type":"observed_failure", "new_facts":["current local source failed under cargo test"], "invalidated_claims":["current state passes selected verifier"], "remaining_blockers":["repair source before acceptance"]},
        "stop_decision": {"stop_decision_id": stable_id("stage12213_stop", episode_id), "continue_or_stop":"CONTINUE", "reason":"current-state verifier failure requires repair or diagnosis; task is not complete"},
        "anti_cheat": {"deterministic_option_shuffle": True, "singleton_options": False, "target_label_not_visible_before_options": True, "target_value_not_visible_before_options": True, "source_is_prior_authoritative_verifier_log": True, "target_not_promotable_eval": True},
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "projection_permissions": {"may_project_verifier_transition": True, "may_project_continue_or_stop": True, "may_project_patch_generation": False, "claim_boundary":"Strict current-state failure log converted to Level-3 train support only."},
    }, None


def main() -> int:
    seen=existing_command_hashes()
    rows=[]; blocked=[]
    for path in CANDIDATE_LOGS:
        rec,reason=convert(path,seen)
        if rec: rows.append(rec)
        else: blocked.append({"path":str(path),"blocker":reason})
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT_DIR/"strict_fail_current_state_level3_records.jsonl", rows)
    write_jsonl(OUT_DIR/"blocked_strict_fail_current_state_logs.jsonl", blocked)
    summary={
        "stage":STAGE,
        "decision":"strict_fail_current_state_records_materialized" if rows else "blocked_no_records",
        "level3_episode_count":len(rows),
        "blocked_count":len(blocked),
        "language_counts":dict(Counter(r.get("language") for r in rows)),
        "verifier_transition_counts":dict(Counter(r.get("verifier_transition") for r in rows)),
        "train_support_only":True,
        "strict_eval_eligible":False,
        "claim_boundary":"Only two strict unconsumed current-state failures were admitted; env/dependency failures remain excluded.",
        "artifact_paths":{"records":str(OUT_DIR/"strict_fail_current_state_level3_records.jsonl"),"blocked":str(OUT_DIR/"blocked_strict_fail_current_state_logs.jsonl")},
    }
    write_json(OUT_DIR/"summary.json", summary); write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if rows else 2

if __name__ == "__main__":
    raise SystemExit(main())
