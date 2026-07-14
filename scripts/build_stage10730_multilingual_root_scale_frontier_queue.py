#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACT_DIR = ROOT / "runs/local/artifacts/stage10730_multilingual_root_scale_frontier_queue"

STAGE10729 = ROOT / "runs/local/artifacts/stage10729_semantic_contrast_probe_audit/semantic_contrast_probe_audit.json"
STAGE10516_ROOTS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
STAGE10687_ROOTS = ROOT / "runs/local/artifacts/stage10687_reviewed_v27_plus_two_fresh_rust_support_package/reviewed_v27_plus_two_fresh_rust_root_manifest.jsonl"
STAGE10475 = ROOT / "runs/local/artifacts/stage10475_python_verifier_materialized_root_bundle_builder/python_verifier_materialized_root_bundle_builder.json"
STAGE10493 = ROOT / "runs/local/artifacts/stage10493_python_verifier_fresh_review_packet_builder/python_verifier_fresh_review_packet_builder.json"
STAGE10664 = ROOT / "runs/local/artifacts/stage10664_rust_materialization_inventory_refresh/rust_materialization_inventory_refresh.json"
STAGE10441 = ROOT / "runs/local/artifacts/stage10441_rust_evidence_citation_fresh_builder_request/rust_evidence_citation_fresh_builder_request.json"
STAGE10418 = ROOT / "runs/local/artifacts/stage10418_pure_web_verifier_anchor_gap_audit/pure_web_verifier_anchor_gap_audit.json"
STAGE10613 = ROOT / "runs/local/artifacts/stage10613_multilingual_root_scale_quality_contract/multilingual_root_scale_quality_contract.json"

PHASE_TARGETS = {
    "python": {"phase_1": 500, "phase_2": 2500, "phase_3": 10000, "phase_4": 40000},
    "rust": {"phase_1": 500, "phase_2": 2000, "phase_3": 10000, "phase_4": 20000},
    "c_cpp": {"phase_1": 500, "phase_2": 2000, "phase_3": 10000, "phase_4": 20000},
    "web_js_ts_html": {"phase_1": 500, "phase_2": 2000, "phase_3": 10000, "phase_4": 20000},
}

