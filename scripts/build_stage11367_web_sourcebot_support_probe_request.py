#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11367
NAME = "stage11367_web_sourcebot_support_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "web_sourcebot_support_probe_request.json"
CMD = OUT / "web_sourcebot_support_probe_command.json"
MAN = OUT / "web_sourcebot_support_probe_manifest.jsonl"
TRAIN = ART / "stage11364_web_sourcebot_executed_support_rows/web_sourcebot_executed_support_rows.jsonl"
CANARY = ART / "stage11312_deleaked_fail_to_pass_transition_package"
VAL = CANARY / "deleaked_fail_to_pass_validation_rows.jsonl"
STRICT = CANARY / "deleaked_fail_to_pass_strict_rows.jsonl"
HELDOUT = ART / "stage11361_web_llama_stack_executed_heldout_rows/web_llama_stack_executed_heldout_rows.jsonl"
INIT = ART / "stage11200_role_focused_residual_probe/runtime_model/runtime_model_bundle.json"
BASELINE = ART / "stage11365_web_sourcebot_support_current_score/web_sourcebot_support_current_score.json"
RUN = ART / "stage11368_web_sourcebot_support_probe"
PROBE = RUN / "bounded_decoder_probe"
RUNTIME = RUN / "runtime_model"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def mirror_summary() -> None:
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    train = read_jsonl(TRAIN)
    val = read_jsonl(VAL)
    strict = read_jsonl(STRICT)
    heldout = read_jsonl(HELDOUT)
    protected = {root_key(r) for r in val + strict + heldout}
    overlaps = sorted({root_key(r) for r in train} & protected)
    if overlaps:
        raise SystemExit(f"root overlap with protected eval/heldout: {overlaps[:5]}")
    bad = [r.get("row_id") for r in train if r.get("strict_eval_eligible") or not r.get("train_support_only")]
    if bad:
        raise SystemExit(f"non support-only train rows: {bad[:5]}")
    rows = []
    for split, split_rows in [("train", train), ("eval", val), ("strict_eval", strict)]:
        for row in split_rows:
            item = dict(row)
            item["split"] = split
            rows.append(item)
    write_jsonl(MAN, rows)
    baseline = read_json(BASELINE).get("product_metrics", {})
    cmd = [
        "env", "CUDA_VISIBLE_DEVICES=2", "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True", "TMPDIR=/data/tmp", "TEMP=/data/tmp", "TMP=/data/tmp",
        "conda", "run", "-n", "trellis", "python", str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
        "--repo-root", str(ROOT),
        "--manifest", str(MAN),
        "--mode", "bounded_decoder_ce_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", str(ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"),
        "--tokenizer-json", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),
        "--tokenizer-config", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),
        "--tokenizer-hashlock", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows", str(len(train)),
        "--max-eval-rows", str(len(val)),
        "--max-strict-rows", str(len(strict)),
        "--max-steps", "80",
        "--batch-size", "3",
        "--learning-rate", "5e-6",
        "--max-encoder-tokens", "768",
        "--max-decoder-tokens", "16",
        "--decoder-ce-weight", "0.1",
        "--bounded-choice-aux-weight", "2.5",
        "--bounded-choice-aux-source", "encoder_option_retrieval_evidence_judgment_head",
        "--bounded-decoder-train-sampler", "residual_family_balanced",
        "--structured-aux-weight", "0.0",
        "--denoise-weight", "0.0",
        "--eos-loss-weight", "4.0",
        "--enable-generation-audit",
        "--max-generation-rows", "8",
        "--max-generation-tokens", "16",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir", str(RUNTIME),
        "--initialize-from-runtime-model", str(INIT),
        "--preservation-reference-runtime-model", str(INIT),
        "--bounded-choice-contrast-weight", "1.0",
        "--bounded-choice-contrast-margin", "0.10",
        "--preservation-kl-weight", "0.75",
        "--no-final-checkpoint-export",
        "--output-dir", str(PROBE),
    ]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "decision": "web_sourcebot_support_probe_requested_diagnostic_only",
        "metrics": {
            "train_rows": len(train),
            "eval_rows": len(val),
            "strict_rows": len(strict),
            "sealed_heldout_rows_not_in_manifest": len(heldout),
            "root_overlaps_with_eval_or_heldout": overlaps,
            "baseline_sourcebot_support": baseline.get("sourcebot_web_support"),
            "baseline_llama_stack_heldout": baseline.get("llama_stack_web_heldout"),
            "baseline_canary_strict": baseline.get("canary_strict"),
            "baseline_canary_validation": baseline.get("canary_validation"),
        },
        "source_artifacts": {
            "train": rel(TRAIN),
            "baseline_score": rel(BASELINE),
            "canary_validation": rel(VAL),
            "canary_strict": rel(STRICT),
            "sealed_heldout": rel(HELDOUT),
            "init_runtime": rel(INIT),
        },
        "outputs": {"summary": rel(SUMMARY), "command": rel(CMD), "manifest": rel(MAN), "probe_dir": rel(PROBE), "runtime_model": rel(RUNTIME)},
        "promotion_gate": {
            "diagnostic_only": True,
            "sourcebot_support_should_improve": "above 0/6 baseline",
            "sealed_llama_stack_heldout_should_improve": "above 0/6 baseline; heldout was not trained",
            "canary_strict_must_remain": "22/22",
            "canary_validation_must_remain": ">=20/23",
            "frontier_replacement_allowed": False,
        },
        "command": cmd,
    }
    write_json(CMD, {"command": cmd})
    write_json(SUMMARY, summary)
    mirror_summary()
    print(json.dumps({"passed": True, "metrics": summary["metrics"], "cmd": rel(CMD)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
