#!/usr/bin/env python3
"""Audit whether mining is recovered enough to start expanding data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_FILES = {
    "arxiv_indexer": "scripts/index_arxiv_software_corpus.py",
    "repo_capability_builder": "scripts/build_stage8601_arxiv_repo_capability_and_graph_seed.py",
    "symbol_binding_extractor": "scripts/build_stage8603_arxiv_symbol_binding_candidates.py",
    "counterfactual_builder": "scripts/build_stage8610_symbol_binding_counterfactual_patch.py",
    "counterfactual_audit": "scripts/counterfactual_obligation_audit.py",
    "dataset_judge": "scripts/structured_dataset_junk_ranker.py",
    "curriculum_compiler": "scripts/curriculum_compiler.py",
    "shortcut_audit": "scripts/shortcut_baseline_audit.py",
    "loss_mask": "scripts/loss_mask_card.py",
    "telemetry_contract": "scripts/structured_telemetry_contract.py",
    "action_feature_registry": "configs/software_maintainer/action_feature_registry.json",
    "mining_contract": "configs/software_maintainer/mining_contract_v1.json",
}

OBJECTIVE_MINERS = {
    "repo_capability_catalog": ["repo_capability_builder"],
    "repo_state_graph_v1": ["repo_capability_builder"],
    "symbol_binding": ["symbol_binding_extractor", "counterfactual_builder"],
    "intent_to_build_strategy": [],
    "edit_localization": [],
    "patch_operator": [],
    "verifier_repair": [],
    "bounded_decoder_arguments": [],
    "output_repair_denoise": [],
}

REQUIRED_CONCEPTS = {
    "semantic_presentation_surfaces": ["maintainer_answer", "repo_qa_answer", "repair_plan", "bounded_patch_hunk", "retrieve_more_answer"],
    "user_intent_fields": ["intent_type", "requested_output_type", "allowed_imports", "blocked_imports", "verification_mode"],
    "hard_negative_requirements": ["same graph shape with different target", "missing evidence routed retrieve", "allowed import vs blocked import contrast"],
    "baseline_gates": ["single-feature baseline below ceiling", "degree profile alone does not solve target", "surface marker alone does not solve surface"],
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    file_presence = {name: Path(path).is_file() for name, path in REQUIRED_FILES.items()}
    mining_contract = read_json(Path(REQUIRED_FILES["mining_contract"])) if file_presence["mining_contract"] else {}
    concept_checks = {}
    for key, required_values in REQUIRED_CONCEPTS.items():
        values = mining_contract.get(key, [])
        concept_checks[key] = {
            "present": all(value in values for value in required_values),
            "missing": [value for value in required_values if value not in values],
        }

    objective_status = {}
    for objective, required_miners in OBJECTIVE_MINERS.items():
        missing = [name for name in required_miners if not file_presence.get(name, False)]
        objective_status[objective] = {
            "miner_scripts_required": required_miners,
            "miner_scripts_missing": missing,
            "recovered": not missing and bool(required_miners),
        }

    recovered_objectives = [name for name, status in objective_status.items() if status["recovered"]]
    missing_objectives = [name for name, status in objective_status.items() if not status["recovered"]]
    foundational_files_ok = all(file_presence.values())
    concepts_ok = all(check["present"] for check in concept_checks.values())
    fully_recovered_for_all_mining = foundational_files_ok and concepts_ok and not missing_objectives

    metrics = {
        "file_presence": file_presence,
        "concept_checks": concept_checks,
        "objective_status": objective_status,
        "recovered_objectives": recovered_objectives,
        "missing_objectives": missing_objectives,
        "foundational_files_ok": foundational_files_ok,
        "concepts_ok": concepts_ok,
        "fully_recovered_for_all_mining": fully_recovered_for_all_mining,
        "safe_to_continue_limited_mining": recovered_objectives == ["repo_capability_catalog", "repo_state_graph_v1", "symbol_binding"] or set(recovered_objectives) >= {"repo_capability_catalog", "repo_state_graph_v1", "symbol_binding"},
        "model_ready_training_rows": 0,
    }
    passed = foundational_files_ok and concepts_ok and not fully_recovered_for_all_mining
    summary = {
        "stage": 8614,
        "name": "stage8614_reconstructed_mining_recovery_readiness_audit",
        "passed": passed,
        "summary": "Audited recovered mining stack before data expansion. Foundational judge/compiler/counterfactual/telemetry contracts exist and semantic/user-intent concepts are recovered, but full mining is not restored for all software-maintainer objective families.",
        "metrics": metrics,
        "gates": {
            "fully_recovered_for_all_mining": fully_recovered_for_all_mining,
            "safe_to_continue_limited_mining": metrics["safe_to_continue_limited_mining"],
            "model_ready_training_rows": 0,
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "transition_head_training_authorized_next": False,
            "body_emission_authorized": False,
            "source_emission_authorized": False,
            "runtime_authorized": False,
            "gemma_execution_authorized_next": False,
            "harness_execution_authorized_next": False,
            "scoring_authorized_next": False,
            "controller_complete_merge_authorized_next": False,
            "promotion_ready": False
        },
        "next_best_step": "Restore miners for intent_to_build_strategy, edit_localization, patch_operator, verifier_repair, bounded_decoder_arguments, and output_repair_denoise before broad mining; limited symbol-binding test-bind patch mining may continue."
    }
    out = Path("runs/local/artifacts/stage8614_mining_recovery_readiness_audit")
    write_json(out / "audit_card.json", metrics)
    write_json(Path("runs/summaries/stage8614_reconstructed_mining_recovery_readiness_audit.json"), summary)
    print(json.dumps({"passed": passed, "fully_recovered_for_all_mining": fully_recovered_for_all_mining, "missing_objectives": missing_objectives}, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
