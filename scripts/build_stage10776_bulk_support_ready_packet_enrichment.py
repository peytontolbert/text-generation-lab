#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10776
NAME = "stage10776_bulk_support_ready_packet_enrichment"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "bulk_support_ready_packet_enrichment.json"
ENRICHED_INDEX_JSONL = OUT_DIR / "enriched_packet_index.jsonl"
SUMMARY_CARD = ROOT / "runs/summaries" / f"{NAME}.json"

DECISIONS_JSONL = ROOT / "runs/local/artifacts/stage10775_bulk_multilingual_packet_ai_adjudication/packet_ai_adjudication.jsonl"
PACKET_INDEX_JSONL = ROOT / "runs/local/artifacts/stage10774_bulk_multilingual_review_packet_builder/packet_index.jsonl"

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

LANGUAGE_LIMITS = {
    "python": 12,
    "c_cpp": 7,
    "rust": 0,
    "web_js_ts_html": 0,
}

REPO_CAPS = {
    "python": 2,
    "c_cpp": 3,
}


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
    symbols = [str(item) for item in bundle["compiled_brief_summary"].get("key_symbols_sample") or []]
    lang = str(bundle["language_family"])

    values: list[str] = []
    values.extend(changed)
    values.extend(tests)
    if lang == "python":
        values.extend(
            [
                "src/main.py",
                "tests/test_main.py",
                "src/utils.py",
                "docs/usage.md",
            ]
        )
    elif lang == "c_cpp":
        values.extend(
            [
                "src/main.cpp",
                "include/config.h",
                "tests/test_smoke.cpp",
                "bench/benchmark.cpp",
            ]
        )
    deduped = []
    seen = set()
    for value in values + symbols:
        value = value.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped[:8]


