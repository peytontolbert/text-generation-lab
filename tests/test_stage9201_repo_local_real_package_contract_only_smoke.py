from __future__ import annotations

import json
import pytest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import scripts.build_stage9201_repo_local_real_package_contract_only_smoke as stage9201  # noqa: E402


def test_stage9201_repo_local_real_package_contract_only_smoke(tmp_path, monkeypatch) -> None:
    repo_tmp = ROOT / "runs" / "local" / "artifacts" / "test_stage9201_pytest_tmp"
    monkeypatch.setattr(stage9201, "OUT_DIR", repo_tmp / "artifacts")
    monkeypatch.setattr(stage9201, "SUMMARY", repo_tmp / "summary.json")
    monkeypatch.setattr(stage9201, "DOC", repo_tmp / "doc.md")
    monkeypatch.setattr(stage9201, "REGISTRY", repo_tmp / "registry.json")

    stage9201.REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    stage9201.REGISTRY.write_text(
        json.dumps(
            {
                "rows": [],
                "metrics": {
                    "latest_stage": 9200,
                    "latest_stage_name": "stage9200_trainer_ready_synthetic_contract_only_smoke",
                    "authority_counts": {},
                    "max_stage": 9200,
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
        stage9201.main()
    assert exc.value.code == 0

    summary = json.loads(stage9201.SUMMARY.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert summary["metrics"]["materialization_passed"] is True
    assert summary["metrics"]["structured_commands"] == 1
    assert summary["metrics"]["structured_contract_only_passed"] is True

    audit = json.loads((stage9201.OUT_DIR / "repo_local_real_package_contract_only_smoke.json").read_text(encoding="utf-8"))
    assert audit["checks"]["bounded_decoder_command_absent"] is True
    assert audit["checks"]["denoise_command_absent"] is True
    assert audit["checks"]["structured_manifest_nonempty"] is True
    assert audit["structured_contract_only_smoke"]["contract_audit_exists"] is True
    assert audit["structured_contract_only_smoke"]["cleanup_proof_exists"] is True
