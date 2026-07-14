#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11301
NAME = "stage11301_semantic_candidate_scorer_probe_request"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "semantic_candidate_scorer_probe_request.json"
COMMAND_JSON = OUT_DIR / "semantic_candidate_scorer_probe_command.json"
MANIFEST = OUT_DIR / "semantic_candidate_scorer_probe_manifest.jsonl"

BASE_PACKAGE = ARTIFACTS / "stage11198_role_focused_residual_support_package"
BASE_TRAIN = BASE_PACKAGE / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE_PACKAGE / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE_PACKAGE / "agentkernel_lite_encdec_strict_eval.jsonl"
JUDGMENT_PACKAGE = ARTIFACTS / "stage11296_capped_fact_rich_verifier_package"
JUDGMENT_SUMMARY = JUDGMENT_PACKAGE / "capped_fact_rich_verifier_package.json"
JUDGMENT_AUDIT = JUDGMENT_SUMMARY
JUDGMENT_TRAIN = JUDGMENT_PACKAGE / "capped_fact_rich_verifier_train_rows.jsonl"
JUDGMENT_VALIDATION = JUDGMENT_PACKAGE / "capped_fact_rich_verifier_validation_rows.jsonl"
JUDGMENT_STRICT = JUDGMENT_PACKAGE / "capped_fact_rich_verifier_strict_rows.jsonl"
RESIDUAL_BANK = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"
INIT_RUNTIME = ARTIFACTS / "stage11200_role_focused_residual_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ARTIFACTS / "stage11302_semantic_candidate_scorer_probe"
PROBE_OUT = RUN_DIR / "bounded_decoder_probe"
RUNTIME_OUT = RUN_DIR / "runtime_model"


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


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items()))


def main() -> None:
    package = load_json(JUDGMENT_SUMMARY)
    audit = load_json(JUDGMENT_AUDIT)
    if not package.get("passed"):
        raise SystemExit("Stage11296 package did not pass")
    if not audit.get("passed"):
        raise SystemExit("Stage11296 audit did not pass")

    base_train = load_jsonl(BASE_TRAIN)
    base_validation = load_jsonl(BASE_VALIDATION)
    base_strict = load_jsonl(BASE_STRICT)
    judgment_train = load_jsonl(JUDGMENT_TRAIN)
    judgment_validation = load_jsonl(JUDGMENT_VALIDATION)
    judgment_strict = load_jsonl(JUDGMENT_STRICT)
    residual = load_jsonl(RESIDUAL_BANK)

    protected_roots = {root_key(row) for row in base_validation + base_strict + residual + judgment_validation + judgment_strict}
    judgment_train_roots = {root_key(row) for row in judgment_train}
    overlaps = sorted(judgment_train_roots & protected_roots)
    if overlaps:
        raise SystemExit(f"judgment train roots overlap protected roots: {overlaps[:10]}")

    train_rows = judgment_train + base_train
    manifest_rows: list[dict[str, Any]] = []
    for split, rows in (("train", train_rows), ("eval", base_validation), ("strict_eval", base_strict)):
        for row in rows:
            payload = dict(row)
            payload["split"] = split
            manifest_rows.append(payload)
    write_jsonl(MANIFEST, manifest_rows)

    command = [
        "env", "CUDA_VISIBLE_DEVICES=2", "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True", "TMPDIR=/data/tmp", "TEMP=/data/tmp", "TMP=/data/tmp",
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
        "--max-train-rows", str(len(train_rows)),
        "--max-eval-rows", str(len(base_validation)),
        "--max-strict-rows", str(len(base_strict)),
        "--max-steps", "224",
        "--batch-size", "4",
        "--learning-rate", "8e-6",
        "--max-encoder-tokens", "768",
        "--max-decoder-tokens", "16",
        "--decoder-ce-weight", "0.1",
        "--bounded-choice-aux-weight", "2.0",
        "--bounded-choice-aux-source", "encoder_option_retrieval_semantic_candidate_head",
        "--bounded-decoder-train-sampler", "residual_family_balanced",
        "--structured-aux-weight", "0.0",
        "--denoise-weight", "0.0",
        "--eos-loss-weight", "4.0",
        "--enable-generation-audit",
        "--max-generation-rows", "12",
        "--max-generation-tokens", "16",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir", str(RUNTIME_OUT),
        "--initialize-from-runtime-model", str(INIT_RUNTIME),
        "--preservation-reference-runtime-model", str(INIT_RUNTIME),
        "--bounded-choice-contrast-weight", "1.0",
        "--bounded-choice-contrast-margin", "0.10",
        "--preservation-kl-weight", "0.35",
        "--no-final-checkpoint-export",
        "--output-dir", str(PROBE_OUT),
    ]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "semantic_candidate_scorer_probe_requested",
        "rationale": [
            "Stage11296 supplies capped same-root fact-rich verifier/assertion evidence paired with implementation-like changed-source negatives; this request isolates the new semantic candidate scorer head on the same data.",
            "The new scorer uses explicit state-option semantic metadata buckets for task type, evidence role, and verifier transition while preserving base option-retrieval logits.",
            "This is diagnostic and not promotable unless it improves clean residuals beyond 5/10 and verifier_and_test_constraint residuals above 0/3 without clean strict regression.",
        ],
        "metrics": {
            "base_train_rows": len(base_train),
            "judgment_train_rows": len(judgment_train),
            "train_rows": len(train_rows),
            "base_validation_rows": len(base_validation),
            "base_strict_rows": len(base_strict),
            "judgment_validation_rows_for_postrun": len(judgment_validation),
            "judgment_strict_rows_for_postrun": len(judgment_strict),
            "residual_rows_for_postrun": len(residual),
            "protected_root_overlaps": overlaps,
            "judgment_train_by_target": by(judgment_train, "semantic_target_value"),
            "judgment_train_by_language": by(judgment_train, "language_family"),
            "judgment_package_counts": package.get("counts"),
            "judgment_audit": audit.get("audit"),
        },
        "promotion_gate_for_postrun": {
            "clean_strict_must_remain": "22/22",
            "clean_validation_should_not_regress": ">=20/23",
            "clean_residual_must_improve_for_frontier_claim": ">5/10",
            "verifier_and_test_constraint_residual_must_improve": ">0/3",
            "fact_rich_validation_or_strict_should_score_above_majority_baseline": True,
        },
        "source_artifacts": {
            "base_train": rel(BASE_TRAIN),
            "base_validation": rel(BASE_VALIDATION),
            "base_strict": rel(BASE_STRICT),
            "judgment_package": rel(JUDGMENT_SUMMARY),
            "judgment_audit": rel(JUDGMENT_AUDIT),
            "judgment_train": rel(JUDGMENT_TRAIN),
            "judgment_validation": rel(JUDGMENT_VALIDATION),
            "judgment_strict": rel(JUDGMENT_STRICT),
            "residual_bank": rel(RESIDUAL_BANK),
            "initialize_from_runtime": rel(INIT_RUNTIME),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "command_json": rel(COMMAND_JSON),
            "manifest_jsonl": rel(MANIFEST),
            "probe_output_dir": rel(PROBE_OUT),
            "runtime_model_dir": rel(RUNTIME_OUT),
        },
        "command": command,
    }
    write_json(COMMAND_JSON, {"command": command})
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
