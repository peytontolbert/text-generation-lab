#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10579
NAME = "stage10579_visible_candidate_balanced_decisive_contrast_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "visible_candidate_balanced_decisive_contrast_probe_request.json"
COMMAND_JSON = OUT_DIR / "visible_candidate_balanced_decisive_contrast_probe_command.json"
MANIFEST_JSONL = OUT_DIR / "visible_candidate_balanced_decisive_contrast_probe_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SUPPORT_PACKAGE = ROOT / "runs/local/artifacts/stage10578_visible_candidate_balanced_decisive_contrast_support_package/visible_candidate_balanced_decisive_contrast_support_package.json"
SUPPORT_ROWS = ROOT / "runs/local/artifacts/stage10578_visible_candidate_balanced_decisive_contrast_support_package/visible_candidate_balanced_decisive_contrast_support_rows.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10561_visible_candidate_successor_package/strict_eval_rows.jsonl"
EVAL_ROWS = ROOT / "runs/local/artifacts/stage10561_visible_candidate_successor_package/eval_rows.jsonl"
CANARY_AUDIT = ROOT / "runs/local/artifacts/stage10575_visible_candidate_mixed_preservation_canary_audit/visible_candidate_mixed_preservation_canary_audit.json"
TRANSITION_AUDIT = ROOT / "runs/local/artifacts/stage10563_visible_candidate_transition_bounded_audit/visible_candidate_transition_bounded_audit.json"
COMPARISON_AUDIT = ROOT / "runs/local/artifacts/stage10576_visible_candidate_successor_same_manifest_comparison/visible_candidate_successor_same_manifest_comparison.json"

INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10574_visible_candidate_mixed_preservation_probe/runtime_model/runtime_model_bundle.json"
PRESERVATION_REF = ROOT / "runs/local/artifacts/stage10574_visible_candidate_mixed_preservation_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10580_visible_candidate_balanced_decisive_contrast_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10580_visible_candidate_balanced_decisive_contrast_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10580_visible_candidate_balanced_decisive_contrast_probe/runtime_model"


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
    for path, out_split in ((SUPPORT_ROWS, "train"), (EVAL_ROWS, "eval"), (STRICT_ROWS, "strict_eval")):
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
        "--max-eval-rows", str(split_counts["eval"]),
        "--max-strict-rows", str(split_counts["strict_eval"]),
        "--max-steps", "64",
        "--batch-size", "1",
        "--learning-rate", "6e-6",
        "--max-encoder-tokens", "1024",
        "--max-decoder-tokens", "8",
        "--decoder-ce-weight", "1.0",
        "--bounded-choice-aux-weight", "1.0",
        "--bounded-choice-aux-source", "decoder_first_step",
        "--structured-aux-weight", "0.0",
        "--denoise-weight", "0.0",
        "--eos-loss-weight", "2.0",
        "--enable-generation-audit",
        "--max-generation-rows", "24",
        "--max-generation-tokens", "8",
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
    canary = load_json(CANARY_AUDIT)
    transition = load_json(TRANSITION_AUDIT)
    comparison = load_json(COMPARISON_AUDIT)
    manifest_rows, split_counts, language_counts = normalize_rows()
    command = build_command(split_counts)
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(support_package.get("passed")),
        "decision": "visible_candidate_balanced_decisive_contrast_probe_ready",
        "source_support_package": display(SUPPORT_PACKAGE),
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
            "Diagnostic multilingual target-100M probe that starts from the stage10574 restored runtime and trains only on the stage10578 balanced decisive-contrast support plus heldout-preserving eval/strict splits.",
            "Targets decisive_evidence_top1 specifically while preserving the rebuilt verifier/retrieve behavior already recovered in stage10574-stage10576.",
            "Not promotable unless post-run strict bounded accuracy holds at or above the stage10574 baseline and the repaired v2.7 canary remains 22/24.",
        ],
        "motivation": {
            "stage10575_canary_bounded_accuracy": ((canary.get("summary") or {}).get("bounded_accuracy")),
            "stage10563_decisive_decoder_accuracy": ((((transition.get("per_target_subtype") or {}).get("decisive_evidence_top1")) or {}).get("decoder_first_step") or {}).get("accuracy"),
            "stage10576_hundred_m_decisive_exact": ((((comparison.get("hundred_m") or {}).get("by_target_subtype")) or {}).get("decisive_evidence_top1") or {}).get("exact_accuracy"),
            "stage10576_hundred_m_overall_exact": ((((comparison.get("hundred_m") or {}).get("overall")) or {}).get("exact_accuracy")),
        },
        "training_deltas": {
            "train_support_manifest": "stage10578_visible_candidate_balanced_decisive_contrast_support_package",
            "initialize_from_runtime_model": "stage10574_visible_candidate_mixed_preservation_probe",
            "preservation_reference_runtime_model": "stage10574_visible_candidate_mixed_preservation_probe",
            "max_steps": "64",
            "learning_rate": "6e-6",
            "bounded_choice_aux_source": "decoder_first_step",
        },
        "required_honesty_gates": [
            "stage10561 strict_eval rows remain eval-only and never enter train support",
            "stage10578 support rows remain train-only and root-disjoint from stage10561 strict roots",
            "post-run canary audit must remain at least 22/24 bounded on the repaired v2.7 overlay",
            "post-run rebuilt strict bounded audit must stay at least 36/54 overall or the run is non-promotable",
            "post-run same-manifest comparison versus Gemma must be reported separately from bounded-choice runtime audits",
            "decisive-evidence improvement only counts if verifier and retrieve do not regress materially",
        ],
        "post_run_required_artifacts": [
            "bounded_decoder_probe/execution_result.json",
            "post-run repaired v2.7 canary audit",
            "post-run rebuilt strict same-manifest comparison versus Gemma",
            "post-run result audit that compares stage10580 against stage10574-stage10577",
        ],
        "known_limits": [
            "Rust and web still rely on thin source supply and extra permutations rather than fresh roots, so any uplift is still a repair probe rather than a broad scaling claim.",
            "This probe is still bounded-choice-focused and does not solve the longer-term seq2seq frontier on its own.",
        ],
        "next_best_step": "Launch the stage10580 probe from this request, then rerun canary and same-manifest audits before deciding whether the balanced decisive-contrast package is the first non-regressive decisive-evidence improvement.",
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
