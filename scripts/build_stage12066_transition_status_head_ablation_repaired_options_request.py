#!/usr/bin/env python3
"""Build Stage12062 verifier-status-head isolation ablation request."""
from __future__ import annotations

import collections
import datetime as dt
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
NAME = "stage12066_transition_status_head_ablation_repaired_options_request"
OUT = ART / NAME
SUMMARY = OUT / "transition_status_head_ablation_repaired_options_request.json"
MANIFEST = OUT / "transition_status_head_ablation_repaired_options_manifest.jsonl"
COMMAND_JSON = OUT / "transition_status_head_ablation_repaired_options_command.json"
BASE_MANIFEST = ART / "stage11923_transition_listwise_head_only_probe_request/transition_listwise_head_only_manifest.jsonl"
V35_ROWS = ART / "stage12056_transition_support_rollup_v35/transition_support_rows_v35.jsonl"
V35_AUDIT = ART / "stage12057_transition_support_v35_audit/transition_support_v35_audit.json"
INIT_RUNTIME = ART / "stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json"
PRESERVE_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
RUNTIME_DIR = ART / "stage12068_transition_status_head_ablation_repaired_options_probe/runtime_model"
OUTPUT_DIR = ART / "stage12068_transition_status_head_ablation_repaired_options_probe/bounded_decoder_probe"
TRAIN_SCRIPT = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def read_jsonl(p: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def load(p: Path) -> Any:
    return json.loads(p.read_text())


def write_json(p: Path, payload: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_jsonl(p: Path, rows: list[dict[str, Any]]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def split_of(r: dict[str, Any]) -> str:
    return str(r.get("split") or r.get("package_split") or "")


def normalize_mask(r: dict[str, Any]) -> None:
    r["loss_mask"] = {
        "bounded_choice_aux": True,
        "decoder_ce": True,
        "structured_aux": True,
        "transition_projection": True,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SUM.mkdir(parents=True, exist_ok=True)
    base = read_jsonl(BASE_MANIFEST)
    v35 = read_jsonl(V35_ROWS)
    audit = load(V35_AUDIT)
    old_verifier = [r for r in base if split_of(r) == "train" and r.get("task_type") == "transition_verifier_transition"]
    eval_rows = [r for r in base if split_of(r) == "eval"]
    strict_rows = [r for r in base if split_of(r) == "strict_eval"]
    train: list[dict[str, Any]] = []
    for r0 in old_verifier:
        r = dict(r0)
        r["row_id"] = f"{r['row_id']}::stage12066_verifier_replay"
        r["stage12066_replay_source"] = "stage11923_old_transition_verifier_transition_only"
        normalize_mask(r)
        train.append(r)
    for r0 in v35:
        r = dict(r0)
        r["split"] = "train"
        r["package_split"] = "train"
        r["row_id"] = f"{r['row_id']}::stage12066_v35_status_support"
        r["stage12066_support_source"] = "stage12056_v35_verifier_status_support"
        r["stage12066_train_support_only"] = True
        normalize_mask(r)
        source = dict(r.get("standalone_projection_source") or {})
        if not source.get("opaque_options") and r.get("opaque_options"):
            source["opaque_options"] = r.get("opaque_options")
            source.setdefault("gold_label", r.get("bounded_choice_target_label") or r.get("target_label") or r.get("target_text"))
            target = r.get("target") if isinstance(r.get("target"), dict) else {}
            source.setdefault("gold_value", target.get("semantic_value") or r.get("observed_verifier_transition"))
            source["stage12066_repaired_option_mirror"] = True
            r["standalone_projection_source"] = source
            r["stage12066_repaired_option_mirror"] = True
        train.append(r)
    rows = train + eval_rows + strict_rows
    write_jsonl(MANIFEST, rows)
    counts = collections.Counter(split_of(r) for r in rows)
    status_counts = collections.Counter(
        r.get("observed_verifier_transition")
        or (r.get("target") or {}).get("semantic_value")
        or "UNKNOWN"
        for r in train
    )
    language_counts = collections.Counter(r.get("language_family", "unknown") for r in train)
    command = [
        "env", "CUDA_VISIBLE_DEVICES=2", "NVIDIA_VISIBLE_DEVICES=2", "AGENTKERNEL_EVAL_DEVICE=cuda:0",
        "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True", "TMPDIR=/data/tmp", "TEMP=/data/tmp", "TMP=/data/tmp",
        "conda", "run", "-n", "trellis", "python", str(TRAIN_SCRIPT),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST), "--mode", "bounded_decoder_ce_probe",
        "--probe-scale", "target_100m", "--implementation", "transformer", "--model-config", str(MODEL_CONFIG),
        "--tokenizer-json", str(TOKENIZER_JSON), "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--execution-authorized-for-recovery-probe", "--max-train-rows", str(counts["train"]), "--max-eval-rows", str(counts["eval"]), "--max-strict-rows", str(counts["strict_eval"]),
        "--max-steps", "384", "--batch-size", "8", "--learning-rate", "8e-5", "--max-encoder-tokens", "768", "--max-decoder-tokens", "16",
        "--decoder-ce-weight", "0.0", "--bounded-choice-aux-weight", "3.0", "--bounded-choice-root-group-aux-weight", "0.0",
        "--bounded-choice-aux-source", "encoder_option_retrieval_transition_status_head", "--bounded-choice-train-head-only",
        "--bounded-decoder-train-sampler", "cyclic", "--bounded-choice-contrast-weight", "0.0", "--structured-aux-weight", "0.0", "--denoise-weight", "0.0", "--eos-loss-weight", "1.0",
        "--enable-generation-audit", "--max-generation-rows", "8", "--max-generation-tokens", "8", "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness", "--runtime-model-save-dir", str(RUNTIME_DIR), "--initialize-from-runtime-model", str(INIT_RUNTIME),
        "--preservation-reference-runtime-model", str(PRESERVE_RUNTIME), "--preservation-kl-weight", "4.0", "--no-final-checkpoint-export", "--output-dir", str(OUTPUT_DIR),
    ]
    write_json(COMMAND_JSON, command)
    gates = {
        "base_manifest_exists": BASE_MANIFEST.exists(),
        "v35_rows_exists": V35_ROWS.exists(),
        "v35_audit_train_ready": bool(audit.get("train_ready_against_floor_and_hard_audit")),
        "init_runtime_exists": INIT_RUNTIME.exists(),
        "preservation_runtime_exists": PRESERVE_RUNTIME.exists(),
        "old_verifier_replay_rows_160": len(old_verifier) == 160,
        "v35_support_rows_311": len(v35) == 311,
        "train_rows_471": counts["train"] == 471,
        "eval_rows_22": counts["eval"] == 22,
        "strict_rows_22": counts["strict_eval"] == 22,
        "uses_gpu2_mask": "CUDA_VISIBLE_DEVICES=2" in command and "NVIDIA_VISIBLE_DEVICES=2" in command,
        "status_head_enabled": "encoder_option_retrieval_transition_status_head" in command,
        "head_only_enabled": "--bounded-choice-train-head-only" in command,
    }
    passed = all(gates.values())
    summary = {
        "stage": 12066,
        "stage_name": NAME,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "transition_status_head_ablation_repaired_options_request_ready" if passed else "transition_status_head_ablation_repaired_options_request_blocked",
        "passed": passed,
        "execute_now": False,
        "hypothesis": "Stage12063 failed because 256 v35 rows lacked standalone_projection_source.opaque_options, causing option-retrieval scorers to skip whole batches. Mirror top-level opaque_options into standalone_projection_source, then train a separate transition-status head only on old verifier-transition replay plus repaired v35 status rows.",
        "claim_boundary": [
            "Diagnostic only until a routed postrun audit proves old 640 retention and protected gates.",
            "This does not replace the Stage11924 selected frontier unless composite routing beats 364/640 and preserves protected gates.",
        ],
        "row_counts": {"train_rows": counts["train"], "old_verifier_replay_rows": len(old_verifier), "v35_support_rows": len(v35), "eval_rows": counts["eval"], "strict_rows": counts["strict_eval"], "train_language_counts": dict(sorted(language_counts.items())), "train_status_counts": dict(sorted(status_counts.items()))},
        "gates_before_execution": gates,
        "postrun_required_route": {"transition_verifier_transition": "encoder_option_retrieval_transition_status_head from Stage12063", "other_transition_tasks": "encoder_option_retrieval_semantic_candidate_head from Stage11924", "compact_protected": "encoder_option_retrieval_evidence_judgment_head from Stage11507/Stage11924 routing"},
        "promotion_gate": {"old_transition_640_composite": ">=364 retention, >386 Gemma win", "transition_verifier_transition_subset": "must improve over Stage11924", "protected_filtered_strict": "22/22", "protected_old_canary_strict": "23/23", "residual": ">=7/10", "source_heldout_smoke": ">=6/12"},
        "outputs": {"summary": rel(SUMMARY), "summary_mirror": f"runs/summaries/{NAME}.json", "manifest": rel(MANIFEST), "command": rel(COMMAND_JSON), "runtime_dir": rel(RUNTIME_DIR), "output_dir": rel(OUTPUT_DIR)},
        "source_artifacts": {"base_stage11923_manifest": rel(BASE_MANIFEST), "v35_support_rows": rel(V35_ROWS), "v35_audit": rel(V35_AUDIT), "init_runtime": rel(INIT_RUNTIME), "preservation_runtime": rel(PRESERVE_RUNTIME), "stage12061_decision": "runs/summaries/stage12061_guarded_transition_training_decision.json", "stage12065_preflight": "runs/summaries/stage12065_status_head_batch_differentiability_preflight.json"},
        "next_stage_if_executed": "stage12068_transition_status_head_ablation_repaired_options_probe",
        "next_stage_after_execution": "stage12069_transition_status_head_repaired_options_composite_routed_audit",
    }
    write_json(SUMMARY, summary)
    write_json(SUM / f"{NAME}.json", summary)
    print(json.dumps({"passed": passed, "summary": rel(SUMMARY), "row_counts": summary["row_counts"]}, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
