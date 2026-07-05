from __future__ import annotations

import argparse
import hashlib
import json
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

ALLOWED_SPLITS = {"train", "eval", "strict_eval", "holdout", "locked_eval"}
BLOCKED_TRAIN_REASONS = {
    "locked_eval_source",
    "unknown_license_without_review",
    "security_policy_missing_for_external_code",
    "body_or_source_leak",
    "missing_content_hash",
}


def stable_hash(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_source_id(source_uri: str, content_hash: str) -> str:
    return "src_" + stable_hash({"source_uri": source_uri, "content_hash": content_hash})[:16]


def make_lineage_hash(source_card: Mapping[str, Any]) -> str:
    payload = {
        "source_id": source_card.get("source_id"),
        "source_uri": source_card.get("source_uri"),
        "content_hash": source_card.get("content_hash"),
        "transform_chain": source_card.get("transform_chain", []),
        "split_eligibility": source_card.get("split_eligibility", {}),
        "license_status": source_card.get("license_status"),
        "security_policy_present": source_card.get("security_policy_present"),
    }
    return stable_hash(payload)


def build_lineage_card(row: Mapping[str, Any]) -> dict[str, Any]:
    source_uri = str(row.get("source_uri") or row.get("path") or row.get("repo") or "")
    content = row.get("content")
    content_hash = str(row.get("content_hash") or "")
    if not content_hash and content is not None:
        content_hash = stable_hash(content)
    transform_chain = row.get("transform_chain")
    if not isinstance(transform_chain, list):
        transform_chain = ["raw_source_inventory"]
    split = str(row.get("split") or "holdout")
    if split not in ALLOWED_SPLITS:
        split = "holdout"
    license_status = str(row.get("license_status") or "unknown")
    security_policy_present = bool(row.get("security_policy_present"))
    locked_eval = bool(row.get("locked_eval")) or split == "locked_eval"
    source_body_leak = bool(row.get("source_body_leak") or row.get("body_leak") or row.get("raw_body_in_model_input"))
    source_id = str(row.get("source_id") or make_source_id(source_uri, content_hash or "missing"))
    reasons: list[str] = []
    if locked_eval:
        reasons.append("locked_eval_source")
    if not content_hash:
        reasons.append("missing_content_hash")
    if license_status == "unknown" and split == "train":
        reasons.append("unknown_license_without_review")
    if not security_policy_present and split == "train":
        reasons.append("security_policy_missing_for_external_code")
    if source_body_leak:
        reasons.append("body_or_source_leak")
    train_eligible = split == "train" and not any(reason in BLOCKED_TRAIN_REASONS for reason in reasons)
    card = {
        "source_id": source_id,
        "source_uri": source_uri,
        "content_hash": content_hash,
        "license_status": license_status,
        "security_policy_present": security_policy_present,
        "transform_chain": transform_chain,
        "split": split,
        "split_eligibility": {
            "train": train_eligible,
            "eval": split in {"eval", "strict_eval", "holdout"} and not source_body_leak,
            "strict_eval": split in {"strict_eval", "holdout"} and not source_body_leak,
            "locked_eval": locked_eval,
        },
        "blocked_reasons": sorted(set(reasons)),
        "authority": AUTHORITY_CLOSED,
    }
    card["lineage_hash"] = make_lineage_hash(card)
    return card


def audit_lineage_cards(cards: list[Mapping[str, Any]]) -> dict[str, Any]:
    source_ids: dict[str, int] = {}
    lineage_hashes: dict[str, int] = {}
    failures: list[dict[str, Any]] = []
    train_eligible = 0
    locked_eval = 0
    for card in cards:
        sid = str(card.get("source_id") or "")
        lhash = str(card.get("lineage_hash") or "")
        source_ids[sid] = source_ids.get(sid, 0) + 1
        lineage_hashes[lhash] = lineage_hashes.get(lhash, 0) + 1
        authority = card.get("authority") if isinstance(card.get("authority"), dict) else {}
        row_failures: list[str] = []
        if not sid:
            row_failures.append("missing_source_id")
        if not card.get("content_hash"):
            row_failures.append("missing_content_hash")
        if not lhash:
            row_failures.append("missing_lineage_hash")
        if any(value is True for value in authority.values()):
            row_failures.append("authority_open")
        eligibility = card.get("split_eligibility") if isinstance(card.get("split_eligibility"), dict) else {}
        train_eligible += int(eligibility.get("train") is True)
        locked_eval += int(eligibility.get("locked_eval") is True)
        if eligibility.get("locked_eval") is True and eligibility.get("train") is True:
            row_failures.append("locked_eval_train_eligible")
        if row_failures:
            failures.append({"source_id": sid, "failures": row_failures})
    duplicate_source_ids = sorted(key for key, count in source_ids.items() if key and count > 1)
    duplicate_lineage_hashes = sorted(key for key, count in lineage_hashes.items() if key and count > 1)
    return {
        "rows": len(cards),
        "train_eligible_rows": train_eligible,
        "locked_eval_rows": locked_eval,
        "duplicate_source_ids": duplicate_source_ids,
        "duplicate_lineage_hashes": duplicate_lineage_hashes,
        "failures": failures,
        "passed": not failures and not duplicate_lineage_hashes,
        "authority": AUTHORITY_CLOSED,
    }


def lineage_manifest(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    cards = [build_lineage_card(row) for row in rows]
    return {"cards": cards, "audit": audit_lineage_cards(cards), "authority": AUTHORITY_CLOSED}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Reusable source inventory lineage tracker for mined curriculum rows.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = read_jsonl(args.input) if args.input else [
        {"source_uri": "/arxiv/repositories/example/file.py", "content": "def f(): pass", "split": "train", "license_status": "license_file_present", "security_policy_present": True},
        {"source_uri": "/arxiv/datasets/locked/example.parquet", "content": "locked", "split": "locked_eval", "locked_eval": True},
    ]
    manifest = lineage_manifest(rows)
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
