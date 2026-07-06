#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9033
NAME = "stage9033_operator_detail_seed_catalog"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9030_SUMMARY = ROOT / "runs/summaries/stage9030_operator_detail_schema_gap_audit.json"
SOURCE_9032_SUMMARY = ROOT / "runs/summaries/stage9032_operator_detail_reference_contract.json"
SOURCE_SESSION_GREP = ROOT / "runs/summaries/stage8703_low_level_training_concept_session_grep.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPERATOR_DETAIL_SEED_CATALOG_STAGE9033.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CATALOG = OUT_DIR / "operator_detail_seed_catalog.json"

DETAIL_FIELDS_REQUIRED_FOR_TRAINING_ROADMAP = [
    "id",
    "name",
    "layer",
    "inputs",
    "outputs",
    "confidence_score",
    "failure_modes",
    "training_label_source",
    "metric",
]

RECOVERED_METADATA_FIELDS = ["id", "name", "layer", "layer_role", "operator_category"]
MISSING_DETAIL_FIELDS = [
    field for field in DETAIL_FIELDS_REQUIRED_FOR_TRAINING_ROADMAP if field not in {"id", "name", "layer"}
]

LAYER_TO_ROLE = {
    "A": "instruction_intake_and_scope_control",
    "B": "code_semantic_parsing",
    "C": "repo_relationship_graph",
    "D": "retrieval_and_context_packing",
    "E": "planning_and_control",
    "F": "candidate_search_and_selection",
    "G": "synthesis_and_edit_transform",
    "H": "validation_and_verification",
    "I": "probabilistic_compression_and_calibration",
    "J": "memory_and_learning",
    "K": "environment_and_tooling",
    "L": "version_control_and_collaboration",
}

LAYER_TO_CATEGORY = {
    "A": "instruction_intent",
    "B": "software_grounding",
    "C": "relationship_graph",
    "D": "retrieval_context",
    "E": "planning",
    "F": "candidate_search",
    "G": "synthesis_transform",
    "H": "validation",
    "I": "probabilistic_compression",
    "J": "memory_learning",
    "K": "environment_tooling",
    "L": "version_control_collaboration",
}

OPERATOR_LINE_RE = re.compile(r"\b(OP\d{3})\t([a-z0-9_]+)\t([A-L])\b")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def recover_operator_rows(session_text: str) -> list[dict[str, Any]]:
    session_text = (
        session_text.replace("\\\\t", "\t")
        .replace("\\\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\n", "\n")
    )
    rows_by_id: dict[str, dict[str, Any]] = {}
    for match in OPERATOR_LINE_RE.finditer(session_text):
        operator_id, name, layer = match.groups()
        rows_by_id[operator_id] = {
            "id": operator_id,
            "name": name,
            "layer": layer,
            "layer_role": LAYER_TO_ROLE[layer],
            "operator_category": LAYER_TO_CATEGORY[layer],
            "operator_schema_version": "operator_detail_seed_v0_reconstructed",
            "detail_status": "name_layer_recovered_metadata_only",
            "recovered_metadata_fields": RECOVERED_METADATA_FIELDS,
            "missing_detail_fields_before_training": MISSING_DETAIL_FIELDS,
            "detail_required_before_mining": True,
            "detail_required_before_operator_specific_training": True,
            "detail_source_stage": "stage8703_low_level_training_concept_session_grep",
            "detail_hash": None,
        }
    return [rows_by_id[key] for key in sorted(rows_by_id)]


def build_catalog(registry: dict[str, Any]) -> dict[str, Any]:
    s9030 = load_json(SOURCE_9030_SUMMARY)
    s9032 = load_json(SOURCE_9032_SUMMARY)
    session_text_present = SOURCE_SESSION_GREP.exists()
    session_text = SOURCE_SESSION_GREP.read_text(encoding="utf-8", errors="replace") if session_text_present else ""
    rows = recover_operator_rows(session_text)
    layer_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for row in rows:
        layer_counts[row["layer"]] = layer_counts.get(row["layer"], 0) + 1
        category_counts[row["operator_category"]] = category_counts.get(row["operator_category"], 0) + 1
    expected_ids = {f"OP{index:03d}" for index in range(1, 109)}
    recovered_ids = {row["id"] for row in rows}
    checks = {
        "source_stage9030_present": SOURCE_9030_SUMMARY.exists(),
        "source_stage9030_passed": s9030.get("passed") is True,
        "source_stage9032_present": SOURCE_9032_SUMMARY.exists(),
        "source_stage9032_passed": s9032.get("passed") is True,
        "source_session_grep_present": session_text_present,
        "operator_count_108_recovered": len(rows) == 108,
        "operator_ids_contiguous_op001_op108": expected_ids == recovered_ids,
        "all_layers_a_to_l_present": set(layer_counts) == set(LAYER_TO_ROLE),
        "all_rows_metadata_only": all(row["detail_status"] == "name_layer_recovered_metadata_only" for row in rows),
        "all_rows_require_detail_before_training": all(
            row["detail_required_before_operator_specific_training"] is True for row in rows
        ),
        "no_raw_payload_fields_materialized": all(
            not any(field in row for field in ["raw_operator_body", "raw_session_text", "raw_training_target"])
            for row in rows
        ),
        "authority_counts_zero": not any(
            ((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0)
            for key in AUTHORITY_CLOSED
        ),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "OPERATOR_DETAIL_SEED_CATALOG_NO_EXECUTION",
        "operator_detail_seed_rows": rows,
        "layer_to_role": LAYER_TO_ROLE,
        "layer_to_category": LAYER_TO_CATEGORY,
        "checks": checks,
        "metrics": {
            "operator_seed_rows": len(rows),
            "expected_operator_rows": 108,
            "missing_operator_ids": len(expected_ids - recovered_ids),
            "extra_operator_ids": len(recovered_ids - expected_ids),
            "layer_count": len(layer_counts),
            "category_count": len(category_counts),
            "missing_detail_fields_per_row": len(MISSING_DETAIL_FIELDS),
            "detail_training_ready_rows": 0,
            "metadata_only_rows": len(rows),
            "operator_details_materialized_now": False,
            "raw_session_text_materialized_now": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "gemma_execution_attempted": False,
            "harness_scoring_attempted": False,
            "arxiv_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Recovered a metadata-only OP001-OP108 operator seed catalog from session grep. It is an index for future recovery, not a training-ready per-operator schema.",
    }


def validate_catalog(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "operator_details_materialized_now",
        "raw_session_text_materialized_now",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
        "gemma_execution_attempted",
        "harness_scoring_attempted",
        "arxiv_write_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    if card["metrics"].get("detail_training_ready_rows") != 0:
        failures.append("detail_training_ready_rows")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_catalog(registry)
    failures = validate_catalog(card)
    CATALOG.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"catalog": str(CATALOG.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Use the OP001-OP108 seed catalog to rebuild missing per-operator inputs/outputs/confidence/failure/label/metric fields; keep mining and training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9033 Operator Detail Seed Catalog",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage recovers the OP001-OP108 name/layer catalog from session grep as metadata-only operator seeds. It does not recover full training-ready operator details, read raw session payloads into rows, mine data, train, or write `/arxiv`.",
                "",
                f"Operator seed rows: `{summary['metrics']['operator_seed_rows']}`",
                f"Layer count: `{summary['metrics']['layer_count']}`",
                f"Detail training-ready rows: `{summary['metrics']['detail_training_ready_rows']}`",
                f"Training authorized: `{summary['metrics']['training_authorized']}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
