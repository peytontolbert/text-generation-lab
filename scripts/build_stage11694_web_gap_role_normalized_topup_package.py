#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11694_web_gap_role_normalized_topup_package"
OUT = ART / NAME
SUMMARY = OUT / "web_gap_role_normalized_topup_package.json"
TOPUP_ROWS = OUT / "web_gap_role_normalized_topup_rows.jsonl"
REJECTED_ROWS = OUT / "web_gap_role_normalized_rejected_rows.jsonl"

SUPPORT = ART / "stage11693_web_gap_targeted_support_inventory/web_gap_targeted_support_rows.jsonl"
HELDOUT = ART / "stage11690_original_web_canonical_bridge_audit/original_web_canonical_bridged_rows.jsonl"
GAP = ART / "stage11692_web_bridged_miss_family_audit/web_bridged_gemma_margin_rows.jsonl"

SOURCE_LIKE_ROLES = {
    "candidate_change_surface",
    "nearby_definition_or_usage_context",
    "symptom_or_call_path_analogue",
}
TARGET_TASKS = {"symptom_localization", "minimal_fix_selection"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_lineage_key") or row.get("root_id") or row.get("row_id"))


def target_label(row: dict[str, Any]) -> str:
    return str(row.get("bounded_choice_target_label") or row.get("target_text") or (row.get("target") or {}).get("bounded_choice_target_label") or "").strip()


def option_role(option: dict[str, Any]) -> str:
    obj = option.get("canonical_candidate_object") if isinstance(option.get("canonical_candidate_object"), dict) else {}
    semantic = option.get("semantic_candidate") if isinstance(option.get("semantic_candidate"), dict) else {}
    return str(option.get("role") or obj.get("role") or semantic.get("role") or "unknown")


def set_option_role(option: dict[str, Any], role: str) -> dict[str, Any]:
    out = copy.deepcopy(option)
    old_role = option_role(out)
    out["stage11694_original_role"] = old_role
    out["role"] = role
    obj = out.get("canonical_candidate_object") if isinstance(out.get("canonical_candidate_object"), dict) else {}
    obj = dict(obj)
    obj["role"] = role
    out["canonical_candidate_object"] = obj
    semantic = out.get("semantic_candidate") if isinstance(out.get("semantic_candidate"), dict) else {}
    semantic = dict(semantic)
    semantic["role"] = role
    semantic["stage11694_original_role"] = old_role
    out["semantic_candidate"] = semantic
    value = str(out.get("value") or "")
    parts = []
    for part in value.split(";"):
        stripped = part.strip()
        if stripped.startswith("role="):
            parts.append(f"role={role}")
        elif stripped:
            parts.append(stripped)
    if parts:
        out["value"] = "; ".join(parts)
    return out


def options(row: dict[str, Any]) -> list[dict[str, Any]]:
    source = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    opts = source.get("opaque_options") if isinstance(source.get("opaque_options"), list) else row.get("opaque_options")
    return [opt for opt in opts or [] if isinstance(opt, dict)]


def target_option(row: dict[str, Any]) -> dict[str, Any] | None:
    label = target_label(row)
    for option in options(row):
        if str(option.get("label")) == label:
            return option
    return None


def no_leak(row: dict[str, Any]) -> bool:
    anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
    return (
        len(options(row)) > 1
        and anti.get("gold_label_visible_before_options") is not True
        and anti.get("no_gold_label_in_prompt_before_options") is not False
    )


def replace_options_in_prompt(prompt: str, opts: list[dict[str, Any]]) -> str:
    marker = "\nCANDIDATES\n"
    if marker not in prompt:
        return prompt
    before = prompt.split(marker, 1)[0]
    lines = [before, "CANDIDATES"]
    for option in opts:
        obj = option.get("canonical_candidate_object") if isinstance(option.get("canonical_candidate_object"), dict) else {}
        lines.append(
            f"{obj.get('candidate_id') or option.get('label')}: role={obj.get('role') or option.get('role')} | "
            f"artifact_type={obj.get('artifact_type') or option.get('artifact_type')} | "
            f"value={obj.get('value') or option.get('text')} | "
            f"evidence_ids={','.join(obj.get('artifact_refs') or [])} | text={obj.get('text') or option.get('text')}"
        )
    lines.extend(["", "QUESTION", "Choose the best candidate from the visible evidence.", "Answer:"])
    return "\n".join(lines)


def compile_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    task = str(row.get("task_type") or "")
    if task not in TARGET_TASKS:
        return None, "not_target_task"
    if not no_leak(row):
        return None, "leak_or_singleton_risk"
    tgt = target_option(row)
    if not tgt:
        return None, "missing_target_option"
    tgt_role = option_role(tgt)
    if tgt_role not in SOURCE_LIKE_ROLES:
        return None, "target_not_source_like"
    opts = options(row)
    source_like_count = sum(1 for opt in opts if option_role(opt) in SOURCE_LIKE_ROLES)
    if source_like_count < 2:
        return None, "fewer_than_two_source_like_candidates"
    new_opts = [
        set_option_role(opt, "candidate_change_surface") if option_role(opt) in SOURCE_LIKE_ROLES else copy.deepcopy(opt)
        for opt in opts
    ]
    out = copy.deepcopy(row)
    out["row_id"] = f"{row.get('row_id')}::stage11694_role_normalized_source_fix"
    out["stage11694_role_normalized_topup"] = True
    out["stage11694_source_row_id"] = row.get("row_id")
    out["stage11694_gap_need_family"] = "same_role_source_or_fix_discrimination"
    source = dict(out.get("standalone_projection_source") or {})
    source["opaque_options"] = copy.deepcopy(new_opts)
    source["projection_mode"] = "stage11694_role_normalized_source_fix_topup"
    out["standalone_projection_source"] = source
    out["opaque_options"] = copy.deepcopy(new_opts)
    out["prompt_text"] = replace_options_in_prompt(str(out.get("prompt_text") or out.get("input_text") or ""), new_opts)
    out["input_text"] = out["prompt_text"]
    out["trainable_now"] = True
    out["strict_eval_eligible_now"] = False
    out["train_support_only"] = True
    out["split"] = "train"
    out["package_split"] = "train"
    out["split_component"] = "stage11694_web_gap_role_normalized_train"
    anti = dict(out.get("anti_cheat") or {})
    anti.update(
        {
            "role_normalized_source_like_candidates": True,
            "stage11694_train_support_only": True,
            "same_root_as_bridged_web_heldout": False,
            "deterministic_option_shuffle": True,
        }
    )
    out["anti_cheat"] = anti
    return out, "admitted"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    support = load_jsonl(SUPPORT)
    heldout_roots = {root_key(row) for row in load_jsonl(HELDOUT)}
    gap_roots = {root_key(row) for row in load_jsonl(GAP)}
    admitted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    reject_reasons: Counter[str] = Counter()
    for row in support:
        reason = ""
        if root_key(row) in heldout_roots or root_key(row) in gap_roots:
            compiled = None
            reason = "heldout_or_gap_root_overlap"
        else:
            compiled, reason = compile_row(row)
        if compiled is None:
            item = {
                "row_id": row.get("row_id"),
                "root_id": row.get("root_id"),
                "task_type": row.get("task_type"),
                "repo_id": row.get("repo_id"),
                "reject_reason": reason,
            }
            rejected.append(item)
            reject_reasons[reason] += 1
            continue
        key = (root_key(compiled), str(compiled.get("task_type")), target_label(compiled))
        if key in seen:
            reject_reasons["duplicate_root_task_target"] += 1
            rejected.append({"row_id": row.get("row_id"), "root_id": row.get("root_id"), "task_type": row.get("task_type"), "reject_reason": "duplicate_root_task_target"})
            continue
        seen.add(key)
        admitted.append(compiled)
    write_jsonl(TOPUP_ROWS, admitted)
    write_jsonl(REJECTED_ROWS, rejected)
    roots = {root_key(row) for row in admitted}
    gates = {
        "topup_rows_at_least_20": len(admitted) >= 20,
        "topup_roots_at_least_10": len(roots) >= 10,
        "no_heldout_root_overlap": not (roots & heldout_roots),
        "no_gap_root_overlap": not (roots & gap_roots),
        "all_train_support_only": all(row.get("train_support_only") is True and row.get("strict_eval_eligible_now") is False for row in admitted),
    }
    decision = "role_normalized_web_gap_topup_ready" if all(gates.values()) else "role_normalized_web_gap_topup_insufficient"
    summary = {
        "stage": 11694,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "counts": {
            "input_support_rows": len(support),
            "admitted_rows": len(admitted),
            "admitted_roots": len(roots),
            "rejected_rows": len(rejected),
            "reject_reasons": dict(reject_reasons.most_common()),
            "admitted_by_task": dict(Counter(str(row.get("task_type") or "unknown") for row in admitted).most_common()),
            "admitted_by_repo": dict(Counter(str(row.get("repo_id") or row.get("repo_family") or "unknown") for row in admitted).most_common()),
            "admitted_target_labels": dict(Counter(target_label(row) for row in admitted).most_common()),
        },
        "gates": gates,
        "recommended_next": [
            "Merge these top-up rows with Stage11693 targeted support rows, then run a guarded head-only probe only if protected replay is included.",
            "Promotion requires canonical-bridged Web >56/66, filtered strict 22/22, old strict 23/23, residual >=7/10.",
            "Do not use bridged heldout rows or Gemma-margin rows as training support.",
        ],
        "claim_boundary": [
            "This package derives train-support-only same-role source/fix rows from existing disjoint canonical train roots.",
            "It normalizes source-like candidate roles for training geometry; it is not a new heldout benchmark.",
        ],
        "source_artifacts": {"support": rel(SUPPORT), "heldout": rel(HELDOUT), "gap": rel(GAP)},
        "outputs": {"summary": rel(SUMMARY), "topup_rows": rel(TOPUP_ROWS), "rejected_rows": rel(REJECTED_ROWS)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "counts": summary["counts"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
