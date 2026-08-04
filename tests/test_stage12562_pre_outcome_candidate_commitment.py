from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("stage12562", ROOT / "scripts/build_stage12562_pre_outcome_candidate_commitment.py")
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def ready(candidate="c"):
    return {"candidate_id": candidate, "task_key": ["dataset", "revision", "train", candidate]}


def hashes():
    return {"ready": "1" * 64, "authority": "2" * 64, "task_bindings": "3" * 64,
            "checkout_summary": "4" * 64, "preflight_summary": "5" * 64, "scope_gate": "6" * 64,
            "frontier_decision": "7" * 64, "runtime_bundle": "8" * 64, "runtime_weights": M.EXPECTED_WEIGHTS_SHA256}


def build(rows=None, executed=0, weights=M.EXPECTED_WEIGHTS_SHA256, source_hashes=None):
    return M.build(rows or [ready()], {"executed_count": executed, "level3_count_increment": 0},
                   {"active_scope_clearance": False, "sandbox_progression_allowed": False},
                   {"weights_sha256": weights}, source_hashes or hashes(), created_at_utc="2026-07-21T00:00:00Z")


def test_zero_outcome_commitment_is_valid_but_never_authorizes_execution():
    result = build()
    assert result["pre_outcome_commitment_valid"] is True
    assert result["execution_authorized"] is False


def test_existing_outcome_rejects_commitment():
    assert "replay_outcome_already_present" in build(executed=1)["blocking_reasons"]


def test_duplicate_candidate_rejects_commitment():
    assert build([ready(), ready()])["pre_outcome_commitment_valid"] is False


def test_model_identity_or_source_digest_change_rejects():
    assert build(weights="0" * 64)["pre_outcome_commitment_valid"] is False
    changed = hashes(); changed["runtime_weights"] = "0" * 64
    assert build(source_hashes=changed)["pre_outcome_commitment_valid"] is False


def test_commitment_digest_is_order_stable():
    left = build([ready("b"), ready("a")])
    right = build([ready("a"), ready("b")])
    assert left["commitment_sha256"] == right["commitment_sha256"]
