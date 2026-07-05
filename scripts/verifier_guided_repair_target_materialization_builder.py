from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from gate_status_contract import gate_status_card
except Exception:  # pragma: no cover - fallback for isolated imports
    def gate_status_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
        complete = sum(int(bool(row.get("gate_status"))) for row in rows)
        return {"rows": len(rows), "complete_gate_status_rows": complete, "all_rows_have_complete_gate_status": complete == len(rows)}

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

ACTION_TEXT = {
    "DIAGNOSE_FAILURE": "classify the verifier failure before proposing another edit",
    "LOCALIZE_FAILURE": "bind the verifier failure to the smallest visible source or test location",
    "REPAIR_API_CALL": "repair the API-call shape using source-backed call and signature evidence",
    "REPAIR_ASSERTION": "repair the assertion or expected-value relation using verifier-visible test evidence",
    "REPAIR_IMPORT": "repair the import or dependency boundary without adding unapproved dependencies",
    "REPAIR_SYNTAX": "repair syntax or parse-level structure before semantic widening",
    "RERUN_VERIFIER": "rerun or request the verifier when the prior result is inconclusive",
    "RETRIEVE_MORE": "retrieve more evidence because the verifier packet is insufficient",
    "ROLLBACK_OR_ABSTAIN": "rollback or abstain because the verifier signal is unsafe or unsupported",
}

INTERNAL_TOKEN_RE = re.compile(r"(<(?:MT|COPY|SEM|CTRL|PLAN|MNSB|PYPLAN)[^>]*>|POLICY_|CONTROL_|INTERNAL_|decoder_control)")
HTML_RE = re.compile(r"<(html|body|script|style|div|span|table|svg|DOCTYPE)\b", re.I)
REPEAT_RE = re.compile(r"\b(\w{3,})\b(?:\s+\1\b){4,}", re.I)


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_id(*parts: str) -> str:
    return stable_hash("\x1f".join(parts))[:16]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def byte_token_len(text: str) -> int:
    return len(text.encode("utf-8"))


def target_text_for(row: dict[str, Any]) -> str:
    clean = row.get("clean_state") or {}
    state = row.get("corrupted_state") or {}
    action = str(clean.get("verifier_repair_action") or "UNKNOWN")
    language = str(state.get("language") or "unknown_language")
    signal = str(state.get("verifier_signal") or "unknown_verifier_signal")
    packet = state.get("verifier_packet") or {}
    visibility = []
    for key in ["log_available", "source_location_visible", "test_name_visible", "patch_summary_visible"]:
        if packet.get(key) is True:
            visibility.append(key)
    visibility_text = ", ".join(visibility) if visibility else "no direct verifier visibility"
    action_text = ACTION_TEXT.get(action, "hold the repair until verifier evidence is clarified")
    return (
        f"For {language}, {action_text}. "
        f"Verifier signal: {signal}. "
        f"Visible verifier evidence: {visibility_text}. "
        "Keep the repair bounded, source-backed, and runtime-closed."
    )


def target_quality(text: str, *, max_tokens: int) -> dict[str, Any]:
    token_len = byte_token_len(text)
    return {
        "decoder_token_len": token_len,
        "decoder_char_len": len(text),
        "decoder_budget_ok": token_len <= max_tokens,
        "empty_target": not bool(text.strip()),
        "internal_token_present": bool(INTERNAL_TOKEN_RE.search(text)),
        "html_doc_fragment": bool(HTML_RE.search(text)),
        "degenerate_repetition": bool(REPEAT_RE.search(text)),
    }


def _complete_gate_status(row: dict[str, Any]) -> bool:
    gate = row.get("gate_status") or {}
    required = [
        "source_inventory_lineage",
        "source_provenance",
        "contamination_leakage_detector",
        "golden_locked_eval_suite",
        "drift_canary_regression_monitor",
        "cluster_slice_near_duplicate_detector",
        "dataset_junk_ood_ranker_v1",
        "schema_drift_detector",
    ]
    return all(key in gate for key in required)


