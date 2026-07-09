#!/usr/bin/env python3
from __future__ import annotations

import copy
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
STAGE = 9661
NAME = "stage9661_visible_semantic_episode_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9660_visible_observe_repair_boundary_prefix_tiny_probe.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9659_visible_observe_repair_manifest/visible_observe_repair_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "visible_semantic_episode_manifest.jsonl"
RUN_DIR = OUT_DIR / "episode_step_contract"
AUDIT = OUT_DIR / "visible_semantic_episode_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "VISIBLE_SEMANTIC_EPISODE_MANIFEST_STAGE9661.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
FOCUSED_LOSSES = {"episode_failure_type_ce", "episode_repair_outcome_ce", "episode_step_value_mse"}
SPLIT_CAPS = {"train": 48, "eval": 9, "strict_eval": 9}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def transition(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}


def obs(row: dict[str, Any]) -> dict[str, Any]:
    trans = transition(row)
    return trans.get("observation_t") if isinstance(trans.get("observation_t"), dict) else {}


def verifier(row: dict[str, Any]) -> dict[str, Any]:
    trans = transition(row)
    return trans.get("reward_or_verifier") if isinstance(trans.get("reward_or_verifier"), dict) else {}


def next_state(row: dict[str, Any]) -> dict[str, Any]:
    trans = transition(row)
    return trans.get("state_t_plus_1") if isinstance(trans.get("state_t_plus_1"), dict) else {}


def target_label(row: dict[str, Any], target: str) -> str:
    if target == "failure_type":
        return str(verifier(row).get("failure_type"))
    if target == "repair_outcome":
        return str(next_state(row).get("repair_outcome"))
    if target == "step_value":
        return "1.0" if float(verifier(row).get("reward") or 0.0) >= 0.5 else "0.0"
    raise ValueError(target)


def model_feature(row: dict[str, Any], name: str) -> str:
    mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
    return str(mi.get(name))


def baseline_exact(rows: list[dict[str, Any]], feat: str, tgt: str) -> float:
    table: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        table[model_feature(row, feat)][target_label(row, tgt)] += 1
    mapping = {key: counts.most_common(1)[0][0] for key, counts in table.items() if counts}
    return sum(1 for row in rows if mapping.get(model_feature(row, feat)) == target_label(row, tgt)) / len(rows) if rows else 0.0


def combo_exact(rows: list[dict[str, Any]], feats: list[str], tgt: str) -> float:
    table: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = tuple(model_feature(row, feat) for feat in feats)
        table[key][target_label(row, tgt)] += 1
    mapping = {key: counts.most_common(1)[0][0] for key, counts in table.items() if counts}
    return sum(1 for row in rows if mapping.get(tuple(model_feature(row, feat) for feat in feats)) == target_label(row, tgt)) / len(rows) if rows else 0.0


def visible_semantic_bits(row: dict[str, Any]) -> dict[str, Any]:
    o = obs(row)
    v = verifier(row)
    mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
    boundary_match = bool(o.get("boundary_next_token_match"))
    prefix_match = bool(o.get("target_prefix_match"))
    stopped = bool(o.get("stopped_on_eos"))
    repeated = bool(o.get("degenerate_repetition"))
    short = bool(o.get("short_or_junk"))
    residual_count = len(o.get("residual_reasons") or [])
    phase = str(row.get("phase") or "unknown")
    if phase == "verify":
        attempt_kind = "target_prefix_verification"
    else:
        attempt_kind = "suffix_repair_attempt"
    return {
        "semantic_verifier_phase": True,
        "repair_attempt_kind": attempt_kind,
        "observed_boundary_miss": not boundary_match,
        "observed_target_prefix_miss": not prefix_match,
        "observed_repetition": repeated,
        "observed_unterminated": not stopped,
        "observed_short_or_junk": short,
        "observed_residual_reason_count": residual_count,
        "observed_verifier_success": bool(v.get("step_passed")),
        "observed_success_relation": "passed" if bool(v.get("step_passed")) else "failed",
        "observed_boundary_prefix_pair": mi.get("verifier_pair_relation"),
        "semantic_features_source": "primitive_observe_verifier_bits",
    }


