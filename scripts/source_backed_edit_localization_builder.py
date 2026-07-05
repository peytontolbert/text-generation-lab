from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from gate_status_contract import default_gate_status, gate_status_card

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

LOSS_MASK = {
    "surface_role_ce": False,
    "repair_surface_ce": False,
    "build_mode_ce": False,
    "allowed_import_policy_ce": False,
    "blocked_import_policy_ce": False,
    "repo_dependency_policy_ce": False,
    "action_sequence_ce": False,
    "file_plan_ce": False,
    "symbol_binding_ce": False,
    "edit_localization_ce": False,
    "patch_operator_ce": False,
    "verifier_repair_ce": False,
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
}

TARGETS = {"TARGET_FILE", "TARGET_SYMBOL", "TARGET_CONFIG", "TARGET_TEST", "TARGET_ENTRYPOINT", "RETRIEVE_MORE", "ABSTAIN_UNBOUND"}


def opaque(value: str, prefix: str = "o") -> str:
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def lineage_records(path: Path) -> dict[str, dict[str, Any]]:
    records = json.loads(path.read_text(encoding="utf-8"))["records"]
    return {str(record["path"]): record for record in records}


def _source_lineage(lin_by_path: dict[str, dict[str, Any]]) -> dict[str, Any]:
    nodes = lin_by_path["/arxiv/TOLBERT_BRAIN/data/repos/nodes_repos.jsonl"]
    spans = lin_by_path["/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl"]
    levels = lin_by_path.get("/arxiv/TOLBERT_BRAIN/data/repos/level_sizes_repos.json", nodes)
    return {
        "graph_nodes_source_id": nodes["source_id"],
        "graph_nodes_lineage_hash": nodes["lineage_hash"],
        "graph_spans_source_id": spans["source_id"],
        "graph_spans_lineage_hash": spans["lineage_hash"],
        "graph_level_sizes_source_id": levels["source_id"],
        "graph_level_sizes_lineage_hash": levels["lineage_hash"],
        "locked_eval_source": False,
        "train_eligible_lineage": True,
        "raw_source_in_model_input": False,
    }


def build_source_backed_rows(neutral_rows: list[dict[str, Any]], lineage_path: Path) -> list[dict[str, Any]]:
    lin = lineage_records(lineage_path)
    source_lineage = _source_lineage(lin)
    rows: list[dict[str, Any]] = []
    for neutral in neutral_rows:
        clean = dict(neutral.get("clean_state") or {})
        target = clean.get("edit_localization_target")
        if target not in TARGETS:
            continue
        state = dict(neutral.get("corrupted_state") or {})
        graph_packet = dict(state.get("graph_packet") or {})
        old_id = str(neutral.get("row_id") or neutral.get("semantic_key") or len(rows))
        row_id = "stage8765_" + opaque(old_id, "row")
        query_node_id = opaque(f"query:{old_id}", "node")
        candidate_family_id = opaque(f"candidates:{state.get('language')}:{state.get('task_observation')}:{graph_packet.get('query_node_type')}", "cand")
        visible_state = {
            "task_family": "edit_localization",
            "language": state.get("language"),
            "file_extension": state.get("file_extension"),
            "task_observation": state.get("task_observation"),
            "visible_locality_evidence": state.get("visible_locality_evidence"),
            "locality_signal": state.get("locality_signal"),
            "neutral_context_bits": state.get("neutral_context_bits"),
            "budget": state.get("budget"),
        }
        graph_input = {
            "opaque_graph_id": opaque(str(graph_packet.get("opaque_graph_id")), "graph"),
            "query_node_type": graph_packet.get("query_node_type"),
            "edge_family_count": graph_packet.get("edge_family_count"),
            "candidate_node_count": graph_packet.get("candidate_node_count"),
            "candidate_family_id": candidate_family_id,
            "source_graph_materialized": False,
        }
        row = {
            "row_id": row_id,
            "split": neutral.get("split"),
            "objective_family": "source_backed_edit_localization",
            "route": "CANDIDATE_NEEDS_AUDIT",
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK),
            "gate_status": default_gate_status(
                source_inventory_lineage=True,
                source_provenance=True,
                golden_locked_eval_suite=True,
            ),
            "source_backed": True,
            "source_stage": "stage8765_from_stage8636_with_repo_graph_lineage_controls",
            "source_row_ref": {
                "source_stage": neutral.get("source_stage"),
                "source_row_id_hash": opaque(old_id, "srcrow"),
                "source_row_id_in_model_input": False,
            },
            "semantic_key": f"{neutral.get('split')}:{state.get('language')}:{opaque(old_id, 'sem')}",
            "source_lineage": dict(source_lineage),
            "graph_input": graph_input,
            "query": {
                "query_kind": graph_packet.get("query_node_type"),
                "query_node_id": query_node_id,
                "query_node_id_is_opaque": True,
            },
            "corrupted_state": visible_state,
            "clean_state": {
                "edit_localization_target": target,
                "action_sequence": clean.get("action_sequence"),
                "file_plan": clean.get("file_plan"),
            },
            "anti_cheat": {
                "raw_source_included": False,
                "raw_symbol_names_in_model_input": False,
                "target_label_in_id": False,
                "target_path_in_model_input": False,
                "source_row_id_in_model_input": False,
                "requires_shortcut_audit_before_training": True,
                "requires_recovered_gate_status_before_compiler": True,
            },
        }
        rows.append(row)
    return rows


def build_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    targets = Counter((row.get("clean_state") or {}).get("edit_localization_target") for row in rows)
    splits = Counter(row.get("split") for row in rows)
    languages = Counter((row.get("corrupted_state") or {}).get("language") for row in rows)
    gate_card = gate_status_card(rows)
    return {
        "rows": len(rows),
        "targets": dict(sorted(targets.items())),
        "splits": dict(sorted(splits.items())),
        "languages": dict(sorted(languages.items())),
        "gate_status": gate_card,
        "authority_rows": sum(int(any((row.get("authority") or {}).values())) for row in rows),
        "training_loss_rows": sum(int(any((row.get("loss_mask") or {}).values())) for row in rows),
    }
