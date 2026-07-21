from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12493_root_local_concept_source_adapter.py"
OUT = ROOT / "runs/local/artifacts/stage12493_root_local_concept_source_adapter"
SUMMARY = ROOT / "runs/summaries/stage12493_root_local_concept_source_adapter.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_stage12493_emits_balanced_source_candidates_without_admission() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

    summary = read_json(SUMMARY)
    guardrail = read_json(OUT / "guardrail_scan.json")
    records = read_jsonl(OUT / "root_local_source_candidate_records.jsonl")
    coverage = read_jsonl(OUT / "work_item_source_coverage.jsonl")

    assert summary["decision"] == "root_local_source_candidates_ready_training_blocked"
    assert summary["source_candidate_count"] == len(records) == 56
    assert summary["work_item_coverage_count"] == len(coverage) == 7
    assert summary["work_items_with_full_target_root_count"] == 7
    assert summary["language_counts"] == {
        "c_cpp": 14,
        "python": 14,
        "rust": 14,
        "web_js_ts_html": 14,
    }
    assert summary["max_source_family_share"] <= 0.15
    assert guardrail["scan_passed"] is True
    assert summary["raw_leak_count"] == guardrail["raw_leak_count"] == 0
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False
    assert summary["external_repair_credit_count"] == 0

    required_stages = {
        "stage12205_authoritative_verifier_log_level3_joiner",
        "stage12320_event_local_semantic_review_admission",
        "stage12416_direct_verifier_log_train_support_canonicalizer",
        "stage12417_combined_train_support_ledger_v16",
    }
    assert required_stages.issubset(summary["source_stage_counts"])

    for row in records:
        assert row["training_allowed"] is False
        assert row["admission_allowed"] is False
        assert row["external_repair_credit_count"] == 0
        assert row["claim_boundary"] == {
            "source_adapter_candidate": True,
            "reviewed_train_support": False,
            "proof_grade_repair": False,
        }
        assert row["unresolved_required_fields"]
        assert "independent_policy_label_hash" in row["unresolved_required_fields"]
        assert row["language_family"] in {"python", "rust", "c_cpp", "web_js_ts_html"}

    assert max(Counter(row["source_family_hash"] for row in records).values()) <= 8