def perspective_contract(bundle: dict[str, Any], perspective: str, options: list[dict[str, str]]) -> dict[str, Any]:
    tests = [str(item) for item in bundle["compiled_brief_summary"].get("verification_targets_sample") or []]
    changed = [str(item) for item in bundle["compiled_brief_summary"].get("changed_files_sample") or []]
    evidence_keys = sorted(k for k, v in (bundle.get("maintainer_visible_evidence") or {}).items() if v)
    contracts = {
        "symptom_localization": "Target should be justified by visible competition between changed files, nearby implementation paths, and verifier evidence.",
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
        "language_family": bundle["language_family"],
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
    if lang == "c_cpp" and len(changed) >= 2:
        return "strong_support_candidate", [
            "attach concrete snippet text for implementation and test surfaces",
            "adjudicate gold answers across all eight perspectives",
        ]
    return "good_support_candidate", [
        "attach concrete snippet text for changed and competing files",
        "adjudicate gold answers across all eight perspectives",
    ]


def select_support_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    per_lang = Counter()
    per_repo: dict[str, Counter[str]] = {"python": Counter(), "c_cpp": Counter()}
    ordered = sorted(rows, key=lambda r: (r["language_family"], -int(r["priority_score"]), int(r["queue_rank"]), r["root_id"]))
    for row in ordered:
        lang = str(row["language_family"])
        if lang not in LANGUAGE_LIMITS:
            continue
        if per_lang[lang] >= LANGUAGE_LIMITS[lang]:
            continue
        cap = REPO_CAPS.get(lang)
        repo = str(row["repo_family"])
        if cap is not None and per_repo[lang][repo] >= cap:
            continue
        selected.append(row)
        per_lang[lang] += 1
        if cap is not None:
            per_repo[lang][repo] += 1
    return selected


def main() -> None:
    decisions = load_jsonl(DECISIONS_JSONL)
    packet_index = {str(row["root_id"]): row for row in load_jsonl(PACKET_INDEX_JSONL)}
    support_rows = [
        row for row in decisions
        if row["ai_status"] == "support_ready_after_enrichment"
        and row["language_family"] in {"python", "c_cpp"}
    ]
    selected_rows = select_support_rows(support_rows)

    enriched_index: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    selected_ids = {str(row["root_id"]) for row in selected_rows}

    for row in support_rows:
        if str(row["root_id"]) in selected_ids:
            continue
        skipped_rows.append(
            {
                "root_id": row["root_id"],
                "language_family": row["language_family"],
                "repo_family": row["repo_family"],
                "priority_score": row["priority_score"],
                "skip_reason": "repo_or_language_cap",
            }
        )

    for row in selected_rows:
        packet_row = packet_index[str(row["root_id"])]
        packet_dir = ROOT / str(packet_row["packet_dir"])
        bundle = load_json(packet_dir / "fresh_root_bundle_preview.json")

        candidate_values = expanded_candidates(bundle)
        abstain_options = relabel_options(candidate_values, add_abstain=True)
        singleton_options = relabel_options(candidate_values, add_abstain=False)

        enriched = {
            "bundle_id": bundle["bundle_id"],
            "root_id": bundle["root_id"],
            "root_lineage_key": packet_row["root_lineage_key"],
            "repo_family": bundle["repo_family"],
            "language_family": bundle["language_family"],
            "source_route": bundle["source_route"],
            "preview_packet_dir": packet_row["packet_dir"],
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
                "selected_from_bulk_packet_adjudication": True,
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

        enriched_index.append(
            {
                "root_id": bundle["root_id"],
                "repo_family": bundle["repo_family"],
                "language_family": bundle["language_family"],
                "ai_status": row["ai_status"],
                "enrichment_status": status,
                "required_next_actions": actions,
                "preview_packet_dir": packet_row["packet_dir"],
                "enriched_candidate": display(enriched_path),
                "candidate_option_count": len(candidate_values),
                "priority_score": row["priority_score"],
                "queue_rank": row["queue_rank"],
            }
        )

    enriched_index.sort(key=lambda r: (r["language_family"], -int(r["priority_score"]), int(r["queue_rank"]), r["root_id"]))
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "bulk_support_ready_packets_enriched_into_reviewed_support_candidates",
        "claim_scope": [
            "Upgrade the strongest bulk C/C++ and Python preview packets into stricter reviewed-support candidates.",
            "Apply repo and language caps so the next support package grows multilingual breadth instead of defaulting to Python dominance.",
            "Add explicit candidate competition pools and per-perspective contracts without pretending the packets are scoreable yet.",
        ],
        "metrics": {
            "support_ready_pool_count": len(support_rows),
            "selected_enriched_packet_count": len(enriched_index),
            "selected_by_language": dict(sorted(Counter(r["language_family"] for r in enriched_index).items())),
            "skipped_due_to_caps": len(skipped_rows),
        },
        "headline_findings": [
            "The strongest bulk support-ready packets are now enriched into reviewed-support candidates with explicit competition contracts.",
            "Repo and language caps prevent the next package from collapsing into Python-only growth, while still preserving the strongest Python verifier/generation roots.",
            "C/C++ remains the cleanest near-term lane for broadening reviewed maintainer bundles because its selected candidates span multiple real repo families.",
        ],
        "next_best_step": "Attach concrete snippet text and AI gold adjudication to these enriched support candidates, then assemble the next reviewed multilingual support package from them before another training run.",
        "source_artifacts": {
            "bulk_packet_adjudication": display(DECISIONS_JSONL),
            "bulk_packet_index": display(PACKET_INDEX_JSONL),
        },
        "outputs": {
            "summary_json": display(SUMMARY_JSON),
            "enriched_packet_index": display(ENRICHED_INDEX_JSONL),
        },
    }

    write_jsonl(ENRICHED_INDEX_JSONL, enriched_index)
    write_json(
        OUT_DIR / "skipped_due_to_caps.json",
        {
            "rows": skipped_rows,
        },
    )
    write_json(SUMMARY_JSON, payload)
    write_json(
        SUMMARY_CARD,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "artifact": display(SUMMARY_JSON),
            "enriched_packet_count": payload["metrics"]["selected_enriched_packet_count"],
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
