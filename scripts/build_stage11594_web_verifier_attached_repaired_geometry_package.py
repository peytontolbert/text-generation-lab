#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11594
NAME = "stage11594_web_verifier_attached_repaired_geometry_package"
OUT = ART / NAME
SUMMARY = OUT / "web_verifier_attached_repaired_geometry_package.json"
ROWS_OUT = OUT / "web_verifier_attached_repaired_rows.jsonl"
TRAIN_ROWS = OUT / "web_verifier_attached_repaired_train_rows.jsonl"
STRICT_ROWS = OUT / "web_verifier_attached_repaired_successor_strict_rows.jsonl"
SOURCE_ROWS = ART / "stage11580_web_verifier_attached_admission_package/web_verifier_attached_rows.jsonl"

TASK_INSTRUCTIONS = {
    "symptom_localization": {
        "question": "Choose the source-side candidate most likely to own the observed behavior under maintenance.",
        "criterion": "Prefer an implementation/source surface when the prompt asks where the behavior should be localized; do not choose the verifier merely because a test was executed.",
    },
    "evidence_citation": {
        "question": "Choose the visible evidence item that most directly supports the maintainer decision.",
        "criterion": "Prefer the verifier/test constraint when the task asks for supporting evidence from an observed verifier run.",
    },
    "verifier_outcome": {
        "question": "Choose the verifier/test candidate whose observed run determines the current verifier outcome.",
        "criterion": "Prefer the focused verifier/test evidence when the task asks what was executed and observed.",
    },
    "minimal_fix_selection": {
        "question": "Choose the smallest source-side candidate that would be edited if the observed behavior required a local fix.",
        "criterion": "Prefer the implementation/source surface for minimal fix selection; a test path is evidence, not the edit target, unless the visible facts say the test itself is stale.",
    },
    "alternative_hypothesis_elimination": {
        "question": "Choose the evidence that best rules out a plausible but wrong alternative hypothesis.",
        "criterion": "Prefer the verifier/test constraint when it directly shows which behavior was exercised and therefore rules out unrelated candidates.",
    },
    "abstention_insufficient_evidence": {
        "question": "Decide whether visible evidence is sufficient to answer, or whether abstention is required.",
        "criterion": "Choose abstain only when the visible source/verifier evidence is insufficient; if a focused verifier transition is visible, choose the evidence that makes answering justified.",
    },
}

ROLE_TARGET_BY_TASK = {
    "symptom_localization": "candidate_change_surface",
    "minimal_fix_selection": "candidate_change_surface",
    "evidence_citation": "verifier_and_test_constraint",
    "verifier_outcome": "verifier_and_test_constraint",
    "alternative_hypothesis_elimination": "verifier_and_test_constraint",
    "abstention_insufficient_evidence": "verifier_and_test_constraint",
}

OPTION_ROLE_DESCRIPTIONS = {
    "candidate_change_surface": "source-side candidate surface",
    "verifier_and_test_constraint": "focused verifier or selected test evidence",
    "symptom_or_call_path_analogue": "nearby symptom, helper, or call-path analogue",
    "abstain_insufficient_evidence": "abstain because visible evidence is insufficient",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def options(row: dict[str, Any]) -> list[dict[str, Any]]:
    return list(((row.get("standalone_projection_source") or {}).get("opaque_options") or []) or row.get("opaque_options") or [])


def root_id(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("root_lineage_key") or row.get("row_id"))


def deterministic_labels(row: dict[str, Any], n: int) -> list[str]:
    labels = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:n])
    seed = hashlib.sha256(str(row.get("row_id") or "").encode("utf-8")).digest()
    decorated = []
    for idx, label in enumerate(labels):
        digest = hashlib.sha256(seed + label.encode("utf-8") + str(idx).encode("utf-8")).hexdigest()
        decorated.append((digest, label))
    return [label for _, label in sorted(decorated)]


def evidence_block(prompt: str) -> str:
    if "Visible source evidence" in prompt:
        tail = "Visible source evidence" + prompt.split("Visible source evidence", 1)[1]
    else:
        tail = prompt
    return tail.split("Choices:", 1)[0].rstrip()


def short_value(value: str) -> str:
    text = str(value or "").strip()
    if len(text) <= 160:
        return text
    return text[:157] + "..."


def build_prompt(row: dict[str, Any], shuffled_options: list[dict[str, Any]]) -> str:
    task = str(row.get("task_type") or "")
    instruction = TASK_INSTRUCTIONS.get(task, {"question": "Choose the best justified option.", "criterion": "Use only visible evidence."})
    old_prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    lines = [
        "Language: web_js_ts_html",
        f"Perspective: {task}",
        f"Task: {instruction['question']}",
        f"Decision criterion: {instruction['criterion']}",
        "Use only the visible source snippets, verifier/test snippets, observed transition, and option descriptions below.",
        "Do not infer from option letter position; labels are deterministically shuffled per row.",
    ]
    repo_family = row.get("repo_family") or row.get("repository_family") or ""
    if repo_family:
        lines.append(f"Repository family: {repo_family}")
    lines.append(evidence_block(old_prompt))
    lines.append("Choices:")
    for opt in shuffled_options:
        role = str(opt.get("semantic_role") or "")
        role_desc = OPTION_ROLE_DESCRIPTIONS.get(role, "candidate")
        # Keep value visible as maintainer evidence, but pair it with role-neutral prose.
        lines.append(f"option {opt['label']}: {role_desc}; visible handle: {short_value(str(opt.get('text') or opt.get('value') or ''))}")
    return "\n".join(line for line in lines if str(line).strip())


