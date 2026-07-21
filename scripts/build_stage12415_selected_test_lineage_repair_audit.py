#!/usr/bin/env python3
"""Stage12415 fail-closed selected-test lineage repair audit.

Consumes Stage12414 blocked items and attempts deterministic repair through the
safe upstream metadata chain. Public artifacts intentionally expose only stage
names, stable identifiers, hashes, counters, and blocker codes.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12415_selected_test_lineage_repair_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12414_MANIFEST = (
    ROOT
    / "runs/local/artifacts/stage12414_selected_test_verifier_log_materialization"
    / "selected_test_verifier_log_materialization_manifest.json"
)
STAGE12407_WORKLIST = (
    ROOT
    / "runs/local/artifacts/stage12407_prioritized_adapter_materialization_worklist"
    / "prioritized_adapter_materialization_worklist.jsonl"
)
STAGE12406_CANDIDATES = (
    ROOT
    / "runs/local/artifacts/stage12406_transition_source_expansion_preflight"
    / "source_adapter_candidates.jsonl"
)
UPSTREAM_STAGE_FILES = {
    "stage12322_priority_rust_cpp_selected_test_admission": [
        ROOT
        / "runs/local/artifacts/stage12322_priority_rust_cpp_selected_test_admission"
        / "priority_rust_cpp_selected_test_train_support_rows.jsonl",
        ROOT
        / "runs/local/artifacts/stage12322_priority_rust_cpp_selected_test_admission"
        / "priority_rust_cpp_selected_test_blocked_rows.jsonl",
        ROOT / "runs/summaries/stage12322_priority_rust_cpp_selected_test_admission.json",
    ],
    "stage12326_direct_python_selected_test_admission": [
        ROOT
        / "runs/local/artifacts/stage12326_direct_python_selected_test_admission"
        / "direct_python_selected_test_train_support_rows.jsonl",
        ROOT
        / "runs/local/artifacts/stage12326_direct_python_selected_test_admission"
        / "direct_python_selected_test_blocked_rows.jsonl",
        ROOT / "runs/summaries/stage12326_direct_python_selected_test_admission.json",
    ],
    "stage12355_selected_test_materializer_and_plateau_control": [
        ROOT
        / "runs/local/artifacts/stage12355_selected_test_materializer_and_plateau_control"
        / "selected_test_materializer_and_plateau_control.json",
        ROOT / "runs/summaries/stage12355_selected_test_materializer_and_plateau_control.json",
    ],
    "stage12360_review_corrected_mixed_selected_test_decision": [
        ROOT
        / "runs/local/artifacts/stage12360_review_corrected_mixed_selected_test_decision"
        / "stage12360_admitted_einops_only_rows.jsonl",
        ROOT
        / "runs/local/artifacts/stage12360_review_corrected_mixed_selected_test_decision"
        / "stage12360_deferred_openhands_rows.jsonl",
        ROOT / "runs/summaries/stage12360_review_corrected_mixed_selected_test_decision.json",
    ],
}
REAL_LOG_FILES = {
    "stage12203_controlled_selected_verifier_replay": [
        ROOT
        / "runs/local/artifacts/stage12203_controlled_selected_verifier_replay"
        / "level3_episode_records.jsonl",
        ROOT
        / "runs/local/artifacts/stage12203_controlled_selected_verifier_replay"
        / "command_results.jsonl",
    ],
    "stage12207_no_install_selected_test_log_level3_joiner": [
        ROOT
        / "runs/local/artifacts/stage12207_no_install_selected_test_log_level3_joiner"
        / "no_install_selected_test_level3_records.jsonl",
    ],
    "stage12215_hydratable_selected_verifier_reexecution": [
        ROOT
        / "runs/local/artifacts/stage12215_hydratable_selected_verifier_reexecution"
        / "level3_reexecution_records.jsonl",
        ROOT
        / "runs/local/artifacts/stage12215_hydratable_selected_verifier_reexecution"
        / "reexecution_observations.jsonl",
    ],
}

REQUIRED_JOIN_KEYS = [
    "real_log_stage",
    "real_log_record_id",
    "episode_id",
    "command_result_id",
    "verifier_anchor_id",
    "selected_test_anchor_hash",
    "source_or_test_hash",
    "repo_family_hash",
    "root_lineage_key_hash",
    "verifier_output_class",
    "verifier_status",
    "state_update_id",
    "stop_decision_id",
]
REQUIRED_UPSTREAM_FIELDS = {
    "stage12406_source_adapter_candidates": [
        "source_ref_hash_to_exact_upstream_row_id",
        "source_ref_hash_to_real_log_stage",
        "source_ref_hash_to_real_log_record_id",
        "source_ref_hash_to_episode_id",
        "source_ref_hash_to_command_result_id",
        "source_ref_hash_to_verifier_anchor_id",
        "selected_test_anchor_hash",
        "source_or_test_hash",
    ],
    "stage12407_prioritized_adapter_materialization_worklist": [
        "work_item_id",
        "source_adapter_ref_hash",
        "exact_upstream_row_id",
        "real_log_stage",
        "real_log_record_id",
        "episode_id",
        "command_result_id",
        "verifier_anchor_id",
        "selected_test_anchor_hash",
        "verifier_output_class",
    ],
    "stage12322_12326_12355_12360_selected_test_sources": [
        "row_id",
        "source_row_id",
        "repo_family_hash",
        "root_lineage_key_hash",
        "selected_test_anchor_hash",
        "source_or_test_hash",
        "real_log_stage",
        "real_log_record_id",
        "episode_id",
        "command_result_id",
        "verifier_anchor_id",
        "verifier_status",
        "verifier_output_class",
        "state_update_id",
        "stop_decision_id",
    ],
    "stage12203_12207_12215_real_verifier_logs": [
        "stable_real_log_record_id",
        "episode_id",
        "command_result_id",
        "verifier_anchor_id",
        "selected_test_anchor_hash",
        "source_or_test_hash",
        "repo_family_hash",
        "root_lineage_key_hash",
        "verifier_status",
        "verifier_output_class",
        "state_update_id",
        "stop_decision_id",
    ],
}

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){1,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
RAW_OUTPUT_KEY_RE = re.compile(r"(stdout|stderr|output|tail|command|cmd|argv|cwd|path|url|diff|source_text)", re.I)
COMMANDISH_RE = re.compile(r"\b(python|pytest|cargo|npm|yarn|pnpm|bash|sh|git)\b.+\s(-m|-q|test|run|checkout|diff)\b", re.I)
DIFF_RE = re.compile(r"(^|\n)(diff --git|@@ |\+{3} |--- )")
RISKY_TRUE_KEYS = {
    "training_allowed",
    "train_support_allowed",
    "strict_eval_eligible",
    "source_heldout_admissible",
    "level3_admitted",
    "patch_trace_admitted",
    "repair_claim_admitted",
    "training_rows_created",
    "eval_rows_created",
    "level3_claim_emitted",
    "repair_claim_emitted",
}


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists() or not path.is_file():
        return rows
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def iter_public_strings(value: Any, parent_key: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            found.extend(iter_public_strings(child, str(key)))
    elif isinstance(value, list):
        for child in value:
            found.extend(iter_public_strings(child, parent_key))
    elif isinstance(value, str):
        found.append((parent_key, value))
    return found


def iter_all_strings(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            strings.append(str(key))
            strings.extend(iter_all_strings(child))
    elif isinstance(value, list):
        for child in value:
            strings.extend(iter_all_strings(child))
    elif isinstance(value, str):
        strings.append(value)
    return strings


def safe_record_id(row: dict[str, Any]) -> str:
    for key in ("row_id", "work_item_id", "adapter_id", "episode_id", "command_result_id"):
        if row.get(key):
            return str(row[key])
    return f"record::{stable_hash(row)}"


def flatten_for_join(row: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in [
        "row_id",
        "source_row_id",
        "work_item_id",
        "adapter_id",
        "source_ref_hash",
        "source_adapter_ref_hash",
        "source_record_ref_hash",
        "source_path_hash",
        "source_artifact_hash",
        "repo_family_hash",
        "root_lineage_key_hash",
        "episode_id",
        "command_result_id",
        "state_update_id",
        "stop_decision_id",
        "source_stage",
        "verifier_status",
    ]:
        if row.get(key) not in (None, ""):
            out[key] = str(row[key])
    command_result = row.get("command_result") if isinstance(row.get("command_result"), dict) else {}
    verifier_anchor = row.get("verifier_anchor") if isinstance(row.get("verifier_anchor"), dict) else {}
    selected_anchor = row.get("selected_test_anchor")
    state_update = row.get("state_update") if isinstance(row.get("state_update"), dict) else {}
    stop_decision = row.get("stop_decision") if isinstance(row.get("stop_decision"), dict) else {}
    if command_result.get("command_result_id"):
        out["command_result_id"] = str(command_result["command_result_id"])
    if verifier_anchor.get("verifier_anchor_id"):
        out["verifier_anchor_id"] = str(verifier_anchor["verifier_anchor_id"])
    if isinstance(selected_anchor, dict):
        if selected_anchor.get("selected_test_anchor_hash"):
            out["selected_test_anchor_hash"] = str(selected_anchor["selected_test_anchor_hash"])
        elif selected_anchor:
            out["selected_test_anchor_hash"] = stable_hash(selected_anchor)
    elif isinstance(selected_anchor, str) and selected_anchor:
        out["selected_test_anchor_hash"] = stable_hash(selected_anchor)
    if state_update.get("state_update_id"):
        out["state_update_id"] = str(state_update["state_update_id"])
    if stop_decision.get("stop_decision_id"):
        out["stop_decision_id"] = str(stop_decision["stop_decision_id"])
    transition = row.get("verifier_transition")
    if isinstance(transition, dict):
        if transition.get("to_status"):
            out["verifier_output_class"] = str(transition["to_status"])
        elif transition.get("status"):
            out["verifier_output_class"] = str(transition["status"])
    elif isinstance(transition, str) and transition:
        out["verifier_output_class"] = transition
    return out


def load_upstream_rows() -> dict[str, list[dict[str, Any]]]:
    rows_by_stage: dict[str, list[dict[str, Any]]] = {}
    for stage, paths in UPSTREAM_STAGE_FILES.items():
        rows: list[dict[str, Any]] = []
        for path in paths:
            if path.suffix == ".jsonl":
                rows.extend(read_jsonl(path))
            else:
                obj = read_json(path)
                if obj:
                    rows.append(obj)
        rows_by_stage[stage] = rows
    return rows_by_stage


def load_real_log_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage, paths in REAL_LOG_FILES.items():
        for path in paths:
            for row in read_jsonl(path):
                enriched = dict(row)
                enriched["_real_log_stage"] = stage
                enriched["_real_log_record_id"] = safe_record_id(row)
                enriched["_join_keys"] = flatten_for_join(row)
                rows.append(enriched)
    return rows


def build_token_index(rows: list[dict[str, Any]]) -> dict[str, set[int]]:
    index: dict[str, set[int]] = defaultdict(set)
    for idx, row in enumerate(rows):
        for key, value in flatten_for_join(row).items():
            if value:
                index[f"{key}={value}"].add(idx)
        for value in iter_all_strings(row):
            if re.fullmatch(r"[A-Za-z0-9_:\-]{12,128}", value):
                index[f"string={value}"].add(idx)
    return index


def direct_real_log_join(
    blocked: dict[str, Any],
    work_item: dict[str, Any],
    adapter: dict[str, Any],
    upstream_rows: list[dict[str, Any]],
    real_rows: list[dict[str, Any]],
    real_index: dict[str, set[int]],
) -> dict[str, Any]:
    candidate_tokens: set[str] = set()
    for row in [blocked, work_item, adapter, *upstream_rows]:
        for key, value in flatten_for_join(row).items():
            if value:
                candidate_tokens.add(f"{key}={value}")
                candidate_tokens.add(f"string={value}")

    hit_indexes: set[int] = set()
    matched_token_count = 0
    for token in candidate_tokens:
        hits = real_index.get(token)
        if hits:
            matched_token_count += 1
            hit_indexes.update(hits)

    hit_rows = [real_rows[idx] for idx in sorted(hit_indexes)]
    hit_stages = sorted({str(row.get("_real_log_stage")) for row in hit_rows})
    shared_key_counts = Counter()
    for row in hit_rows:
        for key in (row.get("_join_keys") or {}):
            shared_key_counts[key] += 1

    required_present = set()
    if hit_rows:
        joined_keys = {}
        for row in hit_rows:
            joined_keys.update(row.get("_join_keys") or {})
        field_aliases = {
            "real_log_stage": "_real_log_stage",
            "real_log_record_id": "_real_log_record_id",
            "episode_id": "episode_id",
            "command_result_id": "command_result_id",
            "verifier_anchor_id": "verifier_anchor_id",
            "selected_test_anchor_hash": "selected_test_anchor_hash",
            "source_or_test_hash": "source_or_test_hash",
            "repo_family_hash": "repo_family_hash",
            "root_lineage_key_hash": "root_lineage_key_hash",
            "verifier_output_class": "verifier_output_class",
            "verifier_status": "verifier_status",
            "state_update_id": "state_update_id",
            "stop_decision_id": "stop_decision_id",
        }
        for required, source_key in field_aliases.items():
            if required in {"real_log_stage", "real_log_record_id"}:
                required_present.add(required)
            elif joined_keys.get(source_key):
                required_present.add(required)
    missing = [key for key in REQUIRED_JOIN_KEYS if key not in required_present]
    proven = not missing and len(hit_rows) == 1
    return {
        "direct_real_log_hit_count": len(hit_rows),
        "direct_real_log_hit_stage_counts": dict(Counter(hit_stages)),
        "matched_safe_token_count": matched_token_count,
        "shared_join_key_counts": dict(sorted(shared_key_counts.items())),
        "missing_join_keys": missing,
        "direct_real_verifier_log_join_proven": proven,
    }


def upstream_repair_rows_for(
    source_stage: str,
    adapter: dict[str, Any],
    rows_by_stage: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = rows_by_stage.get(source_stage, [])
    if not rows:
        return []
    needles = {
        str(adapter.get("source_record_ref_hash") or ""),
        str(adapter.get("source_ref_hash") or ""),
        str(adapter.get("source_path_hash") or ""),
        str(adapter.get("source_artifact_hash") or ""),
    }
    needles.discard("")
    if not needles:
        return rows[:2]
    hits = []
    for row in rows:
        strings = set(iter_all_strings(row))
        if strings & needles:
            hits.append(row)
    return hits


def public_guardrail_scan(public_payloads: list[Any]) -> dict[str, Any]:
    raw_leak_counts = Counter()
    raw_leak_examples: list[dict[str, str]] = []
    overclaim_counts = Counter()

    def walk(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for child_key, child in value.items():
                child_key_str = str(child_key)
                if child is True and child_key_str in RISKY_TRUE_KEYS:
                    overclaim_counts[f"{child_key_str}_true"] += 1
                if isinstance(child, int) and child > 0 and child_key_str in {
                    "admitted_rows",
                    "training_row_count",
                    "eval_row_count",
                    "level3_admitted",
                    "patch_trace_admitted",
                    "repair_claim_admitted",
                }:
                    overclaim_counts[f"{child_key_str}_positive"] += 1
                walk(child, child_key_str)
        elif isinstance(value, list):
            for child in value:
                walk(child, key)
        elif isinstance(value, str):
            checks = {
                "raw_path": bool(ABS_PATH_RE.search(value)) or (RAW_OUTPUT_KEY_RE.search(key) and "/" in value),
                "url": bool(URL_RE.search(value)),
                "command": bool(COMMANDISH_RE.search(value)) or (RAW_OUTPUT_KEY_RE.search(key) and " " in value),
                "diff": bool(DIFF_RE.search(value)),
                "multiline_output": RAW_OUTPUT_KEY_RE.search(key) is not None and ("\n" in value or "\r" in value),
            }
            for issue, matched in checks.items():
                if matched:
                    raw_leak_counts[issue] += 1
                    if len(raw_leak_examples) < 10:
                        raw_leak_examples.append({"issue": issue, "field": key, "value_hash": stable_hash(value)})

    for payload in public_payloads:
        walk(payload)
    return {
        "stage": STAGE,
        "scan_passed": not raw_leak_counts and not overclaim_counts,
        "raw_leak_count": sum(raw_leak_counts.values()),
        "raw_leak_issue_counts": dict(sorted(raw_leak_counts.items())),
        "raw_leak_examples": raw_leak_examples,
        "overclaim_count": sum(overclaim_counts.values()),
        "overclaim_issue_counts": dict(sorted(overclaim_counts.items())),
        "public_raw_content_policy": {
            "raw_paths_emitted": False,
            "raw_commands_emitted": False,
            "raw_outputs_emitted": False,
            "source_text_emitted": False,
            "urls_emitted": False,
            "diffs_emitted": False,
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12414 = read_json(STAGE12414_MANIFEST)
    blocked_items = stage12414.get("blocked_items") if isinstance(stage12414.get("blocked_items"), list) else []
    work_items = {
        row.get("source_adapter_ref_hash"): row
        for row in read_jsonl(STAGE12407_WORKLIST)
        if row.get("source_adapter_ref_hash")
    }
    adapters = {
        row.get("source_ref_hash"): row
        for row in read_jsonl(STAGE12406_CANDIDATES)
        if row.get("source_ref_hash")
    }
    rows_by_stage = load_upstream_rows()
    real_rows = load_real_log_rows()
    real_index = build_token_index(real_rows)

    repair_audits: list[dict[str, Any]] = []
    missing_join_key_counts: Counter[str] = Counter()
    source_stage_counts: Counter[str] = Counter()
    blocker_counts: Counter[str] = Counter()
    repairable_items = 0

    for idx, blocked in enumerate(blocked_items, 1):
        source_ref_hash = str(blocked.get("source_adapter_ref_hash") or "")
        work_item = work_items.get(source_ref_hash) or {}
        adapter = adapters.get(source_ref_hash) or {}
        source_stage = str(blocked.get("source_stage") or work_item.get("source_stage") or adapter.get("source_stage") or "unknown")
        upstream_rows = upstream_repair_rows_for(source_stage, adapter, rows_by_stage)
        join = direct_real_log_join(blocked, work_item, adapter, upstream_rows, real_rows, real_index)
        missing_join_key_counts.update(join["missing_join_keys"])
        source_stage_counts[source_stage] += 1
        blocker_counts.update(blocked.get("blocked_reasons") or [])
        if join["direct_real_verifier_log_join_proven"]:
            repairable_items += 1

        repair_audits.append(
            {
                "audit_item_id": f"{STAGE}::{idx:04d}::{stable_hash(blocked)}",
                "source_adapter_ref_hash": source_ref_hash,
                "source_stage": source_stage,
                "source_path_hash": blocked.get("source_path_hash"),
                "work_item_id": blocked.get("work_item_id"),
                "upstream_safe_row_candidates_seen": len(upstream_rows),
                "repair_status": (
                    "repairable_direct_real_verifier_log_join"
                    if join["direct_real_verifier_log_join_proven"]
                    else "unrepaired_missing_direct_real_verifier_log_join"
                ),
                "direct_join_audit": join,
                "schema_fix_required": not join["direct_real_verifier_log_join_proven"],
                "required_schema_fix_ref": "required_schema_fix_manifest",
                "blocked_reason_codes": sorted(set(blocked.get("blocked_reasons") or [])),
            }
        )

    admitted_rows: list[dict[str, Any]] = []
    base_count = int((stage12414.get("counters") or {}).get("base_current_admitted_train_support_tasks") or 0)
    counters = {
        "input_blocked_items": len(blocked_items),
        "repairable_items": repairable_items,
        "unrepaired_items": len(blocked_items) - repairable_items,
        "admitted_rows": len(admitted_rows),
        "training_allowed": bool(admitted_rows),
        "remaining_gap_to_500": max(0, 500 - base_count - len(admitted_rows)),
        "missing_join_key_counts": dict(sorted(missing_join_key_counts.items())),
        "required_upstream_fields": REQUIRED_UPSTREAM_FIELDS,
        "raw_leak_count": 0,
        "overclaim_count": 0,
    }
    required_schema_fix_manifest = {
        "stage": STAGE,
        "decision": "schema_fix_required_before_training_admission",
        "required_upstream_fields": REQUIRED_UPSTREAM_FIELDS,
        "missing_join_key_counts": counters["missing_join_key_counts"],
        "fail_closed_rule": "No row may be emitted unless one exact Stage12203/12207/12215 real verifier-log record is joined by stable IDs and required anchors.",
        "blocked_source_stage_counts": dict(sorted(source_stage_counts.items())),
        "blocked_reason_counts": dict(sorted(blocker_counts.items())),
    }
    manifest = {
        "stage": STAGE,
        "decision": (
            "zero_admission_required_schema_fix"
            if not admitted_rows
            else "admitted_only_rows_with_direct_real_verifier_log_join"
        ),
        "claim_boundary": "Fail-closed lineage repair audit only; public artifacts contain only safe IDs, hashes, counters, and blocker codes.",
        "training_allowed": bool(admitted_rows),
        "admitted_rows": len(admitted_rows),
        "repair_audit_items": repair_audits,
        "required_schema_fix_manifest": required_schema_fix_manifest,
        "artifact_names": {
            "training_rows": "selected_test_lineage_repair_train_support_rows.jsonl",
            "repair_audit": "selected_test_lineage_repair_audit_items.jsonl",
            "required_schema_fix": "required_schema_fix_manifest.json",
            "guardrail_scan": "guardrail_scan.json",
        },
        "counters": counters,
    }
    summary = {
        "stage": STAGE,
        "decision": manifest["decision"],
        "claim_boundary": manifest["claim_boundary"],
        "training_allowed": counters["training_allowed"],
        "admitted_rows": counters["admitted_rows"],
        "remaining_gap_to_500": counters["remaining_gap_to_500"],
        "required_upstream_fields": REQUIRED_UPSTREAM_FIELDS,
        "missing_join_key_counts": counters["missing_join_key_counts"],
        "counters": counters,
        "guardrail_scan_passed": False,
        "required_schema_fix_manifest": required_schema_fix_manifest,
    }

    guardrail = public_guardrail_scan([manifest, summary, repair_audits, required_schema_fix_manifest, admitted_rows])
    counters["raw_leak_count"] = guardrail["raw_leak_count"]
    counters["overclaim_count"] = guardrail["overclaim_count"]
    manifest["counters"] = counters
    summary["counters"] = counters
    summary["guardrail_scan_passed"] = guardrail["scan_passed"]

    write_jsonl(OUT / "selected_test_lineage_repair_train_support_rows.jsonl", admitted_rows)
    write_jsonl(OUT / "selected_test_lineage_repair_audit_items.jsonl", repair_audits)
    write_json(OUT / "required_schema_fix_manifest.json", required_schema_fix_manifest)
    write_json(OUT / "selected_test_lineage_repair_audit_manifest.json", manifest)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(SUMMARY, summary)
    print(json.dumps(counters, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
