from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import scripts.build_stage9202_repo_local_real_input_selector as stage9202  # noqa: E402


def test_stage9202_repo_local_real_input_selector(monkeypatch) -> None:
    repo_tmp = ROOT / "runs" / "local" / "artifacts" / "test_stage9202_pytest_tmp"
    monkeypatch.setattr(stage9202, "OUT_DIR", repo_tmp / "artifacts")
    monkeypatch.setattr(stage9202, "SUMMARY", repo_tmp / "summary.json")
    monkeypatch.setattr(stage9202, "DOC", repo_tmp / "doc.md")
    monkeypatch.setattr(stage9202, "SELECTOR", repo_tmp / "artifacts" / "selector.json")
    monkeypatch.setattr(stage9202, "SELECTED", repo_tmp / "artifacts" / "selected.json")
    monkeypatch.setattr(stage9202, "REGISTRY", repo_tmp / "registry.json")

    stage9202.REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    stage9202.REGISTRY.write_text(
        json.dumps(
            {
                "rows": [],
                "metrics": {
                    "latest_stage": 9201,
                    "latest_stage_name": "stage9201_repo_local_real_package_contract_only_smoke",
                    "authority_counts": {},
                    "max_stage": 9201,
                    "registry_rows": 0,
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        stage9202.main()
    assert exc.value.code == 0

    summary = json.loads(stage9202.SUMMARY.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert summary["metrics"]["candidate_bundles"] >= 1
    assert summary["metrics"]["selected_bundle_present"] is True
    assert summary["metrics"]["selected_bundle_materialization_passed"] is True
    assert summary["metrics"]["selected_bundle_eligible_modes"] >= 1

    selector = json.loads(stage9202.SELECTOR.read_text(encoding="utf-8"))
    assert selector["checks"]["all_candidates_repo_local"] is True
    assert selector["checks"]["trainer_execution_closed"] is True
    assert selector["checks"]["runtime_closed"] is True
    assert selector["selected_bundle_id"] == "stage8937_tiny_explicit_manifest_cli_audit"
