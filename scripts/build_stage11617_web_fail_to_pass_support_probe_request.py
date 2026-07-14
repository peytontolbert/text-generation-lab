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
STAGE = 11617
NAME = "stage11617_web_fail_to_pass_support_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "web_fail_to_pass_support_probe_request.json"
COMMAND = OUT / "web_fail_to_pass_support_probe_command.json"
MANIFEST = OUT / "web_fail_to_pass_support_probe_manifest.jsonl"

TRAIN_ROWS = ART / "stage11615_web_mutation_rows_anticheat_audit/web_mutation_rows_admitted_train_support.jsonl"
FILTERED_VALIDATION = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl"
FILTERED_STRICT = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
OLD_VALIDATION = ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl"
OLD_STRICT = ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
INIT_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
PROBE = ART / "stage11617_web_fail_to_pass_support_probe/bounded_decoder_probe"
RUNTIME_OUT = ART / "stage11617_web_fail_to_pass_support_probe/runtime_model"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def row_root(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("root_lineage_key") or row.get("source_root_id") or row.get("row_id"))


def root_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {row_root(row) for row in rows}


def normalize(row: dict[str, Any], split: str) -> dict[str, Any]:
    out = dict(row)
    out["split"] = split
    out.setdefault("prompt_text", out.get("input_text") or out.get("prompt") or "")
    out.setdefault("decoder_text", out.get("target_text") or out.get("bounded_choice_target_label") or "")
    out["loss_mask"] = {"decoder_ce": True, "bounded_choice_aux": True}
    out["expected_enabled_loss"] = "decoder_ce+bounded_choice_aux+bounded_choice_contrast"
    src = dict(out.get("standalone_projection_source") or {})
    src.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = src
    out["target"] = {
        "decoder_text": out.get("decoder_text"),
        "bounded_choice_target_label": out.get("bounded_choice_target_label") or out.get("target_text"),
        "semantic_value": out.get("target_semantic_value") or out.get("semantic_target_value"),
    }
    return out


def option_count(row: dict[str, Any]) -> int:
    opts = row.get("opaque_options") or (row.get("standalone_projection_source") or {}).get("opaque_options") or []
    return len(opts)


def all_false(rows: list[dict[str, Any]], key: str) -> bool:
    return all(row.get(key) is False for row in rows)


