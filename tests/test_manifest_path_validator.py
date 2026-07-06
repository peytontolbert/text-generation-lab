from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.manifest_path_validator import allowed_manifest_roots, validate_manifest_input_path  # noqa: E402


def test_accepts_existing_explicit_manifest_under_allowed_repo_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    manifest = repo / "runs" / "local" / "manifests" / "rows.jsonl"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"row_id":"r1"}\n', encoding="utf-8")

    card = validate_manifest_input_path("runs/local/manifests/rows.jsonl", repo_root=repo, must_exist=True)
    assert card["allowed"] is True
    assert card["root_label"] == "runs/local/manifests"
    assert card["data_mining_authorized"] is False
    assert card["training_authorized"] is False


def test_accepts_future_explicit_manifest_when_existence_not_required(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    card = validate_manifest_input_path("datasets/recovered/future.jsonl", repo_root=repo, must_exist=False)
    assert card["allowed"] is True
    assert card["exists"] is False
    assert card["root_label"] == "datasets/recovered"


def test_allowed_roots_are_focused_manifest_roots(tmp_path: Path) -> None:
    roots = allowed_manifest_roots(tmp_path / "repo")
    assert set(roots) == {"runs/local/artifacts", "runs/local/recovered", "runs/local/manifests", "datasets/recovered"}


def test_rejects_backup_and_unfocused_absolute_roots(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    arxiv = validate_manifest_input_path("/arxiv/datasets/rows.jsonl", repo_root=repo, must_exist=False)
    data = validate_manifest_input_path("/data/rows.jsonl", repo_root=repo, must_exist=False)
    assert "manifest_path_under_arxiv_forbidden" in arxiv["failures"]
    assert "manifest_path_under_data_outside_repo_forbidden" in data["failures"]
    assert arxiv["allowed"] is False
    assert data["allowed"] is False


def test_rejects_globs_traversal_remote_uri_and_wrong_suffix(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    globbed = validate_manifest_input_path("runs/local/manifests/*.jsonl", repo_root=repo, must_exist=False)
    traversal = validate_manifest_input_path("runs/local/manifests/../rows.jsonl", repo_root=repo, must_exist=False)
    remote = validate_manifest_input_path("https://example.com/rows.jsonl", repo_root=repo, must_exist=False)
    wrong_suffix = validate_manifest_input_path("runs/local/manifests/rows.txt", repo_root=repo, must_exist=False)
    assert "glob_manifest_path_forbidden" in globbed["failures"]
    assert "path_traversal_forbidden" in traversal["failures"]
    assert "remote_manifest_uri_forbidden" in remote["failures"]
    assert "manifest_must_be_jsonl" in wrong_suffix["failures"]
    assert all(card["allowed"] is False for card in [globbed, traversal, remote, wrong_suffix])


def test_rejects_directories_and_missing_required_manifest(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    manifest_dir = repo / "runs" / "local" / "manifests"
    manifest_dir.mkdir(parents=True)

    directory = validate_manifest_input_path("runs/local/manifests", repo_root=repo, must_exist=True)
    missing = validate_manifest_input_path("runs/local/manifests/missing.jsonl", repo_root=repo, must_exist=True)
    assert "manifest_path_is_directory" in directory["failures"]
    assert "manifest_must_be_jsonl" in directory["failures"]
    assert "manifest_path_missing" in missing["failures"]
    assert directory["allowed"] is False
    assert missing["allowed"] is False
