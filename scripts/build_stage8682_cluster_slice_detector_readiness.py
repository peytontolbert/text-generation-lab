#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage8682_cluster_slice_detector_readiness"
SUMMARY = ROOT / "runs/summaries/stage8682_cluster_slice_detector_readiness.json"
DOC = ROOT / "docs/CLUSTER_SLICE_DETECTOR_READINESS_STAGE8682.md"
MANIFEST = ROOT / "runs/local/artifacts/stage8676_source_backed_symbol_binding_shortcut_repair_manifest/source_backed_symbol_binding_shortcut_repair_manifest.jsonl"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

import sys

sys.path.insert(0, str(ROOT / "scripts"))
from cluster_slice_near_duplicate_detector import detect_clusters
from dataset_junk_ood_ranker_v1 import AUTHORITY_CLOSED


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    sample_rows = [
        {"row_id": "sample_a", "split": "train", "semantic_key": "same", "encoder_text": "alpha beta gamma delta epsilon"},
        {"row_id": "sample_b", "split": "eval", "semantic_key": "same", "encoder_text": "alpha beta gamma delta epsilon"},
        {"row_id": "sample_c", "split": "train", "objective_family": "x", "clean_state": {"binding_action": "A"}, "graph_input": {"query_kind": "q"}},
    ]
    sample_card = detect_clusters(sample_rows, near_duplicate_threshold=0.9)
    manifest_card = detect_clusters(read_jsonl(MANIFEST), near_duplicate_threshold=0.97)
    (OUT_DIR / "sample_cluster_card.json").write_text(json.dumps(sample_card, indent=2, sort_keys=True) + "\n")
    (OUT_DIR / "stage8676_manifest_cluster_card.json").write_text(json.dumps(manifest_card, indent=2, sort_keys=True) + "\n")

    if sample_card["metrics"]["semantic_split_overlap_clusters"] < 1:
        failures.append("sample_semantic_split_overlap_not_detected")
    if sample_card["metrics"]["near_duplicate_pairs"] < 1:
        failures.append("sample_near_duplicate_not_detected")
    if manifest_card["rows"] != 80:
        failures.append("stage8676_row_count_mismatch")

    card = {
        "stage": 8682,
        "stage_name": "stage8682_cluster_slice_detector_readiness",
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            "failures": failures,
            "sample_rows": len(sample_rows),
            "sample_metrics": sample_card["metrics"],
            "stage8676_rows": manifest_card["rows"],
            "stage8676_metrics": manifest_card["metrics"],
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "runtime_authorized": False,
            "promotion_ready": False,
            "data_mining_allowed": False,
            "training_allowed": False,
        },
        "artifacts": {
            "detector_module": "scripts/cluster_slice_near_duplicate_detector.py",
            "tests": "tests/test_cluster_slice_near_duplicate_detector.py",
            "sample_card": str((OUT_DIR / "sample_cluster_card.json").relative_to(ROOT)),
            "stage8676_manifest_card": str((OUT_DIR / "stage8676_manifest_cluster_card.json").relative_to(ROOT)),
        },
        "decision": "Recovered cluster_slice_near_duplicate_detector as a deterministic support module. It reports exact/semantic/source/slice/split/near-duplicate structure but does not authorize mining or training.",
        "next_best_step": "Attach Stage8681 and Stage8682 support modules to the central graph, then recover shared locked-eval/source-exclusion and feature-normalizer helper libraries.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "cluster_slice_readiness_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "# Stage8682 Cluster/Slice Detector Readiness\n\n"
        f"Passed: `{card['passed']}`\n\n"
        f"- Sample metrics: `{sample_card['metrics']}`\n"
        f"- Stage8676 metrics: `{manifest_card['metrics']}`\n"
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
                    "min_stage": min([row.get("stage", 8682) for row in rows] + [8682]),
                    "max_stage": 8682,
                    "latest_stage": 8682,
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
