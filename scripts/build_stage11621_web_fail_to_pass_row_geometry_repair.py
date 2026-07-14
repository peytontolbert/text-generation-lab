#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11621
NAME = "stage11621_web_fail_to_pass_row_geometry_repair"
OUT = ART / NAME
SUMMARY = OUT / "web_fail_to_pass_row_geometry_repair.json"
REPAIRED_ROWS = OUT / "web_fail_to_pass_geometry_repaired_train_support.jsonl"
SOURCE_ROWS = ART / "stage11615_web_mutation_rows_anticheat_audit/web_mutation_rows_admitted_train_support.jsonl"

CONCRETE_TARGET_ROLE_BY_TASK = {
    "symptom_localization": "candidate_change_surface",
    "minimal_fix_selection": "candidate_change_surface",
    "patch_impact": "candidate_change_surface",
    "evidence_citation": "verifier_and_test_constraint",
    "verifier_outcome": "verifier_and_test_constraint",
}


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


def option_shuffle(options: list[dict[str, str]], seed: str) -> list[dict[str, str]]:
    def key(opt: dict[str, str]) -> str:
        raw = f"{seed}::{opt.get('semantic_role')}::{opt.get('value')}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
    labels = list("ABCDEFGH")
    return [{**opt, "label": labels[idx]} for idx, opt in enumerate(sorted(options, key=key))]


def choices_text(options: list[dict[str, str]]) -> str:
    return "\n".join(f"option {opt['label']}: {opt.get('text') or opt.get('value')}" for opt in options)


def replace_choices(prompt: str, options: list[dict[str, str]]) -> str:
    head = prompt.split("Choices:", 1)[0].rstrip()
    return f"{head}\nChoices:\n{choices_text(options)}"


def target_option(options: list[dict[str, str]], role: str) -> dict[str, str]:
    matches = [opt for opt in options if opt.get("semantic_role") == role]
    if len(matches) != 1:
        raise RuntimeError(f"expected one target role {role}, got {len(matches)}")
    return matches[0]


def repair_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    task = str(out.get("task_type") or "")
    source = dict(out.get("standalone_projection_source") or {})
    original_options = [dict(opt) for opt in source.get("opaque_options") or [] if isinstance(opt, dict)]
    if task == "abstention_insufficient_evidence":
        base_options = [
            {
                "semantic_role": "answer_with_visible_evidence",
                "value": "answer_with_visible_evidence",
                "text": "ANSWER_WITH_VISIBLE_EVIDENCE: visible source, verifier, and restored PASS evidence are sufficient",
            },
            {
                "semantic_role": "abstain_insufficient_evidence",
                "value": "ABSTAIN_INSUFFICIENT_EVIDENCE",
                "text": "ABSTAIN_INSUFFICIENT_EVIDENCE",
            },
            {
                "semantic_role": "retrieve_more",
                "value": "RETRIEVE_MORE",
                "text": "RETRIEVE_MORE",
            },
            {
                "semantic_role": "needs_verifier",
                "value": "NEEDS_VERIFIER",
                "text": "NEEDS_VERIFIER",
            },
        ]
        repaired_options = option_shuffle(base_options, f"stage11621::{out.get('root_id')}::{task}")
        target = target_option(repaired_options, "answer_with_visible_evidence")
        out["semantic_target_role"] = "answer_with_visible_evidence"
        out["semantic_target_value"] = "answer_with_visible_evidence"
    else:
        concrete_options = [
            {
                "semantic_role": str(opt.get("semantic_role") or ""),
                "value": str(opt.get("value") or ""),
                "text": str(opt.get("text") or opt.get("value") or ""),
            }
            for opt in original_options
            if str(opt.get("semantic_role") or "") != "abstain_insufficient_evidence"
        ]
        repaired_options = option_shuffle(concrete_options, f"stage11621::{out.get('root_id')}::{task}")
        target_role = CONCRETE_TARGET_ROLE_BY_TASK.get(task)
        if not target_role:
            raise RuntimeError(f"unsupported task for geometry repair: {task}")
        target = target_option(repaired_options, target_role)
        out["semantic_target_role"] = target_role
        out["semantic_target_value"] = target["value"]

    source["opaque_options"] = repaired_options
    source["option_shuffle_seed"] = f"stage11621::{out.get('root_id')}::{task}"
    source["projection_mode"] = "controlled_fail_to_pass_mutation_v2_deabstained_answerable"
    source["geometry_repair"] = {
        "removed_global_abstain_from_concrete_tasks": task != "abstention_insufficient_evidence",
        "abstention_task_uses_action_options": task == "abstention_insufficient_evidence",
    }
    out["standalone_projection_source"] = source
    out["row_id"] = f"{out.get('row_id')}::stage11621_geometry_v2"
    out["target_text"] = target["label"]
    out["decoder_text"] = target["label"]
    out["bounded_choice_target_label"] = target["label"]
    out["target"] = {
        "decoder_text": target["label"],
        "bounded_choice_target_label": target["label"],
        "semantic_value": out.get("semantic_target_value"),
    }
    out["prompt_text"] = replace_choices(str(out.get("prompt_text") or out.get("input_text") or ""), repaired_options)
    out["input_text"] = out["prompt_text"]
    anti = dict(out.get("anti_cheat") or {})
    anti["geometry_repaired_stage11621"] = True
    anti["deterministic_option_shuffle"] = True
    anti["strict_eval_eligible"] = False
    anti["requires_review_before_promotion"] = True
    out["anti_cheat"] = anti
    out["stage11621_geometry_repair"] = {
        "original_option_count": len(original_options),
        "repaired_option_count": len(repaired_options),
        "target_role": out.get("semantic_target_role"),
        "target_value": out.get("semantic_target_value"),
    }
    return out


