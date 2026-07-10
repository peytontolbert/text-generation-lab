from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_stage10117_builds_contract() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10117_true_source_backed_maintainer_eval_replacement_contract.py",
        "stage10117_live",
    )
    built = mod.build()
    assert built["passed"] is True
    assert built["claim_boundary"]["synthetic_stage8636_to_stage8765_lineage_retired_for_headline_benchmarking"] is True
    assert built["metrics"]["required_perspective_count"] == 8
    assert built["builder_bootstrap_plan"]["rust"] == "replenish_real_session_roots_before_four_language_claim"


def test_stage10117_writes_contract() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10117_true_source_backed_maintainer_eval_replacement_contract.py",
        "stage10117_written",
    )
    mod.main()
    payload = json.loads(mod.CONTRACT.read_text(encoding="utf-8"))
    assert payload["root_bundle_contract"]["unit_of_independence"] == "root_bug_fix_case"
    assert payload["root_bundle_contract"]["minimum_rows_per_root"] == 6
    assert "abstention_insufficient_evidence" in payload["root_bundle_contract"]["required_perspectives"]
