#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from skill_tool_registry import build_registry

STAGE = 8769
NAME = "stage8769_skill_tool_registry_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SKILL_TOOL_REGISTRY_READINESS_STAGE8769.md"
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}
TOOLS = [
    {"tool_id": "read_file", "action_type": "observe", "permission": "read_only", "input_schema": {"path": "str"}, "failure_modes": ["missing_file"]},
    {"tool_id": "edit_file", "action_type": "act", "permission": "workspace_write", "input_schema": {"path": "str", "patch": "str"}, "failure_modes": ["patch_conflict"]},
    {"tool_id": "network_fetch", "action_type": "observe", "permission": "network", "input_schema": {"url": "str"}, "failure_modes": ["timeout"], "requires_explicit_authority": True},
    {"tool_id": "bad_tool", "action_type": "act", "permission": "destructive", "input_schema": {"path": "str"}, "failure_modes": ["data_loss"]},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_skill_tool_registry.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    sample = build_registry(TOOLS)
    sample_path = OUT_DIR / "skill_tool_registry_sample_card.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures=[]
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if sample["metrics"]["passed_tools"] != 3 or sample["metrics"]["blocked_tools"] != 1 or sample["metrics"]["safe_for_training_surface"] != 2:
        failures.append("sample_route_counts_wrong")
    card={"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "sample_tools": len(TOOLS), "passed_tools": sample["metrics"]["passed_tools"], "blocked_tools": sample["metrics"]["blocked_tools"], "safe_for_training_surface": sample["metrics"]["safe_for_training_surface"], "failures": failures}, "artifacts": {"sample_card": str(sample_path.relative_to(ROOT)), "module": "scripts/skill_tool_registry.py", "tests": "tests/test_skill_tool_registry.py"}, "decision": "Skill/tool registry is ready as a no-execution ontology and permission gate for future observe-orient-act training surfaces." if not failures else "Skill/tool registry readiness failed.", "next_best_step": "Attach skill_tool_registry to central graph when commit/reconcile path is clear; attach skill_tool_registry to the central graph, then recover source-backed patch operator or ngram_repetition_style_detectors.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8769 Skill Tool Registry Readiness", "", f"Passed: `{card['passed']}`", "", "Recovered a typed tool/action registry for observe-orient-act rows. It validates permissions, input schemas, failure modes, and explicit authority requirements for dangerous tools.", "", "Only read-only and workspace-write passing tools are marked safe for training surfaces. Runtime/network/destructive actions remain authority-gated.", "", "Authority remains closed. This does not execute tools, mine, train, score, or promote.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
