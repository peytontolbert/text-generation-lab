#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10434
NAME = "stage10434_reviewed_v27_strict_leak_repair_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "reviewed_v27_strict_leak_repair_request.json"
TARGETS_JSONL = OUT_DIR / "reviewed_v27_strict_leak_repair_targets.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

LEAK_QUEUE_JSONL = ROOT / "runs/local/artifacts/stage10432_reviewed_v27_strict_leak_cleanup_queue/reviewed_v27_strict_leak_cleanup_rows.jsonl"
STRICT_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_strict_eval.jsonl"
SCALING_ATLAS_JSON = ROOT / "runs/local/artifacts/stage10417_multilingual_reviewed_scaling_atlas/multilingual_reviewed_scaling_atlas.json"
POST_REVALIDATION_ARTIFACTS = [
    ROOT / "runs/local/artifacts/stage10429_reviewed_v27_eval_hacking_audit/reviewed_v27_eval_hacking_audit.json",
    ROOT / "runs/local/artifacts/stage10431_reviewed_v27_saved_runtime_margin_audit/reviewed_v27_saved_runtime_margin_audit.json",
]


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
    leak_rows = load_jsonl(LEAK_QUEUE_JSONL)
    strict_rows = {row["row_id"]: row for row in load_jsonl(STRICT_ROWS_JSONL)}
    atlas = load_json(SCALING_ATLAS_JSON)
    packet_by_bundle = {
        row["bundle_id"]: row
        for row in atlas.get("admitted_bundle_rows") or []
        if isinstance(row, dict) and row.get("bundle_id")
    }

    targets: list[dict[str, Any]] = []
    for leak in leak_rows:
        strict_row = strict_rows[leak["row_id"]]
        bundle_id = str(strict_row.get("source_bundle_id") or "")
        packet = packet_by_bundle[bundle_id]
        projection = strict_row.get("standalone_projection_source") or {}
        targets.append(
            {
                "row_id": leak["row_id"],
                "bundle_id": bundle_id,
                "packet_dir": packet.get("packet_dir"),
                "language_family": leak["language_family"],
                "repo_family": leak["repo_family"],
                "task_type": leak["task_type"],
                "target_label": leak["target_label"],
                "target_semantic_value": leak["target_semantic_value"],
                "predicted_label": leak["predicted_label"],
                "predicted_semantic_value": leak["predicted_semantic_value"],
                "margin_top1_minus_top2": leak["margin_top1_minus_top2"],
                "selected_tests": packet.get("selected_tests") or [],
                "visible_evidence_keys": packet.get("visible_evidence_keys") or [],
                "standalone_projection_mode": projection.get("projection_mode"),
                "perspective_gold_adjudication": projection.get("perspective_gold_adjudication"),
                "repair_instruction": (
                    "Rewrite the visible evidence so the gold semantic target is no longer stated verbatim before options, while preserving the same gold answer and maintainer answerability."
                ),
                "allowed_repair_mechanisms": [
                    "replace value-bearing evidence line with a causal paraphrase",
                    "swap in a different visible support fact from the same reviewed packet",
                    "compress or summarize the evidence without naming the gold semantic target",
                ],
                "disallowed_repair_mechanisms": [
                    "change the split assignment",
                    "change the gold answer",
                    "replace the row with a different root",
                    "mask the answer with placeholders that make the row unanswerable",
                ],
                "must_preserve": [
                    "same source bundle and reviewed packet lineage",
                    "same task type and language family",
                    "same strict_eval status",
                    "same root-level claim boundary",
                ],
            }
        )

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "request_scope": [
            "Repair the 4 leaked strict evidence-citation rows in the reviewed v2.7 package.",
            "Preserve root identity, gold answer, and strict split status.",
            "Eliminate prompt-visible target leakage before the options block.",
        ],
        "source_artifacts": {
            "leak_cleanup_queue": display(LEAK_QUEUE_JSONL),
            "strict_manifest": display(STRICT_ROWS_JSONL),
            "reviewed_scaling_atlas": display(SCALING_ATLAS_JSON),
        },
        "targets": targets,
        "post_repair_required_revalidation": [
            "rebuild the strict packaged rows",
            "rerun stage10429-style eval-hacking audit and confirm strict leak rows drop to zero",
            "rerun stage10431-style saved-runtime margin audit and confirm no new semantic collapse is introduced",
            "keep stress rows excluded and keep root splits unchanged",
        ],
        "post_repair_reference_artifacts": [display(path) for path in POST_REVALIDATION_ARTIFACTS],
        "success_condition": {
            "strict_leak_rows_after_repair": 0,
            "gold_answers_changed": 0,
            "strict_split_membership_changed": 0,
        },
        "outputs": {
            "request_json": display(REQUEST_JSON),
            "repair_targets": display(TARGETS_JSONL),
        },
    }

    write_json(REQUEST_JSON, request)
    write_jsonl(TARGETS_JSONL, targets)
    write_json(SUMMARY, request)
    print(json.dumps(request, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
