from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("candidate row must be an object")
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


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


def _bool(row: dict[str, Any], key: str, default: bool = False) -> bool:
    value = row.get(key, default)
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes"}
    return bool(value)


def candidate_is_safe(row: dict[str, Any], *, max_decoder_tokens: int) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not row.get("row_id"):
        reasons.append("missing_row_id")
    split = _split(row)
    if split not in {"train", "eval", "strict_eval"}:
        reasons.append("bad_split")
    route = row.get("route") or row.get("risk_bucket") or row.get("dataset_route")
    decode_allowed = _bool(row, "decode_allowed", route == "KEEP_BOUNDED_DECODER")
    budget_ok = _bool(row, "decoder_budget_ok", True)
    if route not in {None, "", "KEEP_BOUNDED_DECODER"} and not decode_allowed:
        reasons.append("not_bounded_decoder_route")
    if not decode_allowed:
        reasons.append("decode_not_allowed")
    if not budget_ok:
        reasons.append("decoder_budget_not_ok")
    token_len = _token_len(row)
    if token_len is None:
        reasons.append("missing_decoder_token_len")
    elif token_len > max_decoder_tokens:
        reasons.append("decoder_token_over_cap")
    if _bool(row, "copied_target_text_in_input") or _bool(row, "target_text_copied_to_input"):
        reasons.append("copied_target_text_in_input")
    authority = row.get("authority") if isinstance(row.get("authority"), dict) else row
    open_auth = [key for key, value in AUTHORITY_CLOSED.items() if bool(authority.get(key, value))]
    if open_auth:
        reasons.append("authority_open")
    return not reasons, reasons


def make_loss_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["split"] = _split(row)
    out["authority"] = dict(AUTHORITY_CLOSED)
    out["loss_mask"] = {
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
        "decoder_ce": True,
        "denoise_ce": False,
        "runtime_reward": False,
    }
    out["loss_mask_source"] = "stage8568_bounded_decoder_ce_loss_mask_reopen_design"
    return out


def build_design(args: argparse.Namespace) -> dict[str, Any]:
    candidates = read_jsonl(args.candidates)
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    caps = {"train": args.max_train_rows, "eval": args.max_eval_rows, "strict_eval": args.max_strict_rows}
    selected_by_split = {key: 0 for key in caps}
    for row in candidates:
        ok, reasons = candidate_is_safe(row, max_decoder_tokens=args.max_decoder_tokens)
        split = _split(row)
        if ok and selected_by_split[split] >= caps[split]:
            ok = False
            reasons = ["split_cap_reached"]
        if ok:
            selected.append(make_loss_row(row))
            selected_by_split[split] += 1
        else:
            rejected.append({"row_id": row.get("row_id", ""), "split": split, "reasons": reasons})

    write_jsonl(args.rows_output, selected)
    card = {
        "stage": 8568,
        "stage_name": "stage8568_v27_bounded_decoder_ce_loss_mask_reopen_design",
        "passed": bool(selected) and not any(r["reasons"] != ["split_cap_reached"] for r in rejected),
        "claim_scope": "non_executing_loss_mask_design_for_tiny_bounded_decoder_ce_probe",
        "candidate_rows": len(candidates),
        "selected_rows": len(selected),
        "rejected_rows": len(rejected),
        "selected_by_split": selected_by_split,
        "caps": caps,
        "max_decoder_tokens": args.max_decoder_tokens,
        "rows_output": str(args.rows_output),
        "rejected_examples": rejected[:100],
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": "audit loss-mask reopen design before wrapper/final pre-execution audit",
    }
    args.card_output.parent.mkdir(parents=True, exist_ok=True)
    args.card_output.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return card


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build bounded decoder CE loss-mask reopen design rows from audited candidates.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--rows-output", type=Path, required=True)
    parser.add_argument("--card-output", type=Path, required=True)
    parser.add_argument("--max-train-rows", type=int, default=32)
    parser.add_argument("--max-eval-rows", type=int, default=16)
    parser.add_argument("--max-strict-rows", type=int, default=16)
    parser.add_argument("--max-decoder-tokens", type=int, default=768)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    card = build_design(args)
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
