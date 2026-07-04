#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8650_aggregate_structured_curriculum_gate"
SUMMARY = ROOT / "runs" / "summaries" / "stage8650_aggregate_structured_curriculum_gate.json"
DOC = ROOT / "docs" / "AGGREGATE_STRUCTURED_CURRICULUM_GATE_STAGE8650.md"

AUTHORITY_KEYS = [
    "model_execution_authorized_next",
    "decoder_ce_training_authorized_next",
    "runtime_authorized",
    "source_emission_authorized",
    "body_emission_authorized",
    "gemma_execution_authorized_next",
    "harness_execution_authorized_next",
    "scoring_authorized_next",
    "controller_complete_merge_authorized_next",
    "promotion_ready",
]
AUTHORITY_CLOSED = {key: False for key in AUTHORITY_KEYS}

OBJECTIVES = {
    "intent_to_build_strategy": {
        "manifest_summary": "stage8630_intent_to_build_neutral_manifest.json",
        "shortcut_summary": "stage8631_intent_to_build_shortcut_baseline.json",
        "required_loss_closed": ["decoder_ce", "runtime_reward"],
    },
    "edit_localization": {
        "manifest_summary": "stage8636_edit_localization_neutral_manifest.json",
        "shortcut_summary": "stage8637_edit_localization_shortcut_baseline.json",
        "required_loss_closed": ["decoder_ce", "runtime_reward"],
    },
    "patch_operator": {
        "manifest_summary": "stage8638_patch_operator_neutral_manifest.json",
        "shortcut_summary": "stage8639_patch_operator_shortcut_baseline.json",
        "required_loss_closed": ["decoder_ce", "runtime_reward"],
    },
    "verifier_repair": {
        "manifest_summary": "stage8643_verifier_repair_neutral_manifest.json",
        "shortcut_summary": "stage8644_verifier_repair_shortcut_baseline.json",
        "required_loss_closed": ["decoder_ce", "runtime_reward"],
    },
    "bounded_decoder_arguments": {
        "manifest_summary": "stage8645_bounded_decoder_arguments_neutral_manifest.json",
        "shortcut_summary": "stage8646_bounded_decoder_arguments_shortcut_baseline.json",
        "required_loss_closed": ["decoder_ce", "runtime_reward"],
    },
    "output_repair_denoise": {
        "manifest_summary": "stage8647_output_repair_denoise_neutral_manifest.json",
        "shortcut_summary": "stage8648_output_repair_denoise_shortcut_baseline.json",
        "required_loss_closed": ["decoder_ce", "denoise_ce", "runtime_reward"],
    },
}


def load_summary(name: str) -> dict[str, Any]:
    path = ROOT / "runs" / "summaries" / name
    if not path.exists():
        return {"exists": False, "summary_file": name, "passed": False}
    data = json.loads(path.read_text(encoding="utf-8"))
    data["exists"] = True
    data["summary_file"] = name
    data["summary_path"] = str(path.relative_to(ROOT))
    return data


def opened_authority(summary: dict[str, Any]) -> dict[str, Any]:
    authority = summary.get("authority") or summary.get("metrics", {}).get("authority") or {}
    return {key: authority.get(key) for key in AUTHORITY_KEYS if bool(authority.get(key))}


def metric(summary: dict[str, Any], key: str, default: Any = None) -> Any:
    metrics = summary.get("metrics", {})
    if key in metrics:
        return metrics[key]
    return default


