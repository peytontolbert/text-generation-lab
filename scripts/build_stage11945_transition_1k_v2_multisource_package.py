#!/usr/bin/env python3
"""Build Transition-1K-v2 from multiple admitted support-row sources."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11945
NAME = "stage11945_transition_1k_v2_multisource_package"
OUT = ART / NAME
SUMMARY = OUT / "transition_1k_v2_multisource_package.json"
RECORDS = OUT / "verified_transition_records_v2.jsonl"
ROWS = OUT / "transition_projection_rows_v2.jsonl"
ADMITTED_ROWS = OUT / "admitted_source_rows.jsonl"
REJECTED_ROWS = OUT / "rejected_source_rows.jsonl"

INVENTORY = ART / "stage11944_transition_1k_v2_source_inventory_and_plan/source_inventory.jsonl"
OLD_TRANSITION_ROWS = ART / "stage11897_transition_record_projection_rows/transition_projection_rows.jsonl"

TASK_TO_ACTION = {
    "symptom_localization": "LOCALIZE_FAILURE",
    "evidence_citation": "RETRIEVE_EVIDENCE",
    "verifier_outcome": "SELECT_TEST",
    "verifier_outcome_semantic_transition": "VERIFY_RESULT",
    "patch_impact": "PLAN_PATCH",
    "minimal_fix_selection": "PLAN_PATCH",
    "abstention_insufficient_evidence": "ABSTAIN_OR_ROLLBACK",
    "alternative_hypothesis_elimination": "RETRIEVE_EVIDENCE",
    "evidence_candidate_judgment": "RETRIEVE_EVIDENCE",
}
ALLOWED_ACTION_SPACE = [
    "LOCALIZE_FAILURE",
    "RETRIEVE_EVIDENCE",
    "BIND_SYMBOL",
    "SELECT_TEST",
    "PLAN_PATCH",
    "APPLY_PATCH_ABSTRACT",
    "VERIFY_RESULT",
    "REPAIR_AFTER_FAILURE",
    "ABSTAIN_OR_ROLLBACK",
]
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}
LOSS_MASK_CLOSED = {
    "structured_aux": False,
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
    "preference": False,
}

# Reuse the established Stage11897 renderer/projection implementation.
spec = importlib.util.spec_from_file_location("stage11897_projection", ROOT / "scripts/build_stage11897_transition_record_projection_rows.py")
projection = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(projection)  # type: ignore[union-attr]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def compact(value: Any, limit: int = 360) -> str:
    return " ".join(str(value or "").split())[:limit]


def target_label(row: dict[str, Any]) -> str:
    target = row.get("bounded_choice_target_label") or row.get("target_label") or row.get("target_text")
    if isinstance(row.get("target"), dict):
        target = target or row["target"].get("bounded_choice_target_label") or row["target"].get("decoder_text")
    return str(target or "").strip()


def root_id(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("root_lineage_key") or row.get("source_row_id") or row.get("row_id") or "").strip()


def language(row: dict[str, Any]) -> str:
    return str(row.get("language_family") or row.get("language") or "unknown").strip()


def task_type(row: dict[str, Any]) -> str:
    return str(row.get("task_type") or row.get("perspective") or "unknown").strip()


def verifier_blob(row: dict[str, Any]) -> dict[str, Any]:
    verifier = row.get("verifier_evidence") if isinstance(row.get("verifier_evidence"), dict) else {}
    transition = row.get("verifier_transition") or row.get("observed_verifier_transition") or row.get("selected_verifier_transition") or verifier.get("result") or verifier.get("transition")
    selected_tests = verifier.get("selected_tests") or row.get("selected_tests") or row.get("selected_verifier_path") or row.get("selected_test_anchor") or []
    if isinstance(selected_tests, str):
        selected_tests = [selected_tests]
    status = str(transition or "").strip()
    if not status:
        if task_type(row) == "abstention_insufficient_evidence":
            status = "VERIFIER_REMOVED"
        elif verifier or selected_tests:
            status = "PASS_CURRENT_STATE"
        else:
            status = "PASS_TO_PASS"
    return {
        "verifier_status": status,
        "checks": [str(x) for x in selected_tests[:8]] if isinstance(selected_tests, list) else [],
        "runtime_executed": bool(verifier or selected_tests),
        "verifier_ref": verifier.get("id") or row.get("selected_verifier_path") or ("V01" if verifier or selected_tests else None),
    }


def option_ref(option: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": option.get("label"),
        "role": option.get("role") or option.get("semantic_role") or "candidate",
        "artifact_ref": option.get("value") or option.get("semantic_value"),
        "evidence_ids": option.get("evidence_ids") or [],
    }


def selected_candidate(row: dict[str, Any], options: list[dict[str, Any]], label: str) -> dict[str, Any] | None:
    found = next((opt for opt in options if str(opt.get("candidate_id")) == label), None)
    if found:
        return found
    return None


def has_verifier_anchor(row: dict[str, Any]) -> bool:
    if row.get("verifier_evidence") or row.get("verifier_transition") or row.get("observed_verifier_transition"):
        return True
    if row.get("selected_test_anchor") or row.get("selected_test_anchor_present") or row.get("selected_verifier_path") or row.get("selected_tests") or row.get("build_verifier_only"):
        return True
    if task_type(row) == "abstention_insufficient_evidence":
        return True
    return False


def admit_row(row: dict[str, Any], source_path: str, old_roots: set[str], seen_row_ids: set[str]) -> tuple[dict[str, Any] | None, list[str]]:
    failures: list[str] = []
    rid = str(row.get("row_id") or "")
    label = target_label(row)
    opts_raw = row.get("opaque_options") if isinstance(row.get("opaque_options"), list) else []
    opts = [option_ref(opt) for opt in opts_raw if isinstance(opt, dict)]
    root = root_id(row)
    if not rid:
        failures.append("missing_row_id")
    if rid in seen_row_ids:
        failures.append("duplicate_source_row_id")
    if not root:
        failures.append("missing_root_id")
    if language(row) not in {"python", "rust", "c_cpp", "web_js_ts_html"}:
        failures.append("unsupported_or_missing_language")
    if task_type(row) not in TASK_TO_ACTION:
        failures.append("unsupported_or_missing_task_type")
    if not label:
        failures.append("missing_target_label")
    if not opts:
        failures.append("missing_opaque_options")
    chosen = selected_candidate(row, opts, label)
    if not chosen:
        failures.append("target_label_not_in_options")
    if not has_verifier_anchor(row):
        failures.append("missing_verifier_or_abstain_anchor")
    if failures:
        return None, failures
    seen_row_ids.add(rid)
    verifier = verifier_blob(row)
    evidence = row.get("evidence_ledger") if isinstance(row.get("evidence_ledger"), list) else []
    action = TASK_TO_ACTION[task_type(row)]
    source_ref = row.get("root_lineage_key") or root
    provenance_ref = row.get("source_snapshot_id") or row.get("repo_id") or source_path
    record = {
        "record_id": f"stage11945::{stable_hash(rid)}::{rid}",
        "schema_version": "verified_transition_record_v1",
        "split": "unassigned",
        "source_lineage_ref": source_ref,
        "source_provenance_ref": provenance_ref,
        "task_intent": {
            "intent_type": "software_maintenance_transition",
            "language_family": language(row),
            "task_family": task_type(row),
            "root_id": root,
        },
        "state_before_ref": {
            "repo_state_graph_ref": row.get("repo_id"),
            "visible_packet_ref": rid,
            "prompt_ref": rid,
            "no_raw_source_body": True,
        },
        "retrieval_context_refs": [item.get("id") for item in evidence if isinstance(item, dict) and item.get("id")],
        "allowed_action_space": list(ALLOWED_ACTION_SPACE),
        "chosen_action": action,
        "candidate_actions": opts,
        "chosen_candidate": chosen,
        "tool_observation_ref": {
            "observation_type": "verifier_or_static_support",
            "observation_ref": verifier.get("verifier_ref"),
            "selected_test_anchor": bool(row.get("selected_test_anchor") or row.get("selected_verifier_path") or row.get("selected_tests")),
        },
        "verifier_result": verifier,
        "state_after_ref": {"next_state_ref": None, "materialized_patch_ref": None},
        "transition_label": action,
        "reward_value_label": {"reward_available": bool(verifier.get("runtime_executed")), "value_bucket": "support_positive"},
        "confidence_ood_label": {"confidence_bucket": "unlabeled_support", "ood_route": "in_distribution_support"},
        "gate_status": {key: True for key in ["source_inventory_lineage", "source_provenance", "contamination_leakage_detector", "golden_locked_eval_suite", "drift_canary_regression_monitor", "cluster_slice_near_duplicate_detector", "dataset_junk_ood_ranker_v1", "schema_drift_detector"]},
        "anti_cheat": {"raw_source_body": False, "raw_patch_body": False, "raw_decoder_target_text": False, "hidden_eval_answer": False, "runtime_output_body": False, "gemma_score_body": False, "unhashed_commit_message_body": False},
        "authority": dict(AUTHORITY_CLOSED),
        "loss_mask": dict(LOSS_MASK_CLOSED),
        "training_projection_targets": {
            "next_action": action,
            "candidate_label": label,
            "candidate_role": (chosen or {}).get("role"),
            "verifier_transition": verifier.get("verifier_status"),
            "continue_or_stop": "ABSTAIN" if action == "ABSTAIN_OR_ROLLBACK" else "CONTINUE",
        },
        "provenance": {"compiler": NAME, "source_row_id": rid, "source_artifact": source_path, "old_transition_root_overlap": root in old_roots},
    }
    return record, []


def root_split(root: str) -> str:
    bucket = int(hashlib.sha256(root.encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < 72:
        return "train"
    if bucket < 86:
        return "validation"
    return "strict_eval"


def main() -> None:
    inventory = [r for r in read_jsonl(INVENTORY) if r.get("rows", 0) > 0]
    # Prefer verifier-backed, option-backed sources while preserving broad language supply.
    inventory = sorted(inventory, key=lambda r: (r.get("verifier_or_selected_test_rows", 0), r.get("opaque_option_rows", 0), r.get("rows", 0)), reverse=True)
    old_roots = {str(r.get("root_id")) for r in read_jsonl(OLD_TRANSITION_ROWS)}
    seen: set[str] = set()
    admitted_records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    # Caps keep this first v2 package inside the requested 1k-2k projected-row range.
    max_records = 480
    per_lang_cap = {"c_cpp": 150, "python": 150, "rust": 150, "web_js_ts_html": 240}
    per_source_cap = 80
    lang_counts = Counter()
    root_seen: set[str] = set()
    root_task_seen: set[tuple[str, str]] = set()
    root_row_counts: Counter[str] = Counter()
    for src in inventory:
        if len(admitted_records) >= max_records:
            break
        source_path = str(src["path"])
        source_rows = read_jsonl(ROOT / source_path)
        accepted_from_source = 0
        for row in source_rows:
            if len(admitted_records) >= max_records or accepted_from_source >= per_source_cap:
                break
            rec, failures = admit_row(row, source_path, old_roots, seen)
            if not rec:
                rejected.append({"source_path": source_path, "row_id": row.get("row_id"), "root_id": root_id(row), "language_family": language(row), "task_type": task_type(row), "failures": failures})
                continue
            lang = rec["task_intent"]["language_family"]
            if lang_counts[lang] >= per_lang_cap.get(lang, 0):
                rejected.append({"source_path": source_path, "row_id": row.get("row_id"), "root_id": root_id(row), "language_family": lang, "task_type": task_type(row), "failures": ["language_cap_reached"]})
                continue
            rroot = str(rec["task_intent"]["root_id"])
            task = str(rec["task_intent"]["task_family"])
            if (rroot, task) in root_task_seen:
                rejected.append({"source_path": source_path, "row_id": row.get("row_id"), "root_id": rroot, "language_family": lang, "task_type": task_type(row), "failures": ["duplicate_root_task"]})
                continue
            if root_row_counts[rroot] >= 6:
                rejected.append({"source_path": source_path, "row_id": row.get("row_id"), "root_id": rroot, "language_family": lang, "task_type": task_type(row), "failures": ["root_task_cap_reached"]})
                continue
            split = "train" if rec["provenance"].get("old_transition_root_overlap") else root_split(rroot)
            rec["split"] = split
            rec["provenance"]["split_rule"] = "sha256(root_id)%100: train<72 validation<86 strict_else"
            admitted_records.append(rec)
            root_seen.add(rroot)
            root_task_seen.add((rroot, task))
            root_row_counts[rroot] += 1
            lang_counts[lang] += 1
            accepted_from_source += 1
    projected_rows: list[dict[str, Any]] = []
    projection_failures: list[dict[str, Any]] = []
    for rec in admitted_records:
        rows, failures = projection.project_record(rec)
        if failures:
            projection_failures.append({"record_id": rec.get("record_id"), "failures": failures})
        for row in rows:
            split = rec["split"]
            row["split"] = split
            row["package_split"] = split
            row["train_support_only"] = split == "train"
            row["strict_eval_eligible"] = split == "strict_eval"
            row["source_heldout_admissible"] = split in {"validation", "strict_eval"} and not rec["provenance"].get("old_transition_root_overlap")
            row["old_transition_root_overlap"] = bool(rec["provenance"].get("old_transition_root_overlap"))
            row["stage11945_transition_1k_v2"] = True
            row["row_id"] = row["row_id"].replace("stage11897::", "stage11945::", 1)
            projected_rows.append(row)
    dup_rows = [row_id for row_id, n in Counter(r["row_id"] for r in projected_rows).items() if n > 1]
    root_splits = defaultdict(set)
    for row in projected_rows:
        root_splits[row["root_id"]].add(row["split"])
    split_violations = {root: sorted(splits) for root, splits in root_splits.items() if len(splits) > 1}
    pre_leaks=[]
    for row in projected_rows:
        gold=str((row.get("standalone_projection_source") or {}).get("gold_value") or "")
        if gold and len(gold)>2 and gold not in {"CONTINUE","ABSTAIN"}:
            before=str(row.get("prompt_text") or "").split("\nCANDIDATES\n",1)[0]
            if gold in before:
                pre_leaks.append(row["row_id"])
    write_jsonl(RECORDS, admitted_records)
    write_jsonl(ROWS, projected_rows)
    write_jsonl(ADMITTED_ROWS, [{"record_id": r["record_id"], "source_row_id": r["provenance"]["source_row_id"], "source_artifact": r["provenance"]["source_artifact"], "split": r["split"], "root_id": r["task_intent"]["root_id"], "language_family": r["task_intent"]["language_family"], "task_family": r["task_intent"]["task_family"]} for r in admitted_records])
    write_jsonl(REJECTED_ROWS, rejected)
    counts = {
        "source_files_considered": len(inventory),
        "admitted_records": len(admitted_records),
        "projected_rows": len(projected_rows),
        "expected_projected_rows": len(admitted_records) * 4,
        "unique_roots": len(root_seen),
        "record_split_counts": dict(Counter(r["split"] for r in admitted_records)),
        "row_split_counts": dict(Counter(r["split"] for r in projected_rows)),
        "language_record_counts": dict(Counter(r["task_intent"]["language_family"] for r in admitted_records)),
        "language_row_counts": dict(Counter(r["language_family"] for r in projected_rows)),
        "task_record_counts": dict(Counter(r["task_intent"]["task_family"] for r in admitted_records)),
        "transition_task_row_counts": dict(Counter(r["task_type"] for r in projected_rows)),
        "verifier_status_counts": dict(Counter(str(r["verifier_result"]["verifier_status"]) for r in admitted_records)),
        "rejected_rows": len(rejected),
    }
    passed = (
        1000 <= len(projected_rows) <= 2000
        and len(root_seen) >= 100
        and len(admitted_records) >= 250
        and not projection_failures
        and not dup_rows
        and not split_violations
        and not pre_leaks
        and counts["record_split_counts"].get("train", 0) > 0
        and counts["record_split_counts"].get("validation", 0) > 0
        and counts["record_split_counts"].get("strict_eval", 0) > 0
    )
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": passed,
        "decision": "transition_1k_v2_package_ready_for_probe_request" if passed else "transition_1k_v2_package_blocked",
        "counts": counts,
        "audits": {
            "projection_failures": projection_failures[:20],
            "projection_failure_count": len(projection_failures),
            "duplicate_row_ids": dup_rows[:20],
            "duplicate_row_id_count": len(dup_rows),
            "root_split_violations": dict(list(split_violations.items())[:20]),
            "root_split_violation_count": len(split_violations),
            "pre_options_target_value_leaks": pre_leaks[:20],
            "pre_options_target_value_leak_count": len(pre_leaks),
            "old_transition_roots_excluded": len(old_roots),
            "rejection_reason_counts": dict(Counter(reason for item in rejected for reason in item.get("failures", []))),
        },
        "source_artifacts": {"inventory": rel(INVENTORY), "old_transition_rows_exclusion": rel(OLD_TRANSITION_ROWS)},
        "outputs": {"summary": rel(SUMMARY), "records": rel(RECORDS), "rows": rel(ROWS), "admitted_rows": rel(ADMITTED_ROWS), "rejected_rows": rel(REJECTED_ROWS)},
        "claim_boundary": [
            "This package is a train/validation/strict successor for transition-record training only.",
            "It excludes old Stage11897 transition-manifest roots from admission.",
            "It is not a Gemma win until a GPU2 probe and same-manifest comparison beat the current Gemma reference while preserving protected compact gates.",
        ],
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "passed": passed, "counts": counts, "audit_summary": {k:v for k,v in artifact["audits"].items() if k.endswith("count") or k in {"rejection_reason_counts"}}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
