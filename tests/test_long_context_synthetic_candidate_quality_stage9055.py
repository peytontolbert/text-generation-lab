from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9055_long_context_synthetic_candidate_quality_audit import build_audit  # noqa: E402


def test_stage9055_build_audit_prefers_code_fixture_evidence() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_stage9054_long_context_ticket_controls_graph_attachment.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    audit = build_audit()
    assert audit["passed"] is True
    assert audit["checks"]["engine_row_usable"] is True
    assert audit["checks"]["translation_row_rejected"] is True
    assert audit["checks"]["lockfile_row_rejected"] is True
    assert audit["metrics"]["real_corpus_scan_authorized_now"] is False


def test_stage9055_builder_materializes_closed_summary() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_stage9055_long_context_synthetic_candidate_quality_audit.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    summary = json.loads(result.stdout)
    assert summary["passed"] is True
    assert summary["metrics"]["synthetic_fixture_only"] is True
    assert summary["metrics"]["arxiv_read_authorized_now"] is False
    assert summary["metrics"]["training_authorized"] is False
