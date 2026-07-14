#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10702
NAME = "stage10702_leak_rewrite_interface_builder"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST_JSON = OUT_DIR / "leak_rewrite_interface_builder.json"
JOBS_JSONL = OUT_DIR / "rewrite_jobs.jsonl"
DRAFT_ROWS_JSONL = OUT_DIR / "rewritten_row_drafts.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SELECTED_ROOTS = ROOT / "runs/local/artifacts/stage10701_first_multilingual_leak_rewrite_candidate_set/rewrite_candidate_roots.jsonl"
COMPILED_ROWS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_multitarget_rows.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def parse_input_text(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "repository": None,
        "query_index": None,
        "transition_target": None,
        "execution_route": None,
        "verifier_route": None,
        "changed_files": [],
        "verification_targets": [],
        "key_symbols": [],
        "task": None,
    }
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if key == "Repository":
            fields["repository"] = value
        elif key == "Query index":
            fields["query_index"] = value
        elif key == "Transition target":
            fields["transition_target"] = value
        elif key == "Execution route":
            fields["execution_route"] = value
        elif key == "Verifier route":
            fields["verifier_route"] = value
        elif key == "Changed files":
            fields["changed_files"] = [part.strip() for part in value.split(",") if part.strip()]
        elif key == "Verification targets":
            fields["verification_targets"] = [part.strip() for part in value.split(",") if part.strip()]
        elif key == "Key symbols":
            fields["key_symbols"] = [part.strip() for part in value.split(",") if part.strip()]
        elif key == "Task":
            fields["task"] = value
    return fields


def normalize_token(text: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in text).strip("_")


def parse_target_text(text: str) -> Any:
    raw = (text or "").strip()
    if not raw:
        return None
    if raw.startswith("[") and raw.endswith("]"):
        try:
            return ast.literal_eval(raw)
        except Exception:
            return raw
    return raw


def infer_decisive_bucket(target_value: Any, fields: dict[str, Any]) -> tuple[str | None, dict[str, int]]:
    entries = [str(item) for item in target_value] if isinstance(target_value, list) else [str(target_value)]
    scores = {"verification_targets": 0, "changed_files": 0, "key_symbols": 0, "repository_metadata": 0}
    normalized_entries = [normalize_token(entry) for entry in entries]
    for target in fields["verification_targets"]:
        token = normalize_token(target)
        if any(token and token in entry for entry in normalized_entries):
            scores["verification_targets"] += 1
    for path in fields["changed_files"]:
        token = normalize_token(path)
        if any(token and token in entry for entry in normalized_entries):
            scores["changed_files"] += 1
    for sym in fields["key_symbols"]:
        token = normalize_token(sym)
        if any(token and token in entry for entry in normalized_entries):
            scores["key_symbols"] += 1
    repo = fields.get("repository")
    if repo:
        token = normalize_token(str(repo))
        if any(token and token in entry for entry in normalized_entries):
            scores["repository_metadata"] += 1
    best = max(scores.values()) if scores else 0
    if best <= 0:
        return None, scores
    winners = [name for name, score in scores.items() if score == best]
    transition_target = str(fields.get("transition_target") or "")
    if len(winners) > 1:
        if transition_target == "verification_targets" and "verification_targets" in winners:
            return "verification_targets", scores
        if transition_target == "changed_files" and "changed_files" in winners:
            return "changed_files", scores
    if len(winners) != 1:
        return None, scores
    return winners[0], scores


