#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9657
NAME = "stage9657_widened_model_input_comparator_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9656_model_input_comparator_tiny_probe.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "widened_model_input_comparator_manifest.jsonl"
RUN_DIR = OUT_DIR / "episode_step_contract"
AUDIT = OUT_DIR / "widened_model_input_comparator_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WIDENED_MODEL_INPUT_COMPARATOR_MANIFEST_STAGE9657.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
LOSS_MASK = {
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
    "episode_repair_outcome_ce": False,
    "episode_failure_type_ce": False,
    "episode_boundary_match_ce": True,
    "episode_target_prefix_match_ce": True,
    "episode_step_value_mse": False,
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def prefix_for(lang: str, split: str, idx: int) -> str:
    lang_phrase = {
        "python": "Return python parser token",
        "rust": "Return rust borrow token",
        "c_cpp": "Return c family symbol token",
        "web_js_ts_html": "Return web component token",
    }[lang]
    return f"{lang_phrase} {split} {idx}"


def make_row(split: str, lang: str, idx: int, positive: bool) -> dict[str, Any]:
    expected = f"tok_{lang}_{idx}"
    got = expected if positive else f"wrong_{lang}_{idx}"
    relation = "same" if positive else "different"
    prefix = prefix_for(lang, split, idx)
    generated = f"{prefix} {got} continuation"
    label = "positive" if positive else "negative"
    return {
        "row_id": f"stage9657_{split}_{lang}_{idx:02d}_{label}",
        "split": split,
        "language_family": lang,
        "transition_schema": "episode_step_suffix_transition_v1",
        "objective_family": "widened_model_input_comparator",
        "model_input": {
            "boundary_token_relation": relation,
            "boundary_relation_source": "precomputed_observation_comparator",
            "comparison_surface": "episode_boundary_prefix",
        },
        "episode_transition": {
            "state_t": {
                "source_stage": "stage9657_widened_model_input_comparator",
                "target_visible": False,
                "clean_target_hidden_from_model_input": True,
                "generation_prefix_text": prefix,
                "guard_event_count": 0,
            },
            "action_t": {"action": "OBSERVE_GENERATION_AND_SELECT_CONTINUATION_REPAIR", "target_surface": "suffix_continuation"},
            "observation_t": {
                "generated_text": generated,
                "target_prefix_match": positive,
                "boundary_next_token_match": positive,
                "boundary_expected_rank": 1 if positive else 99,
                "degenerate_repetition": False,
                "short_or_junk": False,
                "stopped_on_eos": True,
                "residual_reasons": [] if positive else ["boundary_next_token_miss", "target_prefix_miss"],
            },
            "reward_or_verifier": {"verifier_source": "stage9657_widened_model_input_comparator", "step_passed": positive, "reward": 1.0 if positive else 0.0, "failure_type": "none" if positive else "boundary_next_token_miss+target_prefix_miss"},
            "state_t_plus_1": {"repair_outcome": "verified_continue" if positive else "repair_prefix_boundary"},
        },
        "loss_mask": dict(LOSS_MASK),
        "authority": dict(AUTHORITY_CLOSED),
    }


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for split in ["train", "eval", "strict_eval"]:
        for lang_idx, lang in enumerate(LANGS):
            for local_idx in range(2):
                idx = lang_idx * 10 + local_idx
                rows.append(make_row(split, lang, idx, True))
                rows.append(make_row(split, lang, idx, False))
    return rows


def obs(row: dict[str, Any]) -> dict[str, Any]:
    return row["episode_transition"]["observation_t"]


def label(row: dict[str, Any], target: str) -> str:
    if target == "boundary_match":
        return str(obs(row).get("boundary_next_token_match"))
    if target == "target_prefix_match":
        return str(obs(row).get("target_prefix_match"))
    raise ValueError(target)


def feature(row: dict[str, Any], name: str) -> str:
    if name == "model_boundary_token_relation":
        return str(row["model_input"].get("boundary_token_relation"))
    if name == "prefix":
        return str(row["episode_transition"]["state_t"].get("generation_prefix_text"))
    if name == "language_family":
        return str(row.get("language_family"))
    return ""


def baseline_exact(rows: list[dict[str, Any]], feat: str, tgt: str) -> float:
    table: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        table[feature(row, feat)][label(row, tgt)] += 1
    mapping = {key: counts.most_common(1)[0][0] for key, counts in table.items() if counts}
    return sum(1 for row in rows if mapping.get(feature(row, feat)) == label(row, tgt)) / len(rows) if rows else 0.0


def contract_command() -> list[str]:
    return ["env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}", "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST), "--mode", "episode_step_structured_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON), "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--max-train-rows", "16", "--max-eval-rows", "16", "--max-strict-rows", "16", "--max-steps", "0", "--batch-size", "2", "--learning-rate", "3e-4",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", "8", "--decoder-ce-weight", "0.0", "--structured-aux-weight", "1.0", "--denoise-weight", "0.0",
        "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
        "--output-dir", str(RUN_DIR), "--run-id", "stage9657_widened_model_input_comparator_contract", "--contract-only"]


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
        failures.append("stage9656_not_passed")
    split_counts = {split: sum(1 for row in rows if row["split"] == split) for split in ["train", "eval", "strict_eval"]}
    lang_counts = dict(Counter(str(row["language_family"]) for row in rows))
    label_by_split = {split: {target: dict(Counter(label(row, target) for row in rows if row["split"] == split)) for target in ["boundary_match", "target_prefix_match"]} for split in ["train", "eval", "strict_eval"]}
    prefix_baselines = {f"prefix->{target}": baseline_exact(rows, "prefix", target) for target in ["boundary_match", "target_prefix_match"]}
    language_baselines = {f"language_family->{target}": baseline_exact(rows, "language_family", target) for target in ["boundary_match", "target_prefix_match"]}
    comparator_baselines = {f"model_boundary_token_relation->{target}": baseline_exact(rows, "model_boundary_token_relation", target) for target in ["boundary_match", "target_prefix_match"]}
    if split_counts != {"train": 16, "eval": 16, "strict_eval": 16}:
        failures.append("split_counts_wrong")
    if any(count != 12 for count in lang_counts.values()) or set(lang_counts) != set(LANGS):
        failures.append("language_counts_wrong")
    if max(prefix_baselines.values()) != 0.5:
        failures.append("prefix_identity_not_blocked")
    if max(language_baselines.values()) != 0.5:
        failures.append("language_shortcut_not_blocked")
    if min(comparator_baselines.values()) != 1.0:
        failures.append("model_input_comparator_not_predictive")
    run = subprocess.run(contract_command(), cwd=ROOT, text=True, capture_output=True, check=False) if not failures else None
    if run is not None and run.returncode != 0:
        failures.append("contract_command_failed")
    card = load_json(RUN_DIR / "probe_contract_audit.json")
    if not card and not failures:
        failures.append("missing_probe_contract_audit")
    elif card and card.get("passed") is not True:
        failures.append("probe_contract_not_passed")
    audit = {"passed": not failures, "failures": failures, "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT)), "rows": len(rows), "split_counts": split_counts, "language_counts": lang_counts, "label_by_split": label_by_split, "prefix_baselines": prefix_baselines, "language_baselines": language_baselines, "model_input_comparator_baselines": comparator_baselines, "contract_passed": card.get("passed"), "loss_counts": card.get("loss_counts"), "model_execution_attempted": card.get("model_execution_attempted"), "authority": dict(AUTHORITY_CLOSED)}
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If Stage9657 passes, run Stage9658 widened model-input comparator target-100M probe."
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": audit["passed"], "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **audit}, "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))}, "decision": "Widened model-input comparator manifest passed contract preflight; no model execution occurred." if audit["passed"] else "Widened model-input comparator manifest failed; do not execute.", "next_best_step": next_step, "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9657 Widened Model-Input Comparator Manifest", "", f"Passed: `{audit['passed']}`", f"Rows: `{audit['rows']}`", f"Splits: `{split_counts}`", f"Languages: `{lang_counts}`", f"Prefix baselines: `{prefix_baselines}`", f"Language baselines: `{language_baselines}`", f"Comparator baselines: `{comparator_baselines}`", "", "Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.", "", f"Next: {next_step}", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "rows": len(rows), "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
