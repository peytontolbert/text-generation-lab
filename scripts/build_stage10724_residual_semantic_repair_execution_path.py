#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10724
NAME = "stage10724_residual_semantic_repair_execution_path"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "residual_semantic_repair_execution_path.json"
TARGETS_JSONL = OUT_DIR / "residual_semantic_repair_targets.jsonl"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

SAMPLING_AUDIT = ROOT / "runs/local/artifacts/stage10722_frontloaded_python_verifier_probe_audit/frontloaded_python_verifier_probe_audit.json"
REPRESENTATION_AUDIT = ROOT / "runs/local/artifacts/stage10723_mirrormind_tokenizers_representation_audit/mirrormind_tokenizers_representation_audit.json"
PYTHON_SUPPLY = ROOT / "runs/local/artifacts/stage10463_python_verifier_fresh_root_inventory/python_verifier_fresh_root_inventory.json"
RUST_SUPPLY = ROOT / "runs/local/artifacts/stage10464_rust_citation_fresh_root_inventory/rust_citation_fresh_root_inventory.json"
PYTHON_MATERIALIZED = ROOT / "runs/local/artifacts/stage10475_python_verifier_materialized_root_bundle_builder/python_verifier_materialized_root_bundle_builder.json"
RUST_MATERIALIZED = ROOT / "runs/local/artifacts/stage10476_rust_citation_materialized_root_bundle_builder/rust_citation_materialized_root_bundle_builder.json"
PYTHON_SINGLETON_SUPPORT = ROOT / "runs/local/artifacts/stage10717_python_singleton_verifier_support_manifest/python_singleton_verifier_support_manifest.json"
PYTHON_ABSTAIN_SUPPORT = ROOT / "runs/local/artifacts/stage10716_python_verifier_setvalued_or_abstain_support_builder/python_verifier_setvalued_or_abstain_support_builder.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    sampling = load_json(SAMPLING_AUDIT)
    representation = load_json(REPRESENTATION_AUDIT)
    python_supply = load_json(PYTHON_SUPPLY)
    rust_supply = load_json(RUST_SUPPLY)
    python_materialized = load_json(PYTHON_MATERIALIZED)
    rust_materialized = load_json(RUST_MATERIALIZED)
    python_singleton = load_json(PYTHON_SINGLETON_SUPPORT)
    python_abstain = load_json(PYTHON_ABSTAIN_SUPPORT)

    python_family = representation["families"]["python_mirrormind_verifier"]
    rust_family = representation["families"]["rust_tokenizers_citation"]

    targets = [
        {
            "language_family": "python",
            "priority": 1,
            "residual_family": "verifier_target_disambiguation",
            "row_id": python_family["row_id"],
            "target_label": python_family["target"],
            "gold_value": python_family["gold_value"],
            "current_best_target_rank": python_family["best_target_rank"],
            "current_representation_fixable": bool(python_family["correct_variants"]),
            "required_builder": "semantic_contrast_root_builder",
            "support_status": {
                "existing_singleton_support_rows": python_singleton["metrics"]["support_row_count"],
                "existing_abstention_support_rows": python_abstain["metrics"]["train_row_count"],
                "materialized_promotable_roots": python_materialized["metrics"]["promotable_disjoint_root_count"],
                "fresh_root_requirement": python_supply["builder_requirements"][0],
            },
            "next_stage": "stage10725_python_verifier_semantic_contrast_builder",
            "must_build": [
                "at least 6 new root-disjoint Python verifier roots",
                "3 or more plausible test targets per root",
                "one close sibling wrong test target that remains tempting under visible evidence",
                "selected-test anchor present but not answer-revealing by filename alone",
                "evidence block that distinguishes the gold verifier target from the sibling integration target",
            ],
            "must_preserve": [
                "keep existing stage10717 singleton support as preservation-only input",
                "keep stage10716 abstention rows as honesty-only support",
                "frontload any newly added support or raise step budget so train rows are actually sampled",
            ],
            "anti_cheat_gates": [
                "no reuse of the current MirrorMind strict root in train support",
                "prompt_target_leak must be false",
                "candidate ordering must not reveal the answer",
                "test names alone must not solve the row without the evidence block",
                "representation audit must show either a true semantic improvement or explicitly stay non-promotable",
            ],
            "promotion_gate": [
                "strict accuracy must improve beyond 22/24 with zero regressions",
                "new support must be root-disjoint from strict rows",
                "fresh heldout roots from the same skill family must also improve before any broader Python claim",
            ],
        },
        {
            "language_family": "rust",
            "priority": 2,
            "residual_family": "evidence_citation_semantic_contrast",
            "row_id": rust_family["row_id"],
            "target_label": rust_family["target"],
            "gold_value": rust_family["gold_value"],
            "current_best_target_rank": rust_family["best_target_rank"],
            "current_representation_fixable": bool(rust_family["correct_variants"]),
            "required_builder": "fresh_non_tokenizers_citation_builder",
            "support_status": {
                "materialized_executable_roots": rust_materialized["metrics"]["executable_root_count"],
                "fresh_pending_queue_count": rust_materialized["metrics"]["fresh_pending_queue_count"],
                "fresh_root_requirement": rust_supply["builder_requirements"][0],
                "exact_disjoint_e_vs_f_exists": rust_supply["current_supply_state"]["exact_e_vs_f_disjoint_contrast_exists"],
            },
            "next_stage": "stage10726_rust_citation_semantic_contrast_builder",
            "must_build": [
                "at least 6 new rust evidence-citation roots",
                "non-tokenizers repo families only for promotable support",
                "both symptom_or_call_path_analogue and verifier_and_test_constraint visible as competing options",
                "candidate_change_surface present as a tempting negative but not the gold",
                "real source-backed spans that make the E-vs-F distinction non-trivial",
            ],
            "must_preserve": [
                "keep candle-core executable rows auxiliary only",
                "keep tokenizers same-surface rows diagnostic-only and out of promotable support",
                "record selected-test or verifier-anchor presence explicitly for each new root",
            ],
            "anti_cheat_gates": [
                "no direct copying of the tokenizers strict row into train",
                "prompt_target_leak must be false",
                "option-value permutations must vary so label identity is not fixed",
                "future strict roots must remain root-disjoint from any builder support",
                "representation audit must not be the only evidence of improvement",
            ],
            "promotion_gate": [
                "strict accuracy must improve beyond 22/24 with zero regressions",
                "at least one fresh non-tokenizers root must demonstrate the same semantic contrast honestly",
                "same-surface tokenizers gains alone remain diagnostic-only",
            ],
        },
    ]

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "semantic_repair_execution_path_ready",
        "claim_scope": [
            "Convert the stage10721 and stage10723 residual diagnosis into the next concrete repair execution path.",
            "Forbid another broad support merge as the primary fix path while the two surviving residuals remain semantic-boundary failures.",
        ],
        "current_frontier": {
            "strict_accuracy": sampling["metric_deltas"]["strict_constrained_top1_10721"],
            "strict_correct": 22,
            "strict_total": 24,
            "python_target_rank_after_frontload": sampling["residuals"]["python_verifier"]["target_rank_full_vocab_10721"],
            "rust_target_rank_after_frontload": sampling["residuals"]["rust_citation"]["target_rank_full_vocab_10721"],
        },
        "representation_audit_summary": {
            "python_has_any_correct_variant": bool(representation["conclusions"]["python_has_any_correct_variant"]),
            "rust_has_any_correct_variant": bool(representation["conclusions"]["rust_has_any_correct_variant"]),
            "python_best_target_rank": representation["conclusions"]["python_best_target_rank"],
            "rust_best_target_rank": representation["conclusions"]["rust_best_target_rank"],
        },
        "headline_conclusion": [
            "Python is no longer blocked on missing support or unsampled support; it is blocked on a true B-vs-C verifier disambiguation boundary.",
            "Rust is no longer blocked on option templating; it is blocked on missing fresh non-tokenizers E-vs-F citation roots.",
            "Neither surviving miss flips under representation-only candidate scoring changes, so the next improvement must come from new semantic contrast data.",
        ],
        "next_stage_sequence": [
            "stage10725_python_verifier_semantic_contrast_builder",
            "stage10726_rust_citation_semantic_contrast_builder",
            "stage10727_semantic_contrast_support_package",
            "stage10728_semantic_contrast_probe_request",
            "stage10729_semantic_contrast_probe_audit",
        ],
        "shared_contract": {
            "preserve_canary": "Keep the current 24-row repaired overlay as the regression gate.",
            "freshness_rule": "All newly claimed support must be root-disjoint from the strict overlay rows.",
            "sampling_rule": "Any added support rows must either be frontloaded or trained with enough steps to guarantee sampling coverage.",
            "runtime_rule": "Use the trellis environment for all runtime torch-dependent audits or probes.",
            "anti_cheat_rule": [
                "prompt_target_leak must be false",
                "candidate order cannot encode the answer",
                "same-surface replay remains diagnostic-only",
                "fresh heldout confirmation is required before broadening any claim",
            ],
        },
        "source_artifacts": {
            "sampling_audit": display(SAMPLING_AUDIT),
            "representation_audit": display(REPRESENTATION_AUDIT),
            "python_supply": display(PYTHON_SUPPLY),
            "rust_supply": display(RUST_SUPPLY),
            "python_materialized": display(PYTHON_MATERIALIZED),
            "rust_materialized": display(RUST_MATERIALIZED),
            "python_singleton_support": display(PYTHON_SINGLETON_SUPPORT),
            "python_abstain_support": display(PYTHON_ABSTAIN_SUPPORT),
        },
        "targets_jsonl": display(TARGETS_JSONL),
    }

    write_jsonl(TARGETS_JSONL, targets)
    write_json(REQUEST_JSON, request)
    write_json(
        SUMMARY_JSON,
        {
            "stage": STAGE,
            "passed": True,
            "decision": request["decision"],
            "strict_accuracy": request["current_frontier"]["strict_accuracy"],
            "targets_jsonl": display(TARGETS_JSONL),
            "artifact": display(REQUEST_JSON),
        },
    )
    print(json.dumps(request, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
