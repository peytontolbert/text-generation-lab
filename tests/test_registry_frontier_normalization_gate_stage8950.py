from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8950_registry_frontier_normalization_gate import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_report,
    recent_summary_rows,
    validate_report,
)


def registry(latest: int = 8946) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8950_identifies_frontier_only_failures_without_execution_authority() -> None:
    rows = recent_summary_rows()
    assert any(row["stage"] == 8948 and row["summary_passed"] for row in rows)
    assert any(row["frontier_only_failure"] for row in rows)
    report = build_report(registry())
    assert report["metrics"]["stale_frontier_rows"] >= 1
    assert report["metrics"]["runtime_authorized_flag"] is False
    assert report["metrics"]["training_authorized"] is False


def test_stage8950_validation_rejects_open_authority_or_bad_frontier() -> None:
    report = build_report(registry())
    assert validate_report(report, registry()) == []
    bad_authority = build_report(registry())
    bad_authority["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_report(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_report(report, registry(latest=9999))
