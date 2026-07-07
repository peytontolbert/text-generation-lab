from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import scripts.build_stage9203_selected_bundle_contract_only_handoff as stage9203  # noqa: E402


def test_stage9203_selected_bundle_contract_only_handoff(monkeypatch) -> None:
    repo_tmp = ROOT / "runs" / "local" / "artifacts" / "test_stage9203_pytest_tmp"
    monkeypatch.setattr(stage9203, "OUT_DIR", repo_tmp / "artifacts")
    monkeypatch.setattr(stage9203, "SUMMARY", repo_tmp / "summary.json")
    monkeypatch.setattr(stage9203, "DOC", repo_tmp / "doc.md")
    monkeypatch.setattr(stage9203, "REGISTRY", repo_tmp / "registry.json")

    stage9203.REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    stage9203.REGISTRY.write_text(
        json.dumps(
            {
                "rows": [],
                "metrics": {
                    "latest_stage": 9202,
                    "latest_stage_name": "stage9202_repo_local_real_input_selector",
                    "authority_counts": {},
                    "max_stage": 9202,
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
        stage9203.main()
    assert exc.value.code == 0

    summary = json.loads(stage9203.SUMMARY.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert summary["metrics"]["materialization_passed"] is True
    assert summary["metrics"]["recommended_commands"] >= 1
    assert summary["metrics"]["contract_only_smokes"] >= 1
    assert summary["metrics"]["contract_only_smokes_passed"] == summary["metrics"]["contract_only_smokes"]

    audit = json.loads((stage9203.OUT_DIR / "selected_bundle_contract_only_handoff.json").read_text(encoding="utf-8"))
    assert audit["checks"]["selected_bundle_present"] is True
    assert audit["checks"]["all_contract_only_smokes_passed"] is True
    assert audit["checks"]["all_contract_audits_written"] is True
    assert audit["checks"]["all_cleanup_proofs_written"] is True
