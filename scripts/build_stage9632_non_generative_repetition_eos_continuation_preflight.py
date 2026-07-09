#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9632
NAME = "stage9632_non_generative_repetition_eos_continuation_preflight"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9631_repetition_guard_probe_audit.json"
BASELINE_SAMPLES = ROOT / "runs/local/artifacts/stage9623_tri_phase_reconnect_tiny_probe/tri_phase_probe/phase3_full_residual_denoise_probe/sample_generation_audit.json"
GUARDED_SAMPLES = ROOT / "runs/local/artifacts/stage9630_tri_phase_repetition_guard_tiny_probe/tri_phase_probe/phase3_full_residual_denoise_probe/sample_generation_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "non_generative_repetition_eos_continuation_manifest.jsonl"
RUN_DIR = OUT_DIR / "episode_step_contract"
AUDIT = OUT_DIR / "non_generative_repetition_eos_continuation_preflight.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NON_GENERATIVE_REPETITION_EOS_CONTINUATION_PREFLIGHT_STAGE9632.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
LOSS_MASK = {
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
    "episode_repair_outcome_ce": True,
    "episode_failure_type_ce": True,
    "episode_boundary_match_ce": True,
    "episode_target_prefix_match_ce": True,
    "episode_step_value_mse": True,
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def repeated_text(text: str) -> bool:
    words = [word for word in text.lower().split() if word]
    if len(words) >= 6:
        for width in (1, 2, 3):
            ngrams = [tuple(words[idx:idx + width]) for idx in range(len(words) - width + 1)]
            counts: dict[tuple[str, ...], int] = {}
            for ngram in ngrams:
                counts[ngram] = counts.get(ngram, 0) + 1
            if counts and max(counts.values()) >= 4:
                return True
    return False


def failure_reasons(sample: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    boundary = sample.get("boundary_next_token") if isinstance(sample.get("boundary_next_token"), dict) else {}
    text = str(sample.get("generated_text") or "")
    if sample.get("short_or_junk"):
        reasons.append("short_or_junk")
    if sample.get("internal_token_leak"):
        reasons.append("internal_token_leak")
    if sample.get("degenerate_repetition") or repeated_text(text):
        reasons.append("degenerate_repetition")
    if not sample.get("stopped_on_eos"):
        reasons.append("unterminated_generation")
    if not sample.get("target_prefix_match"):
        reasons.append("target_prefix_miss")
    if not boundary.get("match"):
        reasons.append("boundary_next_token_miss")
    return sorted(set(reasons))


def outcome_from(reasons: list[str]) -> str:
    if not reasons:
        return "verified_continue"
    if "degenerate_repetition" in reasons:
        return "repair_repetition"
    if "unterminated_generation" in reasons:
        return "repair_eos"
    if "boundary_next_token_miss" in reasons or "target_prefix_miss" in reasons:
        return "repair_prefix_boundary"
    return "repair_output"


def split_for(index: int) -> str:
    return ["train", "eval", "strict_eval"][index % 3]


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_name, path in [("stage9623_baseline", BASELINE_SAMPLES), ("stage9630_guarded", GUARDED_SAMPLES)]:
        samples = load_json(path).get("samples") or []
        for idx, sample in enumerate(samples):
            reasons = failure_reasons(sample)
            boundary = sample.get("boundary_next_token") if isinstance(sample.get("boundary_next_token"), dict) else {}
            generated_text = str(sample.get("generated_text") or "")
            row_id = f"stage9632_{source_name}_{idx:03d}"
            row = {
                "row_id": row_id,
                "source_sample_row_id": sample.get("row_id"),
                "split": split_for(len(rows)),
                "language_family": "mixed",
                "transition_schema": "episode_step_suffix_transition_v1",
                "objective_family": "non_generative_repetition_eos_continuation",
                "encoder_text": "\n".join([
                    "episode_step_suffix_transition_v1",
                    f"source={source_name}",
                    f"generated_text={generated_text}",
                    f"generation_prefix_text={sample.get('generation_prefix_text') or ''}",
                    f"boundary_expected_token_text={boundary.get('expected_token_text') or ''}",
                    f"boundary_generated_token_text={boundary.get('generated_token_text') or ''}",
                    f"generated_char_len={len(generated_text)}",
                    f"guard_event_count={int(sample.get('generation_repetition_guard_event_count') or 0)}",
                    "target_text_hidden=true",
                    "match_labels_hidden=true",
                ]),
                "episode_transition": {
                    "state_t": {
                        "source_stage": source_name,
                        "target_visible": False,
                        "clean_target_hidden_from_model_input": True,
                        "generation_prefix_text": sample.get("generation_prefix_text"),
                        "guard_event_count": int(sample.get("generation_repetition_guard_event_count") or 0),
                    },
                    "action_t": {"action": "OBSERVE_GENERATION_AND_SELECT_CONTINUATION_REPAIR", "target_surface": sample.get("surface") or "suffix_continuation"},
                    "observation_t": {
                        "generated_text": generated_text,
                        "target_prefix_match": bool(sample.get("target_prefix_match")),
                        "boundary_next_token_match": bool(boundary.get("match")),
                        "boundary_expected_rank": boundary.get("expected_rank"),
                        "degenerate_repetition": "degenerate_repetition" in reasons,
                        "short_or_junk": bool(sample.get("short_or_junk")),
                        "stopped_on_eos": bool(sample.get("stopped_on_eos")),
                        "residual_reasons": reasons,
                    },
                    "reward_or_verifier": {
                        "verifier_source": source_name,
                        "step_passed": not reasons,
                        "reward": 1.0 if not reasons else 0.0,
                        "failure_type": "none" if not reasons else "+".join(reasons),
                    },
                    "state_t_plus_1": {"repair_outcome": outcome_from(reasons)},
                },
                "loss_mask": dict(LOSS_MASK),
                "authority": dict(AUTHORITY_CLOSED),
            }
            rows.append(row)
    return rows


def command() -> list[str]:
    return [
        "env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}",
        "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST),
        "--mode", "episode_step_structured_probe",
        "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON),
        "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--max-train-rows", "8", "--max-eval-rows", "8", "--max-strict-rows", "8",
        "--max-steps", "0", "--batch-size", "2", "--learning-rate", "2e-4",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", "8",
        "--decoder-ce-weight", "0.0", "--structured-aux-weight", "1.0", "--denoise-weight", "0.0",
        "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
        "--output-dir", str(RUN_DIR), "--run-id", "stage9632_non_generative_repetition_eos_continuation_contract",
        "--contract-only",
    ]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = build_rows()
    write_jsonl(MANIFEST, rows)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9631_not_passed")
    if len(rows) != 24:
        failures.append("manifest_rows_not_24")
    split_counts = {split: sum(1 for row in rows if row.get("split") == split) for split in ["train", "eval", "strict_eval"]}
    if split_counts != {"train": 8, "eval": 8, "strict_eval": 8}:
        failures.append("split_counts_not_balanced")
    outcome_counts: dict[str, int] = {}
    failure_counts: dict[str, int] = {}
    for row in rows:
        transition = row["episode_transition"]
        outcome = transition["state_t_plus_1"]["repair_outcome"]
        failure_type = transition["reward_or_verifier"]["failure_type"]
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        failure_counts[failure_type] = failure_counts.get(failure_type, 0) + 1
    run = subprocess.run(command(), cwd=ROOT, text=True, capture_output=True, check=False) if not failures else None
    if run is not None and run.returncode != 0:
        failures.append("contract_command_failed")
    card = load_json(RUN_DIR / "probe_contract_audit.json")
    if not card:
        failures.append("missing_probe_contract_audit")
    elif card.get("passed") is not True:
        failures.append("probe_contract_not_passed")
    if card.get("mode") != "episode_step_structured_probe":
        failures.append("wrong_contract_mode")
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "manifest_rows": len(rows),
        "split_counts": split_counts,
        "outcome_counts": outcome_counts,
        "failure_counts": failure_counts,
        "contract_passed": card.get("passed"),
        "contract_mode": card.get("mode"),
        "loss_counts": card.get("loss_counts"),
        "model_execution_attempted": card.get("model_execution_attempted"),
        "non_generative": True,
        "decoder_ce_rows": 0,
        "denoise_ce_rows": 0,
        "runtime_authorized": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Audit Stage9632 label balance/shortcut risk, then decide whether to run a tiny episode-step structured probe or construct more counterbalanced observe-phase rows."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Non-generative observe-phase continuation objective preflight is contract-clean; no model execution occurred.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9632 Non-Generative Repetition/EOS Continuation Preflight",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{audit['manifest_rows']}`",
        f"Splits: `{audit['split_counts']}`",
        f"Outcomes: `{audit['outcome_counts']}`",
        f"Failure types: `{audit['failure_counts']}`",
        "",
        "This preflight converts Stage9623/9630 generation observations into episode-step structured supervision. Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
