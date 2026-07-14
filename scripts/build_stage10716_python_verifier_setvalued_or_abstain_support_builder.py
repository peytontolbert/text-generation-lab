#!/usr/bin/env python3
"""Build honest Python verifier support from fresh multi-target roots.

This stage converts fresh multi-target Python verifier roots into train-only
support rows that explicitly teach abstention on underdetermined verifier
selection. It does not claim singleton recovery or promotion readiness.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
STAGE = 10716
NAME = "stage10716_python_verifier_setvalued_or_abstain_support_builder"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

INPUT_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage10715_fresh_python_verifier_contrast_builder/fresh_python_verifier_contrast_builder.json"
)
INPUT_DIAGNOSTIC = (
    ROOT
    / "runs/local/artifacts/stage10715_fresh_python_verifier_contrast_builder/diagnostic_multi_target_python_verifier_roots.jsonl"
)
TYPED_EVENTS = (
    ROOT
    / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_typed_events.jsonl"
)

SUMMARY_JSON = OUT_DIR / "python_verifier_setvalued_or_abstain_support_builder.json"
ROOTS_JSONL = OUT_DIR / "python_verifier_setvalued_root_manifest.jsonl"
ROWS_JSONL = OUT_DIR / "python_verifier_setvalued_bounded_rows.jsonl"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

ABSTAIN = "ABSTAIN_INSUFFICIENT_EVIDENCE"
CHOICE_LABELS = list("ABCDEFGHJKLMNOPQRSTUVWXYZ")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def compact(text: str, limit: int = 260) -> str:
    clean = " ".join(str(text).split())
    return clean if len(clean) <= limit else clean[: limit - 3].rstrip() + "..."


def parse_json_maybe(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def looks_like_test_target(path: str) -> bool:
    lower = path.lower()
    return (
        "/test" in lower
        or lower.startswith("tests/")
        or "/tests/" in lower
        or lower.endswith("_test.py")
        or lower.endswith("tests.py")
    )


def parse_user_task(content: str) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "repository": "",
        "query_index": "",
        "transition_target": "",
        "execution_route": "",
        "verifier_route": "",
        "changed_files": [],
        "verification_targets": [],
        "key_symbols": [],
    }
    for raw in str(content).splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if key == "Repository":
            fields["repository"] = value
        elif key == "Query index":
            fields["query_index"] = value
        elif key == "Transition target":
            fields["transition_target"] = value
        elif key == "Execution route":
            fields["execution_route"] = value
        elif key == "Verifier route":
            fields["verifier_route"] = value
        elif key == "Changed files":
            fields["changed_files"] = [part.strip() for part in value.split(",") if part.strip()]
        elif key == "Verification targets":
            fields["verification_targets"] = [part.strip() for part in value.split(",") if part.strip()]
        elif key == "Key symbols":
            fields["key_symbols"] = [part.strip() for part in value.split(",") if part.strip()]
    return fields


def build_prompt(fields: dict[str, Any], options: list[tuple[str, str]]) -> str:
    header = [
        f"Language: python",
        "Perspective: verifier_outcome",
        "Task: Choose the most honest verifier consequence from the visible evidence. If multiple tests remain plausible, abstain instead of guessing.",
        "Evidence:",
        f"candidate_change_surface: {', '.join(fields['changed_files'])}",
        f"verifier_and_test_constraint: {', '.join(fields['verification_targets'])}",
        f"nearby_definition_or_usage_context: {', '.join(fields['key_symbols']) if fields['key_symbols'] else 'No key symbols extracted.'}",
        "Options:",
    ]
    header.extend(f"{label}. {value}" for label, value in options)
    header.append("Answer:")
    return "\n".join(header) + "\n"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    stage10715 = load_json(INPUT_SUMMARY)
    diagnostic_roots = load_jsonl(INPUT_DIAGNOSTIC)
    typed_events = load_jsonl(TYPED_EVENTS)

    events_by_root: dict[str, dict[str, Any]] = {}
    for event in typed_events:
        root_id = str(event.get("root_id") or "")
        if not root_id:
            continue
        bucket = events_by_root.setdefault(root_id, {})
        event_type = str(event.get("event_type") or "")
        content = parse_json_maybe(event.get("content"))
        if event_type == "USER_TASK":
            bucket["user_task"] = str(content or "")
        elif event_type == "SEARCH_RESULT":
            bucket["search_result"] = content
        elif event_type == "TEST_RESULT":
            bucket["test_result"] = content

    deduped: list[dict[str, Any]] = []
    seen_target_sets: set[tuple[str, ...]] = set()
    quarantined: list[dict[str, Any]] = []

    for row in diagnostic_roots:
        targets = tuple(str(v) for v in row.get("verification_targets") or [])
        if not targets:
            updated = dict(row)
            updated["quarantine_reason"] = "missing_targets"
            quarantined.append(updated)
            continue
        if targets in seen_target_sets:
            updated = dict(row)
            updated["quarantine_reason"] = "duplicate_target_family_snapshot"
            quarantined.append(updated)
            continue
        seen_target_sets.add(targets)
        deduped.append(row)

    selected_roots: list[dict[str, Any]] = []
    filtered_out: list[dict[str, Any]] = []
    for row in deduped:
        targets = [str(v) for v in row.get("verification_targets") or []]
        is_test_family = all(looks_like_test_target(target) for target in targets)
        if not is_test_family:
            updated = dict(row)
            updated["quarantine_reason"] = "non_test_verification_family"
            filtered_out.append(updated)
            continue
        if len(targets) < 3:
            updated = dict(row)
            updated["quarantine_reason"] = "too_few_targets_for_useful_multitarget_support"
            filtered_out.append(updated)
            continue
        if len(targets) > 6:
            updated = dict(row)
            updated["quarantine_reason"] = "too_many_targets_for_clean_multitarget_support"
            filtered_out.append(updated)
            continue
        selected_roots.append(row)

    rows: list[dict[str, Any]] = []
    root_manifest: list[dict[str, Any]] = []

    for row in selected_roots:
        root_id = str(row["root_id"])
        event_bundle = events_by_root.get(root_id, {})
        fields = parse_user_task(str(event_bundle.get("user_task") or ""))
        targets = [str(v) for v in row.get("verification_targets") or []]
        option_values = targets + [ABSTAIN]
        if len(option_values) > len(CHOICE_LABELS):
            raise ValueError(f"too_many_options::{root_id}")
        options = list(zip(CHOICE_LABELS[: len(option_values)], option_values))
        target_label = next(label for label, value in options if value == ABSTAIN)
        prompt = build_prompt(fields, options)

        root_meta = {
            "record_type": "long_context_multitarget_verifier_support_root",
            "root_id": root_id,
            "repo_id": row.get("repo_id"),
            "repo_family": row.get("repo_family"),
            "language_family": "python",
            "task_types": ["verifier_outcome"],
            "verification_target_count": len(targets),
            "verification_targets": targets,
            "selected_test_anchor": True,
            "verifier_anchor": True,
            "abstention_heavy": True,
            "source_heldout_admissible": False,
            "train_support_only": True,
            "strict_eval_eligible": False,
            "split": "train",
            "split_role": "train_support",
            "same_surface_eval_admissible": False,
            "claim_notes": [
                "fresh_long_context_python_multitarget_verifier_support",
                "abstain_is_gold_due_to_multiple_plausible_verification_targets",
                "non_promotable_support_only",
            ],
        }
        root_manifest.append(root_meta)

        row_payload = {
            "row_id": f"{root_id}::python::verifier_outcome::multitarget_abstain_support",
            "source_root_id": root_id,
            "source_bundle_id": root_id,
            "repo_id": row.get("repo_id"),
            "repo_family": row.get("repo_family"),
            "language_family": "python",
            "task_type": "verifier_outcome",
            "split": "train",
            "split_role": "train_support",
            "train_support_only": True,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "selected_test_anchor": True,
            "verifier_anchor": True,
            "abstention_heavy": True,
            "surface": "long_context_multitarget_verifier_abstain_support",
            "objective_family": "bounded_decoder_ce",
            "package_source_kind": "long_context_multitarget_verifier_support",
            "package_split": "train",
            "prompt_text": prompt,
            "input_text": prompt,
            "query_text": "long_context::python::verifier_outcome::multitarget_abstain_support",
            "opaque_options": [{"label": label, "value": value} for label, value in options],
            "target_text": target_label,
            "decoder_text": target_label,
            "target_token_len": 1,
            "loss_mask": {"decoder_ce": True},
            "expected_enabled_loss": "decoder_ce",
            "disable_losses": [],
            "anti_cheat": {
                "compact_prompt_contract": True,
                "opaque_labels": True,
                "deterministic_option_shuffle": False,
                "same_surface_eval_admissible": False,
                "root_disjoint_from_current_frontier": True,
                "multitarget_abstain_honesty_contract": True,
                "singleton_guess_disallowed": True,
            },
            "support_contract": {
                "support_role": "honesty_abstention_for_multitarget_verifier",
                "visible_verification_targets": targets,
                "gold_value": ABSTAIN,
            },
        }
        rows.append(row_payload)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": {
            "stage10715_summary": str(INPUT_SUMMARY.relative_to(ROOT)),
            "stage10715_diagnostic_roots": str(INPUT_DIAGNOSTIC.relative_to(ROOT)),
            "typed_events": str(TYPED_EVENTS.relative_to(ROOT)),
        },
        "status": "support_only_non_promotable",
        "claim_boundary": [
            "This stage builds honest Python verifier support from fresh multi-target roots.",
            "These rows teach abstention when multiple verifier targets remain plausible.",
            "This stage does not solve the singleton MirrorMind-style verifier residual and must not be used as a promotion artifact.",
        ],
        "upstream_stage10715_status": stage10715.get("status"),
        "metrics": {
            "diagnostic_multi_target_root_count": len(diagnostic_roots),
            "deduped_root_count": len(deduped),
            "selected_support_root_count": len(selected_roots),
            "filtered_or_quarantined_count": len(quarantined) + len(filtered_out),
            "train_row_count": len(rows),
            "rows_by_repo": dict(sorted(Counter(str(row.get("repo_id")) for row in rows).items())),
            "target_count_histogram": dict(
                sorted(Counter(len(row.get("verification_targets") or []) for row in selected_roots).items())
            ),
        },
        "promotion_readiness": {
            "promotable": False,
            "reason": "no_fresh_singleton_python_verifier_roots",
            "support_value": "honesty_and_setvalued_supervision_only",
        },
        "next_best_step": (
            "Train only if you want broader verifier honesty support, but keep the promotion path separate. "
            "The next honest promotion-stage need remains fresh singleton Python verifier roots with real B-vs-C-vs-D competition."
        ),
        "outputs": {
            "summary_json": str(SUMMARY_JSON.relative_to(ROOT)),
            "root_manifest": str(ROOTS_JSONL.relative_to(ROOT)),
            "bounded_rows": str(ROWS_JSONL.relative_to(ROOT)),
            "train_rows": str(TRAIN_JSONL.relative_to(ROOT)),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(ROOTS_JSONL, root_manifest)
    write_jsonl(ROWS_JSONL, rows)
    write_jsonl(TRAIN_JSONL, rows)
    write_jsonl(VALIDATION_JSONL, [])
    write_jsonl(STRICT_JSONL, [])
    write_jsonl(STRESS_JSONL, [])
    write_jsonl(OUT_DIR / "quarantined_python_verifier_roots.jsonl", quarantined + filtered_out)


if __name__ == "__main__":
    main()
