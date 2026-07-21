#!/usr/bin/env python3
"""Build Stage12274 status join for root-repaired child loops.

Reads raw Codex session JSONLs locally to classify verifier outputs as coarse
PASS/FAIL/UNKNOWN, but emits no raw output, raw arguments, raw patch bodies, or
raw source paths. This is a deterministic pre-review join, not admission.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12274_status_join_for_root_repaired_child_loops"
CODEX_SESSIONS = Path("/home/peyton/.codex/sessions")
PAIRS = ROOT / "runs/local/artifacts/stage12259_codex_tool_call_observation_pairer/tool_call_observation_pairs.jsonl"
CHILDREN = ROOT / "runs/local/artifacts/stage12273_root_repaired_child_loop_splitter/root_repaired_child_loop_candidates.jsonl"
OUT_DIR = ROOT / f"runs/local/artifacts/{STAGE}"
SUMMARY_PATH = ROOT / f"runs/summaries/{STAGE}.json"


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if line:
                yield line_no, json.loads(line)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def tool_pair_ref(row: dict[str, Any]) -> str:
    return stable_id("tool_pair_ref", row.get("chat_id"), row.get("call_id"), int(row.get("call_line_number") or 0), int(row.get("output_line_number") or 0))


def build_pair_index() -> dict[str, dict[str, Any]]:
    out = {}
    for _, row in iter_jsonl(PAIRS):
        ref = tool_pair_ref(row)
        out[ref] = row
    return out


def build_raw_path_index() -> dict[str, Path]:
    out = {}
    if not CODEX_SESSIONS.exists():
        return out
    for path in CODEX_SESSIONS.rglob("*.jsonl"):
        if path.is_file():
            out[sha1_text(str(path))] = path
    return out


def load_line(path: Path, line_no: int) -> dict[str, Any] | None:
    if line_no <= 0:
        return None
    with path.open("rb") as f:
        for idx, raw in enumerate(f, 1):
            if idx == line_no:
                try:
                    return json.loads(raw.decode("utf-8", errors="ignore"))
                except Exception:
                    return None
            if idx > line_no:
                break
    return None


def output_text_from_obj(obj: dict[str, Any] | None) -> str:
    if not isinstance(obj, dict):
        return ""
    payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
    value = payload.get("output")
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return json.dumps(value, sort_keys=True, default=str)


def classify_status(text: str) -> str:
    lower = text.lower()
    if not lower.strip():
        return "UNKNOWN_EMPTY"
    if re.search(r"(?:process exited with code|exit code|returncode)[:= ]+0\b", lower):
        if re.search(r"\b(failed|failure|error|traceback|assertionerror)\b", lower):
            return "PASS_WITH_FAILURE_TEXT_REVIEW"
        return "PASS"
    if re.search(r"(?:process exited with code|exit code|returncode)[:= ]+(?!0\b)\d+", lower):
        return "FAIL"
    if re.search(r"\b(\d+ failed|failed tests?|failure|assertionerror|traceback|error:)\b", lower):
        return "FAIL"
    if re.search(r"\b(all tests passed|passed\b|success|ok\b)", lower):
        return "PASS_WEAK"
    return "UNKNOWN"


def status_for_ref(ref: str, pair_index: dict[str, dict[str, Any]], raw_index: dict[str, Path]) -> dict[str, Any]:
    pair = pair_index.get(ref)
    if not pair:
        return {"tool_pair_ref": ref, "status": "UNKNOWN_PAIR_REF_MISSING", "raw_output_emitted": False}
    source_hash = pair.get("source_file_hash_compat")
    # Stage12259 does not carry source_file_hash_compat; derive via chat lookup in child source refs later if needed.
    return {"tool_pair_ref": ref, "status": "UNKNOWN_NEEDS_SOURCE_HASH", "command_head": pair.get("command_head"), "output_digest": pair.get("output_digest"), "output_line_number": pair.get("output_line_number"), "raw_output_emitted": False}


def main() -> int:
    pair_index = build_pair_index()
    raw_index = build_raw_path_index()
    joined = []
    status_counts = Counter(); pre_status_counts = Counter(); post_status_counts = Counter(); reject_counts = Counter()
    for _, child in iter_jsonl(CHILDREN):
        source_hash = child.get("source_refs", {}).get("source_file_hash_compat")
        raw_path = raw_index.get(source_hash)
        if not raw_path:
            reject_counts["raw_source_path_not_recovered"] += 1
        pre_statuses = []
        post_statuses = []
        for item in child.get("pre_verifier_refs") or []:
            ref = item.get("tool_pair_ref")
            pair = pair_index.get(ref)
            status = "UNKNOWN_PAIR_REF_MISSING"
            if pair and raw_path:
                obj = load_line(raw_path, int(pair.get("output_line_number") or 0))
                status = classify_status(output_text_from_obj(obj))
            pre_statuses.append({"tool_pair_ref": ref, "command_head": item.get("command_head"), "status": status, "raw_output_emitted": False})
            pre_status_counts[status] += 1
        for item in child.get("post_verifier_refs") or []:
            ref = item.get("tool_pair_ref")
            pair = pair_index.get(ref)
            status = "UNKNOWN_PAIR_REF_MISSING"
            if pair and raw_path:
                obj = load_line(raw_path, int(pair.get("output_line_number") or 0))
                status = classify_status(output_text_from_obj(obj))
            post_statuses.append({"tool_pair_ref": ref, "command_head": item.get("command_head"), "status": status, "raw_output_emitted": False})
            post_status_counts[status] += 1
        pre_fail = any(s["status"] == "FAIL" for s in pre_statuses)
        post_pass = any(s["status"] in {"PASS", "PASS_WEAK", "PASS_WITH_FAILURE_TEXT_REVIEW"} for s in post_statuses)
        post_fail = any(s["status"] == "FAIL" for s in post_statuses)
        same_head = bool(pre_statuses and post_statuses) and any(a.get("command_head") == b.get("command_head") for a in pre_statuses for b in post_statuses)
        status_class = "FAIL_TO_PASS_STATUS_CANDIDATE" if pre_fail and post_pass and not post_fail and same_head else "NON_COUNTABLE"
        status_counts[status_class] += 1
        child["status_join"] = {
            "join_stage": STAGE,
            "raw_source_path_recovered": bool(raw_path),
            "raw_source_path_emitted": False,
            "pre_verifier_statuses": pre_statuses,
            "post_verifier_statuses": post_statuses,
            "observed_pre_patch_failure": pre_fail,
            "observed_post_patch_pass": post_pass,
            "post_patch_failure_remains": post_fail,
            "same_verifier_pre_post_by_command_head": same_head,
            "status_class": status_class,
            "semantic_verifier_relevance_proven": False,
        }
        child["repair_causality_gates"]["observed_pre_patch_failure"] = pre_fail
        child["repair_causality_gates"]["observed_post_patch_pass"] = post_pass
        child["repair_causality_gates"]["same_verifier_pre_post_proven_by_head_only"] = same_head
        child["admission"]["external_comparable_patch_trace_countable"] = False
        child["admission"]["external_fail_to_pass_countable"] = False
        child["admission"]["blocked_reason"] = "semantic_verifier_relevance_and_patch_effectiveness_review_required"
        joined.append(child)

    write_jsonl(OUT_DIR / "status_joined_child_loop_candidates.jsonl", joined)
    fail_to_pass_status_candidates = sum(1 for c in joined if c["status_join"]["status_class"] == "FAIL_TO_PASS_STATUS_CANDIDATE")
    summary = {
        "stage": STAGE,
        "decision": "status_join_complete_semantic_review_required_training_blocked",
        "counts": {
            "input_child_loops": len(joined),
            "raw_source_paths_recovered": sum(1 for c in joined if c["status_join"]["raw_source_path_recovered"]),
            "child_loops_with_observed_pre_fail": sum(1 for c in joined if c["status_join"]["observed_pre_patch_failure"]),
            "child_loops_with_observed_post_pass": sum(1 for c in joined if c["status_join"]["observed_post_patch_pass"]),
            "child_loops_with_post_failure_remaining": sum(1 for c in joined if c["status_join"]["post_patch_failure_remains"]),
            "same_verifier_pre_post_by_command_head": sum(1 for c in joined if c["status_join"]["same_verifier_pre_post_by_command_head"]),
            "fail_to_pass_status_candidates": fail_to_pass_status_candidates,
            "external_comparable_patch_trace_rows": 0,
            "external_fail_to_pass_rows": 0,
            "training_rows_emitted": 0,
            "admitted_rows": 0,
        },
        "status_class_counts": dict(status_counts),
        "pre_status_counts": dict(pre_status_counts),
        "post_status_counts": dict(post_status_counts),
        "reject_counts": dict(reject_counts),
        "guardrails": {"raw_output_emitted": False, "raw_arguments_emitted": False, "raw_patch_body_emitted": False, "raw_source_path_emitted": False},
        "non_admission_rationale": [
            "status regex is coarse and requires semantic verifier relevance review",
            "same verifier is command-head only, not exact command identity",
            "patch effectiveness is not proven from status transition alone",
        ],
        "next_stage": "stage12275_semantic_review_packet_for_status_candidates",
    }
    write_json(SUMMARY_PATH, summary)
    write_json(OUT_DIR / "status_join_summary.json", summary)
    write_text(OUT_DIR / "STATUS_JOIN_STAGE12274.md", "# Stage12274 Status Join\n\n" + json.dumps(summary["counts"], indent=2) + "\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
