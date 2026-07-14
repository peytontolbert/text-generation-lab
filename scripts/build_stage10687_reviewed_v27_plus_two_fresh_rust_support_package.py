#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10687
NAME = "stage10687_reviewed_v27_plus_two_fresh_rust_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "reviewed_v27_plus_two_fresh_rust_support_package.json"
ROOT_MANIFEST_JSONL = OUT_DIR / "reviewed_v27_plus_two_fresh_rust_root_manifest.jsonl"
ROWS_JSONL = OUT_DIR / "reviewed_v27_plus_two_fresh_rust_bounded_rows.jsonl"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

BASE_PACKAGE = ROOT / "runs/local/artifacts/stage10681_reviewed_v27_plus_linux_rust_train_support_package/reviewed_v27_plus_linux_rust_train_support_package.json"
BASE_ROOTS = ROOT / "runs/local/artifacts/stage10681_reviewed_v27_plus_linux_rust_train_support_package/reviewed_v27_plus_linux_rust_root_manifest.jsonl"
BASE_ROWS = ROOT / "runs/local/artifacts/stage10681_reviewed_v27_plus_linux_rust_train_support_package/reviewed_v27_plus_linux_rust_bounded_rows.jsonl"
BASE_TRAIN = ROOT / "runs/local/artifacts/stage10681_reviewed_v27_plus_linux_rust_train_support_package/agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = ROOT / "runs/local/artifacts/stage10681_reviewed_v27_plus_linux_rust_train_support_package/agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = ROOT / "runs/local/artifacts/stage10681_reviewed_v27_plus_linux_rust_train_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = ROOT / "runs/local/artifacts/stage10681_reviewed_v27_plus_linux_rust_train_support_package/agentkernel_lite_encdec_stress_eval.jsonl"

CANDLE_PACKET = ROOT / "runs/local/artifacts/stage10686_candle_datasets_ai_adjudication/review_packets/candle__candle-datasets/fresh_rust_bundle_preview.json"
CANDLE_GOLD = ROOT / "runs/local/artifacts/stage10686_candle_datasets_ai_adjudication/review_packets/candle__candle-datasets/perspective_gold_adjudication.json"
CANDLE_ANTI_CHEAT = ROOT / "runs/local/artifacts/stage10686_candle_datasets_ai_adjudication/review_packets/candle__candle-datasets/anti_cheat_review_card.json"
CANDLE_ADJUDICATION = ROOT / "runs/local/artifacts/stage10686_candle_datasets_ai_adjudication/candle_datasets_ai_adjudication.json"

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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def candle_root_record(bundle: dict[str, Any], anti_cheat: dict[str, Any]) -> dict[str, Any]:
    visible_keys = sorted(
        key
        for key, values in (bundle.get("maintainer_visible_evidence") or {}).items()
        if isinstance(values, list) and values
    )
    return {
        "record_type": "reviewed_bundle_root",
        "bundle_id": str(bundle["bundle_id"]),
        "root_id": str(bundle["bundle_id"]),
        "repo_id": "candle",
        "repo_family": "candle",
        "language_family": "rust",
        "task_types": [str(row.get("perspective") or "") for row in bundle.get("perspective_rows") or [] if isinstance(row, dict)],
        "task_type_count": len(bundle.get("perspective_rows") or []),
        "candidate_paths_count": len(bundle.get("candidate_paths") or []),
        "selected_tests_count": 0,
        "selected_test_anchor": False,
        "verifier_anchor": True,
        "visible_evidence_keys": visible_keys,
        "visible_evidence_key_count": len(visible_keys),
        "abstention_count": 2,
        "non_abstention_count": 6,
        "abstention_heavy": False,
        "source_heldout_admissible": False,
        "train_support_only": True,
        "strict_eval_eligible": False,
        "stress_overlap_only": False,
        "split_role": "train_support",
        "split": "train",
        "same_surface_eval_admissible": False,
        "reviewed_bundle_source": True,
        "successor_row_source": False,
        "claim_notes": [
            "fresh_candle_datasets_train_support_only",
            "source_derived_verifier_constraint",
            "not_admissible_for_same_surface_comparison",
            "ai_adjudicated",
        ],
        "packet_dir": display(CANDLE_PACKET.parent),
        "perspective_gold_adjudication": display(CANDLE_GOLD),
        "rubric_review": "",
        "anti_cheat_review": display(CANDLE_ANTI_CHEAT),
        "reviewer_id": str(anti_cheat.get("reviewer_id") or ""),
    }