def loss_rows(summary: dict[str, Any], loss_name: str) -> int:
    metrics = summary.get("metrics", {})
    if f"{loss_name}_rows" in metrics:
        return int(metrics.get(f"{loss_name}_rows") or 0)
    loss_counts = metrics.get("loss_counts") or {}
    return int(loss_counts.get(loss_name) or 0)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    objective_cards: dict[str, Any] = {}
    failures: list[str] = []
    total_rows = 0
    total_proxy_max = 0.0
    authority_open: list[dict[str, Any]] = []

    for objective, spec in OBJECTIVES.items():
        manifest = load_summary(spec["manifest_summary"])
        shortcut = load_summary(spec["shortcut_summary"])
        opened = {"manifest": opened_authority(manifest), "shortcut": opened_authority(shortcut)}
        if opened["manifest"] or opened["shortcut"]:
            authority_open.append({"objective": objective, "opened": opened})
        rows = int(metric(manifest, "rows", 0) or 0)
        total_rows += rows
        max_proxy_single = float(metric(shortcut, "max_proxy_single", 0.0) or 0.0)
        max_proxy_combo = float(metric(shortcut, "max_proxy_combo", 0.0) or 0.0)
        total_proxy_max = max(total_proxy_max, max_proxy_single, max_proxy_combo)
        closed_losses = {loss: loss_rows(manifest, loss) == 0 for loss in spec["required_loss_closed"]}
        local_pass = bool(manifest.get("exists") and manifest.get("passed"))
        shortcut_pass = bool(shortcut.get("exists") and shortcut.get("passed"))
        objective_pass = local_pass and shortcut_pass and all(closed_losses.values()) and not opened["manifest"] and not opened["shortcut"]
        if not objective_pass:
            failures.append(objective)
        objective_cards[objective] = {
            "passed": objective_pass,
            "manifest_summary": manifest.get("summary_path"),
            "shortcut_summary": shortcut.get("summary_path"),
            "rows": rows,
            "manifest_passed": manifest.get("passed"),
            "shortcut_passed": shortcut.get("passed"),
            "max_proxy_single": max_proxy_single,
            "max_proxy_combo": max_proxy_combo,
            "required_loss_closed": closed_losses,
            "authority_open": opened,
        }

    hard_blockers = [
        "repo_state_graph_v1 enrichment remains source-sparse/synthetic-small",
        "symbol_binding remains partial and imbalance-prone",
        "source-backed expansion and junk/ranker gates are not yet attached to the recovered objectives",
        "native model/training/decode/runtime authority is still intentionally closed",
    ]
    card = {
        "stage": 8650,
        "stage_name": "stage8650_aggregate_structured_curriculum_gate",
        "passed": not failures and not authority_open,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            "objectives_checked": len(OBJECTIVES),
            "objective_failures": failures,
            "total_manifest_rows": total_rows,
            "max_proxy_baseline_seen": total_proxy_max,
            "authority_open_rows": authority_open,
            "hard_blockers_before_training": hard_blockers,
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "runtime_authorized": False,
            "promotion_ready": False,
        },
        "objectives": objective_cards,
        "decision": "Recovered structured objectives pass as a no-authority curriculum scaffold. This is not a training gate: graph enrichment, symbol binding, source-backed expansion, and data-ranker gates remain required.",
        "next_best_step": "Repair symbol_binding and repo_state_graph_v1 enrichment, then attach source-backed reservoir sampling plus junk/ranker gates before any training candidate.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "aggregate_structured_curriculum_gate.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")

    lines = [
        "# Stage8650 Aggregate Structured Curriculum Gate",
        "",
        "This is a no-authority aggregate gate over the recovered structured objectives. It does not authorize training, decoder CE, denoise CE, runtime, source/body emission, harness execution, Gemma, scoring, or promotion.",
        "",
        "## Objective Status",
    ]
    for objective, info in objective_cards.items():
        lines.append(f"- `{objective}`: passed={info['passed']}, rows={info['rows']}, max_proxy={max(info['max_proxy_single'], info['max_proxy_combo']):.3f}")
    lines.extend(["", "## Hard Blockers Before Training"])
    for blocker in hard_blockers:
        lines.append(f"- {blocker}")
    lines.extend(["", "## Next Step", card["next_best_step"]])
    DOC.write_text("\n".join(lines) + "\n")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
