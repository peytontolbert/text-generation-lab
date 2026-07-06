#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8917
NAME = "stage8917_converter_row_completeness_collision_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CONVERTER_ROW_COMPLETENESS_COLLISION_AUDIT_STAGE8917.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "converter_row_completeness_collision_audit.json"

STAGE8916_DIR = ROOT / "runs/local/artifacts/stage8916_nonexecuting_converter_shape_report_dry_run"
STAGE8916_ROWS = STAGE8916_DIR / "shape_report_rows_metadata_only.jsonl"
STAGE8916_SUMMARY = ROOT / "runs/summaries/stage8916_nonexecuting_converter_shape_report_dry_run.json"

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

EXPECTED_DENSE_ROWS = 43
EXPECTED_PACKED_ROWS = 109
EXPECTED_NEW_INIT_ROWS = 7
EXPECTED_SHAPE_ROWS = 159

FORBIDDEN_OPERATIONS = [
    "read_binary_tensor_values",
    "decode_packed_bitnet",
    "torch_load",
    "state_dict_load",
    "embedding_resize",
    "model_forward",
    "training_step",
    "checkpoint_write",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_rows(path: Path = STAGE8916_ROWS) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def duplicates(values: list[str]) -> list[dict[str, Any]]:
    counts = Counter(values)
    return [{"value": value, "count": count} for value, count in sorted(counts.items()) if count > 1]


def classify(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dense = [row for row in rows if str(row.get("source_artifact") or "").startswith("dense/")]
    packed = [row for row in rows if str(row.get("source_artifact") or "").startswith("layers/")]
    new_init = [row for row in rows if row.get("status") == "new_init_required"]
    blocked_dense = [row for row in dense if row.get("status") == "blocked"]
    unknown_dense = [
        row
        for row in dense
        if "unknown" in json.dumps(row.get("source_shape"), sort_keys=True).lower()
        or row.get("action") == "blocked" and row.get("target_key") is None and row.get("source_artifact") != "dense/enc_pos_embed_weight.f32.bin"
    ]
    target_keys = [str(row["target_key"]) for row in rows if row.get("target_key")]
    source_artifacts = [str(row["source_artifact"]) for row in rows if row.get("source_artifact")]
    source_keys = [str(row["source_key"]) for row in rows if row.get("source_key")]
    packed_missing_sizes = [row for row in packed if row.get("file_size_bytes") is None]
    binary_value_rows = [row for row in rows if row.get("binary_tensor_values_read") is not False]
    embedding_rows = [row for row in rows if row.get("target_key") in {"enc_embed.weight", "dec_embed.weight"}]
    compatible_dense = [row for row in dense if row.get("status") == "compatible"]
    return {
        "shape_rows": len(rows),
        "dense_rows": len(dense),
        "packed_rows": len(packed),
        "new_init_rows": len(new_init),
        "blocked_dense_rows": len(blocked_dense),
        "unknown_dense_rows": len(unknown_dense),
        "compatible_dense_rows": len(compatible_dense),
        "target_key_duplicate_count": len(duplicates(target_keys)),
        "target_key_duplicates": duplicates(target_keys),
        "source_artifact_duplicate_count": len(duplicates(source_artifacts)),
        "source_artifact_duplicates": duplicates(source_artifacts),
        "source_key_duplicate_count": len(duplicates(source_keys)),
        "source_key_duplicates": duplicates(source_keys),
        "packed_rows_missing_file_size": len(packed_missing_sizes),
        "binary_tensor_value_rows": len(binary_value_rows),
        "embedding_migration_rows": len([row for row in embedding_rows if row.get("status") == "needs_migration"]),
        "blocked_dense_artifacts": [row.get("source_artifact") for row in blocked_dense],
        "unknown_dense_artifacts": [row.get("source_artifact") for row in unknown_dense],
        "packed_status_blocked_rows": len([row for row in packed if row.get("status") == "blocked"]),
        "new_init_targets": sorted(str(row.get("target_key")) for row in new_init),
    }


def build_audit() -> dict[str, Any]:
    rows = load_rows()
    stage8916_summary = load_json(STAGE8916_SUMMARY)
    metrics = classify(rows)
    checks = {
        "stage8916_summary_passed": stage8916_summary.get("passed") is True,
        "shape_report_exists": STAGE8916_ROWS.exists(),
        "expected_shape_row_count": metrics["shape_rows"] == EXPECTED_SHAPE_ROWS,
        "expected_dense_row_count": metrics["dense_rows"] == EXPECTED_DENSE_ROWS,
        "expected_packed_row_count": metrics["packed_rows"] == EXPECTED_PACKED_ROWS,
        "expected_new_init_row_count": metrics["new_init_rows"] == EXPECTED_NEW_INIT_ROWS,
        "no_target_key_collisions": metrics["target_key_duplicate_count"] == 0,
        "no_source_artifact_collisions": metrics["source_artifact_duplicate_count"] == 0,
        "no_source_key_collisions": metrics["source_key_duplicate_count"] == 0,
        "no_unknown_dense_rows": metrics["unknown_dense_rows"] == 0,
        "only_positional_embedding_dense_blocked": metrics["blocked_dense_artifacts"] == ["dense/enc_pos_embed_weight.f32.bin"],
        "all_packed_rows_blocked_pending_converter": metrics["packed_status_blocked_rows"] == EXPECTED_PACKED_ROWS,
        "all_packed_rows_have_file_size_metadata": metrics["packed_rows_missing_file_size"] == 0,
        "embedding_rows_require_migration": metrics["embedding_migration_rows"] == 2,
        "no_binary_tensor_values_read": metrics["binary_tensor_value_rows"] == 0,
        "direct_load_allowed": False,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "source_stage": 8916,
        "checks": checks,
        "metrics": metrics,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "authority": AUTHORITY_CLOSED,
        "decision": {
            "row_completeness_status": "passed" if all(checks.values()) else "failed",
            "direct_load_status": "blocked",
            "next_required_artifact": "metadata_only_converter_collision_followup_or_converter_key_mapping_contract",
        },
    }


def validate_audit(audit: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in audit["checks"].items() if value is not True and key != "direct_load_allowed"]
    if audit["checks"].get("direct_load_allowed") is not False:
        failures.append("direct_load_allowed")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = (registry.get("metrics") or {}).get("latest_stage")
    if latest not in {8916, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit()
    failures = validate_audit(audit, registry)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            **audit["metrics"],
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
            "download_authorized": False,
        },
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT))},
        "decision": "Converter metadata rows are complete and collision-free; direct loading remains blocked." if not failures else "Converter row completeness/collision audit failed.",
        "next_best_step": "Write a converter key-mapping contract for compatible rows and explicit initialization/migration policy for embeddings/control heads; still do not decode BitNet weights, load a state dict, execute, or train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8917 Converter Row Completeness Collision Audit",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage audits Stage8916 metadata-only shape rows for completeness, target/source collisions, unknown dense shapes, packed metadata coverage, and migration/new-init coverage.",
        "",
        "It does not decode packed BitNet weights, read tensor values, load a state dict, resize embeddings, execute a model, train, write checkpoints, or authorize runtime.",
        "",
        f"Shape rows: `{audit['metrics']['shape_rows']}`",
        f"Target-key collisions: `{audit['metrics']['target_key_duplicate_count']}`",
        f"Unknown dense rows: `{audit['metrics']['unknown_dense_rows']}`",
        f"Blocked dense artifacts: `{audit['metrics']['blocked_dense_artifacts']}`",
        "",
        "Next: write a converter key-mapping contract for compatible rows and explicit initialization/migration policy for embeddings/control heads.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": card["passed"],
        "path": str(SUMMARY),
        "authority": AUTHORITY_CLOSED,
        "next_best_step": card["next_best_step"],
    })
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {
        **registry.get("metrics", {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": card["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8917 Converter Row Completeness Collision Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + marker + "\n\nStage8917 audits Stage8916 converter metadata rows for completeness and collisions. It confirms the row set is clean enough for a converter key-mapping contract while direct loading, packed-weight decoding, execution, and training remain blocked.\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
