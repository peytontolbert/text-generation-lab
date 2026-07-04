from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

AUTHORITY_CLOSED = {
    "model_execution": False,
    "training": False,
    "runtime": False,
    "source_body_emission": False,
    "scoring_authorized": False,
}

OPERATOR_CATEGORIES = {
    "instruction_intent": ["TASK_INGEST", "GOAL_EXTRACTION", "CONSTRAINT_EXTRACTION", "AMBIGUITY_DETECTION", "ACCEPTANCE_CRITERIA_BUILDER"],
    "software_grounding": ["LANGUAGE_ID", "GRAMMAR_PARSE", "SYMBOL_KIND_CLASSIFIER", "DEFINITION_RESOLVER", "TYPE_SHAPE_EXTRACTOR", "API_CONTRACT_EXTRACTOR"],
    "relationship_graph": ["FILE_TO_MODULE_MAPPER", "IMPORT_DEPENDENCY_EDGE_BUILDER", "CALL_GRAPH_EDGE_BUILDER", "DATAFLOW_EDGE_BUILDER", "TEST_TO_CODE_LINKER", "BLAST_RADIUS_MAPPER"],
    "retrieval_context": ["LEXICAL_RETRIEVER", "STRUCTURAL_RETRIEVER", "NEIGHBORHOOD_RETRIEVER", "HISTORICAL_RETRIEVER", "CONTEXT_PACK_ASSEMBLER", "EVIDENCE_RANKER"],
    "planning": ["SUBTASK_DECOMPOSER", "OPERATOR_ROUTER", "PATCH_SCOPE_PLANNER", "RISK_ESTIMATOR", "FALLBACK_PLANNER", "TOKEN_BUDGET_PLANNER"],
    "synthesis_transform": ["VERBATIM_COPY", "TEMPLATE_INSTANTIATION", "LOCAL_SPAN_EDITOR", "BLOCK_REWRITE", "IMPORT_DEPENDENCY_FIXER", "TEST_GENERATOR"],
    "validation": ["SYNTAX_VALIDATOR", "STATIC_ANALYSIS_RUNNER", "BUILD_VALIDATOR", "UNIT_TEST_SELECTOR", "RUNTIME_SMOKE_RUNNER", "REGRESSION_DETECTOR"],
    "debug_repair": ["FAILURE_TRIAGE", "ROOT_CAUSE_LOCALIZER", "FIX_CANDIDATE_GENERATOR", "FIX_PRIORITIZER", "ITERATIVE_REPAIR_CONTROLLER"],
    "governance": ["CANDIDATE_SCORER_RERANKER", "ABSTAIN_ESCALATE", "RESULT_NARRATOR", "SCOPE_BOUNDARY_ENFORCER"],
    "probabilistic_compression": ["CHOICE_PROBABILITY_ESTIMATOR", "TARGET_CODELENGTH_SCORER", "ENTROPY_BUDGET_ESTIMATOR", "REGRET_ESTIMATOR", "CALIBRATION_CHECKER", "COMPRESSION_GAIN_TRACKER"],
    "candidate_search": ["CANDIDATE_ENUMERATOR", "CANDIDATE_FEATURIZER", "CANDIDATE_EQUIVALENCE_CHECKER", "CANDIDATE_DIVERSITY_CONTROLLER", "BEAM_SEARCH_CONTROLLER", "ORACLE_LEAKAGE_GUARD"],
    "memory_learning": ["REPO_FACT_STORE", "EPISODIC_RUN_MEMORY", "SKILL_CACHE_BUILDER", "RETRIEVAL_UPDATE_OPERATOR", "FORGETTING_CONFLICT_RESOLVER"],
    "semantic_verification": ["SEMANTIC_EQUIVALENCE_CHECKER", "PROPERTY_TEST_BUILDER", "METAMORPHIC_TEST_BUILDER", "API_COMPATIBILITY_CHECKER", "DETERMINISM_CHECKER"],
    "environment_tooling": ["DEPENDENCY_RESOLVER", "ENVIRONMENT_PROBE", "COMMAND_RISK_CLASSIFIER", "ARTIFACT_LOCATOR", "RESOURCE_CONSTRAINT_MONITOR"],
    "version_control_collaboration": ["DIRTY_WORKTREE_AUDITOR", "PATCH_CONFLICT_DETECTOR", "DIFF_EXPLAINER", "ROLLBACK_PLANNER", "COMMIT_PR_PACKAGER", "HANDOFF_SUMMARY_BUILDER"],
}


