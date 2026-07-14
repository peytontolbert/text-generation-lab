#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10452
NAME = "stage10452_rust_evidence_citation_candidate_atlas"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ATLAS_JSON = OUT_DIR / "rust_evidence_citation_candidate_atlas.json"
ROWS_JSONL = OUT_DIR / "rust_evidence_citation_candidate_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_MANIFESTS = {
    "stage10302_hf_local_support": ROOT / "runs/local/artifacts/stage10302_hf_local_support_execution_request/hf_local_support_manifest.jsonl",
    "stage10305_source_backed_action_support": ROOT / "runs/local/artifacts/stage10305_source_backed_action_support_execution_request/source_backed_action_support_manifest.jsonl",
    "stage10307_source_backed_action_support_plus": ROOT / "runs/local/artifacts/stage10307_source_backed_action_support_plus_execution_request/source_backed_action_support_plus_manifest.jsonl",
    "stage10309_action_taking_reweight": ROOT / "runs/local/artifacts/stage10309_action_taking_reweight_execution_request/action_taking_reweight_manifest.jsonl",
}

STRICT_EXECUTION = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/execution_result.json"
LIVE_TRAIN = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_train.jsonl"

SOURCE_BUNDLE = "stage10126::candle::candle-core::rust"
TARGET_STRICT_ROW = "stage10126::tokenizers::tokenizers::rust::evidence_citation::reviewed_v27_compact"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def main() -> None:
    strict = load_json(STRICT_EXECUTION)
    target_row = None
    for row in strict["bounded_choice_eval"]["strict_eval"]["row_cards"]:
        if row["row_id"] == TARGET_STRICT_ROW:
            target_row = row
            break
    if target_row is None:
        raise RuntimeError("target strict row missing")

    live_train_rows = [
        row for row in load_jsonl(LIVE_TRAIN)
        if str(row.get("source_bundle_id") or "") == SOURCE_BUNDLE and str(row.get("task_type") or "") == "evidence_citation"
    ]

    candidate_rows: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    for source_name, path in SOURCE_MANIFESTS.items():
        for row in load_jsonl(path):
            if str(row.get("source_bundle_id") or "") != SOURCE_BUNDLE:
                continue
            if str(row.get("task_type") or "") != "evidence_citation":
                continue
            candidate = {
                "source_manifest_name": source_name,
                "source_manifest_path": display(path),
                "row_id": str(row.get("row_id") or ""),
                "source_bundle_id": str(row.get("source_bundle_id") or ""),
                "split": str(row.get("split") or ""),
                "decoder_text": str(row.get("decoder_text") or ""),
                "train_support_only": row.get("train_support_only"),
                "strict_eval_eligible": row.get("strict_eval_eligible"),
            }
            candidate_rows.append(candidate)
            source_counts[source_name] = source_counts.get(source_name, 0) + 1

    candidate_rows.sort(key=lambda row: (row["source_manifest_name"], row["row_id"]))
    unique_row_ids = sorted({row["row_id"] for row in candidate_rows})

    atlas = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(candidate_rows),
        "decision": "rust_evidence_citation_disjoint_supply_identified",
        "claim_scope": [
            "Identify existing disjoint Rust evidence-citation train-support supply for the next residual packet.",
            "Anchor the next Rust support packet on candle-core train rows while keeping tokenizers as the live strict residual family.",
        ],
        "target_strict_row": {
            "row_id": TARGET_STRICT_ROW,
            "target": target_row["target_text"],
            "pred": target_row["constrained_choice_top1_label"],
            "full_vocab_top1": target_row["full_vocab_top1_text"],
            "target_rank_full_vocab": target_row["target_rank_full_vocab"],
        },
        "source_bundle": SOURCE_BUNDLE,
        "live_train_rows_from_source_bundle": len(live_train_rows),
        "source_manifest_counts": dict(sorted(source_counts.items())),
        "unique_candidate_row_ids": unique_row_ids,
        "unique_candidate_row_count": len(unique_row_ids),
        "rows_jsonl": display(ROWS_JSONL),
        "required_honesty_gates": [
            "Use candle-core support rows only as train-support; keep tokenizers residual rows strict-only.",
            "Prefer compact-bounded perm rows first; treat action_reweight clones as secondary if they are needed at all.",
            "Any next Rust packet must be audited against the live repaired overlay to ensure it does not degrade unrelated rows.",
        ],
        "next_actions": [
            "Build a Rust-only evidence-citation support packet from candle-core compact-bounded perm rows.",
            "Exclude tokenizers strict rows from train and keep tokenizers as the evaluation target family.",
            "Add option-representation invariance variants for the E vs F confusion before re-running the repaired overlay probe.",
        ],
    }

    write_jsonl(ROWS_JSONL, candidate_rows)
    write_json(ATLAS_JSON, atlas)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": atlas["passed"],
            "unique_candidate_row_count": atlas["unique_candidate_row_count"],
            "source_manifest_counts": atlas["source_manifest_counts"],
            "atlas": display(ATLAS_JSON),
        },
    )
    print(json.dumps(atlas, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
