from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10628
NAME = "stage10628_root_admission_scale_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

ROOT_RECORDS_JSONL = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
ROWS_JSONL = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_multitarget_rows.jsonl"
INVENTORY_JSON = ROOT / "runs/local/artifacts/stage10510_long_context_refinery_inventory/long_context_refinery_inventory.json"
HELDOUT_MANIFEST_JSON = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/split_aware_multitarget_bootstrap_manifest_with_heldout.json"

ADMISSION_ROWS_JSONL = OUT_DIR / "root_admission_records.jsonl"
AUDIT_JSON = OUT_DIR / "root_admission_scale_audit.json"
RUN_SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

LANGUAGE_ROOT_TARGETS = {
    "python": 35000,
    "rust": 20000,
    "c_cpp": 20000,
    "web_js_ts_html": 20000,
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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def family_meta(inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    meta: dict[str, dict[str, Any]] = {}
    for family in inventory.get("families", []):
        meta[family["family_id"]] = family
    return meta


def direct_target_visible(row: dict[str, Any]) -> bool:
    target_text = str(row.get("target_text", "")).strip()
    input_text = str(row.get("input_text", ""))
    if not target_text or not input_text:
        return False
    return target_text in input_text


def opaque_or_empty_bounded_target(row: dict[str, Any]) -> bool:
    if row.get("target_family") != "bounded_decision":
        return False
    target_text = str(row.get("target_text", "")).strip()
    return not target_text


def bounded_target_is_route_token(row: dict[str, Any]) -> bool:
    if row.get("target_family") != "bounded_decision":
        return False
    target_text = str(row.get("target_text", "")).strip()
    return target_text in {
        "PASS_TARGETED_TEST_SELECTION",
        "PATCH_PLUS_EXEC",
        "COMMIT_PLUS_VERIFY",
        "ANSWER_WITH_RETRIEVED_EVIDENCE",
        "RETRIEVE_MORE",
        "ABSTAIN_INSUFFICIENT_EVIDENCE",
    }


def classify_admit_role(
    *,
    quality_score: float,
    direct_visible_count: int,
    opaque_bounded_count: int,
    has_verifier_anchor: bool,
    source_role: str,
    split_component: str,
) -> str:
    if direct_visible_count > 0 or opaque_bounded_count > 0:
        return "quarantine"
    if split_component.startswith("strict_eval_") and quality_score >= 85:
        return "strict_eval_candidate"
    if split_component.startswith("validation_") and quality_score >= 80:
        return "validation_candidate"
    if quality_score >= 80 and has_verifier_anchor and source_role not in {"raw_long_context_trace_source", "augmented_long_context_trace_source"}:
        return "gold_train"
    if quality_score >= 65:
        return "silver_train"
    if quality_score >= 45:
        return "bronze_support"
    return "quarantine"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RUN_SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)

    root_records = load_jsonl(ROOT_RECORDS_JSONL)
    rows = load_jsonl(ROWS_JSONL)
    inventory = load_json(INVENTORY_JSON)
    heldout_manifest = load_json(HELDOUT_MANIFEST_JSON)

    family_lookup = family_meta(inventory)
    rows_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rows_by_root[row["root_id"]].append(row)

    root_counts_by_repo = Counter(root["repo_family"] for root in root_records)
    root_counts_by_language = Counter(root["language_family"] for root in root_records)

    admission_rows: list[dict[str, Any]] = []

    for root in root_records:
        root_id = root["root_id"]
        root_rows = rows_by_root.get(root_id, [])
        source_family_id = root.get("provenance", {}).get("source_family_id", "unknown")
        source_meta = family_lookup.get(source_family_id, {})
        source_role = source_meta.get("role", "unmapped_source_family")
        source_quality_tier = source_meta.get("quality_tier", "unknown")

        target_families = sorted({row.get("target_family", "unknown") for row in root_rows})
        target_subtypes = sorted({row.get("target_subtype", "unknown") for row in root_rows})
        anti_cheat = [row.get("anti_cheat", {}) for row in root_rows]
        direct_visible_count = sum(1 for row in root_rows if direct_target_visible(row))
        opaque_bounded_count = sum(1 for row in root_rows if opaque_or_empty_bounded_target(row))
        route_token_count = sum(1 for row in root_rows if bounded_target_is_route_token(row))
        prompt_target_leak_flags = sum(1 for item in anti_cheat if item.get("prompt_target_leak") is True)
        same_root_guard_flags = sum(1 for item in anti_cheat if item.get("same_root_train_eval_forbidden") is True)
        has_verifier_anchor = str(root.get("verifier_id", "")).strip() not in {"", "UNKNOWN", "unknown", "NONE", "None"}

        verifier_anchor_score = 35 if has_verifier_anchor else 5
        diversity_score = min(20, len(target_subtypes) * 3 + len(target_families) * 4)
        source_quality_score = {
            "high": 20,
            "medium": 12,
            "unknown": 8,
            "heldout_only": 6,
            "auxiliary_only": 4,
        }.get(source_quality_tier, 8)
        source_role_bonus = {
            "audited_small_train_ready_reference": 12,
            "midscale_retrieval_teacher_corpus": 8,
            "high_quality_merged_refinery_source": 10,
            "large_raw_long_context_refinery_source": 5,
            "raw_long_context_trace_source": 4,
            "augmented_long_context_trace_source": 4,
        }.get(source_role, 5)
        novelty_penalty = min(20, max(0, root_counts_by_repo[root["repo_family"]] - 5) // 5)
        leak_penalty = 25 * direct_visible_count + 20 * opaque_bounded_count + 10 * prompt_target_leak_flags
        shortcut_penalty = min(15, route_token_count * 2)

        quality_score = max(
            0.0,
            min(
                100.0,
                verifier_anchor_score
                + diversity_score
                + source_quality_score
                + source_role_bonus
                + (5 if same_root_guard_flags > 0 else 0)
                - novelty_penalty
                - leak_penalty
                - shortcut_penalty,
            ),
        )

        root_lineage_key = "::".join(
            [
                root.get("repo_family", "unknown"),
                source_family_id,
                root.get("snapshot_id", "unknown"),
                root.get("provenance", {}).get("example_id", root_id),
            ]
        )
        admit_role = classify_admit_role(
            quality_score=quality_score,
            direct_visible_count=direct_visible_count,
            opaque_bounded_count=opaque_bounded_count,
            has_verifier_anchor=has_verifier_anchor,
            source_role=source_role,
            split_component=root.get("split_component", "unknown"),
        )
        risk_tags: list[str] = []
        if direct_visible_count:
            risk_tags.append("direct_target_visible")
        if opaque_bounded_count:
            risk_tags.append("opaque_or_empty_bounded_target")
        if route_token_count:
            risk_tags.append("route_token_target")
        if root_counts_by_repo[root["repo_family"]] > 25:
            risk_tags.append("repo_family_concentrated")
        if root_counts_by_language[root["language_family"]] < 25:
            risk_tags.append("language_supply_thin")
        if source_role in {"raw_long_context_trace_source", "augmented_long_context_trace_source"}:
            risk_tags.append("raw_trace_refinery_only")

        admission_rows.append(
            {
                "root_id": root_id,
                "root_lineage_key": root_lineage_key,
                "repo_id": root.get("repo_id", "unknown"),
                "repo_family": root.get("repo_family", "unknown"),
                "language_family": root.get("language_family", "unknown"),
                "task_family": root.get("task_family", "unknown"),
                "snapshot_id": root.get("snapshot_id", "unknown"),
                "environment_id": root.get("environment_id", "unknown"),
                "verifier_id": root.get("verifier_id", "unknown"),
                "source_family_id": source_family_id,
                "source_role": source_role,
                "source_quality_tier": source_quality_tier,
                "split_component": root.get("split_component", "unknown"),
                "row_count": len(root_rows),
                "target_families": target_families,
                "target_subtypes": target_subtypes,
                "anti_cheat_summary": {
                    "prompt_target_leak_flags": prompt_target_leak_flags,
                    "same_root_train_eval_forbidden_rows": same_root_guard_flags,
                    "direct_target_visible_rows": direct_visible_count,
                    "opaque_or_empty_bounded_target_rows": opaque_bounded_count,
                    "route_token_target_rows": route_token_count,
                },
                "has_verifier_anchor": has_verifier_anchor,
                "quality_score": round(quality_score, 2),
                "admit_role": admit_role,
                "risk_tags": risk_tags,
            }
        )

    admission_rows.sort(key=lambda row: (-row["quality_score"], row["root_id"]))

    admitted_by_language = Counter()
    admitted_gold_by_language = Counter()
    quarantine_by_language = Counter()
    for row in admission_rows:
        language = row["language_family"]
        if row["admit_role"] != "quarantine":
            admitted_by_language[language] += 1
        if row["admit_role"] == "gold_train":
            admitted_gold_by_language[language] += 1
        if row["admit_role"] == "quarantine":
            quarantine_by_language[language] += 1

    scale_gap = {}
    for language, target in LANGUAGE_ROOT_TARGETS.items():
        current = admitted_by_language.get(language, 0)
        scale_gap[language] = {
            "target_roots": target,
            "current_non_quarantine_roots": current,
            "additional_roots_needed": max(0, target - current),
            "coverage_ratio": 0.0 if target == 0 else round(current / target, 6),
        }

    highest_repo_concentration = sorted(root_counts_by_repo.items(), key=lambda item: (-item[1], item[0]))[:15]
    highest_quarantine = [row for row in admission_rows if row["admit_role"] == "quarantine"][:25]

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "claim_boundary": [
            "This is a root-admission and scaling audit, not a training result.",
            "The audit scores current compiled roots for quality, leak risk, verifier grounding, and scale-readiness.",
            "Non-quarantine admission here means fit for further curation, not automatic promotion to headline eval.",
            "The repaired multilingual v2.7 strict frontier remains a separate Gemma comparison canary.",
        ],
        "inputs": {
            "compiled_roots": str(ROOT_RECORDS_JSONL.relative_to(ROOT)),
            "compiled_rows": str(ROWS_JSONL.relative_to(ROOT)),
            "refinery_inventory": str(INVENTORY_JSON.relative_to(ROOT)),
            "heldout_manifest": str(HELDOUT_MANIFEST_JSON.relative_to(ROOT)),
        },
        "language_root_targets": LANGUAGE_ROOT_TARGETS,
        "metrics": {
            "compiled_root_records": len(root_records),
            "compiled_row_records": len(rows),
            "heldout_strict_rows": heldout_manifest.get("metrics", {}).get("strict_eval_rows", 0),
            "admit_role_counts": dict(sorted(Counter(row["admit_role"] for row in admission_rows).items())),
            "source_role_counts": dict(sorted(Counter(row["source_role"] for row in admission_rows).items())),
            "roots_by_language": dict(sorted(root_counts_by_language.items())),
            "admitted_non_quarantine_by_language": dict(sorted(admitted_by_language.items())),
            "gold_train_by_language": dict(sorted(admitted_gold_by_language.items())),
            "quarantine_by_language": dict(sorted(quarantine_by_language.items())),
            "repo_family_top15": highest_repo_concentration,
            "direct_target_visible_root_count": sum(1 for row in admission_rows if "direct_target_visible" in row["risk_tags"]),
            "opaque_or_empty_bounded_target_root_count": sum(1 for row in admission_rows if "opaque_or_empty_bounded_target" in row["risk_tags"]),
        },
        "scale_gap": scale_gap,
        "quality_ratchet": {
            "required_for_next_scale_jump": [
                "Every new source family must produce root_lineage_key and pass same-root split isolation before row generation.",
                "No bounded_decision root can enter gold or silver if target_text is empty or visibly copied into the prompt.",
                "Repo-family caps must prevent one family from dominating any language slice.",
                "Gold roots should remain verifier-backed and leak-clean; raw long-context refinery families should stay support-only until materialized into compact causal states.",
            ],
            "current_blockers": [
                "Python root supply is large but highly concentrated in agentkernel-family and raw bootstrap routes.",
                "Rust and web root supply are far below any serious multilingual scale target.",
                "Many current bounded_decision roots use route-token targets such as PASS_TARGETED_TEST_SELECTION, which is a shortcut-prone interface.",
            ],
        },
        "next_best_step": (
            "Use this admission audit to drive stage10516_v2 or its successor: expand source-family scanning, "
            "materialize verifier-backed compact states, drop direct-visible bounded targets, and replenish Rust/Web/C++ roots "
            "until non-quarantine root supply grows by language under repo-family caps."
        ),
        "outputs": {
            "root_admission_records": str(ADMISSION_ROWS_JSONL.relative_to(ROOT)),
            "audit": str(AUDIT_JSON.relative_to(ROOT)),
        },
        "sample_quarantine_roots": highest_quarantine,
    }

    write_jsonl(ADMISSION_ROWS_JSONL, admission_rows)
    write_json(AUDIT_JSON, audit)
    write_json(RUN_SUMMARY_JSON, audit)


if __name__ == "__main__":
    main()
