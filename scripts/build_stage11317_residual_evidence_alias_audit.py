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
STAGE = 11317
NAME = "stage11317_residual_evidence_alias_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY = OUT_DIR / "residual_evidence_alias_audit.json"
ROW_AUDIT = OUT_DIR / "residual_evidence_alias_rows.jsonl"
REPLACEMENT_QUEUE = OUT_DIR / "residual_evidence_replacement_queue.jsonl"
RESIDUAL = ARTIFACTS / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_residual_rows.jsonl"
STAGE11315 = ARTIFACTS / "stage11315_deleaked_fail_to_pass_postrun_audit/deleaked_fail_to_pass_postrun_audit.json"

ROLE_ALIASES = [
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
    "external_analogue_reference",
    "algorithmic_background_reference",
    "background_context",
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def prompt(row: dict[str, Any]) -> str:
    return str(row.get("prompt_text") or row.get("input_text") or "")


def options(row: dict[str, Any]) -> list[dict[str, Any]]:
    sps = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    opts = sps.get("opaque_options") or row.get("opaque_options") or []
    return [opt for opt in opts if isinstance(opt, dict)]


def gold(row: dict[str, Any]) -> str:
    sps = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    return str(sps.get("gold_value") or row.get("semantic_target_value") or "")


def root(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def alias_audit(row: dict[str, Any], miss: bool) -> dict[str, Any]:
    text = prompt(row)
    opt_values = [str(opt.get("value") or "") for opt in options(row)]
    role_mentions = {role: len(re.findall(rf"\b{re.escape(role)}\b", text)) for role in ROLE_ALIASES}
    option_values_visible = [value for value in opt_values if value and re.search(rf"\b{re.escape(value)}\b", text)]
    g = gold(row)
    gold_visible = bool(g and re.search(rf"\b{re.escape(g)}\b", text))
    line_starts_with_role = []
    for line in text.splitlines():
        stripped = line.strip()
        for role in ROLE_ALIASES:
            if stripped.startswith(role + " ") or stripped.startswith(role + "[") or stripped.startswith(role + " ["):
                line_starts_with_role.append(role)
    blockers = []
    if option_values_visible:
        blockers.append("option_value_alias_visible_in_prompt")
    if gold_visible:
        blockers.append("gold_role_alias_visible_in_prompt")
    if line_starts_with_role:
        blockers.append("evidence_lines_prefixed_by_role_alias")
    return {
        "row_id": row.get("row_id"),
        "root_id": root(row),
        "language_family": row.get("language_family"),
        "repo_family": row.get("repo_family"),
        "task_type": row.get("task_type"),
        "target_text": row.get("target_text"),
        "gold_value": g,
        "was_stage11315_miss": miss,
        "option_count": len(opt_values),
        "option_values": opt_values,
        "role_mentions": role_mentions,
        "option_values_visible_in_prompt": option_values_visible,
        "gold_role_visible_in_prompt": gold_visible,
        "evidence_line_role_prefixes": line_starts_with_role,
        "valid_as_scorer_diagnostic": True,
        "valid_as_maintainer_grade_residual_eval": not blockers,
        "blockers": blockers,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(RESIDUAL)
    post = read_json(STAGE11315)
    misses = {m.get("row_id") for m in (((post.get("scored") or {}).get("encoder_option_retrieval_verifier_conditioned") or {}).get("residual") or {}).get("misses") or []}
    audits = [alias_audit(row, row.get("row_id") in misses) for row in rows if row.get("task_type") == "evidence_citation"]
    queue = []
    for a in audits:
        if a["blockers"]:
            desired = "verifier/test evidence item vs changed surface" if a["gold_value"] == "verifier_and_test_constraint" else "symptom/call-path evidence item vs changed surface"
            queue.append({
                "source_row_id": a["row_id"],
                "source_root_id": a["root_id"],
                "language_family": a["language_family"],
                "repo_family": a["repo_family"],
                "gold_value": a["gold_value"],
                "was_stage11315_miss": a["was_stage11315_miss"],
                "replacement_requirement": "materialize evidence-item candidates without role aliases in prompt or option values",
                "desired_contrast": desired,
                "must_include": [
                    "concrete source/test/snippet evidence",
                    "opaque candidate ids",
                    "semantic target stored outside prompt",
                    "candidate-change-surface hard negative",
                    "root-disjoint train/support split metadata",
                ],
                "must_not_include": [
                    "role alias strings before options",
                    "gold role as option text",
                    "candidate option value copied verbatim from evidence prefix",
                ],
            })
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "residual_evidence_rows_are_scorer_diagnostics_not_maintainer_grade_eval" if any(a["blockers"] for a in audits) else "residual_evidence_rows_alias_clean",
        "counts": {
            "residual_rows": len(rows),
            "evidence_residual_rows": len(audits),
            "alias_blocked_rows": sum(1 for a in audits if a["blockers"]),
            "stage11315_miss_rows": sum(1 for a in audits if a["was_stage11315_miss"]),
            "replacement_queue_rows": len(queue),
            "by_language": dict(sorted(Counter(str(a["language_family"]) for a in audits).items())),
            "by_gold": dict(sorted(Counter(str(a["gold_value"]) for a in audits).items())),
            "blocker_counts": dict(sorted(Counter(b for a in audits for b in a["blockers"]).items())),
        },
        "interpretation": [
            "The evidence residual bank exposes explicit role aliases in prompt text, including gold role names and option values.",
            "These rows remain useful for scorer debugging, but they are not maintainer-grade evidence-citation eval rows because a parser can match role names directly.",
            "Do not promote frontier claims by optimizing these rows. Replace them with alias-free evidence-item candidate rows using opaque candidates and semantic targets stored out of prompt.",
        ],
        "source_artifacts": {"residual_rows": rel(RESIDUAL), "stage11315_audit": rel(STAGE11315)},
        "outputs": {"summary_json": rel(SUMMARY), "row_audit_jsonl": rel(ROW_AUDIT), "replacement_queue_jsonl": rel(REPLACEMENT_QUEUE)},
        "next_action": "stage11318_alias_free_residual_evidence_item_materialization",
    }
    write_jsonl(ROW_AUDIT, audits)
    write_jsonl(REPLACEMENT_QUEUE, queue)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
