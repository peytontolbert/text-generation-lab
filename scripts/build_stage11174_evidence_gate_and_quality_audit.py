#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11174
NAME = "stage11174_evidence_gate_and_quality_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "evidence_gate_and_quality_audit.json"
ROW_CARDS_JSONL = OUT_DIR / "evidence_quality_row_cards.jsonl"

SCORER_AUDIT = ARTIFACTS / "stage11172_scorer_objective_mismatch_audit" / "scorer_objective_mismatch_audit.json"
SCORER_CARDS = ARTIFACTS / "stage11172_scorer_objective_mismatch_audit" / "scorer_objective_row_cards.jsonl"
ROW_SOURCES = {
    "clean_strict": ARTIFACTS / "stage11146_singleton_strict_quarantine_successor" / "agentkernel_lite_encdec_strict_eval.jsonl",
    "clean_validation": ARTIFACTS / "stage11146_singleton_strict_quarantine_successor" / "agentkernel_lite_encdec_validation.jsonl",
    "reserved_residual": ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence" / "reserved_residual_candidates.jsonl",
}

ROLE_VALUES = {
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
    "algorithmic_background_reference",
    "external_analogue_reference",
}

CONFLICT_PATTERNS = [
    r"changed candidate surface directly",
    r"directly exposes",
    r"directly includes",
    r"bounded packet directly exposes",
    r"primary visible signal points to",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


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


def option_value_for_label(row: dict[str, Any], label: str | None) -> str | None:
    opts = ((row.get("standalone_projection_source") or {}).get("opaque_options") or row.get("opaque_options") or [])
    for opt in opts:
        if isinstance(opt, dict) and str(opt.get("label") or "") == str(label):
            return str(opt.get("value") or "")
    return None


def gold_value(row: dict[str, Any]) -> str:
    sps = row.get("standalone_projection_source") or {}
    return str(sps.get("gold_value") or option_value_for_label(row, str(row.get("target_text") or "")) or "")


def parse_evidence_blocks(text: str) -> dict[str, dict[str, str]]:
    blocks: dict[str, dict[str, str]] = {}
    lines = text.splitlines()
    current_role: str | None = None
    for line in lines:
        if line.startswith("Options:") or line.startswith("Answer:"):
            current_role = None
            continue
        m = re.match(r"^([A-Za-z0-9_]+) \[([^\]]*)\]:\s*(.*)$", line)
        if m and m.group(1) in ROLE_VALUES:
            current_role = m.group(1)
            blocks[current_role] = {"path": m.group(2), "text": m.group(3)}
            continue
        if current_role and line.strip():
            blocks[current_role]["text"] += " " + line.strip()
    return blocks


def quality_card(split: str, row: dict[str, Any]) -> dict[str, Any]:
    text = str(row.get("input_text") or row.get("prompt_text") or "")
    blocks = parse_evidence_blocks(text)
    gold = gold_value(row)
    role_paths: dict[str, str] = {role: block.get("path", "") for role, block in blocks.items()}
    path_to_roles: dict[str, list[str]] = defaultdict(list)
    for role, path in role_paths.items():
        if path:
            path_to_roles[path].append(role)
    duplicate_paths = {path: roles for path, roles in path_to_roles.items() if len(roles) > 1}
    verifier_text = (blocks.get("verifier_and_test_constraint") or {}).get("text", "")
    candidate_text = (blocks.get("candidate_change_surface") or {}).get("text", "")
    conflict_hits = [pat for pat in CONFLICT_PATTERNS if re.search(pat, verifier_text, re.I)]
    has_selected_test_ledger = bool(re.search(r"selected[- ]?test ledger", verifier_text, re.I))
    has_no_selected_test = bool(re.search(r"no_selected_test_recorded|ABSTAIN_INSUFFICIENT_EVIDENCE", verifier_text, re.I))
    role_conflict = bool(
        gold == "candidate_change_surface"
        and "verifier_and_test_constraint" in blocks
        and conflict_hits
    )
    verifier_gold_with_no_selected_test = bool(gold == "verifier_and_test_constraint" and has_no_selected_test)
    duplicated_gold_path = bool(any(gold in roles and len(roles) > 1 for roles in duplicate_paths.values()))
    return {
        "split": split,
        "row_id": str(row.get("row_id") or ""),
        "language_family": str(row.get("language_family") or "unknown"),
        "repo_family": str(row.get("repo_family") or "unknown"),
        "target_label": str(row.get("target_text") or ""),
        "gold_value": gold,
        "role_paths": role_paths,
        "duplicate_paths": duplicate_paths,
        "has_selected_test_ledger": has_selected_test_ledger,
        "has_no_selected_test_marker": has_no_selected_test,
        "verifier_conflict_patterns": conflict_hits,
        "role_conflict_candidate_vs_verifier": role_conflict,
        "verifier_gold_with_no_selected_test": verifier_gold_with_no_selected_test,
        "duplicated_gold_path": duplicated_gold_path,
        "needs_rewrite_or_quarantine": bool(role_conflict or verifier_gold_with_no_selected_test or duplicated_gold_path),
        "candidate_excerpt": candidate_text[:300],
        "verifier_excerpt": verifier_text[:300],
    }


def metric(cards: list[dict[str, Any]]) -> dict[str, Any]:
    correct = sum(1 for card in cards if card.get("match") is True)
    return {"rows": len(cards), "correct": correct, "accuracy": (correct / len(cards)) if cards else None}


def simulate_policies(cards: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by = {(c["split"], c["row_id"], c["source"]): c for c in cards}
    row_keys = sorted({(c["split"], c["row_id"]) for c in cards if c["source"] == "encoder_option_retrieval"})

    def choose(split: str, row_id: str, policy: str) -> dict[str, Any]:
        base = by[(split, row_id, "encoder_option_retrieval")]
        task = str(base.get("task_type") or "")
        values = {str(x.get("value") or "") for x in base.get("option_rankings") or []}
        if policy == "base":
            return base
        if policy == "verifier_conditioned":
            if task == "verifier_outcome_semantic_transition":
                return by[(split, row_id, "encoder_option_retrieval_verifier_conditioned")]
            return base
        if policy == "evidence_role_map_on_bvf":
            if task == "evidence_citation" and {"candidate_change_surface", "verifier_and_test_constraint"} <= values:
                return by[(split, row_id, "encoder_option_retrieval_evidence_role_map")]
            return base
        if policy == "verifier_conditioned_plus_evidence_role_map_on_bvf":
            if task == "verifier_outcome_semantic_transition":
                return by[(split, row_id, "encoder_option_retrieval_verifier_conditioned")]
            if task == "evidence_citation" and {"candidate_change_surface", "verifier_and_test_constraint"} <= values:
                return by[(split, row_id, "encoder_option_retrieval_evidence_role_map")]
            return base
        raise ValueError(policy)

    out: dict[str, dict[str, Any]] = {}
    for policy in ["base", "verifier_conditioned", "evidence_role_map_on_bvf", "verifier_conditioned_plus_evidence_role_map_on_bvf"]:
        out[policy] = {}
        for split in ["clean_strict", "clean_validation", "reserved_residual"]:
            selected = [choose(s, row_id, policy) for s, row_id in row_keys if s == split]
            out[policy][split] = {
                **metric(selected),
                "changed_rows": sum(choose(s, row_id, policy).get("source") != "encoder_option_retrieval" for s, row_id in row_keys if s == split),
                "miss_row_ids": [card["row_id"] for card in selected if card.get("match") is False],
            }
    return out


def main() -> None:
    scorer_audit = load_json(SCORER_AUDIT)
    scorer_cards = load_jsonl(SCORER_CARDS)
    row_cards: list[dict[str, Any]] = []
    evidence_rows_by_split: dict[str, int] = {}
    for split, path in ROW_SOURCES.items():
        rows = [row for row in load_jsonl(path) if str(row.get("task_type") or "") == "evidence_citation"]
        evidence_rows_by_split[split] = len(rows)
        row_cards.extend(quality_card(split, row) for row in rows)

    policy_results = simulate_policies(scorer_cards)
    unsafe_quality = [card for card in row_cards if card["needs_rewrite_or_quarantine"]]
    duplicate_path_cards = [card for card in row_cards if card["duplicated_gold_path"]]
    conflict_cards = [card for card in row_cards if card["role_conflict_candidate_vs_verifier"]]

    base = policy_results["base"]
    verifier_conditioned = policy_results["verifier_conditioned"]
    evidence_role_map = policy_results["evidence_role_map_on_bvf"]
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "evidence_role_global_or_simple_gated_scorer_not_admissible",
        "source_artifacts": {
            "scorer_audit": rel(SCORER_AUDIT),
            "scorer_cards": rel(SCORER_CARDS),
            "row_sources": {split: rel(path) for split, path in ROW_SOURCES.items()},
        },
        "policy_results": policy_results,
        "policy_findings": {
            "verifier_conditioned_is_safe_for_clean_strict": verifier_conditioned["clean_strict"]["correct"] > base["clean_strict"]["correct"] and verifier_conditioned["clean_validation"]["correct"] >= base["clean_validation"]["correct"],
            "evidence_role_map_regresses_clean_strict": evidence_role_map["clean_strict"]["correct"] < base["clean_strict"]["correct"],
            "evidence_role_map_reserved_delta": evidence_role_map["reserved_residual"]["correct"] - base["reserved_residual"]["correct"],
            "no_safe_evidence_gate_from_current_scorers": True,
        },
        "quality_audit": {
            "evidence_rows_by_split": evidence_rows_by_split,
            "rows_audited": len(row_cards),
            "needs_rewrite_or_quarantine_rows": len(unsafe_quality),
            "role_conflict_candidate_vs_verifier_rows": len(conflict_cards),
            "duplicated_gold_path_rows": len(duplicate_path_cards),
            "gold_value_counts": dict(sorted(Counter(card["gold_value"] for card in row_cards).items())),
            "unsafe_by_split": dict(sorted(Counter(card["split"] for card in unsafe_quality).items())),
            "unsafe_by_language": dict(sorted(Counter(card["language_family"] for card in unsafe_quality).items())),
            "unsafe_row_ids": [card["row_id"] for card in unsafe_quality],
        },
        "interpretation": [
            "The verifier-conditioned scorer is a safe narrow improvement for verifier_outcome_semantic_transition, but it does not address evidence citation.",
            "The role-map evidence scorer helps verifier_and_test_constraint rows but systematically flips candidate_change_surface controls, so a simple target-free global or B-vs-F gate is not admissible.",
            "Several evidence rows have role-conflicted verifier ledger text or duplicated source spans across roles; these should be rewritten or quarantined before training a new evidence head.",
        ],
        "next_best_step": "Build stage11175 as a clean evidence-role rewrite/materialization package: remove duplicated role spans, make verifier/test evidence semantically distinct from candidate surface evidence, preserve candidate_change_surface positive controls, and only then train a direct semantic evidence candidate scorer.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "row_cards_jsonl": rel(ROW_CARDS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, payload)
    write_jsonl(ROW_CARDS_JSONL, row_cards)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
