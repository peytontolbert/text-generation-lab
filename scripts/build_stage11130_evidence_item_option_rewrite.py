#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11130
NAME = "stage11130_evidence_item_option_rewrite"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "evidence_item_option_rewrite.json"
ROWS_JSONL = OUT_DIR / "evidence_item_option_rows.jsonl"
AUDIT_JSON = OUT_DIR / "evidence_item_option_audit.json"

SOURCE_ROWS = ARTIFACTS / "stage11114_fresh_family_support_package_with_trainable_admitted_evidence" / "added_admitted_evidence_rows_trainable.jsonl"
ROLE_TO_EVIDENCE_ID = {
    "candidate_change_surface": "E01",
    "nearby_definition_or_usage_context": "E02",
    "symptom_or_call_path_analogue": "E03",
    "verifier_and_test_constraint": "E04",
}
ROLE_NAMES = set(ROLE_TO_EVIDENCE_ID)
LABELS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
LEDGER_PATTERN = re.compile(r"^(E\d{2})\.\s*(.+)$")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def split_prompt(prompt: str) -> tuple[str, str]:
    marker = "\nOptions:\n"
    if marker not in prompt:
        raise ValueError("prompt missing Options marker")
    prefix, rest = prompt.split(marker, 1)
    if "\nAnswer:" not in rest:
        raise ValueError("prompt missing Answer marker")
    return prefix.rstrip(), rest.split("\nAnswer:", 1)[1]


def parse_ledger(prefix: str) -> dict[str, str]:
    ledger: dict[str, str] = {}
    for line in prefix.splitlines():
        match = LEDGER_PATTERN.match(line.strip())
        if match:
            ledger[match.group(1)] = match.group(2).strip()
    return ledger


def has_role_name(text: str) -> bool:
    return any(role in text for role in ROLE_NAMES)


def rewrite_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    if str(row.get("task_type") or "") != "evidence_citation":
        return None, "not_evidence_citation"
    source = dict(row.get("standalone_projection_source") or {})
    gold_role = str(source.get("gold_value") or "")
    gold_evidence_id = ROLE_TO_EVIDENCE_ID.get(gold_role)
    if not gold_evidence_id:
        return None, "missing_gold_evidence_id"
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    prefix, _answer_tail = split_prompt(prompt)
    ledger = parse_ledger(prefix)
    missing = [eid for eid in ROLE_TO_EVIDENCE_ID.values() if eid not in ledger]
    if missing:
        return None, f"missing_ledger::{','.join(missing)}"

    option_order = []
    original_options = ((row.get("standalone_projection_source") or {}).get("opaque_options")) or row.get("opaque_options") or []
    for option in original_options:
        role = str((option or {}).get("value") or "")
        evidence_id = ROLE_TO_EVIDENCE_ID.get(role)
        if evidence_id and evidence_id not in option_order:
            option_order.append(evidence_id)
    for evidence_id in ROLE_TO_EVIDENCE_ID.values():
        if evidence_id not in option_order:
            option_order.append(evidence_id)

    opaque_options = []
    option_lines = []
    target_label = None
    for idx, evidence_id in enumerate(option_order):
        label = LABELS[idx]
        value = f"{evidence_id}: {ledger[evidence_id]}"
        opaque_options.append({"label": label, "value": value, "evidence_id": evidence_id})
        option_lines.append(f"{label}. {value}")
        if evidence_id == gold_evidence_id:
            target_label = label
    if target_label is None:
        return None, "target_label_not_found"

    new_prompt = prefix + "\nOptions:\n" + "\n".join(option_lines) + "\nAnswer:\n"
    if has_role_name(new_prompt):
        return None, "role_name_leak_after_rewrite"
    if has_role_name(json.dumps(opaque_options, sort_keys=True)):
        return None, "option_role_name_leak_after_rewrite"

    rewritten = dict(row)
    rewritten["row_id"] = str(row.get("row_id")) + "::evidence_item_options_v1"
    rewritten["prompt_text"] = new_prompt
    rewritten["input_text"] = new_prompt
    rewritten["decoder_text"] = target_label
    rewritten["target_text"] = target_label
    rewritten["opaque_options"] = opaque_options
    projection = dict(row.get("standalone_projection_source") or {})
    projection.update({
        "projection_mode": "stage11130_evidence_item_option_rewrite",
        "gold_role_value_hidden": True,
        "gold_evidence_id": gold_evidence_id,
        "gold_evidence_text": ledger[gold_evidence_id],
        "opaque_options": opaque_options,
    })
    projection.pop("gold_value", None)
    rewritten["standalone_projection_source"] = projection
    anti = dict(row.get("anti_cheat") or {})
    anti.update({
        "role_name_leak_removed": True,
        "role_names_removed_from_options": True,
        "evidence_item_options": True,
        "option_values_are_visible_evidence_descriptions": True,
        "same_surface_eval_admissible": False,
        "requires_review_before_training": True,
    })
    rewritten["anti_cheat"] = anti
    rewritten["split"] = "train"
    rewritten["split_role"] = "support_only_evidence_item_options"
    rewritten["train_support_only"] = True
    rewritten["strict_eval_eligible"] = False
    return rewritten, None


