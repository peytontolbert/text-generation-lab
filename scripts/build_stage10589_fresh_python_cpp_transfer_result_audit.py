#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10589
NAME = "stage10589_fresh_python_cpp_transfer_result_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "fresh_python_cpp_transfer_result_audit.json"

OLD_FRONTIER_AUDIT = ROOT / "runs/local/artifacts/stage10577_visible_candidate_mixed_preservation_result_audit/visible_candidate_mixed_preservation_result_audit.json"
CANARY_AUDIT = ROOT / "runs/local/artifacts/stage10587_fresh_python_cpp_visible_candidate_canary_audit/fresh_python_cpp_visible_candidate_canary_audit.json"
FRESH_COMPARISON = ROOT / "runs/local/artifacts/stage10588_fresh_python_cpp_visible_candidate_same_manifest_comparison/fresh_python_cpp_visible_candidate_same_manifest_comparison.json"
COMBINED_ROWS = ROOT / "runs/local/artifacts/stage10588_fresh_python_cpp_visible_candidate_same_manifest_comparison/combined_rows.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10584_fresh_python_cpp_visible_candidate_package/strict_eval_rows.jsonl"


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


def exact(value: Any) -> float | None:
    if not isinstance(value, dict):
        return None
    metric = value.get("exact_accuracy")
    return float(metric) if isinstance(metric, (int, float)) else None


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
    fresh = load_json(FRESH_COMPARISON)
    combined_rows = load_jsonl(COMBINED_ROWS)
    strict_rows = load_jsonl(STRICT_ROWS)

    fresh_hundred = fresh["hundred_m"]
    fresh_gemma = fresh["gemma12b"]
    old_state = old_frontier["current_state"]
    canary_summary = canary["summary"]

    retrieve_structure = subtype_distribution(combined_rows, "retrieve_answer_abstain", "hundred_m_generated_text")
    verifier_structure = subtype_distribution(combined_rows, "verifier_outcome_masked", "hundred_m_generated_text")
    decisive_structure = subtype_distribution(combined_rows, "decisive_evidence_top1", "hundred_m_generated_text")
    fresh_strict_target_dist = Counter(str(row.get("target_subtype") or "") for row in strict_rows)
    fresh_language_dist = Counter(str(row.get("language_family") or "") for row in strict_rows)

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
            "fresh_python_cpp_overall_exact": exact(fresh_hundred["overall"]),
            "fresh_python_cpp_gemma_exact": exact(fresh_gemma["overall"]),
            "fresh_python_cpp_decisive_exact": exact(fresh_hundred["by_target_subtype"]["decisive_evidence_top1"]),
            "fresh_python_cpp_gemma_decisive_exact": exact(fresh_gemma["by_target_subtype"]["decisive_evidence_top1"]),
            "fresh_python_cpp_retrieve_exact": exact(fresh_hundred["by_target_subtype"]["retrieve_answer_abstain"]),
            "fresh_python_cpp_gemma_retrieve_exact": exact(fresh_gemma["by_target_subtype"]["retrieve_answer_abstain"]),
            "fresh_python_cpp_verifier_exact": exact(fresh_hundred["by_target_subtype"]["verifier_outcome_masked"]),
            "fresh_python_cpp_gemma_verifier_exact": exact(fresh_gemma["by_target_subtype"]["verifier_outcome_masked"]),
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
        "fresh_per_subtype_language": per_subtype_language(combined_rows),
        "deltas": {
            "fresh_overall_delta_vs_gemma": exact(fresh_hundred["overall"]) - exact(fresh_gemma["overall"]),
            "fresh_decisive_delta_vs_gemma": exact(fresh_hundred["by_target_subtype"]["decisive_evidence_top1"]) - exact(fresh_gemma["by_target_subtype"]["decisive_evidence_top1"]),
            "fresh_retrieve_delta_vs_gemma": exact(fresh_hundred["by_target_subtype"]["retrieve_answer_abstain"]) - exact(fresh_gemma["by_target_subtype"]["retrieve_answer_abstain"]),
            "fresh_verifier_delta_vs_gemma": exact(fresh_hundred["by_target_subtype"]["verifier_outcome_masked"]) - exact(fresh_gemma["by_target_subtype"]["verifier_outcome_masked"]),
            "fresh_overall_delta_vs_old_frontier": exact(fresh_hundred["overall"]) - float(old_state["stage10576_hundred_m_exact"]),
            "fresh_decisive_delta_vs_old_frontier": exact(fresh_hundred["by_target_subtype"]["decisive_evidence_top1"]) - float(old_state["stage10576_hundred_m_decisive_exact"]),
        },
        "truthful_read": [
            "The stage10586 runtime preserved the repaired 24-row canary exactly at 22/24 bounded, so the fresh-root transfer did not regress the prior reviewed frontier.",
            "On the fresh repo-disjoint Python/C++ strict slice, the 100M model beats Gemma overall at 131/189 versus 80/189, including both Python and C/C++.",
            "That overall win is not coming from decisive evidence. Fresh decisive_evidence_top1 is only 5/63 for the 100M model, slightly worse than Gemma at 7/63.",
            "The fresh overall margin is instead driven by constant-target preservation subtypes: retrieve_answer_abstain is 63/63 for the 100M model and verifier_outcome_masked is 63/63.",
            "Because fresh retrieve and fresh verifier are structurally constant-target here, this package proves some repo-disjoint transfer but does not yet prove expert-level evidence selection on fresh roots.",
        ],
        "anti_cheat_implications": [
            "Do not upgrade stage10588 into a broad maintainer-competence claim. It is a fresh-root Python/C++ transfer win with decisive-evidence failure still unresolved.",
            "Any promotion gate for future v2.7/v2.8 should require non-constant retrieve and non-constant verifier target distributions on fresh strict rows.",
            "Decisive-evidence rows need stronger candidate answerability and harder negatives; otherwise overall exact can improve while the maintainer-relevant evidence skill remains weak.",
            "Rust and web remain absent from the fresh strict transfer path, so multilingual headline claims still require fresh repo-disjoint supply in those languages.",
        ],
        "next_actions": [
            "Rebuild fresh retrieve_answer_abstain with real target diversity, including RETRIEVE_MORE, ABSTAIN_INSUFFICIENT_EVIDENCE, and NEEDS_VERIFIER on repo-disjoint roots.",
            "Rebuild fresh verifier_outcome_masked so PASS_TARGETED_TEST_SELECTION is not the only target on the fresh strict path.",
            "Mine fresh rust and web repo-disjoint decisive roots before the next multilingual claim stage.",
            "Keep the repaired 24-row canary and the old rebuilt 54-row frontier as regression gates while expanding fresh strict rows with better subtype balance.",
        ],
        "outputs": {
            "audit_json": display(SUMMARY_JSON),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
