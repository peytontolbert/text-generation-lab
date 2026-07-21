#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12536_stage12535_semantic_risk_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12534_SUMMARY = ROOT / "runs/summaries/stage12534_fresh_hydratable_verifier_observation_admission_gate.json"
STAGE12535_SUMMARY = ROOT / "runs/summaries/stage12535_public_local_repo_verifier_observation_supply.json"
STAGE12535_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12535_public_local_repo_verifier_observation_supply"
    / "sanitized_public_local_verifier_observation_rows.jsonl"
)
STAGE12535_MANIFEST = (
    ROOT
    / "runs/local/artifacts/stage12535_public_local_repo_verifier_observation_supply"
    / "deterministic_public_local_repo_producer_manifest.json"
)

BLOCKED_ROWS_NAME = "stage12535_demoted_semantic_risk_rows.jsonl"
AUDIT_NAME = "stage12535_semantic_grounding_audit.json"
REPAIR_NAME = "stage12535_exact_repair_requirements.json"

RAW_KEY_RE = re.compile(
    r"^(input_text|prompt_text|decoder_text|command|cmd|argv|cwd|stdout|stderr|"
    r"stdout_tail|stderr_tail|stdout_excerpt|stderr_excerpt|output|path|url|diff|patch|"
    r"patch_body|patch_diff|source_text|content|raw_.*)$",
    re.IGNORECASE,
)
RAW_VALUE_RE = re.compile(
    r"https?://|www\.|(^|\n)(diff --git|@@ |\+{3} |--- )|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){1,}[A-Za-z0-9._-]+|"
    r"\b(python|pytest|cargo|npm|yarn|pnpm|bash|sh|git|ctest|cmake)\b.+"
    r"\s(-m|-q|test|run|build|--test-dir|checkout|diff)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE,
)
RISKY_CLAIM_FIELDS = (
    "training_allowed",
    "strict_eval_eligible",
    "source_heldout_admissible",
    "level3_admitted",
    "level4_admitted",
    "patch_trace_admitted",
    "repair_claim_admitted",
    "fail_to_pass_claim_admitted",
    "counts_toward_unbounded_patch_trace_floor",
    "counts_toward_strict_eval_floor",
    "counts_toward_source_heldout_floor",
)
COMMAND_OBSERVATION_FIELDS = (
    "verifier_command_ref_hash",
    "verifier_command_hash",
    "verifier_invocation_hash",
    "verifier_exit_status_class",
    "verifier_exit_code_class",
    "verifier_stdout_hash",
    "verifier_stderr_hash",
    "verifier_output_hash",
    "verifier_observation_hash",
    "command_output_observation_hash",
    "command_output_digest_hash",
    "observed_command_result_hash",
)
TARGETS = {
    "PASS_CURRENT_STATE",
    "FAIL_CURRENT_STATE",
    "NOT_EXERCISED",
    "INSUFFICIENT_EVIDENCE",
    "CONTINUE_SINGLE_VERIFIER_EVIDENCE",
    "STOP_NO_MORE_VERIFIER_EVIDENCE",
}


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                value["__line_no"] = line_no
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


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value > 0
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return False


def iter_strings(value: Any, key: str = ""):
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield from iter_strings(child, str(child_key))
    elif isinstance(value, list):
        for child in value:
            yield from iter_strings(child, key)
    elif isinstance(value, str):
        yield key, value


def guardrail_scan(*objects: Any) -> dict[str, Any]:
    issues = []
    for obj in objects:
        for key, text in iter_strings(obj):
            if RAW_KEY_RE.search(key):
                issues.append({"kind": "raw_key", "key": key})
            elif RAW_VALUE_RE.search(text):
                issues.append({"kind": "raw_value", "key": key, "value_hash": stable_hash(text)})
    return {
        "scan_passed": not issues,
        "raw_leak_count": len(issues),
        "issues": issues[:50],
        "scan_scope": "stage12536_hash_class_only_semantic_risk_outputs",
    }


def risky_claims(row: dict[str, Any]) -> list[str]:
    claims = []
    for field in RISKY_CLAIM_FIELDS:
        if truthy(row.get(field)):
            claims.append(field)
    return claims


def has_command_output_observation(row: dict[str, Any]) -> bool:
    present_fields = {field for field in COMMAND_OBSERVATION_FIELDS if row.get(field)}
    has_status = bool(
        row.get("verifier_exit_status_class")
        or row.get("verifier_exit_code_class")
        or row.get("verifier_status_observed") is True
    )
    has_output_digest = bool(
        row.get("verifier_stdout_hash")
        or row.get("verifier_stderr_hash")
        or row.get("verifier_output_hash")
        or row.get("command_output_digest_hash")
        or row.get("observed_command_result_hash")
    )
    return len(present_fields) >= 2 and has_status and has_output_digest


