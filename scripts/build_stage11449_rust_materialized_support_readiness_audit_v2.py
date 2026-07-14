#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "scripts/build_stage11448_rust_materialized_support_readiness_audit.py"


def main() -> None:
    spec = importlib.util.spec_from_file_location("stage11448_base", BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {BASE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.STAGE = 11449
    module.NAME = "stage11449_rust_materialized_support_readiness_audit_v2"
    module.OUT = module.ART / module.NAME
    module.SUMMARY = module.OUT / "rust_materialized_support_readiness_audit_v2.json"
    module.OUT_ROOTS = module.OUT / "rust_materialized_support_root_audit.jsonl"
    module.OUT_ROWS = module.OUT / "rust_materialized_support_row_audit.jsonl"

    module.SELECTED_TEST_ROLES.update(
        {
            "DECISIVE_VERIFIER_TEST_CONSTRAINT",
            "inline_verifier_test_source",
            "verifier_test",
            "verifier_test_source",
        }
    )
    module.VERIFIER_LOG_ROLES.update(
        {
            "OBSERVED_VERIFIER_FAILURE_LOG",
            "actual_verifier_pass_log",
            "actual_verifier_failure_log",
        }
    )

    module.main()


if __name__ == "__main__":
    main()
