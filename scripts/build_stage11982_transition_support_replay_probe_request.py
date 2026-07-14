#!/usr/bin/env python3
"""Build a guarded replay probe request for Stage11981 multilingual transition support."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11982
NAME = "stage11982_transition_support_replay_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "transition_support_replay_probe_request.json"
COMMAND_JSON = OUT / "transition_support_replay_command.json"
MANIFEST = OUT / "transition_support_replay_manifest.jsonl"
SUPPORT_ROWS = ART / "stage11981_multilingual_transition_support_rollup/multilingual_transition_support_rows.jsonl"
BASE_ROWS = ART / "stage11955_transition_5k_v1_multisource_package/transition_projection_rows_5k_v1.jsonl"
INIT_RUNTIME = ART / "stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json"
RUNTIME_DIR = ART / "stage11983_transition_support_replay_probe/runtime_model"
OUTPUT_DIR = ART / "stage11983_transition_support_replay_probe/bounded_decoder_probe"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _status_value_for_option(option_value: str) -> str:
    text = option_value.lower()
    if "focused verifier" in text and "passed" in text:
        return "PASS_TO_PASS"
    if "collection/build succeeded" in text or "only collection" in text:
        return "PASS_CURRENT_BUILD"
    if "insufficient evidence" in text or "no local-source verifier" in text:
        return "INSUFFICIENT_EVIDENCE"
    if "failed" in text or "underhydrated" in text:
        return "FAIL_TO_FAIL"
    return option_value


def _normalized_options(row: dict[str, Any]) -> list[dict[str, Any]]:
    options = row.get("opaque_options") if isinstance(row.get("opaque_options"), list) else []
    normalized: list[dict[str, Any]] = []
    for option in options:
        if not isinstance(option, dict):
            continue
        label = str(option.get("label") or "").strip()
        value = str(option.get("value") or "").strip()
        if not label:
            continue
        semantic_value = _status_value_for_option(value)
        normalized.append({
            "label": label,
            "value": semantic_value,
            "text": value or semantic_value,
            "role": "verifier_transition_status",
            "artifact_type": "verifier_status",
            "canonical_value": semantic_value,
            "evidence_ids": [str(row.get("selected_test_anchor") or row.get("source_root_id") or row.get("repo_id") or "verifier")],
        })
    return normalized


def normalize_train_row(row: dict[str, Any], idx: int) -> dict[str, Any]:
    out = dict(row)
    target_label = str(row.get("bounded_choice_target_label") or row.get("target_text") or row.get("decoder_text") or "").strip()
    observed_transition = str(row.get("observed_verifier_transition") or (row.get("standalone_projection_source") or {}).get("observed_verifier_transition") or "").strip()
    options = _normalized_options(row)
    out["row_id"] = f"{row.get('row_id')}::stage11982_train"
    out["split"] = "train"
    out["split_role"] = "replay_support_only"
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["stage11982_role"] = "multilingual_support_replay_train"
    out["bounded_choice_target_label"] = target_label
    out["target_text"] = target_label
    out["decoder_text"] = target_label
    out["target"] = {
        "bounded_choice_target_label": target_label,
        "decoder_text": target_label,
        "semantic_value": observed_transition or target_label,
    }
    projection = dict(row.get("standalone_projection_source") or {})
    projection["opaque_options"] = options
    projection["gold_label"] = target_label
    projection["gold_value"] = observed_transition or target_label
    projection["stage11982_option_normalization"] = "top_level_options_mirrored_with_verifier_status_values"
    out["standalone_projection_source"] = projection
    out["loss_mask"] = {
        "bounded_choice_aux": True,
        "decoder_ce": True,
        "structured_aux": True,
        "transition_projection": True,
    }
    return out


def normalize_eval_row(row: dict[str, Any], split: str, idx: int) -> dict[str, Any]:
    out = dict(row)
    out["row_id"] = f"{row.get('row_id')}::stage11982_{split}"
    out["split"] = split
    out["stage11982_role"] = "old_transition_retention_eval"
    return out


def main() -> None:
    support = [normalize_train_row(row, i) for i, row in enumerate(read_jsonl(SUPPORT_ROWS))]
    base = read_jsonl(BASE_ROWS)
    validation = [normalize_eval_row(row, "eval", i) for i, row in enumerate(base) if row.get("split") == "validation"][:248]
    strict = [normalize_eval_row(row, "strict_eval", i) for i, row in enumerate(base) if row.get("split") == "strict_eval"][:356]
    manifest_rows = support + validation + strict
    write_jsonl(MANIFEST, manifest_rows)
    command = [
        "env", "CUDA_VISIBLE_DEVICES=2", "NVIDIA_VISIBLE_DEVICES=2", "AGENTKERNEL_EVAL_DEVICE=cuda:0", "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True", "TMPDIR=/data/tmp", "TEMP=/data/tmp", "TMP=/data/tmp",
        "conda", "run", "-n", "trellis", "python", str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST), "--mode", "bounded_decoder_ce_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"),
        "--tokenizer-json", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),
        "--tokenizer-config", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),
        "--tokenizer-hashlock", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows", str(len(support)), "--max-eval-rows", str(len(validation)), "--max-strict-rows", str(len(strict)),
        "--max-steps", "96", "--batch-size", "4", "--learning-rate", "5e-5", "--max-encoder-tokens", "768", "--max-decoder-tokens", "16",
        "--decoder-ce-weight", "0.0", "--bounded-choice-aux-weight", "2.0", "--bounded-choice-root-group-aux-weight", "0.0",
        "--bounded-choice-aux-source", "encoder_option_retrieval_semantic_candidate_head", "--bounded-choice-train-head-only",
        "--bounded-decoder-train-sampler", "cyclic", "--bounded-choice-contrast-weight", "0.0", "--bounded-choice-contrast-margin", "0.08",
        "--bounded-choice-same-role-listwise-weight", "0.2", "--bounded-choice-verifier-value-listwise-weight", "0.6",
        "--structured-aux-weight", "0.0", "--denoise-weight", "0.0", "--eos-loss-weight", "1.0",
        "--enable-generation-audit", "--max-generation-rows", "8", "--max-generation-tokens", "8", "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness", "--runtime-model-save-dir", str(RUNTIME_DIR),
        "--initialize-from-runtime-model", str(INIT_RUNTIME), "--preservation-reference-runtime-model", str(INIT_RUNTIME), "--preservation-kl-weight", "8.0",
        "--no-final-checkpoint-export", "--output-dir", str(OUTPUT_DIR),
    ]
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "transition_support_replay_probe_request_ready_diagnostic_only",
        "source_artifacts": {"support_rows": rel(SUPPORT_ROWS), "base_rows": rel(BASE_ROWS), "init_runtime": rel(INIT_RUNTIME)},
        "manifest_summary": {"train_support_rows": len(support), "validation_rows": len(validation), "strict_rows": len(strict), "total_rows": len(manifest_rows)},
        "claim_boundary": "diagnostic replay only; Stage11981 rows are not sufficient for a frontier or source-heldout claim",
        "promotion_gate": {"old_transition_retention": ">=364/640 in postrun audit", "protected_compact_gates": "must preserve Stage11507/11924 gates", "support_fit": "must improve support rows without strict collapse", "no_promotion_if": "heldout transition score does not improve beyond Stage11924 or compact gates regress"},
        "command": command,
        "outputs": {"summary": rel(SUMMARY), "command": rel(COMMAND_JSON), "manifest": rel(MANIFEST), "runtime_dir": rel(RUNTIME_DIR), "output_dir": rel(OUTPUT_DIR)},
        "next_stage_recommendation": {"stage": "stage11983_transition_support_replay_probe", "action": "Run this command on GPU2 only, then audit against old transition 640 and protected compact gates."},
    }
    write_json(COMMAND_JSON, {"command": command})
    write_json(SUMMARY, artifact)
    print(json.dumps({"decision": artifact["decision"], "manifest_summary": artifact["manifest_summary"], "claim_boundary": artifact["claim_boundary"], "next": artifact["next_stage_recommendation"]}, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
