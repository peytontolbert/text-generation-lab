#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "runs/local/artifacts/stage8797_bounded_decoder_argument_controls_manifest/bounded_decoder_argument_controls_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts/stage8798_bounded_decoder_argument_controls_shortcut_gate"
SUMMARY = ROOT / "runs/summaries/stage8798_bounded_decoder_argument_controls_shortcut_gate.json"
DOC = ROOT / "docs/BOUNDED_DECODER_ARGUMENT_CONTROLS_SHORTCUT_GATE_STAGE8798.md"

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


def read_rows() -> list[dict[str, Any]]:
    return [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]


def feature_value(row: dict[str, Any], feature: str) -> str:
    state = row["corrupted_state"]
    feats = state["bounded_argument_features"]
    budget = state["budget"]
    mapping = {
        "language": state["language"],
        "file_extension": state["file_extension"],
        "context_key": state.get("context_group", "missing_context_group"),
        "argument_signal": state["argument_signal"],
        "small_argument_required": str(feats["small_argument_required"]),
        "argument_evidence_visible": str(feats["argument_evidence_visible"]),
        "over_budget_signal": str(feats["over_budget_signal"]),
        "approved_import_policy_visible": str(feats["approved_import_policy_visible"]),
        "path_context_visible": str(feats["path_context_visible"]),
        "symbol_context_visible": str(feats["symbol_context_visible"]),
        "target_length_bucket": budget["target_length_bucket"],
        "max_arg_tokens": str(budget["max_arg_tokens"]),
        "decoder_budget_ok": str(budget["decoder_budget_ok"]),
    }
    return mapping[feature]


def grouped_baseline(rows: list[dict[str, Any]], features: list[str]) -> float:
    table: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        table[key][row["clean_state"]["bounded_argument_type"]] += 1
    correct = 0
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        correct += int(table[key].most_common(1)[0][0] == row["clean_state"]["bounded_argument_type"])
    return correct / len(rows) if rows else 0.0


