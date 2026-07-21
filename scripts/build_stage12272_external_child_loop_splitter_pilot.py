#!/usr/bin/env python3
"""Build Stage12272 external child-loop splitter pilot.

Splits Stage12263 patch+verifier parent windows into bounded child loops using
paired tool refs only. This stage emits candidate records and rejection counters;
it does not admit training/eval rows or claim repair causality.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12272_external_child_loop_splitter_pilot"
PROFILES = ROOT / "runs/local/artifacts/stage12263_high_value_window_profiler/source_shard_profiles.jsonl"
PAIRS = ROOT / "runs/local/artifacts/stage12259_codex_tool_call_observation_pairer/tool_call_observation_pairs.jsonl"
OUT_DIR = ROOT / f"runs/local/artifacts/{STAGE}"
SUMMARY_PATH = ROOT / f"runs/summaries/{STAGE}.json"

VERIFIER_HEADS = {"pytest", "ctest", "cargo", "npm", "pnpm", "yarn", "node", "npx", "make", "cmake", "python", "python3"}
INSPECT_HEADS = {"rg", "grep", "find", "sed", "cat", "ls", "jq", "tail", "head", "nl", "git", "pwd"}
CHAT_CHILD_CAP = 30
REPO_CHILD_CAP = 25
PYTHON_CHILD_CAP = 160
HORIZON_CAPS = {"H1": 80, "H2_3": 80, "H4_8": 40, "H9_PLUS": 10}


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


def action_type(tool: str | None, head: str | None) -> str:
    head = head or ""
    if tool == "apply_patch":
        return "patch"
    if head in INSPECT_HEADS:
        return "inspect"
    if head in VERIFIER_HEADS or "test" in head or "pytest" in head:
        return "verify"
    return "run"


def horizon_bucket(post_count: int) -> str:
    if post_count <= 1:
        return "H1"
    if post_count <= 3:
        return "H2_3"
    if post_count <= 8:
        return "H4_8"
    return "H9_PLUS"


def build_pair_index() -> dict[str, list[dict[str, Any]]]:
    by_chat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for _, row in iter_jsonl(PAIRS):
        chat_id = row.get("chat_id")
        if not chat_id:
            continue
        call_line = int(row.get("call_line_number") or 0)
        output_line = int(row.get("output_line_number") or 0)
        tool = row.get("tool_name")
        head = row.get("command_head")
        by_chat[chat_id].append({
            "tool_pair_ref": stable_id("tool_pair_ref", chat_id, row.get("call_id"), call_line, output_line),
            "chat_id": chat_id,
            "tool_name": tool,
            "command_head": head,
            "action_type": action_type(tool, head),
            "call_event_id": row.get("call_event_id"),
            "output_event_id": row.get("output_event_id"),
            "call_line_number": call_line,
            "output_line_number": output_line,
            "arguments_digest": row.get("arguments_digest"),
            "output_digest": row.get("output_digest"),
            "raw_arguments_emitted": False,
            "raw_output_emitted": False,
        })
    for rows in by_chat.values():
        rows.sort(key=lambda r: (r["call_line_number"], r["output_line_number"], r["tool_pair_ref"]))
    return by_chat


def profile_eligible(row: dict[str, Any]) -> tuple[bool, str]:
    if row.get("exclusion_codes"):
        return False, "profile_has_exclusion_codes"
    if row.get("audit_bucket") != "patch_verify_loop":
        return False, "not_patch_verify_loop"
    if row.get("recommended_parser_mode") != "line_window":
        return False, "not_line_window"
    if row.get("source_adapter") != "codex_sessions":
        return False, "not_codex_session_source"
    if not row.get("source_root_repaired_from_chat_manifest"):
        return False, "source_root_not_repaired_from_chat_manifest"
    if int(row.get("patch_signal_count") or 0) < 1:
        return False, "no_patch_signal"
    if int(row.get("verifier_command_count") or 0) < 1:
        return False, "no_verifier_signal"
    if int(row.get("loop_count") or 0) < 1:
        return False, "no_loop_signal"
    if row.get("training_allowed") is not False:
        return False, "profile_not_marked_training_blocked"
    return True, "eligible"


def repo_family(profile: dict[str, Any]) -> str:
    # Stage12263 does not carry reliable external repo identity yet. Keep this
    # explicit so downstream stages do not treat Codex-session source as a repo.
    return str(profile.get("source_root_label") or "unknown_repo_family")


def make_child(profile: dict[str, Any], patch: dict[str, Any], pre_verifiers: list[dict[str, Any]], post_verifiers: list[dict[str, Any]], child_index: int) -> dict[str, Any]:
    selected_post = post_verifiers[:8]
    bucket = horizon_bucket(len(post_verifiers))
    split_group_id = stable_id("split_group", profile.get("chat_id"), profile.get("session_id_hint"), profile.get("source_file_hash_compat"), profile.get("source_root_label"))
    root_lineage_key = stable_id("root_lineage", split_group_id, profile.get("task_window_id"))
    child_loop_id = stable_id("child_loop", root_lineage_key, child_index, patch.get("tool_pair_ref"), patch.get("output_digest"))
    same_verifier_head = bool(pre_verifiers) and any(v.get("command_head") == selected_post[0].get("command_head") for v in pre_verifiers)
    return {
        "schema_version": "external_child_loop_candidate_v1",
        "stage": STAGE,
        "child_loop_id": child_loop_id,
        "horizon_bucket": bucket,
        "source_refs": {
            "snapshot_id": profile.get("snapshot_id"),
            "chat_id": profile.get("chat_id"),
            "session_id_hint": profile.get("session_id_hint"),
            "task_window_id": profile.get("task_window_id"),
            "source_file_hash_compat": profile.get("source_file_hash_compat"),
            "source_root_label": profile.get("source_root_label"),
            "profile_rank": profile.get("rank"),
            "line_start": profile.get("line_start"),
            "line_end": profile.get("line_end"),
            "event_start_id": profile.get("event_start_id"),
            "event_end_id": profile.get("event_end_id"),
        },
        "lineage": {
            "split_group_id": split_group_id,
            "root_lineage_key": root_lineage_key,
            "episode_id": stable_id("episode", root_lineage_key, "child_loop_splitter"),
            "child_loop_index": child_index,
            "dedupe_cluster_id": stable_id("dedupe", root_lineage_key, patch.get("command_head"), selected_post[0].get("command_head")),
            "sibling_loss_group": child_loop_id,
            "projection_loss_weight_cap": 1.0,
        },
        "root_recovery": {
            "status": "needs_external_root_review",
            "repo_kind": "unknown_until_cwd_or_repo_manifest_join",
            "repo_family": repo_family(profile),
            "external_or_other_repo_proven": False,
            "distinct_window_cwd_count": None,
        },
        "child_span_refs": {
            "child_start_line": pre_verifiers[0]["call_line_number"] if pre_verifiers else patch["call_line_number"],
            "patch_call_line": patch["call_line_number"],
            "patch_output_line": patch["output_line_number"],
            "child_end_line": selected_post[-1]["output_line_number"],
            "post_verifier_count_total": len(post_verifiers),
            "post_verifier_count_emitted": len(selected_post),
        },
        "patch_ref": {
            "tool_pair_ref": patch.get("tool_pair_ref"),
            "arguments_digest": patch.get("arguments_digest"),
            "output_digest": patch.get("output_digest"),
            "raw_patch_body_emitted": False,
        },
        "pre_verifier_refs": [
            {"tool_pair_ref": v.get("tool_pair_ref"), "command_head": v.get("command_head"), "output_digest": v.get("output_digest")}
            for v in pre_verifiers[-3:]
        ],
        "post_verifier_refs": [
            {"tool_pair_ref": v.get("tool_pair_ref"), "command_head": v.get("command_head"), "output_digest": v.get("output_digest")}
            for v in selected_post
        ],
        "repair_causality_gates": {
            "exactly_one_patch_in_child": True,
            "post_patch_verifier_present": True,
            "observed_pre_patch_failure": False,
            "observed_post_patch_pass": False,
            "same_verifier_pre_post_proven_by_head_only": same_verifier_head,
            "semantic_verifier_relevance_proven": False,
            "no_intervening_patch_by_child_definition": True,
            "external_task_validity_proven": False,
        },
        "admission": {
            "candidate_only": True,
            "train_support_allowed": False,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "external_comparable_patch_trace_countable": False,
            "external_fail_to_pass_countable": False,
            "blocked_reason": "needs_raw_status_join_external_root_review_and_semantic_verifier_relevance",
        },
        "guardrails": {
            "raw_message_text_emitted": False,
            "raw_patch_body_emitted": False,
            "raw_tool_arguments_emitted": False,
            "raw_tool_output_emitted": False,
        },
    }


def main() -> int:
    pairs_by_chat = build_pair_index()
    hard_reject_counts: Counter[str] = Counter()
    quarantine_counts: Counter[str] = Counter()
    children: list[dict[str, Any]] = []
    parent_counts = Counter()
    chat_counts = Counter()
    repo_counts = Counter()
    lang_counts = Counter()
    horizon_counts = Counter()
    parents_scanned = 0
    parents_split_eligible = 0

    profiles = [row for _, row in iter_jsonl(PROFILES)]
    profiles.sort(key=lambda r: (
        1 if str(r.get("likely_language_family")) == "python" else 0,
        int(r.get("rank") or 10**9),
    ))

    for profile in profiles:
        parents_scanned += 1
        ok, reason = profile_eligible(profile)
        if not ok:
            hard_reject_counts[reason] += 1
            continue
        parents_split_eligible += 1
        chat_id = profile.get("chat_id")
        lang = str(profile.get("likely_language_family") or "unknown")
        repo = repo_family(profile)
        start = int(profile.get("line_start") or 0)
        end = int(profile.get("line_end") or 0)
        actions = [p for p in pairs_by_chat.get(chat_id, []) if start <= int(p["call_line_number"]) <= end]
        if not actions:
            hard_reject_counts["no_pairs_inside_parent_span"] += 1
            continue
        patch_indices = [i for i, a in enumerate(actions) if a["action_type"] == "patch"]
        if not patch_indices:
            hard_reject_counts["no_patch_pair_inside_parent_span"] += 1
            continue
        emitted_for_parent = 0
        for patch_ord, pi in enumerate(patch_indices):
            patch = actions[pi]
            prev_patch_out = actions[patch_indices[patch_ord - 1]]["output_line_number"] if patch_ord > 0 else start - 1
            next_patch_call = actions[patch_indices[patch_ord + 1]]["call_line_number"] if patch_ord + 1 < len(patch_indices) else end + 1
            pre_verifiers = [a for a in actions if a["action_type"] == "verify" and prev_patch_out < a["call_line_number"] < patch["call_line_number"]]
            post_verifiers = [a for a in actions if a["action_type"] == "verify" and patch["output_line_number"] < a["call_line_number"] < next_patch_call]
            if not post_verifiers:
                hard_reject_counts["no_post_patch_verifier"] += 1
                continue
            bucket = horizon_bucket(len(post_verifiers))
            if chat_counts[chat_id] >= CHAT_CHILD_CAP:
                quarantine_counts["chat_child_cap_reached"] += 1
                continue
            if repo_counts[repo] >= REPO_CHILD_CAP:
                quarantine_counts["repo_child_cap_reached"] += 1
                continue
            if lang == "python" and lang_counts[lang] >= PYTHON_CHILD_CAP:
                quarantine_counts["python_child_cap_reached"] += 1
                continue
            if horizon_counts[bucket] >= HORIZON_CAPS[bucket]:
                quarantine_counts[f"horizon_cap_reached_{bucket}"] += 1
                continue
            child = make_child(profile, patch, pre_verifiers, post_verifiers, emitted_for_parent)
            children.append(child)
            emitted_for_parent += 1
            chat_counts[chat_id] += 1
            repo_counts[repo] += 1
            lang_counts[lang] += 1
            horizon_counts[bucket] += 1
            parent_counts[profile.get("task_window_id")] += 1
        if emitted_for_parent == 0:
            quarantine_counts["parent_no_child_after_caps_or_post_verifier_gate"] += 1

    write_jsonl(OUT_DIR / "external_child_loop_candidates.jsonl", children)
    summary = {
        "stage": STAGE,
        "decision": "external_child_loop_candidates_mined_no_admission_training_blocked",
        "inputs": {"profiles": str(PROFILES.relative_to(ROOT)), "tool_pairs": str(PAIRS.relative_to(ROOT))},
        "counts": {
            "parents_scanned": parents_scanned,
            "parents_split_eligible": parents_split_eligible,
            "child_loops_emitted": len(children),
            "unique_parent_windows": len(parent_counts),
            "child_loops_with_pre_verifier_refs": sum(1 for c in children if c["pre_verifier_refs"]),
            "child_loops_with_post_verifier_refs": sum(1 for c in children if c["post_verifier_refs"]),
            "child_loops_with_observed_pre_fail": 0,
            "child_loops_with_observed_post_pass": 0,
            "external_comparable_patch_trace_rows": 0,
            "external_fail_to_pass_rows": 0,
            "training_rows_emitted": 0,
            "admitted_rows": 0,
        },
        "child_loops_by_chat_top10": chat_counts.most_common(10),
        "child_loops_by_repo_family": dict(repo_counts),
        "child_loops_by_language": dict(lang_counts),
        "child_loops_by_horizon": dict(horizon_counts),
        "hard_reject_counts": dict(hard_reject_counts),
        "quarantine_counts": dict(quarantine_counts),
        "caps": {"chat_child_cap": CHAT_CHILD_CAP, "repo_child_cap": REPO_CHILD_CAP, "python_child_cap": PYTHON_CHILD_CAP, "horizon_caps": HORIZON_CAPS},
        "non_admission_rationale": [
            "paired artifacts contain digests/refs but not raw status needed to prove pre-fail/post-pass",
            "source-root externality is not proven for broad profiles until cwd/repo manifest join",
            "same-verifier relation is command-head-only and requires semantic review",
            "PASS-after-patch without observed pre-fail remains non-countable",
        ],
        "next_stage": "stage12273_child_loop_status_join_and_external_root_review",
    }
    write_json(SUMMARY_PATH, summary)
    write_json(OUT_DIR / "external_child_loop_splitter_summary.json", summary)
    write_text(
        OUT_DIR / "EXTERNAL_CHILD_LOOP_SPLITTER_PILOT_STAGE12272.md",
        "# Stage12272 External Child Loop Splitter Pilot\n\n"
        "This stage splits patch+verifier parent windows into one-patch child-loop candidates. "
        "It emits refs/digests only and blocks all training/admission pending source-root review, raw status join, and semantic verifier relevance.\n\n"
        f"Parents scanned: {parents_scanned}\n\n"
        f"Parents split-eligible: {parents_split_eligible}\n\n"
        f"Child loops emitted: {len(children)}\n\n"
        f"Horizon counts: {dict(horizon_counts)}\n\n"
        "Repair rows admitted: 0. External FAIL_TO_PASS rows admitted: 0.\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
