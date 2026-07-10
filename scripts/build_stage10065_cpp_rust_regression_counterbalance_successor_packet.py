#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10065
NAME = "stage10065_cpp_rust_regression_counterbalance_successor_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "cpp_rust_regression_counterbalance_successor_packet.json"
ROWS = OUT_DIR / "cpp_rust_regression_counterbalance_rows.jsonl"
MANIFEST = OUT_DIR / "cpp_rust_regression_counterbalance_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CPP_RUST_REGRESSION_COUNTERBALANCE_SUCCESSOR_PACKET_STAGE10065.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10062_web_non_b_anticollapse_successor_packet/web_non_b_anticollapse_successor_manifest.jsonl"
COMPARE_ROWS = ROOT / "runs/local/artifacts/stage10064_web_non_b_anticollapse_same_manifest_comparison_audit/web_non_b_anticollapse_same_manifest_comparison_rows.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage10064_web_non_b_anticollapse_same_manifest_comparison_audit.json"
SOURCE_POOL = ROOT / "runs/local/artifacts/stage8765_source_backed_edit_localization_candidate_manifest/source_backed_edit_localization_candidate_manifest.jsonl"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"

POOL_LANGUAGE_TO_FAMILY = {
    "cpp": "c_cpp",
    "rust": "rust",
}

HIDDEN_TO_LABEL = {
    "cpp": {
        "TARGET_TEST": "A",
        "TARGET_CONFIG": "B",
        "TARGET_FILE": "C",
        "TARGET_ENTRYPOINT": "D",
        "TARGET_SYMBOL": "E",
    },
    "rust": {
        "TARGET_SYMBOL": "A",
        "TARGET_FILE": "B",
        "TARGET_TEST": "C",
        "TARGET_ENTRYPOINT": "D",
        "TARGET_CONFIG": "E",
    },
}

LOSS_NAME = "edit_localization_ce"
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
TARGET_LANGUAGES = {"c_cpp", "rust"}


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


def _convert_source_row(row: dict[str, Any], *, family: str, label: str, hidden_target: str, rank: int) -> dict[str, Any]:
    corrupted = row.get("corrupted_state") if isinstance(row.get("corrupted_state"), dict) else {}
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    return {
        "row_id": f"stage10065_{row.get('row_id')}::train_{rank}",
        "source_row_id": row.get("row_id"),
        "source_row_ref": row.get("source_row_ref"),
        "source_stage": "stage8765_from_stage8636_with_repo_graph_lineage_controls",
        "source_skill_area": "edit_localization",
        "split": "train",
        "language_family": family,
        "objective_family": "structured_state",
        "route": "KEEP_STRUCTURED",
        "surface": "edit_localization_opaque_choice_surface_v3_web_isolated_disambiguator",
        "obligation_type": "POSITIVE_ORIGINAL",
        "expected_enabled_loss": LOSS_NAME,
        "disable_losses": list(DISABLE_LOSSES),
        "authority": dict(row.get("authority") or {}),
        "loss_mask": {
            **(row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}),
            LOSS_NAME: True,
        },
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
        "semantic_key": f"stage10065:train:{family}:{row.get('row_id')}",
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
        "target": {
            "decoder_text": label,
            "edit_localization": label,
            "target_ref": label,
        },
        "counterfactual_root_row_id": f"{row.get('row_id')}::stage10065_train_root",
        "counterfactual_role": "positive_original",
        "counterfactual_required_obligations": [
            "POSITIVE_ORIGINAL",
            "SOURCE_BACKED",
            "CPP_RUST_REGRESSION_COUNTERBALANCE",
            "FRESH_TRAIN_SOURCE_REQUIRED",
        ],
        "counterfactual_source_stage": "stage8765_from_stage8636_with_repo_graph_lineage_controls",
        "counterfactual_language_family": family,
        "counterfactual_group_id": f"stage10065:{family}:{label}:{row.get('row_id')}",
        "counterfactual_expected_behavior": "label_should_follow_visible_locality_evidence",
        "counterfactual_challenge_stage": NAME,
        "counterfactual_execution_manifest_stage": NAME,
        "choice_permutation_stage": NAME,
        "choice_permutation_order": ["A", "B", "C", "D", "E"],
        "choice_permutation_map": {"A": "A", "B": "B", "C": "C", "D": "D", "E": "E"},
        "stage10065_role": "train",
        "stage10065_expected_label": label,
        "stage10065_selection_reason": "baseline_true_successor_false_counterbalance",
    }


