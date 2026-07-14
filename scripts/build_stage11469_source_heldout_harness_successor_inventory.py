#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"

STAGE = 11469
NAME = "stage11469_source_heldout_harness_successor_inventory"
OUT = ART / NAME
SUMMARY = OUT / "source_heldout_harness_successor_inventory.json"
ROW_AUDIT = OUT / "source_heldout_harness_successor_row_audit.jsonl"
ADMITTED = OUT / "source_heldout_harness_successor_admitted_candidates.jsonl"
QUEUE = OUT / "source_heldout_harness_successor_repair_queue.jsonl"

LANGUAGES = ("python", "rust", "c_cpp", "web_js_ts_html")
TARGET_TASKS = {
    "symptom_localization",
    "evidence_citation",
    "minimal_fix_selection",
    "patch_impact",
    "verifier_outcome",
    "verifier_outcome_semantic_transition",
    "abstention_insufficient_evidence",
}
ROW_FILE_RE = re.compile(
    r"(agentkernel_lite_encdec_(?:strict_eval|validation|stress_eval|train)|"
    r"support_rows|candidate_rows|heldout_candidate_rows|strict_candidates|successor).*\.jsonl$"
)
EXCLUDE_STAGE_RE = re.compile(r"stage1146[3-8]_")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def iter_candidate_files() -> list[Path]:
    files = []
    for path in ART.rglob("*.jsonl"):
        display = rel(path)
        if EXCLUDE_STAGE_RE.search(display):
            continue
        if ROW_FILE_RE.search(path.name) or "reviewed" in display or "verifier" in display or "heldout" in display:
            files.append(path)
    return sorted(files, key=lambda p: rel(p))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def option_count(row: dict[str, Any]) -> int:
    options = row.get("opaque_options")
    if isinstance(options, list):
        return sum(1 for item in options if isinstance(item, dict))
    projection = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    options = projection.get("opaque_options")
    if isinstance(options, list):
        return sum(1 for item in options if isinstance(item, dict))
    return 0


def target_value(row: dict[str, Any]) -> str:
    target = str(row.get("target_text") or row.get("expected_label") or row.get("decoder_text") or "")
    options = row.get("opaque_options")
    if not isinstance(options, list):
        projection = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
        options = projection.get("opaque_options")
    if isinstance(options, list):
        for option in options:
            if isinstance(option, dict) and str(option.get("label") or "") == target:
                return str(option.get("value") or "")
    projection = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    return str(projection.get("gold_value") or "")


def prompt_target_leak(row: dict[str, Any]) -> bool:
    prompt = str(row.get("prompt_text") or row.get("input_text") or row.get("prompt") or "")
    prefix = prompt.split("Options:", 1)[0]
    value = target_value(row)
    return bool(value and value != "ABSTAIN_INSUFFICIENT_EVIDENCE" and value in prefix)


def has_verifier_row(row: dict[str, Any]) -> bool:
    if isinstance(row.get("verifier_row"), dict):
        return True
    if bool(row.get("verifier_anchor")) and str(row.get("task_type") or "").startswith("verifier"):
        return True
    projection = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    records = projection.get("option_semantic_records")
    if isinstance(records, list):
        return any(isinstance(record, dict) and record.get("candidate_value_family") == "verifier_transition" for record in records)
    return False


def has_patch_or_abstain(row: dict[str, Any]) -> bool:
    if isinstance(row.get("patch_row"), dict) or str(row.get("candidate_patch") or ""):
        return True
    return str(row.get("task_type") or "") in {"patch_impact", "minimal_fix_selection", "abstention_insufficient_evidence"}


