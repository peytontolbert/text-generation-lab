#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10604
NAME = "stage10604_fresh_python_cpp_mixed_contract_semantic_output_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "fresh_python_cpp_mixed_contract_semantic_output_probe_request.json"
COMMAND_JSON = OUT_DIR / "fresh_python_cpp_mixed_contract_semantic_output_probe_command.json"
MANIFEST_JSONL = OUT_DIR / "fresh_python_cpp_mixed_contract_semantic_output_probe_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SUPPORT_PACKAGE = ROOT / "runs/local/artifacts/stage10602_fresh_python_cpp_mixed_contract_semantic_output_package/fresh_python_cpp_mixed_contract_semantic_output_package.json"
SUPPORT_ROWS = ROOT / "runs/local/artifacts/stage10602_fresh_python_cpp_mixed_contract_semantic_output_package/support_rows.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10602_fresh_python_cpp_mixed_contract_semantic_output_package/strict_eval_rows.jsonl"
INTERFACE_AUDIT = ROOT / "runs/local/artifacts/stage10603_fresh_python_cpp_mixed_contract_semantic_output_audit/fresh_python_cpp_mixed_contract_semantic_output_audit.json"
CANARY_BASELINE = ROOT / "runs/local/artifacts/stage10595_fresh_python_cpp_mixed_contract_canary_audit/fresh_python_cpp_mixed_contract_canary_audit.json"

INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10586_fresh_python_cpp_visible_candidate_probe/runtime_model/runtime_model_bundle.json"
PRESERVATION_REF = ROOT / "runs/local/artifacts/stage10586_fresh_python_cpp_visible_candidate_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10605_fresh_python_cpp_mixed_contract_semantic_output_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10605_fresh_python_cpp_mixed_contract_semantic_output_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10605_fresh_python_cpp_mixed_contract_semantic_output_probe/runtime_model"


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


def normalize_rows() -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    split_counts = {"train": 0, "eval": 0, "strict_eval": 0}
    language_counts: dict[str, int] = {}
    for path, out_split in ((SUPPORT_ROWS, "train"), (STRICT_ROWS, "strict_eval")):
        for row in load_jsonl(path):
            copied = json.loads(json.dumps(row))
            copied["split"] = out_split
            copied["loss_mask"] = {"decoder_ce": True}
            copied["expected_enabled_loss"] = "decoder_ce"
            copied["disable_losses"] = [] if out_split == "train" else ["denoise_ce", "runtime_reward", "structured_aux"]
            rows.append(copied)
            split_counts[out_split] += 1
            language = str(copied.get("language_family") or "unknown")
            language_counts[language] = language_counts.get(language, 0) + 1
    return rows, split_counts, dict(sorted(language_counts.items()))


def build_command(split_counts: dict[str, int]) -> list[str]:
    return [
        "env",
        f"TMPDIR={TMPDIR}",
        f"TEMP={TMPDIR}",
        f"TMP={TMPDIR}",
        "AGENTKERNEL_TRAIN_DEVICE=cuda",
        "conda", "run", "-n", "trellis",
        "python", str(TRAINER),
        "--repo-root", str(ROOT),
        "--manifest", str(MANIFEST_JSONL),
        "--mode", "bounded_decoder_ce_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG),
        "--tokenizer-json", str(TOKENIZER_JSON),
        "--tokenizer-config", str(TOKENIZER_CONFIG),
        "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows", str(split_counts["train"]),
        "--max-eval-rows", "0",
        "--max-strict-rows", str(split_counts["strict_eval"]),
        "--max-steps", "96",
        "--batch-size", "1",
        "--learning-rate", "6e-6",
        "--max-encoder-tokens", "1024",
        "--max-decoder-tokens", "32",
        "--decoder-ce-weight", "1.0",
        "--bounded-choice-aux-weight", "1.0",
        "--bounded-choice-aux-source", "decoder_first_step",
        "--structured-aux-weight", "0.0",
        "--denoise-weight", "0.0",
        "--eos-loss-weight", "2.0",
        "--enable-generation-audit",
        "--max-generation-rows", "24",
        "--max-generation-tokens", "32",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir", str(ROOT / RUNTIME_MODEL_DIR),
        "--initialize-from-runtime-model", str(INIT_RUNTIME),
        "--preservation-reference-runtime-model", str(PRESERVATION_REF),
        "--preservation-kl-weight", "1.0",
        "--no-final-checkpoint-export",
        "--skip-final-model-save", "1",
        "--output-dir", str(ROOT / OUTPUT_DIR),
        "--run-id", RUN_ID,
    ]


