#!/usr/bin/env python3
# Build a successor Stage8674 manifest that quarantines the Stage8675 shortcut cell.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12645_stage8675_symbol_binding_shortcut_quarantine_reselect"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE8674_SUMMARY = ROOT / "runs/summaries/stage8674_source_backed_symbol_binding_candidate_manifest.json"
STAGE8675_SUMMARY = ROOT / "runs/summaries/stage8675_source_backed_symbol_binding_candidate_manifest_audit.json"
STAGE12644_SUMMARY = ROOT / "runs/summaries/stage12644_repo_code_ce_manifest_independent_review_only.json"
STAGE8674_MANIFEST = ROOT / "runs/local/artifacts/stage8674_source_backed_symbol_binding_candidate_manifest/source_backed_symbol_binding_candidate_manifest.jsonl"

EXPECTED_HASHES = {
    "stage8674_summary": "33a1ebc56c325220dbae733d64aeee6f172d2a27b926951ca5c231d857bd5a3c",
    "stage8675_summary": "1532af2337aa41d41ccd7c08dfbe53b1305837b28fcc237fb202a4f635304c67",
    "stage12644_summary": "88cbc2130fc5b3bb1b3afc1ab60bd5b47197fb7c74823148e5bddc0a20c019c0",
    "stage8674_manifest_bytes": "266b580c7638a8c5edf0c8fe39176fb061f992a85637a1f9318f5b65da15adca",
}
ACTIONS = [
    "RETRIEVE_MORE",
    "BIND_CALL_TO_SYMBOL",
    "BIND_TEST_TO_SYMBOL",
    "ABSTAIN_UNBOUND",
    "BIND_IMPORT_TO_MODULE",
]
REPAIRED_CAP_PER_ACTION = 16
EXPECTED_REPAIRED_ROWS = REPAIRED_CAP_PER_ACTION * len(ACTIONS)
EXPECTED_QUARANTINED_ROWS = 125 - EXPECTED_REPAIRED_ROWS
EXPECTED_REPAIRED_SPLITS = {"eval": 24, "strict_eval": 24, "train": 32}
EXPECTED_STAGE12644_NEXT = "stage12645_stage8675_symbol_binding_shortcut_quarantine_or_reselect"
EXPECTED_ORIGINAL_SHORTCUT = {
    "feature": "query_kind",
    "value": "test",
    "total": 29,
    "dist": {"BIND_TEST_TO_SYMBOL": 25, "RETRIEVE_MORE": 4},
}
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}
LOSS_MASK = {
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
    "symbol_binding_ce": False,
    "source_backed_symbol_binding_candidate_ce": False,
}
FALSE_FIELDS = (
    "dataset_rows_admitted",
    "new_rows_admitted",
    "training_admission_allowed",
    "training_allowed",
    "training_run_allowed",
    "training_admitted",
    "strict_eval_admitted",
    "sealed_eval_admitted",
    "implementation_ready",
    "stage12595_allowed",
    "replay_trustworthy",
    "level_3_materialized",
    "gpu_allocation_requested",
    "cuda2_training_allowed",
    "vm_runner_execution_allowed",
    "runtime_authorized",
    "model_execution_authorized_next",
    "source_emission_authorized",
    "body_emission_authorized",
    "decoder_ce_training_authorized_next",
    "transition_head_training_authorized_next",
    "promotion_ready",
    "global_shortcut_preflight_passed",
    "stage8675_original_audit_passed",
    "stage8675_original_shortcut_issue_resolved",
    "repo_code_stage_complete",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/",
    "/arxiv/",
    "jsonl",
    "row_id",
    "source_row_id",
    "source_ref",
    "old_source_ref_path",
    "raw_stream",
    "stdout.raw",
    "stderr.raw",
    "repository_root",
    "patch_path",
    "production_path",
)


class Stage12645ShortcutQuarantineError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12645ShortcutQuarantineError("json_object_required:" + path.name)
    return value