def audit_row(row: dict[str, Any], source_file: Path) -> dict[str, Any] | None:
    row_id = str(row.get("row_id") or row.get("id") or "")
    language = str(row.get("language_family") or row.get("language") or "")
    task = str(row.get("task_type") or row.get("perspective") or row.get("objective_family") or "")
    prompt = str(row.get("prompt_text") or row.get("input_text") or row.get("prompt") or "")
    if not row_id or language not in LANGUAGES or task not in TARGET_TASKS or not prompt:
        return None
    anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
    source_root = str(row.get("source_root_id") or row.get("root_id") or row.get("source_bundle_id") or "")
    options = option_count(row)
    blockers = []
    if not bool(row.get("source_heldout_admissible")):
        blockers.append("not_source_heldout_admissible")
    if options <= 1:
        blockers.append("singleton_or_missing_options")
    if prompt_target_leak(row):
        blockers.append("prompt_target_value_leak")
    if not bool(anti.get("deterministic_option_shuffle")):
        blockers.append("option_shuffle_not_declared")
    if not bool(anti.get("opaque_labels", True)):
        blockers.append("opaque_labels_not_confirmed")
    if not has_verifier_row(row):
        blockers.append("missing_verifier_row_or_transition")
    if not has_patch_or_abstain(row):
        blockers.append("missing_patch_or_abstain_row")
    if not source_root:
        blockers.append("missing_source_root")
    return {
        "row_id": row_id,
        "source_file": rel(source_file),
        "language_family": language,
        "task_type": task,
        "repo_family": row.get("repo_family") or row.get("repo_id"),
        "source_root_id": source_root,
        "source_heldout_admissible": bool(row.get("source_heldout_admissible")),
        "selected_test_anchor": bool(row.get("selected_test_anchor")),
        "verifier_anchor": bool(row.get("verifier_anchor")),
        "deterministic_option_shuffle": bool(anti.get("deterministic_option_shuffle")),
        "opaque_labels": bool(anti.get("opaque_labels", True)),
        "option_count": options,
        "prompt_target_value_leak": prompt_target_leak(row),
        "has_verifier_row_or_transition": has_verifier_row(row),
        "has_patch_or_abstain_row": has_patch_or_abstain(row),
        "blockers": blockers,
        "admitted": not blockers,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    audited_by_id: dict[str, dict[str, Any]] = {}
    files_seen = 0
    raw_rows_seen = 0
    for path in iter_candidate_files():
        files_seen += 1
        rows = load_jsonl(path)
        raw_rows_seen += len(rows)
        for row in rows:
            audit = audit_row(row, path)
            if not audit:
                continue
            row_id = str(audit["row_id"])
            existing = audited_by_id.get(row_id)
            if existing is None or (len(audit["blockers"]) < len(existing["blockers"])):
                audited_by_id[row_id] = audit

    audits = sorted(audited_by_id.values(), key=lambda row: (row["language_family"], row["task_type"], row["row_id"]))
    admitted = [row for row in audits if row["admitted"]]
    repair_queue = [row for row in audits if not row["admitted"]]

    blockers = Counter(blocker for row in repair_queue for blocker in row["blockers"])
    counts_by_language = Counter(str(row["language_family"]) for row in audits)
    admitted_by_language = Counter(str(row["language_family"]) for row in admitted)
    source_heldout_by_language = Counter(str(row["language_family"]) for row in audits if row["source_heldout_admissible"])
    roots_by_language: dict[str, set[str]] = defaultdict(set)
    admitted_roots_by_language: dict[str, set[str]] = defaultdict(set)
    for row in audits:
        roots_by_language[str(row["language_family"])].add(str(row["source_root_id"]))
    for row in admitted:
        admitted_roots_by_language[str(row["language_family"])].add(str(row["source_root_id"]))

    minimal_successor_ready = all(admitted_by_language.get(language, 0) > 0 for language in LANGUAGES)
    promotion_successor_ready = all(len(admitted_roots_by_language.get(language, set())) >= 2 for language in LANGUAGES)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": (
            "source_heldout_harness_successor_ready"
            if promotion_successor_ready
            else "source_heldout_harness_successor_not_ready"
        ),
        "metrics": {
            "files_seen": files_seen,
            "raw_rows_seen": raw_rows_seen,
            "audited_unique_rows": len(audits),
            "admitted_rows": len(admitted),
            "repair_queue_rows": len(repair_queue),
            "minimal_successor_ready_one_row_per_language": minimal_successor_ready,
            "promotion_successor_ready_two_roots_per_language": promotion_successor_ready,
            "counts_by_language": dict(sorted(counts_by_language.items())),
            "source_heldout_rows_by_language": dict(sorted(source_heldout_by_language.items())),
            "admitted_rows_by_language": dict(sorted(admitted_by_language.items())),
            "unique_roots_by_language": {lang: len(roots) for lang, roots in sorted(roots_by_language.items())},
            "admitted_roots_by_language": {
                lang: len(roots) for lang, roots in sorted(admitted_roots_by_language.items())
            },
            "top_blockers": dict(blockers.most_common(20)),
        },
        "successor_requirements": {
            "languages": list(LANGUAGES),
            "minimum_for_next_smoke": "at least one admitted source-heldout row per language",
            "minimum_for_promotion_candidate": "at least two independent admitted source-heldout roots per language plus deterministic shuffling and verifier/patch-or-abstain rows",
        },
        "recommended_next_actions": [
            "If admitted_rows is zero or language-skewed, materialize new rows rather than training on current canary rows.",
            "Patch row builders to set deterministic_option_shuffle after actually shuffling options.",
            "Add verifier_row objects for verifier/evidence rows and patch_row or explicit abstain scoring rows for patch/minimal-fix/abstention rows.",
            "Prioritize web selected-test heldout roots and Rust non-singleton verifier roots, because those are explicit Stage11468 blockers.",
        ],
        "outputs": {
            "row_audit": rel(ROW_AUDIT),
            "admitted_candidates": rel(ADMITTED),
            "repair_queue": rel(QUEUE),
            "summary": rel(SUMMARY),
        },
    }
    write_jsonl(ROW_AUDIT, audits)
    write_jsonl(ADMITTED, admitted)
    write_jsonl(QUEUE, repair_queue)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
