#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"

STAGE = 11472
NAME = "stage11472_controlled_residual_lab_contract"
OUT = ART / NAME
SUMMARY = OUT / "controlled_residual_lab_contract.json"

SCOREBOARD = ART / "stage11471_frontier_progress_scoreboard/frontier_progress_scoreboard.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def residual_family(row_id: str, target: str | None, predicted: str | None) -> str:
    lowered = row_id.lower()
    if "rust" in lowered and "symptom_or_call_path_analogue" in lowered:
        return "rust_symptom_call_path_vs_candidate_surface"
    if "python" in lowered and "evidence_b_vs_f" in lowered:
        return "python_evidence_verifier_constraint_vs_candidate_surface"
    if "cpp" in lowered or "c_cpp" in lowered or "parametergolf" in lowered:
        return "cpp_evidence_verifier_constraint_vs_candidate_surface"
    return f"residual_target_{target}_predicted_{predicted}"


def main() -> None:
    scoreboard = load_json(SCOREBOARD)
    residual = ((scoreboard.get("scoreboards") or {}).get("frontier") or {}).get("residual_bank") or {}
    misses = [m for m in residual.get("misses") or [] if isinstance(m, dict)]

    families: dict[str, dict[str, Any]] = {}
    for miss in misses:
        family = residual_family(
            str(miss.get("row_id") or ""),
            miss.get("target"),
            miss.get("predicted"),
        )
        bucket = families.setdefault(
            family,
            {
                "family_id": family,
                "frozen_miss_count": 0,
                "frozen_miss_rows": [],
                "required_disjoint_analogue_roots": 10,
                "target_train_analogue_rows": "20-50",
                "candidate_roles_required": [
                    "candidate_change_surface",
                    "verifier_and_test_constraint",
                    "symptom_or_call_path_analogue",
                    "insufficient_evidence",
                ],
            },
        )
        bucket["frozen_miss_count"] += 1
        bucket["frozen_miss_rows"].append(miss)

    hypotheses = [
        {
            "hypothesis_id": "H_data_geometry",
            "failure_mechanism": "Residual misses persist because disjoint analogues do not expose enough role-balanced hard negatives.",
            "intervention_variable": "data supply only",
            "allowed_change": "Add disjoint roots with verifier/test/source-backed candidate sets; keep selected scorer and loss unchanged.",
            "success_signal": "sealed residual analogues improve while Stage11471 preservation gates remain true.",
        },
        {
            "hypothesis_id": "H_pairwise_margin",
            "failure_mechanism": "Generic row CE does not separate correct role from hardest wrong same-root candidate.",
            "intervention_variable": "objective",
            "allowed_change": "Add pairwise margin loss score(correct) > score(hardest_wrong_same_root).",
            "success_signal": "correct-vs-candidate_change_surface and correct-vs-verifier_constraint margins increase on heldout analogues.",
        },
        {
            "hypothesis_id": "H_listwise_same_root",
            "failure_mechanism": "Candidate scores are calibrated poorly across options within the same root.",
            "intervention_variable": "objective",
            "allowed_change": "Add listwise softmax over root-local candidates.",
            "success_signal": "top-1 and margins improve on sealed same-root candidate sets without strict regression.",
        },
        {
            "hypothesis_id": "H_scorer_capacity",
            "failure_mechanism": "The base scorer head cannot represent evidence-role distinctions without targeted adaptation.",
            "intervention_variable": "trainable parameters",
            "allowed_change": "Freeze encoder and train scorer head only; then try low-LR encoder only if scorer-head margins move.",
            "success_signal": "scorer-head-only moves sealed residual margins before any full-model update.",
        },
    ]

    experiment_matrix = [
        {
            "experiment_id": "A_data_only_current_loss",
            "tests_hypothesis": "H_data_geometry",
            "changes": ["disjoint residual analogues"],
            "frozen_components": ["selected scorer", "loss", "runtime architecture"],
        },
        {
            "experiment_id": "B_data_pairwise_margin",
            "tests_hypothesis": "H_pairwise_margin",
            "changes": ["disjoint residual analogues", "pairwise margin loss"],
            "frozen_components": ["selected scorer", "candidate schema"],
        },
        {
            "experiment_id": "C_data_listwise_same_root",
            "tests_hypothesis": "H_listwise_same_root",
            "changes": ["disjoint residual analogues", "listwise same-root candidate loss"],
            "frozen_components": ["selected scorer", "candidate schema"],
        },
        {
            "experiment_id": "D_margin_with_replay_preservation",
            "tests_hypothesis": "H_pairwise_margin",
            "changes": ["pairwise/listwise objective", "explicit old-canary replay preservation"],
            "frozen_components": ["selected scorer"],
        },
        {
            "experiment_id": "E_scorer_head_only",
            "tests_hypothesis": "H_scorer_capacity",
            "changes": ["freeze encoder", "train scorer head only"],
            "frozen_components": ["encoder", "selected product scorer interface"],
        },
        {
            "experiment_id": "F_low_lr_encoder_after_head_signal",
            "tests_hypothesis": "H_scorer_capacity",
            "changes": ["low-LR encoder"],
            "entry_condition": "E_scorer_head_only improves heldout residual margins",
        },
    ]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "controlled_residual_lab_required_before_more_training",
        "baseline": {
            "selected_frontier": "stage11444 + encoder_option_retrieval",
            "scoreboard": rel(SCOREBOARD),
            "current_residual_score": {
                "correct": residual.get("correct"),
                "rows": residual.get("rows"),
            },
            "current_status": scoreboard.get("selected_frontier_status"),
        },
        "residual_families": sorted(families.values(), key=lambda item: item["family_id"]),
        "required_residual_50_shape": {
            "frozen_miss_usage": "eval only; do not train directly on frozen misses",
            "families": "all residual families listed in this contract",
            "fresh_roots_per_family": 10,
            "total_fresh_roots": 10 * max(1, len(families)),
            "rows_per_family": "20-50 disjoint analogue rows",
            "split_rule": "root/repo/family separated before row projection",
            "candidate_set_rule": "each root must include the same semantic candidate roles and hard negatives",
            "required_evidence": [
                "source snippet",
                "selected test or verifier anchor",
                "role-distinct evidence ledger",
                "counterfactual or insufficiency variant where applicable",
            ],
        },
        "hypotheses": hypotheses,
        "experiment_matrix": experiment_matrix,
        "promotion_requirements": {
            "old_canary_strict": "23/23",
            "filtered_strict": "22/22",
            "filtered_validation": ">=20/22",
            "old_canary_validation": ">=21/23",
            "frozen_residual_bank": ">=6/10",
            "sealed_residual_analogue": "above Stage11444 baseline",
            "full_scored_coverage": True,
            "root_overlap": "none",
            "product_scorer": "encoder_option_retrieval",
            "decoder_first_step_luck_allowed": False,
        },
        "stop_conditions": [
            "canary improves but frozen residual remains flat for two controlled probes",
            "frozen residual improves but filtered strict or old canary strict regresses twice",
            "sealed analogue improves but frozen residual does not move",
            "semantic head wins but base product scorer fails",
            "the same pattern needs more than three special-case scorer patches",
        ],
        "pre_training_run_template": {
            "required_fields": [
                "failure_family",
                "failure_mechanism",
                "single_changed_variable",
                "frozen_controls",
                "train_roots",
                "sealed_eval_roots",
                "promotion_metric",
                "regression_gates",
            ],
            "forbidden": [
                "generic support package without named residual family",
                "mixed intervention that changes data, objective, scorer, and context at once",
                "promotion on same residual rows used for training",
            ],
        },
        "outputs": {"summary": rel(SUMMARY)},
    }

    write_json(SUMMARY, payload)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "residual_families": list(families),
                "experiment_count": len(experiment_matrix),
                "promotion_residual_threshold": payload["promotion_requirements"]["frozen_residual_bank"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
