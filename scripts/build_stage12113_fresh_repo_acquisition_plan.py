#!/usr/bin/env python3
"""Plan fresh repo acquisition after local sealed-root supply is exhausted."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12113
NAME = "stage12113_fresh_repo_acquisition_plan"
OUT = ROOT / "runs/local/artifacts" / NAME
SUMMARY = OUT / "fresh_repo_acquisition_plan.json"
MIRROR = ROOT / "runs/summaries" / f"{NAME}.json"
INTAKE_TEMPLATE = OUT / "fresh_repo_acquisition_candidate_template.json"
SCOUT_INTAKE = OUT / "fresh_repo_acquisition_scout_candidates.jsonl"

STAGE12112 = ROOT / "runs/summaries/stage12112_subagent_scout_decision.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prior = read_json(STAGE12112)
    remaining = prior["remaining_gap"]
    template = {
        "repo_family": "canonical_family",
        "source_path_or_acquisition_target": "/local/path/or/org/repo",
        "exists_locally": False,
        "language": "rust|c_cpp|web_js_ts_html|mixed_build_config_dependency",
        "verifier_type": "selected_test_anchor|build_config_anchor|static_compile_anchor|dependency_resolution_anchor",
        "available_evidence": ["manifest/test/build markers if local; expected markers if acquisition target"],
        "missing_evidence": ["fresh checkout", "verifier execution log", "selected test"],
        "suggested_commands": [["cargo", "test", "--locked"], ["npm", "test"], ["cmake", "-S", ".", "-B", "build"]],
        "reserved_family_conflict": False,
        "conflict_reason": "",
        "split_status": "sealed_candidate|needs_acquisition|dev_only",
        "why_valid": "Verifier-grounded transition boundary this root can support.",
        "risk_notes": ["build-only scope", "dependency hydration risk", "repo family cap risk"],
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "fresh_repo_acquisition_plan_ready",
        "do_not_train": True,
        "why": [
            "Stage12103 passed route permutation stability.",
            "Stage12105-12112 showed local sealed supply is insufficient under strict lineage rules.",
            "Subagents are now scoped as acquisition scouts, not data generators.",
            "Only deterministic checkout/execution/admission can promote a candidate into sealed rows.",
        ],
        "remaining_gap": remaining,
        "target_acquisition": {
            "rust": max(20, int(remaining.get("rust", 0))),
            "web_js_ts_html": max(12, int(remaining.get("web_js_ts_html", 0))),
            "c_cpp": max(10, int(remaining.get("c_cpp", 0))),
            "extra_buffer_factor": "1.5x preferred because verifier hydration will reject some roots",
        },
        "strict_rules": [
            "Subagents may propose roots, not train/eval rows.",
            "A needs_acquisition target is not evidence until locally checked out and probed.",
            "No candidate may count as sealed if canonical repo_family overlaps Stage11897, Stage11943, any Stage120xx transition/support artifact, Stage12105, Stage12107, Stage12109, or Stage12111.",
            "Build-only roots must be labeled build_config_anchor/static_compile_anchor and cannot be used as selected_test_anchor.",
            "Every emitted row must use semantic candidate objects and opaque shuffled non-singleton labels.",
            "Target semantic value must not appear before candidate options.",
            "Dev-only candidates can be used later for training/representation, never for Stage12104 sealed confirmation.",
        ],
        "scout_contract": template,
        "next_stage_recommendation": {
            "stage": "stage12114_fresh_repo_acquisition_intake_audit",
            "action": "Merge scout outputs into the intake JSONL, deterministically reject conflicts, then request checkout/probe only for clean needs_acquisition/local candidates.",
        },
        "source_artifacts": {
            "stage12112_scout_decision": rel(STAGE12112),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "summary_mirror": rel(MIRROR),
            "candidate_template": rel(INTAKE_TEMPLATE),
            "scout_intake_placeholder": rel(SCOUT_INTAKE),
        },
    }
    write_json(INTAKE_TEMPLATE, template)
    write_text(SCOUT_INTAKE, "")
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({
        "decision": summary["decision"],
        "remaining_gap": remaining,
        "target_acquisition": summary["target_acquisition"],
        "next_stage": summary["next_stage_recommendation"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
