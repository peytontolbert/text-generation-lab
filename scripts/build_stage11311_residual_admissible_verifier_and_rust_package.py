#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11311
NAME = "stage11311_residual_admissible_verifier_and_rust_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "residual_admissible_verifier_and_rust_package.json"

BASE = ARTIFACTS / "stage11306_clean_per_option_semantic_candidate_package"
BASE_SPLITS = {
    "train": BASE / "clean_per_option_semantic_candidate_train_rows.jsonl",
    "validation": BASE / "clean_per_option_semantic_candidate_validation_rows.jsonl",
    "strict": BASE / "clean_per_option_semantic_candidate_strict_rows.jsonl",
    "judgment_validation": BASE / "clean_per_option_semantic_candidate_judgment_validation_rows.jsonl",
    "judgment_strict": BASE / "clean_per_option_semantic_candidate_judgment_strict_rows.jsonl",
    "residual": BASE / "clean_per_option_semantic_candidate_residual_rows.jsonl",
}

ADMITTED_INPUTS = {
    "explicit_verifier_transition": ARTIFACTS
    / "stage11161_explicit_verifier_transition_admission_audit/admitted_explicit_verifier_transition_rows.jsonl",
    "external_fail_to_pass": ARTIFACTS
    / "stage11167_external_commit_fail_to_pass_admission_audit/admitted_external_commit_fail_to_pass_rows.jsonl",
    "rust_replacement_evidence": ARTIFACTS
    / "stage11194_rust_replacement_admission_audit/admitted_rust_replacement_rows.jsonl",
}

OUT_SPLITS = {
    "train": OUT_DIR / "residual_admissible_train_rows.jsonl",
    "validation": OUT_DIR / "residual_admissible_validation_rows.jsonl",
    "strict": OUT_DIR / "residual_admissible_strict_rows.jsonl",
    "judgment_validation": OUT_DIR / "residual_admissible_judgment_validation_rows.jsonl",
    "judgment_strict": OUT_DIR / "residual_admissible_judgment_strict_rows.jsonl",
    "residual": OUT_DIR / "residual_admissible_residual_rows.jsonl",
    "added_train": OUT_DIR / "added_residual_admissible_train_rows.jsonl",
    "blocked": OUT_DIR / "blocked_residual_admissible_rows.jsonl",
    "option_audit": OUT_DIR / "residual_admissible_option_audit.jsonl",
}

EVIDENCE_ROLES = {
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
    "external_analogue_reference",
    "algorithmic_background_reference",
    "background_context",
}
TRANSITIONS = [
    "FAIL_TO_PASS",
    "PASS_TO_PASS",
    "FAIL_TO_FAIL",
    "NOT_EXERCISED",
    "INSUFFICIENT_EVIDENCE",
    "NEEDS_VERIFIER",
]


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def root_key(row: dict[str, Any]) -> str:
    return str(
        row.get("root_id")
        or row.get("source_root_id")
        or row.get("root_lineage_key")
        or row.get("row_id")
        or ""
    )


