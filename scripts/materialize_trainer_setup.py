#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from curriculum_compiler import LOSS_KEYS, ROUTE_TO_LOSSES
from diagnostic_ticket_contract import AUTHORITY_CLOSED
from loss_mask_card import FORBIDDEN_BY_DEFAULT
from route_card_materializer import materialize_route_card, validate_route_card
from build_stage9128_loss_mask_card_schema_recovery_design import (
    REQUIRED_DISABLED_BY_DEFAULT,
    REQUIRED_TELEMETRY,
)

EXTRA_DISABLED_LOSSES = {
    "source_body_loss",
    "gemma_distill_loss",
    "harness_score_loss",
}
ALL_DISABLED_LOSSES = tuple(sorted(set(REQUIRED_DISABLED_BY_DEFAULT) | EXTRA_DISABLED_LOSSES))
JOIN_KEYS = ("row_id", "semantic_key")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL row in {path} is not an object")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _join_value(row: dict[str, Any]) -> str:
    for key in JOIN_KEYS:
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _index_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _join_value(row)
        if key:
            out[key] = row
    return out


def _objective_family(row: dict[str, Any]) -> str:
    return str(row.get("objective_family") or row.get("task_family") or "intent_to_build_strategy")


def _split(row: dict[str, Any]) -> str:
    return str(row.get("split") or row.get("package_split") or "train")