def build_packet() -> dict[str, Any]:
    base_rows = load_jsonl(BASE_MANIFEST)
    compare_rows = load_jsonl(COMPARE_ROWS)
    source_summary = load_json(SOURCE_SUMMARY)
    pool = load_jsonl(SOURCE_POOL)
    failures: list[str] = []

    regression_counts: Counter[tuple[str, str]] = Counter()
    for row in compare_rows:
        if (
            bool(row.get("baseline_hundred_m_correct"))
            and not bool(row.get("successor_hundred_m_correct"))
            and str(row.get("language_family") or "") in TARGET_LANGUAGES
        ):
            regression_counts[(str(row.get("language_family") or ""), str(row.get("expected_label") or ""))] += 1

    used_source_ids = {str(row.get("source_row_id") or "") for row in base_rows if row.get("source_row_id")}
    grouped_candidates: dict[tuple[str, str], list[dict[str, Any]]] = {}
    availability_counts: Counter[tuple[str, str]] = Counter()
    for row in pool:
        source_language = str((row.get("corrupted_state") or {}).get("language") or "")
        family = POOL_LANGUAGE_TO_FAMILY.get(source_language)
        if family is None:
            continue
        source_id = str(row.get("row_id") or "")
        if source_id in used_source_ids:
            continue
        if str(row.get("split") or "") != "train":
            continue
        hidden_target = str((row.get("clean_state") or {}).get("edit_localization_target") or "")
        label = HIDDEN_TO_LABEL[source_language].get(hidden_target)
        if not label:
            continue
        grouped_candidates.setdefault((family, label), []).append(row)
        availability_counts[(family, label)] += 1

    selected_rows: list[dict[str, Any]] = []
    selected_counts: Counter[tuple[str, str]] = Counter()
    shortages: Counter[tuple[str, str]] = Counter()

    for key, need in sorted(regression_counts.items()):
        family, label = key
        candidates = grouped_candidates.get(key, [])
        for rank in range(1, need + 1):
            if not candidates:
                shortages[key] += 1
                continue
            row = candidates.pop(0)
            hidden_target = str((row.get("clean_state") or {}).get("edit_localization_target") or "")
            converted = _convert_source_row(row, family=family, label=label, hidden_target=hidden_target, rank=selected_counts[key] + 1)
            selected_rows.append(converted)
            selected_counts[key] += 1

    successor_rows = [*base_rows, *selected_rows]
    write_jsonl(ROWS, selected_rows)
    write_jsonl(MANIFEST, successor_rows)

    assess_multilingual_surface_readiness = _load_readiness()
    readiness = assess_multilingual_surface_readiness("edit_localization_probe", successor_rows)
    if not readiness or readiness.get("passed") is not True:
        failures.append("counterbalance_successor_readiness_failed")

    language_counts = Counter(str(row.get("language_family") or "") for row in successor_rows)
    split_counts = Counter(str(row.get("split") or "") for row in successor_rows)
    selected_language_counts = Counter(str(row.get("language_family") or "") for row in selected_rows)
    metrics = {
        "base_rows": len(base_rows),
        "successor_rows": len(successor_rows),
        "fresh_source_rows": len(selected_rows),
        "language_counts": dict(sorted(language_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "fresh_source_language_counts": dict(sorted(selected_language_counts.items())),
        "regression_counts": dict(sorted((f"{k[0]}:{k[1]}", v) for k, v in regression_counts.items())),
        "availability_counts": dict(sorted((f"{k[0]}:{k[1]}", v) for k, v in availability_counts.items())),
        "selected_counts": dict(sorted((f"{k[0]}:{k[1]}", v) for k, v in selected_counts.items())),
        "shortages": dict(sorted((f"{k[0]}:{k[1]}", v) for k, v in shortages.items())),
        "readiness_passed": bool(readiness and readiness.get("passed")),
        "readiness_failed_buckets": list((readiness or {}).get("failed_buckets") or []),
    }

    if source_summary.get("passed") is not True:
        failures.append("stage10064_not_passed")
    if shortages:
        failures.append("insufficient_unused_train_rows_for_regression_counterbalance")
    if metrics["fresh_source_rows"] != 9:
        failures.append("fresh_source_rows_not_9")
    if metrics["successor_rows"] != 151:
        failures.append("successor_rows_not_151")
    if split_counts.get("train") != 96:
        failures.append("train_rows_not_96")
    if split_counts.get("eval") != 38:
        failures.append("eval_rows_not_38")
    if split_counts.get("strict_eval") != 17:
        failures.append("strict_rows_not_17")
    if language_counts.get("python") != 27:
        failures.append("python_rows_not_27")
    if language_counts.get("c_cpp") != 45:
        failures.append("c_cpp_rows_not_45")
    if language_counts.get("rust") != 19:
        failures.append("rust_rows_not_19")
    if language_counts.get("web_js_ts_html") != 60:
        failures.append("web_rows_not_60")
    if metrics["selected_counts"] != {
        "c_cpp:A": 1,
        "c_cpp:B": 3,
        "c_cpp:C": 1,
        "c_cpp:E": 2,
        "rust:B": 1,
        "rust:C": 1,
    }:
        failures.append("selected_counts_mismatch")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "policy": {
            "preserve_stage10062_frontier": True,
            "cpp_rust_only_counterbalance": True,
            "fresh_source_rows_only": True,
            "no_eval_row_replay": True,
            "topup_only_current_baseline_to_successor_regressions": True,
        },
        "inputs": {
            "base_manifest": display(BASE_MANIFEST),
            "comparison_audit": display(SOURCE_SUMMARY),
            "comparison_rows": display(COMPARE_ROWS),
            "source_pool": display(SOURCE_POOL),
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packet()
    write_json(PACKET, built)
    next_step = "Run one capped target-100m probe on this c_cpp/rust counter-balance manifest to test whether the stage10064 4-language Gemma win can be retained while recovering the c_cpp/rust baseline gap."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "packet": display(PACKET),
            "rows": display(ROWS),
            "manifest": display(MANIFEST),
            "doc": display(DOC),
        },
        "decision": "Materialized a fresh-source c_cpp/rust counter-balance successor packet on top of stage10062 using only the labels that regressed relative to the stage10040 baseline in stage10064.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10065 Cpp Rust Regression Counterbalance Successor Packet",
        "",
        f"Passed: `{summary['passed']}`",
        f"Fresh source rows: `{built['metrics']['fresh_source_rows']}`",
        f"Successor rows: `{built['metrics']['successor_rows']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
