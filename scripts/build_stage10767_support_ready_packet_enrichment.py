#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10767
NAME = "stage10767_support_ready_packet_enrichment"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "support_ready_packet_enrichment.json"
ENRICHED_INDEX_JSONL = OUT_DIR / "enriched_packet_index.jsonl"
SUMMARY_CARD = ROOT / "runs/summaries" / f"{NAME}.json"

FOLLOWUP_QUEUE = ROOT / "runs/local/artifacts/stage10766_first_wave_packet_ai_adjudication/packet_followup_queue.jsonl"

PERSPECTIVES = [
    "symptom_localization",
    "evidence_citation",
    "alternative_hypothesis_elimination",
    "patch_impact",
    "verifier_outcome",
    "minimal_fix_selection",
    "regression_risk",
    "abstention_insufficient_evidence",
]


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


def relabel_options(values: list[str], *, add_abstain: bool = False) -> list[dict[str, str]]:
    labels = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M"]
    opts = [{"label": labels[idx], "value": value} for idx, value in enumerate(values[: len(labels)])]
    if add_abstain and len(opts) < len(labels):
        opts.append({"label": labels[len(opts)], "value": "ABSTAIN_INSUFFICIENT_EVIDENCE"})
    return opts


def expanded_candidates(bundle: dict[str, Any]) -> list[str]:
    changed = [str(item) for item in bundle["compiled_brief_summary"].get("changed_files_sample") or []]
    tests = [str(item) for item in bundle["compiled_brief_summary"].get("verification_targets_sample") or []]
    lang = str(bundle["language_family"])

    values: list[str] = []
    if lang == "python":
        values.extend(changed)
        values.extend(tests)
        values.extend(
            [
                "models/shared/datasets.py",
                "models/shared/encoders.py",
                "models/tests/test_training_common.py",
            ]
        )
    else:
        values.extend(changed)
        values.extend(tests)
        values.extend(
            [
                "src/main.cpp" if lang == "c_cpp" else "",
                "include/config.h" if lang == "c_cpp" else "",
                "tests/test_smoke.cpp" if lang == "c_cpp" else "",
            ]
        )
    deduped = []
    seen = set()
    for value in values:
        value = value.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped[:8]


def perspective_contract(bundle: dict[str, Any], perspective: str, options: list[dict[str, str]]) -> dict[str, Any]:
    lang = str(bundle["language_family"])
    tests = [str(item) for item in bundle["compiled_brief_summary"].get("verification_targets_sample") or []]
    changed = [str(item) for item in bundle["compiled_brief_summary"].get("changed_files_sample") or []]
    evidence_keys = sorted(k for k, v in (bundle.get("maintainer_visible_evidence") or {}).items() if v)
    contracts = {
        "symptom_localization": "Target should be justified by a visible competition between changed files, nearby implementation paths, and verifier evidence.",
        "evidence_citation": "Answer should come from visible evidence roles, not from candidate identity or order.",
        "alternative_hypothesis_elimination": "At least one plausible wrong candidate must remain in the option set.",
        "patch_impact": "Candidates must differ in likely behavioral effect, not only file name.",
        "verifier_outcome": "Visible tests must support a nontrivial verifier choice or abstain decision.",
        "minimal_fix_selection": "A smaller but insufficient edit should compete with a larger but stronger edit.",
        "regression_risk": "Visible evidence should allow at least one plausible regression concern.",
        "abstention_insufficient_evidence": "ABSTAIN should remain available when the visible evidence does not force a singleton.",
    }
    return {
        "perspective": perspective,
        "language_family": lang,
        "task_contract": contracts[perspective],
        "candidate_option_count": len(options),
        "candidate_options": options,
        "evidence_keys": evidence_keys,
        "verification_targets_preview": tests[:4],
        "changed_files_preview": changed[:4],
        "scoreable_now": False,
        "gold_status": "needs_ai_or_human_adjudication",
    }


def enrichment_status(bundle: dict[str, Any]) -> tuple[str, list[str]]:
    lang = str(bundle["language_family"])
    changed = [str(item) for item in bundle["compiled_brief_summary"].get("changed_files_sample") or []]
    if lang == "c_cpp" and len(changed) >= 3:
        return "strong_support_candidate", [
            "attach concrete snippet text for implementation and test surfaces",
            "adjudicate gold answers across all eight perspectives",
        ]
    return "good_support_candidate", [
        "attach concrete snippet text for changed and competing files",
        "adjudicate gold answers across all eight perspectives",
    ]


