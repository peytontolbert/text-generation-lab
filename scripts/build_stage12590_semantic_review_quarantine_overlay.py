#!/usr/bin/env python3
"""Apply the reviewed semantic quarantine overlay to Stage12589 candidates."""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12590_semantic_review_quarantine_overlay"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
STAGE12589_INPUT = ROOT / "runs/local/artifacts/stage12589_raw_private_resolution/safe_resolution_records.jsonl"
PINNED_STAGE12589_SHA256 = "79c60d08b20dceb85e2e5ef700ab6577a05d3a677c05ce5bd29667e13742dc56"
MECHANICAL_CLASSIFICATION = "resolved_observed_atom_candidate"
QUARANTINED = "QUARANTINED"
SURVIVOR = "SEMANTIC_REVIEW_SURVIVOR_NON_ADMITTING"
HIDDEN_MUTATION_REASON = "HIDDEN_MUTATION_CLOSURE_UNPROVEN"
DOC_REPO_WIDE_REASON = "DOCUMENTATION_METADATA_REPO_WIDE_PROOF_UNSUPPORTED"
SURVIVOR_REASON = "FURTHER_SEMANTIC_REVIEW_REQUIRED"
ATOM_PREFIX = "stage12589_atom_"
SAFE_STRING = re.compile(r"^[A-Za-z0-9_.:-]+$")
FORBIDDEN_OUTPUT_KEYS = {
    "command", "content", "output", "patch", "path", "prompt", "secret", "text", "url",
}


def _ids(values: str) -> tuple[str, ...]:
    return tuple(f"{ATOM_PREFIX}{value}" for value in values.split())


# Explicit reviewed adversarial-audit input. It is intentionally not inferred from
# Stage12589's mechanical verifier classification.
HIDDEN_MUTATION_IDS = _ids(
    "2cfc8d94043a96017b08 9e66c5fe77a39cc52ad1 84b2695020ccbdef7b9c "
    "e7095f4813f0becb9c0a a36fe355edc6fcc5807f 1d19e95a6e3d16f2f8dd "
    "6098692f3c147d93097f 246d8298404f5d0f83f1 b0ec558de6982eed4af5 "
    "2d4448d34f916406b768 ab920b534abdccbcce95 8adc46dae47424bc44a5 "
    "c2c7a8a84118dd49f6b1 76f34a58e7091e127b01 b316619c99fcb4fc59dc"
)
DOC_REPO_WIDE_IDS = _ids(
    "bca77c772a48ad432e11 42e6af8e7d167e1246fa 3090bb2b000bc15879a3"
)
SURVIVOR_IDS = _ids("aa0dfb012dcb3d947f70 f79d3ff47171eb2dd024")
REVIEWED_IDS = HIDDEN_MUTATION_IDS + DOC_REPO_WIDE_IDS + SURVIVOR_IDS


class GateError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.is_file():
        raise GateError("required_stage12589_input_missing")
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GateError(f"malformed_stage12589_jsonl:{number}") from exc
            if not isinstance(row, dict):
                raise GateError(f"non_object_stage12589_jsonl:{number}")
            yield row


