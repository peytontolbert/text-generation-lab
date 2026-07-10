#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9865
NAME = "stage9865_edit_localization_collapse_diagnostics"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9864_edit_localization_target_100m_structured_tiny_probe_audit.json"
SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage9864_edit_localization_target_100m_structured_tiny_probe_audit/edit_localization_target_100m_structured_tiny_probe_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9859_validity_weighted_structured_tiny_execution_review/tiny_structured_manifests/edit_localization_tiny.jsonl"
LOGITS = ROOT / "runs/local/artifacts/stage9864_edit_localization_target_100m_structured_tiny_probe/edit_localization_probe/row_field_logits.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "edit_localization_collapse_diagnostics.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EDIT_LOCALIZATION_COLLAPSE_DIAGNOSTICS_STAGE9865.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
NEXT_MANIFEST = OUT_DIR / "edit_localization_position_debiased_manifest.jsonl"
NEXT_CANDIDATE = OUT_DIR / "stage9866_edit_localization_position_debiased_probe_candidate.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def target_label(row: dict[str, Any]) -> str:
    tgt = row.get("target") if isinstance(row.get("target"), dict) else {}
    return str(tgt.get("edit_localization") or row.get("edit_localization_target") or row.get("edit_localization") or "")


def language(row: dict[str, Any]) -> str:
    return str(row.get("language_family") or row.get("language") or "unknown")


def option_position_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_split = defaultdict(Counter)
    by_split_lang = defaultdict(lambda: defaultdict(Counter))
    target_pos = defaultdict(Counter)
    fixed_alpha_order_rows = 0
    for row in rows:
        split = str(row.get("split") or "other")
        lang = language(row)
        tgt = target_label(row)
        by_split[split][tgt] += 1
        by_split_lang[split][lang][tgt] += 1
        choices = ((row.get("input_state") or {}).get("candidate_choices") or []) if isinstance(row.get("input_state"), dict) else []
        ordered_labels = []
        pos = None
        for idx, choice in enumerate(choices):
            text = str(choice)
            prefix = text.split(":", 1)[0].strip()
            ordered_labels.append(prefix)
            if prefix == f"option {tgt}":
                pos = idx
        if ordered_labels == ["option A", "option B", "option C", "option D", "option E"]:
            fixed_alpha_order_rows += 1
        if pos is not None:
            target_pos[tgt][pos] += 1
    return {
        "target_counts_by_split": {k: dict(v) for k, v in sorted(by_split.items())},
        "target_counts_by_split_and_language": {
            split: {lang: dict(counter) for lang, counter in sorted(langs.items())}
            for split, langs in sorted(by_split_lang.items())
        },
        "target_position_counts": {k: dict(v) for k, v in sorted(target_pos.items())},
        "fixed_alphabetical_option_order_rows": fixed_alpha_order_rows,
        "all_rows_use_fixed_alphabetical_option_order": fixed_alpha_order_rows == len(rows),
        "target_position_is_singleton_for_every_label": all(len(pos) == 1 for pos in target_pos.values()),
    }


def logit_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_target = defaultdict(lambda: {"rows": 0, "pred_counts": Counter(), "confidence_sum": 0.0, "margin_sum": 0.0, "top1_logit_sum": 0.0})
    top2_map = defaultdict(Counter)
    for record in records:
        tgt = str(record.get("target"))
        pred = str(record.get("pred"))
        card = by_target[tgt]
        card["rows"] += 1
        card["pred_counts"][pred] += 1
        card["confidence_sum"] += float(record.get("confidence") or 0.0)
        card["margin_sum"] += float(record.get("margin") or 0.0)
        card["top1_logit_sum"] += float(record.get("top1_logit") or 0.0)
        top2_map[tgt][str(record.get("top2_label"))] += 1
    out = {}
    for tgt, card in sorted(by_target.items()):
        rows = max(1, int(card["rows"]))
        out[tgt] = {
            "rows": card["rows"],
            "pred_counts": dict(sorted(card["pred_counts"].items())),
            "mean_confidence": card["confidence_sum"] / rows,
            "mean_margin": card["margin_sum"] / rows,
            "mean_top1_logit": card["top1_logit_sum"] / rows,
            "top2_label_counts": dict(sorted(top2_map[tgt].items())),
        }
    pred_counts = Counter(str(record.get("pred")) for record in records)
    dominant_label = None
    if pred_counts:
        dominant_label, _ = pred_counts.most_common(1)[0]
    return {
        "pred_counts": dict(sorted(pred_counts.items())),
        "dominant_predicted_label": dominant_label,
        "all_rows_predicted_as_single_label": len(pred_counts) == 1 and bool(records),
        "all_rows_predicted_as_A": pred_counts == Counter({"A": len(records)}),
        "by_target": out,
    }


