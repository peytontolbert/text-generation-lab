#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8811
NAME = "stage8811_output_repair_denoise_controls_shortcut_gate"
MANIFEST = ROOT / "runs/local/artifacts/stage8810_output_repair_denoise_controls_manifest/output_repair_denoise_controls_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OUTPUT_REPAIR_DENOISE_CONTROLS_SHORTCUT_GATE_STAGE8811.md"
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
    bad = state.get("bad_output_features") or {}
    budget = state.get("budget") or {}
    mapping = {
        "language": state.get("language"),
        "file_extension": state.get("file_extension"),
        "candidate_surface_kind": state.get("candidate_surface_kind"),
        "repair_signal": state.get("repair_signal"),
        "has_internal_token_shape": bad.get("has_internal_token_shape"),
        "has_repetition": bad.get("has_repetition"),
        "structured_state_available": bad.get("structured_state_available"),
        "surface_mismatch": bad.get("surface_mismatch"),
        "too_short": bad.get("too_short"),
        "unsafe_or_unrecoverable": bad.get("unsafe_or_unrecoverable"),
        "verifier_feedback_visible": bad.get("verifier_feedback_visible"),
        "max_repair_steps": budget.get("max_repair_steps"),
        "decoder_budget_ok": budget.get("decoder_budget_ok"),
        "denoise_training_authorized": budget.get("denoise_training_authorized"),
    }
    return str(mapping[feature])


def grouped_baseline(rows: list[dict[str, Any]], features: list[str]) -> float:
    table: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        table[key][row["clean_state"]["output_repair_action"]] += 1
    correct = 0
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        correct += int(table[key].most_common(1)[0][0] == row["clean_state"]["output_repair_action"])
    return correct / len(rows) if rows else 0.0


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_rows()
    labels = [row["clean_state"]["output_repair_action"] for row in rows]
    features = [
        "language", "file_extension", "candidate_surface_kind", "repair_signal",
        "has_internal_token_shape", "has_repetition", "structured_state_available",
        "surface_mismatch", "too_short", "unsafe_or_unrecoverable", "verifier_feedback_visible",
        "max_repair_steps", "decoder_budget_ok", "denoise_training_authorized",
    ]
    single = {feature: grouped_baseline(rows, [feature]) for feature in features}
    combos = {
        "language+surface": grouped_baseline(rows, ["language", "candidate_surface_kind"]),
        "bad_output_bits": grouped_baseline(rows, ["has_internal_token_shape", "has_repetition", "surface_mismatch", "too_short", "unsafe_or_unrecoverable"]),
        "context_bits": grouped_baseline(rows, ["structured_state_available", "verifier_feedback_visible"]),
        "budget_bits": grouped_baseline(rows, ["max_repair_steps", "decoder_budget_ok", "denoise_training_authorized"]),
        "repair_signal+context_bits": grouped_baseline(rows, ["repair_signal", "structured_state_available", "verifier_feedback_visible"]),
    }
    proxy_single = {k: v for k, v in single.items() if k != "repair_signal"}
    proxy_combos = {k: v for k, v in combos.items() if k != "repair_signal+context_bits"}
    authority_rows = [row["row_id"] for row in rows if any((row.get("authority") or {}).values())]
    loss_rows = [row["row_id"] for row in rows if any((row.get("loss_mask") or {}).values())]
    incomplete_gate_rows = [row["row_id"] for row in rows if not all((row.get("gate_status") or {}).values())]
    raw_rows = [row["row_id"] for row in rows if any((row.get("anti_cheat") or {}).get(k) for k in ["raw_source_included", "raw_decoder_text_included", "raw_patch_body_included", "bad_output_text_in_encoder", "target_text_in_encoder", "target_label_in_id", "source_row_id_in_model_input"])]
    denoise_now = [row["row_id"] for row in rows if row["clean_state"].get("denoise_ce_eligible_now") is True]
    metrics = {
        **AUTHORITY_CLOSED,
        "rows": len(rows),
        "label_counts": dict(sorted(Counter(labels).items())),
        "majority_baseline": max(Counter(labels).values()) / len(labels),
        "single_feature_baselines": dict(sorted(single.items())),
        "combo_baselines": dict(sorted(combos.items())),
        "allowed_evidence_baselines": {
            "repair_signal": single["repair_signal"],
            "repair_signal+context_bits": combos["repair_signal+context_bits"],
        },
        "proxy_baseline_ceiling": 0.66,
        "max_proxy_single": max(proxy_single.values()),
        "max_proxy_combo": max(proxy_combos.values()),
        "authority_rows": len(authority_rows),
        "loss_rows": len(loss_rows),
        "incomplete_gate_rows": len(incomplete_gate_rows),
        "raw_or_target_visible_rows": len(raw_rows),
        "denoise_ce_eligible_now_rows": len(denoise_now),
    }
    failures = []
    if metrics["rows"] != 360:
        failures.append("row_count_changed")
    if metrics["majority_baseline"] > 0.21:
        failures.append("majority_baseline_high")
    if metrics["max_proxy_single"] > metrics["proxy_baseline_ceiling"]:
        failures.append("single_proxy_high")
    if metrics["max_proxy_combo"] > metrics["proxy_baseline_ceiling"]:
        failures.append("combo_proxy_high")
    if any(metrics[k] for k in ["authority_rows", "loss_rows", "incomplete_gate_rows", "raw_or_target_visible_rows", "denoise_ce_eligible_now_rows"]):
        failures.append("safety_or_gate_failure")
    metrics["failures"] = failures
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {
            "audit_card": str((OUT_DIR / "output_repair_denoise_controls_shortcut_gate_card.json").relative_to(ROOT)),
            "audited_manifest": str(MANIFEST.relative_to(ROOT)),
            "audit_script": "scripts/audit_stage8811_output_repair_denoise_controls_shortcut_gate.py",
        },
        "decision": "Output repair/denoise controls passed shortcut/gate audit with all losses and authorities closed." if not failures else "Output repair/denoise controls shortcut/gate audit failed.",
        "next_best_step": "Attach output repair/denoise controls to the central graph. Do not enable denoise CE.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "output_repair_denoise_controls_shortcut_gate_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8811 Output Repair Denoise Controls Shortcut Gate",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Majority baseline: `{metrics['majority_baseline']}`",
        f"Max proxy single: `{metrics['max_proxy_single']}`",
        f"Max proxy combo: `{metrics['max_proxy_combo']}`",
        f"Loss rows: `{metrics['loss_rows']}`",
        f"Denoise CE eligible now rows: `{metrics['denoise_ce_eligible_now_rows']}`",
        "",
        "Repair signal is allowed semantic evidence; non-evidence proxies remain below ceiling. Denoise CE remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
