#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from collections import Counter, defaultdict

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9484
NAME = "stage9484_target_prefix_observe_phase_manifest"
SOURCE_BALANCE = ROOT / "runs/local/artifacts/stage9479_episode_target_prefix_balance_manifest/episode_target_prefix_balance_manifest.jsonl"
SOURCE_QUEUE = ROOT / "runs/local/artifacts/stage9482_target_prefix_positive_repair_queue/target_prefix_positive_repair_queue.jsonl"
SOURCE_DESIGN = ROOT / "runs/summaries/stage9483_target_prefix_observe_phase_boundary_design.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9484_target_prefix_observe_phase_manifest"
MANIFEST = OUT_DIR / "target_prefix_observe_phase_manifest.jsonl"
CARD = OUT_DIR / "target_prefix_observe_phase_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TARGET_PREFIX_OBSERVE_PHASE_MANIFEST_STAGE9484.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LOSS_KEYS = [
    "action_sequence_ce",
    "allowed_import_policy_ce",
    "blocked_import_policy_ce",
    "build_mode_ce",
    "decoder_ce",
    "denoise_ce",
    "edit_localization_ce",
    "episode_boundary_match_ce",
    "episode_failure_type_ce",
    "episode_repair_outcome_ce",
    "episode_step_value_mse",
    "episode_target_prefix_match_ce",
    "file_plan_ce",
    "patch_operator_ce",
    "repair_surface_ce",
    "repo_dependency_policy_ce",
    "runtime_reward",
    "suffix_choice_ce",
    "surface_role_ce",
    "symbol_binding_ce",
    "verifier_repair_ce",
]
EVAL_FALSE = {"stage9479_target_prefix_balance_0006", "stage9479_target_prefix_balance_0003", "stage9479_target_prefix_balance_0020"}
STRICT_FALSE = {"stage9479_target_prefix_balance_0037", "stage9479_target_prefix_balance_0028", "stage9479_target_prefix_balance_0040"}
EVAL_TRUE_QUEUE = {"stage9482_cpp_positive_target_prefix_00", "stage9482_python_positive_target_prefix_00", "stage9482_web_js_ts_html_positive_target_prefix_00"}
STRICT_TRUE_QUEUE = {"stage9482_cpp_positive_target_prefix_01", "stage9482_python_positive_target_prefix_01", "stage9482_web_js_ts_html_positive_target_prefix_01"}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def target_prefix_label(row: dict) -> bool:
    return bool(row["episode_transition"]["observation_t"].get("target_prefix_match"))


def configure_row(row: dict, *, row_id: str, split: str, source_kind: str) -> dict:
    row = copy.deepcopy(row)
    obs = row["episode_transition"]["observation_t"]
    target = row["episode_transition"]["state_t_plus_1"].get("decoder_text", "")
    generated = obs.get("generated_text", "")
    row["row_id"] = row_id
    row["split"] = split
    row["objective_family"] = "episode_target_prefix_observe_phase_verifier"
    row["route"] = "KEEP_EPISODE_TARGET_PREFIX_OBSERVE_PHASE"
    row["source_kind"] = source_kind
    row["model_input"] = {
        "observe_phase": True,
        "generated_output_preview": generated,
        "reference_output_preview": target,
        "generated_output_chars": len(str(generated)),
        "reference_output_chars": len(str(target)),
    }
    row["loss_mask"] = {key: False for key in LOSS_KEYS}
    row["loss_mask"]["episode_target_prefix_match_ce"] = True
    row["authority"] = dict(AUTHORITY_CLOSED)
    row.setdefault("anti_cheat", {})["target_prefix_match_label_hidden_from_encoder"] = True
    row["anti_cheat"]["generated_and_reference_text_visible_for_observe_phase_verifier"] = True
    row["anti_cheat"]["decoder_ce_closed"] = True
    row["anti_cheat"]["runtime_closed"] = True
    return row


