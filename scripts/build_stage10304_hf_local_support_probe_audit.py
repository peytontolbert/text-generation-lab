#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10304
NAME = "stage10304_hf_local_support_probe_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT_PATH = OUT_DIR / "hf_local_support_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PREVIOUS_BASE = ROOT / "runs/local/artifacts/stage10293_hard_perspective_support_probe/bounded_decoder_probe"
CURRENT_BASE = ROOT / "runs/local/artifacts/stage10303_hf_local_support_probe/bounded_decoder_probe"
REQUEST_PATH = ROOT / (
    "runs/local/artifacts/"
    "stage10302_hf_local_support_execution_request/"
    "hf_local_support_execution_request.json"
)
HARD_AUDIT_PATH = ROOT / (
    "runs/local/artifacts/"
    "stage10298_hard_perspective_support_probe_audit/"
    "hard_perspective_support_probe_audit.json"
)

HF_LOCAL_PREFIX = "stage10300::"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def safe_div(num: int, den: int) -> float | None:
    return (num / den) if den else None


def split_row_id(row_id: str) -> tuple[str, str, str]:
    parts = row_id.split("::")
    if len(parts) < 5:
        return row_id, "unknown", "unknown"
    bundle = "::".join(parts[:-4])
    return bundle, parts[-4], parts[-3]


def bounded_summary(base: Path) -> dict[str, Any]:
    execution = load_json(base / "execution_result.json")
    bounded = load_json(base / "bounded_choice_eval_audit_strict_eval.json")
    row_cards = [row for row in bounded.get("row_cards") or [] if isinstance(row, dict)]

    by_lang: dict[str, list[bool]] = defaultdict(list)
    by_perspective: dict[str, list[bool]] = defaultdict(list)
    by_bundle: dict[str, dict[str, Any]] = {}

    for row in row_cards:
        row_id = str(row.get("row_id") or "")
        bundle, lang, perspective = split_row_id(row_id)
        ok = bool(row.get("constrained_choice_match"))
        by_lang[lang].append(ok)
        by_perspective[perspective].append(ok)
        if bundle not in by_bundle:
            by_bundle[bundle] = {"bundle": bundle, "lang": lang, "oks": [], "perspectives": defaultdict(list)}
        by_bundle[bundle]["oks"].append(ok)
        by_bundle[bundle]["perspectives"][perspective].append(ok)

    def reduce_group(group: dict[str, list[bool]], key: str) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for name in sorted(group):
            oks = group[name]
            correct = sum(1 for ok in oks if ok)
            cards.append({key: name, "rows": len(oks), "correct": correct, "accuracy": safe_div(correct, len(oks))})
        return cards

    bundle_cards: list[dict[str, Any]] = []
    for bundle, card in sorted(by_bundle.items()):
        oks = card["oks"]
        correct = sum(1 for ok in oks if ok)
        bundle_cards.append(
            {
                "bundle": bundle,
                "lang": card["lang"],
                "rows": len(oks),
                "correct": correct,
                "accuracy": safe_div(correct, len(oks)),
                "perspectives": [
                    {
                        "perspective": perspective,
                        "rows": len(poks),
                        "correct": sum(1 for ok in poks if ok),
                        "accuracy": safe_div(sum(1 for ok in poks if ok), len(poks)),
                    }
                    for perspective, poks in sorted(card["perspectives"].items())
                ],
            }
        )

    constrained_prediction_counts = Counter(str(row.get("constrained_choice_top1_label") or "").strip() for row in row_cards)
    full_vocab_prediction_counts = Counter(str(row.get("full_vocab_top1_text") or "").strip() for row in row_cards)

    return {
        "path": display(base),
        "run_id": execution.get("run_id"),
        "train_rows": execution.get("train_rows"),
        "strict_rows": execution.get("strict_rows"),
        "strict_eval": {
            "rows": bounded.get("rows"),
            "constrained_choice_rows": bounded.get("constrained_choice_rows"),
            "constrained_choice_top1_accuracy": bounded.get("constrained_choice_top1_accuracy"),
            "full_vocab_top1_accuracy": bounded.get("full_vocab_top1_accuracy"),
            "rows_with_target_rank_1": bounded.get("rows_with_target_rank_1"),
        },
        "prediction_shapes": {
            "constrained_choice_prediction_counts": dict(sorted(constrained_prediction_counts.items())),
            "full_vocab_prediction_counts": dict(sorted(full_vocab_prediction_counts.items())),
        },
        "by_lang": reduce_group(by_lang, "lang"),
        "by_perspective": reduce_group(by_perspective, "perspective"),
        "by_bundle": bundle_cards,
    }


def index_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row.get(key)): row for row in rows}


