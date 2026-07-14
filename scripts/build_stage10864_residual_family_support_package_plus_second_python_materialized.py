#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10864
NAME = "stage10864_residual_family_support_package_plus_second_python_materialized"
OUT_DIR = ARTIFACTS / NAME
PACKAGE_JSON = OUT_DIR / "residual_family_support_package_plus_second_python_materialized.json"
ROOTS_JSONL = OUT_DIR / "python_materialized_root_manifest.jsonl"
ROWS_JSONL = OUT_DIR / "python_materialized_bounded_rows.jsonl"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

BASE_DIR = ARTIFACTS / "stage10856_residual_family_rebalanced_support_package_plus_python_materialized"
BASE_PACKAGE = BASE_DIR / "residual_family_rebalanced_support_package_plus_python_materialized.json"
BASE_TRAIN = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

SECOND_ROOT_JSON = (
    ARTIFACTS
    / "stage10863_agentkernel_second_python_verifier_materialization"
    / "agentkernel_second_python_verifier_materialization.json"
)

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


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def compact(text: str, limit: int = 280) -> str:
    clean = " ".join(str(text).split())
    return clean if len(clean) <= limit else clean[: limit - 3].rstrip() + "..."


def evidence_lines(bundle: dict[str, Any], visible_keys: list[str]) -> list[str]:
    evidence = bundle.get("maintainer_visible_evidence")
    if not isinstance(evidence, dict):
        return []
    lines: list[str] = []
    for key in visible_keys:
        values = evidence.get(key)
        if not isinstance(values, list) or not values:
            continue
        first = values[0]
        if not isinstance(first, dict):
            continue
        path = str(first.get("path") or "")
        text = compact(str(first.get("text") or ""))
        prefix = key if not path else f"{key} [{path}]"
        lines.append(f"{prefix}: {text}")
    return lines[:5]


def contract_for(bundle: dict[str, Any], perspective: str) -> dict[str, Any]:
    for row in bundle.get("perspective_rows") or []:
        if isinstance(row, dict) and str(row.get("perspective") or "") == perspective:
            contract = row.get("prompt_contract")
            if isinstance(contract, dict):
                return contract
    return {}


def answer_kind_for_perspective(perspective: str) -> str:
    if perspective == "verifier_outcome":
        return "selected_test"
    if perspective == "evidence_citation":
        return "visible_evidence_key"
    return "abstain"


def build_option_values(bundle: dict[str, Any], perspective: str) -> list[str]:
    contract = contract_for(bundle, perspective)
    kind = answer_kind_for_perspective(perspective)
    if kind == "selected_test":
        values = [str(v) for v in contract.get("selected_tests") or [] if v]
    elif kind == "visible_evidence_key":
        values = [str(v) for v in contract.get("visible_evidence_keys") or [] if v]
    else:
        values = [str(v) for v in contract.get("candidate_paths") or [] if v]
    values.append("ABSTAIN_INSUFFICIENT_EVIDENCE")
    deduped: list[str] = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def compile_bundle_prompt(bundle: dict[str, Any], perspective: str, options: list[tuple[str, str]]) -> str:
    contract = contract_for(bundle, perspective)
    task = " ".join(str(contract.get("task") or "").split())
    visible_keys = [str(v) for v in contract.get("visible_evidence_keys") or [] if v]
    parts = [
        f"Language: {bundle.get('language_family')}",
        f"Perspective: {perspective}",
        f"Task: {task}",
    ]
    ev_lines = evidence_lines(bundle, visible_keys)
    if ev_lines:
        parts.append("Evidence:")
        parts.extend(ev_lines)
    parts.append("Options:")
    parts.extend(f"{label}. {value}" for label, value in options)
    parts.append("Answer:")
    return "\n".join(parts) + "\n"


def compile_python_rows(bundle: dict[str, Any], root_meta: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for perspective_row in bundle.get("perspective_rows") or []:
        if not isinstance(perspective_row, dict):
            continue
        perspective = str(perspective_row.get("perspective") or "")
        if not perspective:
            continue
        values = build_option_values(bundle, perspective)
        if len(values) > len(CHOICE_LABELS):
            raise ValueError(f"too_many_options::{bundle['bundle_id']}::{perspective}")
        options = list(zip(CHOICE_LABELS[: len(values)], values))
        label_by_value = {value: label for label, value in options}
        gold_value = "ABSTAIN_INSUFFICIENT_EVIDENCE"
        prompt = compile_bundle_prompt(bundle, perspective, options)
        rows.append(
            {
                "row_id": f"{bundle['bundle_id']}::{perspective}::second_materialized_residual_support",
                "source_bundle_id": bundle["bundle_id"],
                "source_root_id": bundle["bundle_id"],
                "repo_id": root_meta["repo_id"],
                "repo_family": root_meta["repo_id"],
                "language_family": root_meta["language_family"],
                "task_type": perspective,
                "split": "train",
                "split_role": "train_support",
                "train_support_only": True,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "selected_test_anchor": True,
                "verifier_anchor": True,
                "abstention_heavy": True,
                "surface": "maintainer_bundle_compact_bounded_choice",
                "objective_family": "bounded_decoder_ce",
                "prompt_text": prompt,
                "input_text": prompt,
                "query_text": f"materialized_residual_support::{root_meta['language_family']}::{perspective}::second_root",
                "target_text": label_by_value[gold_value],
                "decoder_text": label_by_value[gold_value],
                "target_token_len": len(label_by_value[gold_value].encode("utf-8")),
                "expected_enabled_loss": "decoder_ce",
                "loss_mask": {"decoder_ce": True},
                "disable_losses": [],
                "opaque_options": [{"label": label, "value": value} for label, value in options],
                "standalone_projection_source": {
                    "projection_mode": "second_materialized_residual_support_bounded_choice",
                    "gold_value": gold_value,
                    "original_answer_kind": answer_kind_for_perspective(perspective),
                    "opaque_options": [{"label": label, "value": value} for label, value in options],
                    "support_family": "python_second_materialized_verifier_residual",
                },
                "anti_cheat": {
                    "reviewed_bundle_source": True,
                    "opaque_labels": True,
                    "compact_prompt_contract": True,
                    "same_surface_eval_admissible": False,
                    "repo_overlap_stress_only": False,
                    "execution_backed_python_bundle": True,
                    "materialized_geometry_residual_support": True,
                    "abstention_oriented_to_avoid_fake_singleton_label": True,
                },
                "support_provenance": {
                    "rebalance_stage": STAGE,
                    "rebalance_source_key": "python_second_materialized_root",
                    "rebalance_source_path": root_meta["packet_dir"],
                },
                "residual_family_rebalance_source": "python_second_materialized_root",
            }
        )
    return rows


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def count_targets(rows: list[dict[str, Any]], task_type: str) -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                str(row.get("target_text") or row.get("decoder_text") or "unknown")
                for row in rows
                if row.get("task_type") == task_type
            ).items()
        )
    )