def row_from_queue(item: dict, index: int, split: str) -> dict:
    clean = item["clean_decoder_text"]
    row = {
        "language_family": item["language_family"],
        "episode_id": f"stage9484_episode_{item['queue_id']}",
        "step_id": f"stage9484_step_{item['queue_id']}",
        "step_index": 0,
        "phase": "verify",
        "source_stage9482_queue_id": item["queue_id"],
        "episode_transition": {
            "state_t": {
                "active_generation_prefix_span": item["active_generation_prefix_span"],
                "bridge_error_family": "target_prefix_observe_phase",
                "prefix_token_bucket": "short",
                "route": "VERIFY_TARGET_PREFIX_RELATION",
                "suffix_prior_available": True,
                "target_prefix_observe_variant": item["task_kind"],
            },
            "action_t": {"action": "VERIFY_TARGET_PREFIX_MATCH", "emission_surface_family": "observe_phase_verifier"},
            "observation_t": {
                "generated_text": item["clean_generated_text"],
                "target_prefix_match": True,
                "boundary_next_token_match": True,
                "boundary_expected_rank": 1,
                "short_or_junk": False,
                "degenerate_repetition": False,
                "stopped_on_eos": True,
                "residual_reasons": [],
            },
            "reward_or_verifier": {"failure_type": "none", "reward": 1.0, "step_passed": True, "verifier_source": "stage9482_constructed_positive_queue"},
            "state_t_plus_1": {"decoder_text": clean, "repair_outcome": "verified_target_prefix_positive", "target_suffix_choice": item["task_kind"]},
        },
        "training_candidate": {"decoder_ce_closed": True, "denoise_ce_closed": True, "episode_step_structured_supervision": True, "model_execution_authorized_now": False, "runtime_reward_closed": True},
        "transition_schema": "episode_step_suffix_transition_v1",
    }
    return configure_row(row, row_id=f"stage9484_observe_queue_{index:04d}", split=split, source_kind="stage9482_queue_positive")


def append_structured(parts: list[str], prefix: str, payload: dict) -> None:
    for key in sorted(payload):
        if key.endswith("_id") or key in {"row_id", "target", "decoder_text", "source_ref", "path"}:
            continue
        value = payload[key]
        if isinstance(value, (str, int, float, bool)):
            parts.append(f"{prefix}.{key}={value}")
        elif isinstance(value, list):
            scalar = [item for item in value if isinstance(item, (str, int, float, bool))]
            if scalar:
                parts.append(f"{prefix}.{key}.count={len(scalar)}")
                for item in scalar[:12]:
                    parts.append(f"{prefix}.{key}.item={item}")


