from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from loss_mask_card import normalize_loss_mask, read_jsonl, validate_loss_mask_row
from stage_summary_schema import AUTHORITY_KEYS


def _split(row: dict[str, Any]) -> str:
    value = str(row.get("split") or row.get("package_split") or "train")
    return "strict_eval" if value == "strict" else value


def _token_len(row: dict[str, Any]) -> int | None:
    for key in ("decoder_token_len", "target_token_len", "target_tokens", "decoder_tokens"):
        value = row.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _bool(row: dict[str, Any], key: str) -> bool:
    value = row.get(key, False)
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes"}
    return bool(value)


def audit_rows(rows: list[dict[str, Any]], *, max_train_rows: int, max_eval_rows: int, max_strict_rows: int, max_decoder_tokens: int) -> dict[str, Any]:
    errors: list[str] = []
    split_counts = {"train": 0, "eval": 0, "strict_eval": 0, "other": 0}
    unsafe_loss_rows: list[dict[str, Any]] = []
    authority_rows: list[str] = []
    over_cap_rows: list[str] = []
    copied_target_rows: list[str] = []
    for index, row in enumerate(rows):
        row_id = str(row.get("row_id") or f"row_{index}")
        split = _split(row)
        split_counts[split if split in split_counts else "other"] += 1
        mask = normalize_loss_mask(row)
        enabled = [key for key, value in mask.items() if value]
        if enabled != ["decoder_ce"]:
            unsafe_loss_rows.append({"row_id": row_id, "enabled_losses": enabled})
        mask_errors = validate_loss_mask_row(row, allow_decoder_ce=True, allow_denoise=False, allow_runtime=False)
        if mask_errors:
            unsafe_loss_rows.append({"row_id": row_id, "errors": mask_errors})
        authority = row.get("authority") if isinstance(row.get("authority"), dict) else row
        if any(bool(authority.get(key, False)) for key in AUTHORITY_KEYS):
            authority_rows.append(row_id)
        token_len = _token_len(row)
        if token_len is None or token_len > max_decoder_tokens:
            over_cap_rows.append(row_id)
        if _bool(row, "copied_target_text_in_input") or _bool(row, "target_text_copied_to_input"):
            copied_target_rows.append(row_id)

    caps = {"train": max_train_rows, "eval": max_eval_rows, "strict_eval": max_strict_rows}
    for split, cap in caps.items():
        if split_counts[split] > cap:
            errors.append(f"{split} rows {split_counts[split]} exceed cap {cap}")
    if split_counts["other"]:
        errors.append(f"unexpected split rows: {split_counts['other']}")
    if unsafe_loss_rows:
        errors.append(f"unsafe loss rows: {len(unsafe_loss_rows)}")
    if authority_rows:
        errors.append(f"authority rows: {len(authority_rows)}")
    if over_cap_rows:
        errors.append(f"over cap or missing token rows: {len(over_cap_rows)}")
    if copied_target_rows:
        errors.append(f"copied target text rows: {len(copied_target_rows)}")

    return {
        "stage": 8569,
        "stage_name": "stage8569_v27_bounded_decoder_ce_loss_mask_reopen_design_audit",
        "passed": bool(rows) and not errors,
        "rows": len(rows),
        "split_counts": split_counts,
        "caps": caps,
        "max_decoder_tokens": max_decoder_tokens,
        "errors": errors,
        "unsafe_loss_rows": len(unsafe_loss_rows),
        "unsafe_loss_examples": unsafe_loss_rows[:50],
        "authority_rows": len(authority_rows),
        "authority_row_ids": authority_rows[:50],
        "over_cap_rows": len(over_cap_rows),
        "over_cap_row_ids": over_cap_rows[:50],
        "copied_target_text_rows": len(copied_target_rows),
        "copied_target_row_ids": copied_target_rows[:50],
        "gates": {
            "rows_present": bool(rows),
            "caps_respected": all(split_counts[s] <= caps[s] for s in caps) and split_counts["other"] == 0,
            "decoder_ce_only": not unsafe_loss_rows,
            "authority_closed": not authority_rows,
            "target_token_lengths_under_cap": not over_cap_rows,
            "copied_target_text_absent": not copied_target_rows,
        },
        "authority": {key: False for key in AUTHORITY_KEYS},
        "next_best_step": "wire audited loss-mask rows into wrapper/final pre-execution audit; do not execute training",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit bounded decoder CE loss-mask reopen design rows.")
    parser.add_argument("rows", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-train-rows", type=int, default=32)
    parser.add_argument("--max-eval-rows", type=int, default=16)
    parser.add_argument("--max-strict-rows", type=int, default=16)
    parser.add_argument("--max-decoder-tokens", type=int, default=768)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    card = audit_rows(
        read_jsonl(args.rows),
        max_train_rows=args.max_train_rows,
        max_eval_rows=args.max_eval_rows,
        max_strict_rows=args.max_strict_rows,
        max_decoder_tokens=args.max_decoder_tokens,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