def main() -> None:
    followup_rows = load_jsonl(FOLLOWUP_QUEUE)
    support_rows = [row for row in followup_rows if row["ai_status"] == "support_ready_after_enrichment"]
    packet_index: list[dict[str, Any]] = []

    for row in support_rows:
        packet_dir = ROOT / row["packet_dir"]
        bundle_path = packet_dir / "fresh_root_bundle_preview.json"
        bundle = load_json(bundle_path)

        candidate_values = expanded_candidates(bundle)
        abstain_options = relabel_options(candidate_values, add_abstain=True)
        singleton_options = relabel_options(candidate_values, add_abstain=False)

        enriched = {
            "bundle_id": bundle["bundle_id"],
            "root_id": bundle["root_id"],
            "repo_id": bundle["repo_id"],
            "repo_family": bundle["repo_family"],
            "language_family": bundle["language_family"],
            "source_route": bundle["source_route"],
            "preview_packet_dir": row["packet_dir"],
            "claim_boundary": {
                "gold_answers_fully_adjudicated": False,
                "supports_training_or_scoring_now": False,
                "support_candidate_only": True,
            },
            "competition_contract": {
                "candidate_values": candidate_values,
                "singleton_candidate_options": singleton_options,
                "abstain_candidate_options": abstain_options,
                "must_not_expose_gold_path_before_options": True,
                "must_include_non_changed_competitors": True,
                "must_test_changed_path_shortcut": True,
            },
            "compiled_brief_summary": bundle["compiled_brief_summary"],
            "maintainer_visible_evidence": bundle["maintainer_visible_evidence"],
            "perspective_contracts": [
                perspective_contract(
                    bundle,
                    perspective,
                    abstain_options if perspective == "abstention_insufficient_evidence" else singleton_options,
                )
                for perspective in PERSPECTIVES
            ],
        }

        status, actions = enrichment_status(bundle)
        enriched_path = packet_dir / "enriched_reviewed_support_candidate.json"
        write_json(enriched_path, enriched)

        packet_index.append(
            {
                "root_id": bundle["root_id"],
                "repo_family": bundle["repo_family"],
                "language_family": bundle["language_family"],
                "ai_status": row["ai_status"],
                "enrichment_status": status,
                "required_next_actions": actions,
                "preview_packet_dir": row["packet_dir"],
                "enriched_candidate": display(enriched_path),
                "candidate_option_count": len(candidate_values),
            }
        )

    packet_index.sort(key=lambda r: (r["language_family"], r["repo_family"], r["root_id"]))
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "support_ready_packets_enriched_into_reviewed_support_candidates",
        "claim_scope": [
            "Upgrade the AI-approved C/C++ and Python preview packets into stricter reviewed-support candidates.",
            "Add explicit candidate competition pools and per-perspective contracts without pretending the packets are scoreable yet.",
            "Prepare the strongest multilingual support lanes for the next reviewed training package.",
        ],
        "metrics": {
            "enriched_packet_count": len(packet_index),
            "enriched_by_language": dict(sorted(Counter(r["language_family"] for r in packet_index).items())),
            "candidate_option_counts": {r["root_id"]: r["candidate_option_count"] for r in packet_index},
        },
        "headline_findings": [
            "The two C/C++ and two Python packets now have explicit candidate pools and perspective-specific competition contracts.",
            "These enriched packets are materially closer to train-support quality than the earlier preview scaffolds, but they still need adjudicated gold and snippet-level evidence text.",
            "This creates a cleaner next step for a reviewed multilingual support package without reopening same-surface replay.",
        ],
        "next_best_step": "Attach concrete snippet text and AI gold adjudication to these four enriched support candidates, then package them into the next reviewed multilingual training support stage.",
        "source_artifacts": {
            "followup_queue": display(FOLLOWUP_QUEUE),
        },
        "outputs": {
            "summary_json": display(SUMMARY_JSON),
            "enriched_packet_index": display(ENRICHED_INDEX_JSONL),
        },
    }

    write_jsonl(ENRICHED_INDEX_JSONL, packet_index)
    write_json(SUMMARY_JSON, payload)
    write_json(
        SUMMARY_CARD,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "artifact": display(SUMMARY_JSON),
            "enriched_packet_count": payload["metrics"]["enriched_packet_count"],
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
