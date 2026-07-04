#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage8681_unified_dataset_junk_ood_ranker_readiness"
SUMMARY = ROOT / "runs/summaries/stage8681_unified_dataset_junk_ood_ranker_readiness.json"
DOC = ROOT / "docs/UNIFIED_DATASET_JUNK_OOD_RANKER_READINESS_STAGE8681.md"
MANIFEST = ROOT / "runs/local/artifacts/stage8676_source_backed_symbol_binding_shortcut_repair_manifest/source_backed_symbol_binding_shortcut_repair_manifest.jsonl"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

import sys

sys.path.insert(0, str(ROOT / "scripts"))
from dataset_junk_ood_ranker_v1 import AUTHORITY_CLOSED, rank_rows_v1


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    sample_rows = [
        {"row_id": "sample_long", "decoder_text": "<html>" + ("x " * 900), "decode_allowed": False, "decoder_budget_ok": False},
        {"row_id": "sample_denoise", "decoder_text": "<MNSB1> POLICY_CONTINUE", "decode_allowed": True, "decoder_budget_ok": True},
        {"row_id": "sample_locked", "source_lineage": {"graph_nodes_source_id": "locked_a"}},
        {"row_id": "sample_leak", "encoder_text": "prefix EXACT_TARGET_PAYLOAD suffix", "target_text": "EXACT_TARGET_PAYLOAD"},
        {"row_id": "sample_structured", "objective_family": "symbol_binding", "clean_state": {"action": "RETRIEVE_MORE"}},
    ]
    sample_card = rank_rows_v1(sample_rows, max_decoder_tokens=100, locked_source_ids={"locked_a"})
    manifest_card = rank_rows_v1(read_jsonl(MANIFEST), max_decoder_tokens=768)
    (OUT_DIR / "sample_ranker_card.json").write_text(json.dumps(sample_card, indent=2, sort_keys=True) + "\n")
    (OUT_DIR / "stage8676_manifest_ranker_card.json").write_text(json.dumps(manifest_card, indent=2, sort_keys=True) + "\n")

    expected_sample_routes = {
        "HOLD_LONG_OUTPUT",
        "USE_FOR_DENOISE_REPAIR",
        "QUARANTINE_AUTHORITY_OR_LOCKED",
        "QUARANTINE_LABEL_CONFLICT",
        "KEEP_STRUCTURED",
    }
    if set(sample_card["route_counts"]) != expected_sample_routes:
        failures.append("sample_route_coverage_failed")
    if any(value is not False for value in sample_card["authority"].values()):
        failures.append("sample_authority_not_closed")
    if any(value is not False for value in manifest_card["authority"].values()):
        failures.append("manifest_authority_not_closed")
    if manifest_card["route_counts"] != {"KEEP_STRUCTURED": 80}:
        failures.append("stage8676_manifest_not_all_keep_structured")
    if manifest_card["loss_counts"].get("decoder_ce") != 0 or manifest_card["loss_counts"].get("denoise_ce") != 0:
        failures.append("stage8676_manifest_opened_decoder_or_denoise_loss")

    card = {
        "stage": 8681,
        "stage_name": "stage8681_unified_dataset_junk_ood_ranker_readiness",
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            "failures": failures,
            "sample_rows": len(sample_rows),
            "sample_route_counts": sample_card["route_counts"],
            "stage8676_rows": manifest_card["rows"],
            "stage8676_route_counts": manifest_card["route_counts"],
            "stage8676_loss_counts": manifest_card["loss_counts"],
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "runtime_authorized": False,
            "promotion_ready": False,
            "data_mining_allowed": False,
            "training_allowed": False,
        },
        "artifacts": {
            "ranker_module": "scripts/dataset_junk_ood_ranker_v1.py",
            "tests": "tests/test_dataset_junk_ood_ranker_v1.py",
            "sample_card": str((OUT_DIR / "sample_ranker_card.json").relative_to(ROOT)),
            "stage8676_manifest_card": str((OUT_DIR / "stage8676_manifest_ranker_card.json").relative_to(ROOT)),
        },
        "decision": "Recovered unified dataset_junk_ood_ranker_v1 as a deterministic support module. It is ready as a shared judge/ranker API but does not authorize mining, training, decoder CE, denoise CE, runtime, or promotion.",
        "next_best_step": "Recover cluster_slice_near_duplicate_detector next, then attach both ranker and cluster detector to the central graph before any source-backed expansion.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "unified_ranker_readiness_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "# Stage8681 Unified Dataset Junk/OOD Ranker Readiness\n\n"
        f"Passed: `{card['passed']}`\n\n"
        f"- Sample routes: `{sample_card['route_counts']}`\n"
        f"- Stage8676 routes: `{manifest_card['route_counts']}`\n"
        f"- Failures: `{failures}`\n\n"
        "This is support-module recovery only. Mining, model execution, training, decoder CE, denoise CE, runtime, and promotion remain closed.\n"
    )

    old_rows = []
    if REGISTRY.exists():
        try:
            old_rows = list((json.loads(REGISTRY.read_text()).get("rows") or []))
        except Exception:
            old_rows = []
    rows = old_rows + [card]
    REGISTRY.write_text(
        json.dumps(
            {
                "passed": card["passed"],
                "rows": rows,
                "metrics": {
                    "min_stage": min([row.get("stage", 8681) for row in rows] + [8681]),
                    "max_stage": 8681,
                    "latest_stage": 8681,
                    "latest_stage_name": card["stage_name"],
                    "latest_stage_next_best_step": card["next_best_step"],
                    "registry_rows": len(rows),
                    "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0 if card["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
