#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10047
NAME = "stage10047_python_symbol_test_source_backed_successor_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "python_symbol_test_source_backed_successor_packet.json"
ROWS = OUT_DIR / "python_symbol_test_source_backed_successor_rows.jsonl"
TRAIN_MANIFEST = OUT_DIR / "python_symbol_test_successor_train_manifest.jsonl"
HELDOUT_ROWS = OUT_DIR / "python_symbol_test_successor_heldout_candidates.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PYTHON_SYMBOL_TEST_SOURCE_BACKED_SUCCESSOR_PACKET_STAGE10047.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

CURRENT_MANIFEST = ROOT / "runs/local/artifacts/stage10036_real_fresh_heldout_merge_validator/expanded_source_heldout_manifest.jsonl"
SOURCE_POOL = ROOT / "runs/local/artifacts/stage8765_source_backed_edit_localization_candidate_manifest/source_backed_edit_localization_candidate_manifest.jsonl"
PYTHON_AUDIT = ROOT / "runs/local/artifacts/stage10046_expanded_python_gap_collapse_audit/expanded_python_gap_collapse_audit.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"

LANGUAGE_LABEL_MAP = {
    "TARGET_SYMBOL": "A",
    "TARGET_FILE": "B",
    "TARGET_CONFIG": "C",
    "TARGET_TEST": "D",
    "TARGET_ENTRYPOINT": "E",
}
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
REQUEST_SPECS = [
    {"hidden_target": "TARGET_SYMBOL", "train_rows": 3, "heldout_rows": 3},
    {"hidden_target": "TARGET_TEST", "train_rows": 3, "heldout_rows": 3},
    {"hidden_target": "TARGET_CONFIG", "train_rows": 2, "heldout_rows": 2},
]


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


def _load_readiness() -> Any:
    spec = importlib.util.spec_from_file_location("train_agentkernel_lite_encdec", TRAINER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return getattr(module, "assess_multilingual_surface_readiness")


def _convert_source_row(row: dict[str, Any], *, role: str, rank: int) -> dict[str, Any]:
    corrupted = row.get("corrupted_state") if isinstance(row.get("corrupted_state"), dict) else {}
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    hidden_target = str(clean.get("edit_localization_target") or "")
    target_label = LANGUAGE_LABEL_MAP[hidden_target]
    if role == "train":
        split = "train"
        lineage_locked = False
        lineage_train = True
        review_required = False
    else:
        split = "eval"
        lineage_locked = True
        lineage_train = False
        review_required = True
    converted = {
        "row_id": f"stage10047_{row.get('row_id')}::{role}_{rank}",
        "source_row_id": row.get("row_id"),
        "source_stage": "stage8765_from_stage8636_with_repo_graph_lineage_controls",
        "source_skill_area": "edit_localization",
        "split": split,
        "language_family": "python",
        "objective_family": f"python_symbol_test_successor_{role}",
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
            "golden_locked_eval_suite": lineage_locked,
        },
        "gate_status_materialized_from": "runs/summaries/stage8766_source_backed_edit_localization_candidate_audit.json",
        "locked_guard_refresh_stage": NAME,
        "anti_cheat": {
            **(row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}),
            "target_label_literals_in_prompt_surface": False,
            "target_label_literals_in_lifted_evidence": False,
            "requires_fresh_source_root": True,
            "requires_expert_maintainer_review_before_promotion": review_required,
            "requires_shortcut_audit_before_training": True,
        },
        "source_backed": True,
        "source_lineage": {
            **(row.get("source_lineage") if isinstance(row.get("source_lineage"), dict) else {}),
            "locked_eval_source": lineage_locked,
            "train_eligible_lineage": lineage_train,
        },
        "semantic_key": f"stage10047:{role}:python:{row.get('row_id')}",
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
            "edit_localization": target_label,
            "edit_localization_target": target_label,
            "edit_localization_target_hidden": hidden_target,
            "action_sequence": clean.get("action_sequence"),
            "file_plan": clean.get("file_plan"),
        },
        "target": {
            "decoder_text": target_label,
            "edit_localization": target_label,
            "target_ref": target_label,
        },
        "counterfactual_root_row_id": f"{row.get('row_id')}::stage10047_{role}_root",
        "counterfactual_role": "positive_original",
        "counterfactual_required_obligations": [
            "POSITIVE_ORIGINAL",
            "SOURCE_BACKED",
            "PYTHON_SYMBOL_TEST_SUCCESSOR",
            "ANTI_CHEAT_REVIEW_REQUIRED" if review_required else "FRESH_TRAIN_SOURCE_REQUIRED",
        ],
        "stage10047_role": role,
        "stage10047_hidden_target": hidden_target,
    }
    return converted


