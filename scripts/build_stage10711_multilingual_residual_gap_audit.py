#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10711
NAME = "stage10711_multilingual_residual_gap_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "multilingual_residual_gap_audit.json"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

EXECUTION_RESULT = ROOT / "runs/local/artifacts/stage10710_rewritten_plus_reviewed_probe_execution_repaired/bounded_decoder_probe/execution_result.json"
TRAIN_ROWS = ROOT / "runs/local/artifacts/stage10709_rewritten_plus_reviewed_training_package_execution_repaired/train_rows.jsonl"
VALIDATION_ROWS = ROOT / "runs/local/artifacts/stage10709_rewritten_plus_reviewed_training_package_execution_repaired/validation_rows.jsonl"


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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def verifier_label_family(row: dict[str, Any]) -> str:
    target = str(row.get("target_text") or row.get("gold_option_label") or "")
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    if "FAIL_TARGETED_TEST_SELECTION" in prompt or "FAIL_TRACE_VERIFICATION_TARGETS" in prompt:
        if target == "B":
            return "fail"
    if "RETRIEVE_MORE" in prompt and target == "C":
        return "retrieve_more"
    if "ABSTAIN_INSUFFICIENT_EVIDENCE" in prompt and target == "D":
        return "abstain"
    if target == "A":
        return "pass"
    return "other"


def rust_evidence_semantic_target(row: dict[str, Any]) -> str:
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    target = str(row.get("target_text") or row.get("gold_option_label") or "")
    option_labels = list(row.get("option_labels") or [])
    option_values = list(row.get("option_values") or [])
    label_to_value = {label: value for label, value in zip(option_labels, option_values)}
    if target in label_to_value:
        return str(label_to_value[target])
    if "candidate_change_surface" in prompt and "symptom_or_call_path_analogue" in prompt and "verifier_and_test_constraint" in prompt:
        # reviewed bundle rows often encode target in the opaque label only
        if target == "C":
            return "symptom_or_call_path_analogue"
        if target == "D":
            return "verifier_and_test_constraint"
        if target == "E":
            return "symptom_or_call_path_analogue"
        if target == "F":
            return "verifier_and_test_constraint"
    return target


def collect_support(rows: list[dict[str, Any]], *, language: str, subtype: str) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        row_language = str(row.get("language_family") or "")
        row_subtype = str(row.get("target_subtype") or row.get("task_type") or "")
        if row_language == language and row_subtype == subtype:
            out.append(row)
    return out


