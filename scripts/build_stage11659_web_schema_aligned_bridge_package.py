#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11659
NAME = "stage11659_web_schema_aligned_bridge_package"
OUT = ART / NAME
MANIFEST = OUT / "web_schema_aligned_bridge_manifest.jsonl"
SUMMARY = OUT / "web_schema_aligned_bridge_package.json"

SOURCE_ROWS = ART / "stage11648_web_gap_grouped_admission_compiler/web_gap_grouped_probe_manifest.jsonl"
TRANSFER_AUDIT = ART / "stage11658_web_head_transfer_gap_audit/web_head_transfer_gap_audit.json"

ROLE_DESCRIPTIONS = {
    "candidate_change_surface": "implementation/source candidate evidence",
    "verifier_and_test_constraint": "focused verifier/test evidence",
    "symptom_or_call_path_analogue": "nearby symptom, helper, or call-path analogue",
    "abstain_insufficient_evidence": "insufficient visible evidence option",
}

TASK_INSTRUCTIONS = {
    "symptom_localization": "Choose the implementation target most directly responsible for the observed verifier behavior.",
    "evidence_citation": "Choose the visible fact that most directly supports the maintainer decision.",
    "verifier_outcome": "Choose the verifier/test candidate whose observed run determines the current outcome.",
    "minimal_fix_selection": "Choose the smallest source-side fix target supported by the visible evidence.",
    "alternative_hypothesis_elimination": "Choose the alternative that the visible evidence most strongly eliminates.",
    "abstention_insufficient_evidence": "Choose whether the visible source and verifier evidence is sufficient to answer.",
}


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def section(prompt: str, start: str, ends: list[str]) -> str:
    if start not in prompt:
        return ""
    tail = prompt.split(start, 1)[1]
    end_indexes = [tail.find(marker) for marker in ends if marker in tail]
    end_indexes = [idx for idx in end_indexes if idx >= 0]
    if end_indexes:
        tail = tail[: min(end_indexes)]
    return tail.strip()


def verifier_execution_text(row: dict[str, Any]) -> str:
    evidence = row.get("verifier_evidence") if isinstance(row.get("verifier_evidence"), dict) else {}
    command = evidence.get("command")
    if isinstance(command, list):
        command_text = " ".join(str(part) for part in command)
    else:
        command_text = str(command or row.get("selected_verifier_path") or "UNKNOWN_VERIFIER")
    status = str(evidence.get("status") or "verifier_status_unknown")
    transition = str(evidence.get("transition") or row.get("observed_verifier_transition") or "UNKNOWN_TRANSITION")
    log_path = str(evidence.get("log_path") or "")
    if log_path:
        return f"Executed focused verifier: {command_text}; result: {status}; transition: {transition}. Log artifact: {log_path}."
    return f"Executed focused verifier: {command_text}; result: {status}; transition: {transition}."


def option_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    source = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    options = source.get("opaque_options") if isinstance(source.get("opaque_options"), list) else row.get("opaque_options")
    return [dict(option) for option in options if isinstance(option, dict)]


def option_sentence(task: str, role: str, handle: str) -> str:
    clean = handle if handle and handle != "ABSTAIN_INSUFFICIENT_EVIDENCE" else "ABSTAIN_INSUFFICIENT_EVIDENCE"
    if role == "candidate_change_surface":
        if task == "evidence_citation":
            return f"The implementation/source snippet at {clean} is the candidate change surface."
        return f"The source-side implementation candidate is {clean}."
    if role == "verifier_and_test_constraint":
        return f"The focused verifier/test evidence is {clean} and its observed run constrains the answer."
    if role == "symptom_or_call_path_analogue":
        return f"The nearby symptom, helper, or call-path analogue is {clean}."
    if role == "abstain_insufficient_evidence":
        return "ABSTAIN_INSUFFICIENT_EVIDENCE"
    return f"{ROLE_DESCRIPTIONS.get(role, role)}: {clean}"


def aligned_options(row: dict[str, Any]) -> list[dict[str, Any]]:
    task = str(row.get("task_type") or "")
    aligned: list[dict[str, Any]] = []
    for option in option_rows(row):
        role = str(option.get("semantic_role") or "")
        handle = str(option.get("text") or option.get("value") or "")
        new_option = dict(option)
        new_option["text"] = option_sentence(task, role, handle)
        if task == "evidence_citation":
            new_option["value"] = role or str(option.get("value") or "")
        else:
            new_option["value"] = str(option.get("value") or handle)
        new_option["schema_aligned_bridge"] = True
        aligned.append(new_option)
    return aligned