def main() -> None:
    train = [normalize(row, "train") for row in load_jsonl(TRAIN_ROWS)]
    validation = [normalize(row, "eval") for row in load_jsonl(FILTERED_VALIDATION)]
    protected_strict = [normalize(row, "strict_eval") for row in load_jsonl(FILTERED_STRICT)]
    old_validation = load_jsonl(OLD_VALIDATION)
    old_strict = load_jsonl(OLD_STRICT)

    manifest = train + validation + protected_strict
    overlaps = {
        "train_vs_filtered_validation": sorted(root_ids(train) & root_ids(validation)),
        "train_vs_filtered_strict": sorted(root_ids(train) & root_ids(protected_strict)),
        "train_vs_old_validation": sorted(root_ids(train) & root_ids(old_validation)),
        "train_vs_old_strict": sorted(root_ids(train) & root_ids(old_strict)),
    }
    anti_cheat = load_json(ART / "stage11615_web_mutation_rows_anticheat_audit/web_mutation_rows_anticheat_audit.json")

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
        str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(MANIFEST),
        "--mode",
        "bounded_decoder_ce_probe",
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        str(ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"),
        "--tokenizer-json",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),
        "--tokenizer-config",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),
        "--tokenizer-hashlock",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows",
        str(len(train)),
        "--max-eval-rows",
        str(len(validation)),
        "--max-strict-rows",
        str(len(protected_strict)),
        "--max-steps",
        "96",
        "--batch-size",
        "4",
        "--learning-rate",
        "2e-7",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "16",
        "--decoder-ce-weight",
        "0.04",
        "--bounded-choice-aux-weight",
        "3.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval_web_task_candidate_head",
        "--bounded-decoder-train-sampler",
        "web_task_family_balanced",
        "--bounded-choice-contrast-weight",
        "0.5",
        "--bounded-choice-contrast-margin",
        "0.08",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--eos-loss-weight",
        "4.0",
        "--enable-generation-audit",
        "--max-generation-rows",
        "8",
        "--max-generation-tokens",
        "16",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(RUNTIME_OUT),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-kl-weight",
        "8.0",
        "--no-final-checkpoint-export",
        "--output-dir",
        str(PROBE),
    ]

    gates = {
        "train_rows_are_36": len(train) == 36,
        "complete_six_task_roots_are_6": len(root_ids(train)) == 6,
        "filtered_validation_rows_are_22": len(validation) == 22,
        "filtered_strict_rows_are_22": len(protected_strict) == 22,
        "no_root_overlap_with_protected_sets": all(not vals for vals in overlaps.values()),
        "all_train_rows_train_support_only": all_false(train, "strict_eval_eligible_now"),
        "all_train_rows_have_options": all(option_count(row) >= 2 for row in train),
        "anti_cheat_admitted_all_rows": anti_cheat.get("admitted_rows") == 36 and anti_cheat.get("rejected_rows") == 0,
        "gpu2_mask_present": "CUDA_VISIBLE_DEVICES=2" in command and "NVIDIA_VISIBLE_DEVICES=2" in command,
        "task_family_sampler_enabled": "web_task_family_balanced" in command,
        "contrast_enabled": "--bounded-choice-contrast-weight" in command and command[command.index("--bounded-choice-contrast-weight") + 1] == "0.5",
        "preservation_kl_high": "--preservation-kl-weight" in command and float(command[command.index("--preservation-kl-weight") + 1]) >= 8.0,
    }

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": all(gates.values()),
        "decision": "guarded_web_fail_to_pass_probe_ready" if all(gates.values()) else "guarded_web_fail_to_pass_probe_blocked",
        "metrics": {
            "train_rows": len(train),
            "train_roots": len(root_ids(train)),
            "filtered_validation_rows": len(validation),
            "filtered_strict_rows": len(protected_strict),
            "train_by_task": dict(Counter(str(row.get("task_type")) for row in train)),
            "train_by_target_role": dict(Counter(str(row.get("target_semantic_value") or row.get("semantic_target_value")) for row in train)),
            "root_overlaps": overlaps,
        },
        "objective_settings": {
            "bounded_choice_aux_source": "encoder_option_retrieval_web_task_candidate_head",
            "bounded_decoder_train_sampler": "web_task_family_balanced",
            "bounded_choice_contrast_weight": 0.5,
            "bounded_choice_contrast_margin": 0.08,
            "preservation_kl_weight": 8.0,
            "learning_rate": "2e-7",
            "max_steps": 96,
            "batch_size": 4,
            "head_only": False,
        },
        "promotion_gates_for_postrun": {
            "filtered_strict": "22/22",
            "filtered_validation": ">=20/22",
            "old_canary_strict": "23/23",
            "old_canary_validation": ">=21/23",
            "residual_bank": ">=7/10",
            "web_heldout": ">35/66 first improvement gate",
            "controlled_mutation_support": "diagnostic only; never headline eval",
        },
        "gates": gates,
        "command": command,
        "claim_boundary": [
            "This is a guarded training probe using controlled bug-injection FAIL_TO_PASS rows as train support only.",
            "It is not an organic Web maintainer benchmark and cannot by itself support broad Web or patch-repair claims.",
            "Promotion requires Web heldout movement plus preservation of Stage11507 residual/canary gates.",
        ],
        "source_artifacts": {
            "train_support_rows": rel(TRAIN_ROWS),
            "anti_cheat_audit": rel(ART / "stage11615_web_mutation_rows_anticheat_audit/web_mutation_rows_anticheat_audit.json"),
            "support_decision": rel(ART / "stage11616_web_fail_to_pass_support_decision/web_fail_to_pass_support_decision.json"),
            "filtered_validation": rel(FILTERED_VALIDATION),
            "filtered_strict": rel(FILTERED_STRICT),
            "old_validation_for_overlap_check": rel(OLD_VALIDATION),
            "old_strict_for_overlap_check": rel(OLD_STRICT),
            "init_runtime": rel(INIT_RUNTIME),
        },
        "outputs": {
            "manifest": rel(MANIFEST),
            "command": rel(COMMAND),
            "summary": rel(SUMMARY),
            "runtime_model": rel(RUNTIME_OUT),
            "probe_output": rel(PROBE),
        },
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
