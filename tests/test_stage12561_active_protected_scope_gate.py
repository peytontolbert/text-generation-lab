from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("stage12561", ROOT / "scripts/build_stage12561_active_protected_scope_gate.py")
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def binding(candidate="c", repo="org/train", instance="org__train-1", commit="a" * 40, split="train"):
    return {"candidate_id": candidate, "policy_split": split,
            "task_identity": {"canonical_repo": repo, "instance_id": instance, "base_commit": commit}}


def ready(candidate="c"):
    return {"candidate_id": candidate}


def protected(repo="org/eval", instance="org__eval-1", commit="b" * 40):
    return {"repo": repo, "instance_id": instance, "base_commit": commit}


def test_disjoint_scope_is_diagnostic_only_without_external_gates():
    result = M.evaluate([ready()], [binding()], [protected()])
    assert result["diagnostic_active_scope_disjoint"] is True
    assert result["active_scope_clearance"] is False


def test_disjoint_scope_clears_only_with_legacy_and_commitment_gates():
    result = M.evaluate([ready()], [binding()], [protected()], legacy_deny_enforced=True, selection_committed_pre_outcome=True)
    assert result["active_scope_clearance"] is True


def test_exact_task_overlap_blocks():
    item = protected("org/train", "org__train-1", "a" * 40)
    result = M.evaluate([ready()], [binding()], [item])
    assert result["exact_task_overlap_count"] == 1
    assert result["active_scope_clearance"] is False


def test_same_repo_different_task_blocks():
    result = M.evaluate([ready()], [binding()], [protected("org/train", "other", "b" * 40)])
    assert result["exact_task_overlap_count"] == 0
    assert result["canonical_repo_overlap_count"] == 1
    assert result["active_scope_clearance"] is False


def test_nontrain_or_malformed_ready_binding_blocks():
    assert M.evaluate([ready()], [binding(split="sealed_eval")], [protected()])["active_scope_clearance"] is False
    assert M.evaluate([ready()], [binding(repo="not-canonical")], [protected()])["active_scope_clearance"] is False


def test_unselected_training_bindings_do_not_enter_candidate_scope():
    bindings = [binding(), binding("unused", "org/eval", "x", "b" * 40, "train")]
    result = M.evaluate([ready()], bindings, [protected("org/eval", "y", "c" * 40)])
    assert result["train_identity_count"] == 1
    assert result["diagnostic_active_scope_disjoint"] is True
    assert result["active_scope_clearance"] is False


def test_duplicate_binding_and_malformed_protected_identity_block():
    result = M.evaluate([ready()], [binding(), binding()], [{"repo": "org/eval", "instance_id": "x", "base_commit": "bad"}],
                        legacy_deny_enforced=True, selection_committed_pre_outcome=True)
    assert result["duplicate_binding_id_count"] == 1
    assert result["malformed_protected_identity_count"] == 1
    assert result["active_scope_clearance"] is False
