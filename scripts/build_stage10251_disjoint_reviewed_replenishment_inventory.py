#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10251
NAME = "stage10251_disjoint_reviewed_replenishment_inventory"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT_JSON = OUT_DIR / "disjoint_reviewed_replenishment_inventory.json"
TRAIN_JSONL = OUT_DIR / "auxiliary_abstention_train_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_PREVIEW_JSONL = ROOT / "runs/local/artifacts/stage10119_true_source_backed_maintainer_root_bundle_preview/true_source_backed_maintainer_root_bundle_preview.jsonl"
WEB_REPLENISH_BUNDLE = ROOT / "runs/local/artifacts/stage10176_code_assist_web_replenishment_bundle/code_assist_web_replenishment_bundle.json"
CURRENT_FRONTIER_SUMMARY = ROOT / "runs/local/artifacts/stage10242_admitted_projection_runtime_successor_multilingual_cuda/first_wave_bundle_inference_summary.json"

REVIEW_PACKET_ROOTS = [
    ROOT / "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets/review_packets",
    ROOT / "runs/local/artifacts/stage10176_code_assist_web_replenishment_bundle/review_packets",
]

BOUND_KINDS = {"candidate_path", "selected_test", "visible_evidence_key", "abstain"}
CHOICE_LABELS = list("ABCDEFGHJKLMNOPQRSTUVWXYZ")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
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


def snippet(text: str, limit: int = 280) -> str:
    clean = " ".join(str(text).split())
    return clean if len(clean) <= limit else clean[: max(0, limit - 3)] + "..."


def deterministic_order(values: list[str], seed: str) -> list[str]:
    return sorted(values, key=lambda value: hashlib.sha256(f"{seed}::{value}".encode("utf-8")).hexdigest())


def review_dir_name(bundle_id: str) -> str:
    return bundle_id.replace("::", "__")


def contract_for(bundle: dict[str, Any], perspective: str) -> dict[str, Any]:
    for row in bundle.get("perspective_rows") or []:
        if isinstance(row, dict) and str(row.get("perspective") or "") == perspective:
            contract = row.get("prompt_contract")
            if isinstance(contract, dict):
                return contract
    return {}


def evidence_lines(bundle: dict[str, Any], visible_keys: list[str]) -> list[str]:
    evidence = bundle.get("maintainer_visible_evidence") if isinstance(bundle.get("maintainer_visible_evidence"), dict) else {}
    lines: list[str] = []
    for key in visible_keys:
        values = evidence.get(key)
        if not isinstance(values, list) or not values:
            continue
        first = values[0]
        if not isinstance(first, dict):
            continue
        prefix = key
        path = str(first.get("path") or "")
        source_type = str(first.get("source_type") or "")
        if path:
            prefix += f" [{path}]"
        elif source_type:
            prefix += f" [{source_type}]"
        lines.append(f"{prefix}: {snippet(str(first.get('text') or ''))}")
    return lines[:4]


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


def compile_prompt(bundle: dict[str, Any], gold: dict[str, Any], options: list[tuple[str, str]]) -> str:
    perspective = str(gold.get("perspective") or "")
    contract = contract_for(bundle, perspective)
    task = " ".join(str(contract.get("task") or "").split())
    visible_keys = [str(v) for v in contract.get("visible_evidence_keys") or [] if v]
    ev_lines = evidence_lines(bundle, visible_keys)
    parts = [
        f"Language: {bundle.get('language_family')}",
        f"Perspective: {perspective}",
        f"Task: {task}",
    ]
    if ev_lines:
        parts.append("Evidence:")
        parts.extend(ev_lines)
    parts.append("Options:")
    parts.extend([f"{label}. {value}" for label, value in options])
    parts.append("Answer:")
    return "\n".join(parts) + "\n"