def operator_inventory() -> dict[str, Any]:
    operators = []
    for category, names in OPERATOR_CATEGORIES.items():
        for name in names:
            operators.append({
                "operator_id": name,
                "category": category,
                "input_contract_required": True,
                "output_contract_required": True,
                "confidence_required": True,
                "failure_modes_required": True,
                "metric_required": True,
                "authority": AUTHORITY_CLOSED,
            })
    return {
        "operator_count": len(operators),
        "category_count": len(OPERATOR_CATEGORIES),
        "categories": {key: len(value) for key, value in sorted(OPERATOR_CATEGORIES.items())},
        "operators": operators,
        "authority": AUTHORITY_CLOSED,
    }


def normalize_probs(probs: Iterable[float]) -> list[float]:
    vals = [max(0.0, float(x)) for x in probs]
    total = sum(vals)
    if total <= 0.0:
        if not vals:
            return []
        return [1.0 / len(vals)] * len(vals)
    return [x / total for x in vals]


def nll_bits(probability: float) -> float:
    return float(-math.log2(max(float(probability), 1e-12)))


def codelength_for_choice(probs: Iterable[float], target_index: int) -> dict[str, Any]:
    p = normalize_probs(probs)
    if not p:
        raise ValueError("probs cannot be empty")
    if target_index < 0 or target_index >= len(p):
        raise IndexError("target_index out of range")
    uniform_bits = math.log2(len(p))
    model_bits = nll_bits(p[target_index])
    best_bits = nll_bits(max(p))
    pred_index = max(range(len(p)), key=lambda i: p[i])
    return {
        "candidate_count": len(p),
        "target_index": target_index,
        "predicted_index": pred_index,
        "correct": pred_index == target_index,
        "target_probability": p[target_index],
        "uniform_bits": uniform_bits,
        "model_nll_bits": model_bits,
        "best_candidate_bits": best_bits,
        "compression_gain_bits": uniform_bits - model_bits,
        "regret_vs_perfect_bits": model_bits,
    }


def codelength_card(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    row_cards = []
    for row in rows:
        card = codelength_for_choice(row.get("probabilities", []), int(row.get("target_index", 0)))
        card["row_id"] = str(row.get("row_id") or row.get("id") or "")
        row_cards.append(card)
    totals = Counter()
    for card in row_cards:
        totals["uniform_bits"] += card["uniform_bits"]
        totals["model_nll_bits"] += card["model_nll_bits"]
        totals["compression_gain_bits"] += card["compression_gain_bits"]
        totals["correct"] += int(card["correct"])
    rows_n = len(row_cards)
    return {
        "rows": rows_n,
        "exact": float(totals["correct"] / max(1, rows_n)),
        "uniform_bits": float(totals["uniform_bits"]),
        "model_nll_bits": float(totals["model_nll_bits"]),
        "compression_gain_bits": float(totals["compression_gain_bits"]),
        "bits_per_row": float(totals["model_nll_bits"] / max(1, rows_n)),
        "row_cards": row_cards,
        "authority": AUTHORITY_CLOSED,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit operator inventory and choice/codelength metrics without model execution.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = read_jsonl(args.input) if args.input else [
        {"row_id": "easy", "probabilities": [0.05, 0.90, 0.03, 0.02], "target_index": 1},
        {"row_id": "miss", "probabilities": [0.60, 0.20, 0.10, 0.10], "target_index": 1},
    ]
    card = {"inventory": operator_inventory(), "codelength": codelength_card(rows), "authority": AUTHORITY_CLOSED}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
