#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11608
NAME = "stage11608_web_task_candidate_head_only_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "web_task_candidate_head_only_probe_request.json"
MANIFEST = OUT / "web_task_candidate_head_only_probe_manifest.jsonl"
COMMAND = OUT / "web_task_candidate_head_only_probe_command.json"
TRAIN_ROWS = ART / "stage11597_web_answerable_no_abstain_geometry_audit/web_answerable_no_abstain_train_rows.jsonl"
STRICT_ROWS = ART / "stage11597_web_answerable_no_abstain_geometry_audit/web_answerable_no_abstain_successor_strict_rows.jsonl"
FILTERED_VALIDATION = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl"
FILTERED_STRICT = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
INIT_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
SCORER_AUDIT = ART / "stage11597_web_answerable_no_abstain_geometry_audit/web_answerable_no_abstain_geometry_audit.json"
PROBE = ART / "stage11608_web_task_candidate_head_only_probe/bounded_decoder_probe"
RUNTIME_OUT = ART / "stage11608_web_task_candidate_head_only_probe/runtime_model"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def normalize(row: dict[str, Any], split: str) -> dict[str, Any]:
    out = dict(row)
    out["split"] = split
    out.setdefault("prompt_text", out.get("input_text") or "")
    out.setdefault("decoder_text", out.get("target_text") or out.get("bounded_choice_target_label") or "")
    out["loss_mask"] = {"decoder_ce": True, "bounded_choice_aux": True}
    out["expected_enabled_loss"] = "decoder_ce+bounded_choice_aux+bounded_choice_contrast"
    src = dict(out.get("standalone_projection_source") or {})
    src.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = src
    out["target"] = {"decoder_text": out.get("decoder_text"), "bounded_choice_target_label": out.get("bounded_choice_target_label") or out.get("target_text")}
    return out


def root_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("root_id") or row.get("root_lineage_key") or row.get("row_id")) for row in rows}


