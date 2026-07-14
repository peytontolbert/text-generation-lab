#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11668
NAME = "stage11668_web_canonical_miss_geometry_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_canonical_miss_geometry_audit.json"

AUDIT = ART / "stage11667_web_canonical_active_contrast_postrun_audit/web_canonical_active_contrast_postrun_audit.json"
CANONICAL_TRAIN = ART / "stage11663_web_canonical_renderer_package/web_canonical_train_support.jsonl"
CANONICAL_HELDOUT = ART / "stage11663_web_canonical_renderer_package/web_canonical_heldout.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def options_by_label(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    options = (((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])
    return {str(opt.get("label")): opt for opt in options if isinstance(opt, dict) and opt.get("label")}


def option_role(opt: dict[str, Any] | None) -> str:
    if not opt:
        return ""
    for key in ("semantic_role", "role", "evidence_role"):
        role = str(opt.get(key) or "").strip()
        if role:
            return role
    sem = opt.get("semantic_candidate")
    if isinstance(sem, dict):
        for key in ("role", "evidence_role"):
            role = str(sem.get(key) or "").strip()
            if role:
                return role
    obj = opt.get("canonical_candidate_object")
    if isinstance(obj, dict):
        role = str(obj.get("role") or "").strip()
        if role:
            return role
    value = str(opt.get("value") or "")
    if value.startswith("role="):
        return value.split(";", 1)[0].split("=", 1)[-1].strip()
    return value


def root_family(row: dict[str, Any]) -> str:
    rid = str(row.get("row_id") or row.get("root_id") or "")
    if "openhands" in rid:
        return "openhands"
    if "llama_stack" in rid:
        return "llama_stack"
    if "mcp_typescript_sdk" in rid:
        return "mcp_typescript_sdk"
    if "sep_automation" in rid:
        return "sep_automation"
    return str(row.get("repo_id") or row.get("repo_family") or "unknown")


def task_type(row: dict[str, Any]) -> str:
    return str(row.get("task_type") or row.get("perspective") or "unknown")


def target_label(row: dict[str, Any]) -> str:
    target = row.get("target")
    if isinstance(target, dict):
        label = str(target.get("bounded_choice_target_label") or "").strip()
        if label:
            return label
    return str(row.get("bounded_choice_target_label") or row.get("target_text") or "").strip()


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_task = Counter()
    by_family = Counter()
    by_target_role = Counter()
    by_task_target_role = Counter()
    for row in rows:
        labels = options_by_label(row)
        role = option_role(labels.get(target_label(row)))
        task = task_type(row)
        family = root_family(row)
        by_task[task] += 1
        by_family[family] += 1
        by_target_role[role] += 1
        by_task_target_role[f"{task}::{role}"] += 1
    return {
        "rows": len(rows),
        "by_task": dict(sorted(by_task.items())),
        "by_family": dict(sorted(by_family.items())),
        "by_target_role": dict(sorted(by_target_role.items())),
        "by_task_target_role": dict(sorted(by_task_target_role.items())),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    audit = load_json(AUDIT)
    train_rows = load_jsonl(CANONICAL_TRAIN)
    heldout_rows = load_jsonl(CANONICAL_HELDOUT)
    heldout_by_id = {row["row_id"]: row for row in heldout_rows}
    miss_cards = audit["results"]["canonical_heldout"]["misses"]

    enriched_misses = []
    miss_counters: dict[str, Counter[str]] = defaultdict(Counter)
    for miss in miss_cards:
        row = heldout_by_id[miss["row_id"]]
        labels = options_by_label(row)
        tgt = str(miss["target"])
        pred = str(miss["predicted"])
        target_role = option_role(labels.get(tgt))
        predicted_role = option_role(labels.get(pred))
        task = task_type(row)
        family = root_family(row)
        item = {
            "row_id": miss["row_id"],
            "task_type": task,
            "root_family": family,
            "target_label": tgt,
            "predicted_label": pred,
            "target_role": target_role,
            "predicted_role": predicted_role,
            "full_vocab_top1_text": miss.get("full_vocab_top1_text"),
            "target_rank_full_vocab": miss.get("target_rank_full_vocab"),
        }
        enriched_misses.append(item)
        miss_counters["by_task"][task] += 1
        miss_counters["by_family"][family] += 1
        miss_counters["by_target_role"][target_role] += 1
        miss_counters["by_predicted_role"][predicted_role] += 1
        miss_counters["by_task_target_role"][f"{task}::{target_role}"] += 1
        miss_counters["by_task_prediction"][f"{task}::{target_role}-> {predicted_role}"] += 1

    train_summary = summarize_rows(train_rows)
    heldout_summary = summarize_rows(heldout_rows)
    dominant_miss_families = [
        {"family": key, "misses": count}
        for key, count in miss_counters["by_task_target_role"].most_common()
        if count >= 2
    ]
    gates = {
        "canonical_heldout_above_routed_38": audit["gates"]["canonical_heldout_beats_routed_38_of_66"],
        "original_web_below_routed_38": not audit["gates"]["original_web_heldout_beats_routed_38_of_66"],
        "protected_gates_preserved": audit["preservation_ok"],
        "dominant_miss_families_identified": bool(dominant_miss_families),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "web_canonical_miss_geometry_audit_complete" if all(gates.values()) else "web_canonical_miss_geometry_audit_incomplete",
        "source_audit": rel(AUDIT),
        "train_summary": train_summary,
        "heldout_summary": heldout_summary,
        "miss_summary": {key: dict(counter) for key, counter in miss_counters.items()},
        "dominant_miss_families": dominant_miss_families,
        "enriched_misses": enriched_misses,
        "gates": gates,
        "recommended_next_package_shape": {
            "purpose": "increase canonical Web heldout above Gemma 52/66 and then restore original Web-surface transfer",
            "target_cells": dominant_miss_families,
            "minimum_rows": {
                "verifier_outcome_with_verifier_and_test_constraint_targets": 30,
                "symptom_localization_candidate_change_surface_vs_symptom_call_path": 20,
                "minimal_fix_selection_candidate_change_surface_vs_symptom_call_path": 20,
            },
            "constraints": [
                "root-disjoint from web_canonical_heldout",
                "same Stage11663 canonical renderer",
                "include original-surface and canonical-surface paired views when possible",
                "head-only training until original_web_heldout beats 38/66",
            ],
        },
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({
        "decision": summary["decision"],
        "dominant_miss_families": dominant_miss_families,
        "miss_summary": summary["miss_summary"],
        "gates": gates,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