def compile_train_row(bundle: dict[str, Any], gold: dict[str, Any], gold_path: Path, review_meta: dict[str, Any]) -> dict[str, Any] | None:
    perspective = str(gold.get("perspective") or "")
    answer_kind = str(gold.get("gold_answer_kind") or "")
    gold_value = str(gold.get("gold_answer_value") or "")
    if answer_kind not in BOUND_KINDS:
        return None
    contract = contract_for(bundle, perspective)
    values = build_option_values(answer_kind=answer_kind, gold_value=gold_value, contract=contract, gold=gold)
    seed = f"replenish::{bundle['bundle_id']}::{perspective}::{answer_kind}"
    ordered_values = deterministic_order(values, seed)
    if len(ordered_values) > len(CHOICE_LABELS):
        raise ValueError(f"too_many_options::{bundle['bundle_id']}::{perspective}")
    options = list(zip(CHOICE_LABELS[: len(ordered_values)], ordered_values))
    label_by_value = {value: label for label, value in options}
    prompt = compile_prompt(bundle, gold, options)
    return {
        "row_id": f"{bundle['bundle_id']}::{perspective}::compact_bounded::replenishment_abstain",
        "semantic_key": f"replenishment_abstain::{bundle['bundle_id']}::{perspective}",
        "bundle_id": bundle["bundle_id"],
        "source_bundle_id": bundle["bundle_id"],
        "source_row_id": f"{bundle['bundle_id']}::{perspective}::compact_bounded",
        "source_stage": STAGE,
        "source_skill_area": "maintainer_bundle_compact_bounded_choice",
        "language_family": bundle["language_family"],
        "task_type": perspective,
        "surface": "maintainer_bundle_compact_bounded_choice",
        "route": "KEEP_BOUNDED_DECODER",
        "objective_family": "bounded_decoder_ce",
        "query_text": f"compact_bounded::{bundle['language_family']}::{perspective}::{answer_kind}::replenishment",
        "prompt_text": prompt,
        "input_text": prompt,
        "target_text": label_by_value[gold_value],
        "decoder_text": label_by_value[gold_value],
        "target_token_len": len(label_by_value[gold_value].encode("utf-8")),
        "split": "train",
        "loss_mask": {"decoder_ce": True},
        "disable_losses": [],
        "expected_enabled_loss": "decoder_ce",
        "standalone_projection_source": {
            "gold_answers_path": display(gold_path),
            "gold_value": gold_value,
            "opaque_options": [{"label": label, "value": value} for label, value in options],
            "original_answer_kind": answer_kind,
            "projection_mode": "compact_bounded_choice_auxiliary",
            "projection_stage": STAGE,
            "review_basis": review_meta,
        },
        "authority": {
            "body_emission_authorized": False,
            "controller_complete_merge_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "gemma_execution_authorized_next": False,
            "harness_execution_authorized_next": False,
            "model_execution_authorized_next": False,
            "promotion_ready": False,
            "runtime_authorized": False,
            "scoring_authorized_next": False,
            "source_emission_authorized": False,
        },
        "anti_cheat": {
            "compact_prompt_contract": True,
            "deterministic_option_shuffle": True,
            "opaque_labels": True,
            "reviewed_bundle_source": True,
            "replenishment_train_only": True,
            "not_for_primary_maintainer_claim": True,
            "disjoint_from_stage10242_miss_roots": True,
            "abstention_only_from_underconstrained_bundle": True,
            "freeform_rows_excluded": True,
        },
    }


def load_bundle_lookup() -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(SOURCE_PREVIEW_JSONL):
        bundle_id = str(row.get("bundle_id") or "")
        if bundle_id:
            lookup[bundle_id] = row
    web_bundle = load_json(WEB_REPLENISH_BUNDLE)
    bundle_id = str(web_bundle.get("bundle_id") or "")
    if bundle_id:
        lookup[bundle_id] = web_bundle
    return lookup


def load_review_records() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for root in REVIEW_PACKET_ROOTS:
        if not root.exists():
            continue
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            gold_path = entry / "perspective_gold_adjudication.json"
            if not gold_path.exists():
                continue
            gold = load_json(gold_path)
            bundle_id = str(gold.get("bundle_id") or "")
            if not bundle_id:
                continue
            records[bundle_id] = {
                "review_dir": entry,
                "gold_path": gold_path,
                "gold": gold,
                "rubric": load_json(entry / "expert_maintainer_rubric_review.json"),
                "anti_cheat": load_json(entry / "anti_cheat_review_card.json"),
            }
    return records


