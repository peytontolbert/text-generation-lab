from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8921_future_probe_artifact_path_policy import (  # noqa: E402
    AUTHORITY_CLOSED,
    audit_artifact_path_policy,
    build_policy,
    negative_mutation_results,
)


def test_artifact_path_policy_accepts_clean_policy() -> None:
    policy = build_policy()
    assert audit_artifact_path_policy(policy, root_exists=False) == []


def test_artifact_path_policy_rejects_negative_mutations() -> None:
    results = negative_mutation_results(build_policy())
    assert results
    assert all(result["rejected"] for result in results.values())


def test_artifact_path_policy_rejects_existing_output_root() -> None:
    failures = audit_artifact_path_policy(build_policy(), root_exists=True)
    assert "allowed_output_root_already_exists" in failures


def test_artifact_path_policy_rejects_checkpoint_allowed() -> None:
    policy = build_policy()
    policy["allowed_write_kinds"].append("checkpoint")
    failures = audit_artifact_path_policy(policy, root_exists=False)
    assert "write_kind_allowed_and_forbidden_overlap" in failures


def test_stage8921_summary_if_present_keeps_authority_closed() -> None:
    summary = ROOT / "runs/summaries/stage8921_future_probe_artifact_path_policy.json"
    if not summary.exists():
        return
    import json
    card = json.loads(summary.read_text(encoding="utf-8"))
    assert card["passed"] is True
    assert card["authority"] == AUTHORITY_CLOSED
    assert card["metrics"]["negative_mutations_rejected"] == card["metrics"]["negative_mutations"]