def encoder_text(row: dict) -> str:
    parts: list[str] = []
    for key, prefix in [("language_family", "language"), ("route", "route"), ("objective_family", "objective")]:
        if row.get(key):
            parts.append(f"{prefix}={row.get(key)}")
    transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    append_structured(parts, "episode.state", transition.get("state_t") if isinstance(transition.get("state_t"), dict) else {})
    append_structured(parts, "episode.action", transition.get("action_t") if isinstance(transition.get("action_t"), dict) else {})
    append_structured(parts, "model", row.get("model_input") if isinstance(row.get("model_input"), dict) else {})
    return " | ".join(parts).lower()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    design = load_json(SOURCE_DESIGN)
    balance_rows = read_jsonl(SOURCE_BALANCE)
    queue_rows = read_jsonl(SOURCE_QUEUE)
    rows: list[dict] = []
    for index, source in enumerate(balance_rows):
        source_id = source["row_id"]
        split = "eval" if source_id in EVAL_FALSE else "strict_eval" if source_id in STRICT_FALSE else "train"
        configured = configure_row(source, row_id=f"stage9484_observe_source_{index:04d}", split=split, source_kind="stage9479_existing")
        configured["source_stage9479_row_id"] = source_id
        rows.append(configured)
    for index, item in enumerate(queue_rows):
        qid = item["queue_id"]
        split = "eval" if qid in EVAL_TRUE_QUEUE else "strict_eval" if qid in STRICT_TRUE_QUEUE else "train"
        rows.append(row_from_queue(item, index, split))
    write_jsonl(MANIFEST, rows)

    split_counts = Counter(row["split"] for row in rows)
    split_lang_label = Counter((row["split"], row.get("language_family"), target_prefix_label(row)) for row in rows)
    loss_counts = {key: sum(1 for row in rows if row["loss_mask"].get(key)) for key in LOSS_KEYS}
    visible_text = [encoder_text(row) for row in rows]
    label_leak_rows = [row["row_id"] for row, text in zip(rows, visible_text) if "target_prefix_match=true" in text or "target_prefix_match=false" in text]
    generated_visible_rows = sum(1 for text in visible_text if "generated_output_preview" in text)
    reference_visible_rows = sum(1 for text in visible_text if "reference_output_preview" in text)
    authority_rows = [row["row_id"] for row in rows if any(bool(value) for value in row.get("authority", {}).values())]
    generated_eq_reference_exact = sum(1 for row in rows if (row.get("model_input", {}).get("generated_output_preview") == row.get("model_input", {}).get("reference_output_preview")) == target_prefix_label(row)) / len(rows)
    language_majority = {}
    for lang in sorted({row.get("language_family") for row in rows}):
        labels = [target_prefix_label(row) for row in rows if row.get("language_family") == lang]
        if labels:
            majority = max(labels.count(True), labels.count(False)) / len(labels)
            language_majority[str(lang)] = majority
    failures: list[str] = []
    if design.get("passed") is not True:
        failures.append("source_stage9483_not_passed")
    if split_counts != {"eval": 6, "strict_eval": 6, "train": 54}:
        failures.append("unexpected_split_counts")
    for split in ["eval", "strict_eval"]:
        for lang in ["cpp", "python", "web_js_ts_html"]:
            if split_lang_label.get((split, lang, True), 0) != 1 or split_lang_label.get((split, lang, False), 0) != 1:
                failures.append(f"split_language_label_not_balanced:{split}:{lang}")
    if loss_counts.get("episode_target_prefix_match_ce") != len(rows):
        failures.append("target_prefix_loss_not_enabled_all_rows")
    for key, count in loss_counts.items():
        if key != "episode_target_prefix_match_ce" and count:
            failures.append(f"forbidden_loss_enabled:{key}")
    if label_leak_rows:
        failures.append("target_prefix_label_visible_in_encoder")
    if generated_visible_rows != len(rows) or reference_visible_rows != len(rows):
        failures.append("observe_phase_text_evidence_missing")
    if authority_rows:
        failures.append("authority_rows_present")

    card = {
        "passed": not failures,
        "failures": failures,
        "source_balance_manifest": str(SOURCE_BALANCE.relative_to(ROOT)),
        "source_queue": str(SOURCE_QUEUE.relative_to(ROOT)),
        "source_design": str(SOURCE_DESIGN.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "split_language_label_counts": {f"{split}::{lang}::{label}": count for (split, lang, label), count in sorted(split_lang_label.items(), key=lambda kv: str(kv[0]))},
        "loss_counts": loss_counts,
        "label_leak_rows": len(label_leak_rows),
        "generated_visible_rows": generated_visible_rows,
        "reference_visible_rows": reference_visible_rows,
        "authority_rows": len(authority_rows),
        "allowed_verifier_relation_baseline_generated_eq_reference_exact": generated_eq_reference_exact,
        "language_majority_baseline_by_language": language_majority,
        "design_note": "Observe-phase target-prefix manifest: generated/reference output evidence is visible, target_prefix_match label is hidden, and only episode_target_prefix_match_ce is enabled.",
        "authority": dict(AUTHORITY_CLOSED),
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    authority = dict(AUTHORITY_CLOSED)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": card["passed"],
        "authority": authority,
        "metrics": {**authority, **card},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Materialized target-prefix as an observe-phase verifier objective with generated/reference evidence visible and target-prefix label hidden.",
        "next_best_step": "Run Stage9485 contract-only preflight for the observe-phase target-prefix target-100M structured probe; do not execute until preflight passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9484 Target-Prefix Observe-Phase Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{len(rows)}`",
        f"Splits: `{dict(sorted(split_counts.items()))}`",
        f"Label leak rows: `{len(label_leak_rows)}`",
        f"Generated evidence visible rows: `{generated_visible_rows}`",
        f"Reference evidence visible rows: `{reference_visible_rows}`",
        "",
        "This manifest moves target-prefix from hidden-observation pre-action guessing to observe-phase verifier training. Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.",
        "",
    ]))
    registry = json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": authority, "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = bool(reg_rows)
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows)}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures, "rows": len(rows), "split_counts": dict(split_counts)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
