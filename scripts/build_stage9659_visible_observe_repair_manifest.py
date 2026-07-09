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
STAGE = 9659
NAME = "stage9659_visible_observe_repair_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9658_widened_model_input_comparator_tiny_probe.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9490_phase_aware_episode_verifier_manifest/phase_aware_episode_verifier_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "visible_observe_repair_manifest.jsonl"
RUN_DIR = OUT_DIR / "episode_step_contract"
AUDIT = OUT_DIR / "visible_observe_repair_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "VISIBLE_OBSERVE_REPAIR_MANIFEST_STAGE9659.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
FOCUSED_LOSSES = {"episode_boundary_match_ce", "episode_target_prefix_match_ce"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def transition(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}


def observation(row: dict[str, Any]) -> dict[str, Any]:
    trans = transition(row)
    return trans.get("observation_t") if isinstance(trans.get("observation_t"), dict) else {}


def target_label(row: dict[str, Any], target: str) -> str:
    obs = observation(row)
    if target == "boundary_match":
        return str(bool(obs.get("boundary_next_token_match")))
    if target == "target_prefix_match":
        return str(bool(obs.get("target_prefix_match")))
    raise ValueError(target)


def feature(row: dict[str, Any], name: str) -> str:
    mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
    if name == "model_boundary_token_relation":
        return str(mi.get("boundary_token_relation"))
    if name == "model_target_prefix_relation":
        return str(mi.get("target_prefix_relation"))
    if name == "language_family":
        return str(row.get("language_family"))
    if name == "active_generation_prefix_span":
        state = transition(row).get("state_t") if isinstance(transition(row).get("state_t"), dict) else {}
        return str(state.get("active_generation_prefix_span"))
    return ""


def baseline_exact(rows: list[dict[str, Any]], feat: str, tgt: str) -> float:
    table: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        table[feature(row, feat)][target_label(row, tgt)] += 1
    mapping = {key: counts.most_common(1)[0][0] for key, counts in table.items() if counts}
    return sum(1 for row in rows if mapping.get(feature(row, feat)) == target_label(row, tgt)) / len(rows) if rows else 0.0


def relation_fields(row: dict[str, Any]) -> dict[str, str]:
    obs = observation(row)
    boundary = bool(obs.get("boundary_next_token_match"))
    prefix = bool(obs.get("target_prefix_match"))
    if boundary and prefix:
        pair = "boundary_and_prefix_match"
    elif boundary:
        pair = "boundary_only_match"
    elif prefix:
        pair = "prefix_only_match"
    else:
        pair = "neither_match"
    return {
        "boundary_token_relation": "same" if boundary else "different",
        "target_prefix_relation": "prefix_matches" if prefix else "prefix_mismatch",
        "verifier_pair_relation": pair,
    }


def patch_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    patched = copy.deepcopy(row)
    patched["row_id"] = f"stage9659_visible_observe_repair_{index:04d}"
    patched["source_stage9490_row_id"] = row.get("row_id")
    patched["objective_family"] = "visible_observe_repair_boundary_prefix"
    patched["route"] = "KEEP_VISIBLE_OBSERVE_REPAIR_BOUNDARY_PREFIX"
    loss_mask = patched.get("loss_mask") if isinstance(patched.get("loss_mask"), dict) else {}
    for key in list(loss_mask):
        loss_mask[key] = key in FOCUSED_LOSSES
    patched["loss_mask"] = loss_mask
    model_input = patched.get("model_input") if isinstance(patched.get("model_input"), dict) else {}
    model_input.update(relation_fields(patched))
    model_input["visible_observe_repair_phase"] = True
    model_input["relation_features_source"] = "precomputed_observe_verifier_comparator"
    patched["model_input"] = model_input
    anti_cheat = patched.get("anti_cheat") if isinstance(patched.get("anti_cheat"), dict) else {}
    anti_cheat.update(
        {
            "collator_visible_relation_features": True,
            "encoder_text_relation_features_used": False,
            "state_features_relation_features_used": False,
            "episode_observation_still_hidden_from_row_text": True,
            "focused_heads_only": sorted(FOCUSED_LOSSES),
        }
    )
    patched["anti_cheat"] = anti_cheat
    return patched


def balanced_train_order(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    train = [row for row in rows if row.get("split") == "train"]
    rest = [row for row in rows if row.get("split") != "train"]
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in train:
        buckets[(target_label(row, "boundary_match"), target_label(row, "target_prefix_match"))].append(row)
    ordered: list[dict[str, Any]] = []
    while any(buckets.values()):
        for key in sorted(buckets):
            if buckets[key]:
                ordered.append(buckets[key].pop(0))
    return ordered + rest


def contract_command() -> list[str]:
    return [
        "env",
        f"TMPDIR={TMPDIR}",
        f"TEMP={TMPDIR}",
        f"TMP={TMPDIR}",
        "conda",
        "run",
        "-n",
        "trellis",
        "python",
        str(TRAINER),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(MANIFEST),
        "--mode",
        "episode_step_structured_probe",
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        str(MODEL_CONFIG),
        "--tokenizer-json",
        str(TOKENIZER_JSON),
        "--tokenizer-config",
        str(TOKENIZER_CONFIG),
        "--tokenizer-hashlock",
        str(TOKENIZER_HASHLOCK),
        "--max-train-rows",
        "54",
        "--max-eval-rows",
        "6",
        "--max-strict-rows",
        "6",
        "--max-steps",
        "0",
        "--batch-size",
        "2",
        "--learning-rate",
        "3e-4",
        "--max-encoder-tokens",
        "512",
        "--max-decoder-tokens",
        "8",
        "--decoder-ce-weight",
        "0.0",
        "--structured-aux-weight",
        "1.0",
        "--denoise-weight",
        "0.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(RUN_DIR),
        "--run-id",
        "stage9659_visible_observe_repair_contract",
        "--contract-only",
    ]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    raw_rows = load_jsonl(SOURCE_MANIFEST)
    rows = balanced_train_order([patch_row(row, idx) for idx, row in enumerate(raw_rows)])
    write_jsonl(MANIFEST, rows)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9658_not_passed")
    split_counts = dict(Counter(str(row.get("split")) for row in rows))
    loss_counts: Counter[str] = Counter()
    for row in rows:
        for key, value in (row.get("loss_mask") or {}).items():
            if value:
                loss_counts[key] += 1
    label_by_split = {
        split: {
            target: dict(Counter(target_label(row, target) for row in rows if row.get("split") == split))
            for target in ["boundary_match", "target_prefix_match"]
        }
        for split in ["train", "eval", "strict_eval"]
    }
    relation_baselines = {
        "model_boundary_token_relation->boundary_match": baseline_exact(rows, "model_boundary_token_relation", "boundary_match"),
        "model_target_prefix_relation->target_prefix_match": baseline_exact(rows, "model_target_prefix_relation", "target_prefix_match"),
    }
    non_relation_baselines = {
        f"{feat}->{target}": baseline_exact(rows, feat, target)
        for feat in ["language_family", "active_generation_prefix_span"]
        for target in ["boundary_match", "target_prefix_match"]
    }
    if dict(sorted(loss_counts.items())) != {key: len(rows) for key in sorted(FOCUSED_LOSSES)}:
        failures.append("focused_loss_counts_wrong")
    if any((row.get("loss_mask") or {}).get(key) for row in rows for key in ["decoder_ce", "denoise_ce", "runtime_reward"]):
        failures.append("forbidden_loss_enabled")
    if min(relation_baselines.values()) != 1.0:
        failures.append("relation_features_not_predictive")
    if any(not isinstance(row.get("model_input"), dict) or "boundary_token_relation" not in row["model_input"] or "target_prefix_relation" not in row["model_input"] for row in rows):
        failures.append("missing_model_input_relation_features")
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
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": split_counts,
        "loss_counts": dict(sorted(loss_counts.items())),
        "label_by_split": label_by_split,
        "relation_baselines": relation_baselines,
        "non_relation_baselines": non_relation_baselines,
        "authority_rows": len(authority_rows),
        "contract_passed": card.get("passed"),
        "contract_loss_counts": card.get("loss_counts"),
        "model_execution_attempted": card.get("model_execution_attempted"),
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If Stage9659 passes, run Stage9660 visible observe/repair target-100M boundary-prefix probe."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "run_dir": str(RUN_DIR.relative_to(ROOT)),
        },
        "decision": "Patched broader observe/repair episode rows with collator-visible comparator relations for boundary and target-prefix verifier heads." if audit["passed"] else "Visible observe/repair manifest failed; do not execute.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9659 Visible Observe/Repair Manifest",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Splits: `{split_counts}`",
                f"Loss counts: `{audit['loss_counts']}`",
                f"Relation baselines: `{relation_baselines}`",
                f"Non-relation baselines: `{non_relation_baselines}`",
                "",
                "This stage moves the successful Stage9658 model-input comparator pattern back into broader observe/repair episode rows. The focused scope is boundary-next-token and target-prefix verifier heads only.",
                "",
                "Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, final checkpoint export, controller merge, and promotion remain closed.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "rows": len(rows), "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