def render_prompt(row: dict[str, Any], options: list[dict[str, Any]]) -> str:
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    source_evidence = section(
        prompt,
        "Visible source evidence (opaque source IDs):",
        ["Visible verifier/test evidence (opaque verifier IDs):", "Observed verifier transition:", "Choices:"],
    )
    verifier_evidence = section(
        prompt,
        "Visible verifier/test evidence (opaque verifier IDs):",
        ["Observed verifier transition:", "Verifier log excerpt:", "Choices:"],
    )
    log_excerpt = section(prompt, "Verifier log excerpt:", ["Choices:"])
    source_evidence = source_evidence or section(prompt, "Visible source evidence:", ["Visible verifier/test evidence:", "Choices:"])
    verifier_evidence = verifier_evidence or section(prompt, "Visible verifier/test evidence:", ["Visible verifier execution evidence:", "Choices:"])
    task = str(row.get("task_type") or "unknown")
    instruction = TASK_INSTRUCTIONS.get(task, "Choose the best maintainer decision from the visible evidence.")
    lines = [
        f"Language: {row.get('language_family') or 'web_js_ts_html'}",
        f"Perspective: {task}",
        instruction,
        f"Repository family: {row.get('repo_family') or row.get('git_repo_family') or 'unknown'}",
        "Task observation:",
        f"Verifier-backed maintainer root {row.get('root_id') or row.get('root_lineage_key') or 'unknown'} requires the selected perspective decision.",
        "Visible source evidence:",
        source_evidence[:2600],
        "Visible verifier/test evidence:",
        verifier_evidence[:2200],
        "Visible verifier execution evidence:",
        verifier_execution_text(row),
    ]
    if log_excerpt:
        lines.extend(["Verifier log excerpt:", log_excerpt[:1400]])
    lines.append("Options:")
    for option in options:
        lines.append(f"{option.get('label')}. {option.get('text')}")
    lines.append("Answer:")
    return "\n".join(str(line).rstrip() for line in lines if str(line).strip())


def has_label_leak(row: dict[str, Any]) -> bool:
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    before_options = prompt.split("Options:", 1)[0]
    target = str(row.get("bounded_choice_target_label") or row.get("target_text") or "")
    return bool(target and re.search(rf"\boption\s+{re.escape(target)}\b", before_options, flags=re.IGNORECASE))


def transform(row: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(row)
    options = aligned_options(out)
    source = dict(out.get("standalone_projection_source") or {})
    source["opaque_options"] = options
    source["projection_mode"] = "stage11659_web_schema_aligned_bridge"
    source["option_value_alignment"] = "heldout_style_semantic_values_for_evidence_rows"
    out["standalone_projection_source"] = source
    out["opaque_options"] = copy.deepcopy(options)
    out["prompt_text"] = render_prompt(out, options)
    out["input_text"] = out["prompt_text"]
    out["stage11659_schema_aligned_bridge"] = True
    out["schema_alignment_source_row_id"] = row.get("row_id")
    out["row_id"] = f"{row.get('row_id')}::stage11659_schema_aligned"
    out["split"] = "train"
    out["package_split"] = "train"
    out["split_component"] = "train_schema_aligned_bridge"
    out["strict_eval_eligible_now"] = False
    out["trainable_now"] = True
    anti_cheat = dict(out.get("anti_cheat") or {})
    anti_cheat.update(
        {
            "deterministic_option_shuffle": True,
            "gold_label_visible_before_options": False,
            "no_gold_label_in_prompt_before_options": not has_label_leak(out),
            "schema_aligned_with_web_heldout_style": True,
        }
    )
    out["anti_cheat"] = anti_cheat
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_rows = load_jsonl(SOURCE_ROWS)
    bridge_rows = [transform(row) for row in source_rows]
    write_jsonl(MANIFEST, bridge_rows)
    task_counts = Counter(str(row.get("task_type") or "unknown") for row in bridge_rows)
    repo_counts = Counter(str(row.get("repo_family") or row.get("git_repo_family") or "unknown") for row in bridge_rows)
    option_value_styles = Counter()
    evidence_value_counts = Counter()
    leak_rows = []
    for row in bridge_rows:
        if has_label_leak(row):
            leak_rows.append(row.get("row_id"))
        for option in option_rows(row):
            value = str(option.get("value") or "")
            if row.get("task_type") == "evidence_citation":
                evidence_value_counts[value] += 1
            if value in ROLE_DESCRIPTIONS:
                option_value_styles["semantic_role"] += 1
            elif re.search(r"\.(tsx?|jsx?|html|css|json|md)\b", value):
                option_value_styles["path_or_symbol_handle"] += 1
            else:
                option_value_styles["other"] += 1

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "web_schema_aligned_bridge_package_ready_for_diagnostic_probe",
        "source_rows": rel(SOURCE_ROWS),
        "transfer_audit": rel(TRANSFER_AUDIT),
        "manifest": rel(MANIFEST),
        "counts": {
            "rows": len(bridge_rows),
            "unique_roots": len({str(row.get("root_lineage_key") or row.get("root_id")) for row in bridge_rows}),
            "task_counts": dict(task_counts.most_common()),
            "repo_counts": dict(repo_counts.most_common()),
            "option_value_styles": dict(option_value_styles.most_common()),
            "evidence_value_counts": dict(evidence_value_counts.most_common()),
            "prompt_label_leak_rows": len(leak_rows),
        },
        "leak_examples": leak_rows[:20],
        "probe_recommendation": {
            "next_stage": "stage11660_web_schema_aligned_bridge_head_only_probe_request",
            "initialization": "stage11507 selected frontier",
            "sampler": "web_gap_same_root_grouped",
            "scorer": "encoder_option_retrieval_web_task_candidate_head",
            "head_only_first": True,
            "promotion_boundary": "diagnostic only unless Web heldout >38/66 and protected routed gates hold",
        },
        "claim_boundary": [
            "This package is train-support only and reuses Stage11648 roots.",
            "It is designed to test schema alignment, not to establish new heldout performance.",
            "OpenHands/Llama heldout rows remain untouched.",
        ],
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "counts": summary["counts"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
