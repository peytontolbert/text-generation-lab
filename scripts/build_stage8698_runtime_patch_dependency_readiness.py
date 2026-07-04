#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from dependency_capability_card_builder import build_dependency_capability_card
from patch_history_modality_builder import build_patch_history_packet
from runtime_trace_normalizer import normalize_runtime_trace

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage8698_runtime_patch_dependency_readiness"
SUMMARY = ROOT / "runs/summaries/stage8698_runtime_patch_dependency_readiness.json"
DOC = ROOT / "docs/RUNTIME_PATCH_DEPENDENCY_READINESS_STAGE8698.md"
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}
TRACE = 'Traceback (most recent call last):\n  File "src/app.py", line 10, in run\n    missing()\nNameError: name \'missing\' is not defined\n'
DIFF = 'diff --git a/src/app.py b/src/app.py\n@@ -1,2 +1,5 @@\n-def old():\n-    pass\n+def new_func():\n+    return 1\n'
DEP = {"name": "numpy", "version": "2.x", "language_family": "python", "allowed_import": True, "exports": ["array", "dot"], "usage_patterns": "vector math,linear algebra", "verifier_requirements": ["import_resolves", "tests_pass"]}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    trace_packet = normalize_runtime_trace(TRACE, row_id="stage8698_trace")
    patch_packet = build_patch_history_packet(DIFF, row_id="stage8698_patch")
    dep_card = build_dependency_capability_card(DEP)
    (OUT_DIR / "sample_runtime_trace_packet.json").write_text(json.dumps(trace_packet, indent=2, sort_keys=True) + "\n")
    (OUT_DIR / "sample_patch_history_packet.json").write_text(json.dumps(patch_packet, indent=2, sort_keys=True) + "\n")
    (OUT_DIR / "sample_dependency_capability_card.json").write_text(json.dumps(dep_card, indent=2, sort_keys=True) + "\n")
    passed = trace_packet["failure_type"] == "symbol_binding_failure" and patch_packet["stats"]["hunks"] == 1 and dep_card["allowed_import"] is True and not dep_card["failures"]
    metrics = {"runtime_frames": len(trace_packet["frames"]), "runtime_failure_type": trace_packet["failure_type"], "patch_files": patch_packet["stats"]["files_changed"], "patch_hunks": patch_packet["stats"]["hunks"], "dependency_exports": len(dep_card["exports"]), "authority_rows": 0, **AUTHORITY_CLOSED}
    card = {"stage": 8698, "name": "stage8698_runtime_patch_dependency_readiness", "stage_name": "stage8698_runtime_patch_dependency_readiness", "passed": passed, "authority": AUTHORITY_CLOSED, "metrics": metrics, "decision": "Recovered deterministic runtime trace normalizer, patch-history modality builder, and dependency capability card builder as no-authority support modules.", "next_best_step": "Attach runtime/patch/dependency modules to the central graph, then recover cross-modal alignment and modality dropout audits.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "runtime_patch_dependency_readiness_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join(["# Stage8698 Runtime/Patch/Dependency Readiness", "", f"Passed: `{passed}`", "", "Recovered modules:", "", "- `runtime_trace_normalizer`", "- `patch_history_modality_builder`", "- `dependency_capability_card_builder`", "", "These modules do not execute code, mine data, train models, or authorize runtime. They normalize already-provided traces, diffs, and dependency metadata into structured packets.", "", "All authority remains closed.", ""]))
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
