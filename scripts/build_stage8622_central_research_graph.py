#!/usr/bin/env python3
"""Build a recovered central research graph for the 100M maintainer project.

This is a documentation/control-plane artifact only. It does not execute models,
load checkpoints, or authorize training. The goal is to make the recovered
research variables queryable from one machine-readable graph.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs" / "software_maintainer"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8622_central_research_graph"
SUMMARY_PATH = ROOT / "runs" / "summaries" / "stage8622_reconstructed_central_research_graph.json"
DOC_PATH = ROOT / "docs" / "CENTRAL_RESEARCH_GRAPH_STAGE8622.md"


AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


CENTRAL_SPINE = [
    "final_objective_100m_software_maintainer",
    "structured_policy",
    "repo_state_graph_v1",
    "symbol_binding",
    "edit_localization",
    "patch_operator",
    "verifier_repair",
    "bounded_decoder_arguments",
    "bounded_decoder_ce_probe",
    "output_repair_denoise",
    "controlled_maintainer_loop",
    "product_harness_integration",
]


RECOVERY_DOCS = [
    "docs/CURRENT_RESEARCH_SPINE_RECONSTRUCTED.md",
    "docs/recovery_v27_100m/00_central_research_spine.md",
    "docs/recovery_v27_100m/03_curriculum_compiler_and_dataset_judge.md",
    "docs/recovery_v27_100m/04_repo_graph_and_maintenance_cognition.md",
    "docs/recovery_v27_100m/11_decoder_stage_deep_reconstruction.md",
    "docs/RECOVERED_VARIABLE_LEDGER_STAGE8615.md",
    "docs/RECOVERED_TRAINING_MINING_GAP_MATRIX_STAGE8616.md",
    "docs/SPINE_LEDGER_SESSION_SCRAPE_STAGE8620.md",
    "docs/MODEL_FAMILY_SCHEMA_RECOVERY_STAGE8621.md",
    "docs/SYMBOL_BINDING_RECOVERY_STATUS.md",
    "docs/MINING_AND_TRAINING_RECOVERY_GAP_STATUS.md",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def node_id(kind: str, name: str) -> str:
    normalized = (
        str(name)
        .strip()
        .replace(" ", "_")
        .replace("/", "_")
        .replace(":", "_")
        .replace("|", "_")
    )
    return f"{kind}:{normalized}"


class Graph:
    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []
        self._edge_seen: set[tuple[str, str, str]] = set()

    def add_node(self, kind: str, name: str, **attrs: Any) -> str:
        nid = node_id(kind, name)
        existing = self.nodes.get(nid, {})
        merged = {
            "id": nid,
            "kind": kind,
            "name": name,
            **existing,
            **{k: v for k, v in attrs.items() if v is not None},
        }
        self.nodes[nid] = merged
        return nid

    def add_edge(self, source: str, relation: str, target: str, **attrs: Any) -> None:
        key = (source, relation, target)
        if key in self._edge_seen:
            return
        self._edge_seen.add(key)
        self.edges.append(
            {
                "source": source,
                "relation": relation,
                "target": target,
                **{k: v for k, v in attrs.items() if v is not None},
            }
        )


def add_list_nodes(
    graph: Graph,
    parent: str,
    relation: str,
    kind: str,
    values: list[str],
    source: str,
) -> None:
    for value in values:
        nid = graph.add_node(kind, value, recovered_from=source)
        graph.add_edge(parent, relation, nid, evidence_source=source)


def add_authority_nodes(graph: Graph) -> None:
    authority_parent = graph.add_node(
        "contract",
        "hard_authority_closed",
        description="All execution/training/product authority remains false until explicit later gates.",
    )
    for flag, value in AUTHORITY_CLOSED.items():
        nid = graph.add_node("authority_flag", flag, value=value)
        graph.add_edge(authority_parent, "sets_false", nid, evidence_source="stage8622")


def add_spine(graph: Graph) -> None:
    final = graph.add_node(
        "final_objective",
        "100M software maintainer",
        description="A 100M-class model stack that can maintain software through structured policy, repo graph reasoning, bounded generation, verifier repair, and controlled product harness integration.",
    )
    previous = final
    for item in CENTRAL_SPINE[1:]:
        nid = graph.add_node("architecture_layer", item)
        graph.add_edge(previous, "requires_next", nid, evidence_source="recovered_central_spine")
        previous = nid


def add_config_registry(graph: Graph, action_registry: dict[str, Any]) -> None:
    root = graph.add_node("registry", "action_feature_registry", path="configs/software_maintainer/action_feature_registry.json")
    list_fields = {
        "objective_families": ("declares_objective", "objective_family"),
        "structured_fields": ("declares_field", "structured_field"),
        "build_modes": ("declares_build_mode", "build_mode"),
        "binding_actions": ("declares_binding_action", "binding_action"),
        "edit_localization_targets": ("declares_edit_target", "edit_target"),
        "patch_operators": ("declares_patch_operator", "patch_operator"),
        "verifier_repair_actions": ("declares_verifier_action", "verifier_repair_action"),
        "high_level_actions": ("declares_high_level_action", "action_label"),
        "software_build_actions": ("declares_build_action", "software_build_action"),
        "curriculum_routes": ("declares_route", "curriculum_route"),
        "dataset_judge_signals": ("declares_judge_signal", "dataset_judge_signal"),
        "gate_features": ("declares_gate_feature", "gate_feature"),
        "derived_fields": ("declares_derived_field", "derived_field"),
        "recovered_behavior_value_labels": ("declares_behavior_value", "behavior_value_label"),
        "recovered_control_labels": ("declares_control_label", "control_label"),
        "recovered_evidence_labels": ("declares_evidence_label", "evidence_label"),
        "recovered_graph_family_labels": ("declares_graph_family", "graph_family"),
    }
    for field, (relation, kind) in list_fields.items():
        values = action_registry.get(field, [])
        if isinstance(values, list):
            add_list_nodes(graph, root, relation, kind, values, "action_feature_registry")

    for route, losses in action_registry.get("loss_policy", {}).items():
        route_node = graph.add_node("curriculum_route", route, recovered_from="action_feature_registry.loss_policy")
        graph.add_edge(root, "sets_loss_policy_for", route_node, evidence_source="action_feature_registry.loss_policy")
        for loss in losses:
            loss_node = graph.add_node("loss", loss)
            graph.add_edge(route_node, "enables_loss", loss_node, evidence_source="action_feature_registry.loss_policy")

    repo_graph = action_registry.get("repo_state_graph_v1", {})
    repo_node = graph.add_node("objective_family", "repo_state_graph_v1")
    for node_type in repo_graph.get("node_types", []):
        graph.add_edge(repo_node, "allows_node_type", graph.add_node("repo_graph_node_type", node_type), evidence_source="repo_state_graph_v1")
    for edge_type in repo_graph.get("edge_types", []):
        graph.add_edge(repo_node, "allows_edge_type", graph.add_node("repo_graph_edge_type", edge_type), evidence_source="repo_state_graph_v1")
    for rule in repo_graph.get("anti_cheat_rules", []):
        graph.add_edge(repo_node, "requires_anti_cheat_rule", graph.add_node("anti_cheat_rule", rule), evidence_source="repo_state_graph_v1")


def add_mining_contract(graph: Graph, mining_contract: dict[str, Any]) -> None:
    root = graph.add_node("contract", "mining_contract_v1", path="configs/software_maintainer/mining_contract_v1.json")
    for field in [
        "mining_must_remain_closed_until",
        "mining_required_cards",
        "hard_negative_requirements",
        "baseline_gates",
        "training_blockers_before_mining",
    ]:
        for item in mining_contract.get(field, []):
            nid = graph.add_node(field.rstrip("s"), item, recovered_from="mining_contract_v1")
            graph.add_edge(root, "requires", nid, evidence_source="mining_contract_v1")
    for family, spec in mining_contract.get("mining_families", {}).items():
        family_node = graph.add_node("objective_family", family, evidence_source=spec.get("source"))
        graph.add_edge(root, "declares_mining_family", family_node, evidence_source="mining_contract_v1")
        for output in spec.get("outputs", []):
            graph.add_edge(family_node, "produces", graph.add_node("manifest_output", output), evidence_source="mining_contract_v1")
        for cf in spec.get("required_counterfactuals", []):
            graph.add_edge(family_node, "requires_counterfactual", graph.add_node("counterfactual_obligation", cf), evidence_source="mining_contract_v1")


def add_model_family_registry(graph: Graph, registry: dict[str, Any]) -> None:
    root = graph.add_node("registry", "model_family_stack_registry", path="configs/software_maintainer/model_family_stack_registry.json")
    for phase in registry.get("loop_phases", []):
        graph.add_edge(root, "declares_loop_phase", graph.add_node("loop_phase", phase), evidence_source="model_family_stack_registry")
    for family, spec in registry.get("model_families", {}).items():
        family_node = graph.add_node("model_family", family, role=spec.get("role"), placement=spec.get("placement"))
        graph.add_edge(root, "declares_model_family", family_node, evidence_source="model_family_stack_registry")
        for phase in spec.get("phase", []):
            graph.add_edge(family_node, "serves_phase", graph.add_node("loop_phase", phase), evidence_source="model_family_stack_registry")
        for output in spec.get("outputs", []):
            graph.add_edge(family_node, "emits_signal", graph.add_node("model_signal", output), evidence_source="model_family_stack_registry")
    fusion = registry.get("fusion_contract", {})
    fusion_node = graph.add_node("contract", "fusion_contract_v1", hard_rule=fusion.get("hard_rule"))
    graph.add_edge(root, "declares_fusion_contract", fusion_node, evidence_source="model_family_stack_registry")
    for output, inputs in fusion.items():
        if output == "hard_rule":
            continue
        output_node = graph.add_node("fusion_output", output)
        graph.add_edge(fusion_node, "produces", output_node, evidence_source="model_family_stack_registry")
        for item in inputs:
            graph.add_edge(graph.add_node("fusion_input", item), "feeds", output_node, evidence_source="model_family_stack_registry")


def add_stage_summaries(graph: Graph) -> tuple[int, int, list[int]]:
    summaries = sorted((ROOT / "runs" / "summaries").glob("*.json"))
    authority_true = 0
    parsed = 0
    stages: list[int] = []
    for path in summaries:
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        parsed += 1
        stage = data.get("stage")
        if isinstance(stage, int):
            stages.append(stage)
        stage_name = data.get("stage_name", path.stem)
        stage_node = graph.add_node(
            "stage",
            str(stage if stage is not None else path.stem),
            stage_name=stage_name,
            passed=data.get("passed"),
            path=str(path.relative_to(ROOT)),
            next_best_step=data.get("next_best_step"),
        )
        for key, value in data.get("authority", {}).items():
            if value is True:
                authority_true += 1
            flag = graph.add_node("authority_flag", key, value=value)
            graph.add_edge(stage_node, "reports_authority", flag, evidence_source=path.name)
        next_step = data.get("next_best_step")
        if next_step:
            graph.add_edge(stage_node, "points_to_next", graph.add_node("next_step", next_step), evidence_source=path.name)
    return parsed, authority_true, stages


def add_docs(graph: Graph) -> int:
    count = 0
    for rel in RECOVERY_DOCS:
        path = ROOT / rel
        if path.exists():
            count += 1
            doc = graph.add_node("doc", rel, path=rel)
            graph.add_edge(graph.add_node("final_objective", "100M software maintainer"), "documented_in", doc, evidence_source="stage8622")
    return count


def write_doc(graph: Graph, metrics: dict[str, Any]) -> None:
    layer_lines = []
    for idx, item in enumerate(CENTRAL_SPINE):
        label = "100M software maintainer" if idx == 0 else item
        layer_lines.append(f"{idx + 1}. `{label}`")

    kind_counts: dict[str, int] = {}
    for node in graph.nodes.values():
        kind_counts[node["kind"]] = kind_counts.get(node["kind"], 0) + 1

    top_kinds = "\n".join(f"- `{kind}`: {count}" for kind, count in sorted(kind_counts.items()))

    DOC_PATH.write_text(
        "\n".join(
            [
                "# Stage8622 Central Research Graph",
                "",
                "This file records the recovered central graph for the 100M software-maintainer research program. It is a control-plane and documentation artifact only; it does not authorize training, runtime, source/body emission, Gemma, harness, scoring, promotion, or decoder CE.",
                "",
                "## Central Spine",
                "",
                *layer_lines,
                "",
                "## What The Graph Contains",
                "",
                top_kinds,
                "",
                "## Recovered Laws",
                "",
                "- Learned logits propose; deterministic gates and verifiers authorize.",
                "- Budget safety is deterministic row fact, not learned authority.",
                "- Long outputs stay in holdout unless a separate chunked/long-output curriculum exists.",
                "- Decoder CE only applies to `KEEP_BOUNDED_DECODER` rows with explicit loss masks and cap compliance.",
                "- Mining remains closed until source inventory, judge route, objective family, authority card, loss mask, counterfactuals, shortcut audit, duplicate key audit, split policy, and telemetry contract exist.",
                "- Repo graph IDs, node IDs, and edge IDs must not encode objective labels.",
                "",
                "## Artifacts",
                "",
                f"- `runs/local/artifacts/stage8622_central_research_graph/central_research_graph.json`",
                f"- `runs/local/artifacts/stage8622_central_research_graph/central_research_nodes.jsonl`",
                f"- `runs/local/artifacts/stage8622_central_research_graph/central_research_edges.jsonl`",
                f"- `runs/summaries/stage8622_reconstructed_central_research_graph.json`",
                "",
                "## Metrics",
                "",
                "```json",
                json.dumps(metrics, indent=2, sort_keys=True),
                "```",
                "",
                "## Next Recovery Step",
                "",
                "Scrape `/arxiv` targeted long-term storage for ledgers, old session mirrors, preserved checkpoints/manifests, and any research-spine documents, then attach those sources to this graph as recovery-source nodes.",
                "",
            ]
        )
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)

    action_registry = load_json(CONFIG_DIR / "action_feature_registry.json")
    mining_contract = load_json(CONFIG_DIR / "mining_contract_v1.json")
    model_registry = load_json(CONFIG_DIR / "model_family_stack_registry.json")

    graph = Graph()
    add_spine(graph)
    add_authority_nodes(graph)
    add_config_registry(graph, action_registry)
    add_mining_contract(graph, mining_contract)
    add_model_family_registry(graph, model_registry)
    summary_count, authority_true, stage_ids = add_stage_summaries(graph)
    doc_count = add_docs(graph)

    generated_at = datetime.now(timezone.utc).isoformat()
    graph_doc = {
        "version": "stage8622_reconstructed_central_research_graph_v1",
        "generated_at": generated_at,
        "authority": AUTHORITY_CLOSED,
        "central_spine": CENTRAL_SPINE,
        "nodes": sorted(graph.nodes.values(), key=lambda n: n["id"]),
        "edges": sorted(graph.edges, key=lambda e: (e["source"], e["relation"], e["target"])),
    }
    (OUT_DIR / "central_research_graph.json").write_text(json.dumps(graph_doc, indent=2, sort_keys=True))
    with (OUT_DIR / "central_research_nodes.jsonl").open("w") as f:
        for node in graph_doc["nodes"]:
            f.write(json.dumps(node, sort_keys=True) + "\n")
    with (OUT_DIR / "central_research_edges.jsonl").open("w") as f:
        for edge in graph_doc["edges"]:
            f.write(json.dumps(edge, sort_keys=True) + "\n")

    metrics = {
        "nodes": len(graph.nodes),
        "edges": len(graph.edges),
        "stage_summaries_parsed": summary_count,
        "docs_attached": doc_count,
        "authority_true_reports_seen": authority_true,
        "latest_stage_seen": max(stage_ids) if stage_ids else None,
        "objective_families": len(action_registry.get("objective_families", [])),
        "structured_fields": len(action_registry.get("structured_fields", [])),
        "curriculum_routes": len(action_registry.get("curriculum_routes", [])),
        "dataset_judge_signals": len(action_registry.get("dataset_judge_signals", [])),
        "gate_features": len(action_registry.get("gate_features", [])),
        "model_families": len(model_registry.get("model_families", {})),
        "mining_families": len(mining_contract.get("mining_families", {})),
    }
    write_doc(graph, metrics)

    summary = {
        "stage": 8622,
        "stage_name": "stage8622_reconstructed_central_research_graph",
        "passed": True,
        "reconstructed": True,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "gates": {
            "central_graph_written": True,
            "machine_readable_nodes_edges_written": True,
            "authority_closed": authority_true == 0,
            "training_authorized": False,
            "model_execution_authorized": False,
        },
        "artifacts": {
            "graph": str((OUT_DIR / "central_research_graph.json").relative_to(ROOT)),
            "nodes": str((OUT_DIR / "central_research_nodes.jsonl").relative_to(ROOT)),
            "edges": str((OUT_DIR / "central_research_edges.jsonl").relative_to(ROOT)),
            "doc": str(DOC_PATH.relative_to(ROOT)),
        },
        "next_best_step": "Targeted /arxiv long-term storage scrape and optional non-destructive mirror of longevity docs under /arxiv.",
        "notes": "This is the central recovered graph for research variables, objective families, routes, gates, model families, and stage summaries. It is schema/control-plane recovery only.",
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(json.dumps({"passed": True, "metrics": metrics, "summary": str(SUMMARY_PATH)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
