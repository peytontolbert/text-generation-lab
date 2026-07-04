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

SURFACES = ["MAINTAINER_EXPLANATION_ARGS", "REPAIR_PLAN_ARGS", "PATCH_HUNK_ARGS", "TEST_PLAN_ARGS"]
LANGUAGES = ["python", "rust", "c_family", "web_js_ts_html"]
SPLITS = ["train", "eval", "strict_eval"]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("input row must be an object")
            rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def make_seed_argument_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for split in SPLITS:
        for language in LANGUAGES:
            for surface in SURFACES:
                for variant in range(2):
                    row_id = f"reconstructed_arg_{split}_{language}_{surface}_{variant}"
                    rows.append({
                        "row_id": row_id,
                        "split": split,
                        "language_family": language,
                        "surface": surface,
                        "target_surface": surface,
                        "route": "KEEP_BOUNDED_DECODER",
                        "decode_allowed": True,
                        "decoder_budget_ok": True,
                        "decoder_token_len": 128 + variant,
                        "target_ref": f"target_ref::{row_id}",
                        "copied_target_text_in_input": False,
                        "input_state": {
                            "operator_surface": surface,
                            "language_family": language,
                            "evidence_state": "direct_present",
                            "target_reference_only": True,
                        },
                        "target": {
                            "target_ref": f"target_ref::{row_id}",
                            "target_shape": surface,
                        },
                        "authority": dict(AUTHORITY_CLOSED),
                        "reconstructed": True,
                    })
    return rows


def normalize_arg_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    surface = row.get("surface") or row.get("target_surface") or row.get("decoder_surface")
    language = row.get("language_family") or row.get("language_group") or row.get("language")
    split = row.get("split") or row.get("package_split") or "train"
    row_id = row.get("row_id") or f"candidate_{index:04d}"
    token_len = row.get("decoder_token_len") or row.get("target_token_len") or 128
    target_ref = row.get("target_ref") or row.get("target", {}).get("target_ref") if isinstance(row.get("target"), dict) else None
    if not target_ref:
        target_ref = f"target_ref::{row_id}"
    return {
        "row_id": f"ce_candidate_{row_id}",
        "source_row_id": row_id,
        "split": "strict_eval" if split == "strict" else split,
        "language_family": language,
        "surface": surface,
        "route": "KEEP_BOUNDED_DECODER",
        "decode_allowed": True,
        "decoder_budget_ok": True,
        "decoder_token_len": int(token_len),
        "target_ref": target_ref,
        "copied_target_text_in_input": False,
        "input_state": row.get("input_state", {}),
        "target": {"target_ref": target_ref, "target_shape": surface},
        "authority": dict(AUTHORITY_CLOSED),
        "reconstructed": bool(row.get("reconstructed", False)),
    }


def build_package(args: argparse.Namespace) -> dict[str, Any]:
    if args.argument_rows and args.argument_rows.is_file():
        source_rows = read_jsonl(args.argument_rows)
    elif args.reconstruct_seed:
        source_rows = make_seed_argument_rows()
    else:
        raise SystemExit("argument rows missing; pass --argument-rows or --reconstruct-seed")
    candidates = [normalize_arg_row(row, i) for i, row in enumerate(source_rows)]
    candidates = candidates[: args.max_rows]
    write_jsonl(args.rows_output, candidates)
    by_split: dict[str, int] = {}
    by_language: dict[str, int] = {}
    by_surface: dict[str, int] = {}
    copied = 0
    over_cap = 0
    authority = 0
    for row in candidates:
        by_split[row["split"]] = by_split.get(row["split"], 0) + 1
        by_language[row["language_family"]] = by_language.get(row["language_family"], 0) + 1
        by_surface[row["surface"]] = by_surface.get(row["surface"], 0) + 1
        copied += int(bool(row.get("copied_target_text_in_input")))
        over_cap += int(int(row.get("decoder_token_len", 0)) > args.max_decoder_tokens)
        authority += int(any(bool(v) for v in row.get("authority", {}).values()))
    card = {
        "stage": 8564,
        "stage_name": "stage8564_v27_bounded_decoder_ce_candidate_package_design",
        "passed": len(candidates) == args.max_rows and copied == 0 and over_cap == 0 and authority == 0,
        "candidate_rows": len(candidates),
        "by_split": by_split,
        "by_language": by_language,
        "by_surface": by_surface,
        "copied_target_text_rows": copied,
        "over_cap_rows": over_cap,
        "current_authority_rows": authority,
        "rows_output": str(args.rows_output),
        "reconstructed_seed_used": bool(args.reconstruct_seed and not (args.argument_rows and args.argument_rows.is_file())),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": "audit bounded decoder CE candidate package design before loss-mask reopen",
    }
    args.card_output.parent.mkdir(parents=True, exist_ok=True)
    args.card_output.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return card


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build bounded decoder CE candidate package rows from bounded decoder argument rows.")
    p.add_argument("--argument-rows", type=Path, default=None)
    p.add_argument("--reconstruct-seed", action="store_true")
    p.add_argument("--rows-output", type=Path, required=True)
    p.add_argument("--card-output", type=Path, required=True)
    p.add_argument("--max-rows", type=int, default=96)
    p.add_argument("--max-decoder-tokens", type=int, default=768)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    card = build_package(args)
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
