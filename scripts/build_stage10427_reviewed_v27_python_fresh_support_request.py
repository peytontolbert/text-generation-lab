#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10427
NAME = "stage10427_reviewed_v27_python_fresh_support_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "reviewed_v27_python_fresh_support_request.json"
MANIFEST_JSONL = OUT_DIR / "reviewed_v27_python_fresh_support_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10421_reviewed_multilingual_v27_target100m_execution_request/reviewed_multilingual_v27_target100m_manifest.jsonl"
PYTHON_SUPPORT_ROWS = ROOT / "runs/local/artifacts/stage10327_python_mirrormind_replenishment_execution_request/python_mirrormind_replenishment_train_rows.jsonl"
PYTHON_SUPPORT_BUNDLE = ROOT / "runs/local/artifacts/stage10327_python_mirrormind_replenishment_execution_request/python_mirrormind_replenishment_bundle.json"
BASE_RUNTIME = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"

SUPPORT_BUNDLE_ID = "stage10327::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_29t02_41_34_019acd7c_b80e_7880_9f45_f500_models_mirrormind_coordinator_py_models_mirrormind_domain_py_models_mirrormind_m_3b079208d1_aug_1500000_8b46e7f662::python"
RUN_ID = "stage10428_reviewed_v27_python_fresh_support_probe"
OUTPUT_DIR = ROOT / "runs/local/artifacts" / RUN_ID / "bounded_decoder_probe"
RUNTIME_MODEL_DIR = ROOT / "runs/local/artifacts" / RUN_ID / "runtime_model"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
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


def normalize_support_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["split"] = "train"
    out["split_role"] = "fresh_python_support"
    out["loss_mask"] = {"decoder_ce": True}
    out["expected_enabled_loss"] = "decoder_ce"
    out["disable_losses"] = []
    out["selected_test_anchor"] = True
    out["verifier_anchor"] = True
    out["abstention_heavy"] = False
    out["source_heldout_admissible"] = False
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["repo_id"] = "repository_library"
    out["repo_family"] = "repository_library"
    out["fresh_support_source"] = "stage10327_python_mirrormind_replenishment"
    out["support_bundle_id"] = SUPPORT_BUNDLE_ID
    return out


def main() -> None:
    base_rows = load_jsonl(BASE_MANIFEST)
    support_rows = [
        normalize_support_row(row)
        for row in load_jsonl(PYTHON_SUPPORT_ROWS)
        if str(row.get("source_bundle_id") or "") == SUPPORT_BUNDLE_ID
    ]
    support_bundle = load_json(PYTHON_SUPPORT_BUNDLE)
    if not support_rows:
        raise SystemExit("no stage10327 support rows matched the expected bundle id")

    merged_rows = list(base_rows) + support_rows
    write_jsonl(MANIFEST_JSONL, merged_rows)

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "Materialized a fresh-support reviewed-v2.7 request that adds only the disjoint stage10327 Mirrormind Python bundle on top of the current stage10421 manifest, leaving the strict frontier unchanged and avoiding same-surface replay.",
        "claim_scope": "same_manifest_reviewed_v27_with_disjoint_python_train_support_only",
        "initialize_from_runtime_model": display(BASE_RUNTIME),
        "manifest": display(MANIFEST_JSONL),
        "rows": len(merged_rows),
        "split_counts": {
            "train": sum(1 for row in merged_rows if str(row.get("split") or "") == "train"),
            "eval": sum(1 for row in merged_rows if str(row.get("split") or "") == "eval"),
            "strict_eval": sum(1 for row in merged_rows if str(row.get("split") or "") == "strict_eval"),
        },
        "added_support": {
            "support_rows": len(support_rows),
            "support_bundle_id": SUPPORT_BUNDLE_ID,
            "support_repo_id": support_bundle.get("repo_id"),
            "support_selected_tests": support_bundle.get("selected_tests"),
            "support_candidate_paths": support_bundle.get("candidate_paths"),
            "support_task_types": [row.get("task_type") for row in support_rows],
        },
        "required_honesty_gates": [
            "strict eval rows remain identical to stage10421/stage10422/stage10423",
            "added rows are disjoint train-support-only stage10327 Mirrormind bundle rows, not same-surface replay rows",
            "Rust remains unchanged in this request because no fresh Rust replenishment supply exists in the current reviewed inventory",
            "Any improvement from this run can support the standalone reviewed-v2.7 frontier, but it still does not upgrade the source-heldout claim boundary",
        ],
        "success_criteria": [
            "Python strict verifier_outcome flips to correct or Python strict accuracy improves with no loss of the 4/4 language win over Gemma on the current same-manifest frontier",
            "No more than one new strict regression is introduced outside Python",
            "Rust strict evidence_citation is reported separately as unresolved if unchanged",
        ],
        "command": [
            "env",
            "TMPDIR=/data/tmp",
            "TEMP=/data/tmp",
            "TMP=/data/tmp",
            "conda",
            "run",
            "-n",
            "trellis",
            "python",
            str((ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py").resolve()),
            "--repo-root",
            str(ROOT),
            "--manifest",
            str(MANIFEST_JSONL.resolve()),
            "--mode",
            "bounded_decoder_ce_probe",
            "--probe-scale",
            "target_100m",
            "--implementation",
            "transformer",
            "--model-config",
            str((ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json").resolve()),
            "--tokenizer-json",
            str((ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json").resolve()),
            "--tokenizer-config",
            str((ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json").resolve()),
            "--tokenizer-hashlock",
            str((ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json").resolve()),
            "--execution-authorized-for-recovery-probe",
            "--max-train-rows",
            "32",
            "--max-eval-rows",
            "24",
            "--max-strict-rows",
            "24",
            "--max-steps",
            "24",
            "--batch-size",
            "2",
            "--learning-rate",
            "5e-6",
            "--max-encoder-tokens",
            "768",
            "--max-decoder-tokens",
            "8",
            "--decoder-ce-weight",
            "0.2",
            "--bounded-choice-aux-weight",
            "1.0",
            "--bounded-choice-aux-source",
            "encoder_option_retrieval",
            "--structured-aux-weight",
            "0.0",
            "--denoise-weight",
            "0.0",
            "--eos-loss-weight",
            "4.0",
            "--enable-generation-audit",
            "--max-generation-rows",
            "12",
            "--max-generation-tokens",
            "8",
            "--require-loss-mask-enforcement-audit",
            "--allow-runtime-model-save-for-harness",
            "--runtime-model-save-dir",
            str(RUNTIME_MODEL_DIR.resolve()),
            "--initialize-from-runtime-model",
            str(BASE_RUNTIME.resolve()),
            "--preservation-reference-runtime-model",
            str(BASE_RUNTIME.resolve()),
            "--preservation-kl-weight",
            "2.0",
            "--no-final-checkpoint-export",
            "--skip-final-model-save",
            "1",
            "--output-dir",
            str(OUTPUT_DIR.resolve()),
            "--run-id",
            RUN_ID,
        ],
        "next_best_step": "Run the stage10428 fresh-support probe to test whether disjoint Python verifier-grade support improves the reviewed-v2.7 strict frontier without broad regressions; keep Rust sourcing as a separate unresolved supply problem.",
    }

    write_json(REQUEST_JSON, request)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": True,
            "artifacts": {"request": display(REQUEST_JSON), "manifest": display(MANIFEST_JSONL)},
            "decision": request["decision"],
            "next_best_step": request["next_best_step"],
            "created_at_utc": request["created_at_utc"],
        },
    )
    print(json.dumps({"stage": STAGE, "passed": True, "request": display(REQUEST_JSON)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
