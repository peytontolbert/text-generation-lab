from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("stage12560", ROOT / "scripts/build_stage12560_protected_namespace_deny_sidecars.py")
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def candidate(repo="org/repo"):
    return {"task_identity": {"canonical_repo": repo}}


def sealed(repo="repo", root="root-1"):
    return {"repo_id": repo, "stage12105_root_key": root, "prompt_text": "never emit", "target_text": "never emit"}


def locked():
    return {"source_id": "s", "task_pack_id": "p", "lineage_hash": "l", "artifact_hash": "a", "path": "org/repo"}


def test_sidecars_emit_hashes_not_raw_protected_values():
    result = M.build_sidecars([candidate()], [sealed()], [locked()])
    text = str(result)
    assert "never emit" not in text
    assert "root-1" not in text
    assert result["summary"]["raw_prompt_target_evidence_emitted"] is False


def test_exact_repo_label_collision_is_counted_but_never_clears():
    result = M.build_sidecars([candidate("org/repo")], [sealed("org/repo")], [locked()])
    assert result["summary"]["exact_repo_label_overlap_count"] == 1
    assert result["summary"]["protected_clearance"] is False


def test_normalized_basename_collision_is_diagnostic_only():
    result = M.build_sidecars([candidate("org/my-repo")], [sealed("my_repo")], [locked()])
    assert result["summary"]["normalized_basename_collision_count"] == 1
    assert result["summary"]["path_or_filename_repo_inference_used"] is False


def test_dedupe_is_deterministic():
    first = M.build_sidecars([candidate(), candidate()], [sealed(), sealed()], [locked(), locked()])
    second = M.build_sidecars([candidate()], [sealed()], [locked()])
    assert first == second


def test_locked_path_never_becomes_repo_identity():
    result = M.build_sidecars([candidate()], [], [locked()])
    assert result["sidecars"]["locked_namespace"]["canonical_repo_mapping_complete"] is False
    assert result["summary"]["exact_repo_label_overlap_count"] == 0