def main() -> None:
    support_package = load_json(SUPPORT_PACKAGE)
    interface_audit = load_json(INTERFACE_AUDIT)
    canary = load_json(CANARY_BASELINE)
    manifest_rows, split_counts, language_counts = normalize_rows()
    command = build_command(split_counts)
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(support_package.get("passed")),
        "decision": "fresh_python_cpp_mixed_contract_semantic_output_probe_ready",
        "source_support_package": display(SUPPORT_PACKAGE),
        "interface_audit": display(INTERFACE_AUDIT),
        "manifest": display(MANIFEST_JSONL),
        "run_id": RUN_ID,
        "output_dir": OUTPUT_DIR,
        "runtime_model_dir": RUNTIME_MODEL_DIR,
        "rows": len(manifest_rows),
        "split_counts": split_counts,
        "language_counts": language_counts,
        "initialize_from_runtime_model": display(INIT_RUNTIME),
        "preservation_reference_runtime_model": display(PRESERVATION_REF),
        "claim_scope": [
            "Fresh-root target-100M probe on the stage10602 semantic-output successor package for Python/C++ mixed-contract rows.",
            "Starts from the stage10586 fresh-transfer runtime so any gain isolates the effect of semantic decoder targets rather than a stronger checkpoint.",
            "The key question is whether separating decoder CE from bare option labels improves the harder mixed-contract interface without regressing the repaired canary.",
        ],
        "motivation": {
            "fresh_support_rows": ((support_package.get("rows") or {}).get("support_rows")),
            "fresh_strict_rows": ((support_package.get("rows") or {}).get("strict_eval_rows")),
            "strict_decoder_equals_label_rows": ((interface_audit.get("strict_eval") or {}).get("decoder_equals_label_rows")),
            "strict_mean_decoder_token_length": ((interface_audit.get("strict_eval") or {}).get("mean_decoder_token_length")),
            "strict_max_decoder_token_length": ((interface_audit.get("strict_eval") or {}).get("max_decoder_token_length")),
            "stage10595_canary_bounded_accuracy": ((canary.get("summary") or {}).get("bounded_accuracy")),
        },
        "training_deltas": {
            "train_support_manifest": "stage10602_fresh_python_cpp_mixed_contract_semantic_output_package",
            "initialize_from_runtime_model": "stage10586_fresh_python_cpp_visible_candidate_probe",
            "preservation_reference_runtime_model": "stage10586_fresh_python_cpp_visible_candidate_probe",
            "max_steps": "96",
            "learning_rate": "6e-6",
            "bounded_choice_aux_source": "decoder_first_step",
            "max_decoder_tokens": "32",
            "max_generation_tokens": "32",
        },
        "required_honesty_gates": [
            "stage10602 keeps the same fresh-root split as stage10591 and changes only the decoder-output contract",
            "bounded-choice constrained scoring must use bounded_choice_target_label rather than decoder_text",
            "post-run repaired v2.7 canary must remain at least 22/24 bounded",
            "post-run fresh strict result must be reported separately from the old 24-row canary and separately from any Gemma baseline",
            "no Rust/Web headline can be made from this package because it covers Python and C/C++ only",
        ],
        "post_run_required_artifacts": [
            "bounded_decoder_probe/execution_result.json",
            "post-run repaired v2.7 canary audit against stage10605 runtime",
            "post-run semantic-output result audit against stage10594 and stage10599 baselines",
        ],
        "known_limits": [
            "This probe intentionally only targets fresh Python and C/C++ because Rust/Web fresh-root supply is still too thin on this path.",
            "The semantic-output contract increases decoder length substantially for retrieve/verifier rows, so full-vocab generation quality is now a more meaningful signal than bare-label emission.",
        ],
        "next_best_step": "Launch the stage10605 probe from this request, then compare it against stage10594 and stage10599 to see whether semantic decoder targets reduce the mixed-contract collapse.",
        "command": command,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(MANIFEST_JSONL, manifest_rows)
    write_json(COMMAND_JSON, {"command": command, "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR)})
    write_json(REQUEST_JSON, request)
    write_json(SUMMARY, {
        "stage": STAGE,
        "passed": True,
        "request": display(REQUEST_JSON),
        "manifest": display(MANIFEST_JSONL),
        "split_counts": split_counts,
        "language_counts": language_counts,
    })
    print(json.dumps({"stage": STAGE, "passed": request["passed"], "run_id": RUN_ID, "rows": len(manifest_rows)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
