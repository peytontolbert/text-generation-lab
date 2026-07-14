#!/usr/bin/env python3
"""Audit Stage11893 using the Stage11891 metric contract."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.build_stage11891_support_only_learnability_postrun_audit as base
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"

base.STAGE = 11894
base.NAME = "stage11894_protected_replay_postrun_audit"
base.OUT = ART / base.NAME
base.SUMMARY = base.OUT / "protected_replay_postrun_audit.json"
base.RUNTIME = ART / "stage11893_rendered_support_protected_replay_probe/runtime_model/runtime_model_bundle.json"
base.SUMMARIES = SUMMARIES


if __name__ == "__main__":
    base.main()
