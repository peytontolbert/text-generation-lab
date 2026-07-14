#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10596
NAME = "stage10596_fresh_python_cpp_mixed_contract_result_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "fresh_python_cpp_mixed_contract_result_audit.json"

OLD_FRONTIER_AUDIT = ROOT / "runs/local/artifacts/stage10577_visible_candidate_mixed_preservation_result_audit/visible_candidate_mixed_preservation_result_audit.json"
CANARY_AUDIT = ROOT / "runs/local/artifacts/stage10595_fresh_python_cpp_mixed_contract_canary_audit/fresh_python_cpp_mixed_contract_canary_audit.json"
FRESH_COMPARISON = ROOT / "runs/local/artifacts/stage10594_fresh_python_cpp_mixed_contract_probe/bounded_decoder_probe/execution_result.json"
COMBINED_ROWS = ROOT / "runs/local/artifacts/stage10591_fresh_python_cpp_visible_candidate_mixed_contract_package/strict_eval_rows.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10591_fresh_python_cpp_visible_candidate_mixed_contract_package/strict_eval_rows.jsonl"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def subtype_distribution(rows: list[dict[str, Any]], subtype: str, field: str) -> dict[str, Any]:
    subset = [row for row in rows if str(row.get("target_subtype") or "") == subtype]
    target_counter = Counter(str(row.get("target_text") or "") for row in subset)
    pred_counter = Counter(str(row.get(field) or "") for row in subset)
    return {
        "rows": len(subset),
        "target_text_counts": dict(sorted(target_counter.items())),
        "predicted_text_counts": dict(sorted(pred_counter.items())),
        "dominant_target_text": target_counter.most_common(1)[0][0] if target_counter else None,
        "dominant_target_text_fraction": (target_counter.most_common(1)[0][1] / len(subset)) if subset else None,
        "dominant_predicted_text": pred_counter.most_common(1)[0][0] if pred_counter else None,
        "dominant_predicted_text_fraction": (pred_counter.most_common(1)[0][1] / len(subset)) if subset else None,
    }


