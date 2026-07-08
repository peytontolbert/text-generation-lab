from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path
from typing import Any

INTERNAL_TOKEN_RE = re.compile(r"(<(?:MT|COPY|SEM|CTRL|PLAN|MNSB|PYPLAN)[^>]*>|POLICY_|CONTROL_|INTERNAL_|decoder_control)")
HTML_RE = re.compile(r"<(html|body|script|style|div|span|table|svg|DOCTYPE)\b", re.I)
REPEAT_RE = re.compile(r"\b(\w{3,})\b(?:\s+\1\b){4,}", re.I)

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

LOSS_KEYS = [
    "surface_role_ce",
    "repair_surface_ce",
    "build_mode_ce",
    "allowed_import_policy_ce",
    "blocked_import_policy_ce",
    "repo_dependency_policy_ce",
    "action_sequence_ce",
    "file_plan_ce",
    "symbol_binding_ce",
    "edit_localization_ce",
    "patch_operator_ce",
    "verifier_repair_ce",
    "suffix_choice_ce",
    "episode_repair_outcome_ce",
    "episode_failure_type_ce",
    "episode_boundary_match_ce",
    "episode_target_prefix_match_ce",
    "episode_step_value_mse",
    "decoder_ce",
    "denoise_ce",
    "runtime_reward",
]

STRUCTURED_LOSSES = {
    "surface_role_ce",
    "repair_surface_ce",
    "build_mode_ce",
    "allowed_import_policy_ce",
    "blocked_import_policy_ce",
    "repo_dependency_policy_ce",
    "action_sequence_ce",
    "file_plan_ce",
    "symbol_binding_ce",
    "edit_localization_ce",
    "patch_operator_ce",
    "verifier_repair_ce",
    "suffix_choice_ce",
    "episode_repair_outcome_ce",
    "episode_failure_type_ce",
    "episode_boundary_match_ce",
    "episode_target_prefix_match_ce",
    "episode_step_value_mse",
}


def _text(row: dict[str, Any], keys: list[str]) -> str:
    parts: list[str] = []
    for key in keys:
        value = row.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, (dict, list)):
            parts.append(json.dumps(value, sort_keys=True))
    return "\n".join(parts)


def _target_text(row: dict[str, Any]) -> str:
    return _text(row, ["decoder_text", "decoder_target", "target_text", "decoder", "target", "clean_state", "output", "label"])


def _explicit_decoder_text(row: dict[str, Any]) -> str:
    return _text(row, ["decoder_text", "decoder_target", "target_text", "decoder", "output", "label"])


def _encoder_text(row: dict[str, Any]) -> str:
    return _text(row, ["encoder_text", "input_text", "encoder", "input", "prompt", "corrupted_state", "model_input", "visible_context"])


def _token_len(row: dict[str, Any], target_text: str) -> int:
    for key in ["decoder_token_len", "target_token_len", "decoder_tokens"]:
        value = row.get(key)
        if isinstance(value, int):
            return value
    if isinstance(row.get("decoder_content_chars"), int):
        return int(row["decoder_content_chars"])
    return len(target_text.split()) if target_text else 0


def _loss_mask(enabled: set[str]) -> dict[str, bool]:
    mask = {key: key in enabled for key in LOSS_KEYS}
    mask["runtime_reward"] = False
    return mask