def build_packet() -> dict[str, Any]:
    manifest_rows = load_jsonl(CURRENT_MANIFEST)
    pool = load_jsonl(SOURCE_POOL)
    python_audit = load_json(PYTHON_AUDIT)
    used_source_ids = {str(row.get("source_row_id") or "") for row in manifest_rows if row.get("source_row_id")}
    selected_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    heldout_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    selection_counts: dict[str, int] = {}

    for spec in REQUEST_SPECS:
        hidden_target = spec["hidden_target"]
        candidates = [
            row
            for row in pool
            if str((row.get("corrupted_state") or {}).get("language") or "") == "python"
            and str((row.get("clean_state") or {}).get("edit_localization_target") or "") == hidden_target
            and str(row.get("row_id") or "") not in used_source_ids
        ]
        train_candidates = [row for row in candidates if str(row.get("split") or "") == "train"]
        eval_candidates = [row for row in candidates if str(row.get("split") or "") == "eval"]
        chosen_train = train_candidates[: spec["train_rows"]]
        chosen_eval = eval_candidates[: spec["heldout_rows"]]
        selection_counts[f"{hidden_target}:train"] = len(chosen_train)
        selection_counts[f"{hidden_target}:heldout_eval"] = len(chosen_eval)
        if len(chosen_train) != spec["train_rows"]:
            failures.append(f"insufficient_train_candidates:{hidden_target}")
        if len(chosen_eval) != spec["heldout_rows"]:
            failures.append(f"insufficient_eval_candidates:{hidden_target}")
        for index, row in enumerate(chosen_train, start=1):
            converted = _convert_source_row(row, role="train", rank=index)
            train_rows.append(converted)
            selected_rows.append(converted)
        for index, row in enumerate(chosen_eval, start=1):
            converted = _convert_source_row(row, role="heldout_eval", rank=index)
            heldout_rows.append(converted)
            selected_rows.append(converted)

    successor_train_manifest = [*manifest_rows, *train_rows]
    write_jsonl(ROWS, selected_rows)
    write_jsonl(TRAIN_MANIFEST, successor_train_manifest)
    write_jsonl(HELDOUT_ROWS, heldout_rows)

    assess_multilingual_surface_readiness = _load_readiness()
    readiness = assess_multilingual_surface_readiness("edit_localization_probe", successor_train_manifest)
    if not readiness or readiness.get("passed") is not True:
        failures.append("successor_train_manifest_readiness_failed")

    train_target_counts = Counter(str((row.get("clean_state") or {}).get("edit_localization_target_hidden") or "") for row in train_rows)
    heldout_target_counts = Counter(str((row.get("clean_state") or {}).get("edit_localization_target_hidden") or "") for row in heldout_rows)
    train_signature_count = len(
        {
            json.dumps(row.get("input_state") if isinstance(row.get("input_state"), dict) else {}, sort_keys=True)
            for row in successor_train_manifest
            if str(row.get("language_family") or "") == "python" and str(row.get("split") or "") == "train"
        }
    )
    packet = {
        "passed": not failures,
        "failures": failures,
        "metrics": {
            "current_manifest_rows": len(manifest_rows),
            "successor_train_manifest_rows": len(successor_train_manifest),
            "selected_rows": len(selected_rows),
            "train_rows": len(train_rows),
            "heldout_candidate_rows": len(heldout_rows),
            "selection_counts": dict(sorted(selection_counts.items())),
            "train_target_counts": dict(sorted(train_target_counts.items())),
            "heldout_target_counts": dict(sorted(heldout_target_counts.items())),
            "successor_python_train_signature_count": train_signature_count,
            "readiness_passed": bool(readiness and readiness.get("passed")),
            "readiness_failed_buckets": list((readiness or {}).get("failed_buckets") or []),
            "python_gap_delta_hundred_m_minus_gemma": (python_audit.get("metrics") or {}).get("delta_hundred_m_minus_gemma"),
            "python_gap_mode_label": (python_audit.get("metrics") or {}).get("hundred_m_mode_label"),
        },
        "policy": {
            "do_not_replay_current_heldout_rows_into_train": True,
            "train_rows_must_be_fresh_source_backed": True,
            "heldout_rows_require_expert_review_before_merge": True,
            "heldout_rows_require_anti_cheat_review_before_merge": True,
            "target_config_rows_are_anchors_not_gap_replays": True,
        },
        "inputs": {
            "current_manifest": display(CURRENT_MANIFEST),
            "source_pool": display(SOURCE_POOL),
            "python_gap_audit": display(PYTHON_AUDIT),
        },
    }
    return packet


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packet()
    write_json(PACKET, built)
    next_step = (
        "Run one capped target-100m probe on the successor train manifest, while separately reviewing the heldout candidates before any same-manifest Python expansion or promotion."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "packet": display(PACKET),
            "rows": display(ROWS),
            "successor_train_manifest": display(TRAIN_MANIFEST),
            "heldout_candidates": display(HELDOUT_ROWS),
            "doc": display(DOC),
        },
        "decision": "Materialized a fresh source-backed Python successor packet that targets the audited symbol-vs-test gap with new train roots and separate heldout review candidates instead of replaying the current evaluation rows.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10047 Python Symbol Test Source Backed Successor Packet",
                "",
                f"Passed: `{summary['passed']}`",
                f"Train rows: `{built['metrics']['train_rows']}`",
                f"Heldout rows: `{built['metrics']['heldout_candidate_rows']}`",
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
