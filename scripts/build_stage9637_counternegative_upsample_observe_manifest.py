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
STAGE = 9637
NAME = "stage9637_counternegative_upsample_observe_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9636_counterbalanced_observe_probe_failure_audit.json"
BASE_MANIFEST = ROOT / "runs/local/artifacts/stage9634_counterbalanced_observe_continuation_manifest/counterbalanced_observe_continuation_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "counternegative_upsample_observe_manifest.jsonl"
RUN_DIR = OUT_DIR / "episode_step_contract"
AUDIT = OUT_DIR / "counternegative_upsample_observe_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COUNTERNEGATIVE_UPSAMPLE_OBSERVE_MANIFEST_STAGE9637.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
LOSS_MASK = {
    "decoder_ce": False, "denoise_ce": False, "runtime_reward": False,
    "episode_repair_outcome_ce": True, "episode_failure_type_ce": True,
    "episode_boundary_match_ce": True, "episode_target_prefix_match_ce": True,
    "episode_step_value_mse": True,
}
FORBIDDEN_ENCODER_MARKERS = ["target_prefix_match=", "boundary_next_token_match=", "prefix_start_match=", "stopped_on_eos=", "repair_outcome=", "failure_type=", "reward="]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def split_for(index: int) -> str:
    return ["train", "eval", "strict_eval"][index % 3]


def obs(row: dict[str, Any]) -> dict[str, Any]:
    return row["episode_transition"]["observation_t"]


def state(row: dict[str, Any]) -> dict[str, Any]:
    return row["episode_transition"]["state_t"]


def text_len_bucket(text: str) -> str:
    n = len(text)
    return "short" if n < 60 else ("medium" if n < 100 else "long")


def prefix_len_bucket(prefix: str) -> str:
    return "short" if len(prefix.split()) <= 5 else "long"


def guard_bucket(count: int) -> str:
    return "zero" if count == 0 else ("one" if count == 1 else "many")


def make_encoder_text(*, source_stage: str, generated: str, prefix: str, expected: str, got: str, guard_count: int) -> str:
    return "\n".join([
        "episode_step_suffix_transition_v1",
        f"source={source_stage}",
        f"generated_text={generated}",
        f"generation_prefix_text={prefix}",
        f"boundary_expected_token_text={expected}",
        f"boundary_generated_token_text={got}",
        f"generated_char_len={len(generated)}",
        f"guard_event_count={guard_count}",
        "target_text_hidden=true",
        "match_labels_hidden=true",
    ])


