from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from repository_universe_builder import build_repository_universe, cosine, repo_node


def test_repo_node_has_stable_vector_and_coord() -> None:
    repo = {"repo_id": "r1", "languages": ["python"], "dependencies": ["pytest"], "files": ["tests/test_app.py"]}
    a = repo_node(repo, dim=8)
    b = repo_node(repo, dim=8)
    assert a["repo_vector"] == b["repo_vector"]
    assert len(a["repo_vector"]) == 8
    assert len(a["repo_coord3d"]) == 3
    assert a["promotion_authority"] is False


def test_similar_repos_get_higher_cosine_than_unrelated() -> None:
    py = repo_node({"repo_id": "py", "languages": ["python"], "dependencies": ["pytest"], "files": ["test_auth.py"]}, dim=16)
    py2 = repo_node({"repo_id": "py2", "languages": ["python"], "dependencies": ["pytest"], "files": ["test_db.py"]}, dim=16)
    js = repo_node({"repo_id": "js", "languages": ["javascript"], "dependencies": ["vite"], "files": ["src/app.ts"]}, dim=16)
    assert cosine(py["repo_vector"], py2["repo_vector"]) > cosine(py["repo_vector"], js["repo_vector"])


def test_build_repository_universe_emits_knn_edges() -> None:
    card = build_repository_universe(
        [
            {"repo_id": "a", "languages": ["python"], "dependencies": ["pytest"]},
            {"repo_id": "b", "languages": ["python"], "dependencies": ["pytest"]},
            {"repo_id": "c", "languages": ["rust"], "dependencies": ["tokio"]},
        ],
        dim=16,
        k=1,
    )
    assert card["metrics"]["repo_count"] == 3
    assert card["metrics"]["edge_count"] == 3
    assert card["metrics"]["authority_rows"] == 0
    assert card["metrics"]["raw_source_rows"] == 0
    assert all(edge["edge_type"] == "repo_knn_similar_to" for edge in card["edges"])


def test_universe_manifest_records_vector_dim_and_language_counts() -> None:
    card = build_repository_universe([{"repo_id": "a", "languages": ["python", "python"]}], dim=12, k=2)
    assert card["universe_manifest"]["vector_dim"] == 12
    assert card["universe_manifest"]["repo_count"] == 1
    assert card["metrics"]["language_counts"]["python"] == 2
