#!/usr/bin/env python3
"""Create verifier-status counterfactual transition records from clean Stage11955 records.

The counterfactuals are train-support only. They do not create new roots or
source-heldout evidence; they add explicit verifier-removed / insufficient /
not-exercised decision boundaries from already admitted verifier-backed records.
"""

from __future__ import annotations

import copy
import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11957
NAME = "stage11957_transition_counterfactual_status_augmentation"
OUT = ART / NAME
SUMMARY = OUT / "transition_counterfactual_status_augmentation.json"
RECORDS = OUT / "counterfactual_transition_records.jsonl"
ROWS = OUT / "counterfactual_transition_projection_rows.jsonl"

SOURCE_RECORDS = ART / "stage11955_transition_5k_v1_multisource_package/verified_transition_records_5k_v1.jsonl"

import importlib.util

projection_spec = importlib.util.spec_from_file_location(
    "stage11897_projection",
    ROOT / "scripts/build_stage11897_transition_record_projection_rows.py",
)
projection = importlib.util.module_from_spec(projection_spec)
assert projection_spec and projection_spec.loader
projection_spec.loader.exec_module(projection)  # type: ignore[union-attr]


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


def language(record: dict[str, Any]) -> str:
    return str((record.get("task_intent") or {}).get("language_family") or "unknown")


def root_id(record: dict[str, Any]) -> str:
    return str((record.get("task_intent") or {}).get("root_id") or record.get("source_lineage_ref") or "")


def has_verifier(record: dict[str, Any]) -> bool:
    verifier = record.get("verifier_result") if isinstance(record.get("verifier_result"), dict) else {}
    status = str(verifier.get("verifier_status") or "")
    return bool(verifier.get("runtime_executed")) and status not in {"", "VERIFIER_REMOVED", "INSUFFICIENT_EVIDENCE", "NOT_EXERCISED"}


def abstain_candidate(status: str) -> dict[str, Any]:
    role = {
        "VERIFIER_REMOVED": "abstain_verifier_removed",
        "INSUFFICIENT_EVIDENCE": "abstain_insufficient_evidence",
        "NOT_EXERCISED": "abstain_not_exercised_by_verifier",
    }.get(status, "abstain_counterfactual")
    return {
        "candidate_id": f"CF_{status}",
        "role": role,
        "artifact_ref": status,
        "evidence_ids": [],
    }


def make_counterfactual(record: dict[str, Any], status: str) -> dict[str, Any]:
    out = copy.deepcopy(record)
    out["record_id"] = f"{record.get('record_id')}::counterfactual::{status.lower()}"
    out["split"] = "train"
    out["source_lineage_ref"] = f"{record.get('source_lineage_ref')}::counterfactual::{status.lower()}"
    out["state_before_ref"] = dict(out.get("state_before_ref") or {})
    out["state_before_ref"]["visible_packet_ref"] = f"{out['state_before_ref'].get('visible_packet_ref')}::counterfactual::{status.lower()}"
    out["task_intent"] = dict(out.get("task_intent") or {})
    out["task_intent"]["root_id"] = f"{root_id(record)}::counterfactual::{status.lower()}"
    out["chosen_action"] = "ABSTAIN_OR_ROLLBACK"
    allowed = list(out.get("allowed_action_space") or [])
    if "ABSTAIN_OR_ROLLBACK" not in allowed:
        allowed.append("ABSTAIN_OR_ROLLBACK")
    out["allowed_action_space"] = allowed

    candidates = [dict(c) for c in (out.get("candidate_actions") or []) if isinstance(c, dict)]
    abstain = abstain_candidate(status)
    candidates.append(abstain)
    out["candidate_actions"] = candidates
    out["chosen_candidate"] = abstain
    out["verifier_result"] = {
        "verifier_status": status,
        "checks": [],
        "runtime_executed": False,
        "verifier_ref": None,
        "counterfactual_from_record_id": record.get("record_id"),
        "counterfactual_reason": "verifier evidence withheld or not exercising the claimed behavior; safest maintainer decision is not to assert completion.",
    }
    out["tool_observation_ref"] = {
        "observation_type": "counterfactual_missing_or_nonexercising_verifier",
        "observation_ref": None,
        "selected_test_anchor": False,
    }
    out["training_projection_targets"] = {
        "next_action": "ABSTAIN_OR_ROLLBACK",
        "candidate_label": abstain["candidate_id"],
        "candidate_role": abstain["role"],
        "verifier_transition": status,
        "continue_or_stop": "ABSTAIN",
    }
    out["retrieval_context_refs"] = []
    out["authority"] = dict(out.get("authority") or {})
    out["authority"]["promotion_ready"] = False
    out["loss_mask"] = dict(out.get("loss_mask") or {})
    out["loss_mask"].update({"decoder_ce": False, "bounded_choice_aux": True, "structured_aux": True, "transition_projection": True})
    out["provenance"] = dict(out.get("provenance") or {})
    out["provenance"].update(
        {
            "compiler": NAME,
            "counterfactual_status": status,
            "counterfactual_from_record_id": record.get("record_id"),
            "train_support_only": True,
            "source_heldout_admissible": False,
            "does_not_create_new_root_supply": True,
        }
    )
    out["anti_cheat"] = dict(out.get("anti_cheat") or {})
    out["anti_cheat"].update(
        {
            "counterfactual_record": True,
            "raw_source_body": False,
            "raw_patch_body": False,
            "hidden_eval_answer": False,
            "source_heldout_claim_eligible": False,
        }
    )
    return out