def compile_candle_row(bundle: dict[str, Any], root_meta: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any] | None:
    perspective = str(gold.get("perspective") or "")
    answer_kind = str(gold.get("gold_answer_kind") or "")
    gold_value = str(gold.get("gold_answer_value") or "")
    if answer_kind not in BOUND_KINDS:
        return None
    contract = contract_for(bundle, perspective)
    values = build_option_values(answer_kind=answer_kind, gold_value=gold_value, contract=contract, gold=gold)
    options = list(zip(CHOICE_LABELS[: len(values)], values))
    label_by_value = {value: label for label, value in options}
    prompt = compile_bundle_prompt(bundle, gold, options)
    return {
        "row_id": f"{bundle['bundle_id']}::{perspective}::reviewed_v27_compact",
        "source_bundle_id": bundle["bundle_id"],
        "source_root_id": bundle["bundle_id"],
        "repo_id": root_meta["repo_id"],
        "repo_family": root_meta["repo_family"],
        "language_family": root_meta["language_family"],
        "task_type": perspective,
        "split": "train",
        "split_role": "train_support",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "selected_test_anchor": False,
        "verifier_anchor": True,
        "abstention_heavy": False,
        "surface": "maintainer_bundle_compact_bounded_choice",
        "objective_family": "bounded_decoder_ce",
        "prompt_text": prompt,
        "input_text": prompt,
        "query_text": f"reviewed_v27::{root_meta['language_family']}::{perspective}",
        "target_text": label_by_value[gold_value],
        "decoder_text": label_by_value[gold_value],
        "target_token_len": len(label_by_value[gold_value].encode("utf-8")),
        "expected_enabled_loss": "decoder_ce",
        "loss_mask": {"decoder_ce": True},
        "disable_losses": [],
        "opaque_options": [{"label": label, "value": value} for label, value in options],
        "standalone_projection_source": {
            "projection_mode": "reviewed_v27_compact_bounded_choice",
            "gold_value": gold_value,
            "original_answer_kind": answer_kind,
            "opaque_options": [{"label": label, "value": value} for label, value in options],
            "perspective_gold_adjudication": root_meta["perspective_gold_adjudication"],
        },
        "anti_cheat": {
            "reviewed_bundle_source": True,
            "opaque_labels": True,
            "compact_prompt_contract": True,
            "deterministic_option_shuffle": False,
            "same_surface_eval_admissible": False,
            "repo_overlap_stress_only": False,
            "source_derived_verifier_constraint": True,
        },
    }


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def main() -> None:
    base_package = load_json(BASE_PACKAGE)
    base_roots = load_jsonl(BASE_ROOTS)
    base_rows = load_jsonl(BASE_ROWS)
    base_train = load_jsonl(BASE_TRAIN)
    base_validation = load_jsonl(BASE_VALIDATION)
    base_strict = load_jsonl(BASE_STRICT)
    base_stress = load_jsonl(BASE_STRESS)

    bundle = load_json(CANDLE_PACKET)
    anti_cheat = load_json(CANDLE_ANTI_CHEAT)
    gold = load_json(CANDLE_GOLD)

    root_meta = candle_root_record(bundle, anti_cheat)
    new_rows: list[dict[str, Any]] = []
    for answer in gold.get("perspective_gold_answers") or []:
        if not isinstance(answer, dict):
            continue
        compiled = compile_candle_row(bundle, root_meta, answer)
        if compiled is not None:
            new_rows.append(compiled)

    train_rows = base_train + new_rows
    validation_rows = list(base_validation)
    strict_rows = list(base_strict)
    stress_rows = list(base_stress)
    bounded_rows = base_rows + new_rows
    root_records = base_roots + [root_meta]

    write_jsonl(ROOT_MANIFEST_JSONL, root_records)
    write_jsonl(ROWS_JSONL, bounded_rows)
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(STRESS_JSONL, stress_rows)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "reviewed_v27_extended_with_two_fresh_rust_support_roots",
        "claim_boundary": [
            "The strict and stress evaluation sets remain unchanged from the prior reviewed v2.7 successor package.",
            "The newly added candle-datasets Rust packet is train-support-only and uses a source-derived verifier constraint rather than a separate test file.",
            "This increases fresh Rust support breadth but does not change the current headline comparison claim by itself.",
        ],
        "source_artifacts": {
            "base_package": display(BASE_PACKAGE),
            "candle_datasets_adjudication": display(CANDLE_ADJUDICATION),
            "candle_datasets_packet": display(CANDLE_PACKET),
            "candle_datasets_gold": display(CANDLE_GOLD),
            "candle_datasets_anti_cheat": display(CANDLE_ANTI_CHEAT),
        },
        "delta_from_stage10681": {
            "added_root_id": root_meta["root_id"],
            "added_train_rows": len(new_rows),
            "train_rows_before": len(base_train),
            "train_rows_after": len(train_rows),
            "strict_rows_unchanged": len(strict_rows) == int(((base_package.get("metrics") or {}).get("strict_eval_rows")) or len(base_strict)),
        },
        "metrics": {
            "root_records": len(root_records),
            "bounded_rows": len(bounded_rows),
            "train_rows": len(train_rows),
            "validation_rows": len(validation_rows),
            "strict_eval_rows": len(strict_rows),
            "stress_rows": len(stress_rows),
            "root_language_counts": count_by(root_records, "language_family"),
            "root_repo_counts": count_by(root_records, "repo_id"),
            "row_language_counts": count_by(bounded_rows, "language_family"),
            "row_repo_counts": count_by(bounded_rows, "repo_id"),
            "row_split_counts": count_by(bounded_rows, "split"),
            "row_task_counts": count_by(bounded_rows, "task_type"),
            "selected_test_anchor_counts": {
                "present": sum(1 for row in bounded_rows if bool(row.get("selected_test_anchor"))),
                "absent": sum(1 for row in bounded_rows if not bool(row.get("selected_test_anchor"))),
            },
            "verifier_anchor_counts": {
                "present": sum(1 for row in bounded_rows if bool(row.get("verifier_anchor"))),
                "absent": sum(1 for row in bounded_rows if not bool(row.get("verifier_anchor"))),
            },
        },
        "support_addition_summary": {
            "bundle_id": root_meta["bundle_id"],
            "target_root_style": "source_derived_verifier_constraint",
            "compiled_bounded_perspectives": [row["task_type"] for row in new_rows],
            "train_support_only": True,
            "same_surface_eval_admissible": False,
        },
        "outputs": {
            "root_manifest": display(ROOT_MANIFEST_JSONL),
            "bounded_rows": display(ROWS_JSONL),
            "train_rows": display(TRAIN_JSONL),
            "validation_rows": display(VALIDATION_JSONL),
            "strict_rows": display(STRICT_JSONL),
            "stress_rows": display(STRESS_JSONL),
        },
        "next_best_step": "Run the next support-only probe from the preserved 22/24 runtime using both fresh Rust support roots and keep the 24-row strict set unchanged.",
    }
    write_json(PACKAGE_JSON, payload)
    print(PACKAGE_JSON)


if __name__ == "__main__":
    main()