def assert_safe_output(value: Any, key: str = "") -> None:
    if isinstance(value, Mapping):
        for child_key, child in value.items():
            folded = str(child_key).casefold()
            if folded in FORBIDDEN_OUTPUT_KEYS or any(token in folded for token in ("raw_", "command", "output", "patch", "path")):
                raise GateError(f"forbidden_output_key:{child_key}")
            assert_safe_output(child, str(child_key))
    elif isinstance(value, (list, tuple)):
        for child in value:
            assert_safe_output(child, key)
    elif isinstance(value, str):
        if not SAFE_STRING.fullmatch(value) or "/" in value or "\\" in value or "://" in value:
            raise GateError(f"unsafe_output_string:{key}")
        if any(marker in value.casefold() for marker in ("bearer", "private_key", "api_key", "password")):
            raise GateError(f"secret_like_output:{key}")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _review_partition() -> dict[str, tuple[str, str, tuple[str, ...]]]:
    partition: dict[str, tuple[str, str, tuple[str, ...]]] = {}
    groups = (
        (HIDDEN_MUTATION_IDS, QUARANTINED, HIDDEN_MUTATION_REASON,
         ("COMPLETE_FILESYSTEM_MUTATION_CLOSURE", "VERIFIER_LAST_OUTCOME_AFFECTING_ACTION")),
        (DOC_REPO_WIDE_IDS, QUARANTINED, DOC_REPO_WIDE_REASON,
         ("EXPLICIT_DOCUMENTATION_METADATA_ASSERTION", "NO_IMPLICIT_REPO_WIDE_PROOF")),
        (SURVIVOR_IDS, SURVIVOR, SURVIVOR_REASON,
         ("COMPLETE_FILESYSTEM_MUTATION_CLOSURE", "VERIFIER_LAST_OUTCOME_AFFECTING_ACTION",
          "EXPLICIT_DOCUMENTATION_METADATA_ASSERTION")),
    )
    for identities, status, reason, requirements in groups:
        for identity in identities:
            if identity in partition:
                raise GateError(f"duplicate_reviewed_id:{identity}")
            partition[identity] = (status, reason, requirements)
    if len(partition) != 20:
        raise GateError("reviewed_partition_must_contain_20_unique_ids")
    return partition