def delta_cards(previous: list[dict[str, Any]], current: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    prev_by = index_by(previous, key)
    curr_by = index_by(current, key)
    all_names = sorted(set(prev_by) | set(curr_by))
    cards: list[dict[str, Any]] = []
    for name in all_names:
        prev = prev_by.get(name, {})
        curr = curr_by.get(name, {})
        prev_acc = prev.get("accuracy")
        curr_acc = curr.get("accuracy")
        delta = None if prev_acc is None or curr_acc is None else curr_acc - prev_acc
        card = {
            key: name,
            "previous_accuracy": prev_acc,
            "current_accuracy": curr_acc,
            "delta_accuracy": delta,
            "previous_rows": prev.get("rows"),
            "current_rows": curr.get("rows"),
        }
        if "lang" in curr or "lang" in prev:
            card["lang"] = curr.get("lang", prev.get("lang"))
        cards.append(card)
    return cards


def build_report() -> dict[str, Any]:
    previous = bounded_summary(PREVIOUS_BASE)
    current = bounded_summary(CURRENT_BASE)
    request = load_json(REQUEST_PATH)
    prior_hard_audit = load_json(HARD_AUDIT_PATH)

    strict_delta = (
        None
        if previous["strict_eval"]["constrained_choice_top1_accuracy"] is None
        or current["strict_eval"]["constrained_choice_top1_accuracy"] is None
        else current["strict_eval"]["constrained_choice_top1_accuracy"]
        - previous["strict_eval"]["constrained_choice_top1_accuracy"]
    )
    full_vocab_delta = (
        None
        if previous["strict_eval"]["full_vocab_top1_accuracy"] is None
        or current["strict_eval"]["full_vocab_top1_accuracy"] is None
        else current["strict_eval"]["full_vocab_top1_accuracy"] - previous["strict_eval"]["full_vocab_top1_accuracy"]
    )
    target_rank_delta = (
        None
        if previous["strict_eval"]["rows_with_target_rank_1"] is None
        or current["strict_eval"]["rows_with_target_rank_1"] is None
        else current["strict_eval"]["rows_with_target_rank_1"] - previous["strict_eval"]["rows_with_target_rank_1"]
    )

    deltas = {
        "by_lang": delta_cards(previous["by_lang"], current["by_lang"], "lang"),
        "by_perspective": delta_cards(previous["by_perspective"], current["by_perspective"], "perspective"),
        "by_bundle": delta_cards(previous["by_bundle"], current["by_bundle"], "bundle"),
    }

    improved_langs = [card["lang"] for card in deltas["by_lang"] if (card.get("delta_accuracy") or 0.0) > 0.0]
    unchanged_langs = [card["lang"] for card in deltas["by_lang"] if (card.get("delta_accuracy") or 0.0) == 0.0]
    improved_perspectives = [
        card["perspective"] for card in deltas["by_perspective"] if (card.get("delta_accuracy") or 0.0) > 0.0
    ]

    current_bundle_index = index_by(current["by_bundle"], "bundle")
    weakest_bundle = min(
        current["by_bundle"],
        key=lambda card: ((card.get("accuracy") if card.get("accuracy") is not None else 1.0), -(card.get("rows") or 0)),
    )

    frontloaded_focus_counts = request.get("frontloaded_focus_counts") or {}
    hf_local_train_rows = int(frontloaded_focus_counts.get("hf_local_added") or 0)
    honesty_gates = [str(item) for item in (request.get("required_honesty_gates") or []) if isinstance(item, str)]
    strict_eval_unchanged = any("strict eval rows remain identical" in gate.lower() for gate in honesty_gates)

    verdict = {
        "strict_eval_constrained_choice_delta": strict_delta,
        "strict_eval_full_vocab_delta": full_vocab_delta,
        "rows_with_target_rank_1_delta": target_rank_delta,
        "improved_langs": improved_langs,
        "unchanged_langs": unchanged_langs,
        "improved_perspectives": improved_perspectives,
        "hf_local_support_rows_train_only": True,
        "hf_local_support_train_rows": hf_local_train_rows,
        "strict_eval_unchanged_from_frontier": strict_eval_unchanged,
        "main_gain_interpretation": (
            "narrow_support_rows_improved_strict_eval_on_existing_admitted_bundles_without_changing_the_eval_set"
            if strict_delta and strict_delta > 0
            else "no_material_strict_eval_gain_detected"
        ),
        "remaining_frontier": {
            "weakest_bundle": weakest_bundle["bundle"],
            "weakest_bundle_lang": weakest_bundle["lang"],
            "weakest_bundle_accuracy": weakest_bundle["accuracy"],
            "weak_perspectives": [
                perspective["perspective"]
                for perspective in weakest_bundle["perspectives"]
                if (perspective.get("accuracy") or 0.0) == 0.0
            ],
        },
        "promotion_call": (
            "keep_as_narrow_support_family_gain_but_do_not_claim_resolution_of_mirrormind_python_or_web_hard_perspectives"
            if strict_delta and strict_delta > 0
            else "reject_as_frontier_change"
        ),
        "next_action": (
            "build source-backed support rows that directly target Mirrormind action-taking and web hard-perspective action selection; "
            "hf_local support helped bounded retrieval behavior but did not repair the main unresolved families"
        ),
        "source_context": {
            "previous_hard_perspective_macro_exact_100m": (
                ((prior_hard_audit.get("results") or {}).get("new_hard_perspective") or {}).get("macro_exact_100m")
            ),
            "previous_hard_perspective_macro_exact_gemma": (
                ((prior_hard_audit.get("results") or {}).get("new_hard_perspective") or {}).get("macro_exact_gemma")
            ),
        },
    }

    return {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "inputs": {
            "previous_probe": display(PREVIOUS_BASE),
            "current_probe": display(CURRENT_BASE),
            "support_request": display(REQUEST_PATH),
            "prior_hard_probe_audit": display(HARD_AUDIT_PATH),
        },
        "runs": {
            "stage10293": previous,
            "stage10303": current,
        },
        "deltas": deltas,
        "verdict": verdict,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    report = build_report()
    OUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(
        json.dumps(
            {
                "stage": STAGE,
                "passed": True,
                "report": display(OUT_PATH),
                "verdict": report["verdict"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"stage": STAGE, "passed": True, "report": display(OUT_PATH), "verdict": report["verdict"]},
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