def build_materialization_controls(rows: list[dict[str, Any]], *, max_decoder_tokens: int = 768) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifest: list[dict[str, Any]] = []
    target_store: list[dict[str, Any]] = []
    for row in rows:
        clean = row.get("clean_state") or {}
        state = row.get("corrupted_state") or {}
        action = str(clean.get("verifier_repair_action") or "UNKNOWN")
        sid = stable_id(str(row.get("row_id")), str(row.get("split")), action, str(state.get("verifier_signal")))
        target_ref = f"target_ref_stage8872_{sid}"
        blockers: list[str] = []
        if action not in ACTION_TEXT:
            blockers.append("unknown_verifier_repair_action")
        if not _complete_gate_status(row):
            blockers.append("incomplete_gate_status")
        if any(bool(v) for v in (row.get("authority") or {}).values()):
            blockers.append("source_authority_open")
        if any(bool(v) for v in (row.get("loss_mask") or {}).values()):
            blockers.append("source_loss_mask_open")
        if (state.get("budget") or {}).get("runtime_reward_allowed") is True:
            blockers.append("runtime_reward_allowed")
        text = target_text_for(row)
        quality = target_quality(text, max_tokens=max_decoder_tokens)
        if quality["empty_target"]:
            blockers.append("empty_target")
        if not quality["decoder_budget_ok"]:
            blockers.append("target_over_decoder_budget")
        if quality["internal_token_present"]:
            blockers.append("internal_token_present")
        if quality["html_doc_fragment"]:
            blockers.append("html_doc_fragment")
        if quality["degenerate_repetition"]:
            blockers.append("degenerate_repetition")
        materialized = not blockers
        target_hash = stable_hash(text)
        if materialized:
            target_store.append({
                "target_ref": target_ref,
                "source_row_id_hash": stable_hash(str(row.get("row_id")))[:16],
                "split": row.get("split"),
                "language": state.get("language"),
                "verifier_signal": state.get("verifier_signal"),
                "verifier_repair_action": action,
                "decoder_text": text,
                "decoder_text_sha256": target_hash,
                "decoder_token_len": quality["decoder_token_len"],
                "decoder_char_len": quality["decoder_char_len"],
                "quality": quality,
                "source_backed": True,
                "target_store_only_not_model_input": True,
                "authority": dict(AUTHORITY_CLOSED),
            })
            blockers.extend([
                "denoise_ce_loss_not_authorized",
                "runtime_verifier_execution_not_authorized",
                "explicit_execution_authorization_required",
            ])
        manifest.append({
            "row_id": f"stage8872_verifier_guided_repair_target_{sid}",
            "semantic_key": f"{row.get('split', 'unknown')}:verifier_guided_repair_target_materialization:{sid}",
            "source_stage": "stage8872_from_stage8788_source_backed_verifier_repair_candidate_manifest",
            "source_row_ref": {
                "source_verifier_repair_row_hash": stable_hash(str(row.get("row_id")))[:16],
                "source_stage": row.get("source_stage"),
                "source_row_id_in_model_input": False,
            },
            "objective_family": "verifier_guided_repair_target_materialization",
            "split": row.get("split"),
            "route": "VERIFIER_REPAIR_TARGET_MATERIALIZED_DENOISE_STILL_CLOSED" if materialized else "VERIFIER_REPAIR_TARGET_MATERIALIZATION_BLOCKED",
            "corrupted_state": {
                "task_family": "verifier_guided_repair_target_materialization",
                "language": state.get("language"),
                "file_extension": state.get("file_extension"),
                "verifier_signal": state.get("verifier_signal"),
                "verifier_packet": state.get("verifier_packet", {}),
                "budget": state.get("budget", {}),
                "patch_context": state.get("patch_context"),
            },
            "clean_state": {
                "verifier_repair_action": action,
                "action_sequence": clean.get("action_sequence"),
                "file_plan": clean.get("file_plan"),
                "repair_target_text_materialized": materialized,
                "repair_target_ref": target_ref if materialized else None,
                "repair_target_text_sha256": target_hash if materialized else None,
                "repair_target_token_len": quality["decoder_token_len"] if materialized else None,
                "repair_target_char_len": quality["decoder_char_len"] if materialized else None,
                "denoise_ce_eligible_now": False,
                "runtime_verifier_execution_eligible_now": False,
                "required_before_denoise_ce": [
                    "target_store_audit_passed",
                    "target_text_not_visible_in_model_input",
                    "repair_denoise_loss_mask_runtime_assertions",
                    "tiny_pre_execution_audit",
                    "explicit_execution_authorization",
                ],
            },
            "materialization_status": {
                "verifier_guided_target_text_materialized": materialized,
                "target_store_ref_present": materialized,
                "target_store_only_not_model_input": True,
                "target_text_visible_in_manifest": False,
                "hard_blockers": blockers,
            },
            "gate_status": row.get("gate_status") or {},
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK_CLOSED),
            "anti_cheat": {
                "raw_source_included": False,
                "raw_log_body_in_model_input": False,
                "raw_patch_body_in_model_input": False,
                "raw_decoder_text_included": False,
                "target_text_in_encoder": False,
                "target_text_in_model_input": False,
                "target_text_in_manifest": False,
                "target_label_in_id": False,
                "source_row_id_in_model_input": False,
                "target_store_is_separate_artifact": True,
                "requires_pre_execution_audit_before_training": True,
            },
        })
    return manifest, target_store