def load_miss_roots() -> set[str]:
    summary = load_json(CURRENT_FRONTIER_SUMMARY)
    miss_roots: set[str] = set()
    for result in summary.get("results") or []:
        if not isinstance(result, dict):
            continue
        pred_path = (ROOT / str(result.get("adapter_payload") or "")).with_name("bundle_predictions.json")
        preds = load_json(pred_path)
        for row in preds.get("hundred_m") or []:
            if not isinstance(row, dict) or row.get("correct") is not False:
                continue
            row_id = str(row.get("row_id") or "")
            marker = "::compact_bounded"
            miss_roots.add(row_id.split(marker, 1)[0] if marker in row_id else row_id)
    return miss_roots


def overlaps_current_miss(bundle_id: str, miss_roots: set[str]) -> bool:
    prefix = f"{bundle_id}::"
    return any(miss == bundle_id or miss.startswith(prefix) for miss in miss_roots)


def review_meta(bundle_id: str, review: dict[str, Any]) -> dict[str, Any]:
    rubric = review.get("rubric") if isinstance(review.get("rubric"), dict) else {}
    anti = review.get("anti_cheat") if isinstance(review.get("anti_cheat"), dict) else {}
    return {
        "bundle_id": bundle_id,
        "review_dir": display(Path(review["review_dir"])),
        "rubric_status": rubric.get("status"),
        "rubric_passed": rubric.get("passed"),
        "anti_cheat_status": anti.get("status"),
        "anti_cheat_passed": anti.get("passed"),
        "anti_cheat_admissible_for_same_surface_comparison": anti.get("admissible_for_same_surface_comparison"),
        "anti_cheat_decision_rationale": anti.get("decision_rationale") or anti.get("reviewer_notes"),
    }


def eligibility_for(bundle: dict[str, Any], review: dict[str, Any], miss_roots: set[str]) -> dict[str, Any]:
    bundle_id = str(bundle.get("bundle_id") or "")
    lang = str(bundle.get("language_family") or "")
    gold = review.get("gold") if isinstance(review.get("gold"), dict) else {}
    answers = [row for row in gold.get("perspective_gold_answers") or [] if isinstance(row, dict)]
    rubric = review.get("rubric") if isinstance(review.get("rubric"), dict) else {}
    anti = review.get("anti_cheat") if isinstance(review.get("anti_cheat"), dict) else {}
    disjoint = not overlaps_current_miss(bundle_id, miss_roots)
    gold_completed = str(gold.get("status") or "") == "completed"
    has_abstain_rows = any(str(row.get("gold_answer_kind") or "") == "abstain" for row in answers)
    anti_completed = str(anti.get("status") or "") == "completed"
    anti_failed = anti.get("passed") is False
    abstention_train_eligible = (
        lang == "c_cpp"
        and disjoint
        and gold_completed
        and has_abstain_rows
        and anti_completed
        and anti_failed
    )
    scoring_ready = bool(rubric.get("passed")) and bool(anti.get("passed")) and disjoint and gold_completed
    reason = []
    if not disjoint:
        reason.append("overlaps_current_miss_root")
    if not gold_completed:
        reason.append("gold_not_completed")
    if lang == "web_js_ts_html" and not disjoint:
        reason.append("all_reviewed_web_roots_already_consumed_by_current_frontier")
    if lang == "web_js_ts_html" and disjoint and not scoring_ready:
        reason.append("no_disjoint_web_root_ready_for_compact_reuse")
    if lang == "c_cpp" and abstention_train_eligible:
        reason.append("abstention_only_train_support_from_underconstrained_bundle")
    return {
        "bundle_id": bundle_id,
        "language_family": lang,
        "disjoint_from_current_miss_roots": disjoint,
        "gold_completed": gold_completed,
        "rubric_passed": rubric.get("passed"),
        "anti_cheat_passed": anti.get("passed"),
        "abstention_train_eligible": abstention_train_eligible,
        "scoring_ready": scoring_ready,
        "reasons": reason,
    }