def build_overlay(stage12589_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    partition = _review_partition()
    all_identity_counts = Counter(str(row.get("resolution_record_id") or "") for row in stage12589_rows)
    candidate_rows = [row for row in stage12589_rows if row.get("classification") == MECHANICAL_CLASSIFICATION]
    candidate_counts = Counter(str(row.get("resolution_record_id") or "") for row in candidate_rows)
    malformed = sorted(identity for identity in candidate_counts if not re.fullmatch(r"stage12589_atom_[0-9a-f]{20}", identity))
    if malformed:
        raise GateError(f"malformed_mechanical_candidate_id:{malformed[0]}")
    duplicates = sorted(identity for identity, count in all_identity_counts.items() if identity and count != 1 and identity in candidate_counts)
    if duplicates:
        raise GateError(f"duplicate_stage12589_candidate_id:{duplicates[0]}")
    reviewed, candidates = set(partition), set(candidate_counts)
    missing = sorted(reviewed - candidates)
    unknown = sorted(candidates - reviewed)
    if missing:
        raise GateError(f"reviewed_id_missing_from_mechanical_candidates:{missing[0]}")
    if unknown:
        raise GateError(f"unknown_mechanical_candidate_id:{unknown[0]}")
    if len(candidate_rows) != 20 or any(candidate_counts[identity] != 1 for identity in reviewed):
        raise GateError("mechanical_candidate_exact_once_coverage_failed")

    overlay = []
    for identity in sorted(reviewed):
        status, reason, requirements = partition[identity]
        record = {
            "record_type": "stage12590_semantic_review_overlay_v1",
            "audit_overlay_id": f"stage12590_overlay_{stable_hash(identity)[:20]}",
            "stage12589_record_id": identity,
            "stage12589_mechanical_classification": MECHANICAL_CLASSIFICATION,
            "stage12590_status": status,
            "semantic_review_reason": reason,
            "proof_requirements": list(requirements),
            "normative_policy_correctness": "unresolved",
            "further_review_only": status == SURVIVOR,
            "level3_allowed": False,
            "admission_allowed": False,
            "training_allowed": False,
            "ranking_credit_allowed": False,
            "positive_stop_target_allowed": False,
            "training_authority": False,
        }
        assert_safe_output(record)
        overlay.append(record)
    return overlay


def downstream_contract() -> dict[str, Any]:
    contract = {
        "record_type": "stage12590_global_downstream_deny_contract_v1",
        "scope": "GLOBAL_DOWNSTREAM_CONSUMERS",
        "default_disposition": "DENY",
        "stage12589_mechanical_classification_sufficient": False,
        "required_status_source": STAGE,
        "only_stage12590_status_may_be_consulted": True,
        "globally_denied_authority_statuses": [QUARANTINED, SURVIVOR],
        "survivor_status_grants_training_authority": False,
        "survivor_status_grants_admission_authority": False,
        "survivor_status_grants_ranking_authority": False,
        "survivor_status_grants_positive_stop_authority": False,
        "normative_policy_correctness": "unresolved",
        "scale_claims_allowed": False,
        "concentration_blocker": {
            "blocker_to_scale_claims": True,
            "dimensions": [
                {"dimension": "source", "concentration_percent": 100},
                {"dimension": "session", "concentration_percent": 100},
                {"dimension": "repo_family", "concentration_percent": 100},
            ],
        },
        "next_private_proof_contract": {
            "complete_filesystem_mutation_closure_required": True,
            "verifier_must_be_last_outcome_affecting_action": True,
            "repo_wide_verifier_proves_documentation_metadata": False,
            "explicit_documentation_metadata_assertion_required": True,
        },
        "level3_allowed": False,
        "admission_allowed": False,
        "training_allowed": False,
        "ranking_credit_allowed": False,
        "positive_stop_target_allowed": False,
        "training_authority": False,
        "admission_authority": False,
        "ranking_authority": False,
        "positive_stop_authority": False,
    }
    assert_safe_output(contract)
    return contract


def execute(*, stage12589_input: Path = STAGE12589_INPUT, out: Path = OUT,
            summary_path: Path = SUMMARY) -> dict[str, Any]:
    if not stage12589_input.is_file():
        raise GateError("required_stage12589_input_missing")
    observed_hash = hashlib.sha256(stage12589_input.read_bytes()).hexdigest()
    if observed_hash != PINNED_STAGE12589_SHA256:
        raise GateError("stage12589_input_hash_mismatch")
    overlay = build_overlay(list(iter_jsonl(stage12589_input)))
    contract = downstream_contract()
    counts = Counter(record["stage12590_status"] for record in overlay)
    reasons = Counter(record["semantic_review_reason"] for record in overlay)
    summary = {
        "stage": STAGE,
        "status": "SEMANTIC_REVIEW_QUARANTINE_OVERLAY_COMPLETE",
        "pinned_stage12589_sha256": PINNED_STAGE12589_SHA256,
        "stage12589_mechanical_candidate_count": len(overlay),
        "audit_overlay_record_count": len(overlay),
        "quarantined_count": counts[QUARANTINED],
        "semantic_review_survivor_non_admitting_count": counts[SURVIVOR],
        "hidden_mutation_quarantine_count": reasons[HIDDEN_MUTATION_REASON],
        "documentation_metadata_quarantine_count": reasons[DOC_REPO_WIDE_REASON],
        "source_concentration_percent": 100,
        "session_concentration_percent": 100,
        "repo_family_concentration_percent": 100,
        "concentration_blocks_scale_claims": True,
        "level3_allowed": False,
        "admission_allowed": False,
        "training_allowed": False,
        "ranking_credit_allowed": False,
        "positive_stop_target_allowed": False,
    }
    if counts != Counter({QUARANTINED: 18, SURVIVOR: 2}):
        raise GateError("reviewed_status_counts_invalid")
    assert_safe_output([overlay, contract, summary])
    write_jsonl(out / "semantic_review_overlay.jsonl", overlay)
    write_json(out / "downstream_consumer_contract.json", contract)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    report = (
        "# Stage12590 Semantic-Review Quarantine Overlay\n\n"
        "The pinned Stage12589 input contains exactly 20 reviewed mechanical candidates. "
        "Stage12590 quarantines 18 and retains 2 only as non-admitting semantic-review survivors.\n\n"
        "All authority remains false. Mechanical classification is insufficient, policy correctness is unresolved, "
        "and 100% source, session, and repository-family concentration blocks scale claims.\n"
    )
    (out / "STAGE12590_SEMANTIC_REVIEW_QUARANTINE_OVERLAY.md").write_text(report, encoding="utf-8")
    return summary


def main() -> int:
    summary = execute()
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