def subtype_contract(subtype: str, fields: dict[str, Any], target_value: Any) -> tuple[list[dict[str, str]], str | None, dict[str, Any]]:
    if subtype == "decisive_evidence":
        options = [
            {"id": "A", "label": "verification_targets", "visible_evidence": ", ".join(fields["verification_targets"])},
            {"id": "B", "label": "changed_files", "visible_evidence": ", ".join(fields["changed_files"])},
            {"id": "C", "label": "key_symbols", "visible_evidence": ", ".join(fields["key_symbols"])},
            {"id": "D", "label": "repository_metadata", "visible_evidence": str(fields.get("repository") or "")},
            {"id": "E", "label": "insufficient_visible_evidence", "visible_evidence": "No visible bucket is clearly decisive."},
        ]
        inferred_label, scores = infer_decisive_bucket(target_value, fields)
        gold_id = next((opt["id"] for opt in options if opt["label"] == inferred_label), None)
        return options, gold_id, {"inference_scores": scores, "inferred_label": inferred_label}
    if subtype == "retrieve_answer_abstain":
        options = [
            {"id": "A", "label": "ANSWER_WITH_RETRIEVED_EVIDENCE", "visible_evidence": "Visible evidence is sufficient to answer now."},
            {"id": "B", "label": "RETRIEVE_MORE", "visible_evidence": "More evidence should be gathered before answering."},
            {"id": "C", "label": "ABSTAIN_INSUFFICIENT_EVIDENCE", "visible_evidence": "Visible evidence is insufficient to answer honestly."},
            {"id": "D", "label": "NEEDS_VERIFIER", "visible_evidence": "Verifier or test evidence is required to proceed."},
        ]
        target = str(target_value)
        gold_id = next((opt["id"] for opt in options if opt["label"] == target), None)
        return options, gold_id, {"direct_target_label": target}
    if subtype == "verifier_outcome":
        positive_label = str(target_value)
        negative_label = (
            positive_label.replace("PASS_", "FAIL_", 1)
            if positive_label.startswith("PASS_")
            else "FAIL_TARGETED_TEST_SELECTION"
        )
        options = [
            {"id": "A", "label": positive_label, "visible_evidence": "Visible evidence indicates the current verifier route should pass."},
            {"id": "B", "label": negative_label, "visible_evidence": "Visible evidence indicates the current verifier route should fail."},
            {"id": "C", "label": "RETRIEVE_MORE", "visible_evidence": "More evidence is needed before predicting verifier outcome."},
            {"id": "D", "label": "ABSTAIN_INSUFFICIENT_EVIDENCE", "visible_evidence": "Visible evidence does not support an honest verifier prediction."},
        ]
        gold_id = "A" if positive_label else None
        return options, gold_id, {"direct_target_label": positive_label, "negative_label": negative_label}
    return [], None, {"unsupported_subtype": subtype}


def build_prompt(fields: dict[str, Any], subtype: str, options: list[dict[str, str]]) -> str:
    header = [
        f"Repository: {fields.get('repository') or ''}",
        f"Execution route: {fields.get('execution_route') or ''}",
        f"Verifier route: {fields.get('verifier_route') or ''}",
        f"Changed files: {', '.join(fields.get('changed_files') or [])}",
        f"Verification targets: {', '.join(fields.get('verification_targets') or [])}",
        f"Key symbols: {', '.join(fields.get('key_symbols') or [])}",
    ]
    tasks = {
        "decisive_evidence": "Which visible evidence bucket is most decisive for this maintenance state?",
        "retrieve_answer_abstain": "Given the visible evidence, should the maintainer answer now, retrieve more, abstain, or require verifier evidence?",
        "verifier_outcome": "What verifier outcome is best supported by the visible evidence?",
    }
    option_lines = [f"{opt['id']}. {opt['label']} :: {opt['visible_evidence']}" for opt in options]
    return "\n".join(header + ["Task: " + tasks.get(subtype, subtype), "Options:"] + option_lines)


