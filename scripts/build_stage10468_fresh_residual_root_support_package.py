#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10468
NAME = "stage10468_fresh_residual_root_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "fresh_residual_root_support_package.json"
ROWS_JSONL = OUT_DIR / "fresh_residual_root_support_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PYTHON_CONTEXT_MANIFEST = ROOT / "runs/local/artifacts/stage10248_weakness_counterbalance_execution_request/weakness_counterbalance_manifest.jsonl"
PYTHON_HF_LOCAL_MANIFEST = ROOT / "runs/local/artifacts/stage10302_hf_local_support_execution_request/hf_local_support_manifest.jsonl"
RUST_CANDLE_MANIFEST = ROOT / "runs/local/artifacts/stage10302_hf_local_support_execution_request/hf_local_support_manifest.jsonl"
SUCCESSOR_MANIFEST = ROOT / "runs/local/artifacts/stage10410_ai_adjudicated_successor_salvage/real_session_successor_adjudicated_manifest.jsonl"
PYTHON_BUILDER = ROOT / "runs/local/artifacts/stage10466_python_verifier_fresh_root_builder/python_verifier_fresh_root_builder.json"
RUST_BUILDER = ROOT / "runs/local/artifacts/stage10467_rust_citation_fresh_root_builder/rust_citation_fresh_root_builder.json"
PROMOTION_GATE = ROOT / "runs/local/artifacts/stage10461_reviewed_v27_residual_promotion_gate/reviewed_v27_residual_promotion_gate.json"

