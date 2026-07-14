#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11013
NAME = "stage11013_fresh_root_build_set"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_root_build_set.json"
ROWS_JSONL = OUT_DIR / "fresh_root_build_rows.jsonl"

BLOCKED_JSON = ARTIFACTS / "stage10409_review_blocked_successor_inventory" / "review_blocked_successor_inventory.json"
BLOCKED_ROWS = ARTIFACTS / "stage10409_review_blocked_successor_inventory" / "review_blocked_successor_inventory_rows.jsonl"
SALVAGE_JSON = ARTIFACTS / "stage10410_ai_adjudicated_successor_salvage" / "ai_adjudicated_successor_salvage.json"
ATLAS_JSON = ARTIFACTS / "stage10417_multilingual_reviewed_scaling_atlas" / "multilingual_reviewed_scaling_atlas.json"
WEB_GAP_JSON = ARTIFACTS / "stage10418_pure_web_verifier_anchor_gap_audit" / "pure_web_verifier_anchor_gap_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counter = Counter(str(row.get(key) or "missing") for row in rows)
    return dict(sorted(counter.items()))


def priority_bucket(row: dict[str, Any]) -> str:
    lang = str(row.get("language_family") or "")
    if lang == "python":
        return "python_fresh_successor_salvage"
    if lang == "c_cpp":
        return "cpp_successor_salvage"
    if lang == "web_js_ts_html":
        return "web_successor_support_only"
    return "other"


