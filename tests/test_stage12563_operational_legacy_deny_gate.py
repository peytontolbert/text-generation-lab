from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("stage12563", ROOT / "scripts/build_stage12563_operational_legacy_deny_gate.py")
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def sealed(root):
    return {"stage12105_root_key": root, "prompt_text": "never emit"}


def locked(i):
    return {"source_id": f"s{i}", "lineage_hash": f"l{i}", "artifact_hash": f"a{i}", "train_eligible": False}


def binding(i):
    return {"candidate_id": f"c{i}", "policy_split": "train",
            "task_identity": {"canonical_repo": f"org/repo{i}", "base_commit": f"{i + 1:040x}"[-40:]}}


def commitment(ids):
    payload = {"candidate_ids": ids}
    return {"pre_outcome_commitment_valid": True, "commitment_payload": payload, "commitment_sha256": M.stable_hash(payload)}


def test_unresolved_protected_root_blocks():
    roots = [sealed("unknown-local-root")] + [sealed(f"sourcebot::{i + 1:040x}") for i in range(24)]
    result = M.audit(roots, [locked(i) for i in range(5)], commitment([f"c{i}" for i in range(8)]), [binding(i) for i in range(8)])
    assert result["unresolved_protected_root_count"] == 1
    assert result["legacy_deny_enforced"] is False


def test_synthetic_resolved_roots_cannot_authorize_operational_gate():
    roots = [sealed(f"sourcebot::{i + 1:040x}") for i in range(25)]
    result = M.audit(roots, [locked(i) for i in range(5)], commitment([f"c{i}" for i in range(8)]), [binding(i) for i in range(8)])
    assert result["legacy_deny_enforced"] is False
    assert result["sandbox_progression_allowed"] is False
    assert "operational_ingestion_hooks_unverified" in result["blocking_reasons"]


def test_commitment_mismatch_blocks():
    roots = [sealed(f"sourcebot::{i + 1:040x}") for i in range(25)]
    item = commitment([f"c{i}" for i in range(8)]); item["commitment_sha256"] = "0" * 64
    assert M.audit(roots, [locked(i) for i in range(5)], item, [binding(i) for i in range(8)])["legacy_deny_enforced"] is False


def test_locked_pack_train_eligibility_blocks():
    roots = [sealed(f"sourcebot::{i + 1:040x}") for i in range(25)]
    packs = [locked(i) for i in range(5)]; packs[0]["train_eligible"] = True
    assert M.audit(roots, packs, commitment([f"c{i}" for i in range(8)]), [binding(i) for i in range(8)])["legacy_deny_enforced"] is False


def test_raw_protected_payload_is_not_emitted():
    roots = [sealed("secret-root")]
    result = M.audit(roots, [locked(i) for i in range(5)], commitment([f"c{i}" for i in range(8)]), [binding(i) for i in range(8)])
    assert "never emit" not in str(result)
    assert "secret-root" not in str(result)
