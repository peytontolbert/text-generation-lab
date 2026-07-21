#!/usr/bin/env python3
"""Audit public-safe sources for trusted private executor binding clues.

Stage12526 is a narrow follow-up to Stage12525. It does not prove readiness and
does not write Stage12521 manifests. It consumes Stage12525 and Stage12510
public-safe artifacts, then scans only public-safe filename/metadata surfaces for
possible trusted ai_env binding or authorized return-writer source files.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12526_private_executor_binding_source_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12510 = "stage12510_ai_env_private_extraction_executor_readiness_audit"
STAGE12525 = "stage12525_private_executor_readiness_manifest_builder"

SLOT_COUNT = 343
PUBLIC_SCAN_DIRS = ("configs", "runs/local/artifacts", "runs/summaries")
EXCLUDED_PARTS = {
    ".git",
    ".agents",
    ".codex",
    "runs/local/private",
    "tmp",
    "__pycache__",
    f"runs/local/artifacts/{STAGE12510}",
    f"runs/local/artifacts/{STAGE12525}",
    f"runs/local/artifacts/{STAGE}",
}
ALLOWED_SUFFIXES = {".json", ".jsonl", ".yaml", ".yml", ".toml", ".py", ".md", ".txt"}
BINDING_TERMS = ("binding", "resolver", "executor", "ai_env", "private", "authorized", "writer")
MANIFEST_TERMS = ("manifest", "config", "contract", "readiness", "source")

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output|verifier output|commit:)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)
FORBIDDEN_PUBLIC_KEYS = {
    "raw",
    "raw_output",
    "raw_outputs",
    "raw_diff",
    "diff",
    "patch",
    "command",
    "commands",
    "cmd",
    "path",
    "paths",
    "file_path",
    "source_text",
    "source_content",
    "verifier_output",
    "stdout",
    "stderr",
    "terminal_output",
    "policy_label",
    "policy_label_hash",
    "training_row",
    "training_rows",
    "admitted_row",
    "level3_atom",
    "patch_trace",
    "proof_row",
}

FALSE_GUARDS = {
    "readiness_fabricated": False,
    "stage12521_readiness_manifests_written": False,
    "candidate_returns_written": False,
    "validated_returns_written": False,
    "stage12516_candidate_rows_written": False,
    "stage12503_return_file_written": False,
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
    "network_performed_by_stage": False,
    "policy_label_materialized": False,
    "level3_atom_materialized": False,
    "patch_trace_materialized": False,
    "raw_source_output_included": False,
    "raw_private_values_revealed": False,
}
ZERO_GUARDS = {
    "stage12521_readiness_manifest_count": 0,
    "candidate_return_records_written": 0,
    "validated_return_records_written": 0,
    "stage12516_candidate_row_count": 0,
    "stage12503_return_records_written": 0,
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "level3_atom_count": 0,
    "patch_trace_admitted": 0,
    "patch_trace_rows": 0,
    "policy_labels_emitted": 0,
    "proof_rows_emitted": 0,
    "executor_return_records_written": 0,
}


class RawLeakError(ValueError):
    pass


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def scan_raw_leaks(value: Any) -> list[str]:
    issues: list[str] = []
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(stable_hash(value))
    elif isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_PUBLIC_KEYS:
                issues.append(stable_hash({"forbidden_key": key}))
            issues.extend(scan_raw_leaks(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan_raw_leaks(child))
    return issues


def enforce_no_raw_leaks(value: Any) -> None:
    issues = scan_raw_leaks(value)
    if issues:
        raise RawLeakError(f"stage12526 raw leak guard rejected {len(issues)} public field(s)")


def prior_artifacts(root: Path) -> dict[str, Any]:
    artifacts = root / "runs/local/artifacts"
    summaries = root / "runs/summaries"
    return {
        "stage12525_summary": read_json(artifacts / STAGE12525 / "summary.json")
        or read_json(summaries / f"{STAGE12525}.json"),
        "stage12525_blockers": read_jsonl(artifacts / STAGE12525 / "private_executor_readiness_manifest_blockers.jsonl"),
        "stage12510_contract": read_json(
            artifacts / STAGE12510 / "ai_env_private_extraction_executor_readiness_contract.json"
        ),
        "stage12510_blockers": read_jsonl(artifacts / STAGE12510 / "ai_env_private_extraction_executor_blockers.jsonl"),
        "stage12510_classifications": read_jsonl(artifacts / STAGE12510 / "executor_candidate_classifications.jsonl"),
    }


def safe_scan_roots(root: Path) -> list[Path]:
    return [root / name for name in PUBLIC_SCAN_DIRS if (root / name).exists()]


def is_excluded(root: Path, candidate: Path) -> bool:
    rel = candidate.relative_to(root).as_posix()
    return any(rel == excluded or rel.startswith(f"{excluded}/") for excluded in EXCLUDED_PARTS)


def iter_public_metadata_files(root: Path) -> Iterable[Path]:
    for scan_root in safe_scan_roots(root):
        for candidate in scan_root.rglob("*"):
            if not candidate.is_file():
                continue
            if is_excluded(root, candidate):
                continue
            if candidate.suffix.lower() in ALLOWED_SUFFIXES:
                yield candidate


def classify_candidate_name(name: str) -> tuple[bool, str]:
    normalized = name.lower().replace("-", "_")
    has_binding = any(term in normalized for term in BINDING_TERMS)
    has_manifest = any(term in normalized for term in MANIFEST_TERMS)
    if not (has_binding and has_manifest):
        return False, "not_binding_writer_source_name"
    if "readiness_manifest" in normalized and "stage12521" in normalized:
        return True, "existing_stage12521_readiness_manifest_name_only_not_proof"
    if "authorized" in normalized and "writer" in normalized:
        return True, "authorized_return_writer_candidate_name"
    if "binding" in normalized or "resolver" in normalized:
        return True, "trusted_binding_candidate_name"
    return True, "private_executor_config_candidate_name"


def candidate_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in sorted(iter_public_metadata_files(root), key=lambda item: item.relative_to(root).as_posix()):
        include, reason = classify_candidate_name(candidate.name)
        if not include:
            continue
        rel = candidate.relative_to(root).as_posix()
        row = {
            "record_type": "stage12526_public_safe_candidate_binding_source_v1",
            "candidate_binding_source_id_hash": stable_hash(rel),
            "candidate_name": candidate.name,
            "candidate_parent_name": candidate.parent.name,
            "candidate_ref_hash": stable_hash({"rel": rel, "suffix": candidate.suffix.lower()}),
            "candidate_suffix": candidate.suffix.lower(),
            "classification": reason,
            "public_safe_metadata_only": True,
            "contents_read": False,
            "trusted_binding_proven": False,
            "authorized_return_writer_proven": False,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(row)
        rows.append(row)
    return rows


def blocker_codes(artifacts: dict[str, Any]) -> list[str]:
    codes: set[str] = set()
    summary = artifacts["stage12525_summary"]
    for code in summary.get("readiness_blocker_codes") or []:
        codes.add(str(code))
    for row in artifacts["stage12525_blockers"]:
        for code in row.get("blocker_codes") or []:
            codes.add(str(code))
    for row in artifacts["stage12510_blockers"]:
        for code in row.get("blocker_codes") or []:
            codes.add(str(code))
    contract = artifacts["stage12510_contract"]
    if contract.get("executor_binding_env"):
        codes.add("trusted_ai_env_private_extractor_binding_env_unproven")
    if not codes:
        codes.update(
            [
                "trusted_ai_env_private_extractor_binding_missing",
                "no_authorized_stage12503_return_writer_configured",
            ]
        )
    return sorted(codes)


def checklist_rows(codes: list[str], artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    blocker_count = len(artifacts["stage12525_blockers"]) or len(artifacts["stage12510_blockers"]) or SLOT_COUNT
    return [
        {
            "record_type": "stage12526_missing_binding_checklist_item_v1",
            "checklist_item_id_hash": stable_hash({"code": code, "idx": idx}),
            "missing_binding_code": code,
            "required_action": {
                "trusted_ai_env_private_extractor_binding_missing": "provide_public_safe_trusted_ai_env_private_extractor_binding_manifest",
                "no_authorized_stage12503_return_writer_configured": "provide_public_safe_authorized_stage12503_return_writer_config_manifest",
                "trusted_ai_env_private_extractor_binding_env_unproven": "bind_stage12510_executor_env_to_a_trusted_public_safe_manifest_ref",
            }.get(code, "resolve_prior_stage_private_executor_readiness_blocker"),
            "affected_stage12525_blocker_row_count": blocker_count,
            "preserved_slot_count_context": SLOT_COUNT,
            "public_safe_metadata_only": True,
            "readiness_claimed": False,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        for idx, code in enumerate(codes, start=1)
    ]


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    out.mkdir(parents=True, exist_ok=True)
    artifacts = prior_artifacts(root)
    enforce_no_raw_leaks(artifacts)

    candidates = candidate_rows(root)
    codes = blocker_codes(artifacts)
    checklist = [] if candidates else checklist_rows(codes, artifacts)
    classification_counts = Counter(row["classification"] for row in candidates)

    decision = (
        "candidate_binding_sources_found_public_safe_worklist_no_readiness_fabricated"
        if candidates
        else "blocked_missing_trusted_binding_and_authorized_writer_sources_checklist_emitted"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12526_private_executor_binding_source_audit_summary_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12526 audits only public-safe artifact metadata and filenames for possible trusted "
            "binding or authorized writer sources. It does not read candidate contents, prove readiness, "
            "write Stage12521 manifests, executor returns, Stage12516 candidates, Stage12503 rows, "
            "training, admission, Level-3 atoms, or patch-trace material."
        ),
        "source_stages": [STAGE12525, STAGE12510],
        "input_stage12525_blocker_row_count": len(artifacts["stage12525_blockers"]),
        "input_stage12510_blocker_row_count": len(artifacts["stage12510_blockers"]),
        "input_stage12510_candidate_classification_count": len(artifacts["stage12510_classifications"]),
        "preserved_slot_count_context": SLOT_COUNT,
        "stage12525_preserved_slot_identity_count": artifacts["stage12525_summary"].get("preserved_slot_identity_count"),
        "stage12525_manifest_slot_count_required": artifacts["stage12525_summary"].get("manifest_slot_count_required"),
        "prior_blocker_codes": codes,
        "public_safe_scan_roots": list(PUBLIC_SCAN_DIRS),
        "candidate_binding_source_count": len(candidates),
        "candidate_classification_counts": dict(sorted(classification_counts.items())),
        "missing_binding_checklist_count": len(checklist),
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "next_stage": (
            "review_candidate_binding_worklist_in_private_context_without_public_raw_leakage"
            if candidates
            else "provide_trusted_binding_and_authorized_writer_manifest_sources_then_rerun_stage12526"
        ),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    guardrail = {
        "stage": STAGE,
        "scan_passed": True,
        "raw_leak_count": 0,
        "raw_leak_issue_hashes": [],
        "scanned_outputs": [
            "candidate_binding_source_worklist.jsonl",
            "missing_binding_checklist.jsonl",
            "summary.json",
        ],
    }
    enforce_no_raw_leaks({"summary": summary, "candidates": candidates, "checklist": checklist, "guardrail": guardrail})
    write_jsonl(out / "candidate_binding_source_worklist.jsonl", candidates)
    write_jsonl(out / "missing_binding_checklist.jsonl", checklist)
    write_json(out / "guardrail_scan.json", guardrail)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()
