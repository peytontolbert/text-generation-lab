from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import json

LOSS_KEYS = (
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
)

FORBIDDEN_BY_DEFAULT = {"decoder_ce", "denoise_ce", "runtime_reward"}


class LossMaskError(ValueError):
    pass


def normalize_loss_mask(row: dict[str, Any]) -> dict[str, bool]:
    mask = row.get("loss_mask") or row.get("losses_enabled") or {}
    if not isinstance(mask, dict):
        raise LossMaskError("loss_mask must be an object")
    return {key: bool(mask.get(key, False)) for key in LOSS_KEYS}


def validate_loss_mask_row(row: dict[str, Any], *, allow_decoder_ce: bool = False, allow_denoise: bool = False, allow_runtime: bool = False) -> list[str]:
    errors: list[str] = []
    if not row.get("row_id"):
        errors.append("row_id missing")
    mask = normalize_loss_mask(row)
    if mask["decoder_ce"] and not allow_decoder_ce:
        errors.append("decoder_ce enabled without authorization")
    if mask["denoise_ce"] and not allow_denoise:
        errors.append("denoise_ce enabled without authorization")
    if mask["runtime_reward"] and not allow_runtime:
        errors.append("runtime_reward enabled without authorization")
    if not any(mask.values()):
        errors.append("no losses enabled")
    return errors


def summarize_rows(rows: list[dict[str, Any]], **kwargs: bool) -> dict[str, Any]:
    counts = {key: 0 for key in LOSS_KEYS}
    failures = []
    for index, row in enumerate(rows):
        mask = normalize_loss_mask(row)
        for key, value in mask.items():
            counts[key] += int(value)
        errors = validate_loss_mask_row(row, **kwargs)
        if errors:
            failures.append({"index": index, "row_id": row.get("row_id", ""), "errors": errors})
    return {"rows": len(rows), "loss_counts": counts, "failure_count": len(failures), "failures": failures[:100]}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise LossMaskError("JSONL row is not object")
            rows.append(value)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or validate a loss-mask card from manifest rows.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--allow-decoder-ce", action="store_true")
    parser.add_argument("--allow-denoise", action="store_true")
    parser.add_argument("--allow-runtime", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    card = summarize_rows(read_jsonl(args.manifest), allow_decoder_ce=args.allow_decoder_ce, allow_denoise=args.allow_denoise, allow_runtime=args.allow_runtime)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    raise SystemExit(1 if card["failure_count"] else 0)


if __name__ == "__main__":
    main()
