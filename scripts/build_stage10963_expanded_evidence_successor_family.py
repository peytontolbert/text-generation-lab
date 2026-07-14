#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10963
NAME = "stage10963_expanded_evidence_successor_family"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "expanded_evidence_successor_family.json"
ROWS_JSONL = OUT_DIR / "expanded_successor_rows.jsonl"

MANIFEST_ROWS = ARTIFACTS / "stage10914_evidence_successor_materialization_manifest" / "candidate_rows.jsonl"
SOURCE_ROW_FILES = [
    ARTIFACTS / "stage10828_evidence_role_probe_request" / "evidence_role_probe_manifest.jsonl",
    ARTIFACTS / "stage10782_targeted_residual_support_probe_request" / "targeted_residual_support_probe_manifest.jsonl",
    ARTIFACTS / "stage10423_reviewed_multilingual_v27_same_manifest_gemma_comparison" / "reviewed_multilingual_v27_same_manifest_gemma_rows.jsonl",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def split_prompt_sections(prompt: str) -> tuple[list[str], list[str]]:
    if "Evidence:\n" not in prompt or "\nOptions:\n" not in prompt:
        raise ValueError("prompt missing Evidence/Options sections")
    before_evidence, evidence_and_rest = prompt.split("Evidence:\n", 1)
    evidence_text, _options_and_rest = evidence_and_rest.split("\nOptions:\n", 1)
    header_lines = before_evidence.strip().splitlines()
    evidence_lines = [line for line in evidence_text.splitlines() if line.strip()]
    return header_lines, evidence_lines


def parse_evidence_map(evidence_lines: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in evidence_lines:
        key = line.split(" [", 1)[0].strip()
        if key:
            parsed[key] = line.strip()
    return parsed


def find_source_row(spec: dict[str, Any], corpus: list[dict[str, Any]]) -> dict[str, Any]:
    target_row_id = str(spec.get("current_checked_row_id") or "")
    if target_row_id:
        for row in corpus:
            if str(row.get("row_id") or "") == target_row_id:
                return row
    bundle_id = str(spec.get("source_bundle_id") or "")
    for row in corpus:
        if (
            str(row.get("source_bundle_id") or "") == bundle_id
            and str(row.get("task_type") or "") == "evidence_citation"
            and str(row.get("repo_id") or "") == str(spec.get("repo_id") or "")
        ):
            return row
    raise ValueError(f"missing source row for queue_id={spec.get('queue_id')}")


def source_options(source_row: dict[str, Any]) -> list[str]:
    values = [str(item.get("value") or "") for item in source_row.get("opaque_options") or [] if isinstance(item, dict)]
    ordered: list[str] = []
    for value in values:
        if value and value not in ordered:
            ordered.append(value)
    return ordered


def choose_surface_path(spec: dict[str, Any]) -> str:
    candidates = list(spec.get("candidate_paths") or [])
    return str(candidates[0] if candidates else "unknown_surface")


def selected_tests_string(spec: dict[str, Any]) -> str:
    selected = list(spec.get("selected_tests") or [])
    return "; ".join(selected) if selected else "no_selected_test_recorded"


def build_verifier_line(spec: dict[str, Any]) -> str:
    rationale = str(spec.get("reviewer_rationale") or "").strip()
    surface = choose_surface_path(spec)
    descriptor = rationale or "Selected tests constrain the intended repair surface more directly than the changed candidate alone."
    return (
        f"verifier_and_test_constraint [{selected_tests_string(spec)}]: "
        f"Selected-test ledger for {surface}. {descriptor}"
    )


def normalize_evidence(spec: dict[str, Any], source_row: dict[str, Any]) -> dict[str, str]:
    prompt = str(source_row.get("prompt_text") or source_row.get("input_text") or "")
    _, evidence_lines = split_prompt_sections(prompt)
    source_map = parse_evidence_map(evidence_lines)
    source_map["verifier_and_test_constraint"] = build_verifier_line(spec)
    return source_map


def option_order(option_values: list[str], seed: str, *, verifier_first: bool) -> list[str]:
    values = {value: value for value in option_values}
    remaining = sorted(values, key=lambda value: hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest())
    preferred = []
    if "candidate_change_surface" in values:
        preferred.append("candidate_change_surface")
    if "verifier_and_test_constraint" in values:
        preferred.append("verifier_and_test_constraint")
    rest = [value for value in remaining if value not in preferred]
    if verifier_first and {"candidate_change_surface", "verifier_and_test_constraint"}.issubset(values):
        return ["verifier_and_test_constraint", "candidate_change_surface", *rest]
    if (not verifier_first) and {"candidate_change_surface", "verifier_and_test_constraint"}.issubset(values):
        return ["candidate_change_surface", "verifier_and_test_constraint", *rest]
    return remaining


def relabel(option_values: list[str]) -> list[dict[str, str]]:
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if len(option_values) > len(labels):
        raise ValueError("too many options")
    return [{"label": labels[idx], "value": value} for idx, value in enumerate(option_values)]


def build_prompt(
    source_row: dict[str, Any],
    evidence_map: dict[str, str],
    option_values: list[str],
    *,
    explicit_ledger: bool,
) -> str:
    prompt = str(source_row.get("prompt_text") or source_row.get("input_text") or "")
    header_lines, _ = split_prompt_sections(prompt)
    task_line = (
        "Task: Choose the visible evidence key that most specifically justifies the edit-target decision. "
        "Use the strongest packet-visible justification rather than relying on candidate order or defaulting to the changed surface."
    )
    rewritten_header = [task_line if line.startswith("Task: ") else line for line in header_lines]
    if explicit_ledger:
        evidence_order = [
            "algorithmic_background_reference",
            "candidate_change_surface",
            "external_analogue_reference",
            "nearby_definition_or_usage_context",
            "symptom_or_call_path_analogue",
            "verifier_and_test_constraint",
        ]
    else:
        evidence_order = [
            "algorithmic_background_reference",
            "candidate_change_surface",
            "external_analogue_reference",
            "nearby_definition_or_usage_context",
            "symptom_or_call_path_analogue",
        ]
    evidence_lines = [evidence_map[key] for key in evidence_order if key in evidence_map and key in option_values or key not in {"candidate_change_surface","verifier_and_test_constraint","algorithmic_background_reference","external_analogue_reference","nearby_definition_or_usage_context","symptom_or_call_path_analogue"}]
    if explicit_ledger and "verifier_and_test_constraint" in evidence_map:
        # Keep the explicit ledger visible even though it is not in the original prompt.
        if evidence_map["verifier_and_test_constraint"] not in evidence_lines:
            evidence_lines.append(evidence_map["verifier_and_test_constraint"])
    option_lines = [f"{item['label']}. {item['value']}" for item in relabel(option_values)]
    return "\n".join([*rewritten_header, "Evidence:", *evidence_lines, "Options:", *option_lines, "Answer:", ""])


def build_row(spec: dict[str, Any], source_row: dict[str, Any], variant: str) -> dict[str, Any]:
    all_values = source_options(source_row)
    explicit_ledger = variant.startswith("ledger_")
    contrast = variant.endswith("_contrast")
    verifier_first = "_verifier_first_" in f"_{variant}_"
    if contrast:
        option_values = [value for value in all_values if value in {
            "candidate_change_surface",
            "verifier_and_test_constraint",
            "nearby_definition_or_usage_context",
            "symptom_or_call_path_analogue",
        }]
    else:
        option_values = list(all_values)
    if explicit_ledger and "verifier_and_test_constraint" not in option_values:
        option_values.append("verifier_and_test_constraint")
    ordered_values = option_order(option_values, f"{spec['queue_id']}::{variant}", verifier_first=verifier_first)
    relabeled = relabel(ordered_values)
    gold_value = str(spec.get("gold_answer_value") or "")
    target_label = next((item["label"] for item in relabeled if item["value"] == gold_value), None)
    if target_label is None:
        raise ValueError(f"missing gold value {gold_value} for {spec.get('queue_id')}::{variant}")
    evidence_map = normalize_evidence(spec, source_row)
    prompt = build_prompt(source_row, evidence_map, ordered_values, explicit_ledger=explicit_ledger)
    return {
        "anti_cheat": {
            "expanded_successor_family": True,
            "explicit_selected_test_ledger": explicit_ledger,
            "gold_conditioned_task_line": False,
            "opaque_labels": True,
            "option_order_changed_from_source": True,
            "reviewed_bundle_source": True,
            "same_surface_eval_admissible": False,
            "target_path_strings_hidden_pre_options": True,
            "variant_family": variant,
        },
        "decoder_text": target_label,
        "expected_enabled_loss": "decoder_ce",
        "input_text": prompt,
        "language_family": spec.get("language_family"),
        "loss_mask": {"decoder_ce": True},
        "objective_family": "bounded_decoder_ce",
        "opaque_options": relabeled,
        "prompt_text": prompt,
        "query_text": f"expanded_successor::{spec.get('language_family')}::{spec['queue_id']}::{variant}",
        "repo_family": spec.get("repo_id"),
        "repo_id": spec.get("repo_id"),
        "row_id": f"stage10963::{spec['queue_id']}::evidence_citation::{variant}",
        "selected_test_anchor": bool(spec.get("selected_tests")),
        "source_bundle_id": spec.get("source_bundle_id"),
        "source_heldout_admissible": False,
        "source_root_id": spec.get("source_bundle_id"),
        "split": "strict_eval_candidate_family",
        "split_role": "heldout_candidate_family_not_admitted",
        "standalone_projection_source": {
            "current_checked_row_id": spec.get("current_checked_row_id"),
            "current_checked_target_value": spec.get("current_checked_target_value"),
            "gold_value": gold_value,
            "opaque_options": relabeled,
            "projection_mode": "stage10963_expanded_successor_family",
            "queue_id": spec.get("queue_id"),
            "selected_tests": spec.get("selected_tests"),
            "candidate_paths": spec.get("candidate_paths"),
            "variant": variant,
        },
        "strict_eval_eligible": False,
        "surface": "maintainer_bundle_compact_bounded_choice",
        "target_text": target_label,
        "target_token_len": 1,
        "task_type": "evidence_citation",
        "train_support_only": False,
        "verifier_anchor": bool(spec.get("selected_tests")),
    }


def main() -> None:
    specs = load_jsonl(MANIFEST_ROWS)
    corpus: list[dict[str, Any]] = []
    for path in SOURCE_ROW_FILES:
        corpus.extend(load_jsonl(path))
    variants = [
        "raw_surface_first_full",
        "raw_verifier_first_full",
        "ledger_surface_first_full",
        "ledger_verifier_first_full",
        "raw_surface_first_contrast",
        "raw_verifier_first_contrast",
        "ledger_surface_first_contrast",
        "ledger_verifier_first_contrast",
    ]
    rows: list[dict[str, Any]] = []
    for spec in specs:
        source_row = find_source_row(spec, corpus)
        for variant in variants:
            rows.append(build_row(spec, source_row, variant))

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "expanded_python_cpp_successor_family_materialized",
        "claim_scope": [
            "Expand the 3-row B-vs-F evidence successor slice into a multi-geometry diagnostic family built from the same reviewed roots.",
            "Separate raw-source versus explicit-ledger geometries and full-option versus contrast-option variants without changing the gold target.",
        ],
        "inputs": {
            "manifest_rows": rel(MANIFEST_ROWS),
            "source_row_files": [rel(path) for path in SOURCE_ROW_FILES],
        },
        "metrics": {
            "row_count": len(rows),
            "roots": len(specs),
            "variants_per_root": len(variants),
            "rows_by_language": {
                language: sum(1 for row in rows if str(row.get("language_family") or "") == language)
                for language in sorted({str(row.get("language_family") or "") for row in rows})
            },
            "rows_by_variant": {
                variant: sum(1 for row in rows if str(row.get("row_id") or "").endswith(f"::{variant}"))
                for variant in variants
            },
        },
        "findings": [
            "This family widens the 3-row slice into raw-versus-ledger and full-versus-contrast geometries across the same reviewed roots.",
            "If only the ledger variants move, the remaining blocker is still visible-evidence materialization rather than generic scoring.",
            "If none of the variants move, the next honest branch is scorer architecture or genuinely new roots rather than more geometry shuffling on the same three roots.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "rows_jsonl": rel(ROWS_JSONL),
        },
        "next_best_step": "Score the latest runtime on this expanded family to measure geometry sensitivity before changing scorer architecture.",
    }
    write_json(SUMMARY_JSON, summary)
    write_jsonl(ROWS_JSONL, rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