LANGUAGE_DISPLAY = {
    "python": "python",
    "rust": "rust",
    "c_cpp": "c_cpp",
    "web_js_ts_html": "web_js_ts_html",
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
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def root_lineage_key(root: dict[str, Any]) -> str:
    repo_id = str(root.get("repo_id") or "unknown")
    snapshot_id = str(root.get("snapshot_id") or root.get("root_id") or "unknown")
    return f"{repo_id}::{snapshot_id}"


def phase_gap(current: int, target: int) -> int:
    return max(target - current, 0)


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    stage10729 = load_json(STAGE10729)
    compiled_roots = load_jsonl(STAGE10516_ROOTS)
    reviewed_roots = load_jsonl(STAGE10687_ROOTS)
    stage10475 = load_json(STAGE10475)
    stage10493 = load_json(STAGE10493)
    stage10664 = load_json(STAGE10664)
    stage10441 = load_json(STAGE10441)
    stage10418 = load_json(STAGE10418)
    stage10613 = load_json(STAGE10613)

    compiled_by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in compiled_roots:
        lang = str(row.get("language_family") or "unknown")
        if lang in LANGUAGE_DISPLAY:
            compiled_by_lang[lang].append(row)

    compiled_repo_counts: dict[str, Counter[str]] = {}
    compiled_verifier_counts: dict[str, Counter[str]] = {}
    for lang, rows in compiled_by_lang.items():
        compiled_repo_counts[lang] = Counter(str(r.get("repo_family") or r.get("repo_id") or "unknown") for r in rows)
        compiled_verifier_counts[lang] = Counter(str(r.get("verifier_id") or "unknown") for r in rows)

    reviewed_by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in reviewed_roots:
        lang = str(row.get("language_family") or "unknown")
        if lang in LANGUAGE_DISPLAY:
            reviewed_by_lang[lang].append(row)

    reviewed_unique_lineage: dict[str, set[str]] = {}
    for lang, rows in reviewed_by_lang.items():
        reviewed_unique_lineage[lang] = {root_lineage_key(r) for r in rows}

    strict_language_breakdown = stage10729["strict_eval_result"]["language_breakdown"]

    targets: list[dict[str, Any]] = []
    summary_languages: dict[str, Any] = {}

    rust_builder_targets = stage10441.get("recommended_candidates") or []
    rust_builder_ids = [str(item.get("candidate_root_id")) for item in rust_builder_targets[:4]]

    for lang in ("python", "rust", "c_cpp", "web_js_ts_html"):
        compiled_count = len(compiled_by_lang.get(lang, []))
        reviewed_count = len(reviewed_unique_lineage.get(lang, set()))
        strict_acc = (strict_language_breakdown.get(lang) or {}).get("accuracy")
        phase_targets = PHASE_TARGETS[lang]
        top_repos = compiled_repo_counts.get(lang, Counter()).most_common(8)
        verifier_counts = dict(compiled_verifier_counts.get(lang, Counter()).most_common())

        notes: list[str] = []
        next_actions: list[str] = []
        lane_blocker = "none"

        if lang == "python":
            lane_blocker = "singleton verifier supply still too small"
            notes.extend(
                [
                    f"Current reviewed executable Python verifier supply is only {stage10475['metrics']['promotable_disjoint_root_count']} promotable disjoint roots.",
                    f"Fresh reviewed packet audit qualifies only {stage10493['summary']['immediately_qualified_targets']} richer verifier-disambiguation target immediately.",
                    "The current strict Python miss is still MirrorMind verifier B-vs-C.",
                ]
            )
            next_actions.extend(
                [
                    "Mine new singleton selected-test verifier roots from compiled Python PASS_TRACE_VERIFICATION_TARGETS lineage.",
                    "Prefer roots with 3+ plausible test candidates and no visible gold path before options.",
                    "Stop using same-surface Python support mixing as a promotion path.",
                ]
            )
        elif lang == "rust":
            lane_blocker = "fresh reviewed E-vs-F evidence-citation roots missing"
            notes.extend(
                [
                    f"Executable reviewed Rust support roots now total {stage10664['metrics']['refreshed_executable_support_root_count']}, but flash-attn remains support-only.",
                    f"Primary remaining Rust builder targets are {', '.join(rust_builder_ids)}.",
                    "The current strict Rust miss is still tokenizers evidence-citation E-vs-F.",
                ]
            )
            next_actions.extend(
                [
                    "Materialize linux::rust, candle-datasets, and candle-transformers into reviewed maintainer bundles with explicit E-vs-F citation geometry.",
                    "Require selected-test or verifier anchors and reject candidate_change_surface leakage.",
                    "Keep flash-attn as support/honesty data, not headline evidence.",
                ]
            )
        elif lang == "c_cpp":
            lane_blocker = "bundle materialization from bootstrap roots not yet done"
            notes.extend(
                [
                    f"C/C++ already has {compiled_count} compiled long-context roots, mostly PASS_TARGETED_TEST_SELECTION.",
                    "The main gap is not raw supply; it is converting bootstrap/retrieval roots into reviewed maintainer bundles with anti-cheat contracts.",
                    "Current strict C/C++ same-surface slice is already 6/6, so expansion should focus on honest heldout breadth.",
                ]
            )
            next_actions.extend(
                [
                    "Promote top C/C++ repo families into reviewed maintainer bundles: parametergolf, onnxruntime, cccl, cuEmbed, falco.",
                    "Prioritize roots with verifier anchors and diverse repo families over more parametergolf repeats.",
                    "Use C/C++ as the first language for large-scale root materialization from the long-context compiler.",
                ]
            )
        elif lang == "web_js_ts_html":
            lane_blocker = "pure-web verifier-anchored source family missing"
            notes.extend(
                [
                    f"Compiled web root count is only {compiled_count}, with repo concentration dominated by mem0.",
                    stage10418["claim_boundary"][2],
                    "Pure-web verifier-anchored source supply is still the main web scaling blocker.",
                ]
            )
            next_actions.extend(
                [
                    "Acquire or ingest a new non-overlapping pure-web repo family with selected tests.",
                    "Keep current web roots as support/stress only until a fresh verifier-anchored family exists.",
                    "Reject broad web headline claims without pure-web selected-test or verifier anchors.",
                ]
            )

        summary_languages[lang] = {
            "strict_accuracy": strict_acc,
            "compiled_root_count": compiled_count,
            "reviewed_root_count": reviewed_count,
            "phase_targets": phase_targets,
            "phase_gaps": {phase: phase_gap(compiled_count, target) for phase, target in phase_targets.items()},
            "top_compiled_repo_families": [{"repo_family": repo, "root_count": count} for repo, count in top_repos],
            "compiled_verifier_counts": verifier_counts,
            "lane_blocker": lane_blocker,
            "notes": notes,
            "next_actions": next_actions,
        }

        targets.append(
            {
                "language_family": lang,
                "lane_blocker": lane_blocker,
                "strict_accuracy": strict_acc,
                "compiled_root_count": compiled_count,
                "reviewed_root_count": reviewed_count,
                "phase_1_target": phase_targets["phase_1"],
                "phase_1_gap": phase_gap(compiled_count, phase_targets["phase_1"]),
                "phase_2_target": phase_targets["phase_2"],
                "phase_2_gap": phase_gap(compiled_count, phase_targets["phase_2"]),
                "phase_3_target": phase_targets["phase_3"],
                "phase_3_gap": phase_gap(compiled_count, phase_targets["phase_3"]),
                "phase_4_target": phase_targets["phase_4"],
                "phase_4_gap": phase_gap(compiled_count, phase_targets["phase_4"]),
                "top_repo_families": [repo for repo, _ in top_repos],
                "next_actions": next_actions,
            }
        )

    anti_cheat_contract = [
        "Root is the atomic split unit; same root_id or root_lineage_key must never cross train/validation/strict splits.",
        "No target path, gold test path, or gold evidence string may appear verbatim before the candidate set.",
        "Every promoted row must have visible supporting evidence for the gold option; reject truncated-evidence rows.",
        "Selected-test, verifier, and evidence-citation options must stay semantically stable under representation changes.",
        "Candidate order and label letters are presentation only; training and audits must operate on semantic candidate values.",
        "Every new root batch must be evaluated on fresh heldout roots and on the repaired v2.7 canary before promotion.",
    ]

    summary = {
        "stage": 10730,
        "stage_name": "stage10730_multilingual_root_scale_frontier_queue",
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "multilingual_root_scale_frontier_queue_ready",
        "claim_scope": [
            "Translate the current 22/24 plateau into a multilingual root-scaling queue tied to real supply, not abstract targets.",
            "Separate languages that are supply-limited from languages that are now materialization-limited.",
            "Make the user-requested long-range target explicit while keeping the next execution phases honest and anti-cheat constrained.",
        ],
        "headline_findings": [
            "Python and Rust are still promotion-blocked by fresh reviewed root supply, not by another same-surface support mix.",
            "C/C++ already has meaningful compiled long-context supply and should become the first large-scale materialization lane.",
            "Web remains the clearest source-acquisition blocker because pure-web verifier-anchored roots are still absent.",
            "The long-range target of 40k Python roots and 20k per other major language is valid, but the next honest milestone is root-admission and bundle materialization quality, not raw count inflation.",
        ],
        "current_frontier": {
            "strict_accuracy": stage10729["headline"]["current_strict_accuracy_stage10728"],
            "strict_miss_rows": stage10729["strict_eval_result"]["miss_summary"]["miss_row_ids"],
            "same_two_misses_remain": stage10729["residual_status"]["same_two_reviewed_v27_misses_remain"],
        },
        "scale_targets": PHASE_TARGETS,
        "language_lanes": summary_languages,
        "anti_cheat_contract": anti_cheat_contract,
        "next_best_steps": [
            "Build a C/C++ reviewed-bundle materialization packet from the compiled long-context roots because C/C++ already has the strongest near-term scale supply.",
            "Build a Python singleton-verifier mining packet that targets PASS_TRACE_VERIFICATION_TARGETS and selected-test ambiguity, not same-surface MirrorMind replay.",
            "Materialize at least one reviewed Rust builder target with true evidence-citation E-vs-F geometry before another Rust promotion attempt.",
            "Treat web as source acquisition first: ingest a new pure-web verifier-anchored family before spending more training cycles there.",
            "After those packets exist, compile a root-admission manifest v3 with explicit gold/silver/bronze tiers and root-level heldout splits.",
        ],
        "sources": {
            "stage10729_plateau_audit": rel(STAGE10729),
            "stage10516_compiled_roots": rel(STAGE10516_ROOTS),
            "stage10687_reviewed_root_manifest": rel(STAGE10687_ROOTS),
            "stage10475_python_materialized_inventory": rel(STAGE10475),
            "stage10493_python_review_packet": rel(STAGE10493),
            "stage10664_rust_inventory_refresh": rel(STAGE10664),
            "stage10441_rust_builder_request": rel(STAGE10441),
            "stage10418_pure_web_gap_audit": rel(STAGE10418),
            "stage10613_root_scale_quality_contract": rel(STAGE10613),
        },
        "output_files": {
            "summary_json": rel(ARTIFACT_DIR / "multilingual_root_scale_frontier_queue.json"),
            "targets_jsonl": rel(ARTIFACT_DIR / "multilingual_root_scale_frontier_targets.jsonl"),
        },
    }

    write_json(ARTIFACT_DIR / "multilingual_root_scale_frontier_queue.json", summary)
    write_jsonl(ARTIFACT_DIR / "multilingual_root_scale_frontier_targets.jsonl", targets)
    print(ARTIFACT_DIR / "multilingual_root_scale_frontier_queue.json")


if __name__ == "__main__":
    main()
