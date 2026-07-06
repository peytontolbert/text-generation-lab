#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9046
NAME = "stage9046_domain_twin_manifest_schema_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9043 = ROOT / "runs/summaries/stage9043_domain_twin_operator_bridge.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DOMAIN_TWIN_MANIFEST_SCHEMA_STAGE9046.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "domain_twin_manifest_schema_design.json"
SCHEMA = OUT_DIR / "domain_twin_manifest_schema_v1.json"

SCHEMA_CONTRACT = {
    "domain_concept_manifest": {
        "required_fields": [
            "concept_id",
            "canonical_name",
            "alias_terms",
            "embedding_ref",
            "source_ref_ids",
            "edge_refs",
            "domain_tags",
            "authority",
            "provenance",
            "anti_cheat",
        ],
        "forbidden_fields": ["raw_paper_text", "raw_repo_source", "target_label", "answer_text", "model_logits"],
    },
    "repo_twin_manifest": {
        "required_fields": [
            "repo_twin_id",
            "repo_ref",
            "capability_refs",
            "symbol_index_ref",
            "test_index_ref",
            "semantic_summary_refs",
            "episodic_memory_refs",
            "style_profile_ref",
            "authority",
            "provenance",
            "anti_cheat",
        ],
        "forbidden_fields": ["raw_source_body", "patch_body", "secret", "hidden_eval_answer", "model_output_body"],
    },
    "paper_twin_manifest": {
        "required_fields": [
            "paper_twin_id",
            "paper_ref",
            "concept_refs",
            "method_operator_refs",
            "assumption_refs",
            "implementation_hint_refs",
            "semantic_summary_refs",
            "citation_graph_refs",
            "authority",
            "provenance",
            "anti_cheat",
        ],
        "forbidden_fields": ["raw_pdf_text", "raw_equation_body", "target_code", "hidden_eval_answer", "teacher_unverified_truth"],
    },
    "domain_twin_alignment_manifest": {
        "required_fields": [
            "alignment_id",
            "concept_id",
            "repo_twin_id",
            "paper_twin_id",
            "alignment_type",
            "evidence_ref_ids",
            "score_metadata",
            "authority",
            "provenance",
            "anti_cheat",
        ],
        "forbidden_fields": ["raw_repo_source", "raw_paper_text", "decoder_target", "target_label", "eval_answer"],
    },
}
REQUIRED_AUTHORITY_FIELDS = [
    "training_authorized",
    "decoder_ce_authorized",
    "denoise_ce_authorized",
    "runtime_authorized",
    "source_body_read_authorized",
    "arxiv_write_authorized",
]
REQUIRED_ANTI_CHEAT_FIELDS = [
    "id_is_opaque",
    "label_coded_id_absent",
    "target_label_absent_from_input",
    "raw_body_absent",
    "shortcut_baseline_required_before_training",
    "split_overlap_check_required",
]
FORBIDDEN_NOW = [
    "materialize_real_domain_manifest",
    "scan_arxiv",
    "scan_repository_library",
    "read_paper_body",
    "read_repo_source_body",
    "write_arxiv",
    "upload_hf",
    "train_model",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    s9043 = load_json(SOURCE_9043)
    checks = {
        "source_stage9043_present": SOURCE_9043.exists(),
        "source_stage9043_passed": s9043.get("passed") is True,
        "schema_has_four_manifest_families": set(SCHEMA_CONTRACT) == {"domain_concept_manifest", "repo_twin_manifest", "paper_twin_manifest", "domain_twin_alignment_manifest"},
        "required_authority_fields_recorded": len(REQUIRED_AUTHORITY_FIELDS) >= 6,
        "required_anti_cheat_fields_recorded": len(REQUIRED_ANTI_CHEAT_FIELDS) >= 6,
        "all_families_have_forbidden_fields": all(len(spec["forbidden_fields"]) >= 5 for spec in SCHEMA_CONTRACT.values()),
        "all_families_have_authority_provenance_anti_cheat": all({"authority", "provenance", "anti_cheat"}.issubset(set(spec["required_fields"])) for spec in SCHEMA_CONTRACT.values()),
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "DOMAIN_TWIN_MANIFEST_SCHEMA_DESIGN_NO_DATA",
        "schema_contract": SCHEMA_CONTRACT,
        "required_authority_fields": REQUIRED_AUTHORITY_FIELDS,
        "required_anti_cheat_fields": REQUIRED_ANTI_CHEAT_FIELDS,
        "forbidden_now": FORBIDDEN_NOW,
        "checks": checks,
        "metrics": {
            "manifest_families": len(SCHEMA_CONTRACT),
            "required_authority_fields": len(REQUIRED_AUTHORITY_FIELDS),
            "required_anti_cheat_fields": len(REQUIRED_ANTI_CHEAT_FIELDS),
            "schema_design_only": True,
            "real_manifest_materialized_now": False,
            "arxiv_scan_authorized_now": False,
            "repository_library_scan_authorized_now": False,
            "paper_body_read_authorized_now": False,
            "repo_source_body_read_authorized_now": False,
            "arxiv_write_authorized": False,
            "hf_upload_authorized_now": False,
            "training_authorized": False,
            "model_execution_attempted": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Define metadata-only DomainGraph/RepoTwin/PaperTwin manifest schemas as future compiler inputs without materializing real manifests or opening IO/training.",
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "real_manifest_materialized_now",
        "arxiv_scan_authorized_now",
        "repository_library_scan_authorized_now",
        "paper_body_read_authorized_now",
        "repo_source_body_read_authorized_now",
        "arxiv_write_authorized",
        "hf_upload_authorized_now",
        "training_authorized",
        "model_execution_attempted",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SCHEMA.write_text(json.dumps(SCHEMA_CONTRACT, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"design": str(CARD.relative_to(ROOT)), "schema": str(SCHEMA.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Audit this schema against existing compiler/gate-status contracts, then design a synthetic fixture-only validator before any real DomainGraph/Twin manifest materialization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9046 Domain/Twin Manifest Schema Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines metadata-only schemas for future DomainGraph, RepoTwin, PaperTwin, and alignment manifests.",
        "It materializes no real manifests, scans no corpus, reads no bodies, writes no `/arxiv`, uploads nothing, runs no model, and trains nothing.",
        "",
        "Manifest families:",
        "",
        *[f"- `{name}`" for name in SCHEMA_CONTRACT],
        "",
        "Required anti-cheat fields:",
        "",
        *[f"- `{name}`" for name in REQUIRED_ANTI_CHEAT_FIELDS],
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
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
