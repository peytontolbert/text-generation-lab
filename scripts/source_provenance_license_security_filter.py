from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "training_authorized_next": False,
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

SECRET_RE = re.compile(r"(api[_-]?key|secret|token|password|-----BEGIN [A-Z ]+PRIVATE KEY-----)", re.I)
PII_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}|\b\d{3}-\d{2}-\d{4}\b", re.I)

ALLOWED_LICENSE_STATUSES = {
    "license_file_present",
    "permissive_license",
    "reviewed_allowed",
    "readme_present_license_unknown",
}

SAFE_ROUTES = {
    "ALLOW_SOURCE_FOR_STRUCTURED",
    "ALLOW_SOURCE_FOR_HOLDOUT_ONLY",
    "HOLD_LICENSE_REVIEW",
    "HOLD_SECURITY_REVIEW",
    "BLOCK_SECRET_OR_PII",
    "BLOCK_LOCKED_EVAL_TRAIN",
    "BLOCK_DISALLOWED_IMPORT_SOURCE",
    "BLOCK_MISSING_LINEAGE",
}


def provenance_hash(row: Mapping[str, Any]) -> str:
    payload = {
        "source_id": row.get("source_id"),
        "lineage_hash": row.get("lineage_hash"),
        "license_status": row.get("license_status"),
        "security_policy_present": row.get("security_policy_present"),
        "allowed_import_source": row.get("allowed_import_source"),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _bool(row: Mapping[str, Any], key: str) -> bool:
    return bool(row.get(key))


def filter_source(row: Mapping[str, Any]) -> dict[str, Any]:
    text = str(row.get("content_preview") or row.get("content") or row.get("source_excerpt") or "")
    license_status = str(row.get("license_status") or "unknown")
    security_policy_present = _bool(row, "security_policy_present")
    allowed_import_source = _bool(row, "allowed_import_source")
    source_id = str(row.get("source_id") or "")
    lineage_hash = str(row.get("lineage_hash") or "")
    split_eligibility = row.get("split_eligibility") if isinstance(row.get("split_eligibility"), dict) else {}
    locked_eval = bool(split_eligibility.get("locked_eval")) or _bool(row, "locked_eval")
    train_requested = str(row.get("requested_split") or row.get("split") or "") == "train"
    secret_or_pii = bool(SECRET_RE.search(text) or PII_RE.search(text) or row.get("secret_pattern_bits") or row.get("pii_pattern_bits"))
    reasons: list[str] = []
    if not source_id or not lineage_hash:
        reasons.append("missing_lineage")
    if secret_or_pii:
        reasons.append("secret_or_pii")
    if locked_eval and train_requested:
        reasons.append("locked_eval_train_request")
    if license_status not in ALLOWED_LICENSE_STATUSES:
        reasons.append("license_not_allowed_or_unknown")
    if license_status == "readme_present_license_unknown" and train_requested:
        reasons.append("license_review_required_for_train")
    if not security_policy_present and train_requested:
        reasons.append("security_policy_missing_for_train")
    if not allowed_import_source and _bool(row, "requires_import"):
        reasons.append("disallowed_import_source")

    if "missing_lineage" in reasons:
        route = "BLOCK_MISSING_LINEAGE"
    elif "secret_or_pii" in reasons:
        route = "BLOCK_SECRET_OR_PII"
    elif "locked_eval_train_request" in reasons:
        route = "BLOCK_LOCKED_EVAL_TRAIN"
    elif "disallowed_import_source" in reasons:
        route = "BLOCK_DISALLOWED_IMPORT_SOURCE"
    elif "license_not_allowed_or_unknown" in reasons or "license_review_required_for_train" in reasons:
        route = "HOLD_LICENSE_REVIEW"
    elif "security_policy_missing_for_train" in reasons:
        route = "HOLD_SECURITY_REVIEW"
    elif train_requested:
        route = "ALLOW_SOURCE_FOR_STRUCTURED"
    else:
        route = "ALLOW_SOURCE_FOR_HOLDOUT_ONLY"

    return {
        "source_id": source_id,
        "route": route,
        "safe_route": route in SAFE_ROUTES,
        "reasons": sorted(set(reasons)),
        "provenance_hash": provenance_hash(row),
        "source_license": license_status,
        "security_policy_present": security_policy_present,
        "allowed_import_source": allowed_import_source,
        "secret_or_pii": secret_or_pii,
        "train_allowed": route == "ALLOW_SOURCE_FOR_STRUCTURED",
        "decoder_ce_authorized": False,
        "runtime_authorized": False,
        "model_execution_authorized": False,
        "authority": AUTHORITY_CLOSED,
    }


def filter_card(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    decisions = [filter_source(row) for row in rows]
    route_counts: dict[str, int] = {}
    for decision in decisions:
        route_counts[decision["route"]] = route_counts.get(decision["route"], 0) + 1
    unsafe = [d for d in decisions if not d["safe_route"] or d["decoder_ce_authorized"] or d["runtime_authorized"] or d["model_execution_authorized"]]
    return {
        "rows": len(decisions),
        "route_counts": dict(sorted(route_counts.items())),
        "train_allowed_rows": sum(1 for d in decisions if d["train_allowed"]),
        "blocked_rows": sum(1 for d in decisions if d["route"].startswith("BLOCK_")),
        "review_rows": sum(1 for d in decisions if d["route"].startswith("HOLD_")),
        "unsafe_decisions": len(unsafe),
        "decisions": decisions,
        "authority": AUTHORITY_CLOSED,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Source provenance/license/security filter for curriculum admission.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = read_jsonl(args.input) if args.input else [
        {"source_id": "src_ok", "lineage_hash": "abc", "license_status": "license_file_present", "security_policy_present": True, "allowed_import_source": True, "split": "train"},
        {"source_id": "src_secret", "lineage_hash": "def", "license_status": "license_file_present", "security_policy_present": True, "allowed_import_source": True, "split": "train", "content_preview": "api_key=123"},
    ]
    card = filter_card(rows)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