def _target_text(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    for value in (
        target.get("decoder_text"),
        row.get("decoder_text"),
        target.get("label"),
        row.get("label"),
        target.get("target_ref"),
        row.get("target_ref"),
    ):
        if isinstance(value, str):
            return value
    return ""


def _target_token_len(row: dict[str, Any], target_text: str) -> int:
    for key in ("decoder_token_len", "target_token_len", "target_tokens", "decoder_tokens"):
        value = row.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return len(target_text.encode("utf-8"))


def _length_bucket(token_len: int, decoder_budget_ok: bool) -> str:
    if token_len <= 0:
        return "synthetic_unknown"
    return "bounded" if decoder_budget_ok else "long_holdout"


def materialize_joined_route_cards(
    objective_rows: list[dict[str, Any]],
    judge_rows: list[dict[str, Any]],
    ranker_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    judge_index = _index_rows(judge_rows)
    ranker_index = _index_rows(ranker_rows)
    cards: list[dict[str, Any]] = []
    missing_judge: list[str] = []
    missing_ranker: list[str] = []
    validation_failures: list[str] = []

    for objective_row in objective_rows:
        join_key = _join_value(objective_row)
        if not join_key:
            validation_failures.append("missing_join_key:objective_row")
            continue
        judge_row = judge_index.get(join_key)
        ranker_row = ranker_index.get(join_key)
        if judge_row is None:
            missing_judge.append(join_key)
            continue
        if ranker_row is None:
            missing_ranker.append(join_key)
            continue
        card = materialize_route_card(objective_row, judge_row, ranker_row)
        validation_failures.extend(validate_route_card(card))
        cards.append(card)

    audit = {
        "objective_rows": len(objective_rows),
        "judge_rows": len(judge_rows),
        "ranker_rows": len(ranker_rows),
        "materialized_route_cards": len(cards),
        "missing_judge_rows": len(missing_judge),
        "missing_ranker_rows": len(missing_ranker),
        "missing_judge_examples": missing_judge[:25],
        "missing_ranker_examples": missing_ranker[:25],
        "validation_failures": validation_failures[:100],
        "validation_failure_count": len(validation_failures),
        "route_counts": dict(Counter(str(card.get("route", "")) for card in cards)),
        "split_counts": dict(Counter(_split(card) for card in cards)),
        "authority_closed": all(not any((card.get("authority") or {}).values()) for card in cards),
    }
    return cards, audit


def translate_route_card_to_loss_mask(
    route_card: dict[str, Any],
    objective_row: dict[str, Any],
    *,
    created_by_stage: int = 9200,
) -> dict[str, Any]:
    route = str(route_card.get("route") or "NEEDS_HUMAN_REVIEW")
    enabled = set(ROUTE_TO_LOSSES.get(route, []))
    decoder_budget_ok = bool(route_card.get("decoder_budget_ok") is True)
    decode_allowed = bool(objective_row.get("decode_allowed", route_card.get("decoder_budget_ok")) is True)
    target_text = _target_text(objective_row)
    target_token_len = _target_token_len(objective_row, target_text)
    denoise_route = route == "USE_FOR_DENOISE_REPAIR" or _objective_family(objective_row) == "output_repair_denoise"

    forbidden_loss_reasons: dict[str, str] = {}
    if "decoder_ce" in enabled and not (route == "KEEP_BOUNDED_DECODER" and decoder_budget_ok and decode_allowed and bool(target_text.strip())):
        enabled.discard("decoder_ce")
        forbidden_loss_reasons["decoder_ce"] = "decoder_ce_requires_keep_bounded_decoder_budget_decode_and_target"
    if "denoise_ce" in enabled and not denoise_route:
        enabled.discard("denoise_ce")
        forbidden_loss_reasons["denoise_ce"] = "denoise_ce_requires_denoise_route"
    enabled.discard("runtime_reward")

    loss_mask = {key: key in enabled for key in LOSS_KEYS}
    disabled_losses = set(ALL_DISABLED_LOSSES)
    disabled_losses.update(key for key in LOSS_KEYS if key not in enabled)
    for key in enabled:
        disabled_losses.discard(key)

    return {
        "row_id": str(route_card.get("row_id")),
        "route_card_ref": f"route-card://{route_card.get('row_id')}",
        "enabled_losses": sorted(enabled),
        "disabled_losses": sorted(disabled_losses),
        "loss_weights": {key: 1.0 for key in sorted(enabled)},
        "decoder_ce_allowed": "decoder_ce" in enabled,
        "denoise_ce_allowed": "denoise_ce" in enabled,
        "structured_aux_allowed": bool(enabled - {"decoder_ce", "denoise_ce", "runtime_reward"}),
        "runtime_reward_allowed": False,
        "authority": dict(AUTHORITY_CLOSED),
        "decoder_budget_ok": decoder_budget_ok,
        "decode_allowed": decode_allowed,
        "target_token_len": target_token_len,
        "target_length_bucket": _length_bucket(target_token_len, decoder_budget_ok),
        "loss_authority_evidence": {
            "route": route,
            "objective_family": _objective_family(objective_row),
            "target_present": bool(target_text.strip()),
            "decoder_budget_ok": decoder_budget_ok,
            "decode_allowed": decode_allowed,
            "runtime_closed": True,
        },
        "forbidden_loss_reasons": forbidden_loss_reasons,
        "telemetry_required": list(REQUIRED_TELEMETRY),
        "anti_cheat": {
            "target_not_in_input": bool((route_card.get("anti_cheat") or {}).get("target_not_in_input_checked", True)),
            "authority_closed": True,
            "real_route_card_used": True,
            "real_dataset_row_used": True,
        },
        "created_by_stage": created_by_stage,
        "schema_version": "loss_mask_card_v1_materialized",
        "loss_mask": loss_mask,
    }


def materialize_loss_masks(
    route_cards: list[dict[str, Any]],
    objective_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    objective_index = _index_rows(objective_rows)
    cards: list[dict[str, Any]] = []
    missing_objective: list[str] = []
    forbidden_enabled: list[str] = []

    for route_card in route_cards:
        join_key = _join_value(route_card)
        objective_row = objective_index.get(join_key)
        if objective_row is None:
            missing_objective.append(join_key)
            continue
        card = translate_route_card_to_loss_mask(route_card, objective_row)
        if any((card.get("authority") or {}).values()):
            forbidden_enabled.append(f"{join_key}:authority_open")
        if any(loss in card["enabled_losses"] for loss in FORBIDDEN_BY_DEFAULT - {"decoder_ce", "denoise_ce"}):
            forbidden_enabled.append(f"{join_key}:forbidden_default_enabled")
        cards.append(card)

    enabled_counts = Counter()
    for card in cards:
        enabled_counts.update(card["enabled_losses"])
    audit = {
        "route_cards": len(route_cards),
        "loss_mask_cards": len(cards),
        "missing_objective_rows": len(missing_objective),
        "missing_objective_examples": missing_objective[:25],
        "forbidden_enabled_count": len(forbidden_enabled),
        "forbidden_enabled_examples": forbidden_enabled[:25],
        "enabled_loss_counts": dict(enabled_counts),
        "authority_closed": all(not any((card.get("authority") or {}).values()) for card in cards),
    }
    return cards, audit


def build_trainer_input_rows(
    objective_rows: list[dict[str, Any]],
    route_cards: list[dict[str, Any]],
    loss_mask_cards: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    route_index = _index_rows(route_cards)
    loss_index = _index_rows(loss_mask_cards)
    rows: list[dict[str, Any]] = []
    missing_route: list[str] = []
    missing_loss_mask: list[str] = []

    for objective_row in objective_rows:
        join_key = _join_value(objective_row)
        route_card = route_index.get(join_key)
        loss_mask_card = loss_index.get(join_key)
        if route_card is None:
            missing_route.append(join_key)
            continue
        if loss_mask_card is None:
            missing_loss_mask.append(join_key)
            continue
        row = dict(objective_row)
        row["row_id"] = str(objective_row.get("row_id") or join_key)
        row["route"] = route_card["route"]
        row["risk_bucket"] = route_card["risk_bucket"]
        row["recommended_action"] = route_card["recommended_action"]
        row["objective_family"] = _objective_family(objective_row)
        row["split"] = _split(objective_row)
        row["authority"] = dict(AUTHORITY_CLOSED)
        row["loss_mask"] = dict(loss_mask_card["loss_mask"])
        row["loss_mask_card_ref"] = loss_mask_card["route_card_ref"]
        row["decoder_token_len"] = int(loss_mask_card["target_token_len"])
        row["decode_allowed"] = bool(loss_mask_card["decode_allowed"])
        row["decoder_budget_ok"] = bool(loss_mask_card["decoder_budget_ok"])
        if "target" not in row and _target_text(objective_row):
            row["target"] = {"decoder_text": _target_text(objective_row)}
        rows.append(row)

    split_counts = Counter(_split(row) for row in rows)
    route_counts = Counter(str(row.get("route", "")) for row in rows)
    decoder_rows = sum(int(bool(row.get("loss_mask", {}).get("decoder_ce"))) for row in rows)
    structured_rows = sum(int(any(bool(row.get("loss_mask", {}).get(key)) for key in LOSS_KEYS if key not in {"decoder_ce", "denoise_ce", "runtime_reward"})) for row in rows)
    denoise_rows = sum(int(bool(row.get("loss_mask", {}).get("denoise_ce"))) for row in rows)
    audit = {
        "objective_rows": len(objective_rows),
        "trainer_rows": len(rows),
        "missing_route_cards": len(missing_route),
        "missing_loss_mask_cards": len(missing_loss_mask),
        "missing_route_examples": missing_route[:25],
        "missing_loss_mask_examples": missing_loss_mask[:25],
        "split_counts": dict(split_counts),
        "route_counts": dict(route_counts),
        "decoder_rows": decoder_rows,
        "structured_rows": structured_rows,
        "denoise_rows": denoise_rows,
        "authority_closed": all(not any((row.get("authority") or {}).values()) for row in rows),
    }
    return rows, audit


def build_trainer_dry_run_input(
    trainer_rows: list[dict[str, Any]],
    *,
    manifest_path: Path,
    route_cards_path: Path,
    loss_masks_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    split_counts = dict(Counter(_split(row) for row in trainer_rows))
    decoder_rows = [row for row in trainer_rows if row.get("loss_mask", {}).get("decoder_ce")]
    structured_rows = [
        row for row in trainer_rows
        if any(bool(row.get("loss_mask", {}).get(key)) for key in LOSS_KEYS if key not in {"decoder_ce", "denoise_ce", "runtime_reward"})
    ]
    denoise_rows = [row for row in trainer_rows if row.get("loss_mask", {}).get("denoise_ce")]

    commands: list[dict[str, Any]] = []
    if decoder_rows:
        commands.append(
            {
                "mode": "bounded_decoder_ce_probe",
                "command": [
                    "python",
                    "legacy_src/scripts/train_agentkernel_lite_encdec.py",
                    "--manifest", str(manifest_path),
                    "--mode", "bounded_decoder_ce_probe",
                    "--max-train-rows", str(split_counts.get("train", 0)),
                    "--max-eval-rows", str(split_counts.get("eval", 0)),
                    "--max-strict-rows", str(split_counts.get("strict_eval", 0)),
                    "--max-steps", "8",
                    "--decoder-ce-weight", "1.0",
                    "--structured-aux-weight", "0.0",
                    "--denoise-weight", "0.0",
                    "--require-loss-mask-enforcement-audit",
                    "--no-final-checkpoint-export",
                    "--skip-final-model-save", "1",
                    "--output-dir", str(output_dir / "bounded_decoder_probe"),
                    "--run-id", "materialized_bounded_decoder_probe",
                    "--execution-authorized-for-recovery-probe",
                ],
            }
        )
    if structured_rows:
        commands.append(
            {
                "mode": "structured_policy_probe",
                "command": [
                    "python",
                    "legacy_src/scripts/train_agentkernel_lite_encdec.py",
                    "--manifest", str(manifest_path),
                    "--mode", "structured_policy_probe",
                    "--max-train-rows", str(split_counts.get("train", 0)),
                    "--max-eval-rows", str(split_counts.get("eval", 0)),
                    "--max-strict-rows", str(split_counts.get("strict_eval", 0)),
                    "--max-steps", "8",
                    "--decoder-ce-weight", "0.0",
                    "--structured-aux-weight", "1.0",
                    "--denoise-weight", "0.0",
                    "--require-loss-mask-enforcement-audit",
                    "--no-final-checkpoint-export",
                    "--skip-final-model-save", "1",
                    "--output-dir", str(output_dir / "structured_probe"),
                    "--run-id", "materialized_structured_probe",
                    "--execution-authorized-for-recovery-probe",
                ],
            }
        )
    if denoise_rows:
        commands.append(
            {
                "mode": "denoise_repair_probe",
                "command": [
                    "python",
                    "legacy_src/scripts/train_agentkernel_lite_encdec.py",
                    "--manifest", str(manifest_path),
                    "--mode", "denoise_repair_probe",
                    "--max-train-rows", str(split_counts.get("train", 0)),
                    "--max-eval-rows", str(split_counts.get("eval", 0)),
                    "--max-strict-rows", str(split_counts.get("strict_eval", 0)),
                    "--max-steps", "8",
                    "--decoder-ce-weight", "0.0",
                    "--structured-aux-weight", "0.0",
                    "--denoise-weight", "1.0",
                    "--require-loss-mask-enforcement-audit",
                    "--no-final-checkpoint-export",
                    "--skip-final-model-save", "1",
                    "--output-dir", str(output_dir / "denoise_probe"),
                    "--run-id", "materialized_denoise_probe",
                    "--execution-authorized-for-recovery-probe",
                ],
            }
        )

    return {
        "manifest_path": str(manifest_path),
        "route_cards_path": str(route_cards_path),
        "loss_mask_cards_path": str(loss_masks_path),
        "trainer_rows": len(trainer_rows),
        "split_counts": split_counts,
        "recommended_commands": commands,
        "authority": dict(AUTHORITY_CLOSED),
        "notes": [
            "This setup materializes trainer-ready rows locally.",
            "It does not guarantee competitive quality against larger baselines.",
            "Use tokenizer_json/tokenizer_config flags if you want the recovered BPE path instead of byte fallback.",
        ],
    }


def materialize_training_setup(
    objective_rows: list[dict[str, Any]],
    judge_rows: list[dict[str, Any]],
    ranker_rows: list[dict[str, Any]],
    *,
    output_dir: Path,
) -> dict[str, Any]:
    route_cards, route_audit = materialize_joined_route_cards(objective_rows, judge_rows, ranker_rows)
    loss_masks, loss_audit = materialize_loss_masks(route_cards, objective_rows)
    trainer_rows, trainer_audit = build_trainer_input_rows(objective_rows, route_cards, loss_masks)

    route_cards_path = output_dir / "route_cards.jsonl"
    loss_masks_path = output_dir / "loss_mask_cards.jsonl"
    trainer_rows_path = output_dir / "trainer_rows.jsonl"
    write_jsonl(route_cards_path, route_cards)
    write_json(output_dir / "route_card_materialization_audit.json", route_audit)
    write_json(output_dir / "route_reason_counts.json", route_audit["route_counts"])
    write_json(output_dir / "route_cell_card.json", {"split_counts": route_audit["split_counts"], "route_counts": route_audit["route_counts"]})

    write_jsonl(loss_masks_path, loss_masks)
    write_json(output_dir / "loss_mask_authority_audit.json", loss_audit)
    write_json(
        output_dir / "loss_mask_enforcement_audit.json",
        {
            "loss_mask_cards": len(loss_masks),
            "decoder_rows": sum(int(card["decoder_ce_allowed"]) for card in loss_masks),
            "denoise_rows": sum(int(card["denoise_ce_allowed"]) for card in loss_masks),
            "runtime_reward_rows": sum(int(card["runtime_reward_allowed"]) for card in loss_masks),
            "forbidden_default_losses": list(ALL_DISABLED_LOSSES),
            "authority_closed": loss_audit["authority_closed"],
        },
    )

    write_jsonl(trainer_rows_path, trainer_rows)
    trainer_input = build_trainer_dry_run_input(
        trainer_rows,
        manifest_path=trainer_rows_path,
        route_cards_path=route_cards_path,
        loss_masks_path=loss_masks_path,
        output_dir=output_dir,
    )
    write_json(output_dir / "trainer_dry_run_input.json", trainer_input)
    write_json(output_dir / "trainer_input_audit.json", trainer_audit)

    return {
        "passed": (
            route_audit["missing_judge_rows"] == 0
            and route_audit["missing_ranker_rows"] == 0
            and route_audit["validation_failure_count"] == 0
            and loss_audit["missing_objective_rows"] == 0
            and loss_audit["forbidden_enabled_count"] == 0
            and trainer_audit["missing_route_cards"] == 0
            and trainer_audit["missing_loss_mask_cards"] == 0
        ),
        "route_audit": route_audit,
        "loss_audit": loss_audit,
        "trainer_audit": trainer_audit,
        "trainer_input": trainer_input,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize route cards, loss masks, and trainer input rows from recovered objective/judge/ranker artifacts.")
    parser.add_argument("--objective-rows", type=Path, required=True)
    parser.add_argument("--judge-rows", type=Path, required=True)
    parser.add_argument("--ranker-rows", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = materialize_training_setup(
        read_jsonl(args.objective_rows),
        read_jsonl(args.judge_rows),
        read_jsonl(args.ranker_rows),
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
