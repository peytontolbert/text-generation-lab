from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12490_local_model_concept_proposal_queue.py"
OUT = ROOT / "runs/local/artifacts/stage12490_local_model_concept_proposal_queue"
SUMMARY = ROOT / "runs/summaries/stage12490_local_model_concept_proposal_queue.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_stage12490_builds_proposal_only_public_safe_queue() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

    summary = read_json(SUMMARY)
    guardrail = read_json(OUT / "guardrail_scan.json")
    queue = read_jsonl(OUT / "local_model_concept_proposal_queue.jsonl")

    assert summary["decision"] == "concept_proposal_queue_ready_no_training_no_admission_no_proof"
    assert summary["proposal_queue_rows"] == len(queue)
    assert summary["proposal_queue_rows"] > 0
    assert summary["stage12489_gate_count"] == 7
    assert summary["guardrail_scan_passed"] is True
    assert guardrail["scan_passed"] is True
    assert guardrail["raw_leak_count"] == 0
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False
    assert summary["emitted_training_rows"] == 0
    assert summary["admitted_rows"] == 0
    assert summary["external_repair_credit_count"] == 0
    assert summary["proof_grade_repair_rows"] == 0
    assert summary["eligible_for_training_or_admission_rows"] == 0
    assert summary["local_embedding_outputs_available"] is True
    assert summary["generative_local_model_inference_status"] == "pending_safe_unavailable"

    variant_families = {row["concept_variant_family"] for row in queue}
    assert len(variant_families) >= 4
    assert any(row["anti_collapse_train_support_blockers"] for row in queue)
    for row in queue:
        assert row["proposal_lane"] == "concept_proposal_only"
        assert row["proposal_review_status"] == "requires_stage12491_semantic_review_before_train_support"
        assert row["claim_boundary"] == {
            "concept_proposal": True,
            "reviewed_train_support": False,
            "proof_grade_repair": False,
        }
        assert row["training_allowed"] is False
        assert row["admission_allowed"] is False
        assert row["emitted_training_rows"] == 0
        assert row["admitted_rows"] == 0
        assert row["external_repair_credit_count"] == 0
        assert row["eligible_for_training_or_admission"] is False
        assert set(row["anti_collapse_gate_results"]) == {
            "no_observed_action_imitation",
            "candidate_role_entropy",
            "template_similarity_cap",
            "source_family_cap",
            "proof_training_separation",
            "renderer_consistency",
            "local_model_non_authority",
        }
