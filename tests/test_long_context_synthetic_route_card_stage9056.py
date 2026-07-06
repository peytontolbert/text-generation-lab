from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9056_long_context_synthetic_route_card_audit import build_audit  # noqa: E402


def test_stage9056_build_audit_keeps_synthetic_candidates_review_only() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_stage9055_long_context_synthetic_candidate_quality_audit.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    audit = build_audit()
    assert audit["passed"] is True
    assert audit["checks"]["all_review_only"] is True
    assert audit["checks"]["all_losses_closed"] is True
    assert audit["metrics"]["compiler_ready_rows"] == 0
    assert audit["metrics"]["training_ready_rows"] == 0


def test_stage9056_builder_materializes_closed_summary() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_stage9056_long_context_synthetic_route_card_audit.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    summary = json.loads(result.stdout)
    assert summary["passed"] is True
    assert summary["metrics"]["loss_open_rows"] == 0
    assert summary["metrics"]["training_authorized"] is False
    assert summary["metrics"]["arxiv_read_authorized_now"] is False
