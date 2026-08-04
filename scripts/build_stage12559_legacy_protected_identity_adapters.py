#!/usr/bin/env python3
"""Classify legacy protected sources and emit identity-only adapter status."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12559_legacy_protected_identity_adapters"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCES = {
    "sealed_transition_atlas": {
        "path": ROOT / "runs/local/artifacts/stage12105_sealed_transition_candidate_atlas/sealed_transition_candidate_rows.jsonl",
        "role": "protected_task_universe",
        "parse_allowed": False,
        "declared_count": 2462,
    },
    "locked_benchmark_packs": {
        "path": ROOT / "runs/local/artifacts/stage8672_locked_benchmark_pack_manifest/locked_benchmark_packs.jsonl",
        "role": "protected_task_universe",
        "parse_allowed": True,
    },
    "locked_acceptance_ledger": {
        "path": ROOT / "runs/local/artifacts/stage9718_locked_multilingual_acceptance_evidence_ledger/locked_multilingual_acceptance_evidence_ledger.json",
        "role": "evidence_metadata",
        "parse_allowed": True,
    },
    "scratchpad_exclusions": {
        "path": ROOT / "runs/local/artifacts/stage12037_scratchpad_contamination_exclusion_audit/scratchpad_excluded_keys.jsonl",
        "role": "contamination_exclusion_set",
        "parse_allowed": True,
    },
    "training_scratchpad_exclusions": {
        "path": ROOT / "runs/local/artifacts/stage12040_training_data_scratchpad_contamination_gate/training_scratchpad_excluded_keys.jsonl",
        "role": "contamination_exclusion_set",
        "parse_allowed": True,
    },
}
ZERO = {
    "admission_allowed": False, "training_allowed": False, "replay_allowed": False,
    "root_credit": False, "repair_credit": False, "level3_credit": False,
    "strict_eval_eligible": False, "gpu_allowed": False,
}


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict) and isinstance(value.get("records"), list):
        return [row for row in value["records"] if isinstance(row, dict)]
    return [value] if isinstance(value, dict) else []


def adapt_source(source_id: str, spec: dict[str, Any], reader=read_records) -> dict[str, Any]:
    path = Path(spec["path"])
    role = str(spec["role"])
    digest = sha256_file(path)
    record: dict[str, Any] = {
        "source_id": source_id, "source_role": role, "source_path": str(path),
        "source_sha256": digest, "source_present": path.is_file(),
        "raw_protected_payload_parsed": False, "normalized_identity_count": 0,
        "adapter_complete": False, "clearance_effect": "cannot_clear_replay", "blocking_reasons": [],
    }
    if not path.is_file():
        record["blocking_reasons"] = ["source_missing"]
        return record
    if not spec.get("parse_allowed"):
        record["declared_record_count"] = spec.get("declared_count")
        record["blocking_reasons"] = ["identity_only_sidecar_missing", "canonical_repo_and_base_commit_unavailable"]
        return record

    rows = reader(path)
    record["declared_record_count"] = len(rows)
    if role == "contamination_exclusion_set":
        keys = sorted({str(row.get("exclusion_key")) for row in rows if row.get("exclusion_key")})
        record.update({
            "normalized_identity_count": len(keys),
            "identity_namespace": f"{source_id}:exclusion_key",
            "identity_set_sha256": stable_hash(keys),
            "adapter_complete": len(keys) == len(rows) and bool(rows),
            "clearance_effect": "deny_set_enforced" if len(keys) == len(rows) and rows else "deny_set_incomplete",
            "blocking_reasons": [] if len(keys) == len(rows) and rows else ["exclusion_key_missing_or_duplicate"],
        })
    elif role == "evidence_metadata":
        record["blocking_reasons"] = ["control_metadata_not_task_lineage_authority"]
    else:
        fields = ("task_pack_id", "source_id", "artifact_hash", "lineage_hash")
        identities = sorted({tuple(str(row.get(field) or "") for field in fields) for row in rows})
        record.update({
            "source_local_identity_count": len(identities),
            "source_local_identity_sha256": stable_hash(identities),
            "blocking_reasons": ["canonical_repo_missing", "immutable_base_commit_missing", "cross_source_lineage_unproven"],
        })
    return record


def build(sources: dict[str, dict[str, Any]] = SOURCES) -> dict[str, Any]:
    records = [adapt_source(source_id, spec) for source_id, spec in sorted(sources.items())]
    protected = [row for row in records if row["source_role"] == "protected_task_universe"]
    exclusions = [row for row in records if row["source_role"] == "contamination_exclusion_set"]
    summary = {
        "stage": STAGE,
        "record_type": "stage12559_legacy_protected_identity_adapters_summary_v1",
        "source_count": len(records),
        "source_role_counts": {role: sum(row["source_role"] == role for row in records) for role in sorted({row["source_role"] for row in records})},
        "protected_universe_adapter_complete_count": sum(row["adapter_complete"] for row in protected),
        "protected_universe_count": len(protected),
        "exclusion_adapter_complete_count": sum(row["adapter_complete"] for row in exclusions),
        "exclusion_set_count": len(exclusions),
        "raw_protected_payloads_parsed": False,
        "protected_clearance": bool(protected) and all(row["adapter_complete"] for row in protected),
        "next_required_step": "produce_certified_identity_only_sidecars_for_stage12105_and_stage8672",
        **ZERO,
    }
    return {"records": records, "summary": summary}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    result = build()
    write_json(OUT / "source_role_adapters.json", result["records"])
    write_json(OUT / "summary.json", result["summary"])
    write_json(SUMMARY, result["summary"])
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
