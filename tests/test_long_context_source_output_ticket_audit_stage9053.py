from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9053_long_context_source_output_ticket_audit import (  # noqa: E402
    NEGATIVE_EXPECTATIONS,
    build_card,
)


def test_stage9053_build_card_rejects_negative_mutations() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_stage9052_long_context_source_output_ticket_design.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    card = build_card()
    assert card["passed"] is True
    assert card["checks"]["all_negative_mutations_rejected"] is True
    assert set(card["negative_checks"]) == set(NEGATIVE_EXPECTATIONS)
    assert all(item["observed"] for item in card["negative_checks"].values())


def test_stage9053_builder_materializes_closed_summary() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_stage9053_long_context_source_output_ticket_audit.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    summary = json.loads(result.stdout)
    assert summary["passed"] is True
    assert summary["metrics"]["corpus_scan_authorized_now"] is False
    assert summary["metrics"]["candidate_mining_authorized_now"] is False
    assert summary["metrics"]["arxiv_write_authorized"] is False
