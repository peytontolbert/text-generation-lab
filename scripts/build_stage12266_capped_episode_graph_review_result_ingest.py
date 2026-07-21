#!/usr/bin/env python3
"""Build Stage12266 capped episode-graph review result ingest/materialization.

This stage safely rehydrates the 25 Stage12265 review packets from local Codex
session JSONL and emits only ref/digest/safe classification fields. It performs
no root admission and emits no training rows.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12266_capped_episode_graph_review_result_ingest"
CODEX_SESSIONS = Path("/home/peyton/.codex/sessions")
PACKETS = ROOT / "runs/local/artifacts/stage12265_gpt_review_packet_for_capped_episode_graph_candidates/bounded_review_packets.jsonl"
MANIFEST = ROOT / "runs/local/artifacts/stage12258_live_codex_chat_reconstruction_index/per_chat_manifest.jsonl"

EXIT_RE = re.compile(r"Process exited with code (-?\d+)")


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    return f"{prefix}_{sha256_json(parts)[:20]}"


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


def safe_json(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return json.loads(stripped)
            except Exception:
                return value
    return value


def command_head(cmd: str | None) -> str:
    parts = str(cmd or "").strip().split()
    return parts[0] if parts else ""


def action_type(tool_name: str | None, head: str | None) -> str:
    if tool_name == "apply_patch":
        return "patch"
    head = head or ""
    if head in {"rg", "grep", "find", "sed", "cat", "ls", "jq", "tail", "head", "nl"}:
        return "inspect"
    if head in {"pytest", "ctest", "cargo", "npm", "pnpm", "yarn", "node", "npx", "make", "cmake", "python", "python3"} or "python" in head:
        return "verify"
    if head == "git":
        return "inspect"
    return "run"


def output_status(output: Any) -> str:
    text = str(output or "")
    match = EXIT_RE.search(text)
    if match:
        return "pass" if int(match.group(1)) == 0 else "fail"
    low = text.lower()
    if any(term in low for term in ["timed out", "no such file", "module not found", "permission denied", "network is unreachable"]):
        return "env_blocked"
    return "unknown"


def source_paths_by_hash() -> dict[str, Path]:
    paths: dict[str, Path] = {}
    if not CODEX_SESSIONS.exists():
        return paths
    for p in CODEX_SESSIONS.rglob("*.jsonl"):
        if p.is_file():
            paths[sha1_text(str(p))] = p
    return paths


def read_window_events(path: Path, start: int, end: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, 1):
            if line_no < start:
                continue
            if line_no > end:
                break
            try:
                obj = json.loads(line)
            except Exception:
                continue
            payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
            rows.append({"line_number": line_no, "event": obj, "payload": payload})
    return rows


def materialize_packet(packet: dict[str, Any], manifest: dict[str, dict[str, Any]], paths: dict[str, Path]) -> dict[str, Any]:
    cid = packet["candidate_id"]
    src = packet["source_refs"]
    span = src["event_span_refs"]
    chat_id = src["chat_or_session_ids"][0]
    chat = manifest.get(chat_id, {})
    source_hash = (src.get("raw_payload_digests") or {}).get("source_file_hash_compat")
    source_path = paths.get(source_hash or "")
    line_start = int(span["line_start"])
    line_end = int(span["line_end"])
    events = read_window_events(source_path, line_start, line_end) if source_path else []

    calls: dict[str, dict[str, Any]] = {}
    outputs: dict[str, dict[str, Any]] = {}
    action_records: list[dict[str, Any]] = []
    cwd_counter: Counter[str] = Counter()
    workspace_hint_count = len(chat.get("workspace_root_hints_top") or [])
    cwd_hint_count = len(chat.get("cwd_hints_top") or [])

    for row in events:
        payload = row["payload"]
        ptype = str(payload.get("type") or "")
        tool_name = payload.get("name")
        call_id = payload.get("call_id") or payload.get("id")
        if tool_name:
            args_raw = safe_json(payload.get("arguments"))
            args = args_raw if isinstance(args_raw, dict) else {}
            head = command_head(args.get("cmd")) if tool_name == "exec_command" else None
            workdir = args.get("workdir") if isinstance(args.get("workdir"), str) else None
            if workdir:
                cwd_counter[workdir] += 1
            action_ref = stable_id("action_ref", chat_id, call_id, row["line_number"], tool_name)
            rec = {
                "action_id": action_ref,
                "action_type": action_type(tool_name, head),
                "action_ref": action_ref,
                "tool_name": tool_name,
                "command_head": head,
                "line_number": row["line_number"],
                "source_event_refs": [stable_id("chat_event_line", chat_id, row["line_number"])],
                "tool_pair_ref": None,
                "workdir_digest": sha256_json(workdir)[:16] if workdir else None,
                "workdir_tail": Path(workdir).name if workdir else None,
                "safe_action_summary": f"{action_type(tool_name, head)}:{head or tool_name}",
                "raw_arguments_emitted": False,
            }
            calls[str(call_id)] = rec
            action_records.append(rec)
        elif ptype in {"function_call_output", "custom_tool_call_output"} or "output" in payload:
            if call_id:
                outputs[str(call_id)] = {
                    "line_number": row["line_number"],
                    "outcome_status": output_status(payload.get("output")),
                    "output_digest": sha256_json(payload.get("output"))[:24],
                    "raw_output_emitted": False,
                }
        elif ptype == "patch_apply_end" and call_id:
            outputs[str(call_id)] = {
                "line_number": row["line_number"],
                "outcome_status": "patch_applied" if payload.get("success") is not False else "fail",
                "output_digest": sha256_json(payload)[:24],
                "raw_output_emitted": False,
            }

    observations: list[dict[str, Any]] = []
    for call_id, call in calls.items():
        out = outputs.get(call_id)
        if not out:
            continue
        pair_ref = stable_id("tool_pair_ref", chat_id, call_id, call["line_number"], out["line_number"])
        call["tool_pair_ref"] = pair_ref
        observations.append({
            "observation_ref": stable_id("observation_ref", cid, pair_ref),
            "tool_pair_ref": pair_ref,
            "observation_kind": "patch_result" if call["action_type"] == "patch" else ("verifier_result" if call["action_type"] == "verify" else "command_result"),
            "outcome_status": out["outcome_status"],
            "relevance_to_chosen_action": "ambiguous",
            "line_number": out["line_number"],
            "output_digest": out["output_digest"],
            "raw_output_emitted": False,
        })

    patch_actions = [a for a in action_records if a["action_type"] == "patch"]
    verifier_actions = [a for a in action_records if a["action_type"] == "verify"]
    last_patch = max(patch_actions, key=lambda a: a["line_number"], default=None)
    post_last_verifiers = [a for a in verifier_actions if last_patch and a["line_number"] > last_patch["line_number"]]
    pre_patch_verifiers = [a for a in verifier_actions if last_patch and a["line_number"] < min(p["line_number"] for p in patch_actions)]
    verifier_obs = [o for o in observations if o["observation_kind"] == "verifier_result"]
    pre_patch_verifier_obs = [
        o for o in verifier_obs
        if pre_patch_verifiers and o["tool_pair_ref"] in {a["tool_pair_ref"] for a in pre_patch_verifiers}
    ]
    post_last_verifier_obs = [
        o for o in verifier_obs
        if post_last_verifiers and o["tool_pair_ref"] in {a["tool_pair_ref"] for a in post_last_verifiers}
    ]
    pre_patch_statuses = Counter(o["outcome_status"] for o in pre_patch_verifier_obs)
    post_last_statuses = Counter(o["outcome_status"] for o in post_last_verifier_obs)

    distinct_cwds = len(cwd_counter)
    top_cwd = cwd_counter.most_common(1)[0][0] if cwd_counter else None
    cwd_status = "candidate_proven" if distinct_cwds == 1 else ("chat_hint_only" if cwd_hint_count == 1 or workspace_hint_count == 1 else "blocked")
    repo_family = Path(top_cwd).name if top_cwd else None
    if top_cwd and str(ROOT) in top_cwd:
        repo_kind = "self_research_repo"
    elif top_cwd:
        repo_kind = "external_or_other_repo"
    else:
        repo_kind = "unknown"

    hard_rejects: list[str] = []
    if cwd_status != "candidate_proven":
        hard_rejects.append("candidate_level_cwd_root_not_proven")
    if repo_kind == "self_research_repo":
        hard_rejects.append("self_research_repo_not_external_comparable_repair")
    if not last_patch:
        hard_rejects.append("no_patch_action_materialized")
    if not post_last_verifiers:
        hard_rejects.append("no_verifier_after_last_patch")
    if not post_last_verifier_obs:
        hard_rejects.append("post_last_verifier_observation_missing")
    hard_rejects.append("verifier_relevance_ambiguous_without_semantic_review")
    hard_rejects.append("state_update_safe_summary_requires_review")

    state_before_ref = stable_id("state_before_ref", cid, "before", last_patch["line_number"] if last_patch else line_start)
    state_update_ref = stable_id("state_update_ref", cid, "after", post_last_verifiers[-1]["line_number"] if post_last_verifiers else line_end)
    result = {
        "candidate_id": cid,
        "review_decision": "materializable_with_blockers",
        "source_refs": src,
        "root_recovery": {
            "status": cwd_status,
            "candidate_level_root_proven": cwd_status == "candidate_proven",
            "repo_family": repo_family,
            "repo_kind": repo_kind,
            "cwd_ref": stable_id("cwd_ref", top_cwd) if top_cwd else None,
            "cwd_digest": sha256_json(top_cwd)[:24] if top_cwd else None,
            "cwd_tail": Path(top_cwd).name if top_cwd else None,
            "distinct_window_cwd_count": distinct_cwds,
            "chat_cwd_hint_count": cwd_hint_count,
            "chat_workspace_root_hint_count": workspace_hint_count,
            "raw_cwd_emitted": False,
        },
        "segmentation": {
            "status": "single_lifecycle_task_window",
            "task_boundary_refs": [src.get("task_window_id"), span.get("start_event_id"), span.get("end_event_id")],
            "child_window_proposals": [],
            "multi_loop_window": len(patch_actions) > 1 or len(pre_patch_verifiers) > 0,
        },
        "state_before": {
            "status": "materialized_safe_ref_only" if last_patch else "missing",
            "state_before_ref": state_before_ref if last_patch else None,
            "safe_state_summary": "state before selected last patch action within bounded task window",
            "evidence_refs": [last_patch["action_ref"]] if last_patch else [],
            "raw_content_emitted": False,
        },
        "candidate_action_set": {
            "status": "materialized",
            "action_count": len(action_records),
            "action_type_counts": dict(Counter(a["action_type"] for a in action_records)),
            "actions": [
                {
                    k: a[k]
                    for k in [
                        "action_id",
                        "action_type",
                        "action_ref",
                        "safe_action_summary",
                        "source_event_refs",
                        "tool_pair_ref",
                        "workdir_digest",
                        "workdir_tail",
                    ]
                }
                for a in action_records[:200]
            ],
        },
        "chosen_action": {
            "status": "materialized" if last_patch else "missing",
            "action_id": last_patch["action_id"] if last_patch else None,
            "action_ref": last_patch["action_ref"] if last_patch else None,
            "tool_pair_ref": last_patch.get("tool_pair_ref") if last_patch else None,
            "patch_pair_ref": last_patch.get("tool_pair_ref") if last_patch else None,
            "choice_policy": "last_patch_before_post_last_verifier",
            "evidence_refs": [last_patch["action_ref"]] if last_patch else [],
        },
        "observations": {
            "status": "materialized",
            "items": observations[:200],
        },
        "state_update": {
            "status": "materialized_safe_ref_only" if post_last_verifier_obs else "missing",
            "state_update_ref": state_update_ref if post_last_verifier_obs else None,
            "from_state_ref": state_before_ref if last_patch else None,
            "chosen_action_ref": last_patch["action_ref"] if last_patch else None,
            "observation_refs": [o["observation_ref"] for o in post_last_verifier_obs],
            "safe_update_summary": "post-last-patch verifier observations available; semantic relevance still ambiguous",
            "evidence_refs": [o["tool_pair_ref"] for o in post_last_verifier_obs],
            "raw_content_emitted": False,
        },
        "patch_verifier": {
            "ordering_status": "post_last_patch_verifier" if post_last_verifiers else "not_proven",
            "patch_pair_refs": [a.get("tool_pair_ref") for a in patch_actions if a.get("tool_pair_ref")],
            "verifier_pair_refs": [a.get("tool_pair_ref") for a in verifier_actions if a.get("tool_pair_ref")],
            "post_last_patch_verifier_pair_refs": [a.get("tool_pair_ref") for a in post_last_verifiers if a.get("tool_pair_ref")],
            "pre_patch_verifier_count": len(pre_patch_verifiers),
            "post_last_patch_verifier_count": len(post_last_verifiers),
            "verifier_relevance_status": "ambiguous",
            "pre_patch_verifier_outcome_status_counts": dict(pre_patch_statuses),
            "post_last_verifier_outcome_status_counts": dict(post_last_statuses),
            "verifier_outcome_status_counts": dict(post_last_statuses),
            "potential_fail_to_pass_by_status": bool(pre_patch_statuses.get("fail", 0) and post_last_statuses.get("pass", 0)),
            "evidence_refs": [a["action_ref"] for a in post_last_verifiers],
        },
        "stop_continue": {
            "status": "materialized_weak_terminal_only",
            "label": "STOP",
            "terminal_status": "task_complete",
            "reason_code": "lifecycle_task_complete_not_semantic_completion",
            "next_action_ref": None,
            "evidence_refs": [span.get("end_event_id")],
        },
        "hard_reject_codes": sorted(set(hard_rejects)),
        "next_required_deterministic_join": [
            "semantic_verifier_relevance_review",
            "repo_family_lineage_cap",
            "external_comparable_repair_filter",
            "raw_safe_state_summary_review",
            "same_source_patch_verifier_revalidation",
        ],
        "admission_allowed": False,
        "training_allowed": False,
        "strict_eval_eligible": False,
        "raw_content_emitted": False,
        "raw_patch_body_emitted": False,
        "raw_tool_arguments_emitted": False,
        "raw_tool_output_emitted": False,
    }
    return result


def main() -> int:
    manifest = {row["chat_id"]: row for _, row in iter_jsonl(MANIFEST)}
    paths = source_paths_by_hash()
    rows = [materialize_packet(packet, manifest, paths) for _, packet in iter_jsonl(PACKETS)]
    hard_rejects = Counter(code for row in rows for code in row["hard_reject_codes"])
    root_status = Counter(row["root_recovery"]["status"] for row in rows)
    repo_kinds = Counter(row["root_recovery"]["repo_kind"] for row in rows)
    verifier_statuses = Counter()
    for row in rows:
        verifier_statuses.update(row["patch_verifier"]["verifier_outcome_status_counts"])

    v3_like = sum(
        1
        for row in rows
        if row["state_before"]["status"] != "missing"
        and row["candidate_action_set"]["status"] == "materialized"
        and row["chosen_action"]["status"] != "missing"
        and row["observations"]["status"] == "materialized"
        and row["state_update"]["status"] != "missing"
        and row["stop_continue"]["status"].startswith("materialized")
    )
    v4_ordering = sum(1 for row in rows if row["patch_verifier"]["ordering_status"] == "post_last_patch_verifier")
    admissible = [
        row for row in rows
        if not row["hard_reject_codes"] and row["root_recovery"]["repo_kind"] != "self_research_repo"
    ]

    summary = {
        "stage": STAGE,
        "artifact_type": "capped_episode_graph_review_result_ingest",
        "decision": "safe_materialization_complete_no_admission_training_blocked",
        "training_allowed": False,
        "claim_boundary": (
            "Safe materialization audit only. It derives refs, digests, action categories, cwd digests, and outcome classes. "
            "It emits no raw commands, outputs, patch bodies, root admissions, or training rows."
        ),
        "counts": {
            "input_review_packets": len(rows),
            "v3_like_tuple_materialized": v3_like,
            "v4_ordering_materialized": v4_ordering,
            "admissible_after_stage12266": len(admissible),
            "root_recovery_status": dict(root_status),
            "repo_kind_counts": dict(repo_kinds),
            "post_last_verifier_outcome_status_counts": dict(verifier_statuses),
            "hard_reject_counts": dict(hard_rejects.most_common()),
        },
        "quality_decision": {
            "training_allowed": False,
            "reason": "Rows still require semantic verifier relevance review, external-comparable repair filtering, and deterministic revalidation.",
            "decisive_counter_progress": {
                "sealed_transition_eval_rows": 0,
                "external_comparable_patch_trace_repair_rows": 0,
                "external_fail_to_pass_rows": 0,
                "non_python_external_repair_rows": 0,
                "level3_same_source_closed_loop_candidates": v3_like,
                "level3_same_source_closed_loop_admitted": 0,
            },
        },
        "guardrails": {
            "raw_message_text_emitted": False,
            "raw_patch_body_emitted": False,
            "raw_tool_arguments_emitted": False,
            "raw_tool_output_emitted": False,
            "root_admission_emitted": False,
            "training_rows_emitted_now": False,
        },
        "next_stage": {
            "stage": "stage12267_semantic_verifier_relevance_and_external_filter_audit",
            "scope": "review verifier relevance and external-comparable repair eligibility for materialized V3-like candidates",
            "training_allowed": False,
        },
    }

    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_jsonl(out_dir / "materialized_review_results.jsonl", rows)
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", summary)
    write_json(out_dir / "capped_episode_graph_review_result_ingest.json", summary)
    md = f"""# Stage12266 Capped Episode-Graph Review Result Ingest

## Decision

`{summary["decision"]}`

This stage materializes safe refs/classes only. It is not an admission artifact.

## Key Counts

- V3-like tuples materialized: `{v3_like}`
- V4 ordering materialized: `{v4_ordering}`
- admitted rows: `0`
- external comparable patch-trace repair rows: `0`

The next gate is semantic verifier relevance plus external-comparable repair filtering.
"""
    write_text(out_dir / "CAPPED_EPISODE_GRAPH_REVIEW_RESULT_INGEST_STAGE12266.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "materialized_review_results.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
