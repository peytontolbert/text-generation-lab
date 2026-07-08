#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9255
NAME = "stage9255_precomputed_repo_state_transformation_spine"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "precomputed_repo_state_transformation_spine.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PRECOMPUTED_REPO_STATE_TRANSFORMATION_SPINE_STAGE9255.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

PRECOMPUTABLE_LAYERS = [
    "ast_cst_structure",
    "symbol_table",
    "import_export_graph",
    "call_graph",
    "dataflow_graph",
    "type_signature_schema_map",
    "test_coverage_graph",
    "runtime_error_index",
    "historical_cochange_graph",
    "patch_affordance_index",
    "blast_radius_map",
    "module_boundary_cache",
    "dependency_capability_cards",
    "task_class_operator_bases",
]

ONLINE_COMPONENTS = [
    "task_intent_observable",
    "current_agent_history",
    "active_causal_subgraph",
    "patch_or_action_choice",
    "verifier_feedback_update",
]

STATE_EQUATIONS = {
    "repo_compilation": "Repo -> Psi_R",
    "task_observable": "Task -> O_q",
    "maintenance_state": "S_t = Contract(Psi_R, O_q, h_t)",
    "policy_action": "a_t = pi_theta(S_t)",
    "incremental_update": "Psi_R -> Psi_{R+Delta} after patch/test feedback",
}

NEXT_OBJECTIVES = [
    "repo_state_compiler_cache_manifest",
    "task_observable_schema",
    "active_subgraph_contraction_packet",
    "edit_affordance_tensor_rows",
    "verifier_feedback_state_update_rows",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card() -> dict:
    checks = {
        "precomputable_layers_sufficient": len(PRECOMPUTABLE_LAYERS) >= 12,
        "online_components_present": len(ONLINE_COMPONENTS) >= 5,
        "state_equations_present": set(STATE_EQUATIONS) == {"repo_compilation", "task_observable", "maintenance_state", "policy_action", "incremental_update"},
        "next_objectives_present": len(NEXT_OBJECTIVES) >= 5,
        "authority_closed": not any(AUTHORITY_CLOSED.values()),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "thesis": "Software maintenance should be trained as task-conditioned transformations over a precomputed repo state, not as raw-context code completion.",
        "state_equations": STATE_EQUATIONS,
        "precomputable_layers": PRECOMPUTABLE_LAYERS,
        "online_components": ONLINE_COMPONENTS,
        "next_objectives": NEXT_OBJECTIVES,
        "training_implication": {
            "weights_store": "software transition operators and navigation policy",
            "retrieval_stores": "long-tail repo/API/paper facts",
            "offline_compiler_stores": "repo structure, constraints, affordances, risks, tests, and failure surface",
            "verifier_stores": "truth signals and feedback for state updates",
        },
        "checks": checks,
        "passed": all(checks.values()),
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    card = build_card()
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": card["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "precomputable_layers": len(PRECOMPUTABLE_LAYERS),
            "online_components": len(ONLINE_COMPONENTS),
            "state_equations": len(STATE_EQUATIONS),
            "next_objectives": len(NEXT_OBJECTIVES),
            "authority_rows": 0,
        },
        "artifacts": {"card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Recorded precomputed repo-state transformation as the next maintainer compiler spine; no execution or training opened.",
        "next_best_step": "Build a repo_state_compiler_cache_manifest design that materializes Psi_R layers without reading /arxiv or opening runtime/training.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    doc_lines = [
        "# Stage9255 Precomputed Repo-State Transformation Spine",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Core thesis: software maintenance should be trained as task-conditioned transformations over a precomputed repo state, not as raw-context code completion.",
        "",
        "State equations:",
    ]
    for key, value in STATE_EQUATIONS.items():
        doc_lines.append(f"- `{key}`: `{value}`")
    doc_lines.extend([
        "",
        "Precomputable repo layers:",
        *[f"- `{item}`" for item in PRECOMPUTABLE_LAYERS],
        "",
        "Online task-time components:",
        *[f"- `{item}`" for item in ONLINE_COMPONENTS],
        "",
        "This stage is architecture/control-plane only. It opens no model execution, training, runtime, Gemma, harness, scoring, mining, source/body emission, cleanup, controller merge, or promotion.",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ])
    DOC.write_text("\n".join(doc_lines), encoding="utf-8")
    marker = "## Stage9255 Precomputed Repo-State Transformation Spine"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + marker + "\n\n" + "Stage9255 records the repo-as-precomputed-state formulation: Repo -> Psi_R, Task -> O_q, S_t = Contract(Psi_R, O_q, h_t), a_t = pi_theta(S_t). This folds the tensor-network/codebase-prior idea into the central maintainer spine without opening execution.\n", encoding="utf-8")
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
