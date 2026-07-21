from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12491_concept_proposal_semantic_review_gate.py"
OUT = ROOT / "runs/local/artifacts/stage12491_concept_proposal_semantic_review_gate"
SUMMARY = ROOT / "runs/summaries/stage12491_concept_proposal_semantic_review_gate.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_stage12491_blocks_aggregate_concepts_and_emits_materialization_requirements() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

    summary = read_json(SUMMARY)
    guardrail = read_json(OUT / "guardrail_scan.json")
    accepted = read_jsonl(OUT / "reviewed_concept_train_support_candidates.jsonl")
    blocked = read_jsonl(OUT / "blocked_concept_proposal_refs.jsonl")
    requirements = read_jsonl(OUT / "root_local_concept_materialization_requirements.jsonl")

    assert summary["decision"] == "review_gate_complete_materialization_required_no_train_support_admitted"
    assert summary["stage12490_proposal_queue_rows"] == len(blocked)
    assert summary["accepted_train_support_candidate_count"] == 0
    assert summary["blocked_proposal_count"] > 0
    assert summary["materialization_requirement_count"] == len(requirements)
    assert summary["materialization_requirement_count"] > 0
    assert accepted == []
    assert guardrail["scan_passed"] is True
    assert guardrail["raw_leak_count"] == 0
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False
    assert summary["training_rows_emitted"] == 0
    assert summary["external_repair_credit_count"] == 0

    for row in blocked:
        assert row["training_allowed"] is False
        assert row["admission_allowed"] is False
        assert row["external_repair_credit_count"] == 0
        assert row["reason_codes"]

    for row in requirements:
        assert row["must_generate_root_local_candidates"] is True
        assert row["must_have_independent_policy_label"] is True
        assert row["must_have_state_delta_review"] is True
        assert row["must_not_use_local_model_label_as_gold"] is True
        assert row["must_not_claim_proof_grade_repair"] is True
        assert row["training_allowed"] is False
        assert row["external_repair_credit_count"] == 0