def rank_row_v1(row: dict[str, Any], *, max_decoder_tokens: int = 768, locked_source_ids: set[str] | None = None) -> dict[str, Any]:
    locked_source_ids = locked_source_ids or set()
    row_id = str(row.get("row_id") or row.get("candidate_id") or row.get("id") or "")
    objective = str(row.get("objective_family") or row.get("objective") or row.get("objective_kind") or "")
    encoder_text = _encoder_text(row)
    target_text = _target_text(row)
    explicit_decoder_text = _explicit_decoder_text(row)
    target_tokens = _token_len(row, target_text)
    authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
    loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
    source_lineage = row.get("source_lineage") if isinstance(row.get("source_lineage"), dict) else {}
    split = str(row.get("split") or "")

    reason_bits: dict[str, bool] = {
        "authority_true": any(value is True for value in authority.values()) or bool(row.get("authority_true")),
        "explicit_training_loss_true": any(loss.get(key) is True for key in ["decoder_ce", "denoise_ce", "runtime_reward"]),
        "target_over_decoder_budget": target_tokens > max_decoder_tokens,
        "long_blob": target_tokens > 10000 or len(target_text) > 40000,
        "html_doc_fragment": bool(HTML_RE.search(target_text)),
        "raw_internal_token_in_decoder": bool(INTERNAL_TOKEN_RE.search(target_text)),
        "internal_token_in_model_input": bool(INTERNAL_TOKEN_RE.search(encoder_text)),
        "target_text_copied_in_encoder": bool(target_text and len(target_text) > 16 and target_text in encoder_text),
        "short_or_junk_target": bool(explicit_decoder_text and (len(explicit_decoder_text.split()) <= 2 or explicit_decoder_text.strip() in {".", "...", "OK", "None"})),
        "degenerate_repetition_target": bool(REPEAT_RE.search(target_text)),
        "missing_evidence": bool(row.get("missing_evidence") or row.get("evidence_state") in {"missing", "none", "insufficient", "evidence_removed"}),
        "missing_evidence_but_decode_allowed": bool(row.get("decode_allowed") is True and row.get("evidence_state") in {"missing", "evidence_removed"}),
        "budget_bad_but_decode_allowed": bool(row.get("decode_allowed") is True and row.get("decoder_budget_ok") is False),
        "duplicate_semantic_key": bool(row.get("duplicate_semantic_key") or row.get("duplicate")),
        "label_conflict": bool(row.get("label_conflict") or row.get("teacher_verifier_disagreement")),
        "locked_eval_source": bool(source_lineage.get("locked_eval_source")) or source_lineage.get("graph_nodes_source_id") in locked_source_ids or source_lineage.get("graph_spans_source_id") in locked_source_ids or split.startswith("locked"),
        "unknown_source_lineage": bool(row.get("source_backed") and not source_lineage),
    }
    active_reasons = sorted(key for key, value in reason_bits.items() if value)

    if reason_bits["authority_true"] or reason_bits["explicit_training_loss_true"] or reason_bits["locked_eval_source"]:
        route = "QUARANTINE_AUTHORITY_OR_LOCKED"
        enabled_losses: set[str] = set()
    elif reason_bits["duplicate_semantic_key"]:
        route = "DROP_DUPLICATE"
        enabled_losses = set()
    elif reason_bits["label_conflict"] or reason_bits["target_text_copied_in_encoder"]:
        route = "QUARANTINE_LABEL_CONFLICT"
        enabled_losses = set()
    elif reason_bits["unknown_source_lineage"]:
        route = "NEEDS_SOURCE_LINEAGE"
        enabled_losses = set()
    elif reason_bits["missing_evidence"] or reason_bits["missing_evidence_but_decode_allowed"]:
        route = "NEEDS_RETRIEVAL"
        enabled_losses = {"action_sequence_ce"}
    elif reason_bits["target_over_decoder_budget"] or reason_bits["long_blob"] or reason_bits["html_doc_fragment"]:
        route = "HOLD_LONG_OUTPUT"
        enabled_losses = set()
    elif reason_bits["raw_internal_token_in_decoder"] or reason_bits["short_or_junk_target"] or reason_bits["degenerate_repetition_target"]:
        route = "USE_FOR_DENOISE_REPAIR"
        enabled_losses = {"denoise_ce"}
    elif row.get("decode_allowed") is True and row.get("decoder_budget_ok") is True:
        route = "KEEP_BOUNDED_DECODER"
        enabled_losses = {"decoder_ce"}
    elif row.get("internal_control_token_negative") or row.get("short_output_negative"):
        route = "USE_AS_NEGATIVE"
        enabled_losses = {"action_sequence_ce", "file_plan_ce"}
    else:
        route = "KEEP_STRUCTURED"
        enabled_losses = set(STRUCTURED_LOSSES)

    if row.get("decode_allowed") is not True:
        enabled_losses.discard("decoder_ce")
    if route != "USE_FOR_DENOISE_REPAIR":
        enabled_losses.discard("denoise_ce")

    junk_score = min(
        1.0,
        0.12 * sum(
            reason_bits[key]
            for key in [
                "target_over_decoder_budget",
                "long_blob",
                "html_doc_fragment",
                "raw_internal_token_in_decoder",
                "short_or_junk_target",
                "degenerate_repetition_target",
                "duplicate_semantic_key",
                "label_conflict",
            ]
        )
        + (0.45 if route.startswith("QUARANTINE") else 0.0),
    )
    ood_score = min(
        1.0,
        0.2 * sum(reason_bits[key] for key in ["unknown_source_lineage", "missing_evidence", "internal_token_in_model_input"])
        + (0.25 if objective == "" else 0.0),
    )
    train_eligible = route in {"KEEP_STRUCTURED", "KEEP_BOUNDED_DECODER", "USE_FOR_DENOISE_REPAIR", "USE_AS_NEGATIVE", "NEEDS_RETRIEVAL"}

    return {
        "row_id": row_id,
        "objective_family": objective,
        "route": route,
        "risk_bucket": route,
        "junk_score": round(junk_score, 4),
        "ood_score": round(ood_score, 4),
        "reason_bits": reason_bits,
        "reasons": active_reasons,
        "features": {
            "target_tokens": target_tokens,
            "target_chars": len(target_text),
            "encoder_chars": len(encoder_text),
            "decode_allowed": row.get("decode_allowed"),
            "decoder_budget_ok": row.get("decoder_budget_ok"),
            "split": split,
        },
        "eligibility": {
            "train_eligible": train_eligible,
            "eval_eligible": not reason_bits["locked_eval_source"] and route not in {"QUARANTINE_AUTHORITY_OR_LOCKED"},
            "holdout_only": route == "HOLD_LONG_OUTPUT" or reason_bits["locked_eval_source"],
            "locked_eval_source": reason_bits["locked_eval_source"],
        },
        "loss_mask": _loss_mask(enabled_losses),
        "authority": AUTHORITY_CLOSED,
    }


def rank_rows_v1(rows: list[dict[str, Any]], *, max_decoder_tokens: int = 768, locked_source_ids: set[str] | None = None) -> dict[str, Any]:
    ranked = [rank_row_v1(row, max_decoder_tokens=max_decoder_tokens, locked_source_ids=locked_source_ids) for row in rows]
    route_counts: collections.Counter[str] = collections.Counter(row["route"] for row in ranked)
    reason_counts: collections.Counter[str] = collections.Counter(reason for row in ranked for reason in row["reasons"])
    loss_counts = {key: sum(int(row["loss_mask"].get(key, False)) for row in ranked) for key in LOSS_KEYS}
    return {
        "rows": len(ranked),
        "route_counts": dict(sorted(route_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "loss_counts": loss_counts,
        "authority": AUTHORITY_CLOSED,
        "ranked_rows": ranked,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError(f"non-object row in {path}")
            rows.append(item)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified deterministic dataset junk/OOD/routing ranker v1.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--max-decoder-tokens", type=int, default=768)
    parser.add_argument("--locked-source-id", action="append", default=[])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    card = rank_rows_v1(read_jsonl(args.manifest), max_decoder_tokens=args.max_decoder_tokens, locked_source_ids=set(args.locked_source_id))
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
