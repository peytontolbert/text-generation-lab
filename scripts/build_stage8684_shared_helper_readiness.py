#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage8684_shared_helper_readiness"
SUMMARY = ROOT / "runs/summaries/stage8684_shared_helper_readiness.json"
DOC = ROOT / "docs/SHARED_HELPER_READINESS_STAGE8684.md"
MANIFEST = ROOT / "runs/local/artifacts/stage8676_source_backed_symbol_binding_shortcut_repair_manifest/source_backed_symbol_binding_shortcut_repair_manifest.jsonl"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

import sys

sys.path.insert(0, str(ROOT / "scripts"))
from dataset_junk_ood_ranker_v1 import AUTHORITY_CLOSED
from feature_normalizer import load_aliases, normalize_manifest_rows
from source_lineage_guard import evaluate_row_source_lineage, load_source_registry


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    rows = read_jsonl(MANIFEST)
    aliases = load_aliases()
    registry = load_source_registry()
    normalized = normalize_manifest_rows(rows, aliases)
    lineage_results = [evaluate_row_source_lineage(row, registry) for row in rows]
    normalized_feature_hits = sum(1 for row in normalized if row["normalized_features"])
    blocked_lineage = [row for row in lineage_results if not row["train_eligible_lineage"]]
    required_aliases = ["row_id", "split", "semantic_key", "objective_family", "query_kind", "source_file_is_test", "loss_decoder_ce", "authority_runtime"]
    missing_aliases = [alias for alias in required_aliases if alias not in aliases]
    if missing_aliases:
        failures.append("missing_required_aliases:" + ",".join(missing_aliases))
    if normalized_feature_hits != len(rows):
        failures.append("normalized_features_missing_for_rows")
    if blocked_lineage:
        failures.append(f"blocked_lineage_rows:{len(blocked_lineage)}")
    (OUT_DIR / "stage8676_normalized_features.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in normalized))
    (OUT_DIR / "stage8676_source_lineage_guard.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in lineage_results))

    card = {
        "stage": 8684,
        "stage_name": "stage8684_shared_helper_readiness",
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            "failures": failures,
            "alias_count": len(aliases),
            "required_aliases_checked": required_aliases,
            "missing_aliases": missing_aliases,
            "stage8676_rows": len(rows),
            "normalized_feature_hits": normalized_feature_hits,
            "blocked_lineage_rows": len(blocked_lineage),
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "runtime_authorized": False,
            "promotion_ready": False,
            "data_mining_allowed": False,
            "training_allowed": False,
        },
        "artifacts": {
            "feature_normalizer": "scripts/feature_normalizer.py",
            "source_lineage_guard": "scripts/source_lineage_guard.py",
            "tests": "tests/test_feature_normalizer_and_source_guard.py",
            "normalized_features": str((OUT_DIR / "stage8676_normalized_features.jsonl").relative_to(ROOT)),
            "source_lineage_guard": str((OUT_DIR / "stage8676_source_lineage_guard.jsonl").relative_to(ROOT)),
        },
        "decision": "Recovered shared feature normalizer and source-lineage/locked-eval guard as importable helper libraries. They are ready for builder reuse but do not authorize mining or training.",
        "next_best_step": "Attach Stage8684 helpers to the central graph, then rerun the recovered module/submodule readiness audit.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "shared_helper_readiness_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "# Stage8684 Shared Helper Readiness\n\n"
        f"Passed: `{card['passed']}`\n\n"
        f"- Alias count: `{len(aliases)}`\n"
        f"- Stage8676 rows checked: `{len(rows)}`\n"
        f"- Normalized feature hits: `{normalized_feature_hits}`\n"
        f"- Blocked lineage rows: `{len(blocked_lineage)}`\n"
        f"- Failures: `{failures}`\n\n"
        "This is support-module recovery only. Mining, model execution, training, decoder CE, denoise CE, runtime, and promotion remain closed.\n"
    )
    old_rows = []
    if REGISTRY.exists():
        try:
            old_rows = list((json.loads(REGISTRY.read_text()).get("rows") or []))
        except Exception:
            old_rows = []
    rows_out = old_rows + [card]
    REGISTRY.write_text(
        json.dumps(
            {
                "passed": card["passed"],
                "rows": rows_out,
                "metrics": {
                    "min_stage": min([row.get("stage", 8684) for row in rows_out] + [8684]),
                    "max_stage": 8684,
                    "latest_stage": 8684,
                    "latest_stage_name": card["stage_name"],
                    "latest_stage_next_best_step": card["next_best_step"],
                    "registry_rows": len(rows_out),
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
