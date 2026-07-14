#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11312
NAME = "stage11312_deleaked_fail_to_pass_transition_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "deleaked_fail_to_pass_transition_package.json"

BASE = ARTIFACTS / "stage11311_residual_admissible_verifier_and_rust_package"
BASE_SPLITS = {
    "train": BASE / "residual_admissible_train_rows.jsonl",
    "validation": BASE / "residual_admissible_validation_rows.jsonl",
    "strict": BASE / "residual_admissible_strict_rows.jsonl",
    "judgment_validation": BASE / "residual_admissible_judgment_validation_rows.jsonl",
    "judgment_strict": BASE / "residual_admissible_judgment_strict_rows.jsonl",
    "residual": BASE / "residual_admissible_residual_rows.jsonl",
}
EXTERNAL = ARTIFACTS / "stage11167_external_commit_fail_to_pass_admission_audit/admitted_external_commit_fail_to_pass_rows.jsonl"

OUT_SPLITS = {
    "train": OUT_DIR / "deleaked_fail_to_pass_train_rows.jsonl",
    "validation": OUT_DIR / "deleaked_fail_to_pass_validation_rows.jsonl",
    "strict": OUT_DIR / "deleaked_fail_to_pass_strict_rows.jsonl",
    "judgment_validation": OUT_DIR / "deleaked_fail_to_pass_judgment_validation_rows.jsonl",
    "judgment_strict": OUT_DIR / "deleaked_fail_to_pass_judgment_strict_rows.jsonl",
    "residual": OUT_DIR / "deleaked_fail_to_pass_residual_rows.jsonl",
    "added_train": OUT_DIR / "added_deleaked_fail_to_pass_rows.jsonl",
    "blocked": OUT_DIR / "blocked_deleaked_fail_to_pass_rows.jsonl",
}

TRANSITIONS = ["FAIL_TO_PASS", "PASS_TO_PASS", "NOT_EXERCISED", "INSUFFICIENT_EVIDENCE"]
DESCRIPTIONS = {
    "FAIL_TO_PASS": "focused verifier is expected to fail before the repair and pass after the visible repair is recreated",
    "PASS_TO_PASS": "focused verifier is already expected to pass without requiring the visible repair",
    "NOT_EXERCISED": "focused verifier does not exercise the visible changed behavior",
    "INSUFFICIENT_EVIDENCE": "visible evidence is insufficient to determine the focused verifier transition",
}


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def target_label(row: dict[str, Any]) -> str:
    for value in [row.get("bounded_choice_target_label"), row.get("target_text"), row.get("decoder_text")]:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def gold_value(row: dict[str, Any]) -> str:
    sps = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    for value in [sps.get("gold_value"), row.get("semantic_target_value")]:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def extract_until_ledger(prompt: str) -> str:
    text = prompt.split("Verifier target ledger:", 1)[0]
    text = text.split("Options:", 1)[0]
    text = re.sub(r"^Task:.*$", "Task: Choose the semantic transition for the focused verifier target. Use the visible commit, changed-source, test-snippet, and expected-outcome evidence; do not choose by option order.", text, flags=re.MULTILINE)
    text = re.sub(r"^Verification targets from commit-plus-verify metadata:.*$", "Focused verifier target: V1 (opaque verifier; snippet and evidence shown below)", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]*tests?/[^\]]+)\]", "[V1 focused verifier snippet]", text)
    return text.strip()


def option_metadata(label: str, value: str, idx: int) -> dict[str, Any]:
    transition = value.split(" | ", 1)[0]
    return {
        "schema_version": "stage11312_transition_class_candidate_v1",
        "option_index": idx,
        "candidate_label": label,
        "candidate_value_family": "verifier_transition",
        "task_type": "verifier_outcome_semantic_transition",
        "evidence_role": "verifier_and_test_constraint",
        "verifier_transition": transition,
        "test_id": "V1",
        "value_token_count_proxy": len(value.replace("|", " ").split()),
    }


def make_options(seed: int) -> tuple[list[dict[str, Any]], str]:
    transitions = TRANSITIONS[seed % len(TRANSITIONS):] + TRANSITIONS[:seed % len(TRANSITIONS)]
    labels = ["A", "B", "C", "D"]
    options = []
    target = ""
    for idx, transition in enumerate(transitions):
        label = labels[idx]
        value = f"{transition} | {DESCRIPTIONS[transition]}"
        option = {"label": label, "value": value}
        option["semantic_candidate"] = option_metadata(label, value, idx)
        options.append(option)
        if transition == "FAIL_TO_PASS":
            target = label
    return options, target


