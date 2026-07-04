from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from artifact_paths import (
    ArtifactPathError,
    arxiv_is_backup_only,
    assert_allowed_storage_path,
    config_path,
    doc_path,
    probe_output_dir,
    stage_artifact_dir,
    stage_summary_path,
)


def test_stage_summary_is_focused_under_runs_summaries() -> None:
    path = stage_summary_path("stage8653_storage_policy")
    assert path == ROOT / "runs" / "summaries" / "stage8653_storage_policy.json"


def test_stage_artifacts_are_focused_under_runs_local_artifacts() -> None:
    path = stage_artifact_dir("stage8653_storage_policy")
    assert path == ROOT / "runs" / "local" / "artifacts" / "stage8653_storage_policy"


def test_probe_outputs_are_focused_under_runs_local_probes() -> None:
    path = probe_output_dir("stage8653_storage_policy")
    assert path == ROOT / "runs" / "local" / "probes" / "stage8653_storage_policy"


def test_config_and_doc_helpers_stay_in_focused_roots() -> None:
    assert config_path("storage", "example.json") == ROOT / "configs" / "storage" / "example.json"
    assert doc_path("example.md") == ROOT / "docs" / "example.md"


def test_rejects_path_traversal_and_unfocused_roots() -> None:
    with pytest.raises(ArtifactPathError):
        stage_artifact_dir("../escape")
    with pytest.raises(ArtifactPathError):
        assert_allowed_storage_path("/arxiv")
    with pytest.raises(ArtifactPathError):
        assert_allowed_storage_path(ROOT)


def test_arxiv_is_backup_only_policy() -> None:
    assert arxiv_is_backup_only() is True
