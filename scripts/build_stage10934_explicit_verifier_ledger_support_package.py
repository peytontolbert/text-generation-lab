#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10934
NAME = "stage10934_explicit_verifier_ledger_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "explicit_verifier_ledger_support_package.json"
ROWS_JSONL = OUT_DIR / "added_explicit_verifier_ledger_rows.jsonl"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

BASE_DIR = ARTIFACTS / "stage10883_flash_attn_alias_safe_successor_package"
BASE_SUMMARY_JSON = BASE_DIR / "flash_attn_alias_safe_successor_package.json"
BASE_TRAIN_JSONL = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION_JSONL = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT_JSONL = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS_JSONL = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

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


def sanitize_train_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = "train"
    updated["train_support_only"] = True
    updated["strict_eval_eligible"] = False
    updated["disable_losses"] = []
    updated["loss_mask"] = {"decoder_ce": True}
    updated["expected_enabled_loss"] = "decoder_ce"
    return updated


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


def packet_dir_for(spec: dict[str, Any]) -> Path:
    return ROOT / str(spec["packet_dir"])


def load_gold_by_perspective(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    gold = load_json(packet_dir_for(spec) / "perspective_gold_adjudication.json")
    return {str(row.get("perspective") or ""): row for row in gold.get("perspective_gold_answers") or []}


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


def format_selected_tests(selected_tests: list[str]) -> str:
    if not selected_tests:
        return "no_selected_test_recorded"
    return "; ".join(selected_tests)


def choose_surface_path(spec: dict[str, Any], gold_by_perspective: dict[str, dict[str, Any]]) -> str:
    symptom = gold_by_perspective.get("symptom_localization") or {}
    gold_value = str(symptom.get("gold_answer_value") or "")
    if gold_value:
        return gold_value
    candidates = list(spec.get("candidate_paths") or [])
    return str(candidates[0] if candidates else "unknown_surface")


def build_verifier_line(spec: dict[str, Any], gold_by_perspective: dict[str, dict[str, Any]]) -> str:
    evidence = gold_by_perspective.get("evidence_citation") or {}
    selected_tests = list(evidence.get("selected_tests") or spec.get("selected_tests") or [])
    rationale = str(evidence.get("reviewer_rationale") or "").strip()
    surface = choose_surface_path(spec, gold_by_perspective)
    descriptor = "Selected tests constrain the intended repair surface more directly than the changed candidate alone."
    if rationale:
        descriptor = rationale
    return (
        f"verifier_and_test_constraint [{format_selected_tests(selected_tests)}]: "
        f"Selected-test ledger for {surface}. {descriptor}"
    )


def build_candidate_line(spec: dict[str, Any], gold_by_perspective: dict[str, dict[str, Any]], source_evidence: dict[str, str]) -> str:
    existing = source_evidence.get("candidate_change_surface")
    if existing:
        return existing
    surface = choose_surface_path(spec, gold_by_perspective)
    return f"candidate_change_surface [{surface}]: Changed candidate surface exposed by the reviewed packet: {surface}"


def build_evidence_lines(
    spec: dict[str, Any],
    source_row: dict[str, Any],
    variant_name: str,
    gold_by_perspective: dict[str, dict[str, Any]],
) -> list[str]:
    prompt = str(source_row.get("prompt_text") or source_row.get("input_text") or "")
    _header, original_evidence_lines = split_prompt_sections(prompt)
    source_evidence = parse_evidence_map(original_evidence_lines)

    source_evidence["candidate_change_surface"] = build_candidate_line(spec, gold_by_perspective, source_evidence)
    source_evidence["verifier_and_test_constraint"] = build_verifier_line(spec, gold_by_perspective)

    full_order = [
        "algorithmic_background_reference",
        "candidate_change_surface",
        "external_analogue_reference",
        "nearby_definition_or_usage_context",
        "symptom_or_call_path_analogue",
        "verifier_and_test_constraint",
    ]
    contrast_order = [
        "candidate_change_surface",
        "verifier_and_test_constraint",
        "nearby_definition_or_usage_context",
        "symptom_or_call_path_analogue",
    ]
    order = full_order if variant_name.startswith("ledger_full") else contrast_order
    if variant_name.endswith("verifier_first"):
        order = ["verifier_and_test_constraint", *[key for key in order if key != "verifier_and_test_constraint"]]
    elif variant_name.endswith("candidate_first"):
        order = ["candidate_change_surface", *[key for key in order if key != "candidate_change_surface"]]
    return [source_evidence[key] for key in order if key in source_evidence]


def build_option_pool(source_row: dict[str, Any], variant_name: str) -> list[dict[str, str]]:
    source_options = [item for item in source_row.get("opaque_options") or [] if isinstance(item, dict)]
    if variant_name.startswith("ledger_full"):
        return [{"label": str(item.get("label") or ""), "value": str(item.get("value") or "")} for item in source_options]
    keep = {
        "candidate_change_surface",
        "verifier_and_test_constraint",
        "nearby_definition_or_usage_context",
        "symptom_or_call_path_analogue",
    }
    filtered = []
    for item in source_options:
        value = str(item.get("value") or "")
        if value in keep:
            filtered.append({"label": str(item.get("label") or ""), "value": value})
    return filtered


def reorder_options(options: list[dict[str, str]], key_seed: str) -> list[dict[str, str]]:
    values = {item["value"]: item for item in options}
    ordered_values = sorted(values, key=lambda value: hashlib.sha256(f"{key_seed}:{value}".encode("utf-8")).hexdigest())
    return [values[value] for value in ordered_values]


def relabel_options(options: list[dict[str, str]]) -> list[dict[str, str]]:
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if len(options) > len(labels):
        raise ValueError("too many options to relabel")
    return [{"label": labels[idx], "value": item["value"]} for idx, item in enumerate(options)]


def build_task_line() -> str:
    return (
        "Task: Choose the visible evidence key that most specifically justifies the edit-target decision. "
        "Use the strongest packet-visible justification rather than relying on candidate order or defaulting to the changed surface."
    )


def build_prompt(
    spec: dict[str, Any],
    source_row: dict[str, Any],
    variant_name: str,
    options: list[dict[str, str]],
    gold_by_perspective: dict[str, dict[str, Any]],
) -> str:
    prompt = str(source_row.get("prompt_text") or source_row.get("input_text") or "")
    header_lines, _evidence_lines = split_prompt_sections(prompt)
    rewritten_header = []
    for line in header_lines:
        if line.startswith("Task: "):
            rewritten_header.append(build_task_line())
        else:
            rewritten_header.append(line)
    evidence_lines = build_evidence_lines(spec, source_row, variant_name, gold_by_perspective)
    option_lines = [f"{item['label']}. {item['value']}" for item in options]
    return "\n".join([*rewritten_header, "Evidence:", *evidence_lines, "Options:", *option_lines, "Answer:", ""])


def build_variant_rows(spec: dict[str, Any], source_row: dict[str, Any], gold_by_perspective: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    variants = [
        "ledger_full_verifier_first",
        "ledger_full_candidate_first",
        "ledger_contrast_verifier_first",
        "ledger_contrast_candidate_first",
    ]
    gold_value = str((gold_by_perspective.get("evidence_citation") or {}).get("gold_answer_value") or "")
    rows = []
    for variant_name in variants:
        option_pool = build_option_pool(source_row, variant_name)
        ordered = reorder_options(option_pool, f"{spec['queue_id']}::{variant_name}")
        relabeled = relabel_options(ordered)
        target_label = next((item["label"] for item in relabeled if item["value"] == gold_value), None)
        if target_label is None:
            raise ValueError(f"missing gold value {gold_value} for queue={spec['queue_id']} variant={variant_name}")
        prompt = build_prompt(spec, source_row, variant_name, relabeled, gold_by_perspective)
        rows.append(
            sanitize_train_row(
                {
                    "anti_cheat": {
                        "explicit_selected_test_ledger": True,
                        "gold_conditioned_task_line": False,
                        "opaque_labels": True,
                        "prompt_target_visible_by_design": True,
                        "reviewed_packet_reconstruction": True,
                        "same_surface_eval_admissible": False,
                        "target_path_strings_hidden_pre_options": True,
                        "train_support_only": True,
                    },
                    "decoder_text": target_label,
                    "input_text": prompt,
                    "language_family": spec.get("language_family"),
                    "objective_family": "bounded_decoder_ce",
                    "opaque_options": relabeled,
                    "prompt_text": prompt,
                    "query_text": f"explicit_verifier_ledger::{spec.get('language_family')}::{spec['queue_id']}::{variant_name}",
                    "repo_family": spec.get("repo_id"),
                    "repo_id": spec.get("repo_id"),
                    "row_id": f"stage10934::{spec['queue_id']}::evidence_citation::{variant_name}",
                    "selected_test_anchor": bool(spec.get("selected_tests")),
                    "source_bundle_id": spec.get("source_bundle_id"),
                    "source_heldout_admissible": False,
                    "source_root_id": spec.get("source_bundle_id"),
                    "split_role": "train_support_only",
                    "standalone_projection_source": {
                        "current_checked_row_id": spec.get("current_checked_row_id"),
                        "current_checked_target_value": spec.get("current_checked_target_value"),
                        "gold_value": gold_value,
                        "projection_mode": "stage10934_explicit_verifier_ledger_support",
                        "queue_id": spec.get("queue_id"),
                        "variant": variant_name,
                    },
                    "strict_eval_eligible": False,
                    "surface": "maintainer_bundle_compact_bounded_choice",
                    "target_text": target_label,
                    "target_token_len": 1,
                    "task_type": "evidence_citation",
                    "train_support_only": True,
                    "verifier_anchor": bool(spec.get("selected_tests")),
                }
            )
        )
    return rows


def main() -> None:
    base_summary = load_json(BASE_SUMMARY_JSON)
    base_train = [sanitize_train_row(row) for row in load_jsonl(BASE_TRAIN_JSONL)]
    validation_rows = load_jsonl(BASE_VALIDATION_JSONL)
    strict_rows = load_jsonl(BASE_STRICT_JSONL)
    stress_rows = load_jsonl(BASE_STRESS_JSONL)
    specs = load_jsonl(MANIFEST_ROWS)

    corpus: list[dict[str, Any]] = []
    for path in SOURCE_ROW_FILES:
        corpus.extend(load_jsonl(path))

    added_rows: list[dict[str, Any]] = []
    added_queue_ids: list[str] = []
    for spec in specs:
        source_row = find_source_row(spec, corpus)
        gold_by_perspective = load_gold_by_perspective(spec)
        variant_rows = build_variant_rows(spec, source_row, gold_by_perspective)
        added_rows.extend(variant_rows)
        added_queue_ids.append(str(spec.get("queue_id") or "unknown"))

    merged_train = list(base_train) + list(added_rows)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(added_rows) and bool(strict_rows),
        "decision": "explicit_verifier_ledger_support_package_ready",
        "claim_scope": [
            "Add support-only evidence-citation rows rebuilt from reviewed adjudication packets with explicit selected-test ledger materialization.",
            "Keep the cleaned 23-row validation and 23-row strict overlays unchanged so any movement can be judged against the same honest heldout surface.",
        ],
        "required_honesty_gates": [
            "All added rows remain train_support_only and strict_eval_eligible=false.",
            "Validation and strict rows are copied unchanged from stage10883.",
            "The explicit verifier/test ledger is derived only from reviewed packet adjudication plus selected tests already present in the packet.",
            "This package is support-only and not promotable as a fresh eval surface.",
        ],
        "source_artifacts": {
            "base_summary": rel(BASE_SUMMARY_JSON),
            "base_train": rel(BASE_TRAIN_JSONL),
            "base_validation": rel(BASE_VALIDATION_JSONL),
            "base_strict": rel(BASE_STRICT_JSONL),
            "base_stress": rel(BASE_STRESS_JSONL),
            "manifest_rows": rel(MANIFEST_ROWS),
            "source_row_files": [rel(path) for path in SOURCE_ROW_FILES],
        },
        "metrics": {
            "train_rows_before": len(base_train),
            "explicit_rows_added": len(added_rows),
            "train_rows_after": len(merged_train),
            "validation_rows_unchanged": len(validation_rows),
            "strict_rows_unchanged": len(strict_rows),
            "stress_rows_unchanged": len(stress_rows),
            "queue_ids": added_queue_ids,
            "added_by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in added_rows).items())),
            "added_by_target_label": dict(sorted(Counter(str(row.get("target_text") or "unknown") for row in added_rows).items())),
            "added_by_variant": dict(sorted(Counter(str(row.get("row_id") or "").rsplit("::", 1)[-1] for row in added_rows).items())),
            "train_by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in merged_train).items())),
            "base_metrics_snapshot": base_summary.get("metrics"),
        },
        "interpretation": [
            "This package directly fixes the audited Python defect where verifier_and_test_constraint was present in the options but absent from the visible evidence body.",
            "It also strengthens the C/C++ B-vs-F lane by materializing the selected tests and maintainer rationale as the visible verifier ledger rather than leaving candidate_change_surface as the only concrete anchor.",
            "The agentkernel counter-family is preserved so the model is not trained to always prefer verifier-and-test-constraint over candidate_change_surface.",
        ],
        "next_best_step": "Run a multilingual support probe from the clean stage10928 runtime with these explicit ledger rows, then re-evaluate the unchanged 23-row overlay and the 3-row fresh evidence successor slice.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "added_rows_jsonl": rel(ROWS_JSONL),
            "train_rows_jsonl": rel(TRAIN_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_JSONL),
            "strict_rows_jsonl": rel(STRICT_JSONL),
            "stress_rows_jsonl": rel(STRESS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_jsonl(ROWS_JSONL, added_rows)
    write_jsonl(TRAIN_JSONL, merged_train)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(STRESS_JSONL, stress_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
