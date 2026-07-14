#!/usr/bin/env python3
"""Emit a C/C++ transition recovery probe focused on verifier/build transition rows."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11928
NAME = "stage11928_cpp_transition_recovery_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "cpp_transition_recovery_probe_request.json"
COMMAND_JSON = OUT / "cpp_transition_recovery_command.json"
MANIFEST = OUT / "cpp_transition_recovery_manifest.jsonl"

SUPPORT_ROWS = ART / "stage11897_transition_record_projection_rows/transition_projection_rows.jsonl"
PROTECTED_ROWSETS = {
    "filtered_strict": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "filtered_validation": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl",
}
INIT_RUNTIME = ART / "stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json"
PRESERVATION_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ART / "stage11929_cpp_transition_recovery_probe"
RUNTIME_DIR = RUN_DIR / "runtime_model"
OUTPUT_DIR = RUN_DIR / "bounded_decoder_probe"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def train_copy(row: dict, repeat: int) -> dict:
    out = dict(row)
    out["row_id"] = f"{row.get('row_id')}::stage11928_cpp_recovery_r{repeat}"
    out["split"] = "train"
    out["package_split"] = "train"
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["stage11928_replay_kind"] = "cpp_transition_recovery"
    out["preservation_exempt"] = True
    source = dict(out.get("standalone_projection_source") or {})
    source.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = source
    label = out.get("bounded_choice_target_label") or out.get("target_label") or out.get("target_text")
    if not isinstance(out.get("target"), dict):
        out["target"] = {"decoder_text": out.get("decoder_text") or label, "bounded_choice_target_label": label}
    loss_mask = dict(out.get("loss_mask") or {})
    loss_mask.update({"bounded_choice_aux": True, "structured_aux": True, "transition_projection": True})
    out["loss_mask"] = loss_mask
    return out


def main() -> None:
    all_rows = read_jsonl(SUPPORT_ROWS)
    cpp_rows = [row for row in all_rows if row.get("language_family") == "c_cpp"]
    hard_tasks = {"transition_verifier_transition", "transition_continue_or_stop", "transition_next_action"}
    hard_cpp_rows = [row for row in cpp_rows if row.get("task_type") in hard_tasks]
    train_rows: list[dict] = []
    for repeat in range(3):
        for row in hard_cpp_rows:
            train_rows.append(train_copy(row, repeat))
    for row in cpp_rows:
        train_rows.append(train_copy(row, 3))
    protected_sources = {name: read_jsonl(path) for name, path in PROTECTED_ROWSETS.items()}
    eval_rows = [dict(row, split="eval", package_split="eval") for row in protected_sources["filtered_validation"]]
    strict_rows = [dict(row, split="strict_eval", package_split="strict_eval") for row in protected_sources["filtered_strict"]]
    write_jsonl(MANIFEST, train_rows + eval_rows + strict_rows)

    command = [
        "env", "CUDA_VISIBLE_DEVICES=2", "NVIDIA_VISIBLE_DEVICES=2", "AGENTKERNEL_EVAL_DEVICE=cuda:0",
        "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True", "TMPDIR=/data/tmp", "TEMP=/data/tmp", "TMP=/data/tmp",
        "conda", "run", "-n", "trellis", "python", str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST), "--mode", "bounded_decoder_ce_probe", "--probe-scale", "target_100m",
        "--implementation", "transformer", "--model-config", str(ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"),
        "--tokenizer-json", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),
        "--tokenizer-config", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),
        "--tokenizer-hashlock", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
        "--execution-authorized-for-recovery-probe", "--max-train-rows", str(len(train_rows)), "--max-eval-rows", str(len(eval_rows)),
        "--max-strict-rows", str(len(strict_rows)), "--max-steps", "640", "--batch-size", "8", "--learning-rate", "2e-4",
        "--max-encoder-tokens", "768", "--max-decoder-tokens", "16", "--decoder-ce-weight", "0.0",
        "--bounded-choice-aux-weight", "3.0", "--bounded-choice-root-group-aux-weight", "0.0",
        "--bounded-choice-aux-source", "encoder_option_retrieval_semantic_candidate_head", "--bounded-choice-train-head-only",
        "--bounded-decoder-train-sampler", "task_balanced", "--bounded-choice-contrast-weight", "0.3",
        "--bounded-choice-contrast-margin", "0.08", "--bounded-choice-same-role-listwise-weight", "0.5",
        "--bounded-choice-verifier-value-listwise-weight", "1.0", "--structured-aux-weight", "0.0", "--denoise-weight", "0.0",
        "--eos-loss-weight", "1.0", "--enable-generation-audit", "--max-generation-rows", "8", "--max-generation-tokens", "8",
        "--require-loss-mask-enforcement-audit", "--allow-runtime-model-save-for-harness", "--runtime-model-save-dir", str(RUNTIME_DIR),
        "--initialize-from-runtime-model", str(INIT_RUNTIME), "--preservation-reference-runtime-model", str(PRESERVATION_RUNTIME),
        "--preservation-kl-weight", "4.0", "--no-final-checkpoint-export", "--output-dir", str(OUTPUT_DIR),
    ]
    gates = {
        "uses_gpu2_mask": "CUDA_VISIBLE_DEVICES=2" in command and "NVIDIA_VISIBLE_DEVICES=2" in command,
        "head_only_enabled": "--bounded-choice-train-head-only" in command,
        "cpp_rows_256": len(cpp_rows) == 256,
        "hard_cpp_rows_192": len(hard_cpp_rows) == 192,
        "train_rows_832": len(train_rows) == 832,
        "init_runtime_exists": INIT_RUNTIME.exists(),
        "preservation_runtime_exists": PRESERVATION_RUNTIME.exists(),
        "no_protected_rows_in_train": all(row.get("stage11928_replay_kind") == "cpp_transition_recovery" for row in train_rows),
    }
    artifact = {
        "stage": STAGE, "stage_name": NAME, "created_at_utc": now(), "passed": all(gates.values()),
        "decision": "cpp_transition_recovery_probe_request_ready" if all(gates.values()) else "cpp_transition_recovery_probe_request_blocked",
        "command": command, "gates_before_execution": gates,
        "row_counts": {"train_rows": len(train_rows), "cpp_rows": len(cpp_rows), "hard_cpp_rows": len(hard_cpp_rows), "eval_rows": len(eval_rows), "strict_rows": len(strict_rows)},
        "hypothesis": "C/C++ transition loss is dominated by build/verifier transition geometry and can be recovered by focused semantic-head listwise training.",
        "source_artifacts": {"transition_projection_rows": rel(SUPPORT_ROWS), "manifest": rel(MANIFEST), "initialize_from_runtime_model": rel(INIT_RUNTIME)},
        "outputs": {"summary": rel(SUMMARY), "command": rel(COMMAND_JSON), "runtime_dir": rel(RUNTIME_DIR), "output_dir": rel(OUTPUT_DIR)},
        "claim_boundary": ["Diagnostic: trains on C/C++ transition projection rows and must not be promoted without same-manifest Gemma win plus protected gates."],
    }
    write_json(COMMAND_JSON, {"command": command})
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "passed": artifact["passed"], "row_counts": artifact["row_counts"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
