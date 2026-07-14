#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"

STAGE = 11491
NAME = "stage11491_residual50_listwise_group_compiler"
OUT = ART / NAME
SUMMARY = OUT / "residual50_listwise_group_compiler.json"
GROUPS = OUT / "residual50_listwise_groups.jsonl"
GROUPED_ROWS = OUT / "residual50_listwise_grouped_rows.jsonl"
QUARANTINE = OUT / "residual50_listwise_quarantine_rows.jsonl"

RESIDUAL50 = ART / "stage11481_residual50_ready_package_with_rust_counters/residual50_ready_rows.jsonl"
READINESS = ART / "stage11490_same_root_listwise_objective_readiness/same_root_listwise_objective_readiness.json"
FILTERED_VALIDATION = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl"
FILTERED_STRICT = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
RESIDUAL_BANK = ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def sha16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("row_id") or "")


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def prompt_text(row: dict[str, Any]) -> str:
    return str(row.get("input_text") or row.get("prompt_text") or row.get("prompt") or "")


def evidence_state_text(row: dict[str, Any]) -> str:
    """Visible state without the option-label presentation surface."""
    text = prompt_text(row)
    text = re.split(r"\nOptions:\n", text, maxsplit=1)[0]
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def options(row: dict[str, Any]) -> list[dict[str, str]]:
    source = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    raw = source.get("opaque_options") or row.get("opaque_options") or []
    out: list[dict[str, str]] = []
    for option in raw:
        if not isinstance(option, dict):
            continue
        label = str(option.get("label") or "").strip()
        value = str(option.get("value") or "").strip()
        if label and value:
            out.append({"label": label, "value": value})
    return out


def target_value(row: dict[str, Any]) -> str:
    target = str(row.get("bounded_choice_target_label") or "").strip()
    for option in options(row):
        if option["label"] == target:
            return option["value"]
    return ""


def normalized_role(value: str) -> str:
    mapping = {
        "SUPPORTING_CANDIDATE_CHANGE_SURFACE": "candidate_change_surface",
        "DECISIVE_VERIFIER_TEST_CONSTRAINT": "verifier_and_test_constraint",
        "DECISIVE_SELECTED_TEST_CONSTRAINT": "verifier_and_test_constraint",
        "DECISIVE_BUILD_VERIFIER_CONSTRAINT": "verifier_and_test_constraint",
        "OBSERVED_VERIFIER_LOG": "symptom_or_call_path_analogue",
        "OBSERVED_VERIFIER_PASS_LOG": "symptom_or_call_path_analogue",
        "OBSERVED_VERIFIER_FAILURE_LOG": "symptom_or_call_path_analogue",
        "SUPPORTING_SYMPTOM_OR_CALL_PATH": "symptom_or_call_path_analogue",
        "DISTRACTOR_BACKGROUND_CONTEXT": "nearby_definition_or_usage_context",
    }
    return mapping.get(value, value)


