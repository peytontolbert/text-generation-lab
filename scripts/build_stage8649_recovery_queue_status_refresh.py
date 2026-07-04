#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8649_recovery_queue_status_refresh"
SUMMARY = ROOT / "runs" / "summaries" / "stage8649_recovery_queue_status_refresh.json"
DOC = ROOT / "docs" / "RECOVERY_QUEUE_STATUS_STAGE8649.md"

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

RESTORED = {
    "intent_to_build_strategy": [
        "stage8630_intent_to_build_neutral_manifest.json",
        "stage8631_intent_to_build_shortcut_baseline.json",
    ],
    "edit_localization": [
        "stage8636_edit_localization_neutral_manifest.json",
        "stage8637_edit_localization_shortcut_baseline.json",
    ],
    "patch_operator": [
        "stage8638_patch_operator_neutral_manifest.json",
        "stage8639_patch_operator_shortcut_baseline.json",
    ],
    "verifier_repair": [
        "stage8643_verifier_repair_neutral_manifest.json",
        "stage8644_verifier_repair_shortcut_baseline.json",
    ],
    "bounded_decoder_arguments": [
        "stage8645_bounded_decoder_arguments_neutral_manifest.json",
        "stage8646_bounded_decoder_arguments_shortcut_baseline.json",
    ],
    "output_repair_denoise": [
        "stage8647_output_repair_denoise_neutral_manifest.json",
        "stage8648_output_repair_denoise_shortcut_baseline.json",
    ],
}
PARTIAL = {
    "repo_state_graph_v1_enrichment": "Seed graph was restored/patched at 8536-8539, but enrichment is still synthetic-small and needs source-backed graph expansion plus aggregate curriculum gates.",
    "symbol_binding": "Known partial: symbol-binding objective needs imbalance repair, source-backed rows, and direct route-card coverage before any training candidate.",
}


def read_summary(filename: str) -> dict[str, Any]:
    path = ROOT / "runs" / "summaries" / filename
    if not path.exists():
        return {"summary_file": filename, "exists": False, "passed": False}
    data = json.loads(path.read_text(encoding="utf-8"))
    data["summary_path"] = str(path.relative_to(ROOT))
    data["summary_file"] = filename
    data["exists"] = True
    return data


def authority_open(summary: dict[str, Any]) -> dict[str, Any]:
    authority = summary.get("authority") or summary.get("metrics", {}).get("authority") or {}
    return {key: authority.get(key) for key in AUTHORITY_KEYS if bool(authority.get(key))}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    objective_cards: dict[str, Any] = {}
    restored_count = 0
    failed_or_missing: list[str] = []
    authority_open_rows: list[dict[str, Any]] = []

    for objective, summary_files in RESTORED.items():
        summaries = [read_summary(filename) for filename in summary_files]
        passed = all(item.get("exists") and item.get("passed") for item in summaries)
        restored_count += int(passed)
        if not passed:
            failed_or_missing.append(objective)
        for item in summaries:
            opened = authority_open(item)
            if opened:
                authority_open_rows.append({"objective": objective, "stage": item.get("stage"), "opened": opened})
        objective_cards[objective] = {
            "status": "restored_local_and_shortcut_audited" if passed else "failed_or_missing",
            "summary_files": summary_files,
            "summaries": [
                {
                    "stage": item.get("stage"),
                    "stage_name": item.get("stage_name"),
                    "passed": item.get("passed"),
                    "summary_path": item.get("summary_path"),
                }
                for item in summaries
            ],
        }

    card = {
        "stage": 8649,
        "stage_name": "stage8649_recovery_queue_status_refresh",
        "passed": restored_count == len(RESTORED) and not authority_open_rows,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            "restored_objectives": restored_count,
            "expected_restored_objectives": len(RESTORED),
            "failed_or_missing_objectives": failed_or_missing,
            "partial_objectives": PARTIAL,
            "authority_open_rows": authority_open_rows,
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "runtime_authorized": False,
            "source_emission_authorized": False,
            "body_emission_authorized": False,
            "promotion_ready": False,
        },
        "objectives": objective_cards,
        "decision": "Recovery queue builders are restored for six bounded structured objectives. Remaining work is graph enrichment, symbol-binding repair, aggregate curriculum gating, and source-backed expansion. No training or decoder authority is opened.",
        "next_best_step": "Build an aggregate structured-curriculum gate over restored objectives, then repair repo_state_graph_v1 enrichment and symbol_binding before any training candidate.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "recovery_queue_status.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")

    lines = [
        "# Stage8649 Recovery Queue Status",
        "",
        "## Restored Objectives",
    ]
    for objective, info in objective_cards.items():
        lines.append(f"- `{objective}`: {info['status']} via {', '.join(info['summary_files'])}")
    lines.extend([
        "",
        "## Still Partial",
    ])
    for objective, reason in PARTIAL.items():
        lines.append(f"- `{objective}`: {reason}")
    lines.extend([
        "",
        "## Authority Boundary",
        "- Model/native execution: closed",
        "- Decoder CE: closed",
        "- Denoise CE: closed",
        "- Runtime/source/body/Gemma/harness/scoring/promotion: closed",
        "",
        "## Next Gate",
        "Build an aggregate structured-curriculum gate across the restored objectives, then repair graph enrichment and symbol binding before any training candidate.",
    ])
    DOC.write_text("\n".join(lines) + "\n")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