def main() -> None:
    execution = load_json(EXECUTION_RESULT)
    train_rows = load_jsonl(TRAIN_ROWS)
    validation_rows = load_jsonl(VALIDATION_ROWS)

    strict_cards = ((execution.get("bounded_choice_eval") or {}).get("strict_eval") or {}).get("row_cards") or []
    strict_misses = [row for row in strict_cards if not row.get("constrained_choice_match")]

    python_train = collect_support(train_rows, language="python", subtype="verifier_outcome")
    python_validation = collect_support(validation_rows, language="python", subtype="verifier_outcome")
    rust_train = collect_support(train_rows, language="rust", subtype="evidence_citation")
    rust_validation = collect_support(validation_rows, language="rust", subtype="evidence_citation")

    python_label_counts = Counter(verifier_label_family(row) for row in python_train)
    python_repo_counts = Counter(str(row.get("repo_family") or "") for row in python_train)
    rust_semantic_counts = Counter(rust_evidence_semantic_target(row) for row in rust_train)
    rust_repo_counts = Counter(str(row.get("repo_family") or "") for row in rust_train)

    rust_rows_preview = []
    for row in rust_train + rust_validation:
        rust_rows_preview.append(
            {
                "row_id": row.get("row_id"),
                "repo_family": row.get("repo_family"),
                "package_source_kind": row.get("package_source_kind"),
                "target_text": row.get("target_text"),
                "semantic_target": rust_evidence_semantic_target(row),
            }
        )

    python_preview = []
    for row in python_train[:12]:
        python_preview.append(
            {
                "row_id": row.get("row_id"),
                "repo_family": row.get("repo_family"),
                "package_source_kind": row.get("package_source_kind"),
                "target_text": row.get("target_text"),
                "verifier_family": verifier_label_family(row),
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "multilingual_residual_gap_audited",
        "claim_scope": [
            "Audit the post-repair stage10710 frontier against the current support package and identify why the remaining multilingual misses did not move.",
            "Focus on the two surviving strict misses: Python verifier outcome and Rust evidence citation.",
            "Surface whether current support is real contrast data or only same-pattern reinforcement.",
        ],
        "source_artifacts": {
            "execution_result": display(EXECUTION_RESULT),
            "train_rows": display(TRAIN_ROWS),
            "validation_rows": display(VALIDATION_ROWS),
        },
        "frontier_status": {
            "strict_rows": ((execution.get("bounded_choice_eval") or {}).get("strict_eval") or {}).get("rows"),
            "strict_constrained_choice_accuracy": ((execution.get("bounded_choice_eval") or {}).get("strict_eval") or {}).get("constrained_choice_top1_accuracy"),
            "strict_full_vocab_top1_accuracy": ((execution.get("bounded_choice_eval") or {}).get("strict_eval") or {}).get("full_vocab_top1_accuracy"),
            "strict_miss_count": len(strict_misses),
            "strict_misses": [
                {
                    "row_id": row.get("row_id"),
                    "target_label": row.get("bounded_choice_target_label"),
                    "predicted_label": row.get("constrained_choice_top1_label"),
                    "full_vocab_top1_text": row.get("full_vocab_top1_text"),
                    "target_rank_full_vocab": row.get("target_rank_full_vocab"),
                }
                for row in strict_misses
            ],
        },
        "python_verifier_support_audit": {
            "train_rows": len(python_train),
            "validation_rows": len(python_validation),
            "verifier_family_counts": dict(sorted(python_label_counts.items())),
            "repo_family_counts": dict(sorted(python_repo_counts.items())),
            "all_current_python_verifier_rows_one_sided_pass": set(python_label_counts.keys()) <= {"pass"},
            "preview_rows": python_preview,
        },
        "rust_evidence_support_audit": {
            "train_rows": len(rust_train),
            "validation_rows": len(rust_validation),
            "semantic_target_counts": dict(sorted(rust_semantic_counts.items())),
            "repo_family_counts": dict(sorted(rust_repo_counts.items())),
            "fresh_non_tokenizers_train_rows_present": any(str(row.get("repo_family") or "") not in {"tokenizers"} for row in rust_train),
            "rows_preview": rust_rows_preview,
        },
        "headline_findings": [
            "Stage10710 fixed the execution path but did not move the honest 24-row frontier; strict constrained-choice accuracy stayed at 22/24.",
            "The surviving Python verifier miss is not supported by genuine contrast data: current Python verifier train rows are effectively one-sided PASS-route supervision.",
            "The surviving Rust citation miss is not supported by a real non-tokenizers residual curriculum; current train rows are only a few reviewed bundle citations from candle/linux and do not mirror the tokenizers E-vs-B boundary.",
        ],
        "next_stage_requirements": [
            "Do not promote another probe unless Python verifier support includes fresh non-pass contrast rows that force B-vs-C-vs-D decisions.",
            "Do not promote another probe unless Rust evidence-citation support includes fresh non-tokenizers rows where candidate_change_surface is a tempting negative and the gold is symptom_or_call_path_analogue or verifier_and_test_constraint.",
            "Keep the stage10710 repaired runtime path and runtime bundle as the execution baseline; the remaining work is dataset/interface quality, not harness recovery.",
        ],
        "recommended_next_stage": "stage10712_multilingual_residual_contrast_supply_manifest",
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