def stage12535_metadata_only(summary: dict[str, Any], manifest: dict[str, Any]) -> bool:
    policy = str(manifest.get("source_policy") or summary.get("source_policy") or "")
    claim_boundary = " ".join(
        str(value)
        for value in (
            manifest.get("claim_boundary"),
            summary.get("claim_boundary"),
            manifest.get("record_type"),
            summary.get("record_type"),
        )
        if value
    ).lower()
    return (
        policy == "public_local_git_repos_hash_only"
        or "public local repo metadata" in claim_boundary
        or "hash/class-only" in claim_boundary
    )


def rotated_label_signal(rows: list[dict[str, Any]]) -> bool:
    if len(rows) < len(TARGETS) * 2:
        return False
    labels = [str(row.get("target_semantic_value") or "") for row in rows]
    if any(label not in TARGETS for label in labels):
        return False
    first_cycle = labels[: len(TARGETS)]
    if set(first_cycle) != TARGETS:
        return False
    return labels[: min(len(rows), 60)] == [
        first_cycle[index % len(first_cycle)] for index in range(min(len(rows), 60))
    ]


def semantic_grounding_audit(rows: list[dict[str, Any]], summary: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    observed_rows = [row for row in rows if has_command_output_observation(row)]
    missing_observation_count = len(rows) - len(observed_rows)
    risky_claim_count = sum(1 for row in rows if risky_claims(row))
    metadata_only = stage12535_metadata_only(summary, manifest)
    label_rotation = rotated_label_signal(rows)
    semantically_grounded = bool(rows) and len(observed_rows) == len(rows) and not metadata_only and not label_rotation
    weak_reasons = []
    if not rows:
        weak_reasons.append("stage12535_no_rows_available")
    if metadata_only:
        weak_reasons.append("stage12535_declares_public_local_repo_metadata_hash_only_source")
    if missing_observation_count:
        weak_reasons.append("stage12535_rows_lack_real_command_output_observation_hashes")
    if label_rotation:
        weak_reasons.append("stage12535_target_labels_match_deterministic_rotation_pattern")
    if risky_claim_count:
        weak_reasons.append("stage12535_contains_risky_claim_flags")
    return {
        "semantically_grounded": semantically_grounded,
        "metadata_only_source_signal": metadata_only,
        "deterministic_label_rotation_signal": label_rotation,
        "row_count": len(rows),
        "rows_with_command_output_observation": len(observed_rows),
        "rows_missing_command_output_observation": missing_observation_count,
        "risky_claim_row_count": risky_claim_count,
        "weak_reasons": weak_reasons,
    }


def demoted_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "source_stage": row.get("source_stage") or "stage12535_public_local_repo_verifier_observation_supply",
        "candidate_ref_hash": stable_hash({"line": row.get("__line_no"), "row": row}),
        "source_line_hash": row.get("source_line_hash") or stable_hash(row.get("__line_no")),
        "root_lineage_key_hash": row.get("root_lineage_key_hash") or stable_hash(row.get("__line_no")),
        "repo_family_hash": row.get("repo_family_hash") or stable_hash(row.get("source_stage") or "unknown"),
        "language_family": row.get("language_family") or "unknown",
        "task_projection": row.get("task_projection") or "unknown",
        "observed_target_semantic_value": row.get("target_semantic_value") or "unknown",
        "observed_verifier_status": row.get("verifier_status") or "unknown",
        "semantic_admission": "blocked_demoted_metadata_inventory_only",
        "countable_train_support": False,
        "training_allowed": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
        "blocked_reasons": [
            "no_command_output_verifier_observation_present",
            "metadata_inventory_row_not_training_claim",
            "requires_semantic_repair_before_stage12534_admission",
        ],
    }


