#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12364_diversity_weighted_admission_policy"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
PREVIOUS_CONTROL = ROOT / "runs/summaries/stage12355_selected_test_materializer_and_plateau_control.json"
CURRENT_LEDGER = ROOT / "runs/summaries/stage12363_combined_train_support_ledger_v6.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    previous = read_json(PREVIOUS_CONTROL)
    ledger = read_json(CURRENT_LEDGER)
    policy = {
        "stage": STAGE,
        "decision": "diversity_weighted_admission_policy_supersedes_hard_org_caps",
        "training_allowed": False,
        "claim_boundary": "Control artifact only. No rows are admitted by this stage.",
        "supersedes": str(PREVIOUS_CONTROL),
        "current_ledger_ref": str(CURRENT_LEDGER),
        "current_train_support_rows": ledger.get("current_admitted_train_support_tasks"),
        "current_remaining_gap_to_500": ledger.get("remaining_gap_to_500"),
        "policy_correction": {
            "old_problem": "Stage12355 single-org/single-repo caps were too blunt and could block clean transformed internal data such as MCP core.",
            "new_rule": "Do not hard-block solely because a row comes from a repeated org/source adapter. Admit only if lineage, evidence, anti-leak, and task semantics pass; apply diversity weights and warnings for concentration.",
            "reason": "Caps are anti-overfit/eval-hacking guardrails, not user-level volume limits. The dataset may scale from a source when transformed into diverse, same-source, verifier-backed roots.",
        },
        "hard_rejects_that_remain": [
            "target/gold semantic value visible in model input before opaque options",
            "raw source, raw verifier output, or raw trace text emitted in model-facing fields",
            "missing commit_sha, source_hash_refs, test_hash_refs, or selected verifier command/log refs",
            "cross-source patch/action/verifier joins",
            "patch/test co-presence without causal ordering or verifier relevance when claiming Level-3/repair",
            "PASS_TO_PASS or PASS_CURRENT_BUILD counted as repair proof",
            "strict/source-heldout/Level-3/patch/repair claims set true for support-only rows",
            "singleton options or answer-position shortcuts",
            "dependency/vendor/generated paths used as primary visible source evidence",
            "same root or root_lineage_key crossing train/eval/sealed splits",
        ],
        "weighted_warnings_not_hard_rejects": {
            "same_org_or_source_adapter_repeat": {
                "first_distinct_repo_family": 1.0,
                "additional_distinct_repo_family_with_distinct_verifier": 0.75,
                "same_repo_distinct_package_or_subsystem": 0.5,
                "same_repo_same_task_family_PASS_only": 0.25,
                "repair_grade_fail_to_pass_with_same_source_proof": 1.0,
                "note": "Weights affect progress accounting and sampling priority, not row validity.",
            },
            "OpenHands_or_other_prior_risk_family": "defer only when prior heldout/support leakage or overfit risk is specific and documented; do not block solely by org.",
            "MCP_core": "eligible for train-support reconsideration if distinct package/root/verifier/source/test hashes pass and all stronger claims remain false.",
            "Open_SWE": "source adapter only; raw traces must become internal episode_graph_candidate records and then safe semantic train-support rows. No direct trace-to-training admission.",
        },
        "required_transformation_for_source_adapters": {
            "Open_SWE": [
                "parse trace into ordered events",
                "recover source_root_label and lineage key",
                "extract safe state_before/state_after codes without raw text leakage",
                "join chosen action to command/tool observation",
                "verify same-source command/output evidence",
                "render internal opaque candidate actions",
                "run deterministic anti-leak and split checks",
                "admit only train-support unless Level-3/repair proof is complete",
            ],
            "MCP_or_other_local_repos": [
                "focused local verifier command must execute or have authoritative same-source log",
                "source/test hash refs must be concrete and non-vendor",
                "candidate roles must be task-specific, not generic selected-test-anchor reuse",
                "language/repo/source-family concentration must be visible in the ledger",
            ],
        },
        "admission_accounting_fields_required": [
            "raw_row_count",
            "weighted_progress_count",
            "repo_family",
            "source_adapter",
            "language_family",
            "task_family",
            "verifier_evidence_type",
            "diversity_weight",
            "concentration_warnings",
            "hard_rejects",
        ],
        "next_actions": [
            "reconsider MCP core as train-support under this policy, not Stage12355 hard org cap",
            "keep tokenizers deferred; use non-tokenizers Rust selected-test roots first",
            "move Open-SWE QC candidates through safe semantic extraction only",
            "prioritize non-web selected-test roots and real transition-function rows before more PASS-only web volume",
        ],
        "previous_stage12355_plateau_caps": previous.get("plateau_caps"),
    }
    (OUT / "diversity_weighted_admission_policy.json").write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "DIVERSITY_WEIGHTED_ADMISSION_POLICY_STAGE12364.md").write_text(
        "# Stage12364 Diversity-Weighted Admission Policy\n\n"
        "This stage supersedes hard same-org/source caps with diversity-weighted admission accounting. "
        "Leakage, claim inflation, split overlap, missing evidence, and repair-proof violations remain hard rejects.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
