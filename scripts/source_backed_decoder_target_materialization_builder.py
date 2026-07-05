from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from gate_status_contract import gate_status_card, passed_gate_status

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

MATERIALIZABLE_GATE = "CE_CANDIDATE_NEEDS_SOURCE_BACKED_TARGET_TEXT"
INTERNAL_TOKEN_RE = re.compile(r"(<(?:MT|COPY|SEM|CTRL|PLAN|MNSB|PYPLAN)[^>]*>|POLICY_|CONTROL_|INTERNAL_|decoder_control)")
HTML_RE = re.compile(r"<(html|body|script|style|div|span|table|svg|DOCTYPE)\b", re.I)
REPEAT_RE = re.compile(r"\b(\w{3,})\b(?:\s+\1\b){4,}", re.I)

ARGUMENT_TEXT = {
    "ARG_NAME": "Use the verified identifier argument selected from the source-backed context.",
    "ARG_LITERAL": "Use the verified bounded literal argument selected from the source-backed context.",
    "ARG_IMPORT": "Use the approved import argument selected by the source-backed policy.",
    "ARG_CALL": "Use the verified call argument selected from localized callsite evidence.",
    "ARG_PATH": "Use the verified bounded path argument selected from localized file evidence.",
}

CONTEXT_TEXT = {
    "add_import_plan": "The argument supports an import or dependency adaptation step.",
    "callsite_plan": "The argument supports a localized callsite update step.",
    "literal_plan": "The argument supports a small literal replacement or insertion step.",
    "path_plan": "The argument supports a bounded path or file-reference step.",
    "name_plan": "The argument supports a symbol, identifier, or name-binding step.",
    "hold_plan": "The argument supports a hold, retrieve, or abstain decision under current gates.",
}


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
    # The recovered tiny decoder path used a byte tokenizer, so byte length is the conservative token proxy.
    return len(text.encode("utf-8"))


def target_text_for(row: dict[str, Any]) -> str:
    clean = row.get("clean_state") or {}
    state = row.get("corrupted_state") or {}
    arg_type = str(clean.get("bounded_argument_type") or "UNKNOWN_ARGUMENT")
    context = str(state.get("context_group") or "unknown_context")
    language = str(state.get("language") or "unknown_language")
    arg_sentence = ARGUMENT_TEXT.get(arg_type, "Use the verified bounded argument selected from source-backed evidence.")
    context_sentence = CONTEXT_TEXT.get(context, "The argument supports a bounded maintainer step under the current source-backed gate.")
    return f"For {language}, {arg_sentence} {context_sentence}"


def target_quality(text: str, *, max_decoder_tokens: int) -> dict[str, Any]:
    token_len = byte_token_len(text)
    return {
        "decoder_token_len": token_len,
        "decoder_char_len": len(text),
        "decoder_budget_ok": token_len <= max_decoder_tokens,
        "empty_target": not bool(text.strip()),
        "internal_token_present": bool(INTERNAL_TOKEN_RE.search(text)),
        "html_doc_fragment": bool(HTML_RE.search(text)),
        "degenerate_repetition": bool(REPEAT_RE.search(text)),
    }


