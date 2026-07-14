#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10613
NAME = "stage10613_multilingual_root_scale_quality_contract"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT_JSON = OUT_DIR / "multilingual_root_scale_quality_contract.json"
TARGETS_JSONL = OUT_DIR / "multilingual_root_scale_targets.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PROMOTION_CONTRACT = ROOT / "runs/local/artifacts/stage10609_reviewed_v27_multilingual_promotion_contract/reviewed_v27_multilingual_promotion_contract.json"
PLATEAU_AUDIT = ROOT / "runs/local/artifacts/stage10612_repaired_v27_fresh_root_probe_audit/repaired_v27_fresh_root_probe_audit.json"
V27_PACKAGE = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/reviewed_multilingual_v27_manifest_package.json"
V27_COMPARISON = ROOT / "runs/local/artifacts/stage10424_reviewed_multilingual_v27_comparison_audit/reviewed_multilingual_v27_comparison_audit.json"
ROOT_COMPILER = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/long_context_root_state_compiler.json"
HELDOUT_MANIFEST = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/split_aware_multitarget_bootstrap_manifest_with_heldout.json"
HELDOUT_AUDIT = ROOT / "runs/local/artifacts/stage10522_multitarget_bootstrap_eval_hacking_audit_with_heldout/multitarget_bootstrap_eval_hacking_audit_with_heldout.json"

LONG_TERM_TARGETS = {
    "python": 35000,
    "rust": 20000,
    "c_cpp": 20000,
    "web_js_ts_html": 20000,
}

PHASE_1_TARGETS = {
    "python": 2000,
    "rust": 1000,
    "c_cpp": 1000,
    "web_js_ts_html": 1000,
}

