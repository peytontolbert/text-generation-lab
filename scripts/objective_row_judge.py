#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


INTERNAL_TOKEN_RE = re.compile(r"<(?:MT|COPY|SEM|CTRL|PLAN|MNSB|PYPLAN)[^>]*>")

DEFAULT_AUTHORITY = {
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


ROUTE_TO_LOSSES = {
    "KEEP_STRUCTURED": {
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
    },
    "KEEP_BOUNDED_DECODER": {"decoder_ce"},
    "HOLD_LONG_OUTPUT": set(),
    "USE_FOR_DENOISE_REPAIR": {"denoise_ce"},
    "USE_AS_NEGATIVE": {"action_sequence_ce", "file_plan_ce"},
    "NEEDS_RETRIEVAL": {"action_sequence_ce"},
    "QUARANTINE_LABEL_CONFLICT": set(),
    "DROP_DUPLICATE": set(),
    "NEEDS_HUMAN_REVIEW": set(),
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
    "decoder_ce",
    "denoise_ce",
    "runtime_reward",
]


def text_blob(row: dict[str, Any], keys: list[str]) -> str:
    values: list[str] = []
    for key in keys:
        value = row.get(key)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, (list, dict)):
            values.append(json.dumps(value, sort_keys=True))
    return "\n".join(values)


def token_len(text: str) -> int:
    return len(text.split())


def judge_row(row: dict[str, Any], *, decoder_token_cap: int = 256) -> dict[str, Any]:
    encoder_text = text_blob(row, ["encoder", "input", "prompt", "corrupted_state", "model_input", "visible_context"])
    target_text = text_blob(row, ["decoder", "target", "clean_state", "output", "label"])
    objective = str(row.get("objective_family") or row.get("objective") or "")
    row_id = str(row.get("row_id") or row.get("id") or "")
    reasons: list[str] = []

    target_tokens = token_len(target_text)
    encoder_has_internal = bool(INTERNAL_TOKEN_RE.search(encoder_text))
    target_has_internal = bool(INTERNAL_TOKEN_RE.search(target_text))
    target_in_encoder = bool(target_text and len(target_text) > 16 and target_text in encoder_text)
    long_blob = target_tokens > decoder_token_cap
    html_doc_fragment = "<html" in target_text.lower() or "<body" in target_text.lower() or "</div>" in target_text.lower()
    short_or_junk = bool(target_text and target_tokens <= 2)
    missing_evidence = bool(row.get("missing_evidence") or row.get("evidence_state") in {"missing", "none", "insufficient"})
    label_conflict = bool(row.get("label_conflict") or row.get("teacher_verifier_disagreement"))
    duplicate = bool(row.get("duplicate_semantic_key") or row.get("duplicate"))
    decode_allowed = bool(row.get("decode_allowed") or row.get("decoder_allowed"))
    budget_ok = bool(row.get("decoder_budget_ok") or row.get("deterministic_budget_ok"))

    if duplicate:
        route = "DROP_DUPLICATE"
        reasons.append("duplicate_semantic_key")
    elif label_conflict:
        route = "QUARANTINE_LABEL_CONFLICT"
        reasons.append("label_conflict")
    elif target_in_encoder:
        route = "QUARANTINE_LABEL_CONFLICT"
        reasons.append("raw_text_leak_in_structured_objective")
    elif missing_evidence:
        route = "NEEDS_RETRIEVAL"
        reasons.append("missing_evidence")
    elif long_blob or html_doc_fragment:
        route = "HOLD_LONG_OUTPUT"
        reasons.append("target_over_decoder_budget" if long_blob else "html_doc_fragment")
    elif target_has_internal or short_or_junk:
        route = "USE_FOR_DENOISE_REPAIR"
        reasons.append("raw_internal_token_in_decoder" if target_has_internal else "short_or_junk_target")
    elif decode_allowed and budget_ok:
        route = "KEEP_BOUNDED_DECODER"
        reasons.append("bounded_decoder_candidate")
    else:
        route = "KEEP_STRUCTURED"
        reasons.append("structured_candidate")

    if encoder_has_internal:
        reasons.append("internal_token_in_model_input")
        if route not in {"DROP_DUPLICATE", "QUARANTINE_LABEL_CONFLICT"}:
            route = "NEEDS_HUMAN_REVIEW"

    enabled = ROUTE_TO_LOSSES[route]
    loss_mask = {key: key in enabled for key in LOSS_KEYS}
    if not decode_allowed:
        loss_mask["decoder_ce"] = False
    if route != "USE_FOR_DENOISE_REPAIR":
        loss_mask["denoise_ce"] = False
    loss_mask["runtime_reward"] = False

    return {
        "row_id": row_id,
        "objective_family": objective,
        "route": route,
        "judge_reasons": sorted(set(reasons)),
        "features": {
            "target_tokens": target_tokens,
            "encoder_has_internal_token": encoder_has_internal,
            "target_has_internal_token": target_has_internal,
            "target_text_copied_in_encoder": target_in_encoder,
            "missing_evidence": missing_evidence,
            "decode_allowed": decode_allowed,
            "decoder_budget_ok": budget_ok,
        },
        "loss_mask": loss_mask,
        "authority": DEFAULT_AUTHORITY,
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
    parser = argparse.ArgumentParser(description="Judge objective rows and emit route/loss-mask cards.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--card", type=Path, required=True)
    parser.add_argument("--decoder-token-cap", type=int, default=256)
    args = parser.parse_args()

    rows = read_jsonl(args.manifest)
    judged = [judge_row(row, decoder_token_cap=args.decoder_token_cap) for row in rows]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for row in judged:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    route_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    loss_counts = {key: 0 for key in LOSS_KEYS}
    for row in judged:
        route_counts[row["route"]] = route_counts.get(row["route"], 0) + 1
        for reason in row["judge_reasons"]:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        for key, value in row["loss_mask"].items():
            loss_counts[key] += int(value)
    card = {
        "rows": len(judged),
        "route_counts": dict(sorted(route_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "loss_counts": loss_counts,
        "authority": DEFAULT_AUTHORITY,
    }
    args.card.parent.mkdir(parents=True, exist_ok=True)
    args.card.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