def main() -> None:
    source_rows = load_jsonl(SOURCE_ROWS)
    rewritten_rows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for row in source_rows:
        try:
            rewritten, reason = rewrite_row(row)
        except Exception as exc:  # noqa: BLE001 - audit records construction failure.
            rewritten, reason = None, f"exception::{type(exc).__name__}::{exc}"
        if rewritten is None:
            blocked.append({"row_id": row.get("row_id"), "reason": reason})
        else:
            rewritten_rows.append(rewritten)

    prompt_role_leaks = [row["row_id"] for row in rewritten_rows if has_role_name(str(row.get("prompt_text") or ""))]
    option_role_leaks = [row["row_id"] for row in rewritten_rows if has_role_name(json.dumps(row.get("opaque_options") or [], sort_keys=True))]
    target_leaks = [row["row_id"] for row in rewritten_rows if str((row.get("standalone_projection_source") or {}).get("gold_evidence_id") or "") not in str(row.get("prompt_text") or "")]
    label_counts: dict[str, int] = {}
    repo_counts: dict[str, int] = {}
    lang_counts: dict[str, int] = {}
    for row in rewritten_rows:
        label_counts[str(row.get("target_text"))] = label_counts.get(str(row.get("target_text")), 0) + 1
        repo_counts[str(row.get("repo_family"))] = repo_counts.get(str(row.get("repo_family")), 0) + 1
        lang_counts[str(row.get("language_family"))] = lang_counts.get(str(row.get("language_family")), 0) + 1

    passed = bool(rewritten_rows) and not prompt_role_leaks and not option_role_leaks and not target_leaks
    audit = {
        "source_rows": len(source_rows),
        "rewritten_rows": len(rewritten_rows),
        "blocked_rows": len(blocked),
        "prompt_role_leak_rows": prompt_role_leaks,
        "option_role_leak_rows": option_role_leaks,
        "gold_evidence_id_not_visible_rows": target_leaks,
        "target_label_counts": label_counts,
        "by_repo_family": repo_counts,
        "by_language": lang_counts,
        "blocked": blocked[:50],
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": passed,
        "decision": "evidence_item_option_rows_ready_for_support_package" if passed else "evidence_item_option_rows_blocked",
        "claim_scope": [
            "Rewrite fresh-family evidence support rows so answer options are visible evidence ledger items rather than semantic role names.",
            "Prevent the model/scorer from solving evidence citation by memorizing role aliases such as verifier_and_test_constraint or candidate_change_surface.",
        ],
        "source_artifacts": {"source_rows": rel(SOURCE_ROWS)},
        "metrics": audit,
        "next_best_step": "Package these rows with stage11114 and run one scorer probe only if the rewrite has zero role-name leaks and no heldout overlap.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "rows_jsonl": rel(ROWS_JSONL),
            "audit_json": rel(AUDIT_JSON),
        },
    }
    write_jsonl(ROWS_JSONL, rewritten_rows)
    write_json(AUDIT_JSON, audit)
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
