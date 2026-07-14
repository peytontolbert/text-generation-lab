#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10712
NAME = "stage10712_multilingual_residual_contrast_supply_manifest"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "multilingual_residual_contrast_supply_manifest.json"
PYTHON_ROWS_JSONL = OUT_DIR / "python_verifier_contrast_rows.jsonl"
RUST_ROWS_JSONL = OUT_DIR / "rust_evidence_contrast_rows.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

ARTIFACT_ROOT = ROOT / "runs/local/artifacts"
SCAN_PATHS = [
    ARTIFACT_ROOT / "stage10709_rewritten_plus_reviewed_training_package_execution_repaired",
    ARTIFACT_ROOT / "stage10708_rewritten_support_execution_contract_repair",
    ARTIFACT_ROOT / "stage10704_rewritten_multilingual_support_package",
    ARTIFACT_ROOT / "stage10703_rewritten_multilingual_root_admission_trial",
    ARTIFACT_ROOT / "stage10702_leak_rewrite_interface_builder",
    ARTIFACT_ROOT / "stage10646_reviewed_v28_candidate_same_manifest_comparison",
    ARTIFACT_ROOT / "stage10420_reviewed_multilingual_v27_manifest_package",
    ARTIFACT_ROOT / "stage10144_v27_standalone_bounded_maintainer_bundle_package",
]


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


def python_verifier_class(row: dict[str, Any]) -> str:
    target = str(row.get("target_text") or row.get("gold_option_label") or "")
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    if target == "A" or "PASS_TARGETED_TEST_SELECTION" in target or "PASS_TRACE_VERIFICATION_TARGETS" in target:
        return "pass"
    if target == "B" or "FAIL_TARGETED_TEST_SELECTION" in target or "FAIL_TRACE_VERIFICATION_TARGETS" in target:
        return "fail"
    if target == "C" or "RETRIEVE_MORE" in target:
        return "retrieve_more"
    if target == "D" or "ABSTAIN_INSUFFICIENT_EVIDENCE" in target:
        return "abstain"
    if "FAIL_TARGETED_TEST_SELECTION" in prompt or "FAIL_TRACE_VERIFICATION_TARGETS" in prompt:
        return "fail_candidate_present"
    return "other"


def rust_evidence_class(row: dict[str, Any]) -> str:
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    target = str(row.get("target_text") or row.get("gold_option_label") or "")
    option_labels = list(row.get("option_labels") or [])
    option_values = list(row.get("option_values") or [])
    label_to_value = {label: value for label, value in zip(option_labels, option_values)}
    if target in label_to_value:
        return str(label_to_value[target])
    if "symptom_or_call_path_analogue" in prompt and target in {"C", "E"}:
        return "symptom_or_call_path_analogue"
    if "verifier_and_test_constraint" in prompt and target in {"D", "F"}:
        return "verifier_and_test_constraint"
    if "candidate_change_surface" in prompt and target in {"A", "B"}:
        return "candidate_change_surface"
    return target


def row_meta(path: Path, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_path": display(path),
        "row_id": row.get("row_id"),
        "repo_family": row.get("repo_family"),
        "package_source_kind": row.get("package_source_kind"),
        "split": row.get("split") or row.get("package_split"),
        "target_text": row.get("target_text") or row.get("gold_option_label"),
        "prompt_text": row.get("prompt_text") or row.get("input_text"),
    }


def main() -> None:
    python_rows: list[dict[str, Any]] = []
    rust_rows: list[dict[str, Any]] = []

    for scan_root in SCAN_PATHS:
        if not scan_root.exists():
            continue
        for path in scan_root.rglob("*.jsonl"):
            try:
                rows = load_jsonl(path)
            except Exception:
                continue
            for row in rows:
                language = str(row.get("language_family") or "")
                subtype = str(row.get("target_subtype") or row.get("task_type") or "")
                if language == "python" and subtype == "verifier_outcome":
                    klass = python_verifier_class(row)
                    if klass in {"fail", "retrieve_more", "abstain"}:
                        meta = row_meta(path, row)
                        meta["verifier_class"] = klass
                        python_rows.append(meta)
                if language == "rust" and subtype == "evidence_citation":
                    klass = rust_evidence_class(row)
                    if klass in {"symptom_or_call_path_analogue", "verifier_and_test_constraint"}:
                        meta = row_meta(path, row)
                        meta["semantic_target"] = klass
                        rust_rows.append(meta)

    python_rows.sort(key=lambda row: (str(row.get("verifier_class") or ""), str(row.get("repo_family") or ""), str(row.get("row_id") or "")))
    rust_rows.sort(key=lambda row: (str(row.get("semantic_target") or ""), str(row.get("repo_family") or ""), str(row.get("row_id") or "")))

    write_jsonl(PYTHON_ROWS_JSONL, python_rows)
    write_jsonl(RUST_ROWS_JSONL, rust_rows)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "residual_contrast_supply_manifest_ready",
        "claim_scope": [
            "Enumerate the currently materialized contrast supply for the two remaining multilingual residuals.",
            "Treat Python verifier contrast rows and Rust evidence-citation contrast rows as separate inventories.",
            "Use this manifest as a hard gate before another promotable probe request is built.",
        ],
        "scan_paths": [display(path) for path in SCAN_PATHS if path.exists()],
        "python_verifier_contrast_supply": {
            "rows": len(python_rows),
            "verifier_class_counts": dict(sorted(Counter(str(row.get("verifier_class") or "") for row in python_rows).items())),
            "repo_family_counts": dict(sorted(Counter(str(row.get("repo_family") or "") for row in python_rows).items())),
            "promotable_contrast_present": len(python_rows) > 0,
            "rows_jsonl": display(PYTHON_ROWS_JSONL),
        },
        "rust_evidence_contrast_supply": {
            "rows": len(rust_rows),
            "semantic_target_counts": dict(sorted(Counter(str(row.get("semantic_target") or "") for row in rust_rows).items())),
            "repo_family_counts": dict(sorted(Counter(str(row.get("repo_family") or "") for row in rust_rows).items())),
            "non_tokenizers_contrast_present": any(str(row.get("repo_family") or "") != "tokenizers" for row in rust_rows),
            "rows_jsonl": display(RUST_ROWS_JSONL),
        },
        "headline_findings": [
            "Python promotable contrast supply should be non-empty before another verifier-targeted promotion probe is considered.",
            "Rust evidence-citation contrast supply should include non-tokenizers rows with symptom-or-verifier evidence targets before another citation-targeted promotion probe is considered.",
            "If Python supply remains empty here, the next work item is dataset creation or adjudication, not another training sweep.",
        ],
        "recommended_next_stage": "stage10713_python_rust_residual_contrast_builder_or_quarantine_gate",
        "outputs": {
            "summary_json": display(SUMMARY_JSON),
            "python_rows": display(PYTHON_ROWS_JSONL),
            "rust_rows": display(RUST_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "summary_json": display(SUMMARY_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
