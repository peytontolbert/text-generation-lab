#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8798
NAME = "stage8798_bounded_decoder_argument_controls_audit"
MANIFEST = ROOT / "runs/local/artifacts/stage8796_bounded_decoder_argument_controls_manifest/bounded_decoder_argument_controls_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDED_DECODER_ARGUMENT_CONTROLS_AUDIT_STAGE8798.md"
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
    return str(mapping[feature])


def grouped_baseline(rows: list[dict[str, Any]], features: list[str]) -> float:
    table: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        table[key][row["clean_state"]["bounded_argument_type"]] += 1
    correct = 0
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        correct += int(table[key].most_common(1)[0][0] == row["clean_state"]["bounded_argument_type"])
    return correct / len(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_rows()
    labels = [row["clean_state"]["bounded_argument_type"] for row in rows]
    features = [
        "language",
        "file_extension",
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
        "arg_visibility_bits": grouped_baseline(rows, ["small_argument_required", "argument_evidence_visible", "over_budget_signal", "approved_import_policy_visible", "path_context_visible", "symbol_context_visible"]),
        "budget_bits": grouped_baseline(rows, ["target_length_bucket", "max_arg_tokens", "decoder_budget_ok"]),
        "language+file_extension": grouped_baseline(rows, ["language", "file_extension"]),
        "argument_signal+arg_visibility_bits": grouped_baseline(rows, ["argument_signal", "small_argument_required", "argument_evidence_visible", "over_budget_signal", "approved_import_policy_visible", "path_context_visible", "symbol_context_visible"]),
    }
    proxy_single = {k: v for k, v in single.items() if k != "argument_signal"}
    proxy_combos = {k: v for k, v in combos.items() if k != "argument_signal+arg_visibility_bits"}
    gate_incomplete_rows = [row["row_id"] for row in rows if not isinstance(row.get("gate_status"), dict) or not all(row["gate_status"].values())]
    authority_rows = [row["row_id"] for row in rows if any((row.get("authority") or {}).values())]
    loss_rows = [row["row_id"] for row in rows if any((row.get("loss_mask") or {}).values())]
    raw_rows = [row["row_id"] for row in rows if (row.get("anti_cheat") or {}).get("raw_source_included") or (row.get("anti_cheat") or {}).get("raw_decoder_text_included")]
    card = {
        "rows": len(rows),
        "label_counts": dict(sorted(Counter(labels).items())),
        "majority_baseline": max(Counter(labels).values()) / len(labels),
        "single_feature_baselines": dict(sorted(single.items())),
        "combo_baselines": dict(sorted(combos.items())),
        "allowed_evidence_baselines": {
            "argument_signal": single["argument_signal"],
            "argument_signal+arg_visibility_bits": combos["argument_signal+arg_visibility_bits"],
        },
        "proxy_baseline_ceiling": 0.66,
        "max_proxy_single": max(proxy_single.values()),
        "max_proxy_combo": max(proxy_combos.values()),
        "gate_incomplete_rows": gate_incomplete_rows[:50],
        "gate_incomplete_row_count": len(gate_incomplete_rows),
        "authority_row_count": len(authority_rows),
        "training_loss_row_count": len(loss_rows),
        "raw_source_or_decoder_row_count": len(raw_rows),
        "authority": AUTHORITY_CLOSED,
    }
    card["passed"] = (
        card["majority_baseline"] <= 0.15
        and card["max_proxy_single"] <= card["proxy_baseline_ceiling"]
        and card["max_proxy_combo"] <= card["proxy_baseline_ceiling"]
        and card["gate_incomplete_row_count"] == 0
        and card["authority_row_count"] == 0
        and card["training_loss_row_count"] == 0
        and card["raw_source_or_decoder_row_count"] == 0
    )
    audit_path = OUT_DIR / "bounded_decoder_argument_controls_audit_card.json"
    audit_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": card["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            **card,
            "authority_rows": 0,
        },
        "artifacts": {
            "audit_card": str(audit_path.relative_to(ROOT)),
            "audited_manifest": str(MANIFEST.relative_to(ROOT)),
            "audit_script": "scripts/audit_stage8798_bounded_decoder_argument_controls.py",
        },
        "decision": (
            "Bounded decoder argument controls pass shortcut/gate audit; still no decoder CE, training, runtime, source/body emission, or promotion."
            if card["passed"]
            else "Bounded decoder argument controls audit failed."
        ),
        "next_best_step": "Attach bounded decoder argument controls to central graph, then rebuild bounded decoder CE package controls without enabling CE.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8798 Bounded Decoder Argument Controls Audit",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Rows: `{card['rows']}`",
        f"Majority baseline: `{card['majority_baseline']}`",
        f"Max proxy single: `{card['max_proxy_single']}`",
        f"Max proxy combo: `{card['max_proxy_combo']}`",
        f"Gate incomplete rows: `{card['gate_incomplete_row_count']}`",
        f"Training loss rows: `{card['training_loss_row_count']}`",
        f"Authority rows: `{card['authority_row_count']}`",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
