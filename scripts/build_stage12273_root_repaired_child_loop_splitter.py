#!/usr/bin/env python3
"""Build Stage12273 root-repaired child-loop splitter.

Joins Stage12263 patch+verifier windows with Stage12258 per-chat cwd hints so
repo-family caps operate on likely repo roots instead of the generic
`codex_sessions` source label. Emits candidate records only.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12273_root_repaired_child_loop_splitter"
PROFILES = ROOT / "runs/local/artifacts/stage12263_high_value_window_profiler/source_shard_profiles.jsonl"
PAIRS = ROOT / "runs/local/artifacts/stage12259_codex_tool_call_observation_pairer/tool_call_observation_pairs.jsonl"
MANIFEST = ROOT / "runs/local/artifacts/stage12258_live_codex_chat_reconstruction_index/per_chat_manifest.jsonl"
OUT_DIR = ROOT / f"runs/local/artifacts/{STAGE}"
SUMMARY_PATH = ROOT / f"runs/summaries/{STAGE}.json"

SELF_ROOTS = {"agentkernel-seq2seq-text-lab", "parameter-golf"}
VERIFIER_HEADS = {"pytest", "ctest", "cargo", "npm", "pnpm", "yarn", "node", "npx", "make", "cmake", "python", "python3", "vitest", "tsc"}
INSPECT_HEADS = {"rg", "grep", "find", "sed", "cat", "ls", "jq", "tail", "head", "nl", "git", "pwd"}
CHAT_CHILD_CAP = 30
REPO_CHILD_CAP = 25
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


def path_family(path: str | None) -> str:
    if not path:
        return "unknown"
    clean = path.rstrip("/")
    return clean.split("/")[-1] or "unknown"


def language_from_family(family: str, heads: dict[str, int]) -> str:
    head_keys = set(heads)
    if {"cargo", "rustc"} & head_keys:
        return "rust"
    if {"npm", "npx", "pnpm", "yarn", "node", "tsc", "vitest"} & head_keys or family in {"bddy", "staticpeytonsite", "website"}:
        return "web_js_ts_html"
    if {"cmake", "make", "gcc", "g++", "cc", "ctest"} & head_keys:
        return "c_cpp"
    return "python"


def build_chat_roots() -> dict[str, dict[str, Any]]:
    roots = {}
    for _, row in iter_jsonl(MANIFEST):
        chat_id = row.get("chat_id")
        cwd = None
        if row.get("workspace_root_hints_top"):
            cwd = row["workspace_root_hints_top"][0][0]
        elif row.get("cwd_hints_top"):
            cwd = row["cwd_hints_top"][0][0]
        family = path_family(cwd)
        roots[chat_id] = {
            "root_status": "candidate_proven" if cwd else "missing_cwd_hint",
            "repo_family_label": family,
            "repo_family_digest": stable_id("repo_family", cwd or chat_id),
            "cwd_hint_digest": stable_id("cwd_hint", cwd or chat_id),
            "repo_kind": "self_research_repo" if family in SELF_ROOTS else "external_or_other_repo",
            "language_family_hint": language_from_family(family, row.get("command_head_counts") or {}),
            "cwd_hint_count": row.get("workspace_root_hints_top", row.get("cwd_hints_top", []))[0][1] if (row.get("workspace_root_hints_top") or row.get("cwd_hints_top")) else 0,
            "raw_cwd_path_emitted": False,
        }
    return roots


def action_type(tool: str | None, head: str | None) -> str:
    head = head or ""
    if tool == "apply_patch":
        return "patch"
    if head in INSPECT_HEADS:
        return "inspect"
    if head in VERIFIER_HEADS or "test" in head or "pytest" in head:
        return "verify"
    return "run"


def build_pair_index() -> dict[str, list[dict[str, Any]]]:
    by_chat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for _, row in iter_jsonl(PAIRS):
        chat_id = row.get("chat_id")
        if not chat_id:
            continue
        call_line = int(row.get("call_line_number") or 0)
        output_line = int(row.get("output_line_number") or 0)
        head = row.get("command_head")
        by_chat[chat_id].append({
            "tool_pair_ref": stable_id("tool_pair_ref", chat_id, row.get("call_id"), call_line, output_line),
            "chat_id": chat_id,
            "tool_name": row.get("tool_name"),
            "command_head": head,
            "action_type": action_type(row.get("tool_name"), head),
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
    if int(row.get("patch_signal_count") or 0) < 1:
        return False, "no_patch_signal"
    if int(row.get("verifier_command_count") or 0) < 1:
        return False, "no_verifier_signal"
    if int(row.get("loop_count") or 0) < 1:
        return False, "no_loop_signal"
    return True, "eligible"


def horizon_bucket(n: int) -> str:
    if n <= 1:
        return "H1"
    if n <= 3:
        return "H2_3"
    if n <= 8:
        return "H4_8"
    return "H9_PLUS"


def make_child(profile: dict[str, Any], root: dict[str, Any], patch: dict[str, Any], pre: list[dict[str, Any]], post: list[dict[str, Any]], idx: int) -> dict[str, Any]:
    selected_post = post[:8]
    bucket = horizon_bucket(len(post))
    split_group_id = stable_id("split_group", profile.get("chat_id"), root.get("repo_family_digest"), profile.get("source_file_hash_compat"))
    root_lineage_key = stable_id("root_lineage", split_group_id, profile.get("task_window_id"))
    child_loop_id = stable_id("child_loop", root_lineage_key, idx, patch.get("tool_pair_ref"), patch.get("output_digest"))
    same_head = bool(pre) and any(v.get("command_head") == selected_post[0].get("command_head") for v in pre)
    return {
        "schema_version": "root_repaired_child_loop_candidate_v1",
        "stage": STAGE,
        "child_loop_id": child_loop_id,
        "horizon_bucket": bucket,
        "source_refs": {
            "snapshot_id": profile.get("snapshot_id"),
            "chat_id": profile.get("chat_id"),
            "session_id_hint": profile.get("session_id_hint"),
            "task_window_id": profile.get("task_window_id"),
            "source_file_hash_compat": profile.get("source_file_hash_compat"),
            "line_start": profile.get("line_start"),
            "line_end": profile.get("line_end"),
            "event_start_id": profile.get("event_start_id"),
            "event_end_id": profile.get("event_end_id"),
        },
        "root_recovery": root,
        "lineage": {
            "split_group_id": split_group_id,
            "root_lineage_key": root_lineage_key,
            "episode_id": stable_id("episode", root_lineage_key, "root_repaired_child_loop"),
            "child_loop_index": idx,
            "dedupe_cluster_id": stable_id("dedupe", root_lineage_key, patch.get("command_head"), selected_post[0].get("command_head")),
            "sibling_loss_group": child_loop_id,
            "projection_loss_weight_cap": 1.0,
        },
        "child_span_refs": {
            "child_start_line": pre[0]["call_line_number"] if pre else patch["call_line_number"],
            "patch_call_line": patch["call_line_number"],
            "patch_output_line": patch["output_line_number"],
            "child_end_line": selected_post[-1]["output_line_number"],
            "post_verifier_count_total": len(post),
            "post_verifier_count_emitted": len(selected_post),
        },
        "patch_ref": {"tool_pair_ref": patch["tool_pair_ref"], "arguments_digest": patch.get("arguments_digest"), "output_digest": patch.get("output_digest"), "raw_patch_body_emitted": False},
        "pre_verifier_refs": [{"tool_pair_ref": v["tool_pair_ref"], "command_head": v.get("command_head"), "output_digest": v.get("output_digest")} for v in pre[-3:]],
        "post_verifier_refs": [{"tool_pair_ref": v["tool_pair_ref"], "command_head": v.get("command_head"), "output_digest": v.get("output_digest")} for v in selected_post],
        "repair_causality_gates": {
            "exactly_one_patch_in_child": True,
            "post_patch_verifier_present": True,
            "observed_pre_patch_failure": False,
            "observed_post_patch_pass": False,
            "same_verifier_pre_post_proven_by_head_only": same_head,
            "semantic_verifier_relevance_proven": False,
            "no_intervening_patch_by_child_definition": True,
            "external_task_validity_proven": root.get("repo_kind") == "external_or_other_repo",
        },
        "admission": {
            "candidate_only": True,
            "train_support_allowed": False,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "external_comparable_patch_trace_countable": False,
            "external_fail_to_pass_countable": False,
            "blocked_reason": "needs_status_join_and_semantic_verifier_relevance_before_admission",
        },
        "guardrails": {"raw_message_text_emitted": False, "raw_patch_body_emitted": False, "raw_tool_arguments_emitted": False, "raw_tool_output_emitted": False, "raw_cwd_path_emitted": False},
    }


def main() -> int:
    roots = build_chat_roots()
    pairs_by_chat = build_pair_index()
    profiles = [r for _, r in iter_jsonl(PROFILES)]
    profiles.sort(key=lambda r: (0 if roots.get(r.get("chat_id"), {}).get("repo_kind") == "external_or_other_repo" else 1, int(r.get("rank") or 10**9)))

    children = []
    hard = Counter(); quarantine = Counter(); chats = Counter(); repos = Counter(); langs = Counter(); horizons = Counter(); parents = Counter()
    parents_scanned = parents_eligible = parents_external = 0
    for profile in profiles:
        parents_scanned += 1
        ok, reason = profile_eligible(profile)
        if not ok:
            hard[reason] += 1
            continue
        parents_eligible += 1
        root = roots.get(profile.get("chat_id"), {"root_status": "missing_chat_manifest", "repo_kind": "unknown", "repo_family_label": "unknown", "repo_family_digest": stable_id("repo_family", profile.get("chat_id")), "language_family_hint": profile.get("likely_language_family") or "unknown", "raw_cwd_path_emitted": False})
        if root.get("repo_kind") == "external_or_other_repo":
            parents_external += 1
        chat_id = profile.get("chat_id")
        start = int(profile.get("line_start") or 0); end = int(profile.get("line_end") or 0)
        actions = [p for p in pairs_by_chat.get(chat_id, []) if start <= int(p["call_line_number"]) <= end]
        patch_indices = [i for i,a in enumerate(actions) if a["action_type"] == "patch"]
        if not patch_indices:
            hard["no_patch_pair_inside_parent_span"] += 1
            continue
        emitted_parent = 0
        for patch_ord, pi in enumerate(patch_indices):
            patch = actions[pi]
            prev_patch_out = actions[patch_indices[patch_ord-1]]["output_line_number"] if patch_ord > 0 else start - 1
            next_patch_call = actions[patch_indices[patch_ord+1]]["call_line_number"] if patch_ord + 1 < len(patch_indices) else end + 1
            pre = [a for a in actions if a["action_type"] == "verify" and prev_patch_out < a["call_line_number"] < patch["call_line_number"]]
            post = [a for a in actions if a["action_type"] == "verify" and patch["output_line_number"] < a["call_line_number"] < next_patch_call]
            if not post:
                hard["no_post_patch_verifier"] += 1
                continue
            repo = root.get("repo_family_label") or "unknown"
            lang = root.get("language_family_hint") or profile.get("likely_language_family") or "unknown"
            bucket = horizon_bucket(len(post))
            if chats[chat_id] >= CHAT_CHILD_CAP:
                quarantine["chat_child_cap_reached"] += 1; continue
            if repos[repo] >= REPO_CHILD_CAP:
                quarantine["repo_child_cap_reached"] += 1; continue
            if horizons[bucket] >= HORIZON_CAPS[bucket]:
                quarantine[f"horizon_cap_reached_{bucket}"] += 1; continue
            child = make_child(profile, root, patch, pre, post, emitted_parent)
            children.append(child); emitted_parent += 1
            chats[chat_id] += 1; repos[repo] += 1; langs[lang] += 1; horizons[bucket] += 1; parents[profile.get("task_window_id")] += 1
        if emitted_parent == 0:
            quarantine["parent_no_child_after_caps_or_post_verifier_gate"] += 1

    write_jsonl(OUT_DIR / "root_repaired_child_loop_candidates.jsonl", children)
    summary = {
        "stage": STAGE,
        "decision": "root_repaired_child_loop_candidates_mined_no_admission_training_blocked",
        "counts": {
            "parents_scanned": parents_scanned,
            "parents_split_eligible": parents_eligible,
            "parents_external_root_hint": parents_external,
            "child_loops_emitted": len(children),
            "unique_parent_windows": len(parents),
            "child_loops_with_pre_verifier_refs": sum(1 for c in children if c["pre_verifier_refs"]),
            "child_loops_with_post_verifier_refs": sum(1 for c in children if c["post_verifier_refs"]),
            "child_loops_with_observed_pre_fail": 0,
            "child_loops_with_observed_post_pass": 0,
            "same_verifier_pre_post_head_only": sum(1 for c in children if c["repair_causality_gates"]["same_verifier_pre_post_proven_by_head_only"]),
            "external_comparable_patch_trace_rows": 0,
            "external_fail_to_pass_rows": 0,
            "training_rows_emitted": 0,
            "admitted_rows": 0,
        },
        "child_loops_by_chat_top10": chats.most_common(10),
        "child_loops_by_repo_family": dict(repos),
        "child_loops_by_language": dict(langs),
        "child_loops_by_horizon": dict(horizons),
        "hard_reject_counts": dict(hard),
        "quarantine_counts": dict(quarantine),
        "root_repair_method": "per_chat_manifest_workspace_root_or_cwd_hint_hashed_no_raw_path_emitted",
        "non_admission_rationale": [
            "cwd/root hints repair repo-family caps but do not prove patch/verifier semantic relevance",
            "paired digests do not expose observed pre-fail or post-pass status",
            "external repair rows remain zero until raw status join and semantic review pass",
        ],
        "next_stage": "stage12274_status_join_for_root_repaired_child_loops",
    }
    write_json(SUMMARY_PATH, summary)
    write_json(OUT_DIR / "root_repaired_child_loop_splitter_summary.json", summary)
    write_text(OUT_DIR / "ROOT_REPAIRED_CHILD_LOOP_SPLITTER_STAGE12273.md", "# Stage12273 Root-Repaired Child Loop Splitter\n\n" + json.dumps(summary["counts"], indent=2) + "\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
