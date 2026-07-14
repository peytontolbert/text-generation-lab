#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11638
NAME = "stage11638_web_support_schema_normalization"
OUT = ART / NAME
SUMMARY = OUT / "web_support_schema_normalization.json"
NORMALIZED_ROWS = OUT / "web_support_normalized_rows.jsonl"
ADMITTED_ROWS = OUT / "web_support_normalized_admitted_train_rows.jsonl"
REJECTED_ROWS = OUT / "web_support_normalized_rejected_rows.jsonl"

SOURCES = {
    "stage11580_pass_to_pass": ART / "stage11580_web_verifier_attached_admission_package/web_verifier_attached_rows.jsonl",
    "stage11621_fail_to_pass": ART / "stage11621_web_fail_to_pass_row_geometry_repair/web_fail_to_pass_geometry_repaired_train_support.jsonl",
}
STAGE11637 = ART / "stage11637_web_gap_root_materialization_request/web_gap_root_materialization_request.json"
WEB_HELDOUT_ROWS = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl"

REPO_ALIASES = {
    "frontend": "openhands_openhands_frontend",
    "openhands_frontend": "openhands_openhands_frontend",
    "openhands_openhands_frontend": "openhands_openhands_frontend",
    "llama_stack_ui": "llama_stack_ui",
}
REQUIRED_TASKS = {
    "symptom_localization",
    "evidence_citation",
    "verifier_outcome",
    "minimal_fix_selection",
    "patch_impact",
    "abstention_insufficient_evidence",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def normalize_repo(value: Any, root_id: str = "") -> str:
    raw = str(value or "")
    if not raw and "openhands_openhands::frontend" in root_id:
        raw = "frontend"
    if not raw and "llama_stack::llama_stack_ui" in root_id:
        raw = "llama_stack_ui"
    return REPO_ALIASES.get(raw, raw or "unknown")


def option_roles(row: dict[str, Any]) -> set[str]:
    options = row.get("opaque_options") or (row.get("standalone_projection_source") or {}).get("opaque_options") or []
    return {str(opt.get("semantic_role") or "") for opt in options}


def selected_verifier(row: dict[str, Any]) -> str | None:
    if row.get("selected_verifier_path"):
        return str(row["selected_verifier_path"])
    evidence = row.get("verifier_evidence") or {}
    cmd = evidence.get("command") or []
    for idx, part in enumerate(cmd):
        if part == "--run" and idx + 1 < len(cmd):
            return str(cmd[idx + 1])
    options = row.get("opaque_options") or (row.get("standalone_projection_source") or {}).get("opaque_options") or []
    for opt in options:
        if opt.get("semantic_role") == "verifier_and_test_constraint":
            return str(opt.get("value") or opt.get("text") or "")
    return None


def observed_transition(row: dict[str, Any]) -> str | None:
    evidence = row.get("verifier_evidence") or {}
    return row.get("observed_verifier_transition") or row.get("verifier_transition") or evidence.get("transition") or (row.get("standalone_projection_source") or {}).get("observed_transition")


def normalize_row(row: dict[str, Any], source_name: str) -> dict[str, Any]:
    root_id = str(row.get("root_id") or "")
    repo = normalize_repo(row.get("repo_family"), root_id)
    transition = observed_transition(row)
    verifier = selected_verifier(row)
    anti = dict(row.get("anti_cheat") or {})
    anti.update(
        {
            "deterministic_option_shuffle": bool(anti.get("deterministic_option_shuffle")),
            "opaque_labels": bool(anti.get("opaque_labels")),
            "observed_verifier_transition_present": bool(transition),
            "selected_verifier_path_present": bool(verifier),
            "stage11638_schema_normalized": True,
        }
    )
    out = dict(row)
    out.update(
        {
            "stage11638_source": source_name,
            "repo_family": repo,
            "selected_verifier_path": verifier,
            "observed_verifier_transition": transition,
            "verifier_transition": transition,
            "anti_cheat": anti,
            "root_lineage_key": row.get("root_lineage_key") or root_id,
        }
    )
    return out


def blockers(row: dict[str, Any], heldout_roots: set[str]) -> list[str]:
    blocked: list[str] = []
    task = str(row.get("task_type") or "")
    roles = option_roles(row)
    anti = row.get("anti_cheat") or {}
    if not row.get("root_id") or not row.get("root_lineage_key"):
        blocked.append("missing_root_or_lineage")
    if row.get("root_id") in heldout_roots or row.get("root_lineage_key") in heldout_roots:
        blocked.append("heldout_root_overlap")
    if task not in REQUIRED_TASKS:
        blocked.append("task_not_required_for_stage11637")
    if not row.get("selected_verifier_path"):
        blocked.append("missing_selected_verifier_path")
    if not row.get("observed_verifier_transition"):
        blocked.append("missing_observed_verifier_transition")
    if not anti.get("deterministic_option_shuffle"):
        blocked.append("missing_deterministic_option_shuffle")
    if not anti.get("opaque_labels"):
        blocked.append("missing_opaque_labels")
    if anti.get("gold_label_visible_before_options") is True:
        blocked.append("gold_label_visible_before_options")
    if task == "evidence_citation":
        required_roles = {"candidate_change_surface", "verifier_and_test_constraint", "symptom_or_call_path_analogue"}
        if not required_roles.issubset(roles):
            blocked.append("missing_role_distinct_evidence_options")
    if task == "verifier_outcome" and row.get("observed_verifier_transition") not in {"PASS_TO_PASS", "FAIL_TO_PASS", "FAIL_TO_FAIL", "PASS_TO_FAIL"}:
        blocked.append("invalid_verifier_transition")
    return sorted(set(blocked))


def main() -> None:
    stage11637 = load_json(STAGE11637)
    heldout_roots = {str(row.get("root_id")) for row in load_jsonl(WEB_HELDOUT_ROWS) if row.get("root_id")}
    normalized: list[dict[str, Any]] = []
    for source_name, path in SOURCES.items():
        for row in load_jsonl(path):
            normalized.append(normalize_row(row, source_name))

    admitted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in normalized:
        row_blockers = blockers(row, heldout_roots)
        audit_row = dict(row)
        audit_row["stage11638_admission_blockers"] = row_blockers
        audit_row["stage11638_admitted_train_support"] = not row_blockers
        if row_blockers:
            rejected.append(audit_row)
        else:
            admitted.append(audit_row)

    by_repo_task = Counter((row.get("repo_family"), row.get("task_type")) for row in admitted)
    complete_roots = 0
    tasks_by_root: dict[str, set[str]] = {}
    for row in admitted:
        tasks_by_root.setdefault(str(row.get("root_id")), set()).add(str(row.get("task_type")))
    complete_roots = sum(1 for tasks in tasks_by_root.values() if REQUIRED_TASKS.issubset(tasks))

    gates = {
        "stage11637_request_ready": stage11637.get("decision") == "web_gap_materialization_request_ready",
        "normalized_rows_nonempty": bool(normalized),
        "admitted_rows_nonempty": bool(admitted),
        "has_pass_to_pass": any(row.get("observed_verifier_transition") == "PASS_TO_PASS" for row in admitted),
        "has_fail_to_pass": any(row.get("observed_verifier_transition") == "FAIL_TO_PASS" for row in admitted),
        "has_openhands": any(row.get("repo_family") == "openhands_openhands_frontend" for row in admitted),
        "has_llama": any(row.get("repo_family") == "llama_stack_ui" for row in admitted),
        "has_complete_six_task_roots": complete_roots > 0,
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "web_support_schema_normalized_admitted_train_rows_ready"
        if all(gates.values())
        else "web_support_schema_normalized_but_admission_incomplete",
        "gates": gates,
        "metrics": {
            "normalized_rows": len(normalized),
            "admitted_rows": len(admitted),
            "rejected_rows": len(rejected),
            "admitted_roots": len(tasks_by_root),
            "admitted_complete_six_task_roots": complete_roots,
            "admitted_by_source": dict(Counter(row.get("stage11638_source") for row in admitted)),
            "admitted_by_repo_family": dict(Counter(row.get("repo_family") for row in admitted)),
            "admitted_by_task_type": dict(Counter(row.get("task_type") for row in admitted)),
            "admitted_by_transition": dict(Counter(row.get("observed_verifier_transition") for row in admitted)),
            "admitted_repo_task_counts": {f"{repo}::{task}": count for (repo, task), count in sorted(by_repo_task.items())},
            "rejection_reasons": dict(Counter(reason for row in rejected for reason in row["stage11638_admission_blockers"])),
        },
        "claim_boundary": [
            "This is train-support schema normalization/admission, not a model promotion.",
            "Rows remain train-support only and must not be used as strict heldout claims.",
            "The controlled FAIL_TO_PASS rows are synthetic mutation supervision; PASS_TO_PASS rows are verifier relevance supervision.",
        ],
        "next_actions": [
            "Build a guarded probe request only if admitted rows cover the Stage11637 blocker buckets.",
            "If probing, pin CUDA_VISIBLE_DEVICES=2 and require protected canary/residual preservation.",
            "Do not claim Web superiority until same-manifest Web heldout exceeds Gemma 52/66.",
        ],
        "source_artifacts": {
            "stage11637": rel(STAGE11637),
            "web_heldout_rows": rel(WEB_HELDOUT_ROWS),
            **{f"source_{name}": rel(path) for name, path in SOURCES.items()},
        },
        "outputs": {"summary": rel(SUMMARY), "normalized_rows": rel(NORMALIZED_ROWS), "admitted_rows": rel(ADMITTED_ROWS), "rejected_rows": rel(REJECTED_ROWS)},
    }

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(NORMALIZED_ROWS, normalized)
    write_jsonl(ADMITTED_ROWS, admitted)
    write_jsonl(REJECTED_ROWS, rejected)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "gates": gates, "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
