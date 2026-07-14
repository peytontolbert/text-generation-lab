#!/usr/bin/env python3
"""Build the v2.7 completion gap audit after the Stage11711 policy freeze.

The goal is to keep the compact-policy win separate from the remaining work
needed for source-heldout multilingual and full-product harness claims.
"""

from __future__ import annotations

import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage11712_v27_completion_gap_and_next_worklist"
SUMMARY_PATH = ROOT / "runs/summaries/stage11712_v27_completion_gap_and_next_worklist.json"

SOURCES = {
    "stage11711_freeze": ROOT
    / "runs/local/artifacts/stage11711_product_policy_freeze_and_claim_boundary/"
    / "product_policy_freeze_and_claim_boundary.json",
    "stage11520_source_heldout_smoke_admission": ROOT
    / "runs/local/artifacts/stage11520_provenance_aware_smoke_admission_audit/"
    / "stage11520_provenance_aware_smoke_admission_audit.json",
    "stage11520_blocked_rows": ROOT
    / "runs/local/artifacts/stage11520_provenance_aware_smoke_admission_audit/"
    / "blocked_standalone_smoke_rows.jsonl",
    "stage11520_pending_rows": ROOT
    / "runs/local/artifacts/stage11520_provenance_aware_smoke_admission_audit/"
    / "pending_final_admission_smoke_rows.jsonl",
    "stage11520_admitted_rows": ROOT
    / "runs/local/artifacts/stage11520_provenance_aware_smoke_admission_audit/"
    / "admitted_standalone_smoke_rows.jsonl",
    "stage11517_source_heldout_worklist": ROOT
    / "runs/local/artifacts/stage11517_source_heldout_harness_hardening_worklist/"
    / "stage11517_source_heldout_harness_hardening_worklist.json",
    "stage11517_work_items": ROOT
    / "runs/local/artifacts/stage11517_source_heldout_harness_hardening_worklist/"
    / "source_heldout_harness_hardening_work_items.jsonl",
    "stage11468_full_product_gate": ROOT
    / "runs/local/artifacts/stage11468_selected_runtime_harness_promotion_gate_audit/"
    / "selected_runtime_harness_promotion_gate_audit.json",
    "stage11514_harness_result": ROOT
    / "runs/local/artifacts/stage11514_selected_frontier_harness_result_audit/"
    / "stage11514_selected_frontier_harness_result_audit.json",
}

