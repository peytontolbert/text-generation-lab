#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10093
NAME = "stage10093_canonical_source_heldout_realistic_source_backed_successor_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "canonical_source_heldout_realistic_source_backed_successor_request.json"
ROWS = OUT_DIR / "canonical_source_heldout_realistic_source_backed_successor_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CANONICAL_SOURCE_HELDOUT_REALISTIC_SOURCE_BACKED_SUCCESSOR_REQUEST_STAGE10093.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage10088_canonical_source_heldout_realistic_maintenance_shell/canonical_source_heldout_realistic_maintenance_shell_manifest.jsonl"
SHORTCUT_AUDIT = ROOT / "runs/local/artifacts/stage10092_canonical_source_heldout_realistic_shell_shortcut_audit/canonical_source_heldout_realistic_shell_shortcut_audit.json"
REALISM_SPEC = ROOT / "runs/local/artifacts/stage10087_canonical_source_heldout_realism_audit/canonical_source_heldout_realistic_successor_spec.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def split_value(row: dict[str, Any]) -> str:
    return str(row.get("split") or "")


def clean_state(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}


def input_state(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("input_state") if isinstance(row.get("input_state"), dict) else {}


def anti_cheat(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}


def source_lineage(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("source_lineage") if isinstance(row.get("source_lineage"), dict) else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_rows(manifest_rows: list[dict[str, Any]], realism_spec: dict[str, Any]) -> list[dict[str, Any]]:
    required_l2_fields = list((((realism_spec.get("required_visible_fields_by_level") or {}).get("L2")) or []))
    requests: list[dict[str, Any]] = []
    for row in manifest_rows:
        if split_value(row) not in {"eval", "strict_eval"}:
            continue
        request = {
            "row_id": row.get("row_id"),
            "source_row_id": row.get("source_row_id"),
            "language_family": row.get("language_family"),
            "hidden_target_family": clean_state(row).get("edit_localization_target_hidden"),
            "canonical_label": clean_state(row).get("edit_localization_target"),
            "source_stage": row.get("source_stage"),
            "compare_subset_split": split_value(row),
            "locked_eval_source": source_lineage(row).get("locked_eval_source"),
            "graph_nodes_source_id": source_lineage(row).get("graph_nodes_source_id"),
            "graph_spans_source_id": source_lineage(row).get("graph_spans_source_id"),
            "query_kind": ((row.get("query") if isinstance(row.get("query"), dict) else {}).get("query_kind")),
            "required_visible_fields": required_l2_fields,
            "anti_cheat_requirements": [
                "opaque_candidate_tokens",
                "candidate_permutation",
                "no_target_literals_in_prompt_surface",
                "counterfactual_audit",
                "expert_maintainer_review",
                "source_root_holdout_preserved",
            ],
            "source_materialization_requirements": {
                "failure_text_from_visible_failure_or_assertion": True,
                "trace_excerpt_from_source_backed_graph_or_logs": True,
                "relevant_snippets_from_visible_repo_spans": True,
                "candidate_paths_from_real_candidate_surface_nodes": True,
                "shell_only_not_raw_repo_source": False,
            },
            "current_shell_preview": {
                "failure_text": input_state(row).get("failure_text"),
                "trace_excerpt": input_state(row).get("trace_excerpt"),
                "candidate_paths": input_state(row).get("candidate_paths"),
            },
            "existing_anti_cheat_flags": {
                "requires_shortcut_audit_before_training": anti_cheat(row).get("requires_shortcut_audit_before_training"),
                "requires_expert_maintainer_review_before_promotion": anti_cheat(row).get("requires_expert_maintainer_review_before_promotion"),
                "stage10088_shell_uses_synthetic_visible_evidence": anti_cheat(row).get("stage10088_shell_uses_synthetic_visible_evidence"),
            },
        }
        requests.append(request)
    return requests


def build() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_rows = load_jsonl(MANIFEST)
    shortcut_audit = load_json(SHORTCUT_AUDIT)
    realism_spec = load_json(REALISM_SPEC)
    request_rows = build_rows(manifest_rows, realism_spec)
    by_lang = Counter(str(row.get("language_family") or "") for row in request_rows)
    by_target = Counter(str(row.get("hidden_target_family") or "") for row in request_rows)
    metrics = {
        "heldout_rows_requested": len(request_rows),
        "languages": dict(sorted(by_lang.items())),
        "hidden_target_families": dict(sorted(by_target.items())),
        "compare_subset_split_counts": dict(sorted(Counter(str(row.get("compare_subset_split") or "") for row in request_rows).items())),
        "locked_eval_source_rows": sum(1 for row in request_rows if row.get("locked_eval_source") is True),
        "rows_needing_source_materialization": sum(
            1 for row in request_rows if row.get("existing_anti_cheat_flags", {}).get("stage10088_shell_uses_synthetic_visible_evidence") is True
        ),
        "carried_shortcut_risk": ((shortcut_audit.get("metrics") or {}).get("heldout_shell_signature_majority_lookup_exact")),
    }
    failures: list[str] = []
    if metrics["heldout_rows_requested"] != 55:
        failures.append("heldout_request_count_not_55")
    if metrics["compare_subset_split_counts"] != {"eval": 38, "strict_eval": 17}:
        failures.append("compare_subset_split_counts_mismatch")
    if metrics["rows_needing_source_materialization"] != 55:
        failures.append("source_materialization_flag_count_not_55")

    next_best_step = (
        "Use this request to materialize source-backed L2-or-L3 visible evidence for the 55 heldout rows, then rerun target-100M and Gemma on the same manifest before making broader maintainer claims."
    )
    request = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifacts": {
            "manifest": display(MANIFEST),
            "shortcut_audit": display(SHORTCUT_AUDIT),
            "realism_spec": display(REALISM_SPEC),
            "request_rows": display(ROWS),
        },
        "intent": "Replace the stage10088 synthetic visible shell with source-backed heldout failure, trace, snippet, and candidate evidence while preserving canonical labels and heldout integrity.",
        "metrics": metrics,
        "claim_boundary": {
            "ready_for_expert_maintainer_comparison": False,
            "reason": "The request is only a materialization contract; the source-backed visible evidence still has to be mined and reviewed.",
        },
        "failures": failures,
        "next_best_step": next_best_step,
    }
    return request, request_rows


def write_doc(request: dict[str, Any]) -> None:
    metrics = request["metrics"]
    lines = [
        "# Stage10093 Canonical Source Heldout Realistic Source Backed Successor Request",
        "",
        f"Passed: `{request['passed']}`",
        f"Heldout rows requested: `{metrics['heldout_rows_requested']}`",
        f"Locked eval source rows: `{metrics['locked_eval_source_rows']}`",
        f"Carried shortcut risk: `{metrics['carried_shortcut_risk']}`",
        "",
        "This stage converts the stage10092 shortcut finding into a concrete materialization request for all 55 heldout rows. The goal is to preserve the canonical labels and heldout split while replacing the stage10088 synthetic shell with source-backed failure text, trace excerpts, snippets, and candidate paths.",
        "",
        "Next: Materialize the requested source-backed visible evidence, run the same-manifest 100M and Gemma comparisons on that successor, and only then judge whether the multilingual edge survives a maintainer-appropriate eval.",
        "",
    ]
    DOC.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    request, rows = build()
    write_json(REQUEST, request)
    write_jsonl(ROWS, rows)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": request["passed"],
        "artifacts": request["artifacts"],
        "metrics": request["metrics"],
        "next_best_step": request["next_best_step"],
    }
    write_json(SUMMARY, summary)
    write_doc(request)
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": request["passed"], "failures": request["failures"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