def complete_gate_rows(rows: list[dict[str, Any]]) -> int:
    return sum(int(bool(row.get("gate_status")) and all((row.get("gate_status") or {}).values())) for row in rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = read_rows()
    labels = [row["clean_state"]["bounded_argument_type"] for row in rows]
    features = [
        "language",
        "file_extension",
        "context_key",
        "argument_signal",
        "small_argument_required",
        "argument_evidence_visible",
        "over_budget_signal",
        "approved_import_policy_visible",
        "path_context_visible",
        "symbol_context_visible",
        "target_length_bucket",
        "max_arg_tokens",
        "decoder_budget_ok",
    ]
    single = {feature: grouped_baseline(rows, [feature]) for feature in features}
    combos = {
        "language+context_key": grouped_baseline(rows, ["language", "context_key"]),
        "arg_visibility_bits": grouped_baseline(rows, ["small_argument_required", "argument_evidence_visible", "over_budget_signal", "approved_import_policy_visible", "path_context_visible", "symbol_context_visible"]),
        "budget_bits": grouped_baseline(rows, ["target_length_bucket", "max_arg_tokens", "decoder_budget_ok"]),
        "argument_signal+arg_visibility_bits": grouped_baseline(rows, ["argument_signal", "small_argument_required", "argument_evidence_visible", "over_budget_signal", "approved_import_policy_visible", "path_context_visible", "symbol_context_visible"]),
    }
    proxy_single = {k: v for k, v in single.items() if k != "argument_signal"}
    proxy_combos = {k: v for k, v in combos.items() if k != "argument_signal+arg_visibility_bits"}
    authority_rows = sum(int(any((row.get("authority") or {}).values())) for row in rows)
    training_loss_rows = sum(int(any((row.get("loss_mask") or {}).values())) for row in rows)
    raw_source_rows = sum(int((row.get("anti_cheat") or {}).get("raw_source_included") is True) for row in rows)
    raw_decoder_rows = sum(int((row.get("anti_cheat") or {}).get("raw_decoder_text_included") is True) for row in rows)
    row_id_label_leaks = sum(int((row["clean_state"]["bounded_argument_type"] in row.get("row_id", "")) or (row["clean_state"]["bounded_argument_type"] in row.get("semantic_key", ""))) for row in rows)
    metrics = {
        **AUTHORITY_CLOSED,
        "rows": len(rows),
        "label_counts": dict(sorted(Counter(labels).items())),
        "split_counts": dict(sorted(Counter(row.get("split") for row in rows).items())),
        "majority_baseline": max(Counter(labels).values()) / len(labels) if labels else 0.0,
        "single_feature_baselines": dict(sorted(single.items())),
        "combo_baselines": dict(sorted(combos.items())),
        "allowed_evidence_baselines": {
            "argument_signal": single["argument_signal"],
            "argument_signal+arg_visibility_bits": combos["argument_signal+arg_visibility_bits"],
        },
        "proxy_baseline_ceiling": 0.66,
        "max_proxy_single": max(proxy_single.values()) if proxy_single else 0.0,
        "max_proxy_combo": max(proxy_combos.values()) if proxy_combos else 0.0,
        "authority_rows": authority_rows,
        "training_loss_rows": training_loss_rows,
        "complete_gate_status_rows": complete_gate_rows(rows),
        "raw_source_rows": raw_source_rows,
        "raw_decoder_text_rows": raw_decoder_rows,
        "row_id_label_leak_rows": row_id_label_leaks,
    }
    failures = []
    if metrics["rows"] != 504:
        failures.append("row_count_changed")
    if metrics["majority_baseline"] > 0.15:
        failures.append("majority_baseline_high")
    if metrics["max_proxy_single"] > metrics["proxy_baseline_ceiling"]:
        failures.append("single_feature_proxy_high")
    if metrics["max_proxy_combo"] > metrics["proxy_baseline_ceiling"]:
        failures.append("combo_feature_proxy_high")
    if authority_rows:
        failures.append("authority_rows_nonzero")
    if training_loss_rows:
        failures.append("training_loss_rows_nonzero")
    if metrics["complete_gate_status_rows"] != metrics["rows"]:
        failures.append("incomplete_gate_status")
    if raw_source_rows or raw_decoder_rows:
        failures.append("raw_text_visible")
    if row_id_label_leaks:
        failures.append("row_id_label_leaks")
    metrics["failures"] = failures
    card = {
        "stage": 8798,
        "stage_name": "stage8798_bounded_decoder_argument_controls_shortcut_gate",
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {
            "audit_card": "runs/local/artifacts/stage8798_bounded_decoder_argument_controls_shortcut_gate/shortcut_gate_card.json",
            "audited_manifest": str(MANIFEST.relative_to(ROOT)),
            "audit_script": "scripts/audit_stage8798_bounded_decoder_argument_controls_shortcut_gate.py",
        },
        "decision": "Bounded decoder argument controls passed shortcut/gate audit with authority and losses closed." if not failures else "Bounded decoder argument controls failed shortcut/gate audit.",
        "next_best_step": "Attach Stage8797/8798 bounded decoder argument controls to the central graph, then recover output_repair_denoise candidate controls.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "shortcut_gate_card.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8798 Bounded Decoder Argument Controls Shortcut Gate",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Audited the Stage8797 bounded decoder argument candidate controls for non-evidence shortcut dominance, complete recovered gate status, closed authority, closed loss masks, and raw text absence.",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Majority baseline: `{metrics['majority_baseline']}`",
        f"Max proxy single baseline: `{metrics['max_proxy_single']}`",
        f"Max proxy combo baseline: `{metrics['max_proxy_combo']}`",
        f"Complete gate-status rows: `{metrics['complete_gate_status_rows']}`",
        f"Authority rows: `{metrics['authority_rows']}`",
        f"Training loss rows: `{metrics['training_loss_rows']}`",
        "",
        "Argument signal remains allowed semantic evidence; non-evidence proxy features must stay below the shortcut ceiling.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