LANGS = ("python", "rust", "c_cpp", "web_js_ts_html")


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def require_sources() -> None:
    missing = [str(path.relative_to(ROOT)) for path in SOURCES.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("missing required source artifacts: " + ", ".join(missing))


def blocker_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_lang: dict[str, Counter[str]] = defaultdict(Counter)
    total = Counter()
    for row in rows:
        lang = row.get("language_family", "unknown")
        blockers = row.get("blockers") or []
        for blocker in blockers:
            by_lang[lang][blocker] += 1
            total[blocker] += 1
    return {
        "total": dict(total),
        "by_language": {lang: dict(counter) for lang, counter in sorted(by_lang.items())},
    }


def lang_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(row.get("language_family", "unknown") for row in rows)
    return {lang: counts.get(lang, 0) for lang in LANGS}


def main() -> None:
    require_sources()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    freeze = read_json(SOURCES["stage11711_freeze"])
    smoke = read_json(SOURCES["stage11520_source_heldout_smoke_admission"])
    source_worklist = read_json(SOURCES["stage11517_source_heldout_worklist"])
    harness_gate = read_json(SOURCES["stage11468_full_product_gate"])
    harness_result = read_json(SOURCES["stage11514_harness_result"])
    blocked_rows = read_jsonl(SOURCES["stage11520_blocked_rows"])
    pending_rows = read_jsonl(SOURCES["stage11520_pending_rows"])
    admitted_rows = read_jsonl(SOURCES["stage11520_admitted_rows"])
    source_work_items = read_jsonl(SOURCES["stage11517_work_items"])

    source_heldout_ready_by_language = smoke["metrics"]["admitted_by_language"]
    minimal_multilingual_ready = all(source_heldout_ready_by_language.get(lang, 0) > 0 for lang in LANGS)

    full_product_counts = harness_gate["counts"]
    full_product_ready = (
        full_product_counts.get("runs_with_patch_rows", 0) > 0
        and full_product_counts.get("runs_with_verifier_rows", 0) > 0
        and full_product_counts.get("source_heldout_admissible_rows", 0) > 0
        and full_product_counts.get("singleton_option_rows", 0) == 0
        and full_product_counts.get("prompt_target_value_leak_rows", 0) == 0
    )

    hard_requirements = {
        "compact_multilingual_gemma_win": {
            "status": "satisfied",
            "evidence": freeze["outputs"]["artifact"],
            "summary": (
                f"compact {freeze['metrics']['compact_same_manifest']['hundred_m']['correct']}/"
                f"{freeze['metrics']['compact_same_manifest']['hundred_m']['rows']} vs Gemma "
                f"{freeze['metrics']['compact_same_manifest']['gemma']['correct']}/"
                f"{freeze['metrics']['compact_same_manifest']['gemma']['rows']}"
            ),
        },
        "hardened_compact_anticheat_subset": {
            "status": "satisfied",
            "evidence": freeze["outputs"]["artifact"],
            "summary": (
                f"hardened {freeze['metrics']['compact_hardened_subset']['hundred_m']['correct']}/"
                f"{freeze['metrics']['compact_hardened_subset']['hundred_m']['rows']} vs Gemma "
                f"{freeze['metrics']['compact_hardened_subset']['gemma']['correct']}/"
                f"{freeze['metrics']['compact_hardened_subset']['gemma']['rows']}"
            ),
        },
        "web_compact_gemma_win_with_permutation_stability": {
            "status": "satisfied",
            "evidence": freeze["outputs"]["artifact"],
            "summary": (
                f"web {freeze['metrics']['web_canonical_bridged']['hundred_m_policy']['correct']}/"
                f"{freeze['metrics']['web_canonical_bridged']['hundred_m_policy']['rows']} vs Gemma "
                f"{freeze['metrics']['web_canonical_bridged']['gemma']['correct']}/"
                f"{freeze['metrics']['web_canonical_bridged']['gemma']['rows']}; "
                "3/3 permutations remain 66/66"
            ),
        },
        "multilingual_source_heldout_smoke": {
            "status": "not_satisfied",
            "evidence": str(SOURCES["stage11520_source_heldout_smoke_admission"].relative_to(ROOT)),
            "summary": (
                "admitted source-heldout smoke rows by language: "
                + json.dumps(source_heldout_ready_by_language, sort_keys=True)
            ),
        },
        "broad_full_product_harness_claim": {
            "status": "not_satisfied",
            "evidence": str(SOURCES["stage11468_full_product_gate"].relative_to(ROOT)),
            "summary": (
                f"patch-row runs={full_product_counts.get('runs_with_patch_rows')}, "
                f"verifier-row runs={full_product_counts.get('runs_with_verifier_rows')}, "
                f"source-heldout rows={full_product_counts.get('source_heldout_admissible_rows')}, "
                f"singleton rows={full_product_counts.get('singleton_option_rows')}, "
                f"target-value leaks={full_product_counts.get('prompt_target_value_leak_rows')}"
            ),
        },
        "standalone_weight_freeform_or_patch_generation_better_than_gemma": {
            "status": "not_satisfied",
            "evidence": "no current artifact proves freeform/patch generation superiority",
            "summary": (
                "Current promoted evidence is compact bounded-choice/scorer policy, not freeform patch generation."
            ),
        },
    }

    work_items = [
        {
            "priority": 1,
            "id": "source_heldout_python_cpp_rust_smoke",
            "goal": "Admit at least one clean source-heldout smoke root for Python, C/C++, and Rust.",
            "why": (
                "Stage11520 admits only Web rows; Python/C/C++/Rust all have zero admitted source-heldout smoke rows."
            ),
            "acceptance": [
                "source_heldout_admissible=true or equivalent explicit attestation",
                "root_lineage_key present and not in train/support roots",
                "selected_test_anchor or verifier_anchor present",
                "deterministic option shuffle declared",
                "no singleton options",
                "no prompt target-label/value leak",
            ],
        },
        {
            "priority": 2,
            "id": "promote_pending_web_source_heldout_rows",
            "goal": "Resolve final admission for pending OpenHands/Web source-heldout rows without weakening gates.",
            "why": (
                f"Stage11520 has {len(pending_rows)} pending Web rows with executed verifier provenance."
            ),
            "acceptance": [
                "separate final admission stage asserts source-heldout/no-train split",
                "same anti-cheat gates as strict rows",
                "Gemma and 100M scored same-manifest if promoted to eval",
            ],
        },
        {
            "priority": 3,
            "id": "full_product_patch_verifier_rows",
            "goal": "Create executable patch/verifier harness rows for at least one root per language.",
            "why": (
                "Stage11468 has zero runs with patch rows and zero runs with verifier rows for the compact harness packet."
            ),
            "acceptance": [
                "harness_run_id written",
                "same_task_pack_as_gemma12b=true",
                "tool_trace_spans present",
                "verifier_results include executed focused result",
                "patch_minimality_or_abstain_scores populated",
                "no target leak or source/train overlap",
            ],
        },
        {
            "priority": 4,
            "id": "trainable_product_policy_route",
            "goal": "Replace Stage11709 inference policy with a trained/source-grounded candidate head or frozen scorer route.",
            "why": (
                "Stage11709 is currently a product policy, not a learned weight update; the claim must say that until productized or trained."
            ),
            "acceptance": [
                "route implementation is deterministic and versioned",
                "Stage11710-style option permutation audit remains stable",
                "protected compact gates remain preserved",
                "same-manifest Gemma comparison attached",
            ],
        },
    ]

    artifact = {
        "stage": 11712,
        "stage_name": "v27_completion_gap_and_next_worklist",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "compact_policy_frozen_but_full_v27_goal_not_complete",
        "passed": True,
        "completion_status": "incomplete",
        "hard_requirements": hard_requirements,
        "current_compact_status": {
            "policy_freeze_passed": freeze["passed"],
            "decision": freeze["decision"],
            "supported_scope": freeze["claim_boundary"],
        },
        "source_heldout_status": {
            "minimal_multilingual_ready": minimal_multilingual_ready,
            "admitted_by_language": source_heldout_ready_by_language,
            "admitted_rows_by_language": lang_counts(admitted_rows),
            "pending_rows_by_language": lang_counts(pending_rows),
            "blocked_rows_by_language": lang_counts(blocked_rows),
            "blocked_rows": len(blocked_rows),
            "blockers": blocker_summary(blocked_rows),
            "stage11517_work_item_count": len(source_work_items),
        },
        "full_product_harness_status": {
            "full_product_ready": full_product_ready,
            "same_task_harness_writeback_completed": harness_result["passed"],
            "same_task_harness_metrics": harness_result["metrics"],
            "promotion_gate_counts": full_product_counts,
            "promotion_gate_decision": harness_gate["decision"],
        },
        "next_work_items": work_items,
        "selected_source_heldout_hardening_items": source_work_items[:8],
        "claim_boundary": [
            "Stage11711 is a compact bounded-choice/product-policy win, not full v2.7 completion.",
            "The full objective remains incomplete until multilingual source-heldout rows and executable full-product harness rows are admitted and compared same-manifest against Gemma.",
            "Do not mark broad software-maintenance or freeform/patch superiority complete from current compact scorer artifacts.",
        ],
        "source_artifacts": {
            name: str(path.relative_to(ROOT))
            for name, path in SOURCES.items()
            if path.suffix == ".json"
        },
        "outputs": {
            "artifact": "runs/local/artifacts/stage11712_v27_completion_gap_and_next_worklist/v27_completion_gap_and_next_worklist.json",
            "work_items_jsonl": "runs/local/artifacts/stage11712_v27_completion_gap_and_next_worklist/v27_completion_work_items.jsonl",
            "summary": "runs/summaries/stage11712_v27_completion_gap_and_next_worklist.json",
        },
    }

    artifact_path = OUT_DIR / "v27_completion_gap_and_next_worklist.json"
    work_items_path = OUT_DIR / "v27_completion_work_items.jsonl"
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with work_items_path.open("w", encoding="utf-8") as fh:
        for item in work_items:
            fh.write(json.dumps(item, sort_keys=True) + "\n")
    shutil.copyfile(artifact_path, SUMMARY_PATH)
    print(json.dumps({"artifact": str(artifact_path), "summary": str(SUMMARY_PATH), "work_items": len(work_items)}, indent=2))


if __name__ == "__main__":
    main()