def repair_requirements() -> dict[str, Any]:
    return {
        "stage": STAGE,
        "required_before_any_training_claim": [
            "Replace each Stage12535 inventory row with a fresh row derived from an actual verifier command execution, not index-rotated labels.",
            "Record only sanitized hashes/classes: command invocation hash, repo/commit hash, verifier exit-status class, stdout/stderr or combined output digest hash, and target/status derived from that observation.",
            "Bind every target_semantic_value to the observed verifier result with a review note or rule id hash; do not infer PASS, FAIL, continue, or stop from row position.",
            "Run the Stage12534 supply validator on the repaired JSONL and require zero raw leaks, zero duplicate keys, no collapse groups, and zero Level3/patch-trace/repair/strict/source-heldout claims.",
            "Keep training_allowed false until a separate semantic review/admission stage confirms the repaired rows and the 500 countable train-support floor is reached.",
        ],
        "forbidden_until_proven": [
            "Level3 admission",
            "patch-trace admission",
            "repair or fail-to-pass credit",
            "strict-eval eligibility",
            "source-heldout admissibility",
            "Gemma/product or training-progress claims",
        ],
        "content_exposure_policy": "Do not emit unsanitized source text, paths, URLs, commands, diffs, stdout, or stderr; emit hashes/classes only.",
    }


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12534 = read_json(STAGE12534_SUMMARY)
    stage12535 = read_json(STAGE12535_SUMMARY)
    manifest = read_json(STAGE12535_MANIFEST)
    rows = read_jsonl(STAGE12535_ROWS)

    audit = semantic_grounding_audit(rows, stage12535, manifest)
    blocked = [demoted_row(row) for row in rows] if not audit["semantically_grounded"] else []
    target_counts = Counter(str(row.get("target_semantic_value") or "unknown") for row in rows)
    language_counts = Counter(str(row.get("language_family") or "unknown") for row in rows)
    projection_counts = Counter(str(row.get("task_projection") or "unknown") for row in rows)
    scan = guardrail_scan(audit, blocked, repair_requirements())

    decision = (
        "stage12535_blocked_demoted_semantically_weak_metadata_inventory"
        if not audit["semantically_grounded"]
        else "stage12535_grounded_rollup_pending_separate_semantic_review"
    )
    training_blockers = []
    if not audit["semantically_grounded"]:
        training_blockers.extend(audit["weak_reasons"])
    training_blockers.extend(
        [
            "separate_semantic_review_not_passed",
            "training_allowed_remains_false_by_stage12536_policy",
        ]
    )
    if stage12534.get("training_allowed") is not False:
        training_blockers.append("stage12534_training_state_not_false")

    audit_path = OUT / AUDIT_NAME
    blocked_path = OUT / BLOCKED_ROWS_NAME
    repair_path = OUT / REPAIR_NAME
    write_json(audit_path, audit)
    write_jsonl(blocked_path, blocked)
    write_json(repair_path, repair_requirements())

    summary = {
        "stage": STAGE,
        "record_type": "stage12535_semantic_risk_audit_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12536 is a hash/class-only semantic risk gate over Stage12535. It grants no training, "
            "Level3, patch-trace, repair, fail-to-pass, strict-eval, source-heldout, Gemma/product, or "
            "training-progress claim."
        ),
        "stage12534_decision": stage12534.get("decision") or "unknown",
        "stage12535_record_type": stage12535.get("record_type") or manifest.get("record_type") or "unknown",
        "stage12535_input_hashes": {
            "summary": file_hash(STAGE12535_SUMMARY),
            "manifest": file_hash(STAGE12535_MANIFEST),
            "rows": file_hash(STAGE12535_ROWS),
        },
        "semantic_grounding": audit,
        "demotion": {
            "stage12535_rows_demoted_from_training_claims": not audit["semantically_grounded"],
            "blocked_row_count": len(blocked),
            "blocked_rows_ref": str(blocked_path.relative_to(ROOT)),
        },
        "repair_requirements_ref": str(repair_path.relative_to(ROOT)),
        "artifact_refs": {
            "semantic_grounding_audit": str(audit_path.relative_to(ROOT)),
            "demoted_rows": str(blocked_path.relative_to(ROOT)),
            "repair_requirements": str(repair_path.relative_to(ROOT)),
        },
        "source_inventory": {
            "stage12535_row_count": len(rows),
            "stage12535_manifest_emitted_row_count": int(stage12535.get("emitted_row_count") or 0),
            "target_counts": dict(sorted(target_counts.items())),
            "language_counts": dict(sorted(language_counts.items())),
            "projection_counts": dict(sorted(projection_counts.items())),
        },
        "guardrail_scan_passed": scan["scan_passed"],
        "raw_leak_count": scan["raw_leak_count"],
        "training_allowed": False,
        "countable_train_support": False,
        "countable_train_support_count": 0,
        "new_countable_train_support_count": 0,
        "level3_admitted_rows": 0,
        "patch_trace_admitted_rows": 0,
        "repair_claim_admitted_rows": 0,
        "fail_to_pass_claim_admitted_rows": 0,
        "strict_eval_eligible_count": 0,
        "source_heldout_admissible_count": 0,
        "gemma_or_product_claims": 0,
        "training_blockers": sorted(set(training_blockers)),
        "next_stage": (
            "repair_stage12535_with_real_command_output_verifier_observations_then_rerun_stage12534_and_semantic_review"
        ),
    }
    write_json(SUMMARY, summary)
    return summary


def main() -> None:
    build()


if __name__ == "__main__":
    main()
