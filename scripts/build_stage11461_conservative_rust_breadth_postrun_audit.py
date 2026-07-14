#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "scripts/build_stage11458_rust_breadth_support_postrun_audit.py"


def main() -> None:
    spec = importlib.util.spec_from_file_location("stage11458_base", BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {BASE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.STAGE = 11461
    module.NAME = "stage11461_conservative_rust_breadth_postrun_audit"
    module.OUT_DIR = module.ARTIFACTS / module.NAME
    module.SUMMARY_JSON = module.OUT_DIR / "conservative_rust_breadth_postrun_audit.json"
    module.RUNTIME = module.ARTIFACTS / "stage11460_conservative_rust_breadth_probe/runtime_model/runtime_model_bundle.json"
    module.REQUEST = module.ARTIFACTS / "stage11459_conservative_rust_breadth_probe_request/conservative_rust_breadth_probe_request.json"
    module.PACKAGE = module.ARTIFACTS / "stage11454_rust_breadth_support_package_v2/rust_breadth_support_package_v2.json"

    module.main()


if __name__ == "__main__":
    main()