def group_key(row: dict[str, Any]) -> str:
    return f"{root_key(row)}::state::{sha16(evidence_state_text(row))}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    residual50 = read_jsonl(RESIDUAL50)
    readiness = read_json(READINESS)
    protected = read_jsonl(FILTERED_VALIDATION) + read_jsonl(FILTERED_STRICT) + read_jsonl(RESIDUAL_BANK)
    protected_row_ids = {row_id(row) for row in protected}
    protected_roots = {root_key(row) for row in protected}

    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in residual50:
        by_group[group_key(row)].append(row)

    group_records: list[dict[str, Any]] = []
    grouped_rows: list[dict[str, Any]] = []
    quarantine_rows: list[dict[str, Any]] = []
    quarantine_reasons = Counter()
    group_size_counts = Counter()
    group_role_counts = Counter()
    trainable_groups = 0
    singleton_groups = 0
    contradictory_groups = 0
    protected_overlap_groups = 0

    for key, rows in sorted(by_group.items()):
        roles = [normalized_role(target_value(row)) for row in rows]
        role_counter = Counter(role for role in roles if role)
        group_size_counts[len(rows)] += 1
        for role, count in role_counter.items():
            group_role_counts[role] += count
        row_overlap = sorted(row_id(row) for row in rows if row_id(row) in protected_row_ids)
        root_overlap = sorted({root_key(row) for row in rows if root_key(row) in protected_roots})
        contradictory = len(role_counter) > 1
        singleton = len(rows) == 1
        trainable = (not contradictory) and (not row_overlap) and (not root_overlap)
        if singleton:
            singleton_groups += 1
            trainable = False
        if contradictory:
            contradictory_groups += 1
        if row_overlap or root_overlap:
            protected_overlap_groups += 1
        if trainable:
            trainable_groups += 1

        group_record = {
            "listwise_group_id": f"lw_{sha16(key)}",
            "group_key": key,
            "root_id": root_key(rows[0]) if rows else "",
            "state_hash": sha16(evidence_state_text(rows[0])) if rows else "",
            "rows": len(rows),
            "target_roles": dict(sorted(role_counter.items())),
            "row_ids": [row_id(row) for row in rows],
            "trainable_listwise_group": trainable,
            "singleton_group": singleton,
            "contradictory_targets": contradictory,
            "protected_row_overlaps": row_overlap,
            "protected_root_overlaps": root_overlap,
        }
        group_records.append(group_record)
        for row in rows:
            payload = dict(row)
            source = dict(payload.get("standalone_projection_source") or {})
            source["listwise_group_id"] = group_record["listwise_group_id"]
            source["listwise_state_hash"] = group_record["state_hash"]
            source["listwise_target_role"] = normalized_role(target_value(row))
            source["listwise_trainable_group"] = trainable
            payload["standalone_projection_source"] = source
            payload["listwise_group_id"] = group_record["listwise_group_id"]
            payload["listwise_state_hash"] = group_record["state_hash"]
            payload["listwise_target_role"] = normalized_role(target_value(row))
            payload["listwise_trainable_group"] = trainable
            if trainable:
                grouped_rows.append(payload)
            else:
                reasons = []
                if singleton:
                    reasons.append("singleton_group_no_cross_row_signal")
                if contradictory:
                    reasons.append("contradictory_targets_same_visible_state")
                if row_overlap:
                    reasons.append("protected_row_overlap")
                if root_overlap:
                    reasons.append("protected_root_overlap")
                if not reasons:
                    reasons.append("not_trainable")
                for reason in reasons:
                    quarantine_reasons[reason] += 1
                q = dict(payload)
                q["listwise_quarantine_reasons"] = reasons
                quarantine_rows.append(q)

    write_jsonl(GROUPS, group_records)
    write_jsonl(GROUPED_ROWS, grouped_rows)
    write_jsonl(QUARANTINE, quarantine_rows)

    passed = (
        bool(group_records)
        and not any(record["protected_row_overlaps"] or record["protected_root_overlaps"] for record in group_records)
        and trainable_groups > 0
        and not contradictory_groups
    )
    # Contradictory groups are expected for the current Stage11481 package; keep
    # the stage successful as an audit, but block training until the source rows
    # are recompiled with non-contradictory group identities.
    decision = "listwise_groups_ready_for_training" if passed else "listwise_group_compiler_blocks_training"
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": decision,
        "training_admissible": passed,
        "metrics": {
            "input_rows": len(residual50),
            "listwise_groups": len(group_records),
            "trainable_grouped_rows": len(grouped_rows),
            "quarantined_rows": len(quarantine_rows),
            "trainable_groups": trainable_groups,
            "singleton_groups": singleton_groups,
            "contradictory_groups": contradictory_groups,
            "protected_overlap_groups": protected_overlap_groups,
            "group_size_counts": dict(sorted((str(k), v) for k, v in group_size_counts.items())),
            "target_role_counts": dict(sorted(group_role_counts.items())),
            "quarantine_reasons": dict(sorted(quarantine_reasons.items())),
        },
        "interpretation": [
            "Stage11491 assigns explicit listwise_group_id values from root plus visible-state hash.",
            "The compiler refuses to train groups where the same visible state has contradictory singleton target roles.",
            "The current Residual-50 package still lacks safe multi-row listwise groups; many candidate rows are either singleton or contradictory counterfactual projections.",
        ],
        "blocked_training_reason": (
            "No direct listwise training request should be emitted until Residual-50 is rebuilt with explicit non-contradictory candidate_set_id/state_id groups."
            if not passed
            else None
        ),
        "next_stage_contract": {
            "recommended_stage": "stage11492_residual50_candidate_set_recompiler",
            "goal": "recompile Residual-50 into explicit candidate-set groups where each visible state has one gold role and hard negatives are candidate options, not contradictory sibling labels",
            "success_criteria": [
                "candidate_set_id present on every row",
                "each candidate_set_id has exactly one singleton gold target or explicit set-valued target",
                "each group includes candidate_change_surface, verifier_and_test_constraint, symptom_or_call_path_analogue, and insufficient/background where available",
                "no protected row/root overlap",
                "at least 30 trainable groups across Python, C/C++, and Rust",
            ],
        },
        "source_artifacts": {
            "residual50_rows": rel(RESIDUAL50),
            "stage11490_readiness": rel(READINESS),
            "filtered_validation": rel(FILTERED_VALIDATION),
            "filtered_strict": rel(FILTERED_STRICT),
            "residual_bank": rel(RESIDUAL_BANK),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "groups": rel(GROUPS),
            "grouped_rows": rel(GROUPED_ROWS),
            "quarantine_rows": rel(QUARANTINE),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "training_admissible": passed, "metrics": summary["metrics"], "next_stage_contract": summary["next_stage_contract"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
