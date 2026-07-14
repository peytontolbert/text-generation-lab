#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10701
NAME = "stage10701_first_multilingual_leak_rewrite_candidate_set"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST_JSON = OUT_DIR / "first_multilingual_leak_rewrite_candidate_set.json"
ROWS_JSONL = OUT_DIR / "rewrite_candidate_roots.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BACKLOG_ROWS = ROOT / "runs/local/artifacts/stage10699_multilingual_root_scale_package_v1/quarantine_rewrite_backlog.jsonl"
PRIORITY_ROWS = ROOT / "runs/local/artifacts/stage10700_root_scale_rewrite_priority_manifest/rewrite_priority_rows.jsonl"
ADMISSION_ROWS = ROOT / "runs/local/artifacts/stage10691_root_admission_manifest_v2/root_admission_manifest_v2.jsonl"
COMPILED_ROOTS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
BOOTSTRAP_ROWS = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/multitarget_bootstrap_with_heldout_rows.jsonl"
SCALE_PACKAGE = ROOT / "runs/local/artifacts/stage10699_multilingual_root_scale_package_v1/multilingual_root_scale_package_v1.json"

TARGET_FAMILY_LIMITS = {
    "rust": {"family_caps": {"tiktoken": None, "dbt-core": None, "chroma": None}},
    "web_js_ts_html": {"family_caps": {"mem0": None, "cand_ent_multi_stage_52c293c2ae_12_17b7a104a9": None}},
    "python": {"family_caps": {"agentkernel": 8, "agentkernel-seq2seq-text-lab": 4}},
    "c_cpp": {"family_caps": {"parametergolf": 6, "onnxruntime": 3, "cccl": 3}},
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


def aggregate_bootstrap_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        root_id = str(row.get("root_id") or "")
        entry = grouped.setdefault(
            root_id,
            {
                "rows": 0,
                "prompt_target_leak_rows": 0,
                "target_families": Counter(),
                "target_subtypes": Counter(),
                "split_components": Counter(),
                "source_family_ids": Counter(),
            },
        )
        entry["rows"] += 1
        anti_cheat = row.get("anti_cheat") or {}
        if anti_cheat.get("prompt_target_leak"):
            entry["prompt_target_leak_rows"] += 1
        entry["target_families"][str(row.get("target_family") or "unknown")] += 1
        entry["target_subtypes"][str(row.get("target_subtype") or "unknown")] += 1
        entry["split_components"][str(row.get("split_component") or "unknown")] += 1
        entry["source_family_ids"][str(row.get("source_family_id") or "unknown")] += 1
    return grouped


def rewrite_requirements(language: str) -> list[str]:
    shared = [
        "Remove prompt_target_leak by hiding gold target strings before options or decoder target text.",
        "Expose a visible candidate ledger so the gold target is selectable from model-visible evidence rather than opaque handle recovery.",
        "Preserve root-level split isolation and keep rewritten roots out of current promotable strict eval until post-rewrite re-admission.",
        "Re-run anti-cheat gates: prompt_target_leak=false, no post-fix evidence in pre-decision state, candidate-position invariance.",
    ]
    language_specific = {
        "rust": [
            "Prefer non-tokenizers verifier-backed evidence and explicit E-vs-F style citation competition.",
            "Keep abstention-heavy support separate from promotable singleton localization/citation roots.",
        ],
        "web_js_ts_html": [
            "Require pure-web verifier or selected-test anchors after rewrite; do not preserve changed-path shortcuts.",
            "Reject overlap-heavy code_assist style mixed-language shortcuts from promotable claims.",
        ],
        "python": [
            "Add repo-family caps during later package assembly so rewritten agentkernel-family roots do not dominate train splits.",
            "Bias rewrites toward verifier-outcome and evidence selection states rather than generic retrieval-only rows.",
        ],
        "c_cpp": [
            "Prefer verifier/build/test anchored states and candidate competition across implementation, wrapper, and benchmark surfaces.",
            "After rewrite, cap parametergolf family contribution in train packaging to prevent dominance.",
        ],
    }
    return shared + language_specific.get(language, [])


def main() -> None:
    backlog_rows = load_jsonl(BACKLOG_ROWS)
    priority_rows = load_jsonl(PRIORITY_ROWS)
    admission_rows = load_jsonl(ADMISSION_ROWS)
    compiled_roots = load_jsonl(COMPILED_ROOTS)
    bootstrap_rows = load_jsonl(BOOTSTRAP_ROWS)
    scale_package = load_json(SCALE_PACKAGE)

    compiled_by_root = {str(row.get("root_id") or ""): row for row in compiled_roots}
    admission_by_root = {str(row.get("root_id") or ""): row for row in admission_rows}
    bootstrap_agg = aggregate_bootstrap_rows(bootstrap_rows)
    priority_index: dict[tuple[str, str], int] = {}
    for idx, row in enumerate(priority_rows):
        priority_index[(str(row.get("language_family") or ""), str(row.get("repo_family") or ""))] = idx

    backlog_by_language_family: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in backlog_rows:
        backlog_by_language_family[(str(row.get("language_family") or ""), str(row.get("repo_family") or ""))].append(row)

    selected: list[dict[str, Any]] = []
    for language, cfg in TARGET_FAMILY_LIMITS.items():
        family_caps = dict(cfg["family_caps"])
        ordered_families = sorted(
            family_caps,
            key=lambda repo_family: priority_index.get((language, repo_family), 10**9),
        )
        for repo_family in ordered_families:
            family_rows = sorted(
                backlog_by_language_family.get((language, repo_family), []),
                key=lambda row: (int(row.get("prompt_target_leak_rows") or 0), str(row.get("root_id") or "")),
            )
            cap = family_caps[repo_family]
            if cap is not None:
                family_rows = family_rows[: int(cap)]
            selected.extend(family_rows)

    selected_ids = {str(row.get("root_id") or "") for row in selected}
    enriched_rows: list[dict[str, Any]] = []
    for row in selected:
        root_id = str(row.get("root_id") or "")
        compiled = compiled_by_root.get(root_id, {})
        bootstrap = bootstrap_agg.get(root_id, {})
        admission = admission_by_root.get(root_id, {})
        language = str(row.get("language_family") or "")
        enriched_rows.append(
            {
                "root_id": root_id,
                "language_family": language,
                "repo_family": str(row.get("repo_family") or ""),
                "rewrite_priority": str(row.get("rewrite_priority") or ""),
                "source_kind": str(row.get("source_kind") or ""),
                "quality_score": row.get("quality_score"),
                "prompt_target_leak_rows": int(row.get("prompt_target_leak_rows") or 0),
                "compiled_snapshot_id": compiled.get("snapshot_id"),
                "compiled_split_component": compiled.get("split_component"),
                "compiled_task_family": compiled.get("task_family"),
                "compiled_verifier_id": compiled.get("verifier_id"),
                "compiled_provenance": compiled.get("provenance") or {},
                "bootstrap_row_count": bootstrap.get("rows", 0),
                "bootstrap_split_components": dict(sorted((bootstrap.get("split_components") or {}).items())),
                "bootstrap_target_families": dict(sorted((bootstrap.get("target_families") or {}).items())),
                "bootstrap_target_subtypes": dict(sorted((bootstrap.get("target_subtypes") or {}).items())),
                "bootstrap_source_family_ids": dict(sorted((bootstrap.get("source_family_ids") or {}).items())),
                "admission_notes": admission.get("notes") or [],
                "rewrite_requirements": rewrite_requirements(language),
                "post_rewrite_expected_role": "train_or_validation_candidate",
            }
        )

    enriched_rows.sort(
        key=lambda row: (
            {"high": 0, "medium": 1, "low": 2}.get(str(row.get("rewrite_priority") or "low"), 3),
            str(row.get("language_family") or ""),
            str(row.get("repo_family") or ""),
            str(row.get("root_id") or ""),
        )
    )
    write_jsonl(ROWS_JSONL, enriched_rows)

    language_counts = Counter(str(row.get("language_family") or "") for row in enriched_rows)
    repo_counts = Counter(str(row.get("repo_family") or "") for row in enriched_rows)
    scale_language_cards = {str(card.get("language_family") or ""): card for card in (scale_package.get("language_cards") or [])}

    manifest = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "first_multilingual_leak_rewrite_candidate_set_ready",
        "claim_scope": [
            "Select the first concrete quarantine roots to rewrite into leak-clean, visible-candidate multilingual training/eval supply.",
            "Prioritize all current Rust and web quarantine roots, then add capped Python and C/C++ family slices for high-yield rewrite work.",
            "This is a rewrite input manifest, not a new training or evaluation result.",
        ],
        "source_artifacts": {
            "quarantine_backlog": display(BACKLOG_ROWS),
            "rewrite_priority_rows": display(PRIORITY_ROWS),
            "root_admission_manifest_v2": display(ADMISSION_ROWS),
            "compiled_root_records": display(COMPILED_ROOTS),
            "bootstrap_rows": display(BOOTSTRAP_ROWS),
            "scale_package_v1": display(SCALE_PACKAGE),
        },
        "selection_policy": {
            "rust": "Include all current high-priority quarantine roots from tiktoken, dbt-core, and chroma.",
            "web_js_ts_html": "Include all current high-priority quarantine roots from mem0 and the multi-stage candidate family.",
            "python": "Cap the first rewrite wave to agentkernel and agentkernel-seq2seq-text-lab only.",
            "c_cpp": "Cap the first rewrite wave to parametergolf, onnxruntime, and cccl only.",
        },
        "selected_counts": {
            "roots_total": len(enriched_rows),
            "language_counts": dict(sorted(language_counts.items())),
            "repo_family_counts": dict(sorted(repo_counts.items())),
            "selected_root_ids_count_check": len(selected_ids),
        },
        "language_context": {
            language: {
                "phase_1_gap_before_rewrite": ((scale_language_cards.get(language, {}).get("gaps") or {}).get("phase_1")),
                "ready_train_roots_now": ((scale_package.get("global_counts") or {}).get("ready_for_large_scale_train_by_language") or {}).get(language),
            }
            for language in TARGET_FAMILY_LIMITS
        },
        "headline_findings": [
            "This first rewrite batch is intentionally small and family-capped so the interface repair can be validated before touching the rest of the 729-root quarantine backlog.",
            "Rust and web are fully included because their ready pools are too small to wait behind Python-scale cleanup.",
            "Python and C/C++ are included only through the highest-yield dominant families so rewrite effort improves scale honestly without worsening dominance bias.",
        ],
        "required_next_actions": [
            "Implement a row/interface rewrite stage that converts these roots into visible-candidate, leak-clean causal states.",
            "Re-run root admission on rewritten outputs rather than inheriting promotability from current quarantine records.",
            "Keep rewritten roots out of current strict canaries until fresh heldout reservations are made.",
        ],
        "recommended_next_stage": "stage10702_leak_rewrite_interface_builder",
        "outputs": {
            "rewrite_candidate_roots": display(ROWS_JSONL),
            "manifest_json": display(MANIFEST_JSON),
        },
    }
    write_json(MANIFEST_JSON, manifest)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": manifest["decision"],
            "manifest_json": display(MANIFEST_JSON),
        },
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