PHASE_2_TARGETS = {
    "python": 5000,
    "rust": 3000,
    "c_cpp": 3000,
    "web_js_ts_html": 3000,
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def main() -> None:
    promotion_contract = load_json(PROMOTION_CONTRACT)
    plateau_audit = load_json(PLATEAU_AUDIT)
    v27_package = load_json(V27_PACKAGE)
    v27_comparison = load_json(V27_COMPARISON)
    root_compiler = load_json(ROOT_COMPILER)
    heldout_manifest = load_json(HELDOUT_MANIFEST)
    heldout_audit = load_json(HELDOUT_AUDIT)

    reviewed_root_counts = dict(((v27_package.get("metrics") or {}).get("root_language_counts")) or {})
    compiled_root_counts = dict(((root_compiler.get("metrics") or {}).get("language_counts")) or {})
    strict_rows_reviewed = dict(((v27_comparison.get("strict_rows_by_language")) or (v27_package.get("metrics") or {}).get("row_language_counts") or {}))
    heldout_strict_rows = dict((((heldout_manifest.get("metrics") or {}).get("strict_rows_by_language")) or {}))

    language_priority_notes = {
        "python": [
            "Current standalone residual miss is verifier_outcome target disambiguation.",
            "Scale is easiest here, but Python already dominates the compiler and therefore needs stronger repo-family caps and heldout replenishment discipline.",
        ],
        "rust": [
            "Current standalone residual miss is evidence_citation E-vs-F collapse.",
            "Rust source supply is materially underweight in the long-context compiler and still too dependent on abstention-heavy or tokenizers-adjacent roots.",
        ],
        "c_cpp": [
            "Reviewed v2.7 same-manifest compact slice is currently strong, but long-context root supply is still two orders of magnitude below the desired scale target.",
            "Need more verifier-backed CUDA/kernel/build roots from distinct repo families.",
        ],
        "web_js_ts_html": [
            "Reviewed bundles exist, but pure-web verifier-anchor coverage is still weak and selected-test coverage is sparse.",
            "Need more real frontend/backend failure roots rather than overlap-heavy code_assist style support.",
        ],
    }
    language_quality_flags = {
        "python": [
            "cap one repo family before it can dominate the train split",
            "require verifier-target competition for new verifier_outcome roots",
            "keep current MirrorMind strict root out of train support",
        ],
        "rust": [
            "prefer non-tokenizers, non-abstention-heavy roots for promotion claims",
            "require explicit E-vs-F evidence contrast in reviewed citation packets",
            "keep same-surface tokenizers rows out of promotable support",
        ],
        "c_cpp": [
            "prefer selected-test or build-verifier anchored roots",
            "require candidate competition across kernel, benchmark, and wrapper surfaces",
            "balance CUDA-extension families across repos",
        ],
        "web_js_ts_html": [
            "require pure-web roots with selected tests or verifier anchors before broad web claims",
            "tag overlap-heavy mixed-language bundles as stress-only",
            "reject roots solvable from changed-path signatures alone",
        ],
    }

    target_rows: list[dict[str, Any]] = []
    for language in ("python", "rust", "c_cpp", "web_js_ts_html"):
        compiled_roots = int(compiled_root_counts.get(language, 0))
        reviewed_roots = int(reviewed_root_counts.get(language, 0))
        long_term_target = LONG_TERM_TARGETS[language]
        phase_1_target = PHASE_1_TARGETS[language]
        phase_2_target = PHASE_2_TARGETS[language]
        target_rows.append(
            {
                "language_family": language,
                "current_compiled_roots": compiled_roots,
                "current_reviewed_bundle_roots": reviewed_roots,
                "current_reviewed_strict_rows": int(strict_rows_reviewed.get(language, 0)),
                "current_bootstrap_heldout_rows": int(heldout_strict_rows.get(language, 0)),
                "phase_1_target_roots": phase_1_target,
                "phase_1_root_gap": max(phase_1_target - compiled_roots, 0),
                "phase_2_target_roots": phase_2_target,
                "phase_2_root_gap": max(phase_2_target - compiled_roots, 0),
                "long_term_target_roots": long_term_target,
                "long_term_root_gap": max(long_term_target - compiled_roots, 0),
                "priority_notes": language_priority_notes[language],
                "quality_flags": language_quality_flags[language],
            }
        )

    contract = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "multilingual_root_scale_quality_contract_ready",
        "claim_scope": [
            "Freeze the current reviewed v2.7 standalone compact frontier as a canary and anti-regression surface, not the main scaling target.",
            "Use the long-context root/state compiler plus heldout-safe bootstrap manifest as the main path to multilingual root scale.",
            "Scale root count only under a quality ratchet: leak-clean, root-split, verifier-aware, repo-capped, and heldout-pressured.",
        ],
        "current_truthful_status": {
            "standalone_v27_headline": {
                "promotion_surface": ((promotion_contract.get("promotion_surface") or {}).get("name")),
                "primary_metric": ((promotion_contract.get("promotion_surface") or {}).get("primary_metric")),
                "strict_accuracy": ((plateau_audit.get("headline") or {}).get("probe_constrained_choice_top1_accuracy")),
                "baseline_accuracy": ((plateau_audit.get("headline") or {}).get("baseline_constrained_choice_top1_accuracy")),
                "plateau_reason": ((plateau_audit.get("headline") or {}).get("reason")),
            },
            "root_scale_substrate": {
                "compiled_root_records": ((root_compiler.get("metrics") or {}).get("compiled_root_records")),
                "compiled_multitarget_rows": ((root_compiler.get("metrics") or {}).get("compiled_multitarget_rows")),
                "heldout_strict_rows": ((heldout_manifest.get("metrics") or {}).get("strict_eval_rows")),
                "heldout_multilingual_headline_ready": ((heldout_audit.get("global_findings") or {}).get("multilingual_headline_ready")),
            },
        },
        "source_artifacts": {
            "promotion_contract": display(PROMOTION_CONTRACT),
            "plateau_audit": display(PLATEAU_AUDIT),
            "reviewed_v27_package": display(V27_PACKAGE),
            "reviewed_v27_comparison": display(V27_COMPARISON),
            "long_context_root_compiler": display(ROOT_COMPILER),
            "heldout_manifest": display(HELDOUT_MANIFEST),
            "heldout_eval_hacking_audit": display(HELDOUT_AUDIT),
        },
        "current_scale_snapshot": {
            "reviewed_bundle_roots_by_language": reviewed_root_counts,
            "compiled_roots_by_language": compiled_root_counts,
            "reviewed_compact_strict_rows_by_language": strict_rows_reviewed,
            "bootstrap_heldout_strict_rows_by_language": heldout_strict_rows,
            "current_compiled_total_roots": sum(compiled_root_counts.values()),
            "current_compiled_python_share": round(
                compiled_root_counts.get("python", 0) / max(sum(compiled_root_counts.values()), 1), 4
            ),
        },
        "scale_targets": {
            "phase_1": PHASE_1_TARGETS,
            "phase_2": PHASE_2_TARGETS,
            "long_term": LONG_TERM_TARGETS,
            "rationale": [
                "Phase 1 proves the admission and heldout process at multilingual root scale.",
                "Phase 2 is the first serious training scale for broader multilingual specialist improvement.",
                "Long-term targets align with the desired 20k+ roots per language and 30k-40k Python roots, but only after the quality ratchet is working.",
            ],
        },
        "quality_ratchet": {
            "must_hold_before_any_batch_is_counted_toward_scale": [
                "same root_id must not cross train, validation, strict, or stress claim paths",
                "same root_lineage_key or equivalent provenance family must not silently straddle promotable train/eval",
                "prompt_target_leak must be false for promotable rows",
                "post-fix or answer-only evidence must not appear in pre-decision states",
                "repo-family caps must prevent one family from dominating a language split",
                "new batches must preserve or improve canary accuracy and leak-clean status",
                "new heldout roots must be reserved before training, not after score inspection",
            ],
            "preferred_root_properties": [
                "selected test anchor present",
                "verifier anchor present",
                "plausible candidate competition across nearby files/symbols/tests",
                "real source-backed paths, traces, snippets, or state observations",
                "review packet or maintainer-grade adjudication when available",
            ],
            "promotion_blockers_to_keep_explicit": [
                "no source-heldout claim on reviewed v2.7 compact bundles without provenance proof",
                "no broad web claim without pure-web verifier-anchored roots",
                "no Rust residual recovery claim from tokenizers same-surface or abstention-heavy-only packets",
                "no standalone frontier upgrade from another 22/24 preservation run",
            ],
        },
        "language_gaps": target_rows,
        "required_next_build_order": [
            "Build a root-admission manifest that tags every candidate root with language, repo family, verifier-anchor strength, source family, and promotability role.",
            "Rebalance long-context source supply to reduce Python dominance and increase Rust/Web/C++ verified roots.",
            "Reserve fresh heldout roots per language before expanding train rows.",
            "Only after that, run the next multilingual training package that combines standalone canary replay with larger root-based multitarget training.",
        ],
        "recommended_next_stages": [
            "stage10614_root_admission_manifest_v1",
            "stage10615_multilingual_root_supply_balance_audit",
            "stage10616_reviewed_plus_bootstrap_multilingual_training_package",
        ],
    }

    write_json(CONTRACT_JSON, contract)
    write_jsonl(TARGETS_JSONL, target_rows)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": contract["decision"],
            "contract": display(CONTRACT_JSON),
            "targets": display(TARGETS_JSONL),
        },
    )
    print(json.dumps(contract, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