def build_materialization_controls(rows: list[dict[str, Any]], *, max_decoder_tokens: int = 768) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifest: list[dict[str, Any]] = []
    target_store: list[dict[str, Any]] = []
    for row in rows:
        clean = row.get("clean_state") or {}
        state = row.get("corrupted_state") or {}
        arg_type = str(clean.get("bounded_argument_type") or "UNKNOWN_ARGUMENT")
        gate_decision = str(clean.get("ce_gate_decision") or "UNKNOWN_GATE")
        materializable = gate_decision == MATERIALIZABLE_GATE and arg_type in ARGUMENT_TEXT
        sid = stable_id(str(row.get("row_id")), str(row.get("split")), arg_type, str(state.get("context_group")))
        target_ref = f"target_ref_stage8806_{sid}"
        blockers = []
        target_meta: dict[str, Any] = {
            "target_ref": None,
            "target_text_sha256": None,
            "decoder_token_len": None,
            "decoder_char_len": None,
            "materialized_decoder_budget_ok": False,
        }
        if materializable:
            text = target_text_for(row)
            quality = target_quality(text, max_decoder_tokens=max_decoder_tokens)
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
            target_hash = stable_hash(text)
            target_meta = {
                "target_ref": target_ref,
                "target_text_sha256": target_hash,
                "decoder_token_len": quality["decoder_token_len"],
                "decoder_char_len": quality["decoder_char_len"],
                "materialized_decoder_budget_ok": quality["decoder_budget_ok"] and not blockers,
            }
            target_store.append({
                "target_ref": target_ref,
                "source_row_id_hash": stable_hash(str(row.get("row_id")))[:16],
                "split": row.get("split"),
                "language": state.get("language"),
                "context_group": state.get("context_group"),
                "bounded_argument_type": arg_type,
                "decoder_text": text,
                "decoder_text_sha256": target_hash,
                "decoder_token_len": quality["decoder_token_len"],
                "decoder_char_len": quality["decoder_char_len"],
                "quality": quality,
                "source_backed": True,
                "target_store_only_not_model_input": True,
                "authority": dict(AUTHORITY_CLOSED),
            })
        else:
            blockers.append(gate_decision.lower())
        if materializable and not blockers:
            blockers.extend(["decoder_ce_loss_not_authorized", "explicit_execution_authorization_required"])
        out = {
            "row_id": f"stage8806_target_materialization_{sid}",
            "semantic_key": f"{row.get('split', 'unknown')}:source_backed_target_materialization:{sid}",
            "source_stage": "stage8806_from_stage8802_closed_bounded_decoder_ce_gate",
            "source_row_ref": {
                "source_ce_gate_row_hash": stable_hash(str(row.get("row_id")))[:16],
                "source_stage": row.get("source_stage"),
                "source_row_id_in_model_input": False,
            },
            "objective_family": "source_backed_decoder_target_materialization",
            "split": row.get("split"),
            "route": "TARGET_MATERIALIZED_CE_STILL_CLOSED" if materializable and target_meta["materialized_decoder_budget_ok"] else "TARGET_MATERIALIZATION_BLOCKED",
            "corrupted_state": {
                "task_family": "source_backed_decoder_target_materialization",
                "language": state.get("language"),
                "file_extension": state.get("file_extension"),
                "context_group": state.get("context_group"),
                "argument_signal": state.get("argument_signal"),
                "bounded_argument_features": state.get("bounded_argument_features", {}),
                "budget": state.get("budget", {}),
            },
            "clean_state": {
                "bounded_argument_type": arg_type,
                "ce_gate_decision": gate_decision,
                "decoder_target_text_materialized": bool(materializable and target_meta["materialized_decoder_budget_ok"]),
                "decoder_target_ref": target_meta["target_ref"],
                "decoder_target_text_sha256": target_meta["target_text_sha256"],
                "decoder_target_token_len": target_meta["decoder_token_len"],
                "decoder_target_char_len": target_meta["decoder_char_len"],
                "decoder_ce_eligible_now": False,
                "required_before_decoder_ce": [
                    "target_store_audit_passed",
                    "target_text_not_visible_in_encoder",
                    "loss_mask_runtime_assertions",
                    "tiny_pre_execution_audit",
                    "explicit_execution_authorization",
                ],
            },
            "materialization_status": {
                "source_backed_target_text_materialized": bool(materializable and target_meta["materialized_decoder_budget_ok"]),
                "target_store_ref_present": bool(target_meta["target_ref"]),
                "target_store_only_not_model_input": True,
                "target_text_visible_in_manifest": False,
                "hard_blockers": blockers,
            },
            "gate_status": passed_gate_status(),
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK_CLOSED),
            "anti_cheat": {
                "raw_source_included": False,
                "raw_decoder_text_included": False,
                "raw_patch_body_included": False,
                "target_text_in_encoder": False,
                "target_text_in_model_input": False,
                "target_text_in_manifest": False,
                "target_label_in_id": False,
                "source_row_id_in_model_input": False,
                "target_store_is_separate_artifact": True,
                "requires_pre_execution_audit_before_training": True,
            },
        }
        manifest.append(out)
    return manifest, target_store


def build_card(manifest: list[dict[str, Any]], target_store: list[dict[str, Any]], *, max_decoder_tokens: int = 768) -> dict[str, Any]:
    materialized = [row for row in manifest if (row.get("materialization_status") or {}).get("source_backed_target_text_materialized") is True]
    blocked = [row for row in manifest if row not in materialized]
    target_texts = [str(row.get("decoder_text") or "") for row in target_store]
    target_hashes = [str(row.get("decoder_text_sha256") or "") for row in target_store]
    loss_rows = sum(int(any((row.get("loss_mask") or {}).values())) for row in manifest)
    authority_rows = sum(int(any((row.get("authority") or {}).values())) for row in manifest)
    target_store_authority_rows = sum(int(any((row.get("authority") or {}).values())) for row in target_store)
    manifest_text = "\n".join(json.dumps(row, sort_keys=True) for row in manifest)
    return {
        "rows": len(manifest),
        "target_store_rows": len(target_store),
        "materialized_rows": len(materialized),
        "blocked_rows": len(blocked),
        "route_counts": dict(sorted(Counter(row.get("route") for row in manifest).items())),
        "argument_counts": dict(sorted(Counter((row.get("clean_state") or {}).get("bounded_argument_type") for row in manifest).items())),
        "split_counts": dict(sorted(Counter(row.get("split") for row in manifest).items())),
        "gate_status": gate_status_card(manifest),
        "authority_rows": authority_rows,
        "target_store_authority_rows": target_store_authority_rows,
        "training_loss_rows": loss_rows,
        "decoder_ce_eligible_now_rows": sum(int((row.get("clean_state") or {}).get("decoder_ce_eligible_now") is True) for row in manifest),
        "target_text_visible_in_manifest_rows": sum(int((row.get("anti_cheat") or {}).get("target_text_in_manifest") is True) for row in manifest),
        "target_text_copied_to_manifest_rows": sum(int(text and text in manifest_text) for text in target_texts),
        "target_hash_unique_rows": len(set(target_hashes)),
        "target_ref_unique_rows": len({str(row.get("target_ref")) for row in target_store}),
        "over_cap_target_store_rows": sum(int(int(row.get("decoder_token_len") or 0) > max_decoder_tokens) for row in target_store),
        "empty_target_store_rows": sum(int(not str(row.get("decoder_text") or "").strip()) for row in target_store),
        "internal_token_target_store_rows": sum(int(bool(INTERNAL_TOKEN_RE.search(str(row.get("decoder_text") or "")))) for row in target_store),
        "html_target_store_rows": sum(int(bool(HTML_RE.search(str(row.get("decoder_text") or "")))) for row in target_store),
        "repetition_target_store_rows": sum(int(bool(REPEAT_RE.search(str(row.get("decoder_text") or "")))) for row in target_store),
    }
