#!/usr/bin/env python3
"""Build Stage12058 guarded transition training request.

This stage is a request/package stage only. It combines the selected Stage11923
transition replay/eval manifest with the floor-complete Stage12056 v35 support
rows and records strict postrun gates. It does not execute training.
"""

from __future__ import annotations

import collections
import datetime as dt
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
STAGE = 12058
NAME = "stage12058_guarded_transition_training_request"
OUT = REPO / "runs" / "local" / "artifacts" / NAME
SUMMARIES = REPO / "runs" / "summaries"
SUMMARY = OUT / "guarded_transition_training_request.json"
SUMMARY_MIRROR = SUMMARIES / f"{NAME}.json"
MANIFEST = OUT / "guarded_transition_training_manifest.jsonl"
COMMAND_JSON = OUT / "guarded_transition_training_command.json"

BASE_MANIFEST = REPO / "runs/local/artifacts/stage11923_transition_listwise_head_only_probe_request/transition_listwise_head_only_manifest.jsonl"
V35_ROWS = REPO / "runs/local/artifacts/stage12056_transition_support_rollup_v35/transition_support_rows_v35.jsonl"
V35_AUDIT = REPO / "runs/local/artifacts/stage12057_transition_support_v35_audit/transition_support_v35_audit.json"
INIT_RUNTIME = REPO / "runs/local/artifacts/stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json"
PRESERVE_RUNTIME = REPO / "runs/local/artifacts/stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
RUNTIME_DIR = REPO / "runs/local/artifacts/stage12059_guarded_transition_training_probe/runtime_model"
OUTPUT_DIR = REPO / "runs/local/artifacts/stage12059_guarded_transition_training_probe/bounded_decoder_probe"
TRAIN_SCRIPT = REPO / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = REPO / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = REPO / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = REPO / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = REPO / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"


def rel(path: Path) -> str:
    return str(path.relative_to(REPO))


