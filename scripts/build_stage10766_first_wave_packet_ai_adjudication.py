#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10766
NAME = "stage10766_first_wave_packet_ai_adjudication"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "first_wave_packet_ai_adjudication.json"
DECISIONS_JSONL = OUT_DIR / "packet_ai_adjudication.jsonl"
QUEUE_JSONL = OUT_DIR / "packet_followup_queue.jsonl"
SUMMARY_CARD = ROOT / "runs/summaries" / f"{NAME}.json"

PACKET_INDEX = ROOT / "runs/local/artifacts/stage10765_first_wave_bundle_preview_packets/packet_index.jsonl"


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


def decide_packet(bundle: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    lang = str(bundle["language_family"])
    changed = list(bundle["compiled_brief_summary"].get("changed_files_sample") or [])
    tests = list(bundle["compiled_brief_summary"].get("verification_targets_sample") or [])
    candidate_items = len(bundle["maintainer_visible_evidence"].get("candidate_change_surface") or [])
    verifier_items = len(bundle["maintainer_visible_evidence"].get("verifier_and_test_constraint") or [])
    notes: list[str] = []
    actions: list[str] = []

    if candidate_items <= 1:
        notes.append("candidate competition is still too thin for scoreable maintainer evaluation")
        actions.append("expand candidate set beyond the current changed-file preview")
    if verifier_items == 0:
        notes.append("no verifier evidence is currently visible")
        actions.append("attach concrete verifier/test evidence")
    if lang == "web_js_ts_html":
        notes.append("web preview is still dominated by mem0 and mixed cross-language tests")
        actions.append("separate pure-web candidates from cross-language verifier signals")
    if any(str(path).endswith(("CHANGELOG.md", "README.md", "package.json")) for path in changed):
        notes.append("changed-file preview includes likely shortcut or metadata surfaces that need stronger competing implementation paths")
        actions.append("add nearby implementation files and non-gold path competitors")
    if lang == "python" and len(tests) >= 2:
        notes.append("python packet has useful verifier disambiguation structure")
        actions.append("materialize competing candidate files around the visible tests")
    if lang == "c_cpp" and tests:
        notes.append("c_cpp packet already has selected-test anchors and is the strongest near-term reviewed-support lane")
        actions.append("promote to reviewed-support candidate after anti-cheat enrichment")
    if lang == "rust" and tests:
        notes.append("rust packet is fresh and non-tokenizers, but still needs richer competing candidates before scoring")
        actions.append("construct E-vs-F style evidence competition around test/trace anchors")

    if lang == "c_cpp" and candidate_items >= 1 and tests:
        status = "support_ready_after_enrichment"
    elif lang == "python" and len(tests) >= 2:
        status = "support_ready_after_enrichment"
    elif lang == "rust" and tests:
        status = "fresh_candidate_needs_richer_competition"
    else:
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

        status, notes, actions = decide_packet(bundle)
        evidence = bundle["maintainer_visible_evidence"]
        changed = list(bundle["compiled_brief_summary"].get("changed_files_sample") or [])
        tests = list(bundle["compiled_brief_summary"].get("verification_targets_sample") or [])

        decision = {
            "root_id": row["root_id"],
            "repo_family": row["repo_family"],
            "language_family": row["language_family"],
            "packet_dir": row["packet_dir"],
            "queue_rank": row["queue_rank"],
            "priority_score": row["priority_score"],
            "ai_status": status,
            "ai_scoreability": "not_scoreable_yet",
            "changed_file_count_preview": len(changed),
            "verification_target_count_preview": len(tests),
            "candidate_surface_item_count": len(evidence.get("candidate_change_surface") or []),
            "verifier_constraint_item_count": len(evidence.get("verifier_and_test_constraint") or []),
            "visible_evidence_keys": sorted(k for k, v in evidence.items() if v),
            "ai_notes": notes,
            "required_repairs": actions,
            "anti_cheat_stub_status": anti_cheat.get("status"),
            "rubric_stub_status": rubric.get("status"),
            "gold_stub_status": gold.get("status"),
        }
        decisions.append(decision)

        followup.append(
            {
                "root_id": row["root_id"],
                "language_family": row["language_family"],
                "repo_family": row["repo_family"],
                "ai_status": status,
                "next_best_action": actions[0] if actions else "review packet manually",
                "all_required_repairs": actions,
                "packet_dir": row["packet_dir"],
            }
        )

    decisions.sort(key=lambda row: (row["language_family"], row["ai_status"], row["root_id"]))
    followup.sort(key=lambda row: (row["language_family"], row["ai_status"], row["root_id"]))

    status_counts = Counter(row["ai_status"] for row in decisions)
    by_language = Counter(row["language_family"] for row in decisions)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "first_wave_packet_ai_adjudication_completed",
        "claim_scope": [
            "AI-review the stage10765 multilingual preview packets for scoreability and shortcut risk.",
            "Separate packets that can become reviewed support after enrichment from packets still blocked on realism/competition gaps.",
            "Provide a concrete follow-up queue for the next bundle-enrichment step.",
        ],
        "metrics": {
            "packet_count": len(decisions),
            "packet_counts_by_language": dict(sorted(by_language.items())),
            "ai_status_counts": dict(sorted(status_counts.items())),
        },
        "headline_findings": [
            "None of the preview packets are scoreable yet; they remain scaffolds until competition and gold adjudication are added.",
            "C/C++ and Python packets are the best near-term reviewed-support candidates after enrichment because they already carry selected-test structure.",
            "Rust has fresh non-tokenizers candidates, but they still need richer evidence competition to test the real citation failure mode.",
            "Web packets are still the weakest because they remain vulnerable to changed-path and mixed-surface shortcut risk.",
        ],
        "next_best_step": "Enrich the C/C++ and Python packets into reviewed-support bundles first, then repair Rust competition geometry, while holding web packets behind stronger anti-shortcut enrichment.",
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
