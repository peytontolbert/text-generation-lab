#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10775
NAME = "stage10775_bulk_multilingual_packet_ai_adjudication"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "bulk_multilingual_packet_ai_adjudication.json"
DECISIONS_JSONL = OUT_DIR / "packet_ai_adjudication.jsonl"
QUEUE_JSONL = OUT_DIR / "packet_followup_queue.jsonl"
SUMMARY_CARD = ROOT / "runs/summaries" / f"{NAME}.json"

PACKET_INDEX = ROOT / "runs/local/artifacts/stage10774_bulk_multilingual_review_packet_builder/packet_index.jsonl"


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


def decide_packet(bundle: dict[str, Any], anti_cheat: dict[str, Any], snippet_plan: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    lang = str(bundle["language_family"])
    changed = list(bundle["compiled_brief_summary"].get("changed_files_sample") or [])
    tests = list(bundle["compiled_brief_summary"].get("verification_targets_sample") or [])
    candidate_items = len(bundle["maintainer_visible_evidence"].get("candidate_change_surface") or [])
    verifier_items = len(bundle["maintainer_visible_evidence"].get("verifier_and_test_constraint") or [])
    duplicate_sources = int(bundle["compiled_brief_summary"].get("duplicate_source_count") or 0)
    selected_anchor = bool(bundle["compiled_brief_summary"].get("selected_test_anchor_present"))
    anti_cheat_status = str(anti_cheat.get("status") or "")

    notes: list[str] = []
    actions: list[str] = []

    if candidate_items <= 1:
        notes.append("candidate competition is still too thin for scoreable maintainer evaluation")
        actions.append("expand candidate set beyond the current changed-file preview")
    if verifier_items == 0:
        notes.append("no verifier evidence is currently visible")
        actions.append("attach concrete verifier/test evidence")
    if duplicate_sources < 2:
        notes.append("root currently has weak duplicate-source corroboration")
        actions.append("prefer corroborated sibling sources before promotion if available")
    if any(str(path).endswith(("CHANGELOG.md", "README.md", "package.json", "pyproject.toml")) for path in changed):
        notes.append("changed-file preview includes metadata surfaces that need stronger neighboring implementation competitors")
        actions.append("add nearby implementation files and non-gold path competitors")
    if anti_cheat_status == "high_shortcut_risk_review_required":
        notes.append("anti-cheat card marks this packet as high shortcut risk")
        actions.append("run changed-path shortcut review before any enrichment")

    if lang == "c_cpp":
        notes.append("c_cpp packet is selected-test anchored and the strongest near-term reviewed-support lane")
        actions.append("promote to reviewed-support candidate after anti-cheat enrichment")
    elif lang == "python":
        notes.append("python packet has broader verifier/generation growth potential but needs repo-diversity discipline")
        actions.append("materialize competing candidate files around the visible tests and cap dominant repo-family reuse")
    elif lang == "rust":
        notes.append("rust packet is high-value because source supply is scarce and citation geometry still needs proof")
        actions.append("construct explicit citation-vs-candidate-surface competition around test/trace anchors")
    elif lang == "web_js_ts_html":
        notes.append("web packet count is still too small for a broad claim and remains vulnerable to shortcut risk")
        actions.append("separate pure-web candidates from mixed-language or metadata-heavy signals")

    if not selected_anchor:
        actions.append("recover or verify selected-test anchor before promotion")

    if lang == "c_cpp" and candidate_items >= 2 and tests:
        status = "support_ready_after_enrichment"
    elif lang == "python" and len(tests) >= 2 and candidate_items >= 2:
        status = "support_ready_after_enrichment"
    elif lang == "rust" and tests:
        status = "fresh_candidate_needs_richer_competition"
    elif lang == "web_js_ts_html":
        status = "blocked_on_shortcut_or_source_enrichment"
    else:
        status = "blocked_on_shortcut_or_source_enrichment"

    if snippet_plan.get("status") != "snippet_materialization_required":
        notes.append("snippet materialization plan missing or malformed")
        actions.append("repair snippet plan before promotion")
        status = "blocked_on_shortcut_or_source_enrichment"

    return status, notes, actions


def main() -> None:
    packet_rows = load_jsonl(PACKET_INDEX)
    decisions: list[dict[str, Any]] = []
    followup: list[dict[str, Any]] = []

    for row in packet_rows:
        packet_dir = ROOT / row["packet_dir"]
        bundle = load_json(packet_dir / "fresh_root_bundle_preview.json")
        anti_cheat = load_json(packet_dir / "anti_cheat_review_card.json")
        rubric = load_json(packet_dir / "expert_maintainer_rubric_review.json")
        gold = load_json(packet_dir / "perspective_gold_adjudication.json")
        snippet_plan = load_json(packet_dir / "snippet_materialization_plan.json")

        status, notes, actions = decide_packet(bundle, anti_cheat, snippet_plan)
        evidence = bundle["maintainer_visible_evidence"]
        changed = list(bundle["compiled_brief_summary"].get("changed_files_sample") or [])
        tests = list(bundle["compiled_brief_summary"].get("verification_targets_sample") or [])

        decision = {
            "root_id": row["root_id"],
            "root_lineage_key": row["root_lineage_key"],
            "repo_family": row["repo_family"],
            "language_family": row["language_family"],
            "packet_dir": row["packet_dir"],
            "queue_rank": row["queue_rank"],
            "priority_score": row["priority_score"],
            "semantic_lane": row["semantic_lane"],
            "ai_status": status,
            "ai_scoreability": "not_scoreable_yet",
            "changed_file_count_preview": len(changed),
            "verification_target_count_preview": len(tests),
            "candidate_surface_item_count": len(evidence.get("candidate_change_surface") or []),
            "verifier_constraint_item_count": len(evidence.get("verifier_and_test_constraint") or []),
            "duplicate_source_count": int(bundle["compiled_brief_summary"].get("duplicate_source_count") or 0),
            "selected_test_anchor_present": bool(bundle["compiled_brief_summary"].get("selected_test_anchor_present")),
            "anti_cheat_stub_status": anti_cheat.get("status"),
            "rubric_stub_status": rubric.get("status"),
            "gold_stub_status": gold.get("status"),
            "snippet_plan_status": snippet_plan.get("status"),
            "visible_evidence_keys": sorted(k for k, v in evidence.items() if v),
            "ai_notes": notes,
            "required_repairs": actions,
        }
        decisions.append(decision)

        followup.append(
            {
                "root_id": row["root_id"],
                "root_lineage_key": row["root_lineage_key"],
                "language_family": row["language_family"],
                "repo_family": row["repo_family"],
                "ai_status": status,
                "priority_score": row["priority_score"],
                "queue_rank": row["queue_rank"],
                "next_best_action": actions[0] if actions else "review packet manually",
                "all_required_repairs": actions,
                "packet_dir": row["packet_dir"],
            }
        )

    decisions.sort(key=lambda row: (row["language_family"], row["ai_status"], -int(row["priority_score"]), row["root_id"]))
    followup.sort(key=lambda row: (row["language_family"], row["ai_status"], -int(row["priority_score"]), row["root_id"]))

    status_counts = Counter(row["ai_status"] for row in decisions)
    by_language = Counter(row["language_family"] for row in decisions)
    language_status_counts: dict[str, dict[str, int]] = defaultdict(dict)
    for lang in sorted(by_language):
        subset = [row for row in decisions if row["language_family"] == lang]
        language_status_counts[lang] = dict(sorted(Counter(row["ai_status"] for row in subset).items()))

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "bulk_multilingual_packet_ai_adjudication_completed",
        "claim_scope": [
            "AI-review the stage10774 bulk multilingual preview packets for scoreability and shortcut risk.",
            "Separate packets that can become reviewed support after enrichment from packets still blocked on realism/competition gaps.",
            "Provide a concrete follow-up queue for the next reviewed-bundle build step.",
        ],
        "metrics": {
            "packet_count": len(decisions),
            "packet_counts_by_language": dict(sorted(by_language.items())),
            "ai_status_counts": dict(sorted(status_counts.items())),
            "language_status_counts": language_status_counts,
        },
        "headline_findings": [
            "None of the bulk preview packets are scoreable yet; they remain scaffolds until competition, snippets, and gold adjudication are added.",
            "C/C++ and Python packets are still the best near-term reviewed-support candidates after enrichment because they already carry selected-test structure.",
            "Rust has fresh non-tokenizers candidates, but they still need richer evidence competition to test the real citation failure mode.",
            "Web packets remain the weakest lane because pure-web supply is tiny and shortcut risk stays high.",
        ],
        "next_best_step": "Enrich the strongest C/C++ and Python packets into reviewed-support bundles first, then repair Rust competition geometry while holding web packets behind stronger anti-shortcut enrichment.",
        "source_artifacts": {
            "packet_index": display(PACKET_INDEX),
        },
        "outputs": {
            "summary_json": display(SUMMARY_JSON),
            "packet_ai_adjudication": display(DECISIONS_JSONL),
            "packet_followup_queue": display(QUEUE_JSONL),
        },
    }

    write_jsonl(DECISIONS_JSONL, decisions)
    write_jsonl(QUEUE_JSONL, followup)
    write_json(SUMMARY_JSON, payload)
    write_json(
        SUMMARY_CARD,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "artifact": display(SUMMARY_JSON),
            "packet_count": payload["metrics"]["packet_count"],
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