def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Stage12645ShortcutQuarantineError(f"jsonl_object_required:{line_number}")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        for row in rows:
            data = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
            stream.write(data + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def no_claim_fields() -> dict[str, Any]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise Stage12645ShortcutQuarantineError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12645ShortcutQuarantineError(f"{label}_public_leak:{needle}")


def leaves(value: Any) -> Iterable[Any]:
    if isinstance(value, dict):
        for item in value.values():
            yield from leaves(item)
    elif isinstance(value, list):
        for item in value:
            yield from leaves(item)
    else:
        yield value


def stable_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def feature_value(row: Mapping[str, Any], feature: str) -> Any:
    graph = row.get("graph_input") or {}
    query = row.get("query") or {}
    if feature == "query_kind":
        return graph.get("query_kind")
    if feature == "source_file_is_test":
        return str((query.get("features") or {}).get("source_file_is_test"))
    for node in graph.get("nodes") or []:
        if node.get("node_type") == "file":
            return str((node.get("features") or {}).get(feature))
    return None


def recompute_control_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    actions: collections.Counter[str] = collections.Counter()
    splits: collections.Counter[str] = collections.Counter()
    visible_target_hits = []
    forbidden = []
    missing = []
    shortcut = []
    for row in rows:
        clean = row.get("clean_state") or {}
        action = clean.get("binding_action")
        actions.update([str(action)])
        splits.update([str(row.get("split"))])
        source_lineage = row.get("source_lineage") or {}
        retrieval_control = row.get("retrieval_control") or {}
        for key in ("graph_nodes_source_id", "graph_nodes_lineage_hash", "graph_spans_source_id", "graph_spans_lineage_hash"):
            if not source_lineage.get(key):
                missing.append({"row_hash": stable_hash(row), "missing": key})
        for key in ("bm25_top5_recall", "dense_top5_recall", "hybrid_rrf_top5_recall"):
            if key not in retrieval_control:
                missing.append({"row_hash": stable_hash(row), "missing": "retrieval_control." + key})
        if retrieval_control.get("bm25_top5_recall", 0) < 0.90:
            missing.append({"row_hash": stable_hash(row), "missing": "bm25_recall_floor"})
        visible = {key: row[key] for key in ("graph_input", "query", "source_lineage", "retrieval_control") if key in row}
        visible_text = stable_text(visible)
        for value in leaves(clean):
            if isinstance(value, str) and len(value) >= 4 and value in visible_text:
                visible_target_hits.append({"row_hash": stable_hash(row), "target_string_hash": hashlib.sha256(value.encode()).hexdigest()})
                break
        for key, value in (row.get("authority") or {}).items():
            if value is True:
                forbidden.append({"row_hash": stable_hash(row), "field": "authority." + key})
        for key in LOSS_MASK:
            if (row.get("loss_mask") or {}).get(key) is True:
                forbidden.append({"row_hash": stable_hash(row), "field": "loss_mask." + key})

    for feature in ("query_kind", "source_file_is_test", "import_count_bucket", "definition_count_bucket", "call_count_bucket", "path_depth_bucket", "is_test"):
        table: dict[Any, collections.Counter[str]] = collections.defaultdict(collections.Counter)
        for row in rows:
            action = (row.get("clean_state") or {}).get("binding_action")
            table[feature_value(row, feature)][action] += 1
        for value, counter in table.items():
            total = sum(counter.values())
            if total >= 10:
                majority = max(counter.values()) / total
                if majority > 0.80:
                    shortcut.append({"feature": feature, "value": value, "majority": majority, "total": total, "dist": dict(counter)})
    failures = []
    if not rows:
        failures.append("no_rows")
    if missing:
        failures.append(f"missing_required_controls:{len(missing)}")
    if visible_target_hits:
        failures.append(f"visible_target_hits:{len(visible_target_hits)}")
    if forbidden:
        failures.append(f"forbidden_authority_or_loss:{len(forbidden)}")
    if len(set(actions.values())) != 1:
        failures.append("actions_not_balanced")
    if shortcut:
        failures.append(f"shortcut_feature_cells:{len(shortcut)}")
    return {
        "rows": len(rows),
        "actions": dict(sorted(actions.items())),
        "splits": dict(sorted(splits.items())),
        "missing_required_controls": len(missing),
        "visible_target_hits": len(visible_target_hits),
        "forbidden_authority_or_loss": len(forbidden),
        "shortcut_feature_cells": len(shortcut),
        "failures": failures,
        "shortcut": shortcut,
    }


def load_inputs() -> dict[str, Any]:
    manifest_bytes = STAGE8674_MANIFEST.read_bytes()
    stage8674 = read_json(STAGE8674_SUMMARY)
    stage8675 = read_json(STAGE8675_SUMMARY)
    stage12644 = read_json(STAGE12644_SUMMARY)
    for label, value in (
        ("stage8674_summary", stage8674),
        ("stage8675_summary", stage8675),
        ("stage12644_summary", stage12644),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise Stage12645ShortcutQuarantineError("source_pin_drift:" + label)
    if sha256_bytes(manifest_bytes) != EXPECTED_HASHES["stage8674_manifest_bytes"]:
        raise Stage12645ShortcutQuarantineError("source_pin_drift:stage8674_manifest_bytes")
    return {
        "stage8674": stage8674,
        "stage8675": stage8675,
        "stage12644": stage12644,
        "rows": read_jsonl_bytes(manifest_bytes),
    }


def validate_inputs(inputs: Mapping[str, Any]) -> None:
    stage8674 = inputs["stage8674"]
    stage8675 = inputs["stage8675"]
    stage12644 = inputs["stage12644"]
    rows = inputs["rows"]
    if stage8674.get("passed") is not True or (stage8674.get("metrics") or {}).get("rows") != 125:
        raise Stage12645ShortcutQuarantineError("stage8674_source_drift")
    if stage8675.get("passed") is not False or (stage8675.get("metrics") or {}).get("shortcut_feature_cells") != 1:
        raise Stage12645ShortcutQuarantineError("stage8675_blocker_drift")
    shortcut = ((stage8675.get("samples") or {}).get("shortcut") or [None])[0]
    if not isinstance(shortcut, dict):
        raise Stage12645ShortcutQuarantineError("stage8675_shortcut_sample_missing")
    for key, expected in EXPECTED_ORIGINAL_SHORTCUT.items():
        if shortcut.get(key) != expected:
            raise Stage12645ShortcutQuarantineError("stage8675_shortcut_sample_drift:" + key)
    if stage12644.get("training_allowed") is not False or stage12644.get("dataset_rows_admitted") is not False:
        raise Stage12645ShortcutQuarantineError("stage12644_training_authority_drift")
    if stage12644.get("next_required_action") != EXPECTED_STAGE12644_NEXT:
        raise Stage12645ShortcutQuarantineError("stage12644_next_action_drift")
    if len(rows) != 125:
        raise Stage12645ShortcutQuarantineError("stage8674_manifest_row_count_drift")
    original_audit = recompute_control_audit(rows)
    if original_audit["shortcut_feature_cells"] != 1 or original_audit["failures"] != ["shortcut_feature_cells:1"]:
        raise Stage12645ShortcutQuarantineError("original_shortcut_recompute_drift")


def select_repaired_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected_ids: set[str] = set()
    selected: list[dict[str, Any]] = []
    for action in ACTIONS:
        bucket = [row for row in rows if (row.get("clean_state") or {}).get("binding_action") == action]
        if len(bucket) < REPAIRED_CAP_PER_ACTION:
            raise Stage12645ShortcutQuarantineError("insufficient_action_bucket:" + action)
        for row in bucket[:REPAIRED_CAP_PER_ACTION]:
            selected.append(row)
            selected_ids.add(str(row.get("row_id")))

    # Deterministically promote heldout rows when the full Stage8675 rule still passes.
    # This preserves more eval/strict_eval coverage while keeping action counts fixed.
    changed = True
    split_rank = {"strict_eval": 0, "eval": 1, "train": 2}
    while changed:
        changed = False
        selected_ids = {str(row.get("row_id")) for row in selected}
        for action in ACTIONS:
            current = [row for row in selected if (row.get("clean_state") or {}).get("binding_action") == action]
            candidates = sorted(
                [
                    row for row in rows
                    if (row.get("clean_state") or {}).get("binding_action") == action
                    and str(row.get("row_id")) not in selected_ids
                    and row.get("split") != "train"
                ],
                key=lambda row: (split_rank.get(str(row.get("split")), 99), str(row.get("row_id"))),
            )
            drops = sorted(
                [row for row in current if row.get("split") == "train"],
                key=lambda row: str(row.get("row_id")),
                reverse=True,
            )
            for candidate in candidates:
                for drop in drops:
                    trial = [row for row in selected if str(row.get("row_id")) != str(drop.get("row_id"))] + [candidate]
                    trial_audit = recompute_control_audit(trial)
                    if trial_audit["shortcut_feature_cells"] == 0 and trial_audit["failures"] == []:
                        selected = trial
                        changed = True
                        break
                if changed:
                    break
            if changed:
                break

    selected_ids = {str(row.get("row_id")) for row in selected}
    quarantined = [row for row in rows if str(row.get("row_id")) not in selected_ids]
    if len(selected) != EXPECTED_REPAIRED_ROWS or len(quarantined) != EXPECTED_QUARANTINED_ROWS:
        raise Stage12645ShortcutQuarantineError("repair_selection_count_drift")
    repaired_audit = recompute_control_audit(selected)
    if repaired_audit["shortcut_feature_cells"] != 0 or repaired_audit["failures"]:
        raise Stage12645ShortcutQuarantineError("repair_selection_still_fails_stage8675_rule")
    if repaired_audit["splits"] != EXPECTED_REPAIRED_SPLITS:
        raise Stage12645ShortcutQuarantineError("repair_selection_split_drift")
    return selected, quarantined


def quarantine_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for row in rows:
        records.append({
            "record_type": "stage12645_private_quarantined_stage8674_row_v1",
            "row_sha256": stable_hash(row),
            "source_stage": row.get("source_stage"),
            "action": (row.get("clean_state") or {}).get("binding_action"),
            "split": row.get("split"),
            "quarantine_reason": "excluded_by_stage12645_balanced_16_per_action_reselect_to_remove_stage8675_query_kind_test_shortcut",
            "training_allowed": False,
            "dataset_rows_admitted": False,
        })
    return records


def build_packet(inputs: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    validate_inputs(inputs)
    source_rows = inputs["rows"]
    repaired_rows, quarantined_rows = select_repaired_rows(source_rows)
    original_audit = recompute_control_audit(source_rows)
    repaired_audit = recompute_control_audit(repaired_rows)
    quarantine = quarantine_records(quarantined_rows)
    repaired_manifest_hash = stable_hash(repaired_rows)
    quarantine_hash = stable_hash(quarantine)
    true_fields = {
        "stage12645_shortcut_quarantine_reselect_performed": True,
        "stage8675_successor_shortcut_issue_quarantined": True,
        "stage8675_successor_manifest_stage8675_rule_passed": True,
    }
    private = {
        "record_type": "stage12645_private_stage8675_shortcut_quarantine_reselect_packet_v1",
        **no_claim_fields(),
        **true_fields,
        "source_hashes": EXPECTED_HASHES,
        "selection_policy": {
            "policy": "preserve_stage8674_order_keep_first_16_rows_per_binding_action_then_promote_heldout_rows_while_stage8675_rule_passes",
            "cap_per_action": REPAIRED_CAP_PER_ACTION,
            "actions": ACTIONS,
            "expected_repaired_splits": EXPECTED_REPAIRED_SPLITS,
            "mutates_stage8674_history": False,
        },
        "original_audit": original_audit,
        "repaired_audit": repaired_audit,
        "repaired_manifest_sha256": repaired_manifest_hash,
        "quarantine_manifest_sha256": quarantine_hash,
        "decision": "STAGE8675_SHORTCUT_QUARANTINED_BY_SUCCESSOR_RESELECT_NO_ADMISSION_OR_TRAINING",
    }
    contract = {
        "record_type": "stage12645_public_stage8675_shortcut_quarantine_reselect_contract_v1",
        **no_claim_fields(),
        **true_fields,
        "original_rows": original_audit["rows"],
        "repaired_rows": repaired_audit["rows"],
        "quarantined_rows": len(quarantine),
        "original_action_counts": original_audit["actions"],
        "repaired_action_counts": repaired_audit["actions"],
        "repaired_split_counts": repaired_audit["splits"],
        "original_shortcut_feature_cells": original_audit["shortcut_feature_cells"],
        "repaired_shortcut_feature_cells": repaired_audit["shortcut_feature_cells"],
        "repaired_failures": repaired_audit["failures"],
        "stage8675_original_audit_passed": False,
        "stage8675_original_shortcut_issue_resolved": False,
        "global_shortcut_preflight_passed": False,
        "repaired_manifest_sha256": repaired_manifest_hash,
        "quarantine_manifest_sha256": quarantine_hash,
        "private_packet_sha256": stable_hash(private),
        "claim_boundary": {
            "original_stage8675": "still_failed_historical_audit_not_mutated",
            "successor_reselect": "passes_same_feature_cell_shortcut_rule",
            "row_admission": "not_performed",
            "training": "not_authorized",
            "independent_review": "required_next",
        },
    }
    summary = {
        "record_type": "stage12645_public_stage8675_shortcut_quarantine_reselect_summary_v1",
        **no_claim_fields(),
        **true_fields,
        "stage": STAGE,
        "decision": "STAGE8675_SHORTCUT_QUARANTINED_BY_SUCCESSOR_RESELECT_NO_ADMISSION_OR_TRAINING",
        "original_rows": original_audit["rows"],
        "repaired_rows": repaired_audit["rows"],
        "quarantined_rows": len(quarantine),
        "original_action_counts": original_audit["actions"],
        "repaired_action_counts": repaired_audit["actions"],
        "repaired_split_counts": repaired_audit["splits"],
        "original_shortcut_feature_cells": original_audit["shortcut_feature_cells"],
        "repaired_shortcut_feature_cells": repaired_audit["shortcut_feature_cells"],
        "repaired_failures": repaired_audit["failures"],
        "stage8675_original_audit_passed": False,
        "stage8675_original_shortcut_issue_resolved": False,
        "global_shortcut_preflight_passed": False,
        "model_ready_training_rows": 0,
        "repo_code_ce_training_rows_admitted": 0,
        "symbol_binding_training_rows_admitted": 0,
        "repaired_manifest_sha256": repaired_manifest_hash,
        "quarantine_manifest_sha256": quarantine_hash,
        "private_packet_sha256": stable_hash(private),
        "next_required_action": "stage12646_independent_stage12645_shortcut_quarantine_reselect_review_only",
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12645_" + label)
        assert_public_sanitized(record, "stage12645_" + label)
    check_false(private, "stage12645_private")
    return summary, contract, private, repaired_rows, quarantine


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, contract, private, repaired_rows, quarantine = build_packet(load_inputs())
    pointer = {
        "record_type": "stage12645_public_stage8675_shortcut_quarantine_reselect_pointer_v1",
        **no_claim_fields(),
        "stage12645_shortcut_quarantine_reselect_performed": True,
        "stage8675_successor_shortcut_issue_quarantined": True,
        "stage8675_successor_manifest_stage8675_rule_passed": True,
        "global_shortcut_preflight_passed": False,
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "repaired_manifest_sha256": stable_hash(repaired_rows),
        "quarantine_manifest_sha256": stable_hash(quarantine),
    }
    check_false(pointer, "stage12645_pointer")
    assert_public_sanitized(pointer, "stage12645_pointer")
    write_jsonl(out / "private/repaired_source_backed_symbol_binding_candidate_manifest.jsonl", repaired_rows)
    write_jsonl(out / "private/quarantined_source_backed_symbol_binding_rows.jsonl", quarantine)
    write_json(out / "private/stage8675_shortcut_quarantine_reselect_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
