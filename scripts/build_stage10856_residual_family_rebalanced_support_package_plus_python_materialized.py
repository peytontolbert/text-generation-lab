#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10856
NAME = "stage10856_residual_family_rebalanced_support_package_plus_python_materialized"
OUT_DIR = ARTIFACTS / NAME
PACKAGE_JSON = OUT_DIR / "residual_family_rebalanced_support_package_plus_python_materialized.json"
ROOTS_JSONL = OUT_DIR / "python_materialized_root_manifest.jsonl"
ROWS_JSONL = OUT_DIR / "python_materialized_bounded_rows.jsonl"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

BASE_DIR = ARTIFACTS / "stage10844_residual_family_rebalanced_support_package"
BASE_PACKAGE = BASE_DIR / "residual_family_rebalanced_support_package.json"
BASE_TRAIN = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

PY_ADMISSION_DIR = ARTIFACTS / "stage10855_python_verifier_geometry_materialization_audit"
PY_ADMISSION_JSON = PY_ADMISSION_DIR / "python_verifier_geometry_materialization_audit.json"
PY_ADMITTED_ROOTS = PY_ADMISSION_DIR / "admitted_python_verifier_roots.jsonl"

BOUND_KINDS = {"candidate_path", "selected_test", "visible_evidence_key", "abstain"}
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


def build_option_values(*, answer_kind: str, gold_value: str, contract: dict[str, Any], gold: dict[str, Any]) -> list[str]:
    if answer_kind == "candidate_path":
        values = [str(v) for v in (gold.get("candidate_paths") or contract.get("candidate_paths") or []) if v]
    elif answer_kind == "selected_test":
        values = [str(v) for v in (gold.get("selected_tests") or contract.get("selected_tests") or []) if v]
    elif answer_kind == "visible_evidence_key":
        values = [str(v) for v in (gold.get("visible_evidence_keys") or contract.get("visible_evidence_keys") or []) if v]
    elif answer_kind == "abstain":
        values = [str(v) for v in (gold.get("candidate_paths") or contract.get("candidate_paths") or []) if v]
        if not values:
            values = [str(v) for v in (gold.get("selected_tests") or contract.get("selected_tests") or []) if v]
        if not values:
            values = [str(v) for v in (gold.get("visible_evidence_keys") or contract.get("visible_evidence_keys") or []) if v]
        values.append("ABSTAIN_INSUFFICIENT_EVIDENCE")
    else:
        values = [gold_value]
    deduped: list[str] = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    if gold_value not in seen:
        deduped.append(gold_value)
    return deduped


def compile_bundle_prompt(bundle: dict[str, Any], gold: dict[str, Any], options: list[tuple[str, str]]) -> str:
    perspective = str(gold.get("perspective") or "")
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


