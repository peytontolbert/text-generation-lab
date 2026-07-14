#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10454
NAME = "stage10454_rust_citation_only_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "rust_citation_only_support_package.json"
ROWS_JSONL = OUT_DIR / "rust_citation_only_support_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage10302_hf_local_support_execution_request/hf_local_support_manifest.jsonl"
SOURCE_BUNDLE = "stage10126::candle::candle-core::rust"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def normalize(row: dict[str, Any]) -> dict[str, Any]:
    updated = json.loads(json.dumps(row))
    updated["split"] = "train"
    updated["split_role"] = "train_support"
    updated["loss_mask"] = {"decoder_ce": True}
    updated["expected_enabled_loss"] = "decoder_ce"
    updated["disable_losses"] = []
    updated["train_support_only"] = True
    updated["strict_eval_eligible"] = False
    updated["source_heldout_admissible"] = False
    updated["support_package_stage"] = STAGE
    updated["support_provenance"] = {
        "support_package_stage": STAGE,
        "support_package_name": NAME,
        "source_manifest": display(SOURCE_MANIFEST),
        "support_class": "rust_evidence_citation_only_disjoint_candle_core",
    }
    return updated


def main() -> None:
    rows = [
        normalize(row)
        for row in load_jsonl(SOURCE_MANIFEST)
        if str(row.get("source_bundle_id") or "") == SOURCE_BUNDLE
        and str(row.get("language_family") or "") == "rust"
        and str(row.get("task_type") or "") == "evidence_citation"
        and str(row.get("split") or "") == "train"
        and "::action_reweight::" not in str(row.get("row_id") or "")
    ]
    rows.sort(key=lambda row: str(row.get("row_id") or ""))
    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(rows),
        "decision": "rust_citation_only_support_ready",
        "claim_scope": [
            "Provide Rust evidence-citation-only disjoint train support from candle-core.",
            "Keep tokenizers strict residual rows out of train and avoid action_reweight clones in the first-pass packet.",
        ],
        "source_artifacts": {
            "source_manifest": display(SOURCE_MANIFEST),
        },
        "source_bundle_id": SOURCE_BUNDLE,
        "rows": len(rows),
        "decoder_targets": sorted({str(row.get("decoder_text") or "") for row in rows}),
        "row_ids": [str(row.get("row_id") or "") for row in rows],
        "outputs": {
            "package_json": display(PACKAGE_JSON),
            "rows_jsonl": display(ROWS_JSONL),
        },
        "required_honesty_gates": [
            "Rust support package must include evidence_citation rows only.",
            "Tokenizers strict residual rows stay strict-only and are not copied into train.",
            "Action_reweight clones remain excluded from the first-pass support packet.",
        ],
    }
    write_jsonl(ROWS_JSONL, rows)
    write_json(PACKAGE_JSON, package)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": package["passed"],
            "rows": package["rows"],
            "package": display(PACKAGE_JSON),
        },
    )
    print(json.dumps(package, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
