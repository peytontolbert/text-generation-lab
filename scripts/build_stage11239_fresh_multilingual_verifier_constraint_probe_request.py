#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11239
NAME = "stage11239_fresh_multilingual_verifier_constraint_probe_request"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_multilingual_verifier_constraint_probe_request.json"
COMMAND_JSON = OUT_DIR / "fresh_multilingual_verifier_constraint_probe_command.json"
MANIFEST = OUT_DIR / "fresh_multilingual_verifier_constraint_probe_manifest.jsonl"

BASE_PACKAGE = ARTIFACTS / "stage11198_role_focused_residual_support_package"
BASE_TRAIN = BASE_PACKAGE / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE_PACKAGE / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE_PACKAGE / "agentkernel_lite_encdec_strict_eval.jsonl"
FRESH_PACKAGE = ARTIFACTS / "stage11238_fresh_multilingual_verifier_constraint_package"
FRESH_SUMMARY = FRESH_PACKAGE / "fresh_multilingual_verifier_constraint_package.json"
FRESH_TRAIN = FRESH_PACKAGE / "fresh_verifier_constraint_train_rows.jsonl"
FRESH_VALIDATION = FRESH_PACKAGE / "fresh_verifier_constraint_validation_rows.jsonl"
FRESH_STRICT = FRESH_PACKAGE / "fresh_verifier_constraint_strict_rows.jsonl"
RESIDUAL_BANK = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"
INIT_RUNTIME = ARTIFACTS / "stage11200_role_focused_residual_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ARTIFACTS / "stage11240_fresh_multilingual_verifier_constraint_probe"
PROBE_OUT = RUN_DIR / "bounded_decoder_probe"
RUNTIME_OUT = RUN_DIR / "runtime_model"


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


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def by_lang(rows: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        lang = str(row.get("language_family") or row.get("language") or "unknown")
        out[lang] = out.get(lang, 0) + 1
    return dict(sorted(out.items()))


def main() -> None:
    fresh_summary = load_json(FRESH_SUMMARY)
    if not fresh_summary.get("passed"):
        raise SystemExit("Stage11238 fresh package did not pass")

    base_train = load_jsonl(BASE_TRAIN)
    base_validation = load_jsonl(BASE_VALIDATION)
    base_strict = load_jsonl(BASE_STRICT)
    fresh_train = load_jsonl(FRESH_TRAIN)
    fresh_validation = load_jsonl(FRESH_VALIDATION)
    fresh_strict = load_jsonl(FRESH_STRICT)
    residual = load_jsonl(RESIDUAL_BANK)

    protected_eval_rows = base_validation + base_strict + residual + fresh_validation + fresh_strict
    protected_roots = {root_key(row) for row in protected_eval_rows}
    fresh_train_roots = {root_key(row) for row in fresh_train}
    overlaps = sorted(fresh_train_roots & protected_roots)
    if overlaps:
        raise SystemExit(f"fresh train rows overlap protected eval/residual/fresh eval roots: {overlaps[:10]}")

    train_rows = base_train + fresh_train
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
        "--max-steps", "128",
        "--batch-size", "4",
        "--learning-rate", "8e-6",
        "--max-encoder-tokens", "768",
        "--max-decoder-tokens", "16",
        "--decoder-ce-weight", "0.1",
        "--bounded-choice-aux-weight", "1.75",
        "--bounded-choice-aux-source", "encoder_option_retrieval_verifier_conditioned",
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
        "--preservation-kl-weight", "1.0",
        "--no-final-checkpoint",
        "--output-dir", str(PROBE_OUT),
    ]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "fresh_multilingual_verifier_constraint_probe_requested",
        "rationale": [
            "Existing residual packages and scorer variants stayed flat; Stage11238 supplies fresh root-disjoint verifier/test-constraint evidence rows.",
            "This request isolates data geometry: no new scorer head and no contrast loss, preserving the Stage11200 canary runtime with KL=1.0.",
            "Fresh validation/strict rows are held out for postrun scoring and are not included in the trainer eval manifest.",
        ],
        "metrics": {
            "base_train_rows": len(base_train),
            "fresh_train_rows": len(fresh_train),
            "train_rows": len(train_rows),
            "base_validation_rows": len(base_validation),
            "base_strict_rows": len(base_strict),
            "fresh_validation_rows_for_postrun": len(fresh_validation),
            "fresh_strict_rows_for_postrun": len(fresh_strict),
            "residual_rows_for_postrun": len(residual),
            "fresh_train_unique_roots": len(fresh_train_roots),
            "protected_root_overlaps": overlaps,
            "fresh_train_by_language": by_lang(fresh_train),
            "fresh_validation_by_language": by_lang(fresh_validation),
            "fresh_strict_by_language": by_lang(fresh_strict),
            "c_cpp_gap": (fresh_summary.get("counts") or {}).get("c_cpp_gap"),
        },
        "promotion_gate_for_postrun": {
            "clean_strict_must_remain": "22/22",
            "clean_validation_should_not_regress": ">=20/23",
            "clean_residual_must_improve_for_frontier_claim": ">5/10",
            "verifier_and_test_constraint_residual_must_improve": ">0/3",
            "fresh_validation_and_strict_report_required": True,
        },
        "source_artifacts": {
            "base_train": rel(BASE_TRAIN),
            "base_validation": rel(BASE_VALIDATION),
            "base_strict": rel(BASE_STRICT),
            "fresh_package": rel(FRESH_SUMMARY),
            "fresh_train": rel(FRESH_TRAIN),
            "fresh_validation": rel(FRESH_VALIDATION),
            "fresh_strict": rel(FRESH_STRICT),
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