def compile_python_row(bundle: dict[str, Any], root_meta: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any] | None:
    perspective = str(gold.get("perspective") or "")
    answer_kind = str(gold.get("gold_answer_kind") or "")
    gold_value = str(gold.get("gold_answer_value") or "")
    if answer_kind not in BOUND_KINDS:
        return None
    contract = contract_for(bundle, perspective)
    values = build_option_values(answer_kind=answer_kind, gold_value=gold_value, contract=contract, gold=gold)
    if len(values) > len(CHOICE_LABELS):
        raise ValueError(f"too_many_options::{bundle['bundle_id']}::{perspective}")
    options = list(zip(CHOICE_LABELS[: len(values)], values))
    label_by_value = {value: label for label, value in options}
    prompt = compile_bundle_prompt(bundle, gold, options)
    return {
        "row_id": f"{bundle['bundle_id']}::{perspective}::materialized_residual_support",
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
        "abstention_heavy": perspective == "abstention_insufficient_evidence",
        "surface": "maintainer_bundle_compact_bounded_choice",
        "objective_family": "bounded_decoder_ce",
        "prompt_text": prompt,
        "input_text": prompt,
        "query_text": f"materialized_residual_support::{root_meta['language_family']}::{perspective}",
        "target_text": label_by_value[gold_value],
        "decoder_text": label_by_value[gold_value],
        "target_token_len": len(label_by_value[gold_value].encode("utf-8")),
        "expected_enabled_loss": "decoder_ce",
        "loss_mask": {"decoder_ce": True},
        "disable_losses": [],
        "opaque_options": [{"label": label, "value": value} for label, value in options],
        "standalone_projection_source": {
            "projection_mode": "materialized_residual_support_bounded_choice",
            "gold_value": gold_value,
            "original_answer_kind": answer_kind,
            "opaque_options": [{"label": label, "value": value} for label, value in options],
            "perspective_gold_adjudication": str((Path(root_meta["packet_dir"]) / "perspective_gold_adjudication.json")),
            "support_family": "python_materialized_verifier_residual",
        },
        "anti_cheat": {
            "reviewed_bundle_source": True,
            "opaque_labels": True,
            "compact_prompt_contract": True,
            "same_surface_eval_admissible": False,
            "repo_overlap_stress_only": False,
            "execution_backed_python_bundle": True,
            "materialized_geometry_residual_support": True,
        },
        "support_provenance": {
            "rebalance_stage": STAGE,
            "rebalance_source_key": "python_materialized_admitted_root",
            "rebalance_source_path": root_meta["packet_dir"],
        },
        "residual_family_rebalance_source": "python_materialized_admitted_root",
    }


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
    admission = load_json(PY_ADMISSION_JSON)
    if not admission.get("passed"):
        raise SystemExit("stage10855_not_passed")
    root_manifest = load_jsonl(PY_ADMITTED_ROOTS)

    existing_row_ids = {str(row["row_id"]) for row in base_train}
    new_rows: list[dict[str, Any]] = []
    for root_meta in root_manifest:
        packet_dir = ROOT / str(root_meta["packet_dir"])
        bundle = load_json(packet_dir / "fresh_python_bundle_preview.json")
        gold = load_json(packet_dir / "perspective_gold_adjudication.json")
        for answer in gold.get("perspective_gold_answers") or []:
            if not isinstance(answer, dict):
                continue
            row = compile_python_row(bundle, root_meta, answer)
            if row is None:
                continue
            if row["row_id"] in existing_row_ids:
                continue
            existing_row_ids.add(row["row_id"])
            new_rows.append(row)

    train_rows = base_train + new_rows

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "residual_family_rebalanced_support_package_extended_with_materialized_python_root",
        "claim_scope": [
            "Extend the residual-family support package with the newly materialized Python verifier root.",
            "Keep strict, validation, and stress overlays unchanged while improving Python verifier train geometry with real packet-derived bounded rows.",
        ],
        "source_artifacts": {
            "base_package": rel(BASE_PACKAGE),
            "python_materialization_audit": rel(PY_ADMISSION_JSON),
            "python_materialized_root_manifest": rel(PY_ADMITTED_ROOTS),
        },
        "delta_from_stage10844": {
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
            "The Python verifier lane now includes real bundle-derived rows from the previously blocked agentkernel geometry root.",
            "This does not fix the heldout frontier by itself, but it removes a clear support-inventory weakness: Python residual training no longer depends only on the queue-aligned code_assist packet plus legacy support.",
            "The package remains train-support only and should still be followed by a second independent Python verifier-transition root to reduce same-family shortcut risk.",
        ],
        "honesty_gates": [
            "validation, strict, and stress rows remain unchanged from stage10844",
            "all added rows remain train_support_only and strict_eval_eligible=false",
            "the newly added Python root remains non-headline and same-surface inadmissible",
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
        "next_best_step": "Use this successor package for the next residual-family diagnostic probe, or continue by materializing a second independent Python verifier root before spending another training run.",
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
