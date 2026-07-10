from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_packable_example_quality import audit_packable_example_quality  # noqa: E402


def test_audit_packable_example_quality_reports_family_and_source_concentration(tmp_path: Path) -> None:
    path = tmp_path / "examples.jsonl"
    rows = [
        {
            "example_id": "e1",
            "program_id": "repo_a",
            "query": {"selected_tests": ["tests/test_alpha.py"]},
            "quality": {"quality_score": 0.98},
            "context_rows": [
                {"source_type": "local_repo", "role": "seed_change", "path": "src/a.py"},
                {"source_type": "local_repo", "role": "verification_constraint", "path": "tests/test_alpha.py"},
                {"source_type": "repo", "role": "cross_repo_analogue", "path": "other/src/a.py"},
                {"source_type": "paper", "role": "algorithm_grounding", "path": "paper/method.txt"},
            ],
        },
        {
            "example_id": "e2",
            "program_id": "repo_a",
            "query": {"selected_tests": ["tests/test_alpha.py"]},
            "quality": {"quality_score": 0.97},
            "context_rows": [
                {"source_type": "local_repo", "role": "seed_change", "path": "src/b.py"},
                {"source_type": "local_repo", "role": "verification_constraint", "path": "tests/test_alpha.py"},
                {"source_type": "repo", "role": "cross_repo_analogue", "path": "other/src/b.py"},
                {"source_type": "repo", "role": "cross_repo_analogue", "path": "other/src/c.py"},
            ],
        },
        {
            "example_id": "e3",
            "program_id": "repo_b",
            "query": {"selected_tests": ["tests/test_beta.py"]},
            "quality": {"quality_score": 0.96},
            "context_rows": [
                {"source_type": "local_repo", "role": "seed_change", "path": "src/c.py"},
                {"source_type": "local_repo", "role": "verification_constraint", "path": "tests/test_beta.py"},
                {"source_type": "repo", "role": "cross_repo_analogue", "path": "other/src/d.py"},
            ],
        },
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    detail_rows, summary = audit_packable_example_quality(
        examples_path=path,
        family_share_warn_threshold=0.50,
        source_share_warn_threshold=0.25,
        program_share_warn_threshold=0.50,
    )

    assert summary["example_count"] == 3
    assert summary["verification_family_count"] == 2
    assert summary["top_verification_family"] == "alpha"
    assert round(summary["top_verification_family_share"], 6) == round(2 / 3, 6)
    assert summary["top_program_id"] == "repo_a"
    assert "high_verification_family_concentration" in summary["warning_flags"]
    assert "high_program_concentration" in summary["warning_flags"]
    assert "high_repo_source_share" in summary["warning_flags"]
    assert round(summary["direct_grounding_share"], 6) == round(6 / 11, 6)
    assert detail_rows[0]["example_id"] == "e1"