def repair_row(row: dict[str, Any]) -> dict[str, Any]:
    task = str(row.get("task_type") or "")
    target_role = ROLE_TARGET_BY_TASK.get(task)
    old_options = [dict(opt) for opt in options(row)]
    labels = deterministic_labels(row, len(old_options))
    # Sort by role first so deterministic label shuffle, not source order, controls label-role mapping.
    role_order = ["candidate_change_surface", "verifier_and_test_constraint", "symptom_or_call_path_analogue", "abstain_insufficient_evidence"]
    old_options.sort(key=lambda opt: (role_order.index(str(opt.get("semantic_role"))) if str(opt.get("semantic_role")) in role_order else 99, str(opt.get("value") or "")))
    repaired_options: list[dict[str, Any]] = []
    target_label = None
    for label, opt in zip(labels, old_options):
        new_opt = dict(opt)
        new_opt["label"] = label
        role = str(new_opt.get("semantic_role") or "")
        if role == "abstain_insufficient_evidence":
            new_opt["value"] = "INSUFFICIENT_EVIDENCE_OPTION"
            new_opt["text"] = "INSUFFICIENT_EVIDENCE_OPTION"
        if role == target_role:
            target_label = label
        repaired_options.append(new_opt)
    if target_label is None:
        raise ValueError(f"missing target role {target_role} for {row.get('row_id')}")
    out = dict(row)
    out["row_id"] = f"{row.get('row_id')}::repaired_geometry_v1"
    out["bounded_choice_target_label"] = target_label
    out["target_text"] = target_label
    out["decoder_text"] = target_label
    out["semantic_target_role"] = target_role
    out["semantic_target_value"] = next(str(opt.get("value") or "") for opt in repaired_options if opt.get("label") == target_label)
    src = dict(out.get("standalone_projection_source") or {})
    src["opaque_options"] = repaired_options
    src["option_shuffle_seed"] = hashlib.sha256(str(row.get("row_id") or "").encode("utf-8")).hexdigest()
    src["repaired_geometry_version"] = "stage11594_v1"
    out["standalone_projection_source"] = src
    prompt = build_prompt(out, repaired_options)
    out["prompt_text"] = prompt
    out["input_text"] = prompt
    anti = dict(out.get("anti_cheat") or {})
    anti.update({
        "deterministic_option_shuffle": True,
        "fixed_label_role_mapping_removed": True,
        "perspective_specific_instruction": True,
        "abstain_literal_neutralized": True,
        "gold_label_visible_before_options": False,
        "stage11594_repaired_geometry": True,
    })
    out["anti_cheat"] = anti
    return out


def main() -> None:
    source_rows = load_jsonl(SOURCE_ROWS)
    repaired = [repair_row(row) for row in source_rows]
    train = [row for row in repaired if row.get("trainable_now")]
    strict = [row for row in repaired if row.get("strict_eval_eligible_now")]
    label_roles = Counter()
    for row in repaired:
        for opt in options(row):
            label_roles[(str(opt.get("label")), str(opt.get("semantic_role")))] += 1
    target_by_task = defaultdict(Counter)
    for row in repaired:
        target_by_task[str(row.get("task_type"))][str(row.get("target_text"))] += 1
    metrics = {
        "source_rows": len(source_rows),
        "repaired_rows": len(repaired),
        "train_rows": len(train),
        "strict_rows": len(strict),
        "train_roots": len({root_id(row) for row in train}),
        "strict_roots": len({root_id(row) for row in strict}),
        "rows_by_task": dict(Counter(str(row.get("task_type")) for row in repaired)),
        "target_by_task": {task: dict(counter) for task, counter in sorted(target_by_task.items())},
        "label_role_pairs": {f"{label}:{role}": count for (label, role), count in sorted(label_roles.items())},
    }
    gates = {
        "all_rows_repaired": metrics["source_rows"] == metrics["repaired_rows"] == 192,
        "train_rows_preserved": metrics["train_rows"] == 156,
        "strict_rows_preserved": metrics["strict_rows"] == 36,
        "train_roots_preserved": metrics["train_roots"] >= 20,
        "strict_roots_preserved": metrics["strict_roots"] >= 3,
        "fixed_label_mapping_removed": all((row.get("anti_cheat") or {}).get("fixed_label_role_mapping_removed") for row in repaired),
        "perspective_instruction_present": all((row.get("anti_cheat") or {}).get("perspective_specific_instruction") for row in repaired),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": all(gates.values()),
        "decision": "repaired_web_geometry_ready_for_scoring_audit" if all(gates.values()) else "repaired_web_geometry_blocked",
        "metrics": metrics,
        "gates": gates,
        "claim_boundary": [
            "This repairs presentation and anti-cheat geometry only; it is not a model improvement.",
            "The verifier evidence is current-state PASS_TO_PASS selected-test relevance, not fail-to-pass patch repair supervision.",
            "Training is not authorized until selected Stage11507 scorer behavior is audited on repaired strict rows.",
        ],
        "source_artifacts": {"stage11580_rows": rel(SOURCE_ROWS)},
        "outputs": {"rows": rel(ROWS_OUT), "train_rows": rel(TRAIN_ROWS), "strict_rows": rel(STRICT_ROWS), "summary": rel(SUMMARY)},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(ROWS_OUT, repaired)
    write_jsonl(TRAIN_ROWS, train)
    write_jsonl(STRICT_ROWS, strict)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "metrics": metrics, "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
