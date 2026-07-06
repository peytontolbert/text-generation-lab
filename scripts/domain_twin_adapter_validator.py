from __future__ import annotations

from collections import Counter
from typing import Any

try:
    from scripts.curriculum_compiler import AUTHORITY_CLOSED, LOSS_KEYS, REQUIRED_RECOVERED_GATE_REFERENCES
except ModuleNotFoundError:  # pragma: no cover
    from curriculum_compiler import AUTHORITY_CLOSED, LOSS_KEYS, REQUIRED_RECOVERED_GATE_REFERENCES  # type: ignore

REQUIRED_SOURCE_FIELDS = {
    "domain_concept_manifest": {"concept_id", "authority", "provenance", "anti_cheat"},
    "repo_twin_manifest": {"repo_twin_id", "authority", "provenance", "anti_cheat"},
    "paper_twin_manifest": {"paper_twin_id", "authority", "provenance", "anti_cheat"},
    "domain_twin_alignment_manifest": {"alignment_id", "authority", "provenance", "anti_cheat"},
}
FORBIDDEN_PAYLOAD_FIELDS = {
    "raw_paper_text",
    "raw_pdf_text",
    "raw_repo_source",
    "raw_source_body",
    "patch_body",
    "answer_text",
    "decoder_target",
    "target_label",
    "model_logits",
    "hidden_eval_answer",
}


def _closed_loss_mask() -> dict[str, bool]:
    return {key: False for key in LOSS_KEYS}


def _closed_gate_status() -> dict[str, bool]:
    return {key: False for key in REQUIRED_RECOVERED_GATE_REFERENCES}


def validate_source_record(record: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    family = str(record.get("manifest_family") or "")
    required = REQUIRED_SOURCE_FIELDS.get(family)
    if required is None:
        failures.append("unknown_manifest_family")
    else:
        missing = sorted(required - set(record))
        failures.extend(f"missing:{field}" for field in missing)
    for field in sorted(FORBIDDEN_PAYLOAD_FIELDS & set(record)):
        failures.append(f"forbidden_payload_field:{field}")
    authority = record.get("authority")
    if not isinstance(authority, dict):
        failures.append("missing_authority_card")
    elif any(authority.get(key) is not False for key in AUTHORITY_CLOSED):
        failures.append("authority_open")
    anti = record.get("anti_cheat")
    if not isinstance(anti, dict):
        failures.append("missing_anti_cheat_card")
    else:
        for key in ["id_is_opaque", "label_coded_id_absent", "raw_body_absent"]:
            if anti.get(key) is not True:
                failures.append(f"anti_cheat_failed:{key}")
    return failures


def adapt_source_record(record: dict[str, Any], *, index: int = 0) -> dict[str, Any]:
    failures = validate_source_record(record)
    family = str(record.get("manifest_family") or "unknown")
    source_id = str(record.get("concept_id") or record.get("repo_twin_id") or record.get("paper_twin_id") or record.get("alignment_id") or f"source_{index:06d}")
    route = "NEEDS_HUMAN_REVIEW"
    row = {
        "row_id": f"domain_twin_adapter_{index:06d}",
        "split": str(record.get("split") or "train"),
        "route": route,
        "semantic_key": f"{family}:{source_id}",
        "source_manifest_family": family,
        "source_ref_id": source_id,
        "gate_status": _closed_gate_status(),
        "authority": dict(AUTHORITY_CLOSED),
        "loss_mask": _closed_loss_mask(),
        "anti_cheat": dict(record.get("anti_cheat") or {}),
        "provenance": dict(record.get("provenance") or {}),
        "adapter_status": "blocked_pending_real_gates" if not failures else "blocked_source_record_failed_validation",
        "adapter_failures": failures,
    }
    return row


def adapt_source_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [adapt_source_record(record, index=index) for index, record in enumerate(records)]
    routes = Counter(row["route"] for row in rows)
    families = Counter(row["source_manifest_family"] for row in rows)
    failure_counts: Counter[str] = Counter()
    for row in rows:
        for failure in row["adapter_failures"]:
            failure_counts[failure] += 1
    card = {
        "rows": len(rows),
        "route_counts": dict(sorted(routes.items())),
        "source_manifest_family_counts": dict(sorted(families.items())),
        "adapter_failure_counts": dict(sorted(failure_counts.items())),
        "all_loss_masks_closed": all(not any(row["loss_mask"].values()) for row in rows),
        "all_authority_closed": all(not any(row["authority"].values()) for row in rows),
        "all_gate_status_complete": all(set(REQUIRED_RECOVERED_GATE_REFERENCES).issubset(row["gate_status"]) for row in rows),
        "compiler_ready_for_training": False,
        "real_data_materialized": False,
    }
    return rows, card