def build_inventory() -> dict[str, Any]:
    bundles = load_bundle_lookup()
    reviews = load_review_records()
    miss_roots = load_miss_roots()

    inventory_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []

    target_bundle_ids = sorted(
        bundle_id
        for bundle_id in reviews
        if bundle_id.endswith("::c_cpp") or bundle_id.endswith("::web_js_ts_html")
    )

    for bundle_id in target_bundle_ids:
        bundle = bundles.get(bundle_id)
        if not isinstance(bundle, dict):
            inventory_rows.append({
                "bundle_id": bundle_id,
                "language_family": bundle_id.split("::")[-1],
                "missing_bundle_payload": True,
            })
            continue
        review = reviews[bundle_id]
        eligibility = eligibility_for(bundle, review, miss_roots)
        row = dict(eligibility)
        row["review_meta"] = review_meta(bundle_id, review)
        inventory_rows.append(row)

        if not eligibility["abstention_train_eligible"]:
            continue

        gold = review["gold"]
        gold_path = Path(review["gold_path"])
        for answer in gold.get("perspective_gold_answers") or []:
            if not isinstance(answer, dict):
                continue
            if str(answer.get("gold_answer_kind") or "") != "abstain":
                continue
            compiled = compile_train_row(bundle, answer, gold_path, row["review_meta"])
            if compiled is not None:
                train_rows.append(compiled)

    language_counts: dict[str, int] = {}
    eligible_counts: dict[str, int] = {}
    for row in inventory_rows:
        lang = str(row.get("language_family") or "")
        language_counts[lang] = language_counts.get(lang, 0) + 1
        if row.get("abstention_train_eligible"):
            eligible_counts[lang] = eligible_counts.get(lang, 0) + 1

    train_language_counts: dict[str, int] = {}
    for row in train_rows:
        lang = str(row.get("language_family") or "")
        train_language_counts[lang] = train_language_counts.get(lang, 0) + 1

    write_jsonl(TRAIN_JSONL, train_rows)
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "current_frontier_summary": display(CURRENT_FRONTIER_SUMMARY),
        "source_preview_jsonl": display(SOURCE_PREVIEW_JSONL),
        "web_replenishment_bundle": display(WEB_REPLENISH_BUNDLE),
        "review_packet_roots": [display(path) for path in REVIEW_PACKET_ROOTS],
        "claim_scope": "disjoint reviewed replenishment inventory only; rows emitted here are auxiliary abstention-train support and not primary maintainer scoring rows",
        "metrics": {
            "reviewed_bundle_candidates": len(inventory_rows),
            "eligible_abstention_bundles": sum(1 for row in inventory_rows if row.get("abstention_train_eligible")),
            "eligible_scoring_ready_bundles": sum(1 for row in inventory_rows if row.get("scoring_ready")),
            "generated_auxiliary_train_rows": len(train_rows),
            "bundle_language_counts": dict(sorted(language_counts.items())),
            "eligible_abstention_bundle_counts": dict(sorted(eligible_counts.items())),
            "train_row_language_counts": dict(sorted(train_language_counts.items())),
            "current_miss_root_count": len(miss_roots),
        },
        "anti_cheat_conclusions": [
            "Do not reuse any reviewed web root that already appears in the current miss frontier; that would convert the live eval gap into train leakage.",
            "Unused C/C++ bundles with underconstrained evidence can still contribute abstention-only honesty rows, but they are not admissible same-surface scoring bundles.",
            "The current reviewed inventory contains no disjoint web root that is both gold-complete and safe to promote into compact-bounded training support.",
        ],
        "inventory_rows": inventory_rows,
        "generated_train_rows_path": display(TRAIN_JSONL),
        "recommended_next_step": "Use the emitted C/C++ abstention-only support rows if desired, but replenish fresh disjoint web maintainer roots from source-backed session evidence before attempting another multilingual weakness replay.",
    }
    write_json(OUT_JSON, payload)
    write_json(SUMMARY, {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "artifact": display(OUT_JSON),
        "generated_train_rows_path": display(TRAIN_JSONL),
        "metrics": payload["metrics"],
    })
    return payload


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    payload = build_inventory()
    print(json.dumps({
        "stage": STAGE,
        "passed": True,
        "artifact": display(OUT_JSON),
        "generated_train_rows_path": display(TRAIN_JSONL),
        "metrics": payload["metrics"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