def main() -> None:
    base_package = load_json(BASE_PACKAGE)
    base_train = load_jsonl(BASE_TRAIN)
    base_validation = load_jsonl(BASE_VALIDATION)
    base_strict = load_jsonl(BASE_STRICT)
    base_stress = load_jsonl(BASE_STRESS)
    root_meta = load_json(SECOND_ROOT_JSON)
    packet_dir = ROOT / str(root_meta["packet_dir"])
    bundle = load_json(packet_dir / "materialized_preview.json")

    existing_row_ids = {str(row["row_id"]) for row in base_train}
    new_rows = []
    for row in compile_python_rows(bundle, root_meta):
        if row["row_id"] in existing_row_ids:
            continue
        existing_row_ids.add(row["row_id"])
        new_rows.append(row)

    train_rows = base_train + new_rows
    root_manifest = [root_meta]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "residual_family_support_package_extended_with_second_materialized_python_root",
        "claim_scope": [
            "Extend the residual-family support package with the second materialized Python verifier-support root.",
            "Keep strict, validation, and stress overlays unchanged while increasing source-backed Python verifier support without forcing singleton labels.",
        ],
        "source_artifacts": {
            "base_package": rel(BASE_PACKAGE),
            "second_python_materialization": rel(SECOND_ROOT_JSON),
        },
        "delta_from_stage10856": {
            "added_root_count": len(root_manifest),
            "added_train_rows": len(new_rows),
            "train_rows_before": len(base_train),
            "train_rows_after": len(train_rows),
            "strict_rows_unchanged": len(base_strict),
            "validation_rows_unchanged": len(base_validation),
            "stress_rows_unchanged": len(base_stress),
        },
        "metrics": {
            "train_rows": len(train_rows),
            "validation_rows": len(base_validation),
            "strict_rows": len(base_strict),
            "stress_rows": len(base_stress),
            "new_row_task_counts": count_by(new_rows, "task_type"),
            "new_row_language_counts": count_by(new_rows, "language_family"),
            "train_by_language": count_by(train_rows, "language_family"),
            "train_by_task": count_by(train_rows, "task_type"),
            "verifier_outcome_target_distribution": count_targets(train_rows, "verifier_outcome"),
            "evidence_citation_target_distribution": count_targets(train_rows, "evidence_citation"),
        },
        "interpretation": [
            "The Python verifier lane now contains two source-backed materialized agentkernel roots instead of one.",
            "The newly added rows are abstention-oriented by design, which is honest for the current materialized geometry and avoids training fake singleton verifier labels.",
            "This still does not replace the need for a fresh strict-heldout verifier-transition root whose visible target is test/transition rather than implementation-vs-config.",
        ],
        "honesty_gates": [
            "validation, strict, and stress rows remain unchanged from stage10856",
            "all added rows remain train_support_only and strict_eval_eligible=false",
            "the second materialized Python root is abstention-oriented and non-headline",
        ],
        "outputs": {
            "package_json": rel(PACKAGE_JSON),
            "python_materialized_root_manifest": rel(ROOTS_JSONL),
            "python_materialized_rows": rel(ROWS_JSONL),
            "train_rows": rel(TRAIN_JSONL),
            "validation_rows": rel(VALIDATION_JSONL),
            "strict_rows": rel(STRICT_JSONL),
            "stress_rows": rel(STRESS_JSONL),
        },
        "next_best_step": "Prepare the next diagnostic probe request from this package, then either run it or continue by building a fresh strict-heldout Python verifier-transition root.",
    }

    write_jsonl(ROOTS_JSONL, root_manifest)
    write_jsonl(ROWS_JSONL, new_rows)
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, base_validation)
    write_jsonl(STRICT_JSONL, base_strict)
    write_jsonl(STRESS_JSONL, base_stress)
    write_json(PACKAGE_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "artifact": rel(PACKAGE_JSON),
            "added_train_rows": len(new_rows),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
