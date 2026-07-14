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

STAGE = 11479
NAME = "stage11479_materialized_rust_symptom_call_path_rows"
OUT = ART / NAME
SUMMARY = OUT / "materialized_rust_symptom_call_path_rows.json"
ROWS = OUT / "materialized_rust_symptom_call_path_rows.jsonl"
ADMITTED = OUT / "admitted_materialized_rust_symptom_call_path_rows.jsonl"
BLOCKED = OUT / "blocked_materialized_rust_symptom_call_path_rows.jsonl"

WORK_ITEMS = ART / "stage11478_rust_symptom_call_path_materialization_queue/rust_symptom_call_path_materialization_work_items.jsonl"
ROW_AUDIT = ART / "stage11453_rust_materialized_support_readiness_audit_v3/rust_materialized_support_row_audit.jsonl"

OPTION_VALUES = [
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "insufficient_or_background_context",
]
TARGET_VALUE = "symptom_or_call_path_analogue"
LABELS = list("ABCD")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def root_id(row: dict[str, Any]) -> str:
    return str(row.get("root_lineage_key") or row.get("root_id") or row.get("source_root_id") or row.get("row_id"))


def load_source_rows(row_audit_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    paths = sorted({row.get("source_artifact") for row in row_audit_rows if row.get("source_artifact")})
    by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path_text in paths:
        path = ROOT / str(path_text)
        for row in iter_jsonl(path):
            rid = root_id(row)
            row["_source_artifact"] = str(path_text)
            by_root[rid].append(row)
    return by_root


def evidence_text(row: dict[str, Any]) -> str:
    source = row.get("standalone_projection_source") or {}
    return str(source.get("candidate_evidence_text") or "")


def excerpt(text: str, limit: int = 820) -> str:
    clean = " ".join(text.strip().split())
    return clean[:limit] + ("..." if len(clean) > limit else "")


def option_permutation(seed: str) -> list[dict[str, str]]:
    values = list(OPTION_VALUES)
    values.sort(key=lambda value: hashlib.sha256(f"{seed}::{value}".encode()).hexdigest())
    return [{"label": LABELS[idx], "value": value} for idx, value in enumerate(values)]


def choose_role_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    role_rows: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row.get("semantic_target_value")
        kind = (row.get("standalone_projection_source") or {}).get("candidate_evidence_kind") or ""
        if value == "SUPPORTING_CANDIDATE_CHANGE_SURFACE" and "candidate" not in role_rows:
            role_rows["candidate"] = row
        if value in {"DECISIVE_SELECTED_TEST_CONSTRAINT", "DECISIVE_VERIFIER_TEST_CONSTRAINT"} and "verifier" not in role_rows:
            role_rows["verifier"] = row
        if value in {"OBSERVED_VERIFIER_LOG", "OBSERVED_VERIFIER_PASS_LOG", "OBSERVED_VERIFIER_FAILURE_LOG"} and "symptom" not in role_rows:
            role_rows["symptom"] = row
        if value in {"DISTRACTOR_BACKGROUND_CONTEXT", "DECISIVE_BUILD_VERIFIER_CONSTRAINT"} and "background" not in role_rows:
            role_rows["background"] = row
        if kind in {"actual_verifier_log", "actual_verifier_pass_log"} and "symptom" not in role_rows:
            role_rows["symptom"] = row
    return role_rows


def fingerprint(text: str) -> str:
    clean = " ".join(text.lower().split())
    return hashlib.sha256(clean[:500].encode()).hexdigest()


def make_row(work_item: dict[str, Any], role_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rid = work_item["root_lineage_key"]
    repo = work_item["repo_family"]
    candidate_text = evidence_text(role_rows["candidate"])
    verifier_text = evidence_text(role_rows["verifier"])
    symptom_text = evidence_text(role_rows["symptom"])
    background_text = evidence_text(role_rows.get("background", role_rows["verifier"]))
    options = option_permutation(rid)
    label_by_value = {option["value"]: option["label"] for option in options}
    target_label = label_by_value[TARGET_VALUE]
    evidence = {
        "candidate_change_surface": f"candidate_change_surface: {excerpt(candidate_text)}",
        "verifier_and_test_constraint": f"verifier_and_test_constraint: {excerpt(verifier_text)}",
        "symptom_or_call_path_analogue": f"symptom_or_call_path_analogue: observed verifier/call-path analogue for this root: {excerpt(symptom_text)}",
        "insufficient_or_background_context": f"insufficient_or_background_context: contextual material that is not the decisive symptom/call-path support: {excerpt(background_text, limit=360)}",
    }
    prompt = (
        "Language: rust\n"
        "Perspective: evidence_citation\n"
        "Task: choose the visible evidence item that best supports the symptom or call-path analogue for this Rust maintenance root. "
        "Do not default to the changed source surface; use the evidence role and content.\n"
        f"Repository family: {repo}\n"
        f"Root lineage: {rid}\n\n"
        "Visible evidence ledger:\n"
        f"E01. {evidence['candidate_change_surface']}\n"
        f"E02. {evidence['verifier_and_test_constraint']}\n"
        f"E03. {evidence['symptom_or_call_path_analogue']}\n"
        f"E04. {evidence['insufficient_or_background_context']}\n\n"
        "Options:\n"
        + "\n".join(f"{option['label']}. {option['value']}" for option in options)
        + "\nAnswer:"
    )
    return {
        "row_id": f"stage11479::{rid}::symptom_or_call_path_analogue",
        "root_id": rid,
        "root_lineage_key": rid,
        "repo_family": repo,
        "repo_id": repo,
        "language_family": "rust",
        "task_type": "evidence_citation",
        "split": "train",
        "package_split": "train",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "surface": "residual50_rust_symptom_call_path_materialized_bounded_choice",
        "input_text": prompt,
        "prompt_text": prompt,
        "target_text": target_label,
        "decoder_text": target_label,
        "bounded_choice_target_label": target_label,
        "target_token_len": 1,
        "expected_enabled_loss": "decoder_ce",
        "disable_losses": [],
        "loss_mask": {"decoder_ce": True},
        "opaque_options": options,
        "target": {
            "decoder_text": target_label,
            "target_text": target_label,
            "bounded_choice_target_label": target_label,
        },
        "semantic_target_value": TARGET_VALUE,
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "opaque_labels": True,
            "train_support_only": True,
            "strict_eval_eligible": False,
            "source_text_materialized": True,
            "selected_test_or_verifier_anchor_present": True,
            "candidate_change_surface_hard_negative_present": True,
            "candidate_and_symptom_text_distinct": fingerprint(candidate_text) != fingerprint(symptom_text),
            "reserved_eval_lineage_excluded": True,
        },
        "standalone_projection_source": {
            "projection_mode": "stage11479_rust_symptom_call_path_materialization",
            "gold_value": TARGET_VALUE,
            "gold_label": target_label,
            "opaque_options": options,
            "evidence_facts": evidence,
            "source_rows": {
                "candidate": role_rows["candidate"].get("row_id"),
                "verifier": role_rows["verifier"].get("row_id"),
                "symptom": role_rows["symptom"].get("row_id"),
                "background": role_rows.get("background", role_rows["verifier"]).get("row_id"),
            },
            "source_artifacts": sorted(
                {
                    str(role_rows["candidate"].get("_source_artifact")),
                    str(role_rows["verifier"].get("_source_artifact")),
                    str(role_rows["symptom"].get("_source_artifact")),
                }
            ),
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    work_items = iter_jsonl(WORK_ITEMS)
    row_audit = iter_jsonl(ROW_AUDIT)
    source_rows = load_source_rows(row_audit)
    rows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for work_item in work_items:
        rid = work_item["root_lineage_key"]
        role_rows = choose_role_rows(source_rows.get(rid, []))
        missing = [role for role in ["candidate", "verifier", "symptom"] if role not in role_rows]
        if missing:
            blocked.append({"root_lineage_key": rid, "repo_family": work_item["repo_family"], "block_reasons": [f"missing_{role}_row" for role in missing]})
            continue
        row = make_row(work_item, role_rows)
        reasons = []
        if not row["anti_cheat"]["candidate_and_symptom_text_distinct"]:
            reasons.append("candidate_and_symptom_text_alias")
        if len(row.get("opaque_options") or []) != 4:
            reasons.append("wrong_option_count")
        prompt = row["input_text"]
        if "symptom_or_call_path_analogue" not in prompt or "candidate_change_surface" not in prompt:
            reasons.append("missing_required_visible_roles")
        if reasons:
            blocked_row = dict(row)
            blocked_row["block_reasons"] = reasons
            blocked.append(blocked_row)
        else:
            rows.append(row)

    write_jsonl(ROWS, rows + blocked)
    write_jsonl(ADMITTED, rows)
    write_jsonl(BLOCKED, blocked)
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": len(rows) == len(work_items) and not blocked,
        "decision": "rust_symptom_call_path_rows_admitted"
        if len(rows) == len(work_items) and not blocked
        else "rust_symptom_call_path_rows_incomplete_or_blocked",
        "metrics": {
            "work_items": len(work_items),
            "materialized_rows": len(rows),
            "blocked_rows": len(blocked),
            "admitted_unique_roots": len({row["root_id"] for row in rows}),
            "admitted_by_repo": dict(sorted(Counter(row["repo_family"] for row in rows).items())),
        },
        "source_artifacts": {
            "work_items": rel(WORK_ITEMS),
            "row_audit": rel(ROW_AUDIT),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "rows": rel(ROWS),
            "admitted": rel(ADMITTED),
            "blocked": rel(BLOCKED),
        },
    }
    write_json(SUMMARY, payload)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
