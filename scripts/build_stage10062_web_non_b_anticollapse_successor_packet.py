#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10062
NAME = "stage10062_web_non_b_anticollapse_successor_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "web_non_b_anticollapse_successor_packet.json"
ROWS = OUT_DIR / "web_non_b_anticollapse_successor_rows.jsonl"
MANIFEST = OUT_DIR / "web_non_b_anticollapse_successor_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WEB_NON_B_ANTICOLLAPSE_SUCCESSOR_PACKET_STAGE10062.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10056_balanced_fresh_source_multilingual_geometry_successor_packet/balanced_fresh_source_multilingual_geometry_successor_manifest.jsonl"
SOURCE_POOL = ROOT / "runs/local/artifacts/stage8765_source_backed_edit_localization_candidate_manifest/source_backed_edit_localization_candidate_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage10058_balanced_fresh_source_multilingual_same_manifest_comparison_audit.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"

WEB_LABEL_MAP = {
    "TARGET_TEST": "A",
    "TARGET_ENTRYPOINT": "B",
    "TARGET_SYMBOL": "C",
    "TARGET_FILE": "D",
    "TARGET_CONFIG": "E",
}
TARGET_LABELS = {"C", "D", "E"}


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
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
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


def _load_readiness():
    spec = importlib.util.spec_from_file_location("train_agentkernel_lite_encdec", TRAINER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return getattr(module, "assess_multilingual_surface_readiness")


def _convert_source_row(row: dict[str, Any], *, label: str, hidden_target: str, rank: int) -> dict[str, Any]:
    corrupted = row.get("corrupted_state") if isinstance(row.get("corrupted_state"), dict) else {}
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    return {
        "row_id": f"stage10062_{row.get('row_id')}::train_{rank}",
        "source_row_id": row.get("row_id"),
        "source_row_ref": row.get("source_row_ref"),
        "source_stage": "stage8765_from_stage8636_with_repo_graph_lineage_controls",
        "source_skill_area": "edit_localization",
        "split": "train",
        "language_family": "web_js_ts_html",
        "objective_family": "structured_state",
        "route": "KEEP_STRUCTURED",
        "surface": "edit_localization_opaque_choice_surface_v3_web_isolated_disambiguator",
        "obligation_type": "POSITIVE_ORIGINAL",
        "expected_enabled_loss": "edit_localization_ce",
        "disable_losses": [
            "surface_role_ce", "repair_surface_ce", "build_mode_ce", "allowed_import_policy_ce",
            "blocked_import_policy_ce", "repo_dependency_policy_ce", "action_sequence_ce", "file_plan_ce",
            "symbol_binding_ce", "patch_operator_ce", "verifier_repair_ce",
        ],
        "authority": dict(row.get("authority") or {}),
        "loss_mask": {**(row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}), "edit_localization_ce": True},
        "gate_status": {
            **(row.get("gate_status") if isinstance(row.get("gate_status"), dict) else {}),
            "source_inventory_lineage": True,
            "source_provenance": True,
            "golden_locked_eval_suite": False,
        },
        "gate_status_materialized_from": "runs/summaries/stage8766_source_backed_edit_localization_candidate_audit.json",
        "locked_guard_refresh_stage": NAME,
        "anti_cheat": {
            **(row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}),
            "target_label_literals_in_prompt_surface": False,
            "target_label_literals_in_lifted_evidence": False,
            "requires_fresh_source_root": True,
            "requires_expert_maintainer_review_before_promotion": False,
            "requires_shortcut_audit_before_training": True,
        },
        "source_backed": True,
        "source_lineage": {
            **(row.get("source_lineage") if isinstance(row.get("source_lineage"), dict) else {}),
            "locked_eval_source": False,
            "train_eligible_lineage": True,
        },
        "semantic_key": f"stage10062:train:web_js_ts_html:{row.get('row_id')}",
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
            "edit_localization": label,
            "edit_localization_target": label,
            "edit_localization_target_hidden": hidden_target,
            "action_sequence": clean.get("action_sequence"),
            "file_plan": clean.get("file_plan"),
        },
        "target": {"decoder_text": label, "edit_localization": label, "target_ref": label},
        "counterfactual_root_row_id": f"{row.get('row_id')}::stage10062_train_root",
        "counterfactual_role": "positive_original",
        "counterfactual_required_obligations": ["POSITIVE_ORIGINAL", "SOURCE_BACKED", "WEB_NON_B_ANTICOLLAPSE", "FRESH_TRAIN_SOURCE_REQUIRED"],
        "counterfactual_source_stage": "stage8765_from_stage8636_with_repo_graph_lineage_controls",
        "counterfactual_language_family": "web_js_ts_html",
        "counterfactual_group_id": f"stage10062:web:{label}:{row.get('row_id')}",
        "counterfactual_expected_behavior": "label_should_follow_visible_locality_evidence",
        "counterfactual_challenge_stage": NAME,
        "counterfactual_execution_manifest_stage": NAME,
        "choice_permutation_stage": NAME,
        "choice_permutation_order": ["A", "B", "C", "D", "E"],
        "choice_permutation_map": {"A": "A", "B": "B", "C": "C", "D": "D", "E": "E"},
        "stage10062_role": "train",
        "stage10062_expected_label": label,
    }