def main() -> None:
    selected_roots = load_jsonl(SELECTED_ROOTS)
    compiled_rows = load_jsonl(COMPILED_ROWS)

    selected_by_root = {str(row.get("root_id") or ""): row for row in selected_roots}
    rows = [row for row in compiled_rows if str(row.get("root_id") or "") in selected_by_root]

    rewrite_jobs: list[dict[str, Any]] = []
    draft_rows: list[dict[str, Any]] = []
    recoverability = Counter()
    subtype_counts = Counter()

    for row in rows:
        root_id = str(row.get("root_id") or "")
        selected_meta = selected_by_root[root_id]
        language_family = str(row.get("language_family") or selected_meta.get("language_family") or "")
        subtype = str(row.get("target_subtype") or "")
        subtype_counts[subtype] += 1
        fields = parse_input_text(str(row.get("input_text") or ""))
        target_value = parse_target_text(str(row.get("target_text") or ""))
        options, gold_id, notes = subtype_contract(subtype, fields, target_value)
        recoverability["recoverable" if gold_id else "unresolved"] += 1
        job = {
            "root_id": root_id,
            "row_id": str(row.get("row_id") or ""),
            "language_family": language_family,
            "repo_family": str(selected_meta.get("repo_family") or ""),
            "target_subtype": subtype,
            "current_target_text": row.get("target_text"),
            "rewrite_mode": (
                "bucketed_visible_evidence_contract"
                if subtype == "decisive_evidence"
                else "expanded_honest_choice_contract"
            ),
            "visible_state": fields,
            "proposed_options": options,
            "inferred_gold_option_id": gold_id,
            "rewrite_notes": notes,
            "anti_cheat_requirements": [
                "prompt_target_leak must remain false after rewrite",
                "gold option must be derivable from visible evidence only",
                "same root must remain isolated from promotable heldout claim paths",
                "candidate order must be permutable without changing semantics",
            ],
        }
        rewrite_jobs.append(job)
        draft_rows.append(
            {
                "root_id": root_id,
                "row_id": str(row.get("row_id") or "") + "::rewrite_draft_v1",
                "language_family": language_family,
                "repo_family": str(selected_meta.get("repo_family") or ""),
                "target_family": "bounded_decision",
                "target_subtype": subtype,
                "prompt_text": build_prompt(fields, subtype, options),
                "option_labels": [opt["id"] for opt in options],
                "option_values": [opt["label"] for opt in options],
                "gold_option_label": gold_id,
                "gold_resolution_status": "recoverable" if gold_id else "needs_review",
                "source_row_id": str(row.get("row_id") or ""),
                "rewrite_mode": job["rewrite_mode"],
            }
        )

    rewrite_jobs.sort(key=lambda row: (row["language_family"], row["repo_family"], row["row_id"]))
    draft_rows.sort(key=lambda row: (row["language_family"], row["repo_family"], row["row_id"]))
    write_jsonl(JOBS_JSONL, rewrite_jobs)
    write_jsonl(DRAFT_ROWS_JSONL, draft_rows)

    manifest = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "leak_rewrite_interface_builder_ready",
        "claim_scope": [
            "Convert the first multilingual quarantine rewrite batch into concrete row-level rewrite jobs and draft bounded-choice interfaces.",
            "Replace opaque target strings with visible evidence buckets or expanded honest choice contracts where the gold remains defensible.",
            "This is an interface-rewrite artifact, not a new training or evaluation result.",
        ],
        "source_artifacts": {
            "selected_roots": display(SELECTED_ROOTS),
            "compiled_multitarget_rows": display(COMPILED_ROWS),
        },
        "selected_root_count": len(selected_by_root),
        "row_counts": {
            "source_rows": len(rows),
            "rewrite_jobs": len(rewrite_jobs),
            "draft_rows": len(draft_rows),
            "subtype_counts": dict(sorted(subtype_counts.items())),
            "recoverability": dict(sorted(recoverability.items())),
        },
        "headline_findings": [
            "All selected rewrite roots map to three current subtype families only: decisive_evidence, retrieve_answer_abstain, and verifier_outcome.",
            "retrieve_answer_abstain and verifier_outcome can be rewritten directly into honest expanded-choice contracts.",
            "decisive_evidence requires bucketed visible-evidence contracts, and some rows may still need review if the opaque target overlaps multiple visible buckets.",
        ],
        "required_next_actions": [
            "Run admission/anti-cheat on the rewritten draft rows after converting draft contracts into final train/validation rows.",
            "Manually review unresolved decisive_evidence rows before counting them as promotable scale supply.",
            "Reserve fresh heldout roots before using any rewritten outputs in a new multilingual training package.",
        ],
        "recommended_next_stage": "stage10703_rewritten_multilingual_root_admission_trial",
        "outputs": {
            "rewrite_jobs": display(JOBS_JSONL),
            "rewritten_row_drafts": display(DRAFT_ROWS_JSONL),
            "manifest_json": display(MANIFEST_JSON),
        },
    }
    write_json(MANIFEST_JSON, manifest)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": manifest["decision"],
            "manifest_json": display(MANIFEST_JSON),
        },
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
