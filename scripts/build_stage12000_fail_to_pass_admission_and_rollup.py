#!/usr/bin/env python3
"""Admit Stage11999 real-source FAIL_TO_PASS rows and roll into transition support v7."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12000_fail_to_pass_admission_and_rollup")
STAGE11999_SUMMARY = Path("runs/local/artifacts/stage11999_real_source_fail_to_pass_mutations/real_source_fail_to_pass_mutations.json")
STAGE11999_ROWS = Path("runs/local/artifacts/stage11999_real_source_fail_to_pass_mutations/real_source_fail_to_pass_rows.jsonl")
BASE = Path("runs/local/artifacts/stage11998_transition_support_rollup_v6/transition_support_rows_v6.jsonl")
ADMITTED = ROOT / "real_source_fail_to_pass_admitted_rows.jsonl"
ROLLUP = ROOT / "transition_support_rows_v7.jsonl"
SUMMARY = ROOT / "fail_to_pass_admission_and_rollup.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12000_fail_to_pass_admission_and_rollup.json")
LANGUAGE_FLOORS = {"python": 50, "rust": 50, "c_cpp": 50, "web_js_ts_html": 50}
STATUS_FLOORS = {"FAIL_TO_PASS": 50, "PASS_TO_PASS": 100, "PASS_CURRENT_BUILD": 40, "PASS_CURRENT_BUILD_AND_RUN": 40, "INSUFFICIENT_EVIDENCE": 40, "NOT_EXERCISED": 40}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists(): return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def root_key(row: dict[str, Any]) -> str | None:
    return row.get("root_lineage_key") or row.get("root_id") or row.get("source_root_id") or row.get("source_bundle_id") or row.get("row_id")


def all_pass(results: list[dict[str, Any]]) -> bool:
    return bool(results) and all(r.get("returncode") == 0 and not r.get("timed_out") for r in results)


def any_fail(results: list[dict[str, Any]]) -> bool:
    return bool(results) and any(r.get("returncode") not in (0, None) or r.get("timed_out") for r in results)


def source_card(row: dict[str, Any]) -> dict[str, Any]:
    src = row.get("standalone_projection_source") or {}
    obs = src.get("tool_or_verifier_observation") or {}
    return obs


def valid_row(row: dict[str, Any], summary_cards_by_id: dict[str, dict[str, Any]]) -> tuple[bool, str | None]:
    if row.get("observed_verifier_transition") != "FAIL_TO_PASS":
        return False, "wrong_observed_transition"
    if (row.get("target") or {}).get("semantic_value") != "FAIL_TO_PASS":
        return False, "wrong_target_semantic_value"
    if len(row.get("opaque_options") or []) < 2:
        return False, "singleton_or_missing_options"
    anti = row.get("anti_cheat") or {}
    if anti.get("deterministic_option_shuffle") is not True:
        return False, "shuffle_not_asserted"
    obs = source_card(row)
    if not all_pass(obs.get("baseline") or []):
        return False, "baseline_not_clean_pass"
    if not any_fail(obs.get("mutant") or []):
        return False, "mutant_did_not_fail"
    if not all_pass(obs.get("restored") or []):
        return False, "restored_not_clean_pass"
    card = summary_cards_by_id.get(row.get("row_id"))
    if card and card.get("restored_matches_original") is not True:
        return False, "restore_guard_failed"
    return True, None


def retag(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["split"] = "train"
    out["split_role"] = "stage12000_real_source_fail_to_pass_train_support_only"
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["source_heldout_admissible"] = False
    out["stage12000_admission"] = {"admitted": True, "source_stage": "stage11999", "reason": "baseline_mutant_restored_real_source_fail_to_pass_verified"}
    anti = dict(out.get("anti_cheat") or {})
    anti.update({"deterministic_option_shuffle": True, "singleton_options": False, "target_label_not_visible_before_options": True, "target_value_not_visible_before_options": True, "train_support_only": True})
    out["anti_cheat"] = anti
    return out


def rem(counts: Counter, floors: dict[str, int]) -> dict[str, int]:
    return {k: max(0, v - counts.get(k, 0)) for k, v in floors.items()}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    raw_rows = read_jsonl(STAGE11999_ROWS)
    stage11999 = json.loads(STAGE11999_SUMMARY.read_text()) if STAGE11999_SUMMARY.exists() else {}
    cards_by_row = {}
    # Cards do not include row_id directly; map by spec id embedded in row_id.
    for card in stage11999.get("probe_cards") or []:
        spec_id = ((card.get("spec") or {}).get("id"))
        if spec_id:
            for row in raw_rows:
                if spec_id in (row.get("row_id") or ""):
                    cards_by_row[row.get("row_id")] = card
    admitted, rejected = [], []
    reject_reasons = Counter()
    for row in raw_rows:
        ok, reason = valid_row(row, cards_by_row)
        if ok:
            admitted.append(retag(row))
        else:
            reject_reasons[reason or "unknown"] += 1
            rejected.append({"row_id": row.get("row_id"), "reason": reason or "unknown"})
    write_jsonl(ADMITTED, admitted)

    rows = []
    seen = set()
    duplicates = 0
    for source, path in [("stage11998", BASE), ("stage12000", ADMITTED)]:
        for row in read_jsonl(path):
            out = dict(row)
            out["stage12000_rollup_source"] = source
            key = (out.get("row_id"), root_key(out), out.get("observed_verifier_transition"))
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            rows.append(out)
    write_jsonl(ROLLUP, rows)

    lang = Counter(r.get("language_family") for r in rows)
    status = Counter(r.get("observed_verifier_transition") for r in rows)
    repo = Counter(r.get("repo_family") for r in rows)
    summary = {
        "stage": "stage12000_fail_to_pass_admission_and_rollup",
        "source_rows": str(STAGE11999_ROWS),
        "base_rows": str(BASE),
        "admitted_rows_path": str(ADMITTED),
        "rollup_rows_path": str(ROLLUP),
        "rows_reviewed": len(raw_rows),
        "admitted_rows": len(admitted),
        "rejected_rows": len(rejected),
        "rejection_reasons": dict(sorted(reject_reasons.items())),
        "rollup_total_rows": len(rows),
        "rollup_unique_roots": len({root_key(r) for r in rows}),
        "language_counts": dict(sorted(lang.items())),
        "status_counts": dict(sorted(status.items())),
        "repo_family_counts_top20": dict(repo.most_common(20)),
        "remaining_language_floor": rem(lang, LANGUAGE_FLOORS),
        "remaining_status_floor": rem(status, STATUS_FLOORS),
        "decision": "support_inventory_v7_not_train_ready",
        "reason": "Real-source FAIL_TO_PASS coverage improved, but Transition-Root-250 floors remain far below target; no training probe justified yet.",
        "claim_boundary": "Admitted rows are real local source mutation train-support only, not strict/source-heldout independent task roots.",
        "next_stage_recommendation": {"stage": "stage12001_fresh_executable_root_probe", "action": "Mine additional independent C/C++ and web executable roots, then generate more real-source FAIL_TO_PASS from those roots."},
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    SUMMARY_MIRROR.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__": main()