def split_reassigned_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_outcome: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_outcome[target_label(row, "repair_outcome")].append(row)
    out: list[dict[str, Any]] = []
    for outcome in sorted(by_outcome):
        bucket = by_outcome[outcome]
        for idx, row in enumerate(bucket):
            if idx < 3:
                split = "eval"
            elif idx < 6:
                split = "strict_eval"
            else:
                split = "train"
            row = copy.deepcopy(row)
            row["split"] = split
            out.append(row)
    train = [row for row in out if row.get("split") == "train"]
    eval_rows = [row for row in out if row.get("split") == "eval"]
    strict = [row for row in out if row.get("split") == "strict_eval"]
    # Interleave train rows by value/outcome so short probes do not see a single class block first.
    train_buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in train:
        train_buckets[(target_label(row, "step_value"), target_label(row, "repair_outcome"))].append(row)
    ordered_train: list[dict[str, Any]] = []
    while any(train_buckets.values()):
        for key in sorted(train_buckets):
            if train_buckets[key]:
                ordered_train.append(train_buckets[key].pop(0))
    return ordered_train + eval_rows + strict


def patch_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    patched = copy.deepcopy(row)
    patched["row_id"] = f"stage9661_visible_semantic_episode_{index:04d}"
    patched["source_stage9659_row_id"] = row.get("row_id")
    patched["objective_family"] = "visible_semantic_episode_verifier_normalization"
    patched["route"] = "KEEP_VISIBLE_SEMANTIC_EPISODE"
    loss_mask = patched.get("loss_mask") if isinstance(patched.get("loss_mask"), dict) else {}
    for key in list(loss_mask):
        loss_mask[key] = key in FOCUSED_LOSSES
    patched["loss_mask"] = loss_mask
    model_input = patched.get("model_input") if isinstance(patched.get("model_input"), dict) else {}
    model_input.update(visible_semantic_bits(patched))
    patched["model_input"] = model_input
    anti_cheat = patched.get("anti_cheat") if isinstance(patched.get("anti_cheat"), dict) else {}
    anti_cheat.update({
        "semantic_episode_labels_hidden_from_model_input": True,
        "visible_semantic_inputs_are_primitive_observations": True,
        "decoder_ce_closed": True,
        "denoise_ce_closed": True,
        "runtime_closed": True,
        "focused_heads_only": sorted(FOCUSED_LOSSES),
    })
    patched["anti_cheat"] = anti_cheat
    return patched