def option_roles(row: dict[str, Any]) -> list[str]:
    return [str(opt.get("semantic_role") or "") for opt in (row.get("standalone_projection_source") or {}).get("opaque_options") or []]


def main() -> None:
    source_rows = load_jsonl(SOURCE_ROWS)
    repaired: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in source_rows:
        try:
            repaired.append(repair_row(row))
        except Exception as exc:
            bad = dict(row)
            bad["stage11621_reject_reason"] = f"{type(exc).__name__}: {exc}"
            rejected.append(bad)

    global_abstain_on_concrete = [
        row.get("row_id")
        for row in repaired
        if row.get("task_type") != "abstention_insufficient_evidence" and "abstain_insufficient_evidence" in option_roles(row)
    ]
    task_counts = Counter(str(row.get("task_type")) for row in repaired)
    target_role_counts = Counter(str(row.get("semantic_target_role")) for row in repaired)
    option_role_counts = Counter(role for row in repaired for role in option_roles(row))
    gates = {
        "all_source_rows_repaired": len(repaired) == len(source_rows) and not rejected,
        "row_count_matches_source": len(repaired) == len(source_rows) and len(repaired) > 0,
        "no_global_abstain_on_concrete_tasks": not global_abstain_on_concrete,
        "six_task_balance_preserved": len(set(task_counts.values())) == 1 and set(CONCRETE_TARGET_ROLE_BY_TASK) | {"abstention_insufficient_evidence"} <= set(task_counts),
        "strict_eval_eligible_zero": all(row.get("strict_eval_eligible_now") is False for row in repaired),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "geometry_repaired_rows_ready_for_scorer_audit" if all(gates.values()) else "geometry_repair_blocked",
        "source_rows": len(source_rows),
        "repaired_rows": len(repaired),
        "rejected_rows": len(rejected),
        "task_counts": dict(task_counts),
        "target_role_counts": dict(target_role_counts),
        "option_role_counts": dict(option_role_counts),
        "global_abstain_on_concrete_rows": global_abstain_on_concrete,
        "gates": gates,
        "claim_boundary": [
            "These are repaired controlled bug-injection train-support rows only.",
            "Concrete answerable tasks no longer include a global abstain distractor because Stage11620 showed the selected scorer collapses to abstain on that geometry.",
            "The abstention perspective is preserved as an action-sufficiency decision rather than a path-selection task.",
        ],
        "source_artifacts": {"source_rows": rel(SOURCE_ROWS)},
        "outputs": {"summary": rel(SUMMARY), "repaired_rows": rel(REPAIRED_ROWS)},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(REPAIRED_ROWS, repaired)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "gates": gates, "task_counts": summary["task_counts"], "target_role_counts": summary["target_role_counts"], "option_role_counts": summary["option_role_counts"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
