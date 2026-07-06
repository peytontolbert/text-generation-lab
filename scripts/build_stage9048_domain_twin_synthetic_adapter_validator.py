#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.domain_twin_adapter_validator import adapt_source_records
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from domain_twin_adapter_validator import adapt_source_records  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9048
NAME = "stage9048_domain_twin_synthetic_adapter_validator"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9047 = ROOT / "runs/summaries/stage9047_domain_twin_schema_compiler_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DOMAIN_TWIN_SYNTHETIC_ADAPTER_VALIDATOR_STAGE9048.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ROWS = OUT_DIR / "synthetic_domain_twin_adapter_rows.jsonl"
CARD = OUT_DIR / "synthetic_domain_twin_adapter_card.json"


def closed_record_base() -> dict[str, Any]:
    return {
        "authority": dict(AUTHORITY_CLOSED),
        "provenance": {"source": "synthetic_fixture_only", "body_read": False},
        "anti_cheat": {"id_is_opaque": True, "label_coded_id_absent": True, "raw_body_absent": True},
        "split": "train",
    }

SYNTHETIC_RECORDS = [
    {**closed_record_base(), "manifest_family": "domain_concept_manifest", "concept_id": "concept_fixture_001", "canonical_name": "retrieval repair"},
    {**closed_record_base(), "manifest_family": "repo_twin_manifest", "repo_twin_id": "repo_fixture_001", "repo_ref": "repo_meta_ref_001"},
    {**closed_record_base(), "manifest_family": "paper_twin_manifest", "paper_twin_id": "paper_fixture_001", "paper_ref": "paper_meta_ref_001"},
    {**closed_record_base(), "manifest_family": "domain_twin_alignment_manifest", "alignment_id": "align_fixture_001", "concept_id": "concept_fixture_001", "repo_twin_id": "repo_fixture_001", "paper_twin_id": "paper_fixture_001"},
]
FORBIDDEN_NOW = [
    "real_domain_twin_manifest_read",
    "real_domain_twin_manifest_write",
    "arxiv_scan",
    "repository_library_scan",
    "body_read",
    "training",
    "model_execution",
    "decoder_ce",
    "denoise_ce",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    s9047 = load_json(SOURCE_9047)
    rows, adapter_card = adapt_source_records(SYNTHETIC_RECORDS)
    checks = {
        "source_stage9047_present": SOURCE_9047.exists(),
        "source_stage9047_passed": s9047.get("passed") is True,
        "synthetic_records_only": all((row.get("provenance") or {}).get("source") == "synthetic_fixture_only" for row in SYNTHETIC_RECORDS),
        "adapter_rows_emitted_for_four_families": len(rows) == 4 and len(adapter_card["source_manifest_family_counts"]) == 4,
        "all_loss_masks_closed": adapter_card["all_loss_masks_closed"] is True,
        "all_authority_closed": adapter_card["all_authority_closed"] is True,
        "all_gate_status_complete": adapter_card["all_gate_status_complete"] is True,
        "compiler_ready_for_training_false": adapter_card["compiler_ready_for_training"] is False,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "DOMAIN_TWIN_SYNTHETIC_ADAPTER_VALIDATOR_NO_REAL_DATA",
        "adapter_card": adapter_card,
        "forbidden_now": FORBIDDEN_NOW,
        "checks": checks,
        "metrics": {
            "synthetic_records": len(SYNTHETIC_RECORDS),
            "adapter_rows": len(rows),
            "manifest_families": len(adapter_card["source_manifest_family_counts"]),
            "synthetic_fixture_only": True,
            "real_domain_twin_manifest_read_now": False,
            "real_domain_twin_manifest_written_now": False,
            "arxiv_scan_authorized_now": False,
            "repository_library_scan_authorized_now": False,
            "body_read_authorized_now": False,
            "training_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "arxiv_write_authorized": False,
        },
        "rows": rows,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Validate the Domain/Twin adapter shape on synthetic fixtures only. Rows remain blocked, loss masks closed, and not compiler-ready for training.",
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "real_domain_twin_manifest_read_now",
        "real_domain_twin_manifest_written_now",
        "arxiv_scan_authorized_now",
        "repository_library_scan_authorized_now",
        "body_read_authorized_now",
        "training_authorized",
        "model_execution_attempted",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "arxiv_write_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card)
    rows = card.pop("rows")
    write_jsonl(ROWS, rows)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"adapter_card": str(CARD.relative_to(ROOT)), "adapter_rows": str(ROWS.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "If useful, design a no-real-data shortcut audit over these synthetic adapter rows; real Domain/Twin manifests still require active source tickets.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9048 Domain/Twin Synthetic Adapter Validator",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage validates the Domain/Twin adapter shape using synthetic fixtures only.",
        "It reads no real manifests, scans no corpus, reads no bodies, writes no `/arxiv`, runs no model, and trains nothing.",
        "",
        f"Synthetic adapter rows: `{summary['metrics']['adapter_rows']}`",
        f"Manifest families: `{summary['metrics']['manifest_families']}`",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
    rows_reg = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows_reg.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows_reg = sorted(rows_reg, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows_reg
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows_reg),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
