#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11611
NAME = "stage11611_web_behavior_transition_supply_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_behavior_transition_supply_audit.json"
TRANSITION_ROWS = OUT / "web_behavior_transition_candidates.jsonl"
BLOCKED_ROWS = OUT / "web_behavior_transition_blocked_rows.jsonl"

SOURCES = {
    "focused_verifier_results": ART / "stage11579_web_focused_verifier_execution/web_focused_verifier_results.jsonl",
    "verifier_attached_rows": ART / "stage11580_web_verifier_attached_admission_package/web_verifier_attached_rows.jsonl",
    "answerable_no_abstain_rows": ART / "stage11597_web_answerable_no_abstain_geometry_audit/web_answerable_no_abstain_rows.jsonl",
    "web_root_heldout": ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl",
    "mcp_heldout_rows": ART / "stage11541_mcp_typescript_sdk_web_gold_heldout_rows/mcp_typescript_sdk_web_gold_heldout_rows.jsonl",
    "sep_heldout_rows": ART / "stage11543_sep_automation_web_gold_heldout_rows/sep_automation_web_gold_heldout_rows.jsonl",
    "openclaw_train_rows": ART / "stage11545_openclaw_more_web_gold_train_rows/openclaw_more_web_gold_train_rows.jsonl",
}
BEHAVIOR_TRANSITIONS = {"FAIL_TO_PASS", "PASS_TO_FAIL", "FAIL_TO_FAIL"}
PASS_ONLY_TRANSITIONS = {"PASS_TO_PASS"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"_decode_error": True, "raw": line[:500]})
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def find_transition(row: dict[str, Any]) -> str:
    candidates: list[Any] = []
    for key in ("verifier_transition", "observed_verifier_transition", "transition"):
        candidates.append(row.get(key))
    ve = row.get("verifier_evidence")
    if isinstance(ve, dict):
        candidates.extend([ve.get("transition"), ve.get("observed_verifier_transition"), ve.get("verifier_transition")])
    target = row.get("target")
    if isinstance(target, dict):
        candidates.extend([target.get("verifier_transition"), target.get("transition")])
    src = row.get("standalone_projection_source")
    if isinstance(src, dict):
        candidates.extend([src.get("verifier_transition"), src.get("observed_verifier_transition")])
    text_fields = [row.get("prompt_text"), row.get("input_text"), row.get("raw_output"), row.get("verifier_log_excerpt")]
    for value in candidates:
        text = str(value or "").upper()
        for transition in sorted(BEHAVIOR_TRANSITIONS | PASS_ONLY_TRANSITIONS | {"NOT_EXERCISED", "INSUFFICIENT_EVIDENCE", "NONE"}):
            if transition in text:
                return transition
    joined = "\n".join(str(x or "") for x in text_fields).upper()
    for transition in sorted(BEHAVIOR_TRANSITIONS | PASS_ONLY_TRANSITIONS | {"NOT_EXERCISED", "INSUFFICIENT_EVIDENCE", "NONE"}):
        if transition in joined:
            return transition
    return "MISSING"


def root_id(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("root_lineage_key") or row.get("source_root") or row.get("row_id") or "unknown")


def repo_family(row: dict[str, Any]) -> str:
    return str(row.get("repo_family") or row.get("git_repo_family") or row.get("repository") or "unknown")


def selected_verifier(row: dict[str, Any]) -> str:
    for key in ("selected_verifier_path", "selected_test", "verifier_path"):
        if row.get(key):
            return str(row.get(key))
    ve = row.get("verifier_evidence")
    if isinstance(ve, dict):
        cmd = ve.get("command")
        if isinstance(cmd, list):
            return " ".join(str(x) for x in cmd)
        if ve.get("log_path"):
            return str(ve.get("log_path"))
    return ""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    by_source: dict[str, Counter[str]] = {}
    roots_by_transition: dict[str, set[str]] = defaultdict(set)
    for source_name, path in SOURCES.items():
        rows = load_jsonl(path)
        by_source[source_name] = Counter()
        for row in rows:
            transition = find_transition(row)
            by_source[source_name][transition] += 1
            rid = root_id(row)
            roots_by_transition[transition].add(rid)
            item = {
                "source_name": source_name,
                "source_path": rel(path),
                "row_id": row.get("row_id"),
                "root_id": rid,
                "repo_family": repo_family(row),
                "task_type": row.get("task_type"),
                "split": row.get("split") or row.get("split_component"),
                "transition": transition,
                "selected_verifier": selected_verifier(row),
                "has_prompt": bool(row.get("prompt_text") or row.get("input_text")),
                "has_options": bool(((row.get("standalone_projection_source") or {}).get("opaque_options") if isinstance(row.get("standalone_projection_source"), dict) else row.get("opaque_options"))),
                "trainable_now": row.get("trainable_now"),
                "strict_eval_eligible_now": row.get("strict_eval_eligible_now"),
            }
            blockers = []
            if transition not in BEHAVIOR_TRANSITIONS:
                blockers.append("not_behavior_changing_transition")
            if not item["selected_verifier"]:
                blockers.append("missing_selected_verifier_or_command")
            if not item["has_prompt"]:
                blockers.append("missing_prompt")
            if not item["has_options"]:
                blockers.append("missing_options")
            item["blockers"] = blockers
            if blockers:
                blocked.append(item)
            else:
                candidates.append(item)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "admit_behavior_changing_web_candidates" if candidates else "no_behavior_changing_web_candidates_found",
        "candidate_rows": len(candidates),
        "candidate_roots": len({row["root_id"] for row in candidates}),
        "blocked_rows": len(blocked),
        "transition_counts_by_source": {name: dict(counter) for name, counter in by_source.items()},
        "root_counts_by_transition": {transition: len(roots) for transition, roots in sorted(roots_by_transition.items())},
        "blocker_counts": dict(Counter(blocker for row in blocked for blocker in row["blockers"])),
        "sources": {name: rel(path) for name, path in SOURCES.items()},
        "outputs": {"summary": rel(SUMMARY), "candidates": rel(TRANSITION_ROWS), "blocked": rel(BLOCKED_ROWS)},
        "interpretation": [
            "PASS_TO_PASS rows can teach selected-test relevance but not fail-to-pass repair/verifier transition reasoning.",
            "Behavior-changing candidates require FAIL_TO_PASS, FAIL_TO_FAIL, or PASS_TO_FAIL plus selected verifier/command and optionized prompt rows.",
            "If candidate_rows is zero, the next step is source materialization/execution, not another model probe.",
        ],
    }
    write_jsonl(TRANSITION_ROWS, candidates)
    write_jsonl(BLOCKED_ROWS, blocked[:1000])
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({
        "decision": summary["decision"],
        "candidate_rows": summary["candidate_rows"],
        "candidate_roots": summary["candidate_roots"],
        "transition_counts_by_source": summary["transition_counts_by_source"],
        "blocker_counts": summary["blocker_counts"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