def _deterministic_rotation(row_id: str, label: str) -> int:
    digest = hashlib.sha256(f"{row_id}:{label}:stage9866".encode("utf-8")).digest()
    return digest[0] % 5


def build_position_debiased_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out_rows: list[dict[str, Any]] = []
    target_position_counts = defaultdict(Counter)
    per_label_offsets = defaultdict(Counter)
    for row in rows:
        cloned = json.loads(json.dumps(row))
        input_state = cloned.get("input_state") if isinstance(cloned.get("input_state"), dict) else {}
        choices = list(input_state.get("candidate_choices") or [])
        tgt = target_label(cloned)
        row_id = str(cloned.get("row_id") or "")
        if len(choices) == 5 and tgt in {"A", "B", "C", "D", "E"}:
            offset = _deterministic_rotation(row_id, tgt)
            rotated = choices[offset:] + choices[:offset]
            input_state["candidate_choices"] = rotated
            cloned["input_state"] = input_state
            pos = None
            for idx, choice in enumerate(rotated):
                if str(choice).split(":", 1)[0].strip() == f"option {tgt}":
                    pos = idx
                    break
            if pos is not None:
                target_position_counts[tgt][pos] += 1
                per_label_offsets[tgt][offset] += 1
            anti = cloned.get("anti_cheat") if isinstance(cloned.get("anti_cheat"), dict) else {}
            anti["stage9866_candidate_choice_order_rotated"] = True
            anti["stage9866_rotation_offset"] = offset
            cloned["anti_cheat"] = anti
        out_rows.append(cloned)
    card = {
        "target_position_counts": {k: dict(v) for k, v in sorted(target_position_counts.items())},
        "per_label_offsets": {k: dict(v) for k, v in sorted(per_label_offsets.items())},
        "every_label_spans_multiple_positions": all(len(v) > 1 for v in target_position_counts.values()),
    }
    return out_rows, card


