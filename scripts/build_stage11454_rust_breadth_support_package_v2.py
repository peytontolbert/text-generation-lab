#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "scripts/build_stage11450_rust_breadth_support_package.py"


def main() -> None:
    spec = importlib.util.spec_from_file_location("stage11450_base", BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {BASE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.STAGE = 11454
    module.NAME = "stage11454_rust_breadth_support_package_v2"
    module.OUT = module.ART / module.NAME
    module.SUMMARY = module.OUT / "rust_breadth_support_package_v2.json"
    module.AUDIT = module.OUT / "rust_breadth_support_package_audit.json"
    module.TRAIN = module.OUT / "agentkernel_lite_encdec_train.jsonl"
    module.VALIDATION = module.OUT / "agentkernel_lite_encdec_validation.jsonl"
    module.STRICT = module.OUT / "agentkernel_lite_encdec_strict_eval.jsonl"
    module.RESIDUAL = module.OUT / "semantic_candidate_residual_bank.jsonl"
    module.ADDED = module.OUT / "added_rust_breadth_support_rows.jsonl"
    module.SKIPPED = module.OUT / "skipped_rust_breadth_support_rows.jsonl"
    module.ROOT_AUDIT = module.ART / "stage11453_rust_materialized_support_readiness_audit_v3/rust_materialized_support_root_audit.jsonl"
    module.SOURCE_FILES = list(module.SOURCE_FILES) + [
        module.ART / "stage11452_non_codex_rust_selected_verifier_support_rows/non_codex_rust_selected_verifier_support_rows.jsonl"
    ]

    module.main()


if __name__ == "__main__":
    main()
