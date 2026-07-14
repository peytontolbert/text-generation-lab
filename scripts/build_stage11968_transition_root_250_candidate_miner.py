#!/usr/bin/env python3
"""Mine candidate executable transition roots for the Stage11967 Root-250 contract."""

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
STAGE = 11968
NAME = "stage11968_transition_root_250_candidate_miner"
OUT = ART / NAME
SUMMARY = OUT / "transition_root_250_candidate_miner.json"
QUEUE = OUT / "transition_root_250_candidate_queue.jsonl"
REPAIR_QUEUE = OUT / "transition_root_250_repair_queue.jsonl"
SOURCE_INVENTORY = ART / "stage11944_transition_1k_v2_source_inventory_and_plan/source_inventory.jsonl"
BASE_RECORDS = ART / "stage11955_transition_5k_v1_multisource_package/verified_transition_records_5k_v1.jsonl"
CONTRACT = ART / "stage11967_transition_root_250_supply_contract/transition_root_250_supply_contract.json"

NEEDED_LANG_ROOTS = {"python": 37, "c_cpp": 34, "rust": 23}
NEEDED_STATUSES = {"FAIL_TO_PASS": 30, "PASS_CURRENT_BUILD": 34, "INSUFFICIENT_EVIDENCE": 40, "NOT_EXERCISED": 40}
PRIMARY_LANGS = {"python", "c_cpp", "rust"}
KNOWN_STATUSES = {
    "FAIL_TO_PASS",
    "PASS_TO_PASS",
    "PASS_CURRENT_STATE",
    "PASS_CURRENT_BUILD",
    "PASS_CURRENT_BUILD_AND_RUN",
    "INSUFFICIENT_EVIDENCE",
    "NOT_EXERCISED",
    "VERIFIER_REMOVED",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def nested(d: dict[str, Any], *keys: str) -> Any:
    cur: Any = d
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def row_root(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("root_lineage_key") or nested(row, "task_intent", "root_id") or row.get("source_lineage_ref") or "")


def row_language(row: dict[str, Any]) -> str:
    return str(row.get("language_family") or nested(row, "task_intent", "language_family") or row.get("language") or "unknown")


def row_options(row: dict[str, Any]) -> list[Any]:
    options = row.get("opaque_options")
    if not isinstance(options, list):
        options = nested(row, "standalone_projection_source", "opaque_options")
    return options if isinstance(options, list) else []


def normalize_status(value: Any) -> str:
    text = str(value or "").upper()
    if not text:
        return "UNKNOWN"
    aliases = {
        "FAIL_UNDER_MUTANT": "FAIL_TO_PASS",
        "PASS_AFTER_RESTORE": "FAIL_TO_PASS",
        "PASS": "PASS_TO_PASS",
    }
    if text in aliases:
        return aliases[text]
    for status in KNOWN_STATUSES:
        if status in text:
            return status
    return text or "UNKNOWN"


def row_status(row: dict[str, Any]) -> str:
    value = (
        row.get("verifier_transition")
        or nested(row, "verifier_evidence", "transition")
        or nested(row, "verifier_evidence", "result")
        or nested(row, "standalone_projection_source", "observed_transition")
        or nested(row, "training_projection_targets", "verifier_transition")
        or nested(row, "verifier_result", "verifier_status")
        or nested(row, "verifier_result", "transition")
    )
    return normalize_status(value)


def has_verifier(row: dict[str, Any]) -> bool:
    verifier = row.get("verifier_evidence") if isinstance(row.get("verifier_evidence"), dict) else {}
    if verifier:
        return True
    if row.get("selected_test_anchor") or row.get("verifier_anchor"):
        return True
    if nested(row, "tool_observation_ref", "selected_test_anchor"):
        return True
    prompt = str(row.get("prompt_text") or row.get("input_text") or "").lower()
    return "observed" in prompt and ("verifier" in prompt or "test" in prompt)


def has_actual_log(row: dict[str, Any]) -> bool:
    verifier = row.get("verifier_evidence") if isinstance(row.get("verifier_evidence"), dict) else {}
    keys = {"stdout_log", "stderr_log", "baseline_log_path", "mutant_log_path", "restored_log_path", "command"}
    if any(verifier.get(key) for key in keys):
        return True
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    return "Observed" in prompt and ("Test Files" in prompt or "pytest" in prompt or "vitest" in prompt or "cargo" in prompt)


def source_kind(row: dict[str, Any]) -> str:
    text = " ".join(str(row.get(key) or "") for key in ("source_kind", "split_component", "row_id", "root_id"))
    if "counterfactual" in text:
        return "counterfactual"
    if "controlled_bug_injection" in text or "controlled_fail_to_pass" in text or "mutation" in text or "mutant" in text:
        return "controlled_mutation"
    return "observed_support"


def anti_cheat_state(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    counts = Counter()
    for row in rows:
        ac = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        if ac.get("deterministic_option_shuffle") is True:
            counts["deterministic_option_shuffle"] += 1
        if ac.get("target_label_not_visible_before_options") is True or ac.get("gold_label_visible_before_options") is False:
            counts["target_label_safe"] += 1
        if ac.get("target_value_not_visible_before_options") is True or ac.get("gold_semantic_value_visible_as_legitimate_trace_or_snippet") is True:
            counts["target_value_safe_or_legitimate"] += 1
        if ac.get("singleton_options") is False:
            counts["no_singleton_options"] += 1
    return {
        "rows": total,
        "deterministic_option_shuffle_rows": counts["deterministic_option_shuffle"],
        "target_label_safe_rows": counts["target_label_safe"],
        "target_value_safe_or_legitimate_rows": counts["target_value_safe_or_legitimate"],
        "no_singleton_option_rows": counts["no_singleton_options"],
    }


def base_roots() -> set[str]:
    roots: set[str] = set()
    for record in read_jsonl(BASE_RECORDS):
        rid = row_root(record)
        if rid:
            roots.add(rid)
    return roots


def root_score(root: dict[str, Any], existing_roots: set[str]) -> tuple[int, list[str], list[str]]:
    score = 0
    reasons: list[str] = []
    blockers: list[str] = []
    rid = root["root_id"]
    lang = root["language_family"]
    statuses = set(root["status_counts"])
    if rid in existing_roots:
        blockers.append("already_in_base_transition_records")
    if lang in PRIMARY_LANGS:
        score += 20
        reasons.append("primary_language_deficit_lane")
    else:
        score -= 12
        reasons.append("web_or_nonprimary_language_cap_lane")
    if lang in NEEDED_LANG_ROOTS:
        score += min(30, NEEDED_LANG_ROOTS[lang])
        reasons.append(f"language_root_deficit::{lang}")
    for status in statuses:
        if status in NEEDED_STATUSES:
            add = min(40, NEEDED_STATUSES[status])
            score += add
            reasons.append(f"status_deficit::{status}")
    if root["has_actual_log"]:
        score += 25
        reasons.append("actual_verifier_or_command_log")
    elif root["has_verifier"]:
        score += 10
        reasons.append("verifier_or_selected_test_anchor")
    else:
        blockers.append("missing_verifier_or_selected_test_anchor")
    if root["min_option_count"] < 2:
        blockers.append("missing_competing_options")
    if root["source_kind_counts"].get("counterfactual", 0):
        blockers.append("counterfactual_not_root_scale")
    if root["source_kind_counts"].get("controlled_mutation", 0):
        reasons.append("controlled_mutation_train_support_only")
    if not root["anti_cheat_summary"]["deterministic_option_shuffle_rows"]:
        blockers.append("deterministic_option_shuffle_not_declared")
    if not root["anti_cheat_summary"]["target_label_safe_rows"]:
        blockers.append("target_label_leak_review_required")
    if blockers:
        score -= 50 + (10 * len(blockers))
    return score, reasons, blockers


def main() -> None:
    inventory = read_jsonl(SOURCE_INVENTORY)
    existing_roots = base_roots()
    root_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_file_errors: list[dict[str, Any]] = []
    scanned_files = 0
    for item in inventory:
        path = ROOT / str(item.get("path") or "")
        if not path.exists():
            source_file_errors.append({"path": str(item.get("path")), "error": "missing_source_file"})
            continue
        scanned_files += 1
        for row in read_jsonl(path):
            rid = row_root(row)
            if not rid:
                continue
            r = dict(row)
            r["__source_file"] = rel(path)
            root_rows[rid].append(r)

    roots: list[dict[str, Any]] = []
    for rid, rows in root_rows.items():
        languages = Counter(row_language(row) for row in rows)
        statuses = Counter(row_status(row) for row in rows)
        tasks = Counter(str(row.get("task_type") or nested(row, "task_intent", "task_family") or "unknown") for row in rows)
        source_kinds = Counter(source_kind(row) for row in rows)
        option_counts = [len(row_options(row)) for row in rows]
        files = sorted({str(row.get("__source_file")) for row in rows})
        root = {
            "root_id": rid,
            "language_family": languages.most_common(1)[0][0] if languages else "unknown",
            "rows": len(rows),
            "source_files": files,
            "language_counts": dict(languages),
            "task_counts": dict(tasks),
            "status_counts": dict(statuses),
            "source_kind_counts": dict(source_kinds),
            "has_verifier": any(has_verifier(row) for row in rows),
            "has_actual_log": any(has_actual_log(row) for row in rows),
            "min_option_count": min(option_counts) if option_counts else 0,
            "max_option_count": max(option_counts) if option_counts else 0,
            "anti_cheat_summary": anti_cheat_state(rows),
            "sample_row_ids": [str(row.get("row_id") or "") for row in rows[:5]],
        }
        score, reasons, blockers = root_score(root, existing_roots)
        root["admission_score"] = score
        root["admission_reasons"] = reasons
        root["blockers"] = blockers
        root["admit_role"] = "admit_candidate" if score > 0 and not blockers else "repair_or_quarantine"
        roots.append(root)

    candidates = sorted((root for root in roots if root["admit_role"] == "admit_candidate"), key=lambda item: (-item["admission_score"], item["root_id"]))
    repair = sorted((root for root in roots if root["admit_role"] != "admit_candidate"), key=lambda item: (-item["admission_score"], item["root_id"]))
    write_jsonl(QUEUE, candidates)
    write_jsonl(REPAIR_QUEUE, repair)

    candidate_lang_roots = Counter(root["language_family"] for root in candidates)
    candidate_status_roots: Counter[str] = Counter()
    for root in candidates:
        for status in root["status_counts"]:
            candidate_status_roots[status] += 1
    repair_blockers = Counter(blocker for root in repair for blocker in root["blockers"])
    top_by_status: dict[str, list[dict[str, Any]]] = {}
    for status in sorted(NEEDED_STATUSES):
        top_by_status[status] = [
            {"root_id": root["root_id"], "language_family": root["language_family"], "score": root["admission_score"], "source_files": root["source_files"][:3], "status_counts": root["status_counts"]}
            for root in candidates
            if status in root["status_counts"]
        ][:20]

    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "transition_root_250_candidate_queue_ready",
        "source_inventory": rel(SOURCE_INVENTORY),
        "scanned_source_files": scanned_files,
        "source_file_errors": source_file_errors[:50],
        "existing_base_roots": len(existing_roots),
        "root_scan_counts": {
            "total_candidate_roots_seen": len(roots),
            "admit_candidates": len(candidates),
            "repair_or_quarantine": len(repair),
        },
        "candidate_summary": {
            "candidate_roots_by_language": dict(candidate_lang_roots),
            "candidate_roots_by_status": dict(candidate_status_roots),
            "top_candidates": candidates[:50],
            "top_candidates_by_needed_status": top_by_status,
        },
        "repair_summary": {
            "top_blockers": dict(repair_blockers.most_common(20)),
            "top_repair_items": repair[:50],
        },
        "contract_gap_after_current_candidate_queue": {
            "note": "This is a candidate/admission queue, not yet a compiled transition record package.",
            "candidate_roots_available": len(candidates),
            "candidate_primary_language_roots": {lang: candidate_lang_roots.get(lang, 0) for lang in sorted(PRIMARY_LANGS)},
            "candidate_needed_status_roots": {status: candidate_status_roots.get(status, 0) for status in sorted(NEEDED_STATUSES)},
            "still_needs_materialization": [
                "compile admitted candidates into verified_transition_record_v1",
                "ensure root/repo/time split before projection",
                "verify logs/checks exist and are not only prompt text",
                "cap web roots and counterfactual/verifier_removed rows",
            ],
        },
        "next_stage_recommendation": {
            "stage": "stage11969_transition_root_250_materialization_plan",
            "goal": "Take the highest-scoring admit candidates, materialize verified_transition_record_v1, and prove the contract gap closes without counterfactual root inflation.",
            "priority": [
                "non-web FAIL_TO_PASS candidates if available",
                "PASS_CURRENT_BUILD candidates",
                "Python/C++/Rust roots not already in Stage11955 base records",
                "repair missing anti-cheat fields for otherwise strong verifier-backed roots",
            ],
        },
        "source_artifacts": {
            "contract": rel(CONTRACT),
            "base_records": rel(BASE_RECORDS),
            "queue": rel(QUEUE),
            "repair_queue": rel(REPAIR_QUEUE),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "root_scan_counts": artifact["root_scan_counts"], "candidate_summary": artifact["candidate_summary"], "repair_top_blockers": artifact["repair_summary"]["top_blockers"], "next_stage": artifact["next_stage_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
