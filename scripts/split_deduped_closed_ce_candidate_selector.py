from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

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
    "surface_role_ce": False,
    "repair_surface_ce": False,
    "build_mode_ce": False,
    "allowed_import_policy_ce": False,
    "blocked_import_policy_ce": False,
    "repo_dependency_policy_ce": False,
    "action_sequence_ce": False,
    "file_plan_ce": False,
    "symbol_binding_ce": False,
    "edit_localization_ce": False,
    "patch_operator_ce": False,
    "verifier_repair_ce": False,
    "bounded_decoder_argument_ce": False,
    "bounded_decoder_ce_gate_ce": False,
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
}

SPLIT_PRIORITY = {"train": 0, "eval": 1, "strict": 2, "strict_eval": 2}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def select_rows(manifest: list[dict[str, Any]], target_store: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target_by_ref = {row.get("target_ref"): row for row in target_store}
    materialized = [row for row in manifest if (row.get("materialization_status") or {}).get("source_backed_target_text_materialized") is True]
    hash_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in materialized:
        h = (row.get("clean_state") or {}).get("decoder_target_text_sha256")
        hash_groups[str(h)].append(row)
    selected_refs: set[str] = set()
    for rows in hash_groups.values():
        rows.sort(key=lambda row: (SPLIT_PRIORITY.get(str(row.get("split")), 99), str(row.get("row_id"))))
        ref = (rows[0].get("clean_state") or {}).get("decoder_target_ref")
        if ref:
            selected_refs.add(str(ref))
    out: list[dict[str, Any]] = []
    for row in manifest:
        clean = row.get("clean_state") or {}
        ref = clean.get("decoder_target_ref")
        target = target_by_ref.get(ref)
        materialized_ok = (row.get("materialization_status") or {}).get("source_backed_target_text_materialized") is True
        selected = bool(materialized_ok and ref in selected_refs)
        if selected:
            route = "CLOSED_CE_CANDIDATE_SPLIT_DEDUP_SELECTED"
            blockers = ["decoder_ce_loss_not_authorized", "tiny_pre_execution_audit_required", "explicit_execution_authorization_required"]
        elif materialized_ok:
            route = "CE_BLOCK_SPLIT_DUPLICATE_TARGET_HASH"
            blockers = ["split_duplicate_target_hash"]
        else:
            route = "CE_BLOCK_NOT_MATERIALIZED_OR_NONDECODE_ROUTE"
            blockers = list((row.get("materialization_status") or {}).get("hard_blockers") or ["not_materialized"])
        out.append({
            "row_id": str(row.get("row_id", "")).replace("stage8806_target_materialization", "stage8810_split_dedup_ce_candidate"),
            "semantic_key": str(row.get("semantic_key", "")).replace("source_backed_target_materialization", "split_deduped_closed_ce_candidate"),
            "source_stage": "stage8810_from_stage8806_target_materialization",
            "source_row_ref": row.get("source_row_ref", {}),
            "objective_family": "split_deduped_closed_bounded_decoder_ce_candidate_selection",
            "split": row.get("split"),
            "route": route,
            "corrupted_state": row.get("corrupted_state", {}),
            "clean_state": {
                "bounded_argument_type": clean.get("bounded_argument_type"),
                "decoder_target_ref": ref if selected else None,
                "decoder_target_text_sha256": clean.get("decoder_target_text_sha256") if selected else None,
                "decoder_target_token_len": clean.get("decoder_target_token_len") if selected else None,
                "decoder_ce_candidate_after_dedup": selected,
                "decoder_ce_eligible_now": False,
                "required_before_decoder_ce": [
                    "loss_mask_runtime_assertions",
                    "tiny_pre_execution_audit",
                    "explicit_execution_authorization",
                ],
            },
            "selection_status": {
                "target_materialized": materialized_ok,
                "selected_by_split_dedup": selected,
                "target_store_ref_present": bool(ref and target),
                "target_hash": clean.get("decoder_target_text_sha256") if materialized_ok else None,
                "hard_blockers": blockers,
            },
            "gate_status": row.get("gate_status", {}),
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK_CLOSED),
            "anti_cheat": {
                "target_text_in_manifest": False,
                "target_text_in_model_input": False,
                "target_ref_in_model_input": False,
                "raw_source_included": False,
                "raw_decoder_text_included": False,
                "raw_patch_body_included": False,
                "decoder_ce_loss_authorized": False,
            },
        })
    return out


def build_card(rows: list[dict[str, Any]], target_store: list[dict[str, Any]]) -> dict[str, Any]:
    target_text = "\n".join(str(row.get("decoder_text") or "") for row in target_store)
    manifest_text = "\n".join(json.dumps(row, sort_keys=True) for row in rows)
    selected = [row for row in rows if (row.get("selection_status") or {}).get("selected_by_split_dedup") is True]
    return {
        "rows": len(rows),
        "selected_candidate_rows": len(selected),
        "blocked_rows": len(rows) - len(selected),
        "route_counts": dict(sorted(Counter(row.get("route") for row in rows).items())),
        "split_counts": dict(sorted(Counter(row.get("split") for row in rows).items())),
        "selected_split_counts": dict(sorted(Counter(row.get("split") for row in selected).items())),
        "argument_counts": dict(sorted(Counter((row.get("clean_state") or {}).get("bounded_argument_type") for row in rows).items())),
        "selected_argument_counts": dict(sorted(Counter((row.get("clean_state") or {}).get("bounded_argument_type") for row in selected).items())),
        "training_loss_rows": sum(int(any((row.get("loss_mask") or {}).values())) for row in rows),
        "authority_rows": sum(int(any((row.get("authority") or {}).values())) for row in rows),
        "decoder_ce_eligible_now_rows": sum(int((row.get("clean_state") or {}).get("decoder_ce_eligible_now") is True) for row in rows),
        "selected_target_ref_unique_rows": len({(row.get("clean_state") or {}).get("decoder_target_ref") for row in selected}),
        "selected_target_hash_unique_rows": len({(row.get("clean_state") or {}).get("decoder_target_text_sha256") for row in selected}),
        "target_text_copied_to_manifest_rows": sum(int(bool(text) and text in manifest_text) for text in target_text.split("\n") if text),
    }
