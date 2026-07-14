#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10886
NAME = "stage10886_tokenizers_bindings_node_honesty_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "tokenizers_bindings_node_honesty_audit.json"

PREVIEW_JSON = ARTIFACTS / "stage10885_tokenizers_bindings_node_preview" / "tokenizers_bindings_node_preview_bundle.json"
SUMMARY_JSON = ARTIFACTS / "stage10885_tokenizers_bindings_node_preview" / "tokenizers_bindings_node_preview.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    bundle = load_json(PREVIEW_JSON)
    summary = load_json(SUMMARY_JSON)
    candidate_paths = list(bundle.get("candidate_paths") or [])
    selected_tests = list(bundle.get("selected_tests") or [])
    evidence = bundle.get("maintainer_visible_evidence") or {}

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "bindings_node_preview_not_yet_honest_for_heldout_scoring",
        "claim_scope": [
            "Judge whether the newly materialized tokenizers::bindings/node preview is already honest enough for maintainer-grade heldout scoring.",
            "Keep the Rust heldout lane honest by separating preview materialization progress from actual promotable evaluation readiness.",
        ],
        "headline_findings": [
            "The bindings/node bundle is genuinely root-disjoint from the current train package and materially better than a queue-only suggestion.",
            "It has real source surfaces plus a build anchor, but no failure-specific test or execution trace that uniquely chooses one code surface over the other plausible bindings-node modules.",
            "As currently materialized, the packet is support/stress-quality preview material, not yet a promotable heldout Rust maintainer eval root.",
        ],
        "readiness_checks": {
            "root_disjoint_from_current_train_package": bool((bundle.get("claim_boundary") or {}).get("root_disjoint_from_current_train_package")),
            "has_real_candidate_paths": bool(candidate_paths),
            "has_build_anchor": bool(selected_tests),
            "has_failure_specific_selected_test": False,
            "supports_unique_singleton_localization_now": False,
            "supports_honest_abstention_packet": True,
            "requires_more_gold_adjudication": True,
        },
        "blocking_reasons": [
            "verifier_and_test_constraint is build-anchored rather than tied to a concrete failing maintainer test or execution transition",
            "symptom_localization remains underdetermined among tokenizer.rs, pre_tokenizers.rs, models.rs, and task flow surfaces",
            "evidence_citation cannot be promoted cleanly until the chosen target semantics are fixed by either stronger failure evidence or explicit abstention-first gold answers",
        ],
        "recommended_gold_policy_if_used_now": {
            "symptom_localization": "ABSTAIN_INSUFFICIENT_EVIDENCE",
            "evidence_citation": "ABSTAIN_INSUFFICIENT_EVIDENCE",
            "alternative_hypothesis_elimination": "support_only_freeform_explanation_allowed",
            "patch_impact": "ABSTAIN_INSUFFICIENT_EVIDENCE",
            "verifier_outcome": selected_tests[0] if selected_tests else "ABSTAIN_INSUFFICIENT_EVIDENCE",
            "minimal_fix_selection": "ABSTAIN_INSUFFICIENT_EVIDENCE",
            "regression_risk": "support_only_freeform_risk_allowed",
            "abstention_insufficient_evidence": "ABSTAIN_INSUFFICIENT_EVIDENCE",
        },
        "next_best_steps": [
            "Recover one failure-specific Node binding behavior trace, test, or cargo-build transition that narrows the candidate surface beyond generic module structure.",
            "If that cannot be recovered, keep bindings/node as support-only or abstention-honesty material rather than headline heldout Rust evidence.",
            "Continue searching for a second root-disjoint Rust eval candidate while preserving the quarantined 23-row heldout baseline.",
        ],
        "metrics": {
            "candidate_paths_count": len(candidate_paths),
            "selected_build_anchor_count": len(selected_tests),
            "visible_evidence_key_count": len([k for k, v in evidence.items() if v]),
        },
        "source_artifacts": {
            "preview_bundle": rel(PREVIEW_JSON),
            "preview_summary": rel(SUMMARY_JSON),
        },
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
