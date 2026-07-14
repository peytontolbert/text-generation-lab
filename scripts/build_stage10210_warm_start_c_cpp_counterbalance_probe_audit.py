#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10210
NAME = "stage10210_warm_start_c_cpp_counterbalance_probe_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "warm_start_c_cpp_counterbalance_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
BASELINE_10189 = ROOT / "runs/local/artifacts/stage10189_saved_choice_aux_encoder_option_retrieval_target100m_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
BASELINE_10202 = ROOT / "runs/local/artifacts/stage10202_targeted_contrast_target100m_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
BASELINE_10206 = ROOT / "runs/local/artifacts/stage10206_c_cpp_abstention_counterbalance_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
TARGET_10209 = ROOT / "runs/local/artifacts/stage10209_warm_start_c_cpp_counterbalance_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
REQUEST_10208 = ROOT / "runs/local/artifacts/stage10208_warm_start_c_cpp_counterbalance_execution_request/warm_start_c_cpp_counterbalance_execution_request.json"
PROBLEM_FAMILY = "stage10119::localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_28t16_56_21_019d3560_1014_7761_9ea7_5638_parameter_golf_records_track_10min_16mb_2026_03_26_statespace_causalmachine_cuda_a018ca0b43_aug_1500000_8b46e7f662::c_cpp::evidence_citation::compact_bounded::perm_"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def by_row_id(card_list: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(card.get("row_id") or ""): card for card in card_list if isinstance(card, dict)}


def accuracy(cards: list[dict[str, Any]]) -> float:
    if not cards:
        return 0.0
    hits = sum(1 for card in cards if bool(card.get("constrained_choice_match")))
    return hits / len(cards)


def group_accuracy(cards: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for card in cards:
        row_id = str(card.get("row_id") or "")
        bucket = "unknown"
        parts = row_id.split("::")
        if key == "language_family" and len(parts) >= 3:
            bucket = parts[2]
        elif key == "task_type" and len(parts) >= 4:
            bucket = parts[3]
        buckets[bucket].append(card)
    return {bucket: {"rows": len(rows), "strict_exact": accuracy(rows)} for bucket, rows in sorted(buckets.items())}


def compare_cards(base: dict[str, dict[str, Any]], target: dict[str, dict[str, Any]]) -> dict[str, int]:
    recovered = regressed = unchanged_correct = unchanged_wrong = 0
    shared = sorted(set(base) & set(target))
    for row_id in shared:
        b = bool(base[row_id].get("constrained_choice_match"))
        t = bool(target[row_id].get("constrained_choice_match"))
        if not b and t:
            recovered += 1
        elif b and not t:
            regressed += 1
        elif b and t:
            unchanged_correct += 1
        else:
            unchanged_wrong += 1
    return {"shared_rows": len(shared), "recovered": recovered, "regressed": regressed, "unchanged_correct": unchanged_correct, "unchanged_wrong": unchanged_wrong}


def family_cards(cards_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [card for row_id, card in sorted(cards_by_id.items()) if row_id.startswith(PROBLEM_FAMILY)]


def build_audit() -> dict[str, Any]:
    audit_10189 = load_json(BASELINE_10189)
    audit_10202 = load_json(BASELINE_10202)
    audit_10206 = load_json(BASELINE_10206)
    audit_10209 = load_json(TARGET_10209)
    request_10208 = load_json(REQUEST_10208)

    rows_10189 = audit_10189.get("row_cards") or []
    rows_10202 = audit_10202.get("row_cards") or []
    rows_10206 = audit_10206.get("row_cards") or []
    rows_10209 = audit_10209.get("row_cards") or []
    by_10189 = by_row_id(rows_10189)
    by_10202 = by_row_id(rows_10202)
    by_10206 = by_row_id(rows_10206)
    by_10209 = by_row_id(rows_10209)

    target_ready = bool(rows_10209)
    findings = []
    if request_10208.get("passed"):
        findings.append("stage10208 prepared a warm-start continuation from the saved stage10202 runtime model")
    if not target_ready:
        findings.append("stage10209 strict-eval audit is not written yet; this audit is a pending comparison scaffold")
    else:
        findings.append("stage10209 strict-eval audit is present and can be compared against stage10189, stage10202, and stage10206")

    result = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": target_ready,
        "artifacts": {
            "baseline_10189": display(BASELINE_10189),
            "baseline_10202": display(BASELINE_10202),
            "baseline_10206": display(BASELINE_10206),
            "target_10209": display(TARGET_10209),
            "execution_request_10208": display(REQUEST_10208),
        },
        "metrics": {
            "target_ready": target_ready,
            "strict_exact_10189": audit_10189.get("constrained_choice_top1_accuracy"),
            "strict_exact_10202": audit_10202.get("constrained_choice_top1_accuracy"),
            "strict_exact_10206": audit_10206.get("constrained_choice_top1_accuracy"),
            "strict_exact_10209": audit_10209.get("constrained_choice_top1_accuracy") if target_ready else None,
            "delta_10202_to_10209": ((audit_10209.get("constrained_choice_top1_accuracy") or 0.0) - (audit_10202.get("constrained_choice_top1_accuracy") or 0.0)) if target_ready else None,
            "delta_10206_to_10209": ((audit_10209.get("constrained_choice_top1_accuracy") or 0.0) - (audit_10206.get("constrained_choice_top1_accuracy") or 0.0)) if target_ready else None,
        },
        "per_language": {
            "stage10202": group_accuracy(rows_10202, "language_family"),
            "stage10206": group_accuracy(rows_10206, "language_family"),
            "stage10209": group_accuracy(rows_10209, "language_family") if target_ready else {},
        },
        "per_task": {
            "stage10202": group_accuracy(rows_10202, "task_type"),
            "stage10206": group_accuracy(rows_10206, "task_type"),
            "stage10209": group_accuracy(rows_10209, "task_type") if target_ready else {},
        },
        "row_transition_summary": {
            "stage10202_to_10206": compare_cards(by_10202, by_10206),
            "stage10202_to_10209": compare_cards(by_10202, by_10209) if target_ready else {},
            "stage10206_to_10209": compare_cards(by_10206, by_10209) if target_ready else {},
        },
        "c_cpp_evidence_citation_problem_family": {
            "target_prefix": PROBLEM_FAMILY,
            "stage10202": {"rows": len(family_cards(by_10202)), "strict_exact": accuracy(family_cards(by_10202)), "row_cards": family_cards(by_10202)},
            "stage10206": {"rows": len(family_cards(by_10206)), "strict_exact": accuracy(family_cards(by_10206)), "row_cards": family_cards(by_10206)},
            "stage10209": {"rows": len(family_cards(by_10209)), "strict_exact": accuracy(family_cards(by_10209)) if target_ready else None, "row_cards": family_cards(by_10209)},
        },
        "findings": findings,
    }
    return result


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps({"stage": STAGE, "stage_name": NAME, "passed": audit["passed"], "artifact": display(AUDIT), "target_ready": audit["metrics"]["target_ready"], "strict_exact_10202": audit["metrics"]["strict_exact_10202"], "strict_exact_10209": audit["metrics"]["strict_exact_10209"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "artifact": display(AUDIT)}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