def build_packet() -> dict[str, Any]:
    base_rows = load_jsonl(BASE_MANIFEST)
    pool = load_jsonl(SOURCE_POOL)
    source_summary = load_json(SOURCE_SUMMARY)
    failures: list[str] = []

    used_source_ids = {str(row.get("source_row_id") or "") for row in base_rows if row.get("source_row_id")}
    selected_rows: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()

    for row in pool:
        if str((row.get("corrupted_state") or {}).get("language") or "") != "typescript":
            continue
        if str(row.get("row_id") or "") in used_source_ids:
            continue
        if str(row.get("split") or "") != "train":
            continue
        hidden = str((row.get("clean_state") or {}).get("edit_localization_target") or "")
        label = WEB_LABEL_MAP.get(hidden)
        if label not in TARGET_LABELS:
            continue
        converted = _convert_source_row(row, label=label, hidden_target=hidden, rank=label_counts[label] + 1)
        selected_rows.append(converted)
        label_counts[label] += 1

    if dict(sorted(label_counts.items())) != {"C": 5, "D": 5, "E": 5}:
        failures.append("web_non_b_source_counts_mismatch")

    successor_rows = [*base_rows, *selected_rows]
    write_jsonl(ROWS, selected_rows)
    write_jsonl(MANIFEST, successor_rows)

    assess_multilingual_surface_readiness = _load_readiness()
    readiness = assess_multilingual_surface_readiness("edit_localization_probe", successor_rows)
    if not readiness or readiness.get("passed") is not True:
        failures.append("web_non_b_anticollapse_readiness_failed")

    language_counts = Counter(str(row.get("language_family") or "") for row in successor_rows)
    split_counts = Counter(str(row.get("split") or "") for row in successor_rows)
    metrics = {
        "base_rows": len(base_rows),
        "successor_rows": len(successor_rows),
        "fresh_source_rows": len(selected_rows),
        "language_counts": dict(sorted(language_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "selected_counts": dict(sorted(label_counts.items())),
        "readiness_passed": bool(readiness and readiness.get("passed")),
        "readiness_failed_buckets": list((readiness or {}).get("failed_buckets") or []),
    }

    if source_summary.get("passed") is not True:
        failures.append("stage10058_not_passed")
    if metrics["successor_rows"] != 142:
        failures.append("successor_rows_not_142")
    if metrics["fresh_source_rows"] != 15:
        failures.append("fresh_source_rows_not_15")
    if split_counts.get("train") != 87:
        failures.append("train_rows_not_87")
    if split_counts.get("eval") != 38:
        failures.append("eval_rows_not_38")
    if split_counts.get("strict_eval") != 17:
        failures.append("strict_rows_not_17")
    if language_counts.get("python") != 27:
        failures.append("python_rows_not_27")
    if language_counts.get("c_cpp") != 38:
        failures.append("c_cpp_rows_not_38")
    if language_counts.get("rust") != 17:
        failures.append("rust_rows_not_17")
    if language_counts.get("web_js_ts_html") != 60:
        failures.append("web_rows_not_60")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "policy": {
            "preserve_stage10056_multilingual_geometry_base": True,
            "web_only_anticollapse_refresh": True,
            "add_only_unused_fresh_source_web_non_b_rows": True,
            "no_eval_row_replay": True,
        },
        "inputs": {
            "base_manifest": display(BASE_MANIFEST),
            "source_pool": display(SOURCE_POOL),
            "source_audit": display(SOURCE_SUMMARY),
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packet()
    write_json(PACKET, built)
    next_step = "Run one capped target-100m probe on this web non-B anti-collapse successor manifest to test whether fresh web C/D/E rows fix the stage10058 all-B web failure without disturbing python, rust, or c_cpp."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"packet": display(PACKET), "rows": display(ROWS), "manifest": display(MANIFEST), "doc": display(DOC)},
        "decision": "Materialized a web-only anti-collapse successor packet on top of stage10056 that adds all remaining fresh source-backed web C/D/E train rows while preserving the stronger multilingual base.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10062 Web Non-B Anticollapse Successor Packet",
                "",
                f"Passed: `{summary['passed']}`",
                f"Fresh source rows: `{built['metrics']['fresh_source_rows']}`",
                f"Successor rows: `{built['metrics']['successor_rows']}`",
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
