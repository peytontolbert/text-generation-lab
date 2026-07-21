#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12533_legacy_collapse_group_countable_repair"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12532_OUT = ROOT / "runs/local/artifacts/stage12532_public_source_lane_expansion_and_train_support_admission_gate"
STAGE12532_SUMMARY = ROOT / "runs/summaries/stage12532_public_source_lane_expansion_and_train_support_admission_gate.json"
STAGE12532_TRAIN_ROWS = STAGE12532_OUT / "train_support_only_public_source_lane_rows.jsonl"
STAGE12532_ANTI_COLLAPSE = STAGE12532_OUT / "anti_collapse_audit.json"
STAGE12421_ROWS = ROOT / "runs/local/artifacts/stage12421_new_direct_real_verifier_observation_miner/new_direct_verifier_observation_train_support_rows.jsonl"

TARGET_TRAIN_SUPPORT_FLOOR = 500

RAW_KEY_RE = re.compile(
    r"^(input_text|prompt_text|decoder_text|command|cmd|argv|cwd|stdout|stderr|"
    r"stdout_tail|stderr_tail|output|path|url|diff|source_text|content|raw_.*)$",
    re.IGNORECASE,
)
RAW_VALUE_RE = re.compile(
    r"https?://|www\.|(^|\n)(diff --git|@@ |\+{3} |--- )|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){1,}[A-Za-z0-9._-]+|"
    r"\b(python|pytest|cargo|npm|yarn|pnpm|bash|sh|git)\b.+\s(-m|-q|test|run|checkout|diff)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE,
)

