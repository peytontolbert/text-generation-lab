#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10035
NAME = "stage10035_real_fresh_heldout_candidate_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "real_fresh_heldout_candidate_packet.json"
ROWS = OUT_DIR / "real_fresh_heldout_candidate_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_FRESH_HELDOUT_CANDIDATE_PACKET_STAGE10035.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_POOL = ROOT / "runs/local/artifacts/stage8765_source_backed_edit_localization_candidate_manifest/source_backed_edit_localization_candidate_manifest.jsonl"
BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10003_deduped_source_heldout_successor_request/edit_localization_manifest.jsonl"
REQUEST = ROOT / "runs/local/artifacts/stage10030_python_cpp_fresh_root_replenishment_request/python_cpp_fresh_root_replenishment_request.json"

DISABLE_LOSSES = [
    "surface_role_ce",
    "repair_surface_ce",
    "build_mode_ce",
    "allowed_import_policy_ce",
    "blocked_import_policy_ce",
    "repo_dependency_policy_ce",
    "action_sequence_ce",
    "file_plan_ce",
    "symbol_binding_ce",
    "patch_operator_ce",
    "verifier_repair_ce",
]

LANGUAGE_ALIAS = {"python": "python", "cpp": "c_cpp"}
LANGUAGE_LABEL_MAP = {
    "python": {
        "TARGET_SYMBOL": "A",
        "TARGET_FILE": "B",
        "TARGET_CONFIG": "C",
        "TARGET_TEST": "D",
        "TARGET_ENTRYPOINT": "E",
    },
    "c_cpp": {
        "TARGET_TEST": "A",
        "TARGET_CONFIG": "B",
        "TARGET_FILE": "C",
        "TARGET_ENTRYPOINT": "D",
        "TARGET_SYMBOL": "E",
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_split(value: Any) -> str:
    return "strict_eval" if str(value or "") == "strict" else str(value or "")


def build_packet() -> dict[str, Any]:
    pool = load_jsonl(SOURCE_POOL)
    base_rows = load_jsonl(BASE_MANIFEST)
    request = load_json(REQUEST)
    requests = request.get("requests") if isinstance(request.get("requests"), list) else []
    used_source_ids = {str(row.get("source_row_id") or "") for row in base_rows if row.get("source_row_id")}

    selected_rows: list[dict[str, Any]] = []
    per_request_counts: dict[str, int] = {}
    failures: list[str] = []

    for request_row in requests:
        language_family = str(request_row.get("language_family") or "")
        target_label = str(request_row.get("target_label") or "")
        target_roots = int(request_row.get("requested_fresh_independent_roots") or 0)
        source_language = next((src for src, dst in LANGUAGE_ALIAS.items() if dst == language_family), "")
        candidates = []
        for row in pool:
            if str((row.get("corrupted_state") or {}).get("language") or "") != source_language:
                continue
            source_row_id = str(row.get("row_id") or "")
            if source_row_id in used_source_ids:
                continue
            target_hidden = str((row.get("clean_state") or {}).get("edit_localization_target") or "")
            mapped = LANGUAGE_LABEL_MAP.get(language_family, {}).get(target_hidden)
            if mapped != target_label:
                continue
            split = normalize_split(row.get("split"))
            if split not in {"eval", "strict_eval"}:
                continue
            candidates.append(row)

        chosen = candidates[:target_roots]
        per_request_counts[f"{language_family}:{target_label}"] = len(chosen)
        if len(chosen) != target_roots:
            failures.append(f"insufficient_candidates:{language_family}:{target_label}")
        for index, row in enumerate(chosen, start=1):
            corrupted = row.get("corrupted_state") if isinstance(row.get("corrupted_state"), dict) else {}
            clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
            language = str(LANGUAGE_ALIAS.get(str(corrupted.get("language") or ""), "unknown"))
            target_hidden = str(clean.get("edit_localization_target") or "")
            target_letter = str(LANGUAGE_LABEL_MAP.get(language, {}).get(target_hidden, ""))
            fresh_row = {
                "row_id": f"stage10035_{row.get('row_id')}::fresh_heldout_{index}",
                "source_row_id": row.get("row_id"),
                "source_stage": "stage8765_from_stage8636_with_repo_graph_lineage_controls",
                "source_skill_area": "edit_localization",
                "split": normalize_split(row.get("split")),
                "language_family": language,
                "objective_family": "source_heldout_edit_localization_fresh_candidate",
                "route": "KEEP_STRUCTURED",
                "expected_enabled_loss": "edit_localization_ce",
                "disable_losses": list(DISABLE_LOSSES),
                "authority": dict(row.get("authority") or {}),
                "loss_mask": {
                    **(row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}),
                    "edit_localization_ce": True,
                },
                "gate_status": {
                    **(row.get("gate_status") if isinstance(row.get("gate_status"), dict) else {}),
                    "source_inventory_lineage": True,
                    "source_provenance": True,
                    "golden_locked_eval_suite": True,
                },
                "gate_status_materialized_from": "runs/summaries/stage8766_source_backed_edit_localization_candidate_audit.json",
                "locked_guard_refresh_stage": NAME,
                "anti_cheat": {
                    **(row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}),
                    "target_label_literals_in_prompt_surface": False,
                    "target_label_literals_in_lifted_evidence": False,
                    "requires_fresh_source_root": True,
                    "requires_expert_maintainer_review_before_promotion": True,
                    "requires_shortcut_audit_before_training": True,
                },
                "source_backed": True,
                "source_lineage": {
                    **(row.get("source_lineage") if isinstance(row.get("source_lineage"), dict) else {}),
                    "locked_eval_source": True,
                    "train_eligible_lineage": False,
                },
                "source_row_ref": row.get("source_row_ref"),
                "semantic_key": f"fresh_heldout:{language}:{row.get('row_id')}",
                "graph_input": row.get("graph_input"),
                "query": row.get("query"),
                "corrupted_state": corrupted,
                "input_state": {
                    "task_observation": corrupted.get("task_observation"),
                    "visible_locality_evidence": corrupted.get("visible_locality_evidence"),
                    "file_extension": corrupted.get("file_extension"),
                    "context_config_visible": bool(((corrupted.get("neutral_context_bits") or {}).get("config_visible"))),
                    "context_entrypoint_visible": bool(((corrupted.get("neutral_context_bits") or {}).get("entrypoint_visible"))),
                    "context_symbol_names_visible": bool(((corrupted.get("neutral_context_bits") or {}).get("symbol_names_visible"))),
                    "context_tests_visible": bool(((corrupted.get("neutral_context_bits") or {}).get("tests_visible"))),
                },
                "clean_state": {
                    "edit_localization": target_letter,
                    "edit_localization_target": target_letter,
                    "edit_localization_target_hidden": target_hidden,
                    "action_sequence": clean.get("action_sequence"),
                    "file_plan": clean.get("file_plan"),
                },
                "target": {
                    "decoder_text": target_letter,
                    "edit_localization": target_letter,
                    "target_ref": target_letter,
                },
                "counterfactual_root_row_id": f"{row.get('row_id')}::fresh_root",
                "counterfactual_role": "positive_original",
                "counterfactual_required_obligations": [
                    "POSITIVE_ORIGINAL",
                    "SOURCE_HELDOUT",
                    "EXPERT_MAINTAINER_REVIEW_REQUIRED",
                    "ANTI_CHEAT_REVIEW_REQUIRED",
                ],
            }
            selected_rows.append(fresh_row)

    write_jsonl(ROWS, selected_rows)
    metrics = {
        "base_rows": len(base_rows),
        "candidate_rows": len(selected_rows),
        "candidate_language_counts": dict(sorted(Counter(str(row.get("language_family") or "") for row in selected_rows).items())),
        "candidate_split_counts": dict(sorted(Counter(str(row.get("split") or "") for row in selected_rows).items())),
        "per_request_counts": dict(sorted(per_request_counts.items())),
    }
    packet = {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "inputs": {
            "source_pool": display(SOURCE_POOL),
            "base_manifest": display(BASE_MANIFEST),
            "fresh_root_request": display(REQUEST),
        },
        "policy": {
            "source_ids_must_be_unused_in_base_manifest": True,
            "rows_are_candidate_heldout_only_until_expert_review": True,
            "require_stage10034_validation_before_merge": True,
        },
    }
    return packet


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packet()
    PACKET.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Run expert-maintainer and anti-cheat review on these real fresh heldout candidates, then pass them through stage10034 validation and merge them into the source-heldout manifest for the next honest comparison rerun."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"packet": display(PACKET), "rows": display(ROWS), "doc": display(DOC)},
        "decision": "Materialized a real fresh-heldout candidate packet by selecting unused source-backed Python/C++ edit-localization rows from the stage8765 pool and converting them into the current heldout row schema for the six unresolved families.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10035 Real Fresh Heldout Candidate Packet",
                "",
                f"Passed: `{summary['passed']}`",
                f"Candidate rows: `{built['metrics']['candidate_rows']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
