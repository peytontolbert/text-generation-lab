#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11245
NAME = "stage11245_balanced_evidence_role_grounding_probe_request"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "balanced_evidence_role_grounding_probe_request.json"
COMMAND_JSON = OUT_DIR / "balanced_evidence_role_grounding_probe_command.json"
MANIFEST = OUT_DIR / "balanced_evidence_role_grounding_probe_manifest.jsonl"

BASE_PACKAGE = ARTIFACTS / "stage11198_role_focused_residual_support_package"
BASE_TRAIN = BASE_PACKAGE / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE_PACKAGE / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE_PACKAGE / "agentkernel_lite_encdec_strict_eval.jsonl"
BALANCED_PACKAGE = ARTIFACTS / "stage11243_balanced_evidence_role_grounding_package"
BALANCED_SUMMARY = BALANCED_PACKAGE / "balanced_evidence_role_grounding_package.json"
BALANCED_TRAIN = BALANCED_PACKAGE / "balanced_evidence_role_grounding_train_rows.jsonl"
BALANCED_VALIDATION = BALANCED_PACKAGE / "balanced_evidence_role_grounding_validation_rows.jsonl"
BALANCED_STRICT = BALANCED_PACKAGE / "balanced_evidence_role_grounding_strict_rows.jsonl"
RESIDUAL_BANK = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"
INIT_RUNTIME = ARTIFACTS / "stage11200_role_focused_residual_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ARTIFACTS / "stage11246_balanced_evidence_role_grounding_probe"
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
    package = load_json(BALANCED_SUMMARY)
    if not package.get("passed"):
        raise SystemExit("Stage11243 balanced package did not pass")
    base_train = load_jsonl(BASE_TRAIN)
    base_validation = load_jsonl(BASE_VALIDATION)
    base_strict = load_jsonl(BASE_STRICT)
    balanced_train = load_jsonl(BALANCED_TRAIN)
    balanced_validation = load_jsonl(BALANCED_VALIDATION)
    balanced_strict = load_jsonl(BALANCED_STRICT)
    residual = load_jsonl(RESIDUAL_BANK)

    protected = {root_key(row) for row in base_validation + base_strict + residual + balanced_validation + balanced_strict}
    train_roots = {root_key(row) for row in balanced_train}
    overlaps = sorted(train_roots & protected)
    if overlaps:
        raise SystemExit(f"balanced train rows overlap protected roots: {overlaps[:10]}")

    # Put the new balanced role rows first so cyclic and fallback samplers see them early.
    train_rows = balanced_train + base_train
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
        "--max-steps", "256",
        "--batch-size", "4",
        "--learning-rate", "8e-6",
        "--max-encoder-tokens", "768",
        "--max-decoder-tokens", "16",
        "--decoder-ce-weight", "0.1",
        "--bounded-choice-aux-weight", "2.0",
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
        "decision": "balanced_evidence_role_grounding_probe_requested",
        "rationale": [
            "Stage11238 all-positive verifier rows failed all fresh heldout rows.",
            "Stage11243 balances candidate, verifier, and symptom role targets while preserving concrete evidence facts and root split isolation.",
            "This probe tests whether balanced role supervision can break the candidate_change_surface prior without changing scorer architecture.",
        ],
        "metrics": {
            "base_train_rows": len(base_train),
            "balanced_train_rows": len(balanced_train),
            "train_rows": len(train_rows),
            "base_validation_rows": len(base_validation),
            "base_strict_rows": len(base_strict),
            "balanced_validation_rows_for_postrun": len(balanced_validation),
            "balanced_strict_rows_for_postrun": len(balanced_strict),
            "residual_rows_for_postrun": len(residual),
            "protected_root_overlaps": overlaps,
            "balanced_train_by_role": by(balanced_train, "semantic_target_value"),
            "balanced_train_by_language": by(balanced_train, "language_family"),
            "balanced_package_repo_family_split_overlaps": (package.get("counts") or {}).get("repo_family_split_overlaps"),
            "c_cpp_gap": (package.get("counts") or {}).get("c_cpp_gap"),
        },
        "promotion_gate_for_postrun": {
            "clean_strict_must_remain": "22/22",
            "clean_validation_should_not_regress": ">=20/23",
            "clean_residual_must_improve_for_frontier_claim": ">5/10",
            "verifier_and_test_constraint_residual_must_improve": ">0/3",
            "balanced_validation_or_strict_should_improve_vs_stage11244": True,
        },
        "source_artifacts": {
            "base_train": rel(BASE_TRAIN),
            "base_validation": rel(BASE_VALIDATION),
            "base_strict": rel(BASE_STRICT),
            "balanced_package": rel(BALANCED_SUMMARY),
            "balanced_train": rel(BALANCED_TRAIN),
            "balanced_validation": rel(BALANCED_VALIDATION),
            "balanced_strict": rel(BALANCED_STRICT),
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