def build_card(manifest: list[dict[str, Any]], target_store: list[dict[str, Any]]) -> dict[str, Any]:
    manifest_text = "\n".join(json.dumps(row, sort_keys=True) for row in manifest)
    materialized = [row for row in manifest if (row.get("materialization_status") or {}).get("verifier_guided_target_text_materialized") is True]
    target_text_copied = sum(int(str(t.get("decoder_text") or "") in manifest_text) for t in target_store)
    hash_splits: dict[str, set[str]] = defaultdict(set)
    for row in target_store:
        hash_splits[str(row.get("decoder_text_sha256") or "")].add(str(row.get("split")))
    return {
        "rows": len(manifest),
        "materialized_rows": len(materialized),
        "blocked_rows": len(manifest) - len(materialized),
        "target_store_rows": len(target_store),
        "route_counts": dict(sorted(Counter(row.get("route") for row in manifest).items())),
        "action_counts": dict(sorted(Counter((row.get("clean_state") or {}).get("verifier_repair_action") for row in manifest).items())),
        "split_counts": dict(sorted(Counter(row.get("split") for row in manifest).items())),
        "gate_status": gate_status_card(manifest),
        "authority_rows": sum(int(any((row.get("authority") or {}).values())) for row in manifest),
        "target_store_authority_rows": sum(int(any((row.get("authority") or {}).values())) for row in target_store),
        "training_loss_rows": sum(int(any((row.get("loss_mask") or {}).values())) for row in manifest),
        "denoise_ce_eligible_now_rows": sum(int((row.get("clean_state") or {}).get("denoise_ce_eligible_now") is True) for row in manifest),
        "runtime_verifier_execution_eligible_now_rows": sum(int((row.get("clean_state") or {}).get("runtime_verifier_execution_eligible_now") is True) for row in manifest),
        "target_text_visible_in_manifest_rows": sum(int((row.get("materialization_status") or {}).get("target_text_visible_in_manifest") is True) for row in manifest),
        "target_text_copied_to_manifest_rows": target_text_copied,
        "target_ref_unique_rows": len({row.get("target_ref") for row in target_store}),
        "target_hash_unique_rows": len(hash_splits),
        "cross_split_duplicate_target_hashes": sum(1 for splits in hash_splits.values() if len(splits) > 1),
        "over_cap_target_store_rows": sum(int(not (row.get("quality") or {}).get("decoder_budget_ok", False)) for row in target_store),
        "empty_target_store_rows": sum(int((row.get("quality") or {}).get("empty_target") is True) for row in target_store),
        "internal_token_target_store_rows": sum(int((row.get("quality") or {}).get("internal_token_present") is True) for row in target_store),
        "html_target_store_rows": sum(int((row.get("quality") or {}).get("html_doc_fragment") is True) for row in target_store),
        "repetition_target_store_rows": sum(int((row.get("quality") or {}).get("degenerate_repetition") is True) for row in target_store),
    }