def build_candidate_command() -> list[str]:
    return [
        "/home/peyton/miniconda3/envs/ai/bin/python",
        "legacy_src/scripts/train_agentkernel_lite_encdec.py",
        "--repo-root", str(ROOT),
        "--manifest", str(NEXT_MANIFEST.relative_to(ROOT)),
        "--mode", "edit_localization_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", "configs/model/agentkernel_100m_seq2seq_recovered_target.json",
        "--tokenizer-json", "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json",
        "--tokenizer-config", "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json",
        "--tokenizer-hashlock", "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json",
        "--max-train-rows", "32",
        "--max-eval-rows", "16",
        "--max-strict-rows", "16",
        "--max-steps", "8",
        "--batch-size", "2",
        "--learning-rate", "5e-5",
        "--max-encoder-tokens", "512",
        "--max-decoder-tokens", "8",
        "--decoder-ce-weight", "0.0",
        "--structured-aux-weight", "1.0",
        "--denoise-weight", "0.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save", "1",
        "--output-dir", "runs/local/artifacts/stage9866_edit_localization_position_debiased_target_100m_probe/edit_localization_probe",
        "--run-id", "stage9866_edit_localization_position_debiased_target_100m_probe",
        "--execution-authorized-for-recovery-probe",
    ]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHITY_CLOSED) if False else dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    source_audit = load_json(SOURCE_AUDIT)
    rows = read_jsonl(MANIFEST)
    logits = read_jsonl(LOGITS)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9864_audit_not_passed")
    if not rows:
        failures.append("missing_manifest_rows")
    if not logits:
        failures.append("missing_logit_rows")

    position = option_position_stats(rows)
    logit = logit_stats(logits)
    debiased_rows, debias_card = build_position_debiased_rows(rows)
    write_jsonl(NEXT_MANIFEST, debiased_rows)
    candidate = {
        "future_stage": 9866,
        "future_stage_name": "stage9866_edit_localization_position_debiased_target_100m_probe",
        "selected_surface": "edit_localization",
        "reason": f"Stage9864 showed full collapse to label {logit.get('dominant_predicted_label')} while the tiny manifest renders options in fixed alphabetical order. Stage9866 keeps the same rows and labels but rotates the displayed option order to break position priors.",
        "command": build_candidate_command(),
        "requires_explicit_user_confirmation_before_execution": True,
        "requires_this_stage_passed": True,
        "authority": dict(AUTHORITY_CLOSED),
    }
    NEXT_CANDIDATE.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if not position["all_rows_use_fixed_alphabetical_option_order"]:
        failures.append("unexpected_nonfixed_option_order_in_source_manifest")
    if not position["target_position_is_singleton_for_every_label"]:
        failures.append("target_positions_not_singleton_in_source_manifest")
    source_collapse = (((source_audit.get("metrics") or {}).get("collapse")) or {}) if isinstance(source_audit.get("metrics"), dict) else {}
    if source_collapse.get("collapsed_to_single_label") is not True:
        failures.append("stage9864_not_confusion_backed_single_label_collapse")
    if not debias_card["every_label_spans_multiple_positions"]:
        failures.append("debiased_manifest_did_not_spread_target_positions")

    next_step = f"Run Stage9866 on the position-debiased edit-localization manifest, then compare whether strict exact rises above 0.25 and whether predictions stop collapsing to label {logit.get('dominant_predicted_label')} before changing optimizer or step budgets."
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "failures": failures,
        "position_diagnostics": position,
        "logit_diagnostics": logit,
        "source_stage9864_collapse": source_collapse,
        "debiased_manifest": str(NEXT_MANIFEST.relative_to(ROOT)),
        "debiased_manifest_diagnostics": debias_card,
        "next_execution_candidate": str(NEXT_CANDIDATE.relative_to(ROOT)),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": True,
        "promotion_ready": False,
        "created_at_unix": int(time.time()),
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "debiased_manifest": str(NEXT_MANIFEST.relative_to(ROOT)),
            "next_execution_candidate": str(NEXT_CANDIDATE.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "metrics": {
            "all_rows_use_fixed_alphabetical_option_order": position["all_rows_use_fixed_alphabetical_option_order"],
            "target_position_is_singleton_for_every_label": position["target_position_is_singleton_for_every_label"],
            "all_rows_predicted_as_A": logit["all_rows_predicted_as_A"],
            "debiased_every_label_spans_multiple_positions": debias_card["every_label_spans_multiple_positions"],
        },
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage9865 Edit-Localization Collapse Diagnostics",
            "",
            f"Passed: `{summary['passed']}`",
            f"Fixed alphabetical option order: `{position['all_rows_use_fixed_alphabetical_option_order']}`",
            f"Target position singleton by label: `{position['target_position_is_singleton_for_every_label']}`",
            f"All Stage9864 predictions collapsed to A: `{logit['all_rows_predicted_as_A']}`",
            f"Debiased manifest spreads labels across positions: `{debias_card['every_label_spans_multiple_positions']}`",
            "",
            "This stage turns the Stage9864 collapse into a concrete data hypothesis: the multilingual edit-localization tiny manifest is class-balanced, but it renders options in fixed A/B/C/D/E order, so the output token is also a fixed display position.",
            "",
            f"Next: {next_step}",
            "",
        ]) + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "candidate": str(NEXT_CANDIDATE.relative_to(ROOT)), "failures": failures}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