def main() -> None:
    train = [normalize(row, "train") for row in load_jsonl(TRAIN_ROWS)]
    strict_successor = [normalize(row, "strict_eval") for row in load_jsonl(STRICT_ROWS)]
    validation = [normalize(row, "eval") for row in load_jsonl(FILTERED_VALIDATION)]
    protected_strict = [normalize(row, "strict_eval") for row in load_jsonl(FILTERED_STRICT)]
    manifest = train + validation + protected_strict
    overlaps = {
        "train_vs_validation": sorted(root_ids(train) & root_ids(validation)),
        "train_vs_protected_strict": sorted(root_ids(train) & root_ids(protected_strict)),
        "train_vs_successor_strict": sorted(root_ids(train) & root_ids(strict_successor)),
    }
    command = [
        "env", "CUDA_VISIBLE_DEVICES=2", "NVIDIA_VISIBLE_DEVICES=2", "AGENTKERNEL_EVAL_DEVICE=cuda:0",
        "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True", "TMPDIR=/data/tmp", "TEMP=/data/tmp", "TMP=/data/tmp",
        "conda", "run", "-n", "trellis", "python", str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
        "--repo-root", str(ROOT),
        "--manifest", str(MANIFEST),
        "--mode", "bounded_decoder_ce_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", str(ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"),
        "--tokenizer-json", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),
        "--tokenizer-config", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),
        "--tokenizer-hashlock", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows", str(len(train)),
        "--max-eval-rows", str(len(validation)),
        "--max-strict-rows", str(len(protected_strict)),
        "--max-steps", "256",
        "--batch-size", "4",
        "--learning-rate", "3e-5",
        "--max-encoder-tokens", "768",
        "--max-decoder-tokens", "16",
        "--decoder-ce-weight", "0.04",
        "--bounded-choice-aux-weight", "3.0",
        "--bounded-choice-aux-source", "encoder_option_retrieval_web_task_candidate_head",
        "--bounded-choice-train-head-only",
        "--bounded-decoder-train-sampler", "web_task_family_balanced",
        "--bounded-choice-contrast-weight", "0.5",
        "--bounded-choice-contrast-margin", "0.08",
        "--structured-aux-weight", "0.0",
        "--denoise-weight", "0.0",
        "--eos-loss-weight", "4.0",
        "--enable-generation-audit",
        "--max-generation-rows", "8",
        "--max-generation-tokens", "16",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir", str(RUNTIME_OUT),
        "--initialize-from-runtime-model", str(INIT_RUNTIME),
        "--preservation-reference-runtime-model", str(INIT_RUNTIME),
        "--preservation-kl-weight", "6.0",
        "--no-final-checkpoint-export",
        "--output-dir", str(PROBE),
    ]
    scorer_audit = load_json(SCORER_AUDIT) if SCORER_AUDIT.exists() else {}
    gates = {
        "source_train_rows_present": len(train) == 156,
        "successor_strict_rows_present": len(strict_successor) == 36,
        "protected_rows_present": len(validation) == 22 and len(protected_strict) == 22,
        "no_root_overlap": all(not vals for vals in overlaps.values()),
        "scorer_audit_measurable": (scorer_audit.get("results") or {}).get("train", {}).get("correct", 0) > 0,
        "gpu2_mask_present": "CUDA_VISIBLE_DEVICES=2" in command and "NVIDIA_VISIBLE_DEVICES=2" in command,
        "contrast_enabled": "--bounded-choice-contrast-weight" in command and command[command.index("--bounded-choice-contrast-weight") + 1] == "0.5",
        "head_only_enabled": "--bounded-choice-train-head-only" in command,
        "web_sampler_enabled": "web_task_family_balanced" in command,
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": all(gates.values()),
        "decision": "web_task_candidate_head_only_probe_ready" if all(gates.values()) else "web_task_candidate_head_only_probe_blocked",
        "metrics": {
            "train_rows": len(train),
            "train_roots": len(root_ids(train)),
            "successor_strict_rows": len(strict_successor),
            "successor_strict_roots": len(root_ids(strict_successor)),
            "train_by_task": dict(Counter(str(row.get("task_type")) for row in train)),
            "root_overlaps": overlaps,
        },
        "objective_settings": {
            "learning_rate": "3e-5",
            "max_steps": 256,
            "bounded_choice_aux_source": "encoder_option_retrieval_web_task_candidate_head",
            "bounded_choice_train_head_only": True,
            "bounded_decoder_train_sampler": "web_task_family_balanced",
            "bounded_choice_contrast_weight": 0.5,
            "bounded_choice_contrast_margin": 0.08,
            "preservation_kl_weight": 6.0,
        },
        "gates": gates,
        "command": command,
        "claim_boundary": [
            "This is a guarded head-only probe of a separate Web task-candidate scorer head on answerable no-abstain Web geometry, not a promotion.",
            "Non-abstention tasks remove abstain because visible current-state verifier evidence makes a concrete choice answerable.",
            "Promotion requires canary/residual preservation and Web heldout/successor improvement under selected scorer.",
        ],
        "source_artifacts": {
            "train_rows": rel(TRAIN_ROWS),
            "successor_strict_rows": rel(STRICT_ROWS),
            "scorer_audit": rel(SCORER_AUDIT),
            "semantic_metadata_audit": rel(ART / "stage11601_semantic_candidate_metadata_patch_audit/semantic_candidate_metadata_patch_audit.json"),
            "web_head_code": rel(ROOT / "legacy_src/agentkernel_lite/training_loop.py"),
            "init_runtime": rel(INIT_RUNTIME),
        },
        "outputs": {"manifest": rel(MANIFEST), "command": rel(COMMAND), "summary": rel(SUMMARY), "runtime_model": rel(RUNTIME_OUT)},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(MANIFEST, manifest)
    write_json(COMMAND, {"command": command})
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "metrics": summary["metrics"], "gates": gates, "objective_settings": summary["objective_settings"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