RISKY_FIELDS = (
    "strict_eval_eligible",
    "source_heldout_admissible",
    "level3_admitted",
    "level4_admitted",
    "patch_trace_admitted",
    "repair_claim_admitted",
    "fail_to_pass_claim_admitted",
    "counts_toward_unbounded_patch_trace_floor",
    "counts_toward_strict_eval_floor",
    "counts_toward_source_heldout_floor",
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value > 0
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return False


def risky_claims(row: dict[str, Any]) -> list[str]:
    admission = row.get("admission") if isinstance(row.get("admission"), dict) else {}
    claims = []
    for field in RISKY_FIELDS:
        if truthy(row.get(field)) or truthy(admission.get(field)):
            claims.append(field)
    return claims


def target_value(row: dict[str, Any]) -> str:
    if row.get("target_semantic_value"):
        return str(row["target_semantic_value"])
    if row.get("target_semantic_id"):
        return str(row["target_semantic_id"])
    target_label = row.get("bounded_choice_target_label") or row.get("target_label")
    for option in row.get("opaque_options") or []:
        if isinstance(option, dict) and option.get("label") == target_label:
            return str(option.get("semantic_id") or option.get("value") or "")
    return ""


def projection(row: dict[str, Any]) -> str:
    return str(row.get("task_projection") or row.get("task_family") or row.get("record_type") or "unknown")


def collapse_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_root[str(row.get("root_lineage_key_hash") or "unknown")].append(row)
    groups = []
    for root, group in by_root.items():
        projections = {str(row.get("task_projection") or "") for row in group}
        targets = {str(row.get("target_semantic_value") or row.get("target_or_status_class") or "") for row in group}
        generic_targets = {target for target in targets if target in {"candidate_0", "candidate_selected_test_backed"}}
        reason = None
        if len(group) >= 3 and len(targets) == 1:
            reason = "single_target_across_3_plus_rows"
        elif generic_targets and projections - {"transition_candidate_selection"}:
            reason = "generic_candidate_target_used_outside_candidate_selection"
        if reason:
            groups.append(
                {
                    "root_hash": root,
                    "reason": reason,
                    "row_count": len(group),
                    "countable_row_count": sum(1 for row in group if truthy(row.get("countable_train_support"))),
                    "task_projections": sorted(projections),
                    "target_values": sorted(targets),
                }
            )
    return groups


def collapse_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups = collapse_groups(rows)
    target_counts = Counter(str(row.get("target_semantic_value") or row.get("target_or_status_class") or "unknown") for row in rows)
    max_target_share = (max(target_counts.values()) / len(rows)) if rows else 0.0
    return {
        "collapse_group_count": len(groups),
        "collapsed_groups": groups[:20],
        "max_target_share": round(max_target_share, 6),
        "target_counts": dict(sorted(target_counts.items())),
        "target_dominance_passed": max_target_share <= 0.35 if rows else True,
    }


def iter_strings(value: Any, key: str = ""):
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield from iter_strings(child, str(child_key))
    elif isinstance(value, list):
        for child in value:
            yield from iter_strings(child, key)
    elif isinstance(value, str):
        yield key, value


def guardrail_scan(*objects: Any) -> dict[str, Any]:
    issues = []
    for obj in objects:
        for key, text in iter_strings(obj):
            if RAW_KEY_RE.search(key):
                issues.append({"kind": "raw_key", "key": key})
            elif RAW_VALUE_RE.search(text):
                issues.append({"kind": "raw_value", "key": key, "value_hash": stable_hash(text)})
    return {
        "scan_passed": not issues,
        "raw_leak_count": len(issues),
        "issues": issues[:50],
        "scan_scope": "stage12533_sanitized_metadata_only_countable_repair_outputs",
    }


def replacement_candidates(public_local_rows: list[dict[str, Any]], collapsed_roots: set[str]) -> list[dict[str, Any]]:
    candidates = []
    for row in public_local_rows:
        root = str(row.get("root_lineage_key_hash") or row.get("root_id_hash") or "")
        if root not in collapsed_roots:
            continue
        risks = risky_claims(row)
        controlled = truthy(row.get("controlled_fixture_like"))
        candidates.append(
            {
                "stage": STAGE,
                "candidate_ref_hash": stable_hash(row.get("row_id") or row),
                "source_stage": row.get("source_stage") or row.get("stage"),
                "root_lineage_key_hash": root,
                "language_family": row.get("language_family") or "unknown",
                "task_projection": projection(row),
                "target_semantic_value": target_value(row),
                "anti_collapse_replacement_candidate": not controlled and not risks,
                "blocked_reasons": (["controlled_fixture_like"] if controlled else []) + risks,
                "training_allowed": False,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "level3_admitted": False,
                "patch_trace_admitted": False,
                "repair_claim_admitted": False,
                "fail_to_pass_claim_admitted": False,
            }
        )
    return candidates


def count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field) or "unknown") for row in rows).items()))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    s12532 = read_json(STAGE12532_SUMMARY)
    source_rows = read_jsonl(STAGE12532_TRAIN_ROWS)
    anti12532 = read_json(STAGE12532_ANTI_COLLAPSE)
    public_local_rows = read_jsonl(STAGE12421_ROWS)

    source_groups = anti12532.get("train_support_only", {}).get("collapsed_groups", [])
    collapsed_roots = {str(group.get("root_hash")) for group in source_groups if group.get("root_hash")}

    repaired_rows = []
    demoted_rows = []
    for row in source_rows:
        repaired = dict(row)
        if str(row.get("root_lineage_key_hash")) in collapsed_roots:
            repaired["countable_train_support"] = False
            repaired["collapse_demoted_from_countable"] = True
            repaired["demotion_stage"] = STAGE
            repaired["demotion_reason"] = "legacy_train_support_anti_collapse_group"
            repaired["blocked_reasons"] = sorted(set((repaired.get("blocked_reasons") or []) + ["legacy_train_support_collapse_group_demoted"]))
            demoted_rows.append(repaired)
        else:
            repaired["collapse_demoted_from_countable"] = False
        repaired["training_allowed"] = False
        repaired["strict_eval_eligible"] = False
        repaired["source_heldout_admissible"] = False
        repaired["level3_admitted"] = False
        repaired["patch_trace_admitted"] = False
        repaired["repair_claim_admitted"] = False
        repaired["fail_to_pass_claim_admitted"] = False
        repaired_rows.append(repaired)

    replacement_rows = replacement_candidates(public_local_rows, collapsed_roots)
    replacement_rows_admissible = [row for row in replacement_rows if row["anti_collapse_replacement_candidate"]]
    post_collapse = collapse_audit([row for row in repaired_rows if truthy(row.get("countable_train_support"))])
    scan = guardrail_scan(repaired_rows, demoted_rows, replacement_rows)

    previous_total = int(s12532.get("countable_train_support_count") or 0)
    demoted_countable = sum(1 for row in demoted_rows if truthy(row.get("collapse_demoted_from_countable")))
    admitted_replacements = 0
    current_total = previous_total - demoted_countable + admitted_replacements
    remaining_gap = max(0, TARGET_TRAIN_SUPPORT_FLOOR - current_total)

    repaired_path = OUT / "train_support_only_repaired_countable_rows.jsonl"
    demoted_path = OUT / "demoted_legacy_collapse_train_support_rows.jsonl"
    replacement_path = OUT / "public_local_exact_replacement_candidates.jsonl"
    collapse_path = OUT / "post_repair_anti_collapse_audit.json"
    guardrail_path = OUT / "guardrail_scan.json"

    write_jsonl(repaired_path, repaired_rows)
    write_jsonl(demoted_path, demoted_rows)
    write_jsonl(replacement_path, replacement_rows)
    write_json(collapse_path, {"countable_train_support_after_demotions": post_collapse})
    write_json(guardrail_path, scan)

    checks = {
        "stage12532_guardrail_passed": bool(s12532.get("guardrail_scan_passed")),
        "no_raw_leak": scan["scan_passed"],
        "legacy_collapse_countable_rows_demoted": demoted_countable == 65,
        "no_remaining_countable_train_collapse_groups": post_collapse["collapse_group_count"] == 0,
        "replacement_candidates_are_exact_root_matches": all(row["root_lineage_key_hash"] in collapsed_roots for row in replacement_rows),
        "zero_level3_patch_trace_repair_credit": all(
            not truthy(row.get(field))
            for row in (repaired_rows + replacement_rows)
            for field in ("level3_admitted", "patch_trace_admitted", "repair_claim_admitted", "fail_to_pass_claim_admitted")
        ),
    }

    training_blockers = []
    if current_total < TARGET_TRAIN_SUPPORT_FLOOR:
        training_blockers.append("500_countable_train_support_floor_not_reached")
    if not checks["no_remaining_countable_train_collapse_groups"]:
        training_blockers.append("countable_train_support_collapse_groups_present")
    if not replacement_rows_admissible:
        training_blockers.append("no_exact_public_local_replacements_for_demoted_legacy_collapse_groups")
    if not all(checks.values()):
        training_blockers.append("separate_training_gate_not_passed")

    summary = {
        "stage": STAGE,
        "record_type": "legacy_collapse_group_countable_repair_v1",
        "decision": "legacy_collapsed_train_support_rows_demoted_training_still_blocked_below_500",
        "claim_boundary": (
            "Metadata-only QC repair of Stage12532 train-support inventory. Demotes legacy collapsed train-support rows "
            "from countable accounting and only reports exact public/local replacement candidates by sanitized hashes."
        ),
        "source_stage": s12532.get("stage"),
        "collapse_groups_from_stage12532": len(collapsed_roots),
        "source_train_support_rows": len(source_rows),
        "demoted_legacy_collapse_rows": len(demoted_rows),
        "demoted_collapsed_row_count": len(demoted_rows),
        "demoted_countable_train_support_rows": demoted_countable,
        "public_local_exact_replacement_candidates": len(replacement_rows),
        "replacement_candidate_count": len(replacement_rows),
        "admissible_public_local_exact_replacement_candidates": len(replacement_rows_admissible),
        "admitted_additional_train_support_rows": admitted_replacements,
        "previous_countable_train_support_count": previous_total,
        "pre_repair_collapse_group_count": len(collapsed_roots),
        "post_repair_collapse_group_count": post_collapse["collapse_group_count"],
        "post_repair_countable_train_support_count": current_total,
        "countable_train_support": {
            "stage12532_countable_total": previous_total,
            "demoted_legacy_collapse_rows": demoted_countable,
            "admitted_replacement_rows": admitted_replacements,
            "current_countable_total": current_total,
            "target_floor": TARGET_TRAIN_SUPPORT_FLOOR,
            "remaining_gap_to_500": remaining_gap,
        },
        "countable_train_support_count": current_total,
        "remaining_gap_to_500": remaining_gap,
        "bucket_language_counts_after_repair": count_by(repaired_rows, "language_family"),
        "bucket_projection_counts_after_repair": count_by(repaired_rows, "task_projection"),
        "checks": checks,
        "anti_collapse": {
            "countable_train_support_after_demotions": {
                "collapse_group_count": post_collapse["collapse_group_count"],
                "max_target_share": post_collapse["max_target_share"],
                "target_dominance_passed": post_collapse["target_dominance_passed"],
            }
        },
        "guardrail_scan_passed": scan["scan_passed"],
        "raw_leak_count": scan["raw_leak_count"],
        "level3_admitted": 0,
        "level3_admitted_rows": 0,
        "patch_trace_admitted": 0,
        "patch_trace_admitted_rows": 0,
        "patch_trace_rows": 0,
        "repair_claim_admitted_rows": 0,
        "external_repair_credit_count": 0,
        "fail_to_pass_claim_admitted_rows": 0,
        "strict_eval_eligible_count": 0,
        "strict_eval_rows": 0,
        "source_heldout_admissible_count": 0,
        "source_heldout_rows": 0,
        "training_allowed": False,
        "training_blockers": training_blockers,
        "next_stage": "expand_public_local_countable_train_support_after_collapse_repair",
        "artifact_refs": {
            "repaired_train_support_only": str(repaired_path.relative_to(ROOT)),
            "demoted_legacy_collapse_rows": str(demoted_path.relative_to(ROOT)),
            "public_local_exact_replacement_candidates": str(replacement_path.relative_to(ROOT)),
            "post_repair_anti_collapse_audit": str(collapse_path.relative_to(ROOT)),
            "guardrail_scan": str(guardrail_path.relative_to(ROOT)),
        },
        "input_hashes": {
            "stage12532_summary": file_hash(STAGE12532_SUMMARY),
            "stage12532_train_rows": file_hash(STAGE12532_TRAIN_ROWS),
            "stage12532_anti_collapse": file_hash(STAGE12532_ANTI_COLLAPSE),
            "stage12421_public_local_rows": file_hash(STAGE12421_ROWS),
        },
    }
    write_json(OUT / "legacy_collapse_group_countable_repair.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
