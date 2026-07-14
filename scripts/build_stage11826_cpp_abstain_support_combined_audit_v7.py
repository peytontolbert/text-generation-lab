#!/usr/bin/env python3
"""Combined C/C++ abstain-attractor support audit including whisper.cpp."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11826
NAME = "stage11826_cpp_abstain_support_combined_audit_v7"
OUT = ART / NAME
SUMMARY = OUT / "cpp_abstain_support_combined_audit_v7.json"
COMBINED_ROWS = OUT / "cpp_abstain_support_rows_v7.jsonl"

ROW_SOURCES = [
    ART / "stage11755_cpp_abstain_support_admission_audit/cpp_abstain_support_rows.jsonl",
    ART / "stage11767_cpp_faiss_abstain_support_rows/cpp_faiss_abstain_support_rows.jsonl",
    ART / "stage11783_cpp_pytorch_sample_abstain_support_rows/cpp_pytorch_sample_abstain_support_rows.jsonl",
    ART / "stage11787_cpp_pytorch_mkl_abstain_support_rows/cpp_pytorch_mkl_abstain_support_rows.jsonl",
    ART / "stage11803_cpp_pytorch_xnnpack_abstain_support_rows/cpp_pytorch_xnnpack_abstain_support_rows.jsonl",
    ART / "stage11807_cpp_pytorch_cuda_abstain_support_rows/cpp_pytorch_cuda_abstain_support_rows.jsonl",
    ART / "stage11825_cpp_whisper_utf8_abstain_support_rows/cpp_whisper_utf8_abstain_support_rows.jsonl",
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def failures_for(row: dict[str, Any], seen_row_ids: set[str]) -> list[str]:
    failures: list[str] = []
    anti = row.get("anti_cheat") or {}
    options = row.get("opaque_options") or []
    row_id = str(row.get("row_id") or "")
    root_id = str(row.get("root_id") or "")
    repo_family = str(row.get("repo_family") or "")
    if row_id in seen_row_ids:
        failures.append("duplicate_row_id")
    if row.get("language_family") != "c_cpp":
        failures.append("not_c_cpp")
    if row.get("split") != "train" or row.get("package_split") != "train":
        failures.append("not_train_split")
    if not row.get("train_support_only"):
        failures.append("not_train_support_only")
    if row.get("strict_eval_eligible"):
        failures.append("strict_eval_eligible_true")
    if row.get("source_heldout_admissible"):
        failures.append("source_heldout_admissible_true")
    if len(options) < 2:
        failures.append("singleton_or_missing_options")
    if row.get("target_label") not in {opt.get("label") for opt in options}:
        failures.append("target_label_not_in_options")
    if not row.get("evidence_ledger"):
        failures.append("missing_evidence_ledger")
    for key in [
        "deterministic_option_shuffle",
        "opaque_labels",
        "target_label_not_visible_before_options",
        "target_value_not_visible_before_options",
        "source_backed_snippets",
        "paired_answerable_and_abstain_variants",
    ]:
        if not anti.get(key):
            failures.append(f"anti_cheat_missing_{key}")
    if row.get("verifier_anchor") and not row.get("verifier_evidence"):
        failures.append("verifier_anchor_without_verifier_evidence")
    if "sentencepiece" in root_id or "sentencepiece" in repo_family:
        failures.append("sentencepiece_strict_root_overlap")
    return failures


def main() -> None:
    rows: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    for source in ROW_SOURCES:
        source_rows = read_jsonl(source)
        rows.extend(source_rows)
        source_counts[rel(source)] = len(source_rows)

    admitted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    audited: list[dict[str, Any]] = []
    seen_row_ids: set[str] = set()
    for row in rows:
        failures = failures_for(row, seen_row_ids)
        seen_row_ids.add(str(row.get("row_id") or ""))
        record = {
            "row_id": row.get("row_id"),
            "root_id": row.get("root_id"),
            "repo_family": row.get("repo_family"),
            "task_type": row.get("task_type"),
            "admitted": not failures,
            "failures": failures,
        }
        audited.append(record)
        if failures:
            blocked.append(record)
        else:
            admitted.append(row)

    roots = sorted({row.get("root_id") for row in admitted})
    families = sorted({row.get("repo_family") for row in admitted})
    write_jsonl(COMBINED_ROWS, admitted)
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": len(blocked) == 0 and len(admitted) > 0,
        "decision": "cpp_abstain_support_rows_admitted_but_quota_incomplete",
        "source_counts": source_counts,
        "row_count": len(rows),
        "admitted_rows": len(admitted),
        "blocked_rows": len(blocked),
        "admitted_root_count": len(roots),
        "admitted_roots": roots,
        "admitted_repo_families": families,
        "quota_status": {
            "support_roots_ready": len(roots),
            "support_roots_remaining": max(0, 16 - len(roots)),
            "strict_analogue_roots_ready": 0,
            "strict_analogue_roots_remaining": 4,
        },
        "audited_rows": audited,
        "claim_boundary": [
            "Rows are train-support-only for C/C++ abstain-attractor repair.",
            "The Stage11742 C/C++ quota remains incomplete.",
        ],
        "outputs": {"summary": rel(SUMMARY), "combined_rows": rel(COMBINED_ROWS)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": artifact["decision"],
                "admitted_rows": artifact["admitted_rows"],
                "admitted_root_count": artifact["admitted_root_count"],
                "support_roots_remaining": artifact["quota_status"]["support_roots_remaining"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