def rewrite_row(row: dict[str, Any], idx: int) -> dict[str, Any]:
    prompt = extract_until_ledger(str(row.get("prompt_text") or row.get("input_text") or ""))
    options, target = make_options(idx)
    option_text = "\n".join(f"{opt['label']}. {opt['value']}" for opt in options)
    input_text = f"{prompt}\nTransition options:\n{option_text}\nAnswer:"
    out = dict(row)
    out["row_id"] = f"{row.get('row_id')}::deleaked_transition_class_v1"
    out["input_text"] = input_text
    out["prompt_text"] = input_text
    out["decoder_text"] = target
    out["target_text"] = target
    out["bounded_choice_target_label"] = target
    out["semantic_target_value"] = "FAIL_TO_PASS"
    out["task_type"] = "verifier_outcome_semantic_transition"
    out["split"] = "train"
    out["split_role"] = "train_support"
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["opaque_options"] = options
    sps = dict(out.get("standalone_projection_source") or {})
    sps["gold_value"] = "FAIL_TO_PASS"
    sps["opaque_options"] = options
    sps["option_semantic_schema_version"] = "stage11312_transition_class_candidate_v1"
    sps["option_semantic_records"] = [opt["semantic_candidate"] for opt in options]
    sps["projection_mode"] = "deleaked_fail_to_pass_transition_class"
    out["standalone_projection_source"] = sps
    out["semantic_candidate_schema_version"] = "stage11312_transition_class_candidate_v1"
    out["stage11312_support_provenance"] = {
        "source_manifest": rel(EXTERNAL),
        "support_role": "train_support_only",
        "repair": "rewrote path-level selected-target options into focused-verifier transition-class options",
    }
    return out


def prompt_target_leak(row: dict[str, Any]) -> list[str]:
    prompt = str(row.get("input_text") or "")
    prefix = prompt.split("Transition options:", 1)[0]
    leaks = []
    for opt in (row.get("opaque_options") or []):
        value = str(opt.get("value") or "")
        if value and value in prefix:
            leaks.append("option_value_visible_before_options")
    if "Verifier target ledger:" in prefix:
        leaks.append("old_verifier_target_ledger_still_visible")
    return leaks


def counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "roots": len({root_key(row) for row in rows}),
        "by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in rows).items())),
        "by_task": dict(sorted(Counter(str(row.get("task_type") or "unknown") for row in rows).items())),
        "by_target_label": dict(sorted(Counter(target_label(row) or "unknown" for row in rows).items())),
        "by_target_value": dict(sorted(Counter(gold_value(row) or row.get("semantic_target_value") or "unknown" for row in rows).items())),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = {split: read_jsonl(path) for split, path in BASE_SPLITS.items()}
    protected_roots = {root_key(row) for split in ("validation", "strict", "judgment_validation", "judgment_strict", "residual") for row in base[split]}
    train_roots = {root_key(row) for row in base["train"]}
    existing_ids = {str(row.get("row_id") or "") for rows in base.values() for row in rows}
    added = []
    blocked = []
    for idx, row in enumerate(read_jsonl(EXTERNAL)):
        new = rewrite_row(row, idx)
        blockers = []
        if str(new.get("row_id") or "") in existing_ids:
            blockers.append("row_id_already_present")
        if root_key(new) in protected_roots:
            blockers.append("root_overlaps_protected_split")
        if root_key(new) in train_roots:
            blockers.append("root_already_in_train")
        if len(new.get("opaque_options") or []) <= 1:
            blockers.append("singleton_or_missing_options")
        if not target_label(new):
            blockers.append("missing_target_label")
        if not any(str(opt.get("label") or "") == target_label(new) for opt in (new.get("opaque_options") or [])):
            blockers.append("target_label_not_in_options")
        blockers.extend(prompt_target_leak(new))
        if blockers:
            new["stage11312_blockers"] = blockers
            blocked.append(new)
            continue
        added.append(new)
        existing_ids.add(str(new.get("row_id") or ""))
        train_roots.add(root_key(new))

    merged_train = base["train"] + added
    out = {
        "train": merged_train,
        "validation": base["validation"],
        "strict": base["strict"],
        "judgment_validation": base["judgment_validation"],
        "judgment_strict": base["judgment_strict"],
        "residual": base["residual"],
        "added_train": added,
        "blocked": blocked,
    }
    for split, rows in out.items():
        write_jsonl(OUT_SPLITS[split], rows)
    protected_overlap = sorted({root_key(row) for row in merged_train} & protected_roots)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(added) and not blocked and not protected_overlap,
        "decision": "deleaked_fail_to_pass_transition_support_ready" if bool(added) and not blocked and not protected_overlap else "deleaked_fail_to_pass_transition_support_blocked",
        "source_artifacts": {"base_package": rel(BASE / "residual_admissible_verifier_and_rust_package.json"), "external_fail_to_pass": rel(EXTERNAL)},
        "counts": {"base_train": counts(base["train"]), "added_train": counts(added), "merged_train": counts(merged_train), "validation": counts(base["validation"]), "strict": counts(base["strict"]), "residual": counts(base["residual"]), "blocked": counts(blocked)},
        "audit": {"added_rows": len(added), "blocked_rows": len(blocked), "protected_root_overlap_count": len(protected_overlap), "protected_root_overlaps": protected_overlap, "blocker_counts": dict(sorted(Counter(reason for row in blocked for reason in row.get("stage11312_blockers", [])).items())), "prompt_target_leak_rows": sum(1 for row in added if prompt_target_leak(row))},
        "outputs": {name: rel(path) for name, path in OUT_SPLITS.items()},
        "next_action": {"recommended_stage": "stage11313_deleaked_fail_to_pass_probe_request" if bool(added) and not blocked and not protected_overlap else "repair_blocked_rows", "caveat": "This repairs Python FAIL_TO_PASS transition support only; Rust evidence anchors still need fresh non-overlapping materialization."},
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
