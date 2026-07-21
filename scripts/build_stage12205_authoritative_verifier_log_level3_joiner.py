#!/usr/bin/env python3
"""Materialize Level-3 transition records from authoritative prior verifier logs.

This stage does not execute commands. It joins prior artifacts that already have
repo/cwd or repo_path, command, exit code, stdout/stderr/log previews, and verifier
status into train-support closed-loop verifier-observation records.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12205_authoritative_verifier_log_level3_joiner"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_PATH = ROOT / "runs/summaries" / f"{STAGE}.json"


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(part, sort_keys=True, default=str) for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if line:
                yield line_no, json.loads(line)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def command_text(command: Any) -> str:
    if isinstance(command, list):
        return " ".join(str(x) for x in command)
    return str(command or "")


def pass_record_common(*, source_stage: str, source_path: Path, line_no: int, root_id: str, repo_family: str, language: str, command: Any, cwd: str | None, returncode: int, selected_target: str, stdout_tail: str = "", stderr_tail: str = "", verifier_transition: str = "PASS_CURRENT_STATE", verifier_status: str | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    cmd_text = command_text(command)
    episode_id = stable_id("stage12205_episode", source_stage, root_id, repo_family, selected_target, cmd_text)
    command_id = stable_id("stage12205_command", episode_id, cmd_text, returncode, stdout_tail[-500:], stderr_tail[-500:])
    observation_id = stable_id("stage12205_observation", command_id, verifier_transition)
    action_set_id = stable_id("stage12205_action_set", episode_id)
    state_id = stable_id("stage12205_state_before", episode_id)
    candidate_action_set = {
        "action_set_id": action_set_id,
        "episode_id": episode_id,
        "state_id": state_id,
        "chosen_action_id": "A",
        "candidate_action_count": 4,
        "action_ids": ["A", "B", "C", "D"],
        "hard_negative_action_ids": ["B", "C", "D"],
        "candidate_actions": [
            {
                "action_id": "A",
                "type": "run",
                "arguments": {"cmd": cmd_text, "target": selected_target},
                "semantic_role": "run_selected_verifier",
                "is_chosen": True,
                "negative_kind": "positive_from_authoritative_observed_verifier_log",
                "plausibility_source": source_stage,
            },
            {
                "action_id": "B",
                "type": "inspect",
                "arguments": {"path": selected_target},
                "semantic_role": "inspect_test_file_without_running_verifier",
                "is_chosen": False,
                "negative_kind": "semantic_hard_negative",
                "plausibility_source": "selected_verifier_path",
            },
            {
                "action_id": "C",
                "type": "run",
                "arguments": {"cmd": "run broad test suite", "target": "broad_suite"},
                "semantic_role": "overbroad_verifier_first",
                "is_chosen": False,
                "negative_kind": "semantic_hard_negative",
                "plausibility_source": "generic_repo_maintenance_policy",
            },
            {
                "action_id": "D",
                "type": "abstain",
                "arguments": {"reason": "selected_verifier_log_available_but_unused"},
                "semantic_role": "abstain_despite_authoritative_verifier_log",
                "is_chosen": False,
                "negative_kind": "semantic_hard_negative",
                "plausibility_source": "authoritative_verifier_log",
            },
        ],
    }
    if verifier_status is None:
        verifier_status = "PASS_CURRENT_STATE" if returncode == 0 else "FAIL_CURRENT_STATE"
    record = {
        "admission_level": "level_3_single_step_closed_loop_verifier_observation_from_authoritative_log",
        "episode_id": episode_id,
        "root_id": root_id,
        "repo_family": repo_family,
        "language": language,
        "source_stage": source_stage,
        "source_ref": f"{source_path}:{line_no}",
        "candidate_action_set": candidate_action_set,
        "observed_action": {
            "action_id": "A",
            "type": "run",
            "command": cmd_text,
            "cwd": cwd,
            "command_result_id": command_id,
        },
        "command_result": {
            "command_result_id": command_id,
            "command": cmd_text,
            "cwd": cwd,
            "returncode": returncode,
            "stdout_tail": stdout_tail[-20000:],
            "stderr_tail": stderr_tail[-20000:],
            "stdout_sha256": hashlib.sha256(stdout_tail.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr_tail.encode()).hexdigest(),
        },
        "observation": {
            "observation_id": observation_id,
            "observation_type": "authoritative_selected_verifier_command_output",
            "verifier_status": verifier_status,
            "summary": f"Prior authoritative verifier log returned {returncode} for selected verifier target {selected_target}.",
        },
        "verifier_status": verifier_status,
        "verifier_transition": verifier_transition,
        "state_update": {
            "state_update_id": stable_id("stage12205_state_update", observation_id),
            "state_update_type": "verified" if verifier_status.startswith("PASS") else "observed_failure",
            "new_facts": ["authoritative selected verifier command output is available"],
            "invalidated_claims": [],
            "remaining_blockers": [],
        },
        "stop_decision": {
            "stop_decision_id": stable_id("stage12205_stop_decision", observation_id),
            "continue_or_stop": "CONTINUE",
            "reason": "single selected verifier observation is useful evidence but not a full repair acceptance proof",
        },
        "projection_permissions": [
            "transition_next_action",
            "transition_verifier_transition",
            "transition_continue_or_stop",
            "execution_trace_interpretation",
        ],
        "train_support_only": True,
        "train_support_usable_for_passfail": True,
        "strict_eval_eligible": False,
        "anti_cheat": {
            "source_is_prior_authoritative_verifier_log": True,
            "command_reexecuted_by_stage12205": False,
            "candidate_action_set_includes_observed_action": True,
            "target_not_promotable_eval": True,
        },
    }
    if extra:
        record["source_extra"] = extra
    return record


def collect_stage11579() -> list[dict[str, Any]]:
    path = ROOT / "runs/local/artifacts/stage11579_web_focused_verifier_execution/web_focused_verifier_results.jsonl"
    rows = []
    if not path.exists():
        return rows
    for line_no, row in iter_jsonl(path):
        if row.get("returncode") != 0 or row.get("status") != "verifier_executed_passed":
            continue
        rows.append(pass_record_common(
            source_stage="stage11579_web_focused_verifier_execution",
            source_path=path,
            line_no=line_no,
            root_id=str(row.get("root_id") or row.get("git_repo_family") or ""),
            repo_family=str(row.get("git_repo_family") or row.get("repo_family") or "web"),
            language="web_js_ts_html",
            command=row.get("command"),
            cwd=None,
            returncode=int(row.get("returncode")),
            selected_target=str(row.get("selected_verifier_path") or "selected_web_verifier"),
            stdout_tail=str(row.get("output_preview") or ""),
            stderr_tail="",
            verifier_transition=str(row.get("verifier_transition") or "PASS_CURRENT_STATE"),
            extra={"log_path": row.get("log_path"), "lane": row.get("lane")},
        ))
    return rows


def collect_stage11748() -> list[dict[str, Any]]:
    path = ROOT / "runs/local/artifacts/stage11748_python_repaired_verifier_feasibility/python_repaired_verifier_feasibility_results.jsonl"
    rows = []
    if not path.exists():
        return rows
    for line_no, row in iter_jsonl(path):
        if row.get("returncode") != 0 or row.get("passed") is not True:
            continue
        selected = row.get("selected_tests") or []
        rows.append(pass_record_common(
            source_stage="stage11748_python_repaired_verifier_feasibility",
            source_path=path,
            line_no=line_no,
            root_id=str(row.get("repo_path") or row.get("repo_family") or ""),
            repo_family=str(row.get("repo_family") or "python"),
            language="python",
            command=row.get("command"),
            cwd=str(row.get("repo_path") or ""),
            returncode=int(row.get("returncode")),
            selected_target=" ".join(map(str, selected)) if selected else "selected_python_verifier",
            stdout_tail=str(row.get("stdout_tail") or ""),
            stderr_tail=str(row.get("stderr_tail") or ""),
            verifier_transition="PASS_CURRENT_STATE",
            extra={"stdout_log": row.get("stdout_log"), "stderr_log": row.get("stderr_log"), "support_lane": row.get("support_lane")},
        ))
    return rows


def collect_rust(path: Path, source_stage: str) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for line_no, row in iter_jsonl(path):
        selected = row.get("selected_result") or {}
        if selected.get("returncode") != 0 or selected.get("passed") is not True:
            continue
        rows.append(pass_record_common(
            source_stage=source_stage,
            source_path=path,
            line_no=line_no,
            root_id=str(row.get("repo_path") or row.get("repo_family") or ""),
            repo_family=str(row.get("repo_family") or "rust"),
            language="rust",
            command=selected.get("command"),
            cwd=str(row.get("repo_path") or ""),
            returncode=int(selected.get("returncode")),
            selected_target=str(row.get("selected_test") or selected.get("test_name") or "selected_rust_verifier"),
            stdout_tail=str(selected.get("stdout_tail") or ""),
            stderr_tail=str(selected.get("stderr_tail") or ""),
            verifier_transition=str(row.get("observed_verifier_transition") or "PASS_CURRENT_STATE"),
            extra={"manifest_path": row.get("manifest_path"), "stdout_log": selected.get("stdout_log"), "stderr_log": selected.get("stderr_log"), "support_lane": row.get("support_lane")},
        ))
    return rows



def parse_field(text: str, label: str) -> str:
    match = re.search(rf"^{re.escape(label)}:\s*(.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def collect_stage12043() -> list[dict[str, Any]]:
    path = ROOT / "runs/local/artifacts/stage12043_buildrun_expansion_rows/buildrun_expansion_rows.jsonl"
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_no, row in iter_jsonl(path):
        text = str(row.get("input_text") or row.get("prompt_text") or "")
        transition = str(row.get("observed_verifier_transition") or row.get("target") or "PASS_CURRENT_BUILD_AND_RUN")
        command = parse_field(text, "Observed command") or parse_field(text, "Selected verifier/build pair") or "paired build and runnable verifier command"
        selected = parse_field(text, "Selected verifier/build pair") or command
        output_tail = parse_field(text, "Output tail")
        root = parse_field(text, "Source root") or str(row.get("root_id") or row.get("source_root_id") or row.get("repo_id") or "")
        repo_family = str(row.get("repo_family") or parse_field(text, "Repository family") or "")
        language = str(row.get("language_family") or "unknown")
        rc_text = parse_field(text, "Return code")
        try:
            returncode = int(rc_text)
        except Exception:
            returncode = 0 if transition.startswith("PASS") else 1
        rows.append(pass_record_common(
            source_stage="stage12043_buildrun_expansion_rows",
            source_path=path,
            line_no=line_no,
            root_id=root,
            repo_family=repo_family,
            language=language,
            command=command,
            cwd=root,
            returncode=returncode,
            selected_target=selected,
            stdout_tail=output_tail,
            stderr_tail="",
            verifier_transition=transition,
            verifier_status=transition,
            extra={"row_id": row.get("row_id"), "bounded_choice_target_label": row.get("bounded_choice_target_label")},
        ))
    return rows


def collect_stage12003() -> list[dict[str, Any]]:
    path = ROOT / "runs/local/artifacts/stage12003_cpp_real_source_fail_to_pass_mutations/cpp_real_source_fail_to_pass_rows.jsonl"
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_no, row in iter_jsonl(path):
        text = str(row.get("input_text") or row.get("prompt_text") or "")
        transition = str(row.get("observed_verifier_transition") or "FAIL_TO_PASS")
        root = parse_field(text, "Source root") or str(row.get("root_id") or row.get("source_root_id") or row.get("repo_id") or "")
        selected = parse_field(text, "Selected verifier") or "controlled C++ mutation verifier"
        source_file = parse_field(text, "Source file mutated")
        baseline = parse_field(text, "Baseline build rc")
        mutant = parse_field(text, "Mutant build rc")
        restored = parse_field(text, "Restored build rc")
        output_tail = " | ".join(part for part in [f"baseline {baseline}", f"mutant {mutant}", f"restored {restored}"] if part.strip())
        rows.append(pass_record_common(
            source_stage="stage12003_cpp_real_source_fail_to_pass_mutations",
            source_path=path,
            line_no=line_no,
            root_id=root,
            repo_family=str(row.get("repo_family") or parse_field(text, "Repository family") or "c_cpp"),
            language=str(row.get("language_family") or "c_cpp"),
            command=f"controlled mutation verifier sequence: {selected}",
            cwd=root,
            returncode=1,
            selected_target=selected,
            stdout_tail=output_tail,
            stderr_tail=source_file,
            verifier_transition=transition,
            verifier_status=transition,
            extra={"row_id": row.get("row_id"), "source_file_mutated": source_file, "bounded_choice_target_label": row.get("bounded_choice_target_label")},
        ))
    return rows


def collect_stage11451() -> list[dict[str, Any]]:
    path = ROOT / "runs/local/artifacts/stage11451_non_codex_rust_verifier_log_capture/non_codex_rust_verifier_log_queue.jsonl"
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_no, row in iter_jsonl(path):
        if row.get("materializable_for_support_rows") is not True or row.get("has_verifier_log") is not True:
            continue
        rc = int(row.get("returncode") or 0)
        transition = "PASS_CURRENT_STATE" if rc == 0 else "FAIL_CURRENT_STATE"
        rows.append(pass_record_common(
            source_stage="stage11451_non_codex_rust_verifier_log_capture",
            source_path=path,
            line_no=line_no,
            root_id=str(row.get("root_id") or row.get("repo_path") or row.get("manifest") or ""),
            repo_family=str(row.get("repo_family") or "rust"),
            language=str(row.get("language_family") or "rust"),
            command=row.get("command"),
            cwd=str(Path(str(row.get("manifest") or "")).parent) if row.get("manifest") else None,
            returncode=rc,
            selected_target=str(row.get("manifest") or "rust verifier"),
            stdout_tail=str(row.get("verifier_status") or row.get("command") or ""),
            stderr_tail="",
            verifier_transition=transition,
            verifier_status=transition,
            extra={"source_paths": row.get("source_paths"), "root_lineage_key": row.get("root_lineage_key")},
        ))
    return rows



def collect_stage12025() -> list[dict[str, Any]]:
    summary_path = ROOT / "runs/summaries/stage12025_controlled_fail_to_pass_expansion_rows.json"
    rows: list[dict[str, Any]] = []
    if not summary_path.exists():
        return rows
    summary = json.loads(summary_path.read_text())
    for idx, card in enumerate(summary.get("probe_cards") or [], 1):
        if card.get("admitted") is not True:
            continue
        fixture = card.get("fixture") or {}
        baseline = card.get("baseline") or {}
        mutant = card.get("mutant") or {}
        restored = card.get("restored") or {}
        if baseline.get("returncode") != 0 or restored.get("returncode") != 0:
            continue
        if mutant.get("returncode") == 0:
            continue
        language = str(fixture.get("language_family") or "unknown")
        fixture_id = str(fixture.get("id") or f"fixture_{idx}")
        command = {
            "baseline": baseline.get("command"),
            "mutant": mutant.get("command"),
            "restored": restored.get("command"),
        }
        stdout_tail = "\n--- baseline ---\n" + str(baseline.get("stdout_tail") or "")
        stdout_tail += "\n--- mutant ---\n" + str(mutant.get("stdout_tail") or "")
        stdout_tail += "\n--- restored ---\n" + str(restored.get("stdout_tail") or "")
        stderr_tail = "\n--- baseline ---\n" + str(baseline.get("stderr_tail") or "")
        stderr_tail += "\n--- mutant ---\n" + str(mutant.get("stderr_tail") or "")
        stderr_tail += "\n--- restored ---\n" + str(restored.get("stderr_tail") or "")
        rows.append(pass_record_common(
            source_stage="stage12025_controlled_fail_to_pass_expansion_rows",
            source_path=summary_path,
            line_no=idx,
            root_id=str(card.get("fixture", {}).get("id") or fixture_id),
            repo_family=str(fixture.get("repo_family") or f"stage12025_{language}_controlled_fixture"),
            language=language,
            command=command,
            cwd=str(baseline.get("cwd") or restored.get("cwd") or ""),
            returncode=1,
            selected_target=str(fixture.get("selected_verifier_path") or "controlled_fail_to_pass_verifier"),
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
            verifier_transition="FAIL_TO_PASS",
            verifier_status="FAIL_TO_PASS",
            extra={
                "fixture_id": fixture_id,
                "source_file": fixture.get("source_file"),
                "baseline_log_path": baseline.get("log_path"),
                "mutant_log_path": mutant.get("log_path"),
                "restored_log_path": restored.get("log_path"),
                "controlled_fixture_train_support_only": True,
            },
        ))
    return rows


def main() -> int:
    records: list[dict[str, Any]] = []
    records.extend(collect_stage11579())
    records.extend(collect_stage11748())
    records.extend(collect_rust(ROOT / "runs/local/artifacts/stage11757_rust_selected_verifier_feasibility/rust_selected_verifier_feasibility_results.jsonl", "stage11757_rust_selected_verifier_feasibility"))
    records.extend(collect_rust(ROOT / "runs/local/artifacts/stage11778_rust_lite_core_verifier_feasibility/rust_lite_core_verifier_feasibility_results.jsonl", "stage11778_rust_lite_core_verifier_feasibility"))
    records.extend(collect_stage12043())
    records.extend(collect_stage12003())
    records.extend(collect_stage11451())
    records.extend(collect_stage12025())

    seen = set()
    deduped = []
    for row in records:
        key = (row["source_stage"], row["root_id"], row["observed_action"]["command"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    records = deduped

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT_DIR / "authoritative_level3_episode_records.jsonl", records)
    write_jsonl(OUT_DIR / "command_results.jsonl", [r["command_result"] | {"episode_id": r["episode_id"], "repo_family": r["repo_family"], "language": r["language"]} for r in records])
    write_jsonl(OUT_DIR / "candidate_action_sets.jsonl", [r["candidate_action_set"] for r in records])
    write_jsonl(OUT_DIR / "observations.jsonl", [r["observation"] | {"episode_id": r["episode_id"]} for r in records])
    write_jsonl(OUT_DIR / "verifier_transitions.jsonl", [{"episode_id": r["episode_id"], "verifier_status": r["verifier_status"], "verifier_transition": r["verifier_transition"]} for r in records])
    write_jsonl(OUT_DIR / "state_updates.jsonl", [r["state_update"] | {"episode_id": r["episode_id"]} for r in records])
    write_jsonl(OUT_DIR / "stop_decisions.jsonl", [r["stop_decision"] | {"episode_id": r["episode_id"]} for r in records])

    counts = Counter(r["language"] for r in records)
    stage_counts = Counter(r["source_stage"] for r in records)
    transition_counts = Counter(r["verifier_transition"] for r in records)
    summary = {
        "stage": STAGE,
        "decision": "authoritative_passfail_level3_records_materialized" if records else "blocked_no_authoritative_records",
        "level3_episode_count": len(records),
        "usable_passfail_count": len(records),
        "env_blocked_count": 0,
        "language_counts": dict(counts),
        "source_stage_counts": dict(stage_counts),
        "verifier_transition_counts": dict(transition_counts),
        "strict_eval_eligible": False,
        "train_support_only": True,
        "artifact_paths": {
            "authoritative_level3_episode_records": str(OUT_DIR / "authoritative_level3_episode_records.jsonl"),
            "command_results": str(OUT_DIR / "command_results.jsonl"),
            "candidate_action_sets": str(OUT_DIR / "candidate_action_sets.jsonl"),
        },
        "claim_boundary": "Prior authoritative logs are train-support transition records only; no eval or repair-success claim.",
    }
    write_json(OUT_DIR / "summary.json", summary)
    write_json(SUMMARY_PATH, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if records else 2


if __name__ == "__main__":
    raise SystemExit(main())
