from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9969_blended_weak_language_same_manifest_review_packets.py"
    spec = importlib.util.spec_from_file_location("stage9969", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_packets_reflects_same_manifest_review_scope():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    import build_stage9966_blended_weak_language_target100m_execution_request as stage9966
    import build_stage9967_blended_weak_language_execution_readiness_gate as stage9967
    import build_stage9968_blended_weak_language_same_manifest_handoff_bundle as stage9968

    stage9966.main()
    stage9967.main()
    stage9968.main()

    mod = _load()
    built = mod.build_packets()
    assert built["passed"] is True
    audit = built["audit"]
    assert audit["metrics"]["review_packets"] == 4
    assert audit["metrics"]["same_manifest_compare_rows"] == 80
    assert audit["metrics"]["languages_with_machine_supported_applicable_scope"] == 4
    assert audit["metrics"]["languages_with_clean_anti_cheat_contract"] == 4
    assert len(audit["language_cards"]) == 4
    for row in audit["language_cards"]:
        assert row["compare_rows"] > 0
        assert row["opaque_choice_surface"] is True
        assert row["all_gate_status_true"] is True