def load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def split_of(row: dict[str, Any]) -> str:
    return str(row.get("split") or row.get("package_split") or "")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SUMMARIES.mkdir(parents=True, exist_ok=True)

    base_rows = read_jsonl(BASE_MANIFEST)
    v35_rows = read_jsonl(V35_ROWS)
    audit = load_json(V35_AUDIT)

    old_train = [r for r in base_rows if split_of(r) == "train"]
    eval_rows = [r for r in base_rows if split_of(r) == "eval"]
    strict_rows = [r for r in base_rows if split_of(r) == "strict_eval"]

    support_rows: list[dict[str, Any]] = []
    for row in v35_rows:
        r = dict(row)
        r["split"] = "train"
        r["package_split"] = "train"
        r["stage12058_support_source"] = "stage12056_transition_support_v35"
        r["stage12058_train_support_only"] = True
        mask = r.get("loss_mask")
        if not isinstance(mask, dict) or not any(bool(v) for v in mask.values()):
            r["loss_mask"] = {
                "bounded_choice_aux": True,
                "decoder_ce": True,
                "structured_aux": True,
                "transition_projection": True,
            }
            r["stage12058_loss_mask_normalized"] = True
        r["row_id"] = f"{r['row_id']}::stage12058_guarded_support"
        support_rows.append(r)

    replay_rows: list[dict[str, Any]] = []
    for row in old_train:
        r = dict(row)
        r["stage12058_replay_source"] = "stage11923_transition_listwise_head_only_manifest"
        r["row_id"] = f"{r['row_id']}::stage12058_old640_replay"
        replay_rows.append(r)

    manifest_rows = replay_rows + support_rows + eval_rows + strict_rows
    write_jsonl(MANIFEST, manifest_rows)

    counts_by_split = collections.Counter(split_of(r) for r in manifest_rows)
    train_task_counts = collections.Counter(r.get("task_type", "unknown") for r in replay_rows + support_rows)
    train_status_counts = collections.Counter(
        r.get("observed_verifier_transition")
        or r.get("target", {}).get("semantic_value")
        or r.get("standalone_projection_source", {}).get("observed_verifier_transition")
        or "UNKNOWN"
        for r in support_rows
    )
    language_counts = collections.Counter(r.get("language_family", "unknown") for r in support_rows)
    root_keys = {
        r.get("root_lineage_key") or r.get("source_root_id") or r.get("root_id") or r.get("source_bundle_id")
        for r in support_rows
    }
    root_keys.discard(None)

    max_train_rows = counts_by_split["train"]
    command = [
        "env",
        "CUDA_VISIBLE_DEVICES=2",
        "NVIDIA_VISIBLE_DEVICES=2",
        "AGENTKERNEL_EVAL_DEVICE=cuda:0",
        "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True",
        "TMPDIR=/data/tmp",
        "TEMP=/data/tmp",
        "TMP=/data/tmp",
        "conda",
        "run",
        "-n",
        "trellis",
        "python",
        str(TRAIN_SCRIPT),
        "--repo-root",
        str(REPO),
        "--manifest",
        str(MANIFEST),
        "--mode",
        "bounded_decoder_ce_probe",
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        str(MODEL_CONFIG),
        "--tokenizer-json",
        str(TOKENIZER_JSON),
        "--tokenizer-config",
        str(TOKENIZER_CONFIG),
        "--tokenizer-hashlock",
        str(TOKENIZER_HASHLOCK),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows",
        str(max_train_rows),
        "--max-eval-rows",
        str(counts_by_split["eval"]),
        "--max-strict-rows",
        str(counts_by_split["strict_eval"]),
        "--max-steps",
        "768",
        "--batch-size",
        "8",
        "--learning-rate",
        "1e-4",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "16",
        "--decoder-ce-weight",
        "0.0",
        "--bounded-choice-aux-weight",
        "3.0",
        "--bounded-choice-root-group-aux-weight",
        "0.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval_semantic_candidate_head",
        "--bounded-choice-train-head-only",
        "--bounded-decoder-train-sampler",
        "task_balanced",
        "--bounded-choice-contrast-weight",
        "0.3",
        "--bounded-choice-contrast-margin",
        "0.08",
        "--bounded-choice-same-role-listwise-weight",
        "0.5",
        "--bounded-choice-verifier-value-listwise-weight",
        "0.7",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--eos-loss-weight",
        "1.0",
        "--enable-generation-audit",
        "--max-generation-rows",
        "8",
        "--max-generation-tokens",
        "8",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(RUNTIME_DIR),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(PRESERVE_RUNTIME),
        "--preservation-kl-weight",
        "4.0",
        "--no-final-checkpoint-export",
        "--output-dir",
        str(OUTPUT_DIR),
    ]
    write_json(COMMAND_JSON, command)

    gate_inputs = {
        "base_manifest_exists": BASE_MANIFEST.exists(),
        "v35_rows_exists": V35_ROWS.exists(),
        "v35_audit_exists": V35_AUDIT.exists(),
        "init_runtime_exists": INIT_RUNTIME.exists(),
        "preservation_runtime_exists": PRESERVE_RUNTIME.exists(),
        "train_rows_expected_951": counts_by_split["train"] == 951,
        "eval_rows_22": counts_by_split["eval"] == 22,
        "strict_rows_22": counts_by_split["strict_eval"] == 22,
        "v35_floor_audit_train_ready": bool(audit.get("train_ready_against_floor_and_hard_audit")),
        "v35_hard_blockers_zero": audit.get("hard_blocker_count") == 0,
        "uses_gpu2_mask": "CUDA_VISIBLE_DEVICES=2" in command and "NVIDIA_VISIBLE_DEVICES=2" in command,
        "head_only_enabled": "--bounded-choice-train-head-only" in command,
        "listwise_enabled": "--bounded-choice-same-role-listwise-weight" in command
        and "--bounded-choice-verifier-value-listwise-weight" in command,
        "contrast_enabled": "--bounded-choice-contrast-weight" in command,
    }
    passed = all(gate_inputs.values())

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "guarded_transition_training_request_ready" if passed else "guarded_transition_training_request_blocked",
        "passed": passed,
        "execute_now": False,
        "hypothesis": "The Stage11924 transition listwise head can absorb floor-complete verifier-status support if old 640 replay and preservation KL protect the selected transition/compact gates.",
        "intervention": "Continue from Stage11924, train semantic candidate head only on old 640 transition replay plus Stage12056 v35 support rows, using task-balanced sampling, contrast, and same-role/verifier-value listwise losses.",
        "claim_boundary": [
            "This is a guarded diagnostic training request, not model progress.",
            "Stage12056 v35 rows are train-support-only and do not establish source-heldout or strict-eval superiority.",
            "Promotion requires a postrun routed audit against old transition 640, protected compact gates, residual bank, source-heldout smoke, and same-manifest Gemma if the transition score exceeds baseline.",
        ],
        "row_counts": {
            "train_rows": counts_by_split["train"],
            "old_transition_replay_train_rows": len(replay_rows),
            "v35_support_train_rows": len(support_rows),
            "eval_rows": counts_by_split["eval"],
            "strict_rows": counts_by_split["strict_eval"],
            "v35_unique_root_keys": len(root_keys),
            "v35_language_counts": dict(sorted(language_counts.items())),
            "v35_status_counts": dict(sorted(train_status_counts.items())),
            "train_task_counts": dict(sorted(train_task_counts.items())),
        },
        "v35_audit_summary": {
            "hard_blocker_count": audit.get("hard_blocker_count"),
            "warning_count": audit.get("warning_count"),
            "issue_counts": audit.get("issue_counts"),
            "repo_family_over_10pct": audit.get("repo_family_over_10pct"),
            "repo_family_over_15pct": audit.get("repo_family_over_15pct"),
            "top_repo_share": audit.get("top_repo_share"),
            "controlled_fixture_rows": audit.get("controlled_fixture_rows"),
            "controlled_fixture_ratio": audit.get("controlled_fixture_ratio"),
            "train_ready_against_floor_and_hard_audit": audit.get("train_ready_against_floor_and_hard_audit"),
        },
        "gates_before_execution": gate_inputs,
        "promotion_gate": {
            "old_transition_manifest_correct": ">=364/640 for retention; >386/640 for same-manifest Gemma win",
            "protected_filtered_strict": "22/22",
            "protected_filtered_validation": ">=20/22",
            "protected_old_canary_strict": "23/23",
            "protected_old_canary_validation": ">=21/23",
            "protected_residual_bank": ">=7/10",
            "source_heldout_smoke": ">=6/12 retained; >6/12 for transfer progress",
            "coverage": "100% routed audit coverage, no skipped rows",
            "breakdown_required": [
                "transition_next_action",
                "transition_candidate_selection",
                "transition_verifier_transition",
                "transition_continue_or_stop",
            ],
        },
        "training_controls": {
            "gpu": "cuda:2 only via CUDA_VISIBLE_DEVICES=2/NVIDIA_VISIBLE_DEVICES=2 and AGENTKERNEL_EVAL_DEVICE=cuda:0",
            "environment": "conda run -n trellis",
            "init_runtime": rel(INIT_RUNTIME),
            "preservation_reference_runtime": rel(PRESERVE_RUNTIME),
            "head_only": True,
            "sampler": "task_balanced",
            "preservation_kl_weight": 4.0,
            "bounded_choice_aux_source": "encoder_option_retrieval_semantic_candidate_head",
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "summary_mirror": rel(SUMMARY_MIRROR),
            "manifest": rel(MANIFEST),
            "command": rel(COMMAND_JSON),
            "runtime_dir": rel(RUNTIME_DIR),
            "output_dir": rel(OUTPUT_DIR),
        },
        "source_artifacts": {
            "base_stage11923_manifest": rel(BASE_MANIFEST),
            "v35_support_rows": rel(V35_ROWS),
            "v35_audit": rel(V35_AUDIT),
            "initialize_from_runtime_model": rel(INIT_RUNTIME),
            "preservation_reference_runtime_model": rel(PRESERVE_RUNTIME),
        },
        "next_stage_if_executed": "stage12059_guarded_transition_training_probe",
        "next_stage_after_execution": "stage12060_guarded_transition_training_postrun_audit",
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps({"passed": passed, "summary": rel(SUMMARY), "manifest_rows": len(manifest_rows)}, indent=2))


if __name__ == "__main__":
    main()