def make_counternegative(template: dict[str, Any], idx: int, variant: int) -> dict[str, Any]:
    st = state(template)
    ob = obs(template)
    source = str(st.get("source_stage") or "unknown_source")
    prefix = str(st.get("generation_prefix_text") or "Return the requested value")
    guard_count = int(st.get("guard_event_count") or 0)
    base_text = str(ob.get("generated_text") or prefix)
    expected = "expected" if variant % 2 == 0 else "valid"
    got = "wrong" if variant % 2 == 0 else "mismatch"
    # Keep visible length bucket close to template while changing boundary evidence.
    filler_len = max(0, len(base_text) - len(prefix) - len(got) - 13)
    filler = (" x" * ((filler_len // 2) + 1))[:filler_len]
    generated = f"{prefix} {got}{filler}".strip()
    return {
        "row_id": f"stage9637_counternegative_{idx:03d}_{variant}",
        "source_template_row_id": template.get("row_id"),
        "split": "train",
        "language_family": "mixed",
        "transition_schema": "episode_step_suffix_transition_v1",
        "objective_family": "counternegative_upsample_observe_continuation",
        "encoder_text": make_encoder_text(source_stage=source, generated=generated, prefix=prefix, expected=expected, got=got, guard_count=guard_count),
        "episode_transition": {
            "state_t": {"source_stage": source, "target_visible": False, "clean_target_hidden_from_model_input": True, "generation_prefix_text": prefix, "guard_event_count": guard_count},
            "action_t": {"action": "OBSERVE_GENERATION_AND_SELECT_CONTINUATION_REPAIR", "target_surface": "suffix_continuation"},
            "observation_t": {"generated_text": generated, "target_prefix_match": False, "boundary_next_token_match": False, "boundary_expected_rank": 99, "degenerate_repetition": False, "short_or_junk": False, "stopped_on_eos": True, "residual_reasons": ["boundary_next_token_miss", "target_prefix_miss"]},
            "reward_or_verifier": {"verifier_source": "stage9637_counternegative_upsample", "step_passed": False, "reward": 0.0, "failure_type": "boundary_next_token_miss+target_prefix_miss"},
            "state_t_plus_1": {"repair_outcome": "repair_prefix_boundary"},
        },
        "loss_mask": dict(LOSS_MASK),
        "authority": dict(AUTHORITY_CLOSED),
    }


def make_counterpositive(template: dict[str, Any], idx: int) -> dict[str, Any]:
    st = state(template)
    ob = obs(template)
    source = str(st.get("source_stage") or "unknown_source")
    prefix = str(st.get("generation_prefix_text") or "Return the requested value")
    guard_count = int(st.get("guard_event_count") or 0)
    generated = str(ob.get("generated_text") or prefix)
    if len(generated) < len(prefix) + 12:
        generated = f"{prefix} expected continuation"
    expected = "expected"
    return {
        "row_id": f"stage9637_counterpositive_{idx:03d}",
        "source_template_row_id": template.get("row_id"),
        "split": "train",
        "language_family": "mixed",
        "transition_schema": "episode_step_suffix_transition_v1",
        "objective_family": "counternegative_upsample_observe_continuation",
        "encoder_text": make_encoder_text(source_stage=source, generated=generated, prefix=prefix, expected=expected, got=expected, guard_count=guard_count),
        "episode_transition": {
            "state_t": {"source_stage": source, "target_visible": False, "clean_target_hidden_from_model_input": True, "generation_prefix_text": prefix, "guard_event_count": guard_count},
            "action_t": {"action": "OBSERVE_GENERATION_AND_SELECT_CONTINUATION_REPAIR", "target_surface": "suffix_continuation"},
            "observation_t": {"generated_text": generated, "target_prefix_match": True, "boundary_next_token_match": True, "boundary_expected_rank": 1, "degenerate_repetition": False, "short_or_junk": False, "stopped_on_eos": True, "residual_reasons": []},
            "reward_or_verifier": {"verifier_source": "stage9637_counterpositive_balance", "step_passed": True, "reward": 1.0, "failure_type": "none"},
            "state_t_plus_1": {"repair_outcome": "verified_continue"},
        },
        "loss_mask": dict(LOSS_MASK),
        "authority": dict(AUTHORITY_CLOSED),
    }


def build_rows() -> list[dict[str, Any]]:
    base = load_jsonl(BASE_MANIFEST)
    rows = list(base)
    # Add negatives from every source/guard/length bucket and positives in matching buckets.
    templates_by_key: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in base:
        st = state(row); ob = obs(row)
        key = (
            str(st.get("source_stage")),
            guard_bucket(int(st.get("guard_event_count") or 0)),
            text_len_bucket(str(ob.get("generated_text") or "")),
            prefix_len_bucket(str(st.get("generation_prefix_text") or "")),
        )
        templates_by_key[key].append(row)
    idx = 0
    for key, templates in sorted(templates_by_key.items(), key=lambda item: repr(item[0])):
        for variant in range(2):
            rows.append(make_counternegative(templates[variant % len(templates)], idx, variant))
            idx += 1
        rows.append(make_counterpositive(templates[0], idx))
        idx += 1
    for row_idx, row in enumerate(rows):
        row["split"] = split_for(row_idx)
    return rows


def label(row: dict[str, Any], target: str) -> str:
    tr = row["episode_transition"]
    if target == "repair_outcome": return str(tr["state_t_plus_1"].get("repair_outcome"))
    if target == "target_prefix_match": return str(tr["observation_t"].get("target_prefix_match"))
    if target == "boundary_match": return str(tr["observation_t"].get("boundary_next_token_match"))
    if target == "step_value": return "1.0" if float(tr["reward_or_verifier"].get("reward") or 0.0) >= 0.5 else "0.0"
    return str(tr["reward_or_verifier"].get("failure_type"))


def feature(row: dict[str, Any], name: str) -> str:
    st = state(row); ob = obs(row)
    if name == "source_stage": return str(st.get("source_stage"))
    if name == "guard_event_count_bucket": return guard_bucket(int(st.get("guard_event_count") or 0))
    if name == "generated_len_bucket": return text_len_bucket(str(ob.get("generated_text") or ""))
    if name == "prefix_token_count_bucket": return prefix_len_bucket(str(st.get("generation_prefix_text") or ""))
    return ""


def baseline_exact(rows: list[dict[str, Any]], feat: str, tgt: str) -> float:
    table: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        table[feature(row, feat)][label(row, tgt)] += 1
    mapping = {key: counts.most_common(1)[0][0] for key, counts in table.items() if counts}
    return sum(1 for row in rows if mapping.get(feature(row, feat)) == label(row, tgt)) / len(rows) if rows else 0.0


def command() -> list[str]:
    return ["env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}", "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST), "--mode", "episode_step_structured_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON), "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--max-train-rows", "32", "--max-eval-rows", "32", "--max-strict-rows", "32", "--max-steps", "0", "--batch-size", "2", "--learning-rate", "2e-4",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", "8", "--decoder-ce-weight", "0.0", "--structured-aux-weight", "1.0", "--denoise-weight", "0.0",
        "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
        "--output-dir", str(RUN_DIR), "--run-id", "stage9637_counternegative_upsample_observe_contract", "--contract-only"]


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
        failures.append("stage9636_not_passed")
    split_counts = {split: sum(1 for row in rows if row.get("split") == split) for split in ["train", "eval", "strict_eval"]}
    if max(split_counts.values()) - min(split_counts.values()) > 1:
        failures.append("split_counts_unbalanced")
    forbidden = []
    for row in rows:
        text = str(row.get("encoder_text") or "")
        hits = [marker for marker in FORBIDDEN_ENCODER_MARKERS if marker in text]
        if hits:
            forbidden.append({"row_id": row.get("row_id"), "hits": hits})
    if forbidden:
        failures.append("forbidden_encoder_label_markers_present")
    targets = ["repair_outcome", "failure_type", "boundary_match", "target_prefix_match", "step_value"]
    features = ["source_stage", "guard_event_count_bucket", "generated_len_bucket", "prefix_token_count_bucket"]
    baselines = {f"{feat}->{tgt}": baseline_exact(rows, feat, tgt) for feat in features for tgt in targets}
    strongest = max(baselines.values()) if baselines else 0.0
    strongest_key = max(baselines, key=baselines.get) if baselines else None
    if strongest >= 0.75:
        failures.append("single_feature_baseline_too_high")
    label_counts = {target: dict(Counter(label(row, target) for row in rows)) for target in targets}
    counternegative_rows = sum(1 for row in rows if str(row.get("row_id", "")).startswith("stage9637_counternegative"))
    counterpositive_rows = sum(1 for row in rows if str(row.get("row_id", "")).startswith("stage9637_counterpositive"))
    run = subprocess.run(command(), cwd=ROOT, text=True, capture_output=True, check=False) if not failures else None
    if run is not None and run.returncode != 0:
        failures.append("contract_command_failed")
    card = load_json(RUN_DIR / "probe_contract_audit.json")
    if not card and not failures:
        failures.append("missing_probe_contract_audit")
    elif card and card.get("passed") is not True:
        failures.append("probe_contract_not_passed")
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "base_rows": len(load_jsonl(BASE_MANIFEST)),
        "counternegative_rows": counternegative_rows,
        "counterpositive_rows": counterpositive_rows,
        "split_counts": split_counts,
        "forbidden_encoder_label_marker_rows": len(forbidden),
        "forbidden_encoder_label_marker_examples": forbidden[:20],
        "single_feature_baselines": baselines,
        "strongest_single_feature_baseline": strongest,
        "strongest_single_feature_baseline_key": strongest_key,
        "label_counts": label_counts,
        "contract_passed": card.get("passed"),
        "loss_counts": card.get("loss_counts"),
        "model_execution_attempted": card.get("model_execution_attempted"),
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If Stage9637 passes, run Stage9638 tiny episode-step structured probe; otherwise add same-feature/different-label rows until shortcut baselines drop below 0.75."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Counternegative-upsample observe manifest passed shortcut and contract preflight; no model execution occurred." if audit["passed"] else "Counternegative-upsample observe manifest failed; do not execute.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9637 Counternegative Upsample Observe Manifest",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Counternegative / counterpositive rows: `{counternegative_rows}` / `{counterpositive_rows}`",
        f"Splits: `{split_counts}`",
        f"Strongest single-feature baseline: `{strongest}` via `{strongest_key}`",
        "",
        "Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "rows": len(rows), "strongest_single_feature_baseline": strongest, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