def statuses_for(record: dict[str, Any]) -> list[str]:
    lang = language(record)
    if lang in {"c_cpp", "python", "rust"}:
        return ["VERIFIER_REMOVED", "INSUFFICIENT_EVIDENCE", "NOT_EXERCISED"]
    return ["VERIFIER_REMOVED"]


def main() -> None:
    source_records = read_jsonl(SOURCE_RECORDS)
    counterfactuals: list[dict[str, Any]] = []
    for record in source_records:
        if not has_verifier(record):
            continue
        for status in statuses_for(record):
            counterfactuals.append(make_counterfactual(record, status))

    projected_rows: list[dict[str, Any]] = []
    projection_failures: list[dict[str, Any]] = []
    for record in counterfactuals:
        rows, failures = projection.project_record(record)
        if failures:
            projection_failures.append({"record_id": record.get("record_id"), "failures": failures})
        for row in rows:
            row["split"] = "train"
            row["package_split"] = "train"
            row["train_support_only"] = True
            row["strict_eval_eligible"] = False
            row["source_heldout_admissible"] = False
            row["stage11957_counterfactual_status_augmentation"] = True
            row["row_id"] = row["row_id"].replace("stage11897::", "stage11957::", 1)
            projected_rows.append(row)

    duplicate_row_ids = [rid for rid, count in Counter(str(row.get("row_id")) for row in projected_rows).items() if count > 1]
    pre_option_leaks: list[str] = []
    for row in projected_rows:
        gold = str((row.get("standalone_projection_source") or {}).get("gold_value") or "")
        if gold and len(gold) > 2 and gold not in {"CONTINUE", "ABSTAIN"}:
            before = str(row.get("prompt_text") or "").split("\nCANDIDATES\n", 1)[0]
            if gold in before:
                pre_option_leaks.append(str(row.get("row_id")))

    by_lang_status: dict[str, Counter[str]] = defaultdict(Counter)
    for record in counterfactuals:
        by_lang_status[language(record)][str((record.get("verifier_result") or {}).get("verifier_status"))] += 1

    counts = {
        "source_records": len(source_records),
        "counterfactual_records": len(counterfactuals),
        "projected_rows": len(projected_rows),
        "expected_projected_rows": len(counterfactuals) * 4,
        "unique_counterfactual_roots": len({root_id(record) for record in counterfactuals}),
        "language_record_counts": dict(Counter(language(record) for record in counterfactuals)),
        "verifier_status_counts": dict(Counter(str((record.get("verifier_result") or {}).get("verifier_status")) for record in counterfactuals)),
        "language_status_counts": {lang: dict(counter) for lang, counter in sorted(by_lang_status.items())},
        "transition_task_row_counts": dict(Counter(str(row.get("task_type")) for row in projected_rows)),
    }
    passed = (
        len(counterfactuals) > 0
        and len(projected_rows) == len(counterfactuals) * 4
        and not projection_failures
        and not duplicate_row_ids
        and not pre_option_leaks
    )

    write_jsonl(RECORDS, counterfactuals)
    write_jsonl(ROWS, projected_rows)
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": passed,
        "decision": "counterfactual_status_augmentation_ready_for_train_support" if passed else "counterfactual_status_augmentation_blocked",
        "counts": counts,
        "audits": {
            "projection_failures": projection_failures[:20],
            "projection_failure_count": len(projection_failures),
            "duplicate_row_ids": duplicate_row_ids[:20],
            "duplicate_row_id_count": len(duplicate_row_ids),
            "pre_options_target_value_leaks": pre_option_leaks[:20],
            "pre_options_target_value_leak_count": len(pre_option_leaks),
        },
        "claim_boundary": [
            "These rows are counterfactual train-support only.",
            "They do not add independent roots and must not be counted as source-heldout promotion evidence.",
            "They are valid for verifier-status, abstain, and continue/stop supervision because the prompt explicitly withholds or marks verifier evidence as non-exercising.",
        ],
        "source_artifacts": {"source_records": rel(SOURCE_RECORDS)},
        "outputs": {"summary": rel(SUMMARY), "records": rel(RECORDS), "rows": rel(ROWS)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "passed": passed, "counts": counts, "audits": artifact["audits"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
