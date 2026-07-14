#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11318
NAME = "stage11318_alias_free_residual_evidence_item_materialization"
OUT_DIR = ARTIFACTS / NAME
SUMMARY = OUT_DIR / "alias_free_residual_evidence_item_materialization.json"
ROWS = OUT_DIR / "alias_free_residual_evidence_item_rows.jsonl"
BLOCKED = OUT_DIR / "alias_free_residual_evidence_item_blocked.jsonl"
QUEUE = ARTIFACTS / "stage11317_residual_evidence_alias_audit/residual_evidence_replacement_queue.jsonl"
RESIDUAL = ARTIFACTS / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_residual_rows.jsonl"
ROLE_ALIASES = [
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
    "external_analogue_reference",
    "algorithmic_background_reference",
    "background_context",
]
LABELS = list("ABCDEFGHIJ")


def now() -> str:
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


def root(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def gold(row: dict[str, Any]) -> str:
    sps = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    return str(sps.get("gold_value") or row.get("semantic_target_value") or "")


def prompt(row: dict[str, Any]) -> str:
    return str(row.get("prompt_text") or row.get("input_text") or "")


def parse_role_items(text: str) -> list[dict[str, str]]:
    body = text.split("Evidence:", 1)[1] if "Evidence:" in text else text.split("Visible evidence ledger:", 1)[1] if "Visible evidence ledger:" in text else ""
    body = body.split("Options:", 1)[0]
    items: list[dict[str, str]] = []
    # Case 1: role-prefixed lines: role [path]: content
    role_pat = "|".join(re.escape(role) for role in ROLE_ALIASES)
    pattern = re.compile(rf"(?ms)^({role_pat})\s*\[([^\]]+)\]:\s*(.*?)(?=^({role_pat})\s*\[[^\]]+\]:|\Z)")
    for match in pattern.finditer(body):
        items.append({"role": match.group(1), "path": match.group(2), "content": re.sub(r"\s+", " ", match.group(3)).strip()})
    if items:
        return items
    # Case 2: ledger lines, including "E01." and "Evidence item E01:" formats.
    ledger_pattern = re.compile(r"(?ms)^(?:Evidence item )?E(\d+)[\.:]\s*(.*?)(?=^(?:Evidence item )?E\d+[\.:]|\Z)")
    for match in ledger_pattern.finditer(body):
        content = re.sub(r"\s+", " ", match.group(2)).strip()
        lower = content.lower()
        if "modified implementation surface" in lower or "modified source surface" in lower or "changed surface" in lower:
            role = "candidate_change_surface"
        elif "execution verifier" in lower or "selected test" in lower or "test/verification" in lower:
            role = "verifier_and_test_constraint"
        elif "call-path" in lower or "symptom" in lower or "runtime-support analogue" in lower:
            role = "symptom_or_call_path_analogue"
        elif "runtime/api path" in lower or "related runtime" in lower:
            role = "nearby_definition_or_usage_context"
        else:
            role = "background_context"
        path_match = re.search(r"`([^`]+)`", content)
        items.append({"role": role, "path": path_match.group(1) if path_match else f"evidence_{match.group(1)}", "content": content})
    return items


def has_role_alias(text: str) -> bool:
    return any(re.search(rf"\b{re.escape(role)}\b", text) for role in ROLE_ALIASES)


def materialize(row: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    g = gold(row)
    items = parse_role_items(prompt(row))
    blockers = []
    if not items:
        blockers.append("no_evidence_items_parsed")
    matching = [idx for idx, item in enumerate(items) if item["role"] == g]
    if len(matching) != 1:
        blockers.append(f"gold_role_match_count_{len(matching)}")
    if blockers:
        return None, {"row_id": row.get("row_id"), "root_id": root(row), "gold_value": g, "blockers": blockers, "parsed_items": items[:4]}
    evidence_lines = []
    evidence_records = []
    for idx, item in enumerate(items):
        eid = f"E{idx + 1:02d}"
        clean_content = item["content"]
        for role in ROLE_ALIASES:
            clean_content = re.sub(rf"\b{re.escape(role)}\b", "evidence item", clean_content)
        evidence_lines.append(f"{eid}. Source path: {item['path']}. Snippet: {clean_content[:700]}")
        evidence_records.append((idx, eid, item))
    # Deterministic per-row option order avoids teaching or evaluating a fixed target-position shortcut.
    seed = hashlib.sha256(str(row.get("row_id") or "").encode("utf-8")).hexdigest()
    evidence_records = sorted(evidence_records, key=lambda rec: hashlib.sha256((seed + rec[1]).encode("utf-8")).hexdigest())
    options = []
    target_label = ""
    for option_index, (original_idx, eid, item) in enumerate(evidence_records):
        label = LABELS[option_index]
        value = evidence_lines[original_idx]
        opt = {
            "label": label,
            "value": value,
            "semantic_candidate": {
                "schema_version": "stage11318_alias_free_evidence_item_candidate_v1",
                "option_index": option_index,
                "candidate_label": label,
                "candidate_value_family": "opaque_evidence_item_id",
                "task_type": "evidence_citation",
                "evidence_role": item["role"],
                "verifier_transition": "NONE",
                "test_id": eid,
                "value_token_count_proxy": 1,
            },
        }
        options.append(opt)
        if original_idx == matching[0]:
            target_label = label
    task_by_gold = {
        "verifier_and_test_constraint": "Task: Choose the evidence item that contains the concrete selected-test, assertion, verifier, command-result, or expected-outcome constraint. Use the content of each item, not option order or hidden metadata.",
        "candidate_change_surface": "Task: Choose the evidence item that contains the modified source, configuration, implementation, or change surface. Use the content of each item, not option order or hidden metadata.",
        "symptom_or_call_path_analogue": "Task: Choose the evidence item that contains the symptom, call path, runtime behavior, or failure analogue rather than the changed implementation itself. Use the content of each item, not option order or hidden metadata.",
    }
    input_text = "\n".join([
        f"Language: {row.get('language_family')}",
        "Perspective: evidence_citation",
        task_by_gold.get(g, "Task: Choose the evidence item that best supports the requested maintainer decision. Use the content of each item, not option order or hidden metadata."),
        f"Repository family: {row.get('repo_family')}",
        "Visible evidence items:",
        *evidence_lines,
        "Options:",
        *[f"{opt['label']}. {opt['value']}" for opt in options],
        "Answer:",
    ])
    if has_role_alias(input_text):
        return None, {"row_id": row.get("row_id"), "root_id": root(row), "gold_value": g, "blockers": ["role_alias_still_visible_after_rewrite"]}
    out = dict(row)
    out["row_id"] = f"{row.get('row_id')}::alias_free_evidence_item_v1"
    out["input_text"] = input_text
    out["prompt_text"] = input_text
    out["decoder_text"] = target_label
    out["target_text"] = target_label
    out["bounded_choice_target_label"] = target_label
    out["semantic_target_value"] = g
    out["opaque_options"] = options
    out["strict_eval_eligible"] = False
    out["train_support_only"] = False
    sps = dict(out.get("standalone_projection_source") or {})
    sps["gold_value"] = g
    sps["gold_evidence_item_id"] = f"E{matching[0] + 1:02d}"
    sps["gold_source_role_hidden_from_prompt"] = g
    sps["opaque_options"] = options
    sps["option_semantic_schema_version"] = "stage11318_alias_free_evidence_item_candidate_v1"
    sps["evidence_items_hidden_role_metadata"] = items
    sps["projection_mode"] = "alias_free_evidence_item_selection"
    out["standalone_projection_source"] = sps
    out["stage11318_materialization"] = {"source_row_id": row.get("row_id"), "source_root_id": root(row), "claim_scope": "replacement candidate for alias-blocked scorer diagnostic residual row"}
    return out, None


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    queue_ids = {q.get("source_row_id") for q in read_jsonl(QUEUE)}
    source_rows = [row for row in read_jsonl(RESIDUAL) if row.get("row_id") in queue_ids]
    out_rows = []
    blocked = []
    for row in source_rows:
        new, block = materialize(row)
        if block:
            blocked.append(block)
        else:
            out_rows.append(new)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": bool(out_rows) and not blocked,
        "decision": "alias_free_residual_evidence_item_rows_ready" if bool(out_rows) and not blocked else "alias_free_residual_evidence_item_rows_blocked_or_partial",
        "counts": {
            "queue_rows": len(queue_ids),
            "source_rows": len(source_rows),
            "materialized_rows": len(out_rows),
            "blocked_rows": len(blocked),
            "by_language": dict(sorted(Counter(str(row.get("language_family")) for row in out_rows).items())),
            "by_gold": dict(sorted(Counter(gold(row) for row in out_rows).items())),
            "by_target_label": dict(sorted(Counter(str(row.get("target_text")) for row in out_rows).items())),
        },
        "audit": {
            "role_alias_visible_rows": sum(1 for row in out_rows if has_role_alias(prompt(row))),
            "all_rows_have_multiple_options": all(len((row.get("opaque_options") or [])) > 1 for row in out_rows),
            "all_targets_in_options": all(any(opt.get("label") == row.get("target_text") for opt in (row.get("opaque_options") or [])) for row in out_rows),
            "blocked": blocked,
        },
        "interpretation": [
            "This replaces alias-labeled evidence-role residual prompts with evidence-item selection prompts.",
            "Semantic roles remain only in hidden metadata for analysis; the prompt and option values expose opaque evidence IDs and snippets, not role aliases.",
            "These rows are replacement evaluation candidates, not train rows, until scored and reviewed against canary behavior.",
        ],
        "source_artifacts": {"queue": rel(QUEUE), "source_residual": rel(RESIDUAL)},
        "outputs": {"summary_json": rel(SUMMARY), "rows_jsonl": rel(ROWS), "blocked_jsonl": rel(BLOCKED)},
        "next_action": "stage11319_score_alias_free_residual_evidence_items_with_current_frontier",
    }
    write_jsonl(ROWS, out_rows)
    write_jsonl(BLOCKED, blocked)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