def main() -> None:
    blocked = load_json(BLOCKED_JSON)
    blocked_rows = load_jsonl(BLOCKED_ROWS)
    salvage = load_json(SALVAGE_JSON)
    atlas = load_json(ATLAS_JSON)
    web_gap = load_json(WEB_GAP_JSON)

    selected_rows: list[dict[str, Any]] = []

    # High-priority Python successor salvage: selected-test anchored, non-frontier.
    python_candidates = [
        row
        for row in blocked_rows
        if str(row.get("language_family") or "") == "python"
        and str(row.get("repo_id") or "") == "agentkernel"
        and str(row.get("successor_template") or "") == "python_implementation_vs_config"
        and int(row.get("selected_tests_count") or 0) >= 4
    ]
    python_candidates = sorted(
        python_candidates,
        key=lambda row: (
            -int(row.get("priority_score") or 0),
            int(row.get("shortcut_risk_score") or 0),
            -int(row.get("selected_tests_count") or 0),
            str(row.get("row_id") or ""),
        ),
    )[:8]
    for row in python_candidates:
        selected_rows.append(
            {
                "build_lane": "python_fresh_successor_salvage",
                "priority": "high",
                "language_family": "python",
                "repo_id": row.get("repo_id"),
                "row_id": row.get("row_id"),
                "review_packet_dir": None,
                "source_kind": "review_blocked_successor",
                "successor_template": row.get("successor_template"),
                "selected_tests_count": row.get("selected_tests_count"),
                "shortcut_risk_score": row.get("shortcut_risk_score"),
                "candidate_surface_pair": row.get("candidate_surface_pair"),
                "target_contract": "Convert into fresh verifier-anchored implementation-vs-config maintainer bundles or explicit abstention rows.",
                "required_gates": [
                    "prompt_target_leak_rows == 0",
                    "selected tests remain visible but do not reveal the target surface directly",
                    "same root does not cross train/eval splits",
                    "repair or abstain decision must be human-judgeable from visible evidence",
                ],
            }
        )

    # C++ salvage remains weak, but keep the best available non-frontier rows explicit.
    cpp_candidates = [
        row
        for row in blocked_rows
        if str(row.get("language_family") or "") == "c_cpp"
        and str(row.get("repo_id") or "") == "parametergolf"
    ]
    cpp_candidates = sorted(
        cpp_candidates,
        key=lambda row: (
            -int(row.get("selected_tests_count") or 0),
            int(row.get("shortcut_risk_score") or 0),
            -int(row.get("priority_score") or 0),
            str(row.get("row_id") or ""),
        ),
    )[:4]
    for row in cpp_candidates:
        selected_rows.append(
            {
                "build_lane": "cpp_successor_salvage",
                "priority": "medium",
                "language_family": "c_cpp",
                "repo_id": row.get("repo_id"),
                "row_id": row.get("row_id"),
                "review_packet_dir": None,
                "source_kind": "review_blocked_successor",
                "successor_template": row.get("successor_template"),
                "selected_tests_count": row.get("selected_tests_count"),
                "shortcut_risk_score": row.get("shortcut_risk_score"),
                "candidate_surface_pair": row.get("candidate_surface_pair"),
                "target_contract": "Convert into fresh implementation-vs-implementation maintainer bundles or abstention rows; do not overclaim verifier strength when selected tests are absent.",
                "required_gates": [
                    "prompt_target_leak_rows == 0",
                    "candidate surfaces remain plausibly confusable from visible evidence",
                    "if selected tests are absent, abstention must be allowed rather than forcing singleton localization",
                ],
            }
        )

    # Use unconsumed Rust reviewed packets outside tokenizers/flash-attn as the next fresh materialization targets.
    admitted = atlas.get("admitted_bundle_rows") or []
    rust_review_targets = [
        row
        for row in admitted
        if str(row.get("language_family") or "") == "rust"
        and str(row.get("bundle_id") or "") in {
            "stage10126::candle::candle-core::rust",
        }
    ]
    rust_blocked_extra = [
        row
        for row in blocked.get("language_examples", {}).get("c_cpp", [])
    ]  # no-op placeholder to keep schema stable
    del rust_blocked_extra
    extra_rust_packets = [
        {
            "bundle_id": "stage10126::candle::candle-examples::rust",
            "language_family": "rust",
            "repo_id": "candle",
            "packet_dir": "runs/local/artifacts/stage10127_true_source_backed_rust_review_packets_and_signoff/review_packets/stage10126__candle__candle-examples__rust",
            "selected_tests_count": 0,
            "visible_evidence_keys": [
                "algorithmic_background_reference",
                "candidate_change_surface",
                "external_analogue_reference",
                "nearby_definition_or_usage_context",
                "symptom_or_call_path_analogue",
                "verifier_and_test_constraint",
            ],
            "decision_rationale": "Unconsumed reviewed Rust packet; use as fresh materialization target rather than reusing tokenizers/flash-attn.",
        },
        {
            "bundle_id": "stage10126::candle::candle-nn::rust",
            "language_family": "rust",
            "repo_id": "candle",
            "packet_dir": "runs/local/artifacts/stage10127_true_source_backed_rust_review_packets_and_signoff/review_packets/stage10126__candle__candle-nn__rust",
            "selected_tests_count": 0,
            "visible_evidence_keys": [
                "algorithmic_background_reference",
                "candidate_change_surface",
                "nearby_definition_or_usage_context",
                "symptom_or_call_path_analogue",
            ],
            "decision_rationale": "Unconsumed reviewed Rust packet; likely abstention-heavy but fresh relative to the failed tokenizers/flash-attn families.",
        },
    ]
    for row in [*rust_review_targets, *extra_rust_packets]:
        selected_rows.append(
            {
                "build_lane": "rust_fresh_review_packet_materialization",
                "priority": "medium",
                "language_family": "rust",
                "repo_id": row.get("repo_id"),
                "bundle_id": row.get("bundle_id"),
                "packet_dir": row.get("packet_dir"),
                "source_kind": "reviewed_packet",
                "selected_tests_count": row.get("selected_tests_count"),
                "visible_evidence_keys": row.get("visible_evidence_keys"),
                "decision_rationale": row.get("decision_rationale"),
                "target_contract": "Materialize fresh non-tokenizers Rust evidence rows; allow abstention when visible evidence does not uniquely justify a singleton surface.",
                "required_gates": [
                    "candidate_change_surface must not duplicate the gold evidence span",
                    "rows must be fresh relative to tokenizers and flash-attn headline failures",
                    "selected-test anchors preserved when present",
                ],
            }
        )

    # Web remains support-only until pure-web selected-test supply exists, but keep the verifier-anchored code_assist successor explicit.
    selected_rows.append(
        {
            "build_lane": "web_support_only_successor",
            "priority": "support_only",
            "language_family": "web_js_ts_html",
            "repo_id": "code_assist",
            "row_id": "stage10110::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t13_13_10_019bff96_2dc5_7162_88f8_83eb_src_code_assist_orchestrator_cognitive_perfection_py_src_code_assist_orchestrato_3a0f6d8311_aug_1500000_8b46e7f662::web_implementation_vs_implementation",
            "source_kind": "ai_adjudicated_successor",
            "selected_tests_count": 6,
            "adjudicated_gold_answer": "B",
            "target_contract": "Use only as stress/train-support until a pure-web selected-test family exists.",
            "required_gates": [
                "never promote to source-heldout headline",
                "mark mixed-language overlap explicitly",
            ],
        }
    )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Package the next concrete fresh-root build set from in-repo reviewed and review-blocked sources.",
            "Separate promotable fresh-root generation work from support-only web and abstention-heavy Rust salvage lanes.",
        ],
        "source_artifacts": {
            "blocked_successor_inventory": rel(BLOCKED_JSON),
            "blocked_successor_rows": rel(BLOCKED_ROWS),
            "ai_adjudicated_successor_salvage": rel(SALVAGE_JSON),
            "reviewed_scaling_atlas": rel(ATLAS_JSON),
            "pure_web_gap_audit": rel(WEB_GAP_JSON),
        },
        "metrics": {
            "selected_rows": len(selected_rows),
            "by_language": count_by(selected_rows, "language_family"),
            "by_lane": count_by(selected_rows, "build_lane"),
            "python_selected_tests_total": sum(int(row.get("selected_tests_count") or 0) for row in selected_rows if str(row.get("language_family") or "") == "python"),
            "cpp_selected_tests_total": sum(int(row.get("selected_tests_count") or 0) for row in selected_rows if str(row.get("language_family") or "") == "c_cpp"),
            "rust_selected_tests_total": sum(int(row.get("selected_tests_count") or 0) for row in selected_rows if str(row.get("language_family") or "") == "rust"),
            "web_source_heldout_headline_ready": ((web_gap.get("verdict") or {}).get("web_source_heldout_headline_ready")),
        },
        "findings": [
            "Python fresh-root expansion should start with the high-selected-test agentkernel implementation-vs-config successor lane, because it is the largest in-repo non-frontier supply with concrete verifier anchors.",
            "C/C++ has only weak non-frontier successor supply in-repo; the remaining parametergolf rows should be treated as salvage/support, not as sufficient headline replenishment.",
            "Rust must shift to unconsumed reviewed packets like candle-core, candle-examples, and candle-nn if we want fresh rows outside tokenizers and flash-attn.",
            "Web still lacks a pure-web selected-test family; code_assist remains support-only even though it is adjudicated.",
        ],
        "next_best_step": "Materialize these selected rows/packets into fresh successor prompts with explicit anti-cheat fields, then run one fresh-root expansion probe instead of another same-root geometry probe.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "fresh_root_build_rows_jsonl": rel(ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_jsonl(ROWS_JSONL, selected_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
