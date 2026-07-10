from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from select_ranked_commit_seed_batch import select_ranked_commit_seed_batch  # noqa: E402


def test_select_ranked_commit_seed_batch_enforces_one_per_repo_and_targeted_tests(tmp_path: Path) -> None:
    ranked = tmp_path / "ranked.jsonl"
    ranked.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "seed_id": "s1",
                        "repo_id": "repo_alpha",
                        "rank_metadata": {
                            "discoverability_route": "PASS_TARGETED_TEST_SELECTION",
                            "discoverability_score": 30.0,
                            "has_direct_test_touch": True,
                        },
                    }
                ),
                json.dumps(
                    {
                        "seed_id": "s2",
                        "repo_id": "repo_alpha",
                        "rank_metadata": {
                            "discoverability_route": "PASS_TARGETED_TEST_SELECTION",
                            "discoverability_score": 29.0,
                            "has_direct_test_touch": True,
                        },
                    }
                ),
                json.dumps(
                    {
                        "seed_id": "s3",
                        "repo_id": "repo_beta",
                        "rank_metadata": {
                            "discoverability_route": "NEEDS_BROAD_TEST_DISCOVERY",
                            "discoverability_score": 50.0,
                            "has_direct_test_touch": True,
                        },
                    }
                ),
                json.dumps(
                    {
                        "seed_id": "s4",
                        "repo_id": "repo_gamma",
                        "rank_metadata": {
                            "discoverability_route": "PASS_TARGETED_TEST_SELECTION",
                            "discoverability_score": 28.0,
                            "has_direct_test_touch": False,
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows, summary = select_ranked_commit_seed_batch(
        ranked_seeds_path=ranked,
        max_seeds=10,
        one_per_repo=True,
        require_targeted_tests=True,
        require_direct_test_touch=False,
    )

    assert [row["seed_id"] for row in rows] == ["s1", "s4"]
    assert summary["selected_seed_count"] == 2
    assert summary["route_counts"]["SKIP_DUPLICATE_REPO"] == 1
    assert summary["route_counts"]["SKIP_ROUTE_NEEDS_BROAD_TEST_DISCOVERY"] == 1



def test_select_ranked_commit_seed_batch_supports_unseen_broad_discovery_and_seen_cap(tmp_path: Path) -> None:
    ranked = tmp_path / "ranked.jsonl"
    ranked.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "seed_id": "seen_1",
                        "repo_id": "repo_seen_alpha",
                        "rank_metadata": {
                            "discoverability_route": "PASS_TARGETED_TEST_SELECTION",
                            "discoverability_score": 90.0,
                            "has_direct_test_touch": True,
                            "corpus_novelty": {"repo_seen_before": True},
                        },
                    }
                ),
                json.dumps(
                    {
                        "seed_id": "seen_2",
                        "repo_id": "repo_seen_beta",
                        "rank_metadata": {
                            "discoverability_route": "PASS_TARGETED_TEST_SELECTION",
                            "discoverability_score": 85.0,
                            "has_direct_test_touch": True,
                            "corpus_novelty": {"repo_seen_before": True},
                        },
                    }
                ),
                json.dumps(
                    {
                        "seed_id": "unseen_broad",
                        "repo_id": "repo_unseen_gamma",
                        "rank_metadata": {
                            "discoverability_route": "NEEDS_BROAD_TEST_DISCOVERY",
                            "discoverability_score": 40.0,
                            "has_direct_test_touch": False,
                            "corpus_novelty": {"repo_seen_before": False},
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows, summary = select_ranked_commit_seed_batch(
        ranked_seeds_path=ranked,
        max_seeds=10,
        one_per_repo=True,
        require_targeted_tests=True,
        require_direct_test_touch=False,
        allow_broad_discovery_for_unseen=True,
        max_seen_repos=1,
    )

    assert [row["seed_id"] for row in rows] == ["seen_1", "unseen_broad"]
    assert summary["route_counts"]["SKIP_MAX_SEEN_REPOS"] == 1
    assert summary["constraints"]["allow_broad_discovery_for_unseen"] is True
    assert summary["constraints"]["max_seen_repos"] == 1


def test_select_ranked_commit_seed_batch_filters_weak_broad_discovery_rows(tmp_path: Path) -> None:
    ranked = tmp_path / "ranked.jsonl"
    ranked.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "seed_id": "weak_broad",
                        "repo_id": "repo_unseen_weak",
                        "rank_metadata": {
                            "discoverability_route": "NEEDS_BROAD_TEST_DISCOVERY",
                            "discoverability_score": 20.0,
                            "has_direct_test_touch": False,
                            "top_broad_test_score": 2.0,
                            "top_broad_verification_score": 0.0,
                            "corpus_novelty": {"repo_seen_before": False},
                        },
                    }
                ),
                json.dumps(
                    {
                        "seed_id": "strong_broad",
                        "repo_id": "repo_unseen_strong",
                        "rank_metadata": {
                            "discoverability_route": "NEEDS_BROAD_TEST_DISCOVERY",
                            "discoverability_score": 30.0,
                            "has_direct_test_touch": False,
                            "top_broad_test_score": 7.5,
                            "top_broad_verification_score": 0.0,
                            "corpus_novelty": {"repo_seen_before": False},
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows, summary = select_ranked_commit_seed_batch(
        ranked_seeds_path=ranked,
        max_seeds=10,
        one_per_repo=True,
        require_targeted_tests=True,
        require_direct_test_touch=False,
        allow_broad_discovery_for_unseen=True,
        min_broad_discovery_score=5.0,
    )

    assert [row["seed_id"] for row in rows] == ["strong_broad"]
    assert summary["route_counts"]["SKIP_BROAD_DISCOVERY_BELOW_MIN_SCORE"] == 1
    assert summary["constraints"]["min_broad_discovery_score"] == 5.0


def test_select_ranked_commit_seed_batch_fails_when_no_rows_survive(tmp_path: Path) -> None:
    ranked = tmp_path / "ranked.jsonl"
    ranked.write_text(
        json.dumps(
            {
                "seed_id": "broad_only",
                "repo_id": "repo_alpha",
                "rank_metadata": {
                    "discoverability_route": "NEEDS_BROAD_TEST_DISCOVERY",
                    "discoverability_score": 10.0,
                    "has_direct_test_touch": False,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="no_ranked_commit_seeds_selected"):
        select_ranked_commit_seed_batch(
            ranked_seeds_path=ranked,
            max_seeds=10,
            one_per_repo=True,
            require_targeted_tests=True,
            require_direct_test_touch=False,
        )