def target_label(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    for value in [
        target.get("bounded_choice_target_label"),
        row.get("bounded_choice_target_label"),
        target.get("target_text"),
        row.get("target_text"),
        target.get("target_ref"),
        row.get("target_ref"),
        row.get("decoder_text"),
    ]:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def gold_value(row: dict[str, Any]) -> str:
    sps = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    for value in [sps.get("gold_value"), row.get("semantic_target_value"), row.get("gold_value")]:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def transition_from_value(value: str) -> str:
    text = str(value).upper()
    for transition in TRANSITIONS:
        if transition in text:
            return transition
    return "NONE"


def test_id_from_value(value: str) -> str:
    text = str(value).strip()
    if "|" in text:
        return text.split("|", 1)[0].strip()
    match = re.match(r"([A-Z]+\d+)\b", text)
    return match.group(1) if match else ""


def role_from_value(value: str, task_type: str) -> str:
    raw = str(value).strip()
    prefix = raw.split("|", 1)[0].strip()
    if prefix in EVIDENCE_ROLES:
        return prefix
    if task_type.startswith("verifier_outcome") or transition_from_value(raw) != "NONE":
        return "verifier_and_test_constraint"
    if raw.upper().startswith("ABSTAIN") or "INSUFFICIENT" in raw.upper():
        return "insufficient_evidence_option"
    return "candidate_value_surface"


def all_options(row: dict[str, Any]) -> list[dict[str, Any]]:
    sps = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    options = sps.get("opaque_options") or row.get("opaque_options") or []
    return [option for option in options if isinstance(option, dict)]


def infer_target_label_from_gold(row: dict[str, Any], options: list[dict[str, Any]]) -> str:
    gold = gold_value(row)
    for option in options:
        if str(option.get("value") or "").strip() == gold:
            return str(option.get("label") or "").strip()
    return ""


def option_semantics(option: dict[str, Any], *, row: dict[str, Any], option_index: int) -> tuple[dict[str, Any], dict[str, Any]]:
    task = str(row.get("task_type") or "").strip()
    label = str(option.get("label") or "").strip()
    value = str(option.get("value") or "").strip()
    transition = transition_from_value(value)
    role = role_from_value(value, task)
    metadata = {
        "schema_version": "stage11311_per_option_semantic_candidate_v2",
        "option_index": option_index,
        "candidate_label": label,
        "candidate_value_family": "verifier_transition"
        if transition != "NONE"
        else ("evidence_role" if role in EVIDENCE_ROLES else "generic_candidate"),
        "task_type": task,
        "evidence_role": role,
        "verifier_transition": transition,
        "test_id": test_id_from_value(value),
        "value_token_count_proxy": len(value.replace("|", " ").split()),
    }
    out = dict(option)
    out["semantic_candidate"] = metadata
    audit = {
        "row_id": row.get("row_id"),
        "label": label,
        "value": value,
        **metadata,
    }
    return out, audit


def prompt_prefix(row: dict[str, Any]) -> str:
    prompt = str(row.get("prompt_text") or row.get("input_text") or row.get("encoder_text") or "")
    markers = ["\nOptions:", "\nChoices:", "\nCandidate options:"]
    cut = len(prompt)
    for marker in markers:
        idx = prompt.find(marker)
        if idx >= 0:
            cut = min(cut, idx)
    return prompt[:cut]


def prompt_target_leak(row: dict[str, Any], options: list[dict[str, Any]], label: str) -> list[str]:
    prefix = prompt_prefix(row)
    leaks: list[str] = []
    target_value = ""
    for option in options:
        if str(option.get("label") or "").strip() == label:
            target_value = str(option.get("value") or "").strip()
            break
    if target_value and target_value in prefix:
        # Transition labels such as FAIL_TO_PASS are task vocabulary; exact long option values are not.
        if len(target_value) > 24 or "|" in target_value:
            leaks.append("target_option_value_visible_before_options")
    return leaks


def normalize_row(row: dict[str, Any], *, source_name: str) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    out = dict(row)
    out["split"] = "train"
    out["split_role"] = "train_support"
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["support_package_stage"] = STAGE
    out["source_split_before_stage11311"] = source_name
    out["semantic_candidate_schema_version"] = "stage11311_per_option_semantic_candidate_v2"

    raw_options = all_options(out)
    normalized_options: list[dict[str, Any]] = []
    option_audits: list[dict[str, Any]] = []
    for idx, option in enumerate(raw_options):
        normalized, audit = option_semantics(option, row=out, option_index=idx)
        normalized_options.append(normalized)
        option_audits.append(audit)

    sps = dict(out.get("standalone_projection_source") or {})
    sps["opaque_options"] = normalized_options
    sps["option_semantic_schema_version"] = "stage11311_per_option_semantic_candidate_v2"
    sps["option_semantic_records"] = [opt.get("semantic_candidate") for opt in normalized_options]
    if gold_value(out):
        sps.setdefault("gold_value", gold_value(out))
    out["standalone_projection_source"] = sps
    out["opaque_options"] = normalized_options

    label = target_label(out)
    inferred = infer_target_label_from_gold(out, normalized_options)
    if not label and inferred:
        out["target_text"] = inferred
        out["decoder_text"] = inferred
        out["bounded_choice_target_label"] = inferred
        label = inferred
    if label:
        out["target_text"] = label
        out["decoder_text"] = label
        out["bounded_choice_target_label"] = label

    blockers: list[str] = []
    if len(normalized_options) <= 1:
        blockers.append("singleton_or_missing_options")
    if not label:
        blockers.append("missing_target_label")
    if label and not any(str(opt.get("label") or "").strip() == label for opt in normalized_options):
        blockers.append("target_label_not_in_options")
    if not all(isinstance(opt.get("semantic_candidate"), dict) for opt in normalized_options):
        blockers.append("missing_per_option_semantic_metadata")
    blockers.extend(prompt_target_leak(out, normalized_options, label))

    audit = {
        "row_id": out.get("row_id"),
        "source_name": source_name,
        "root_id": root_key(out),
        "language_family": out.get("language_family"),
        "task_type": out.get("task_type"),
        "target_label": label,
        "gold_value": gold_value(out),
        "option_count": len(normalized_options),
        "blockers": blockers,
        "admitted": not blockers,
    }
    return out, option_audits, audit


def counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "roots": len({root_key(row) for row in rows}),
        "by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in rows).items())),
        "by_task": dict(sorted(Counter(str(row.get("task_type") or "unknown") for row in rows).items())),
        "by_target_label": dict(sorted(Counter(target_label(row) or "unknown" for row in rows).items())),
        "by_target_value": dict(sorted(Counter(gold_value(row) or "unknown" for row in rows).items())),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = {split: read_jsonl(path) for split, path in BASE_SPLITS.items()}
    protected_roots = {
        root_key(row)
        for split in ("validation", "strict", "judgment_validation", "judgment_strict", "residual")
        for row in base[split]
    }
    existing_ids = {str(row.get("row_id") or "") for rows in base.values() for row in rows}
    train_roots = {root_key(row) for row in base["train"]}

    added_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    option_audits: list[dict[str, Any]] = []
    row_audits: list[dict[str, Any]] = []
    for source_name, path in ADMITTED_INPUTS.items():
        for row in read_jsonl(path):
            normalized, option_audit, row_audit = normalize_row(row, source_name=source_name)
            blockers = list(row_audit["blockers"])
            row_id = str(normalized.get("row_id") or "")
            rk = root_key(normalized)
            if row_id in existing_ids:
                blockers.append("row_id_already_in_base_package")
            if rk in protected_roots:
                blockers.append("root_overlaps_protected_split")
            if rk in train_roots:
                blockers.append("root_already_in_base_train")
            row_audit["blockers"] = blockers
            row_audit["admitted"] = not blockers
            row_audits.append(row_audit)
            option_audits.extend(option_audit)
            if blockers:
                blocked = dict(normalized)
                blocked["stage11311_blockers"] = blockers
                blocked_rows.append(blocked)
                continue
            normalized["stage11311_support_provenance"] = {
                "source_name": source_name,
                "source_manifest": rel(path),
                "support_role": "train_support_only",
                "claim_scope": "admitted residual repair support; not promotable heldout evidence",
            }
            added_rows.append(normalized)
            existing_ids.add(row_id)
            train_roots.add(rk)

    merged_train = base["train"] + added_rows
    outputs = {
        "train": merged_train,
        "validation": base["validation"],
        "strict": base["strict"],
        "judgment_validation": base["judgment_validation"],
        "judgment_strict": base["judgment_strict"],
        "residual": base["residual"],
        "added_train": added_rows,
        "blocked": blocked_rows,
        "option_audit": option_audits,
    }
    for split, rows in outputs.items():
        write_jsonl(OUT_SPLITS[split], rows)

    final_train_roots = {root_key(row) for row in merged_train}
    protected_overlap = sorted(final_train_roots & protected_roots)
    added_target_values = [gold_value(row) or "unknown" for row in added_rows]
    added_has_fail_to_pass = any("FAIL_TO_PASS" in value for value in added_target_values)
    added_has_rust_evidence = any(
        str(row.get("language_family") or "") == "rust" and str(row.get("task_type") or "") == "evidence_citation"
        for row in added_rows
    )
    probe_worthy = bool(added_rows) and not protected_overlap and (added_has_fail_to_pass or added_has_rust_evidence)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": probe_worthy and not blocked_rows,
        "decision": "residual_admissible_support_package_probe_worthy"
        if probe_worthy and not blocked_rows
        else (
            "partial_clean_support_built_but_not_probe_worthy"
            if added_rows and not protected_overlap
            else "residual_admissible_support_package_blocked_or_empty"
        ),
        "source_stage": "stage11306_clean_per_option_semantic_candidate_package",
        "source_artifacts": {
            "base_package": rel(BASE / "clean_per_option_semantic_candidate_package.json"),
            **{name: rel(path) for name, path in ADMITTED_INPUTS.items()},
        },
        "counts": {
            "base_train": counts(base["train"]),
            "added_train": counts(added_rows),
            "merged_train": counts(merged_train),
            "validation": counts(base["validation"]),
            "strict": counts(base["strict"]),
            "judgment_validation": counts(base["judgment_validation"]),
            "judgment_strict": counts(base["judgment_strict"]),
            "residual": counts(base["residual"]),
            "blocked": counts(blocked_rows),
        },
        "audit": {
            "candidate_rows_seen": sum(len(read_jsonl(path)) for path in ADMITTED_INPUTS.values()),
            "added_rows": len(added_rows),
            "blocked_rows": len(blocked_rows),
            "protected_root_overlap_count": len(protected_overlap),
            "protected_root_overlaps": protected_overlap[:50],
            "blocker_counts": dict(
                sorted(Counter(reason for row in row_audits for reason in row.get("blockers", [])).items())
            ),
            "all_added_rows_have_per_option_metadata": all(
                all(isinstance(opt.get("semantic_candidate"), dict) for opt in all_options(row)) for row in added_rows
            ),
            "all_added_rows_are_train_support_only": all(row.get("train_support_only") is True for row in added_rows),
            "added_has_fail_to_pass": added_has_fail_to_pass,
            "added_has_rust_evidence": added_has_rust_evidence,
            "probe_worthy": probe_worthy,
            "row_audit": row_audits,
        },
        "outputs": {name: rel(path) for name, path in OUT_SPLITS.items()},
        "next_action": {
            "recommended_stage": "stage11312_residual_admissible_verifier_and_rust_probe_request"
            if probe_worthy and not blocked_rows
            else "repair_fail_to_pass_prompt_leakage_and_fresh_rust_anchors_before_probe",
            "probe_policy": "use stable scored interface first; semantic-candidate metadata remains attached for later scorer work",
            "promotion_gates": [
                "clean strict remains 22/22",
                "clean validation >= 20/23",
                "residual bank improves beyond 5/10",
                "verifier_and_test_constraint residual improves beyond 0/3",
            ],
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