def per_subtype_language(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        buckets[str(row.get("target_subtype") or "unknown")][str(row.get("language_family") or "unknown")].append(row)
    out: dict[str, Any] = {}
    for subtype, lang_buckets in sorted(buckets.items()):
        out[subtype] = {}
        for language, bucket in sorted(lang_buckets.items()):
            hundred_correct = sum(1 for row in bucket if row.get("hundred_m_exact_match") is True)
            gemma_correct = sum(1 for row in bucket if row.get("gemma12b_exact_match") is True)
            size = len(bucket)
            out[subtype][language] = {
                "rows": size,
                "hundred_m_exact_accuracy": (hundred_correct / size) if size else None,
                "gemma12b_exact_accuracy": (gemma_correct / size) if size else None,
                "delta_hundred_m_minus_gemma": ((hundred_correct - gemma_correct) / size) if size else None,
            }
    return out


def main() -> None:
    old_frontier = load_json(OLD_FRONTIER_AUDIT)
    canary = load_json(CANARY_AUDIT)
    execution = load_json(FRESH_COMPARISON)
    strict_rows = load_jsonl(STRICT_ROWS)

    old_state = old_frontier["current_state"]
    canary_summary = canary["summary"]
    strict_cards = (((execution.get("bounded_choice_eval") or {}).get("strict_eval") or {}).get("row_cards") or [])
    row_index = {str(row.get("row_id") or ""): row for row in strict_rows}
    merged = []
    for card in strict_cards:
        row_id = str(card.get("row_id") or "")
        meta = row_index.get(row_id, {})
        merged.append({**meta, **card})

    fresh_strict_target_dist = Counter(str(row.get("target_subtype") or "") for row in strict_rows)
    fresh_language_dist = Counter(str(row.get("language_family") or "") for row in strict_rows)

    def metric(rows, field):
        vals=[row for row in rows if isinstance(row.get(field), bool)]
        correct=sum(1 for row in vals if row.get(field) is True)
        return (correct/len(vals)) if vals else None

    subtype_lang = defaultdict(lambda: defaultdict(list))
    for row in merged:
        subtype_lang[str(row.get("target_subtype") or "unknown")][str(row.get("language_family") or "unknown")].append(row)
    fresh_per_subtype_language = {}
    for subtype, langs in sorted(subtype_lang.items()):
        fresh_per_subtype_language[subtype] = {}
        for lang, bucket in sorted(langs.items()):
            fresh_per_subtype_language[subtype][lang] = {
                "rows": len(bucket),
                "hundred_m_exact_accuracy": metric(bucket, "full_vocab_top1_match"),
            }

    def structure(subtype):
        subset=[row for row in merged if str(row.get("target_subtype") or "") == subtype]
        target_counts=Counter(str(row.get("target_text") or "") for row in subset)
        pred_counts=Counter(str(row.get("full_vocab_top1_text") or "") for row in subset)
        return {
            "rows": len(subset),
            "target_text_counts": dict(sorted(target_counts.items())),
            "predicted_text_counts": dict(sorted(pred_counts.items())),
            "dominant_target_text": target_counts.most_common(1)[0][0] if target_counts else None,
            "dominant_target_text_fraction": (target_counts.most_common(1)[0][1] / len(subset)) if subset else None,
            "dominant_predicted_text": pred_counts.most_common(1)[0][0] if pred_counts else None,
            "dominant_predicted_text_fraction": (pred_counts.most_common(1)[0][1] / len(subset)) if subset else None,
        }

    retrieve_structure = structure("retrieve_answer_abstain")
    verifier_structure = structure("verifier_outcome_masked")
    decisive_structure = structure("decisive_evidence_top1")

    strict_eval = ((execution.get("bounded_choice_eval") or {}).get("strict_eval") or {})
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "inputs": {
            "old_frontier_audit": display(OLD_FRONTIER_AUDIT),
            "canary_audit": display(CANARY_AUDIT),
            "fresh_same_manifest_comparison": display(FRESH_COMPARISON),
            "fresh_combined_rows": display(COMBINED_ROWS),
            "fresh_strict_rows": display(STRICT_ROWS),
        },
        "claim_scope": [
            "Cross-audits the old rebuilt 54-row frontier, the repaired 24-row canary, and the fresh repo-disjoint Python/C++ strict transfer result.",
            "Separates real fresh-root transfer from structural shortcut wins on constant-target subtypes.",
            "This is a result audit and next-step gate, not a new training run.",
        ],
        "current_state": {
            "old_rebuilt_frontier_overall_exact": old_state["stage10576_hundred_m_exact"],
            "old_rebuilt_frontier_gemma_exact": old_state["stage10576_gemma_exact"],
            "old_rebuilt_frontier_decisive_exact": old_state["stage10576_hundred_m_decisive_exact"],
            "old_rebuilt_frontier_retrieve_exact": old_state["stage10576_hundred_m_retrieve_exact"],
            "old_rebuilt_frontier_verifier_exact": old_state["stage10576_hundred_m_verifier_exact"],
            "repaired_canary_bounded_accuracy": canary_summary["bounded_accuracy"],
            "fresh_python_cpp_overall_exact": (strict_eval.get("full_vocab_top1_accuracy")),
            "fresh_python_cpp_gemma_exact": None,
            "fresh_python_cpp_decisive_exact": metric([row for row in merged if str(row.get("target_subtype") or "") == "decisive_evidence_top1"], "full_vocab_top1_match"),
            "fresh_python_cpp_gemma_decisive_exact": None,
            "fresh_python_cpp_retrieve_exact": metric([row for row in merged if str(row.get("target_subtype") or "") == "retrieve_answer_abstain"], "full_vocab_top1_match"),
            "fresh_python_cpp_gemma_retrieve_exact": None,
            "fresh_python_cpp_verifier_exact": metric([row for row in merged if str(row.get("target_subtype") or "") == "verifier_outcome_masked"], "full_vocab_top1_match"),
            "fresh_python_cpp_gemma_verifier_exact": None,
        },
        "fresh_split_shape": {
            "strict_rows": len(strict_rows),
            "strict_language_counts": dict(sorted(fresh_language_dist.items())),
            "strict_target_subtype_counts": dict(sorted(fresh_strict_target_dist.items())),
            "language_scope_note": "Fresh strict transfer currently covers python and c_cpp only; rust and web are not in this comparison.",
        },
        "fresh_structure_audit": {
            "retrieve_answer_abstain": retrieve_structure,
            "verifier_outcome_masked": verifier_structure,
            "decisive_evidence_top1": decisive_structure,
            "retrieve_is_constant_target": retrieve_structure["dominant_target_text_fraction"] == 1.0,
            "verifier_is_constant_target": verifier_structure["dominant_target_text_fraction"] == 1.0,
            "decisive_is_constant_target": decisive_structure["dominant_target_text_fraction"] == 1.0,
        },
        "fresh_per_subtype_language": fresh_per_subtype_language,
        "deltas": {
            "fresh_overall_delta_vs_gemma": None,
            "fresh_decisive_delta_vs_gemma": None,
            "fresh_retrieve_delta_vs_gemma": None,
            "fresh_verifier_delta_vs_gemma": None,
            "fresh_overall_delta_vs_old_frontier": (strict_eval.get("full_vocab_top1_accuracy") - float(old_state["stage10576_hundred_m_exact"])),
            "fresh_decisive_delta_vs_old_frontier": (metric([row for row in merged if str(row.get("target_subtype") or "") == "decisive_evidence_top1"], "full_vocab_top1_match") - float(old_state["stage10576_hundred_m_decisive_exact"])),
        },
        "truthful_read": [
            "The stage10594 runtime preserved the repaired 24-row canary exactly at 22/24 bounded, so the harder mixed-contract package did not damage the prior reviewed frontier.",
            "On the fresh repo-disjoint Python/C++ mixed-contract strict slice, the 100M model collapsed to 26/189 full-vocab top-1 on its own execution result, so this run is not promotable.",
            "The failure is broad, not just decisive evidence: the model predicts label C for most strict rows, including retrieve and verifier rows that no longer have constant-target shortcuts.",
            "This means the anti-cheat package repair worked, but the current 100M runtime does not yet generalize to the harder mixed-contract interface.",
            "A same-manifest Gemma comparison is not the next priority for this run because the 100M model is already far below its prior 131/189 fresh-transfer baseline.",
        ],
        "anti_cheat_implications": [
            "Do not upgrade stage10594 into any claim. It is a non-promotable mixed-contract probe that preserved the canary but failed the new fresh strict package.",
            "The new non-constant contract gate remains correct and should stay in place; the failure is model-side, not a reason to relax the gate.",
            "The next model-side experiment should be a diagnostic support run or curriculum step targeted at the new mixed retrieve/verifier labels before rerunning a full fresh comparison.",
            "Rust and web remain outside this mixed-contract path, so multilingual headline claims are still blocked independently of this failure.",
        ],
        "next_actions": [
            "Keep stage10591 as the new honest package baseline and do not revert to the old constant-target contract.",
            "Design the next training support around the mixed A/B/D retrieve and verifier labels that stage10591 introduced.",
            "Run an old-frontier rebuilt audit against stage10594 only if needed for bookkeeping; the fresh strict collapse is already sufficient to reject promotion.",
            "After a targeted recovery run, repeat the mixed-contract fresh comparison before spending cycles on Gemma for this package.",
        ],
        "outputs": {
            "audit_json": display(SUMMARY_JSON),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
