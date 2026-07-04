from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LINEAGE = ROOT / "configs/software_maintainer/source_inventory_lineage_registry_stage8663.json"


def load_source_registry(path: Path = DEFAULT_LINEAGE) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text())
    records = data.get("records")
    if not isinstance(records, list):
        raise ValueError(f"missing records in {path}")
    return {str(record["source_id"]): record for record in records if isinstance(record, dict) and record.get("source_id")}


def locked_source_ids(registry: dict[str, dict[str, Any]]) -> set[str]:
    return {source_id for source_id, record in registry.items() if record.get("locked_eval") or record.get("hidden_final")}


def train_eligible_source_ids(registry: dict[str, dict[str, Any]]) -> set[str]:
    return {source_id for source_id, record in registry.items() if record.get("train_eligible") is True and not record.get("locked_eval") and not record.get("hidden_final")}


def source_ids_from_row(row: dict[str, Any]) -> set[str]:
    lineage = row.get("source_lineage") if isinstance(row.get("source_lineage"), dict) else {}
    ids = set()
    for key in ["source_id", "graph_nodes_source_id", "graph_spans_source_id", "retrieval_source_id", "dataset_source_id"]:
        value = lineage.get(key) or row.get(key)
        if isinstance(value, str) and value:
            ids.add(value)
    return ids


def evaluate_row_source_lineage(row: dict[str, Any], registry: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    registry = registry or load_source_registry()
    ids = source_ids_from_row(row)
    unknown = sorted(source_id for source_id in ids if source_id not in registry)
    locked = sorted(source_id for source_id in ids if registry.get(source_id, {}).get("locked_eval") or registry.get(source_id, {}).get("hidden_final"))
    ineligible = sorted(
        source_id
        for source_id in ids
        if source_id in registry and registry[source_id].get("train_eligible") is not True
    )
    train_eligible = bool(ids) and not unknown and not locked and not ineligible
    return {
        "row_id": row.get("row_id") or row.get("id") or "",
        "source_ids": sorted(ids),
        "unknown_source_ids": unknown,
        "locked_source_ids": locked,
        "train_ineligible_source_ids": ineligible,
        "train_eligible_lineage": train_eligible,
        "blocked_training_reason": (
            "unknown_source_id" if unknown else "locked_eval_source" if locked else "train_ineligible_source" if ineligible else None
        ),
    }


def assert_row_train_source_allowed(row: dict[str, Any], registry: dict[str, dict[str, Any]] | None = None) -> None:
    result = evaluate_row_source_lineage(row, registry)
    if not result["train_eligible_lineage"]:
        raise ValueError(f"row source lineage not train-eligible: {result}")
