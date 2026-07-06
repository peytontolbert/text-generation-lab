from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_stage9051_candidate_miner_guard_audit_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_stage9051_long_context_candidate_miner_guard_audit.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    card = json.loads((ROOT / "runs/local/artifacts/stage9051_long_context_candidate_miner_guard_audit/long_context_candidate_miner_guard_audit.json").read_text())
    assert json.loads(result.stdout)["passed"] is True
    assert all(card["checks"].values())
    assert card["metrics"]["candidate_mining_executed_now"] is False
    assert card["metrics"]["arxiv_candidate_write_authorized_now"] is False