STAGE10236_BUNDLE = (
    "stage10236::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_"
    "src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662::python"
)
STAGE10300_BUNDLE = (
    "stage10300::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_"
    "src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662::python"
)
RUST_CANDLE_BUNDLE = "stage10126::candle::candle-core::rust"
AGENTKERNEL_SUCCESSOR_ROWS = {
    "stage10110::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_45_019d39fb_a380_7a30_8790_9d59_agent_kernel_improvement_py_agent_kernel_modeling_adapter_training_py_agent_kern_94b87c02df_aug_1500000_8b46e7f662::python_implementation_vs_implementation",
    "stage10110::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_54_019d39fb_c43d_7e62_b055_b00b_agent_kernel_cycle_runner_py_agent_kernel_improvement_py_agent_kernel_learning_c_6a4dce0d0c_aug_1500000_8b46e7f662::python_implementation_vs_implementation",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def normalize_train_support(row: dict[str, Any], *, source_manifest: Path, support_class: str, support_role: str) -> dict[str, Any]:
    updated = json.loads(json.dumps(row))
    updated["split"] = "train"
    updated["split_role"] = "train_support"
    updated["loss_mask"] = {"decoder_ce": True}
    updated["expected_enabled_loss"] = "decoder_ce"
    updated["disable_losses"] = []
    updated["train_support_only"] = True
    updated["strict_eval_eligible"] = False
    updated["source_heldout_admissible"] = False
    updated["support_package_stage"] = STAGE
    provenance = dict(updated.get("support_provenance") or {})
    provenance.update(
        {
            "support_package_stage": STAGE,
            "support_package_name": NAME,
            "source_manifest": display(source_manifest),
            "support_class": support_class,
            "support_role": support_role,
        }
    )
    updated["support_provenance"] = provenance
    return updated


def main() -> None:
    python_builder = load_json(PYTHON_BUILDER)
    rust_builder = load_json(RUST_BUILDER)
    gate = load_json(PROMOTION_GATE)

    python_context_rows = [
        normalize_train_support(
            row,
            source_manifest=PYTHON_CONTEXT_MANIFEST,
            support_class="python_context_pack_disjoint_support",
            support_role="promotable_disjoint_support_candidate",
        )
        for row in load_jsonl(PYTHON_CONTEXT_MANIFEST)
        if str(row.get("source_bundle_id") or "") == STAGE10236_BUNDLE
        and str(row.get("language_family") or "") == "python"
    ]
    python_hf_rows = [
        normalize_train_support(
            row,
            source_manifest=PYTHON_HF_LOCAL_MANIFEST,
            support_class="python_hf_local_disjoint_support",
            support_role="promotable_disjoint_support_candidate",
        )
        for row in load_jsonl(PYTHON_HF_LOCAL_MANIFEST)
        if str(row.get("source_bundle_id") or "") == STAGE10300_BUNDLE
        and str(row.get("language_family") or "") == "python"
    ]
    rust_rows = [
        normalize_train_support(
            row,
            source_manifest=RUST_CANDLE_MANIFEST,
            support_class="rust_candle_core_interim_support",
            support_role="diagnostic_train_support_only",
        )
        for row in load_jsonl(RUST_CANDLE_MANIFEST)
        if str(row.get("source_bundle_id") or "") == RUST_CANDLE_BUNDLE
        and str(row.get("language_family") or "") == "rust"
        and str(row.get("task_type") or "") == "evidence_citation"
        and str(row.get("split") or "") == "train"
        and "::action_reweight::" not in str(row.get("row_id") or "")
    ]

    python_context_rows.sort(key=lambda row: str(row.get("row_id") or ""))
    python_hf_rows.sort(key=lambda row: str(row.get("row_id") or ""))
    rust_rows.sort(key=lambda row: str(row.get("row_id") or ""))

    successor_rows = [
        row for row in load_jsonl(SUCCESSOR_MANIFEST)
        if str(row.get("row_id") or "") in AGENTKERNEL_SUCCESSOR_ROWS
    ]
    successor_rows.sort(key=lambda row: str(row.get("row_id") or ""))

    all_rows = python_context_rows + python_hf_rows + rust_rows
    write_jsonl(ROWS_JSONL, all_rows)

    task_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    for row in all_rows:
        task = str(row.get("task_type") or "unknown")
        lang = str(row.get("language_family") or "unknown")
        role = str((row.get("support_provenance") or {}).get("support_role") or "unknown")
        task_counts[task] = task_counts.get(task, 0) + 1
        language_counts[lang] = language_counts.get(lang, 0) + 1
        role_counts[role] = role_counts.get(role, 0) + 1

    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(all_rows),
        "decision": "fresh_residual_root_support_package_ready",
        "claim_scope": [
            "Provide the next executable residual-support package for the repaired v2.7 frontier without replaying current strict rows into train.",
            "Use code_assist-rooted Python support as the promotable disjoint component and candle-core Rust citation rows as interim diagnostic support only.",
            "Attach agentkernel successor abstention rows as honesty metadata, not executable training rows, until they are materialized into the bounded trainer format.",
        ],
        "source_artifacts": {
            "python_context_manifest": display(PYTHON_CONTEXT_MANIFEST),
            "python_hf_local_manifest": display(PYTHON_HF_LOCAL_MANIFEST),
            "rust_candle_manifest": display(RUST_CANDLE_MANIFEST),
            "python_builder": display(PYTHON_BUILDER),
            "rust_builder": display(RUST_BUILDER),
            "promotion_gate": display(PROMOTION_GATE),
            "successor_manifest": display(SUCCESSOR_MANIFEST),
        },
        "rows": len(all_rows),
        "language_counts": dict(sorted(language_counts.items())),
        "task_counts": dict(sorted(task_counts.items())),
        "support_role_counts": dict(sorted(role_counts.items())),
        "bundle_counts": {
            STAGE10236_BUNDLE: len(python_context_rows),
            STAGE10300_BUNDLE: len(python_hf_rows),
            RUST_CANDLE_BUNDLE: len(rust_rows),
        },
        "honesty_only_metadata_rows": {
            "count": len(successor_rows),
            "row_ids": [row["row_id"] for row in successor_rows],
            "reason_not_executable_yet": "adjudicated successor rows are not yet materialized into the bounded trainer row contract",
        },
        "builder_contracts": {
            "python": python_builder["target_package_contract"],
            "rust": rust_builder["target_package_contract"],
        },
        "promotion_gate_requirements": gate["required_for_future_promotion"],
        "outputs": {
            "package_json": display(PACKAGE_JSON),
            "rows_jsonl": display(ROWS_JSONL),
        },
        "required_honesty_gates": [
            "No repaired strict overlay row is copied into train.",
            "Python support remains code_assist-rooted only for the promotable disjoint component.",
            "Rust tokenizers same-surface rows remain excluded from train.",
            "Rust candle-core rows are diagnostic support only and cannot justify a fresh-root claim by themselves.",
            "Agentkernel successor rows remain metadata-only until converted into bounded executable training rows.",
        ],
    }

    write_json(PACKAGE_JSON, package)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "rows": package["rows"],
            "package": display(PACKAGE_JSON),
        },
    )
    print(json.dumps(package, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