def contract_command() -> list[str]:
    return ["env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}", "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST), "--mode", "episode_step_structured_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON), "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--max-train-rows", str(SPLIT_CAPS["train"]), "--max-eval-rows", str(SPLIT_CAPS["eval"]), "--max-strict-rows", str(SPLIT_CAPS["strict_eval"]), "--max-steps", "0", "--batch-size", "3", "--learning-rate", "3e-4",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", "8", "--decoder-ce-weight", "0.0", "--structured-aux-weight", "1.0", "--denoise-weight", "0.0",
        "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
        "--output-dir", str(RUN_DIR), "--run-id", "stage9661_visible_semantic_episode_contract", "--contract-only"]


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
    source_rows = load_jsonl(SOURCE_MANIFEST)
    rows = [patch_row(row, idx) for idx, row in enumerate(source_rows)]
    rows = split_reassigned_rows(rows)
    write_jsonl(MANIFEST, rows)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9660_not_passed")
    split_counts = dict(Counter(str(row.get("split")) for row in rows))
    if split_counts != SPLIT_CAPS:
        failures.append("split_counts_wrong")
    loss_counts: Counter[str] = Counter()
    for row in rows:
        for key, value in (row.get("loss_mask") or {}).items():
            if value:
                loss_counts[key] += 1
    expected_losses = {key: len(rows) for key in sorted(FOCUSED_LOSSES)}
    if dict(sorted(loss_counts.items())) != expected_losses:
        failures.append("focused_loss_counts_wrong")
    if any((row.get("loss_mask") or {}).get(key) for row in rows for key in ["decoder_ce", "denoise_ce", "runtime_reward", "episode_boundary_match_ce", "episode_target_prefix_match_ce"]):
        failures.append("forbidden_loss_enabled")
    label_by_split = {split: {target: dict(Counter(target_label(row, target) for row in rows if row.get("split") == split)) for target in ["failure_type", "repair_outcome", "step_value"]} for split in ["train", "eval", "strict_eval"]}
    for split in ["eval", "strict_eval"]:
        if len(label_by_split[split]["repair_outcome"]) != 3:
            failures.append(f"{split}_repair_outcome_not_three_class")
        if len(label_by_split[split]["step_value"]) != 2:
            failures.append(f"{split}_step_value_not_binary")
    single_baselines = {f"{feat}->{target}": baseline_exact(rows, feat, target) for feat in ["observed_boundary_prefix_pair", "observed_residual_reason_count", "repair_attempt_kind", "observed_success_relation"] for target in ["failure_type", "repair_outcome", "step_value"]}
    combo_baselines = {
        "primitive_failure_bits->failure_type": combo_exact(rows, ["observed_boundary_miss", "observed_target_prefix_miss", "observed_repetition", "observed_unterminated", "observed_residual_reason_count"], "failure_type"),
        "phase_plus_success->repair_outcome": combo_exact(rows, ["repair_attempt_kind", "observed_success_relation", "observed_boundary_prefix_pair"], "repair_outcome"),
        "success_relation->step_value": baseline_exact(rows, "observed_success_relation", "step_value"),
    }
    authority_rows = [row.get("row_id") for row in rows if any((row.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED)]
    if authority_rows:
        failures.append("authority_rows_present")
    run = subprocess.run(contract_command(), cwd=ROOT, text=True, capture_output=True, check=False) if not failures else None
    if run is not None and run.returncode != 0:
        failures.append("contract_command_failed")
    card = load_json(RUN_DIR / "probe_contract_audit.json")
    if not card and not failures:
        failures.append("missing_probe_contract_audit")
    elif card and card.get("passed") is not True:
        failures.append("probe_contract_not_passed")
    audit = {"passed": not failures, "failures": failures, "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)), "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT)), "rows": len(rows), "split_counts": split_counts, "loss_counts": dict(sorted(loss_counts.items())), "label_by_split": label_by_split, "single_feature_baselines": single_baselines, "combo_baselines": combo_baselines, "authority_rows": len(authority_rows), "contract_passed": card.get("passed"), "contract_loss_counts": card.get("loss_counts"), "model_execution_attempted": card.get("model_execution_attempted"), "authority": dict(AUTHORITY_CLOSED)}
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If Stage9661 passes, run Stage9662 visible semantic episode target-100M probe for failure/outcome/value heads."
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": audit["passed"], "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **audit}, "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))}, "decision": "Built semantic visible episode manifest for failure/outcome/value verifier heads; no decoder/runtime opened." if audit["passed"] else "Semantic visible episode manifest failed; do not execute.", "next_best_step": next_step, "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9661 Visible Semantic Episode Manifest", "", f"Passed: `{audit['passed']}`", f"Rows: `{audit['rows']}`", f"Splits: `{split_counts}`", f"Loss counts: `{audit['loss_counts']}`", f"Label by split: `{label_by_split}`", f"Single-feature baselines: `{single_baselines}`", f"Combo baselines: `{combo_baselines}`", "", "This stage exposes primitive observe/verifier bits to normalize episode failure type, repair outcome, and step value. Boundary/prefix heads are closed here because Stage9660 already passed them.", "", "Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, final checkpoint export, controller merge, and promotion remain closed.", "", f"Next: {next_step}", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "rows": len(rows), "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
