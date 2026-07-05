#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8796
NAME = "stage8796_current_gap_audit_after_registry_reconciliation"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DOC = ROOT / "docs" / "CURRENT_GAP_AUDIT_AFTER_REGISTRY_RECONCILIATION_STAGE8796.md"
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def summary_passed(rel: str) -> bool:
    path = ROOT / rel
    if not path.exists():
        return False
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("passed") is True
    except json.JSONDecodeError:
        return False


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    objective_status = {
        "intent_to_build_strategy": {
            "status": "neutral_ready_not_source_backed",
            "evidence": ["runs/summaries/stage8630_intent_to_build_neutral_manifest.json", "runs/summaries/stage8631_intent_to_build_shortcut_baseline.json", "runs/summaries/stage8668_intent_to_build_copy_routed_manifest.json"],
            "gap": "No current source-backed/gate-status candidate manifest equivalent to symbol/edit/patch/verifier.",
        },
        "source_backed_symbol_binding": {
            "status": "candidate_ready_needs_expansion_and_compiler_gates",
            "evidence": ["runs/summaries/stage8674_source_backed_symbol_binding_candidate_manifest.json", "runs/summaries/stage8675_source_backed_symbol_binding_candidate_manifest_audit.json"],
            "gap": "Validated seed exists; test-query counterexamples and full gate materialization remain thin before mining/training.",
        },
        "source_backed_edit_localization": {
            "status": "candidate_ready_no_training",
            "evidence": ["runs/summaries/stage8765_source_backed_edit_localization_candidate_manifest.json", "runs/summaries/stage8766_source_backed_edit_localization_candidate_audit.json", "runs/summaries/stage8767_source_backed_edit_localization_graph_attachment.json"],
            "gap": "Rows are candidate-only; remaining recovered gates must be explicitly materialized before compiler-ready training rows.",
        },
        "source_backed_patch_operator": {
            "status": "candidate_ready_no_training",
            "evidence": ["runs/summaries/stage8774_source_backed_patch_operator_candidate_manifest.json", "runs/summaries/stage8775_source_backed_patch_operator_candidate_audit.json", "runs/summaries/stage8776_source_backed_patch_operator_graph_attachment.json"],
            "gap": "Rows are candidate-only; remaining recovered gates must be explicitly materialized before compiler-ready training rows.",
        },
        "source_backed_verifier_repair": {
            "status": "candidate_ready_no_training",
            "evidence": ["runs/summaries/stage8788_source_backed_verifier_repair_candidate_manifest.json", "runs/summaries/stage8789_source_backed_verifier_repair_candidate_audit.json", "runs/summaries/stage8790_source_backed_verifier_repair_graph_attachment.json"],
            "gap": "Rows are candidate-only; remaining recovered gates must be explicitly materialized before compiler-ready training rows.",
        },
        "bounded_decoder_arguments": {
            "status": "neutral_ready_missing_source_backed_gate_status_controls",
            "evidence": ["runs/summaries/stage8645_bounded_decoder_arguments_neutral_manifest.json", "runs/summaries/stage8646_bounded_decoder_arguments_shortcut_baseline.json"],
            "gap": "Next objective to recover: candidate manifest under gate_status_contract with decoder_ce still closed.",
        },
        "bounded_decoder_ce": {
            "status": "old_scaffold_exists_current_rebuild_blocked",
            "evidence": ["runs/summaries/stage8592_reconstructed_bounded_decoder_ce_candidate_and_loss_mask_package.json", "runs/summaries/stage8594_reconstructed_bounded_decoder_ce_final_pre_execution_audit.json"],
            "gap": "Must be rebuilt from recovered bounded-decoder-argument controls and loss masks; no decoder CE execution authorized.",
        },
        "output_repair_denoise": {
            "status": "neutral_ready_missing_source_backed_gate_status_controls",
            "evidence": ["runs/summaries/stage8647_output_repair_denoise_neutral_manifest.json", "runs/summaries/stage8648_output_repair_denoise_shortcut_baseline.json"],
            "gap": "Needs source-backed/verified repair controls after bounded decoder argument controls; denoise CE remains closed.",
        },
    }
    for obj in objective_status.values():
        obj["evidence_present"] = {rel: exists(rel) for rel in obj["evidence"]}
        obj["evidence_passed"] = {rel: summary_passed(rel) for rel in obj["evidence"] if rel.endswith(".json")}

    support_status = {
        "stage8753_missing_real_modules": "locally_ready_per_stage8792",
        "query_expansion_rewriter": "ready_no_authority_per_stage8791_graph_attached_stage8793",
        "curriculum_compiler": "requires recovered gates and routes rows to human review when gates fail; still needs deeper mandatory integration with ranker/cluster/lineage for mining scale",
        "training_telemetry": "modules exist but no authorized native training run has produced current row/logit/gradient telemetry for recovered objectives",
        "runtime_verifier_loop": "contract recovered but runtime execution remains closed",
        "transformer_100m": "target architecture features recovered; model execution remains closed",
    }

    remaining_blockers = [
        "Recover source-backed bounded_decoder_arguments candidate controls under gate_status_contract.",
        "Recover output_repair_denoise candidate controls after bounded decoder arguments.",
        "Rebuild bounded_decoder_ce candidate/loss-mask package from current recovered argument controls, not stale pre-gate artifacts.",
        "Materialize full recovered gate_status passes for candidate rows: contamination, locked/golden eval, drift canary, cluster/slice, junk/OOD, schema, source lineage/provenance.",
        "Rerun no-training scale-readiness preflight after current candidate controls are rebuilt.",
        "Do not resume mining until objective builders emit counterfactual obligations, duplicate/split checks, route cards, authority cards, and loss-mask cards.",
        "Do not resume training/model execution until structured telemetry, loss masks, and final pre-execution audits pass for the current manifests.",
    ]

    metrics = {
        **AUTHORITY_CLOSED,
        "authority_rows": 0,
        "objectives_reviewed": len(objective_status),
        "candidate_ready_no_training_objectives": sum(1 for value in objective_status.values() if "candidate_ready" in value["status"]),
        "neutral_ready_missing_source_backed_controls": sum(1 for value in objective_status.values() if "missing_source_backed" in value["status"]),
        "remaining_blocker_count": len(remaining_blockers),
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "objective_status": objective_status,
        "support_status": support_status,
        "remaining_blockers": remaining_blockers,
        "decision": "Current gap audit recorded. Recovery has advanced through source-backed verifier repair, but bounded decoder arguments, output repair denoise, current bounded decoder CE packaging, full gate materialization, mining, and training remain blocked.",
        "next_best_step": "Recover source-backed bounded decoder argument candidate controls under gate_status_contract.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    summary_path = SUMMARY
    summary_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "current_gap_audit_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Stage8796 Current Gap Audit After Registry Reconciliation",
        "",
        "Passed: `true`",
        "",
        "This is a no-authority status audit. It updates the stale Stage8629/8686 gap picture after the Stage8765-8795 recoveries and registry/spine reconciliation.",
        "",
        "## Remaining Blockers",
        "",
    ]
    lines.extend(f"- {item}" for item in remaining_blockers)
    lines.extend(["", "## Objective Status", ""])
    for name, status in objective_status.items():
        lines.append(f"- `{name}`: `{status['status']}` - {status['gap']}")
    lines.extend(["", "Authority remains closed: no mining, training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, controller merge, or promotion is authorized.", ""])
    DOC.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
